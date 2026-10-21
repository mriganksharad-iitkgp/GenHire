from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from bson import ObjectId
import requests
from workflow_test_support import MongoTestCase
from assessment_test_fixtures import sql, coding, executor_results
from models.hiring_workflow import WorkflowError
from services.sphere_engine_service import SphereEngineClient
from services.sql_execution_service import SqlExecutionService
from services.managed_assessment_validator import ManagedAssessmentValidator
from services.assessment_validation_jobs import AssessmentValidationJobs
from services.assessment_authoring_service import AssessmentAuthoringService, ensure_authoring_indexes
from services.assessment_executor_preflight import canaries, security_review, REVIEW_CHECKS
from models.assessment_content import validate_question


class Response:
    def __init__(self, value, status=200): self.data, self.status_code = value, status
    def iter_content(self, chunk_size): yield self.data.encode() if isinstance(self.data, str) else json.dumps(self.data).encode()
    def json(self): return self.data
    def close(self): pass


class SphereContractTests(unittest.TestCase):
    def test_public_diagnostics_are_bounded_and_redact_token_urls_and_controls(self):
        class Session:
            def request(self, *args, **kwargs): return Response('PRIVATE_TOKEN https://vendor.test/path?access_token=PRIVATE_TOKEN\x1b[31m\nCompile failed')
        client = SphereEngineClient('https://fixture.compilers.sphere-engine.com/api/v4', 'PRIVATE_TOKEN', session=Session())
        result = client.diagnostics(42)
        self.assertNotIn('PRIVATE_TOKEN', result); self.assertNotIn('https://', result); self.assertNotIn('\x1b', result)
        self.assertIn('Compile failed', result)

    def test_sql_startup_timeout_is_infrastructure_and_query_timeout_is_candidate(self):
        spec = importlib.util.spec_from_file_location('oa_sql_runner_step6', Path(__file__).resolve().parents[2] / 'infra/oa_sql/runner.py')
        runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
        class Receiver:
            def __init__(self, query): self.query = query
            def poll(self, timeout): return self.query
            def recv(self): self.query = False; return {'phase': 'query'}
            def close(self): pass
        class Process:
            def start(self): pass
            def join(self, **kwargs): pass
            def is_alive(self): return False
        class Context:
            def __init__(self, query): self.receiver = Receiver(query)
            def Pipe(self, **kwargs): return self.receiver, Receiver(False)
            def Process(self, **kwargs): return Process()
        for query, expected in [(False, 'infrastructure_error'), (True, 'time_limit')]:
            with patch.object(runner.multiprocessing, 'get_context', return_value=Context(query)):
                self.assertEqual(runner.execute({'time_ms': 1000})['status'], expected)

    def test_vendor_payloads_version_pinning_and_token_uri_redaction(self):
        class Session:
            calls = []
            def request(inner, method, url, **kwargs):
                inner.calls.append((method, url, kwargs))
                if url.endswith('/compilers'): return Response(dict(items=[dict(id=1, name='Python', versions=[dict(id=7, name='3.12')], uri='https://secret?access_token=PRIVATE_TOKEN')]))
                if method == 'POST': return Response({'id': 42, 'number': 0}, 201)
                return Response(dict(executing=False, result=dict(status=dict(code=15), time=.01, memory=10,
                    streams=dict(source=dict(uri='https://secret?access_token=PRIVATE_TOKEN'), output=dict(size=2, uri='https://secret?access_token=PRIVATE_TOKEN')))))
        session = Session()
        client = SphereEngineClient('https://fixture.compilers.sphere-engine.com/api/v4', 'PRIVATE_TOKEN', session=session)
        self.assertNotIn('PRIVATE_TOKEN', json.dumps(client.compilers()))
        self.assertEqual(client.create_submission('print(2)', 1, 7, '', 2), 42)
        self.assertEqual(session.calls[-1][2]['data']['compilerVersionId'], 7)
        self.assertFalse(session.calls[-1][2]['allow_redirects'])
        self.assertNotIn('PRIVATE_TOKEN', json.dumps(client.submission(42)))
        problems = SphereEngineClient('https://fixture.problems.sphere-engine.com/api/v4', 'PRIVATE_TOKEN', 'problems', session)
        self.assertEqual(problems.create_problem('Echo', 'Echo input', 1), 42)
        self.assertEqual(problems.create_testcase(42, '2', '2', 1, 1), 0)
        problems.create_submission('source', 1, 7, problem_id=42)
        self.assertEqual(session.calls[-1][2]['data']['executionMode'], 'isolated')

    def test_missing_credentials_invalid_endpoints_and_ambiguous_posts_fail_closed(self):
        for endpoint in ['', 'http://fixture.compilers.sphere-engine.com/api/v4', 'https://evil.test/api/v4',
                         'https://fixture.compilers.sphere-engine.com/api/v4?secret=token',
                         'https://fixture.compilers.sphere-engine.com:invalid/api/v4']:
            with self.assertRaises(WorkflowError): SphereEngineClient(endpoint, 'token')
        class Session:
            def request(self, *args, **kwargs): raise requests.Timeout('https://vendor?access_token=PRIVATE_TOKEN')
        client = SphereEngineClient('https://fixture.compilers.sphere-engine.com/api/v4', 'PRIVATE_TOKEN', session=Session())
        with self.assertRaises(WorkflowError) as exc: client.create_submission('code', 1, 1)
        self.assertEqual(exc.exception.code, 'executor_dispatch_unknown')
        self.assertNotIn('PRIVATE_TOKEN', str(exc.exception))

    def test_live_acceptance_contracts_and_security_review_fail_closed(self):
        fixtures = canaries('test-no-execution')
        self.assertEqual(len(fixtures), 10)
        for _, q, _, _ in fixtures: self.assertEqual(validate_question(q), q)
        review = dict(policy_id='fixture-policy', reviewed_by='operator@example.test', evidence_reference='private-review-001',
            reviewed_at=datetime.now(timezone.utc).isoformat(), **{key: True for key in REVIEW_CHECKS})
        self.assertEqual(security_review(review, 'fixture-policy'), review)
        for update in [dict(policy_id='different'), dict(code_network_denied=False),
                dict(reviewed_at=(datetime.now(timezone.utc)-timedelta(days=8)).isoformat()), dict(reviewed_at='2026-01-01')]:
            with self.assertRaises(WorkflowError): security_review(dict(review, **update), 'fixture-policy')

    def test_runner_input_contract_is_importable_without_database_or_cloud_access(self):
        path = Path(__file__).resolve().parents[2] / 'infra/oa_sql/runner.py'
        spec = importlib.util.spec_from_file_location('_sql_runner_contract', path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        value = dict(schema_version=1, request_id='a'*24, engine='postgresql', engine_version='17',
            schema_sql='CREATE TABLE t(v int);', seed_sql='', query='SELECT 1', time_ms=1000, max_rows=1000)
        self.assertEqual(module.validate_request(value, 'postgresql', '17'), value)
        for update in [dict(engine_version='16'), dict(request_id='../escape'), dict(schema_version=True), dict(time_ms=10001), dict(max_rows=1000.0)]:
            with self.assertRaises(ValueError): module.validate_request(dict(value, **update), 'postgresql', '17')


class SqlAdmissionTests(MongoTestCase):
    def setUp(self):
        super().setUp()
        self.env = patch.dict(os.environ, {'GENHIRE_ASSESSMENT_EXECUTION_ENABLED': 'true', 'GENHIRE_SQL_PROJECT': 'genhire-fixture-project',
            'GENHIRE_SQL_REGION': 'europe-west1', 'GENHIRE_SQL_ARTIFACT_BUCKET': 'genhire-fixture-private', 'GENHIRE_SQL_POSTGRESQL_JOB': 'sql-pg',
            'GENHIRE_SQL_MONTHLY_EXECUTION_LIMIT': '200'})
        self.env.start(); self.addCleanup(self.env.stop)
        self.service = SqlExecutionService(self.db)

    def test_global_concurrency_and_monthly_quota_and_replay(self):
        ids = [str(ObjectId()), str(ObjectId())]
        def reserve(i):
            try: return self.service.reserve(i, sql(), 'sample1')['state']
            except WorkflowError as exc: return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(reserve, ids))
        self.assertCountEqual(results, ['reserved', 'sql_capacity'])
        winner = self.db.sql_execution_dispatches.find_one({})
        self.assertEqual(self.service.reserve(winner['_id'], sql(), 'sample1')['_id'], winner['_id'])
        self.assertEqual(self.db.sql_execution_limits.find_one({'_id': 'active'})['count'], 1)
        self.db.sql_execution_limits.update_one({'_id': 'active'}, {'$set': {'count': 0}})
        self.db.sql_execution_limits.update_one({'_id': winner['month']}, {'$set': {'count': 200}})
        with self.assertRaises(WorkflowError) as exc: self.service.reserve(str(ObjectId()), sql(), 'sample1')
        self.assertEqual(exc.exception.code, 'sql_monthly_limit')

    def test_unknown_cloud_post_is_not_dispatched_twice(self):
        class Blob:
            def upload_from_string(self, *a, **k): pass
        class Storage:
            def bucket(self, _): return self
            def blob(self, _): return Blob()
        class Session:
            calls = 0
            def post(inner, *a, **k): inner.calls += 1; raise requests.Timeout('private URL not returned')
        session = Session()
        service = SqlExecutionService(self.db, session=session, storage=Storage())
        request_id = str(ObjectId()); service.reserve(request_id, sql(), 'sample1')
        with self.assertRaises(WorkflowError): service.dispatch(request_id)
        with self.assertRaises(WorkflowError): service.dispatch(request_id)
        self.assertEqual(session.calls, 1)
        self.assertEqual(self.db.sql_execution_dispatches.find_one({})['state'], 'dispatch_unknown')
        self.assertEqual(self.db.sql_execution_limits.find_one({'_id': 'active'})['count'], 1)

    def test_flags_and_unsupported_versions_do_not_consume_quota(self):
        with patch.dict(os.environ, {'GENHIRE_ASSESSMENT_EXECUTION_ENABLED': 'false'}):
            with self.assertRaises(WorkflowError): self.service.reserve(str(ObjectId()), sql(), 'sample1')
        q = sql(); q['sql']['engine_version'] = '16'
        with self.assertRaises(WorkflowError): self.service.reserve(str(ObjectId()), q, 'sample1')
        self.assertEqual(self.db.sql_execution_limits.count_documents({}), 0)

    def test_no_live_attestation_means_no_managed_validation(self):
        validator = ManagedAssessmentValidator(self.db)
        self.assertFalse(validator.capabilities()['available'])
        with self.assertRaises(WorkflowError): validator.validate(coding(), 'hash')
        self.assertEqual(self.db.assessment_executor_dispatches.count_documents({}), 0)

    def test_sphere_quota_is_atomic_idempotent_and_counts_unknown_dispatches(self):
        validator = ManagedAssessmentValidator(self.db)
        with patch.dict(os.environ, {'GENHIRE_SPHERE_MONTHLY_SUBMISSION_LIMIT': '1'}):
            def reserve(key):
                try: return validator.reserve_submission(key)
                except WorkflowError as exc: return exc.code
            with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(reserve, ['a', 'b']))
            self.assertCountEqual(results, [True, 'sphere_monthly_limit'])
            winner = self.db.assessment_executor_dispatches.find_one({})
            self.assertFalse(validator.reserve_submission(winner['_id']))
            self.db.assessment_executor_dispatches.update_one({'_id': winner['_id']}, {'$set': {'state': 'dispatch_unknown'}})
            self.assertFalse(validator.reserve_submission(winner['_id']))
            self.assertEqual(self.db.assessment_executor_limits.find_one({})['count'], 1)
            with self.assertRaises(WorkflowError): validator.reserve_submission('another')


