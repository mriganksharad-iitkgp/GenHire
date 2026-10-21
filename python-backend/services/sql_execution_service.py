"""SQL Cloud Run admission and dispatch, using private artifact references.

Durable intent precedes each external POST. Unknown outcomes hold their slot
for reconciliation; they are not automatically dispatched a second time.
"""
from datetime import datetime, timezone
import json
import os
import re
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from core.mongo_transactions import atomic
from models.hiring_workflow import WorkflowError
from models.assessment_content import validate_question
from services.workflow_service import request_identity


class SqlExecutionService:
    def __init__(self, db, session=None, storage=None):
        self.db, self.session, self.storage = db, session, storage

    def settings(self):
        from config.assessment_execution import enabled
        if not enabled(): raise WorkflowError('execution_disabled', 'Assessment execution is disabled.', 503)
        project, region = os.getenv('GENHIRE_SQL_PROJECT', ''), os.getenv('GENHIRE_SQL_REGION', 'europe-west1')
        bucket = os.getenv('GENHIRE_SQL_ARTIFACT_BUCKET', '')
        if not re.fullmatch(r'[a-z][a-z0-9-]{4,61}[a-z0-9]', project) or region != 'europe-west1' or not re.fullmatch(r'[a-z0-9][a-z0-9_.-]{2,61}', bucket):
            raise WorkflowError('sql_not_configured', 'SQL project, region and private artifact bucket must be configured.', 503)
        return project, region, bucket

    def clients(self):
        if self.session is None:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
            credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
            self.session = AuthorizedSession(credentials)
        if self.storage is None:
            from google.cloud import storage
            self.storage = storage.Client(project=os.environ['GENHIRE_SQL_PROJECT'])

    def reserve(self, request_id, question, case_id):
        self.settings()
        q = validate_question(question)
        if q['type'] != 'sql': raise WorkflowError('invalid_type', 'A SQL question is required.', 400)
        if q['sql']['engine_version'] != ('17' if q['sql']['engine'] == 'postgresql' else '8.4'):
            raise WorkflowError('unsupported_sql_version', 'The SQL pilot requires PostgreSQL 17 or MySQL 8.4.', 400)
        job = os.getenv('GENHIRE_SQL_POSTGRESQL_JOB' if q['sql']['engine'] == 'postgresql' else 'GENHIRE_SQL_MYSQL_JOB', '')
        if not re.fullmatch(r'[a-z][a-z0-9-]{0,62}', job):
            raise WorkflowError('sql_not_configured', 'SQL job is not configured; no quota has been reserved.', 503)
        if not isinstance(request_id, str) or not re.fullmatch(r'[a-f0-9]{24}', request_id): raise WorkflowError('invalid_id', 'Invalid execution request ID.', 400)
        case = next((data for data in q['sql']['datasets'] if data['id'] == case_id), None)
        if not case: raise WorkflowError('invalid_case', 'Unknown SQL dataset.', 400)
        payload = dict(schema_version=1, request_id=request_id, engine=q['sql']['engine'], engine_version=q['sql']['engine_version'],
            schema_sql=q['sql']['schema_sql'], seed_sql=case['seed_sql'], query=q['sql']['reference_query'], time_ms=q['sql']['time_ms'], max_rows=1000)
        digest = request_identity(payload)
        month = datetime.now(timezone.utc).strftime('%Y-%m')
        try: limit = int(os.getenv('GENHIRE_SQL_MONTHLY_EXECUTION_LIMIT', '200'))
        except ValueError: raise WorkflowError('invalid_sql_quota', 'Invalid SQL quota.', 503) from None
        if not 1 <= limit <= 200: raise WorkflowError('invalid_sql_quota', 'SQL pilot quota must be 1–200 executions/month.', 503)
        def reserve(session):
            old = self.db.sql_execution_dispatches.find_one({'_id': request_id}, session=session)
            if old:
                if old['request_hash'] != digest: raise WorkflowError('idempotency_conflict', 'SQL execution ID reused with different content.')
                return old
            month_counter = self.db.sql_execution_limits.find_one({'_id': month}, session=session)
            active = self.db.sql_execution_limits.find_one({'_id': 'active'}, session=session)
            if (month_counter or {}).get('count', 0) >= limit: raise WorkflowError('sql_monthly_limit', 'Monthly SQL execution quota reached.', 429)
            if (active or {}).get('count', 0) >= 1: raise WorkflowError('sql_capacity', 'A SQL execution is already active; retry later.', 429)
            for scope in (month, 'active'):
                self.db.sql_execution_limits.update_one({'_id': scope}, {'$inc': {'count': 1}}, upsert=True, session=session)
            record = dict(_id=request_id, request_hash=digest, payload=payload, state='reserved', month=month,
                created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
            self.db.sql_execution_dispatches.insert_one(record, session=session)
            return record
        try: return atomic(self.db, reserve)
        except DuplicateKeyError: return atomic(self.db, reserve)

    def dispatch(self, request_id):
        project, region, bucket_name = self.settings()
        record = self.db.sql_execution_dispatches.find_one({'_id': request_id})
        if not record: raise WorkflowError('not_found', 'SQL execution was not reserved.', 404)
        if record['state'] in {'running', 'completed'}: return {k: record[k] for k in ('_id', 'state', 'operation')}
        if record['state'] != 'reserved': raise WorkflowError('dispatch_reconciliation_required', 'SQL dispatch outcome requires reconciliation; it will not be submitted again.', 503)
        engine = record['payload']['engine']
        expected = '17' if engine == 'postgresql' else '8.4'
        if record['payload']['engine_version'] != expected: raise WorkflowError('unsupported_sql_version', f'The SQL pilot requires {engine} {expected}.', 400)
        job = os.getenv('GENHIRE_SQL_POSTGRESQL_JOB' if engine == 'postgresql' else 'GENHIRE_SQL_MYSQL_JOB', '')
        if not re.fullmatch(r'[a-z][a-z0-9-]{0,62}', job): raise WorkflowError('sql_not_configured', 'SQL job is not configured.', 503)
        self.clients()
        path = f'sql-validation/requests/{request_id}.json'
        blob = self.storage.bucket(bucket_name).blob(path)
        content = json.dumps(record['payload'], allow_nan=False, separators=(',', ':'))
        try:
            blob.upload_from_string(content, content_type='application/json', if_generation_match=0, timeout=20)
        except Exception:
            # An existing immutable artifact is acceptable only if its exact hash matches.
            try:
                blob.reload(timeout=10)
                if blob.size > 512000 or request_identity(json.loads(blob.download_as_bytes(timeout=10))) != record['request_hash']:
                    raise ValueError('Artifact differs')
            except Exception: raise WorkflowError('sql_artifact_unavailable', 'Private SQL request artifact could not be confirmed.', 503) from None
        changed = self.db.sql_execution_dispatches.update_one({'_id': request_id, 'state': 'reserved'},
            {'$set': {'state': 'dispatching', 'updated_at': datetime.now(timezone.utc)}})
        if changed.matched_count != 1: raise WorkflowError('dispatch_reconciliation_required', 'Another worker owns this SQL dispatch.', 503)
        url = f'https://run.googleapis.com/v2/projects/{project}/locations/{region}/jobs/{job}:run'
        body = dict(overrides=dict(taskCount=1, timeout='60s', containerOverrides=[dict(env=[
            dict(name='SQL_REQUEST_BUCKET', value=bucket_name), dict(name='SQL_REQUEST_OBJECT', value=path),
            dict(name='SQL_RESULT_OBJECT', value=f'sql-validation/results/{request_id}.json')])]))
        response = None
        try:
            response = self.session.post(url, json=body, timeout=(5, 20), allow_redirects=False)
            if response.status_code != 200: raise ValueError('Run request rejected')
            operation = response.json().get('name')
            prefix = f'projects/{project}/locations/{region}/operations/'
            if not isinstance(operation, str) or not operation.startswith(prefix) or not re.fullmatch(r'[a-zA-Z0-9_-]+', operation[len(prefix):]):
                raise ValueError('Unexpected operation name')
            self.db.sql_execution_dispatches.update_one({'_id': request_id, 'state': 'dispatching'},
                {'$set': {'state': 'running', 'operation': operation, 'updated_at': datetime.now(timezone.utc)}})
            return dict(_id=request_id, state='running', operation=operation)
        except Exception:
            self.db.sql_execution_dispatches.update_one({'_id': request_id, 'state': 'dispatching'}, {'$set': {'state': 'dispatch_unknown'}})
            raise WorkflowError('dispatch_reconciliation_required', 'Cloud dispatch could not be confirmed; reconcile before retrying.', 503) from None
        finally:
            if response is not None: response.close()

    def result(self, request_id):
        _, _, bucket_name = self.settings()
        record = self.db.sql_execution_dispatches.find_one({'_id': request_id})
        if not record: raise WorkflowError('not_found', 'Unknown SQL execution.', 404)
        if record['state'] == 'completed': return record['result']
        if record['state'] not in {'running', 'dispatch_unknown', 'dispatching'}: raise WorkflowError('sql_result_pending', 'SQL execution is not ready for result collection.', 409)
        self.clients()
        blob = self.storage.bucket(bucket_name).blob(f'sql-validation/results/{request_id}.json')
        try:
            blob.reload(timeout=10)
            if blob.size > 1048576: raise ValueError('Result too large')
            value = json.loads(blob.download_as_bytes(timeout=10))
            if (not isinstance(value, dict) or value.get('request_id') != request_id or value.get('request_hash') != record['request_hash']
                    or value.get('engine') != record['payload']['engine'] or value.get('engine_version') != record['payload']['engine_version']):
                raise ValueError('Result mismatch')
        except Exception: raise WorkflowError('sql_result_pending', 'SQL result is unavailable or not yet verified.', 409) from None
        def settle(session):
            current = self.db.sql_execution_dispatches.find_one({'_id': request_id}, session=session)
            if current['state'] == 'completed': return current['result']
            self.db.sql_execution_dispatches.update_one({'_id': request_id, 'state': {'$in': ['running', 'dispatch_unknown', 'dispatching']}},
                {'$set': {'state': 'completed', 'result': value, 'updated_at': datetime.now(timezone.utc)}}, session=session)
            self.db.sql_execution_limits.update_one({'_id': 'active', 'count': {'$gte': 1}}, {'$inc': {'count': -1}}, session=session)
            return value
        return atomic(self.db, settle)
