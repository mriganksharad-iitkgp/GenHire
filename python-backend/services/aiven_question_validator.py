"""Trusted operator-only PostgreSQL reference validation. Never a candidate judge."""
from datetime import date, datetime
from decimal import Decimal
import os
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
import uuid
from models.hiring_workflow import WorkflowError
from models.assessment_content import validate_question
from services.assessment_validation import sql_rows_equal
from services.sql_result_codec import readonly_query


class AivenQuestionValidator:
    def __init__(self,connect=None):self.connect=connect

    def settings(self):
        if os.getenv('OA_POSTGRES_QUESTION_AUTHORING_ENABLED','true').lower()!='true':
            raise WorkflowError('postgres_authoring_disabled','PostgreSQL authoring is disabled.',503)
        if os.getenv('AIVEN_POSTGRES_SSL_REQUIRED','true').lower()!='true' or os.getenv('AIVEN_POSTGRES_PURPOSE','question_validation')!='question_validation':
            raise WorkflowError('invalid_aiven_configuration','Aiven requires SSL and the trusted question_validation purpose.',503)
        uri=os.getenv('AIVEN_POSTGRES_URL','').strip()
        try:
            parsed=urlsplit(uri)
            valid=parsed.scheme in ('postgres','postgresql') and parsed.hostname and parsed.hostname.endswith('.aivencloud.com') and parsed.username and parsed.password and parsed.path not in ('','/')
            query=parse_qs(parsed.query)
        except ValueError:valid=False;query={}
        if not valid:raise WorkflowError('aiven_not_configured','Set the dedicated Aiven PostgreSQL service URL.',503)
        cert=os.getenv('AIVEN_POSTGRES_SSL_ROOT_CERT','').strip() or (query.get('sslrootcert') or [''])[0]
        if not cert or not Path(cert).is_file():raise WorkflowError('aiven_ca_required','Supply the Aiven service CA certificate file for verify-full TLS.',503)
        return uri,dict(sslmode='verify-full',sslrootcert=cert,connect_timeout=10,application_name='genhire_trusted_question_validation')

    @staticmethod
    def cell(value):
        if isinstance(value,Decimal):return int(value) if value==value.to_integral_value() else float(value)
        if isinstance(value,(date,datetime)):return value.isoformat()
        if type(value) not in (type(None),str,int,float,bool):raise WorkflowError('unsupported_postgres_result','Cast unsupported PostgreSQL result types explicitly in the reference query.',400)
        return value

    def validate(self,question,*,trusted_reference=False):
        if trusted_reference is not True:raise WorkflowError('trusted_reference_required','Only explicitly approved operator-authored SQL may access Aiven.',403)
        q=validate_question(question)
        if q['type']!='sql' or q['sql']['engine']!='postgresql':raise WorkflowError('invalid_type','A PostgreSQL question is required.',400)
        if q['sql']['engine_version'].split('.')[0]!='18':raise WorkflowError('postgres_version_mismatch','The trusted question must target PostgreSQL 18.',400)
        query=readonly_query(q['sql']['reference_query'])
        uri,options=self.settings()
        connect=self.connect
        if connect is None:
            try:import psycopg2
            except ImportError:raise WorkflowError('aiven_driver_missing','Install the backend PostgreSQL dependency.',503) from None
            connect=psycopg2.connect
        connection=None
        try:
            connection=connect(uri,**options);cursor=connection.cursor()
            cursor.execute('SHOW server_version_num');version=int(cursor.fetchone()[0])
            if not 180000<=version<190000:raise WorkflowError('postgres_version_mismatch','The trusted development service must run PostgreSQL 18.',503)
            runs=[]
            for case in q['sql']['datasets']:
                schema='gh_validation_'+uuid.uuid4().hex
                cursor.execute('CREATE SCHEMA '+schema)
                cursor.execute('SET LOCAL search_path TO '+schema+', pg_catalog')
                cursor.execute('SET LOCAL statement_timeout = %s',(min(q['sql']['time_ms'],10000),))
                cursor.execute("SET LOCAL lock_timeout = '2s'")
                cursor.execute(q['sql']['schema_sql'])
                if case['seed_sql'].strip():cursor.execute(case['seed_sql'])
                cursor.execute(query)
                if cursor.description is None:raise WorkflowError('invalid_postgres_reference','The trusted reference must return a result set.',400)
                columns=[column[0] for column in cursor.description]
                rows=[[self.cell(cell) for cell in row] for row in cursor.fetchmany(1001)]
                if len(rows)>1000:raise WorkflowError('postgres_output_limit','Trusted result exceeds the 1000-row budget.',400)
                runs.append(dict(case_id=case['id'],passed=columns==case['columns'] and sql_rows_equal(rows,case['expected_rows'],q['sql']['ordered'],q['sql']['numeric_tolerance']),row_count=len(rows)))
            return dict(provider='aiven',purpose='question_validation',postgres_version=version,passed=all(r['passed'] for r in runs),
                candidate_execution_allowed=False,publishable_for_candidate_execution=False,runs=runs)
        except WorkflowError:raise
        except Exception:raise WorkflowError('aiven_validation_failed','Trusted PostgreSQL connection or reference validation failed; inspect private service logs.',503) from None
        finally:
            if connection is not None:
                cleanup_failed=False
                try:connection.rollback()
                except Exception:cleanup_failed=True
                try:connection.close()
                except Exception:cleanup_failed=True
                if cleanup_failed:raise WorkflowError('aiven_cleanup_failed','Trusted validation cleanup failed; inspect private service logs.',503) from None
