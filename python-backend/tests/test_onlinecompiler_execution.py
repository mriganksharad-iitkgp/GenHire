"""Synthetic contracts and disposable-Mongo dispatch safety; no live attestation."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import mongomock
import requests
import workflow_test_support
from models.hiring_workflow import WorkflowError
from services.onlinecompiler_execution_provider import OnlineCompilerExecutionProvider as Provider
from services.sql_result_codec import readonly_query, sql_source, sql_result
from services.aiven_question_validator import AivenQuestionValidator
from services.assessment_executor_preflight import canaries, security_review
from services.managed_assessment_validator import ManagedAssessmentValidator
from assessment_test_fixtures import sql, coding


class Response:
    def __init__(self,data,status=200):self.data,self.status_code=data,status
    def iter_content(self,size):yield json.dumps(self.data).encode()
    def close(self):pass


class Session:
    def __init__(self,data,status=200):self.data,self.status,self.calls=data,status,[]
    def request(self,method,url,**kwargs):
        self.calls.append((method,url,kwargs))
        if isinstance(self.data,Exception):raise self.data
        return Response(self.data,self.status)


def raw(**changes):return dict(dict(status='success',exit_code=0,output='2\n',error='',time='0.012',memory='1024',signal=None,truncated=False),**changes)


SETTINGS={'ONLINECOMPILER_API_KEY':'SYNTHETIC_PRIVATE_KEY','ONLINECOMPILER_API_BASE_URL':'https://api.onlinecompiler.io',
    'OA_EXECUTION_PROVIDER':'onlinecompiler','OA_GENERIC_SQL_PROVIDER':'onlinecompiler',
    'OA_MAX_CONCURRENT_EXECUTIONS':'2','ONLINECOMPILER_RUNS_PER_MINUTE':'30','ONLINECOMPILER_TEST_BATCH_SIZE':'4',
    'GENHIRE_ASSESSMENT_EXECUTION_ENABLED':'true','GENHIRE_EXECUTOR_ISOLATION_POLICY_ID':'test-policy'}


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,SETTINGS);self.env.start();self.addCleanup(self.env.stop)
        self.db=mongomock.MongoClient().db
        self.tx=patch('services.onlinecompiler_execution_provider.atomic',side_effect=lambda db,fn:fn(None))
        self.tx.start();self.addCleanup(self.tx.stop)

    def test_server_only_header_and_replay_safety(self):
        session=Session(raw());p=Provider(self.db,session)
        self.assertEqual(p.execute('id','python-3.14','print(2)'),p.execute('id','python-3.14','print(2)'))
        method,url,options=session.calls[0]
        self.assertEqual((method,url),('POST','https://api.onlinecompiler.io/api/run-code-sync/'))
        self.assertEqual(options['headers'],{'Authorization':SETTINGS['ONLINECOMPILER_API_KEY']})
        self.assertFalse(options['allow_redirects']);self.assertEqual(len(session.calls),1)
        self.assertNotIn(SETTINGS['ONLINECOMPILER_API_KEY'],str(self.db.oa_provider_requests.find_one({})))
        with self.assertRaises(WorkflowError):p.execute('id','python-3.14','print(3)')

    def test_ambiguous_dispatch_is_never_retried_and_retains_capacity(self):
        session=Session(requests.Timeout('PRIVATE_ERROR'));p=Provider(self.db,session)
        for _ in range(2):
            with self.assertRaises(WorkflowError) as error:p.execute('id','python-3.14','print(2)')
            self.assertNotIn('PRIVATE_ERROR',str(error.exception))
        self.assertEqual(len(session.calls),1)
        self.assertEqual(self.db.oa_provider_requests.find_one({})['state'],'dispatch_unknown')
        self.assertEqual(self.db.oa_provider_limits.find_one({'_id':'active'})['count'],1)

    def test_known_rate_quota_and_auth_rejections_release_capacity(self):
        for status,data,code in [(429,{'error':'monthly quota'},'provider_quota_exhausted'),(429,{'error':'rate'},'provider_rate_limit'),(401,{},'provider_authentication_failed')]:
            session=Session(data,status);p=Provider(self.db,session)
            with self.assertRaises(WorkflowError) as error:p.execute(str(status)+code,'python-3.14','print(2)')
            self.assertEqual(error.exception.code,code)
            self.assertEqual(self.db.oa_provider_limits.find_one({'_id':'active'})['count'],0)

    def test_native_weighted_tests_count_runs_and_strip_hidden_data(self):
        cases=[dict(input='2',expected_output='4',hidden=False,weight=1),dict(input='4',expected_output='8',hidden=True,weight=3)]
        session=Session(dict(total=2,passed=1,score=75,tests=[dict(verdict='wrong_answer',hidden=False,time='0.1',memory='1024'),dict(verdict='accepted',hidden=True,output='PRIVATE',error='PRIVATE',time=1)]))
        result=Provider(self.db,session).judge('judge','python-3.14','print(input())',cases)
        self.assertEqual([r['passed'] for r in result],[False,True]);self.assertEqual(result[1],dict(status='ok',passed=True,native_judged=True))
        payload=session.calls[0][2]['json'];self.assertEqual(payload['scoring'],'weighted');self.assertFalse(payload['stop_on_failure'])
        record=self.db.oa_provider_requests.find_one({});self.assertEqual((record['estimated_runs'],record['actual_runs']),(2,2))

    def test_native_malformed_visibility_or_count_never_scores(self):
        cases=[dict(input='',expected_output='',hidden=True,weight=1)]
        for response in ({'total':1,'tests':[dict(verdict='accepted',hidden=False)]},{'total':2,'tests':[]}):
            with self.assertRaises(WorkflowError):Provider().normalize_judging(response,cases)

    def test_resources_and_provider_limits_are_normalized(self):
        p=Provider()
        self.assertEqual(p.normalize(raw())['time_ms'],12)
        for changes,status in [({'exit_code':124},'time_limit'),({'exit_code':137},'memory_limit'),({'exit_code':153},'output_limit'),({'truncated':True},'output_limit'),({'exit_code':1,'error':'SyntaxError'},'compile_error'),({'exit_code':1},'runtime_error')]:
            self.assertEqual(p.normalize(raw(**changes))['status'],status)

    def test_secret_destinations_and_oversized_inputs_fail_before_network(self):
        for endpoint in ('http://api.onlinecompiler.io','https://evil.example','https://secret@api.onlinecompiler.io','https://api.onlinecompiler.io?secret=x'):
            with patch.dict(os.environ,{'ONLINECOMPILER_API_BASE_URL':endpoint}),self.assertRaises(WorkflowError):Provider().settings()
        for value in ('x\0','x'*100001,'雪'*40000):
            with self.assertRaises(WorkflowError):Provider.validate_text(value)
        with patch.dict(os.environ,{'ONLINECOMPILER_API_KEY':''}),self.assertRaises(WorkflowError):Provider().settings()

    def test_capacity_and_rate_reservation_prevents_dispatch(self):
        session=Session(raw());p=Provider(self.db,session)
        self.db.oa_provider_limits.insert_one(dict(_id='active',count=2))
        with self.assertRaises(WorkflowError) as error:p.execute('busy','python-3.14','print(2)')
        self.assertEqual(error.exception.code,'provider_capacity');self.assertEqual(session.calls,[])
        self.db.oa_provider_limits.delete_many({})
        with patch.dict(os.environ,{'ONLINECOMPILER_RUNS_PER_MINUTE':'1'}):
            p.execute('one','python-3.14','print(2)')
            with self.assertRaises(WorkflowError) as error:p.execute('two','python-3.14','print(2)')
            self.assertEqual(error.exception.code,'provider_rate_limit')

    def test_postgres_candidate_guard_and_live_attestation_remain_closed(self):
        with self.assertRaises(WorkflowError):ManagedAssessmentValidator.check_runtime(sql('postgresql'),'sql')
        self.assertFalse(ManagedAssessmentValidator(self.db).capabilities()['available'])
        with self.assertRaises(WorkflowError):security_review({},'test-policy')
        for _,question,_,_ in canaries('synthetic'):
            for language in question['coding']['languages']:ManagedAssessmentValidator.check_runtime(question,language)


class SQLCodecTests(unittest.TestCase):
    def frame(self,columns,rows):
        values=[[dict(gh_frame='marker',gh_columns=json.dumps(columns))]]+([rows] if rows else [])+[[dict(gh_end='marker')]]
        return '\n'.join(json.dumps(value,ensure_ascii=False) for value in values)

    def test_null_unicode_duplicates_empty_and_actual_column_names(self):
        rows=[dict(actual_alias=1.25,label='NULL\t雪',missing=None)]*2
        result=sql_result(dict(status='ok',stdout=self.frame(['actual_alias','label','missing'],rows)),'marker')
        self.assertEqual(result['rows'],[[1.25,'NULL\t雪',None]]*2)
        self.assertEqual(sql_result(dict(status='ok',stdout=self.frame(['actual_alias'],[])),'marker')['columns'],['actual_alias'])

    def test_truncated_untyped_and_nested_outputs_fail_closed(self):
        for text in ('value\n2',self.frame(['value'],[dict(value=2)]).replace('gh_end','wrong'),self.frame(['value'],[dict(value={})])):
            with self.assertRaises(WorkflowError):sql_result(dict(status='ok',stdout=text),'marker')

    def test_duckdb_numeric_strings_use_actual_types_and_text_stays_text(self):
        metadata=[dict(gh_frame='marker',gh_columns='["total","label","amount"]',gh_types='["HUGEINT","VARCHAR","DECIMAL(38,2)"]')]
        records=[dict(total='6',label='6',amount='1.25')]
        text='\n'.join(json.dumps(value) for value in [metadata,records,[dict(gh_end='marker')]])
        result=sql_result(dict(status='ok',stdout=text),'marker')
        self.assertEqual(result['rows'],[[6,'6',1.25]])

    def test_sql_queries_cannot_inject_client_commands_or_multiple_statements(self):
        for query in ('DROP TABLE x','SELECT 1; SELECT 2','SELECT 1 --hidden','SELECT 1\n.shell whoami','SELECT 1 INTO OUTFILE \'x\'','WITH x AS (DELETE FROM t RETURNING *) SELECT * FROM x'):
            with self.assertRaises(WorkflowError):readonly_query(query)
        self.assertEqual(readonly_query("SELECT ';' AS value;"),"SELECT ';' AS value")
        for engine in ('sqlite','duckdb'):
            source,marker=sql_source(engine,'CREATE TABLE t(n INT)','INSERT INTO t VALUES(2)','SELECT n FROM t','id')
            self.assertIn('CREATE TABLE t',source);self.assertIn('INSERT INTO t',source);self.assertIn(marker,source)


class AivenTests(unittest.TestCase):
    def test_explicit_trust_and_credentials_are_required(self):
        with self.assertRaises(WorkflowError) as error:AivenQuestionValidator().validate(sql('postgresql'))
        self.assertEqual(error.exception.code,'trusted_reference_required')
        with patch.dict(os.environ,{'AIVEN_POSTGRES_URL':''}),self.assertRaises(WorkflowError):AivenQuestionValidator().settings()

    def test_verified_tls_postgres18_transaction_cleanup_and_typed_results(self):
        class Cursor:
            description=[('value',)]
            def __init__(self):self.statements=[];self.seed=0
            def execute(self,statement,params=None):
                self.statements.append(statement)
                if 'INSERT INTO' in statement:self.seed=9371 if '9371' in statement else 2
            def fetchone(self):return [180001]
            def fetchmany(self,limit):return [[self.seed]]
        class Connection:
            def __init__(self):self.cur=Cursor();self.rolled_back=False;self.closed=False
            def cursor(self):return self.cur
            def rollback(self):self.rolled_back=True
            def close(self):self.closed=True
        connection=Connection();calls=[]
        def connect(uri,**kwargs):calls.append(kwargs);return connection
        with tempfile.TemporaryDirectory() as directory:
            cert=Path(directory)/'ca.pem';cert.write_text('synthetic fixture')
            with patch.dict(os.environ,{'AIVEN_POSTGRES_URL':'postgresql://test:synthetic@host.aivencloud.com:123/defaultdb?sslmode=require',
                'AIVEN_POSTGRES_SSL_ROOT_CERT':str(cert),'AIVEN_POSTGRES_SSL_REQUIRED':'true','AIVEN_POSTGRES_PURPOSE':'question_validation','OA_POSTGRES_QUESTION_AUTHORING_ENABLED':'true'}):
                result=AivenQuestionValidator(connect).validate(sql('postgresql'),trusted_reference=True)
        self.assertTrue(result['passed']);self.assertFalse(result['candidate_execution_allowed'])
        self.assertEqual(calls[0]['sslmode'],'verify-full');self.assertTrue(connection.rolled_back and connection.closed)
        self.assertEqual(sum(s.startswith('CREATE SCHEMA') for s in connection.cur.statements),2)


class TransactionTests(workflow_test_support.MongoTestCase):
    def setUp(self):
        super().setUp();self.env=patch.dict(os.environ,SETTINGS);self.env.start();self.addCleanup(self.env.stop)

    def test_concurrent_same_identity_posts_once(self):
        session=Session(raw());provider=Provider(self.db,session)
        def execute(_):
            try:return provider.execute('same','python-3.14','print(2)')['status']
            except WorkflowError as exc:return exc.code
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(execute,range(4)))
        self.assertIn('ok',results);self.assertTrue(set(results)<={'ok','dispatch_reconciliation_required'})
        self.assertEqual(len(session.calls),1);self.assertEqual(self.db.oa_provider_requests.count_documents({}),1)

    def test_unknown_survives_adapter_restart(self):
        session=Session(requests.Timeout('synthetic'))
        for _ in range(2):
            with self.assertRaises(WorkflowError):Provider(self.db,session).execute('unknown','python-3.14','print(2)')
        self.assertEqual(len(session.calls),1)

    def test_real_adapter_hidden_verdict_completes_durable_queue_without_output(self):
        from services.assessment_execution_service import AssessmentExecutionService, ensure_execution_indexes
        from config.assessment_execution import RUNTIMES
        ensure_execution_indexes(self.db)
        question=coding();question['coding']['runtime_versions']=dict(RUNTIMES)
        question['coding']['limits']['memory_mb']=512
        validator=ManagedAssessmentValidator(self.db,validation_mode=True)
        session=Session(dict(total=1,tests=[dict(verdict='accepted',hidden=True)]))
        validator.provider=Provider(self.db,session)
        engine=AssessmentExecutionService(self.db,lambda:datetime.now(timezone.utc),validator)
        task=engine.enqueue('native-task',question,'hidden1','python','print(input())','grading','synthetic-attempt')
        engine.tick()
        saved=self.db.assessment_execution_tasks.find_one({'_id':task['_id']})
        self.assertEqual(saved['state'],'complete');self.assertEqual(saved['result'],dict(status='ok',passed=True))
        self.assertEqual(session.calls[0][2]['json']['tests'][0]['expected_output'],'PRIVATE_OUTPUT_9371')
        self.assertEqual(self.db.assessment_execution_capacity.find_one({'_id':'global'})['active'],0)

    def test_retired_queued_task_is_preserved_blocked_and_releases_queue_counter(self):
        from services.assessment_execution_service import AssessmentExecutionService
        self.db.assessment_execution_tasks.insert_one(dict(identity='legacy',state='queued',provider='onecompiler',provider_id='old-id'))
        self.db.assessment_execution_capacity.insert_one(dict(_id='queue',count=1))
        engine=AssessmentExecutionService(self.db,lambda:datetime.now(timezone.utc))
        engine.tick();engine.tick()
        saved=self.db.assessment_execution_tasks.find_one({'identity':'legacy'})
        self.assertEqual(saved['state'],'blocked');self.assertEqual(saved['provider_id'],'old-id')
        self.assertEqual(self.db.assessment_execution_capacity.find_one({'_id':'queue'})['count'],0)
        with self.assertRaises(WorkflowError) as error:
            engine.reconcile(dict(_id='admin',user_type='admin',permissions=['*']),str(saved['_id']),'retry_confirmed','retired-retry-key','Verified historical record, do not replay.')
        self.assertEqual(error.exception.code,'retired_provider_reconciliation_required')