class ValidationQueueTests(MongoTestCase):
    def test_real_queue_storage_with_fake_executor_checks_worker_ownership_and_idempotency(self):
        ensure_authoring_indexes(self.db)
        actor = dict(_id=ObjectId(), user_type='recruiter', is_verified=True)
        self.db.users.insert_one(actor)
        authoring = AssessmentAuthoringService(self.db)
        question = authoring.save_question(actor, coding('function'), 'queue-question-key')
        class FakeExecutor:
            def capabilities(self): return dict(available=True)
            def validate(self, q, _): return executor_results(q)
        queue = AssessmentValidationJobs(self.db, FakeExecutor())
        job = queue.enqueue(actor, question['_id'], 'queue-validation-key')
        self.assertEqual(queue.enqueue(actor, question['_id'], 'queue-validation-key'), job)
        self.assertTrue(queue.run_once())
        self.assertEqual(queue.get(actor, job['id'])['state'], 'completed')
        self.assertTrue(authoring.get_question(actor, question['_id'])['validation']['passed'])
        # The test fake cannot make production publication available.
        self.assertFalse(authoring.validator.capabilities()['available'])
        job2 = queue.enqueue(actor, question['_id'], 'queue-revoked-key')
        self.db.users.update_one({'_id': actor['_id']}, {'$set': {'is_verified': False}})
        queue.run_once()
        self.assertEqual(queue.get(actor, job2['id'])['state'], 'failed')


if __name__ == '__main__': unittest.main()
