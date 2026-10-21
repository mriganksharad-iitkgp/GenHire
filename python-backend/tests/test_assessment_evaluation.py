"""Local Mongo tests with explicitly fake transports; no actual code execution."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
import json
import os
import unittest
from unittest.mock import patch
from bson import ObjectId
import test_assessment_runtime as runtime_fixture
from assessment_test_fixtures import coding, mcq, sql
from models.assessment_content import candidate_question
from models.hiring_workflow import WorkflowError
from services.assessment_evaluation_service import AssessmentEvaluationService, ensure_evaluation_indexes
from services.assessment_execution_service import AssessmentExecutionService
from services.assessment_scoring import score, comparison, fixtures
from services.managed_assessment_validator import ManagedAssessmentValidator
from services.workflow_service import request_identity


class FakeClient:
    def __init__(self):
        self.calls, self.next_id = [], 100
        self.status, self.time, self.memory = 15, .01, 32
        self.stdout, self.size, self.fail_post, self.fail_get = 'PRIVATE_OUTPUT_9371', None, False, False
    def create_submission(self, source, compiler, version, input_text='', seconds=2):
        self.calls.append(dict(source=source, input=input_text, compiler=compiler, version=version))
        if self.fail_post: raise RuntimeError('TEST_ONLY_FAKE unknown POST')
        self.next_id += 1; return self.next_id
    def submission(self, identifier):
        if self.fail_get: raise RuntimeError('TEST_ONLY_FAKE unavailable GET')
        return dict(executing=False, status_code=self.status, compiler_id=1, compiler_version_id=2, output_size=self.size if self.size is not None else len(self.stdout), time=self.time, memory_kb=self.memory)
    def output(self, identifier, limit): return self.stdout


class FakeExecutor:
    def __init__(self, db): self.transport, self.available, self.db = FakeClient(), True, db
    def capabilities(self): return dict(available=self.available)
    def profile_hash(self): return 'TEST_ONLY_FAKE_PROFILE_NOT_AN_ATTESTATION'
    def client(self, product): return self.transport
    def reserve_submission(self, key): return ManagedAssessmentValidator(self.db).reserve_submission(key)


class ScoringTests(unittest.TestCase):
    def test_runtime_source_budget_is_accepted_by_code_and_sql_contracts(self):
        from services.assessment_public_run_service import AssessmentPublicRunService
        for question, language in [(coding('function'), 'python'), (sql(), 'sql')]:
            prepared, _ = AssessmentPublicRunService.prepare(question, dict(language=language, source='x'*64000), None)
            self.assertEqual(len(prepared[question['type']]['reference_solutions']['python'] if language == 'python' else prepared['sql']['reference_query']), 64000)
    def test_exact_multiple_mcq_no_negative_and_unanswered_zero(self):
        q = mcq(); q['mcq'].update(selection='multiple', correct_option_ids=['optionA', 'optionB'])
        config = dict(sections=[dict(type='mcq', weight=100)])
        for answer, expected in [(['optionA'], 0), (['optionB', 'optionA'], 100), ([], 0)]:
            result = score(config, {'q': q}, {'q': {'option_ids': answer}}, {})
            self.assertEqual(result['score'], expected)
        self.assertEqual(score(config, {'q': q}, {}, {})['score'], 0)

    def test_weighted_hidden_partial_credit_sections_and_pending(self):
        q = coding(); q['marks'] = 30
        q['coding']['tests'].append(dict(q['coding']['tests'][1], id='hidden2', weight=1))
        config = dict(sections=[dict(type='mcq', weight=40), dict(type='coding', weight=60)])
        answers = dict(m={'option_ids': ['optionA']}, c={'language': 'python', 'source': 'candidate source'})
        evidence = {('c', 'hidden1'): dict(status='ok', passed=True), ('c', 'hidden2'): dict(status='runtime_error', passed=False)}
        result = score(config, dict(m=mcq(), c=q), answers, evidence)
        self.assertEqual(result['score'], 80); self.assertEqual(result['questions'][1]['earned'], 20)
        self.assertEqual(len(fixtures(q)), 2)
        evidence.pop(('c', 'hidden2'))
        self.assertIsNone(score(config, dict(m=mcq(), c=q), answers, evidence)['score'])

    def test_typed_function_stdout_sql_duplicates_order_and_tolerance(self):
        q = coding('function'); case = q['coding']['tests'][1]
        self.assertTrue(comparison(q, case, dict(status='ok', stdout='9371')))
        for invalid in ('true', '"9371"', 'NaN', '9371\nextra'):
            self.assertFalse(comparison(q, case, dict(status='ok', stdout=invalid)))
        q = sql(); case = q['sql']['datasets'][0]
        self.assertTrue(comparison(q, case, dict(status='ok', columns=['value'], rows=[[2]])))
        self.assertFalse(comparison(q, case, dict(status='ok', columns=['other'], rows=[[2]])))
        q['sql'].update(ordered=False, numeric_tolerance=.1); case['expected_rows'] = [[2], [2.05]]
        self.assertTrue(comparison(q, case, dict(status='ok', columns=['value'], rows=[[2.05], [2]])))
        self.assertFalse(comparison(q, case, dict(status='ok', columns=['value'], rows=[[2], [4]])))


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = runtime_fixture.RuntimeTests(methodName='runTest')
        self.addCleanup(self.fixture.doCleanups); self.fixture.setUp()
        self.db, self.runtime, self.base = self.fixture.db, self.fixture.runtime, self.fixture.base
        ensure_evaluation_indexes(self.db)
        self.flag = patch.dict(os.environ, dict(GENHIRE_OA_EVALUATION_ENABLED='true', GENHIRE_OA_EXECUTION_CONCURRENCY='2', GENHIRE_OA_EXECUTION_QUEUE_LIMIT='1000'))
        self.flag.start(); self.addCleanup(self.flag.stop)
        self.evaluation = AssessmentEvaluationService(self.runtime)
        self.fake = FakeExecutor(self.db); self.evaluation.execution.executor = self.fake
        self.evaluation.execution.profiles = lambda: {l: dict(compiler_id=1, version_id=2, runtime_label=v) for l, v in coding()['coding']['runtime_versions'].items()}
        self.admin = dict(_id=ObjectId(), user_type='admin', permissions=['applications.write', 'applications.read'])

    def submit(self, question=None, answer=None):
        if question is not None:
            version = self.db.assessment_versions.find_one({})
            qid = str(ObjectId()); content_hash = request_identity(question)
            self.db.question_versions.insert_one(dict(_id=ObjectId(qid), question_id=qid, revision=1, owner_id=str(self.base.actor['_id']), pool='recruitment', content=question, content_hash=content_hash))
            configuration = deepcopy(version['configuration'])
            configuration['sections'] = [dict(type=question['type'], count=1, difficulty=dict(easy=1, medium=0, hard=0), marks=[question['marks']], weight=100, duration_minutes=5)]
            configuration['coding_contract'] = question.get('coding', {}).get('contract', 'stdin_stdout')
            configuration['sql_engine'] = question.get('sql', {}).get('engine', 'postgresql')
            # Test-only seed: no production publication/attestation is manufactured.
            self.db.assessment_versions.update_one({'_id': version['_id']}, {'$set': {'configuration': configuration, 'question_version_ids': [qid]}})
        with patch.object(ManagedAssessmentValidator, 'capabilities', return_value={'available': True}): self.fixture.start()
        self.attempt_id, self.qid = self.fixture.identifier, self.fixture.qid
        if answer is not None: self.runtime.save(self.base.candidate, self.attempt_id, 0, 'evaluation-answer-save', {self.qid: answer})
        revision = 1 if answer is not None else 0
        self.runtime.finalize(self.attempt_id, 'candidate', self.base.candidate, revision)
        self.submission = self.db.assessment_submissions.find_one({'attempt_id': self.attempt_id})
        return self.evaluation.enqueue(str(self.submission['_id']))

    def advance(self): self.base.now += timedelta(seconds=35)
    def report(self): return self.db.assessment_evaluation_reports.find_one({'attempt_id': self.attempt_id})
    def wallet(self): return self.db.credit_wallets.find_one({})

    def test_mcq_atomic_capture_replay_withholding_and_no_company_advance(self):
        self.submit(answer={'option_ids': ['optionA']})
        with ThreadPoolExecutor(max_workers=2) as pool: list(pool.map(lambda _: self.evaluation.tick(), range(2)))
        self.assertEqual(self.report()['score'], 100)
        self.assertEqual(self.db.assessment_evaluation_reports.count_documents({}), 1)
        self.assertEqual((self.wallet()['reserved_credits'], self.wallet()['total_debited']), (0, 35))
        self.evaluation.tick(); self.assertEqual(self.wallet()['total_debited'], 35)
        stage = next(s for s in self.base.app()['workflow']['stages'] if s['type'] == 'oa')
        self.assertEqual((stage['state'], stage['outcome']), ('completed', 'pending'))
        self.assertEqual(self.base.app()['workflow']['current_stage_id'], 'oa')
        safe = self.evaluation.report(self.base.candidate, self.attempt_id)
        self.assertFalse(safe['result_available']); self.assertNotIn('score', json.dumps(safe))
        self.assertEqual(self.evaluation.report(self.base.actor, self.attempt_id)['report']['score'], 100)
        with self.assertRaises(WorkflowError): self.evaluation.report(dict(self.base.actor, _id=ObjectId()), self.attempt_id)

    def test_missing_credentials_block_code_without_zero_or_capture(self):
        self.submit(coding(), dict(language='python', source='candidate source'))
        self.fake.available = False; self.evaluation.tick()
        job = self.db.assessment_evaluation_jobs.find_one({})
        self.assertEqual((job['state'], job['error_code']), ('blocked', 'executor_unavailable'))
        self.assertIsNone(self.report()); self.assertEqual(self.wallet()['reserved_credits'], 5)
        self.assertEqual(self.fake.transport.calls, [])

    def test_hidden_code_grading_uses_submitted_snapshot_and_private_evidence(self):
        self.submit(coding(), dict(language='python', source='print("candidate source")'))
        self.db.assessment_attempts.update_one({'_id': ObjectId(self.attempt_id)}, {'$set': {'answers': {}}})
        self.evaluation.tick(); self.evaluation.execution.tick(); self.advance(); self.evaluation.tick()
        self.assertEqual(self.report()['score'], 100)
        self.assertIn('candidate source', self.fake.transport.calls[0]['source'])
        self.assertEqual(self.fake.transport.calls[0]['input'], 'PRIVATE_INPUT_9371')
        task = self.db.assessment_execution_tasks.find_one({})
        self.assertNotIn('stdout', task['result']); self.assertNotIn('PRIVATE_OUTPUT_9371', json.dumps(self.report(), default=str))
        self.assertEqual(self.db.assessment_execution_capacity.find_one({'_id': 'global'})['active'], 0)

    def test_bounded_terminal_infrastructure_retries_then_release_without_score(self):
        self.submit(coding(), dict(language='python', source='candidate source'))
        self.fake.transport.status = 20
        self.evaluation.tick()
        for _ in range(3): self.evaluation.execution.tick(); self.advance()
        self.evaluation.tick()
        self.assertEqual(len(self.fake.transport.calls), 3)
        self.assertEqual(self.report()['state'], 'unavailable'); self.assertIsNone(self.report()['score'])
        self.assertEqual((self.wallet()['balance'], self.wallet()['reserved_credits'], self.wallet()['total_debited']), (70, 0, 30))

    def test_candidate_compile_failure_is_graded_zero_and_captured(self):
        self.submit(coding(), dict(language='python', source='bad candidate code'))
        self.fake.transport.status = 11
        self.evaluation.tick(); self.evaluation.execution.tick(); self.advance(); self.evaluation.tick()
        self.assertEqual(self.report()['score'], 0); self.assertEqual(self.report()['billing_action'], 'capture')

    def test_mutated_pinned_content_is_reviewed_without_scoring_or_spending(self):
        self.submit(answer={'option_ids': ['optionA']})
        self.db.question_versions.update_one({'_id': ObjectId(self.qid)}, {'$set': {'content.title': 'Changed after submission'}})
        self.evaluation.tick()
        self.assertEqual(self.db.assessment_evaluation_jobs.find_one({})['state'], 'needs_review')
        self.assertIsNone(self.report()); self.assertEqual(self.wallet()['reserved_credits'], 5)

    def test_capture_rolls_back_when_report_transaction_fails(self):
        self.submit(answer={'option_ids': ['optionA']}); job = self.evaluation.claim()
        from services.assessment_scoring import score
        attempt = self.db.assessment_attempts.find_one({}); questions = self.evaluation.content(attempt, self.submission)
        report = score(attempt['configuration'], questions, self.submission['answers'], {})
        original = type(self.db.assessment_evaluation_reports).insert_one
        def fail(collection, *args, **kwargs):
            if collection.name == 'assessment_evaluation_reports': raise RuntimeError('TEST_ONLY_FAKE report failure')
            return original(collection, *args, **kwargs)
        with patch.object(type(self.db.assessment_evaluation_reports), 'insert_one', fail):
            with self.assertRaises(RuntimeError): self.evaluation.finish(job, report)
        self.assertEqual((self.wallet()['reserved_credits'], self.wallet()['total_debited']), (5, 30))
        self.assertIsNone(self.report())
        self.evaluation.finish(job, report); self.assertEqual(self.wallet()['total_debited'], 35)

    def test_expired_worker_cannot_publish_or_capture(self):
        self.submit(answer={'option_ids': ['optionA']}); stale = self.evaluation.claim()
        self.base.now += timedelta(seconds=61)
        fresh = self.evaluation.claim(); self.assertNotEqual(stale['lease_token'], fresh['lease_token'])
        with self.assertRaises(WorkflowError): self.evaluation.process(stale)
        self.evaluation.process(fresh); self.assertEqual(self.report()['score'], 100)

    def test_platform_failure_releases_once_fences_worker_and_cancels_queue(self):
        self.submit(coding(), dict(language='python', source='candidate source'))
        self.evaluation.tick(); old = self.evaluation.claim()
        for actor in (self.base.actor, self.base.candidate):
            with self.assertRaises(WorkflowError): self.evaluation.platform_failure(actor, self.attempt_id, 'failure-action-key', 'Verified platform outage prevented evaluation.')
        result = self.evaluation.platform_failure(self.admin, self.attempt_id, 'failure-action-key', 'Verified platform outage prevented evaluation.')
        self.assertEqual(result, self.evaluation.platform_failure(self.admin, self.attempt_id, 'failure-action-key', 'Verified platform outage prevented evaluation.'))
        self.assertEqual(self.wallet()['balance'], 70); self.assertEqual(self.wallet()['reserved_credits'], 0)
        self.assertEqual(self.db.assessment_execution_tasks.find_one({})['state'], 'cancelled')
        self.assertEqual(self.db.assessment_execution_capacity.find_one({'_id': 'queue'})['count'], 0)

    def test_queue_and_global_capacity_are_bounded_under_concurrent_workers(self):
        engine = self.evaluation.execution; q = coding()
        with patch.dict(os.environ, {'GENHIRE_OA_EXECUTION_QUEUE_LIMIT': '5'}):
            def enqueue(index):
                try: engine.enqueue('load-task-'+str(index), q, 'hidden1', 'python', 'candidate code', 'grading', 'fixture-attempt'); return True
                except WorkflowError: return False
            with ThreadPoolExecutor(max_workers=8) as pool: admitted = list(pool.map(enqueue, range(20)))
            self.assertEqual(sum(admitted), 5)
        with ThreadPoolExecutor(max_workers=8) as pool: claimed = list(pool.map(lambda _: engine.claim(), range(10)))
        self.assertEqual(sum(t is not None for t in claimed), 2)
        self.assertEqual(self.db.assessment_execution_capacity.find_one({'_id': 'global'})['active'], 2)
        self.assertEqual(self.db.assessment_execution_capacity.find_one({'_id': 'queue'})['count'], 3)

    def test_unknown_post_never_retries_and_operator_binding_fences_old_poll(self):
        self.submit(coding(), dict(language='python', source='candidate source'))
        self.fake.transport.fail_post = True; self.evaluation.tick(); self.evaluation.execution.tick()
        task = self.db.assessment_execution_tasks.find_one({})
        self.assertEqual(task['state'], 'dispatch_unknown'); self.evaluation.execution.tick()
        self.assertEqual(len(self.fake.transport.calls), 1)
        with self.assertRaises(WorkflowError): self.evaluation.execution.reconcile(self.admin, str(task['_id']), 'retry_confirmed', 'unsafe-retry-key', 'Confirmed account evidence for this dispatch.')
        with self.assertRaises(WorkflowError): self.evaluation.execution.reconcile(self.base.actor, str(task['_id']), 'bind_provider', 'bind-provider-key', 'Verified account-side source and fixture identity.', 111)
        self.fake.transport.fail_post = False
        self.evaluation.execution.reconcile(self.admin, str(task['_id']), 'bind_provider', 'bind-provider-key', 'Verified account-side source and fixture identity.', 111)
        stale = dict(task, state='running', provider_id=110)
        self.evaluation.execution.poll(stale)
        self.assertEqual(self.db.assessment_execution_tasks.find_one({})['state'], 'running')
        fresh = self.db.assessment_execution_tasks.find_one({}); self.evaluation.execution.poll(fresh)
        self.assertEqual(self.db.assessment_execution_tasks.find_one({})['state'], 'complete')

    def test_resource_failures_and_missing_evidence_are_not_guessed(self):
        engine = self.evaluation.execution; client = self.fake.transport; q = coding()
        task = dict(question=q, purpose='grading', provider_id=1, language='python')
        for update, expected in [({'time': 3}, 'time_limit'), ({'memory': 999999}, 'memory_limit'), ({'size': 999999}, 'output_limit')]:
            client.time, client.memory, client.size = .01, 32, None
            for key, value in update.items(): setattr(client, key, value)
            self.assertEqual(engine.output(task)['status'], expected)
        client.size, client.time = None, None
        with self.assertRaises(WorkflowError): engine.output(task)

    def test_four_language_function_harness_dispatch_matrix_with_fake_outputs(self):
        engine = self.evaluation.execution
        for language in ['python', 'javascript', 'java', 'cpp']:
            with self.subTest(language=language):
                q = coding('function'); self.fake.transport.stdout = '9371'
                task = engine.enqueue('function-matrix-'+language, q, 'hidden1', language, q['coding']['reference_solutions'][language], 'grading', 'matrix-fixture')
                engine.tick()
                result = self.db.assessment_execution_tasks.find_one({'_id': task['_id']})
                self.assertEqual(result['result']['passed'], True)
                self.assertNotIn('PRIVATE_INPUT', self.fake.transport.calls[-1]['input'])
                self.assertIn('9371', self.fake.transport.calls[-1]['source'])
        # This checks wrapper/transport/scoring contracts, not real compilation.

    def _sql_grade(self, engine):
        self.submit(sql(engine), dict(language='sql', source='SELECT value FROM values_table ORDER BY value'))
        from services.sql_execution_service import SqlExecutionService
        class Blob:
            def __init__(blob, storage, path): blob.storage, blob.path = storage, path
            def upload_from_string(blob, value, **kwargs): blob.storage.objects[blob.path] = value
            def reload(blob, **kwargs): blob.size = len(blob.storage.objects[blob.path].encode())
            def download_as_bytes(blob, **kwargs): return blob.storage.objects[blob.path].encode()
        class Storage:
            def __init__(storage): storage.objects = {}
            def bucket(storage, name): return storage
            def blob(storage, path): return Blob(storage, path)
        storage = Storage()
        class Response:
            status_code = 200
            def json(response): return {'name': 'projects/genhire-test-project/locations/europe-west1/operations/test-operation'}
            def close(response): pass
        class Session:
            def post(session, url, json=None, **kwargs):
                env = {v['name']: v['value'] for v in json['overrides']['containerOverrides'][0]['env']}
                payload = __import__('json').loads(storage.objects[env['SQL_REQUEST_OBJECT']])
                expected = 9371 if '9371' in payload['seed_sql'] else 2
                result = dict(execution_evidence_version=2, request_id=payload['request_id'], request_hash=request_identity(payload),
                    engine=payload['engine'], engine_version=payload['engine_version'], status='ok', columns=['value'], rows=[[expected]])
                storage.objects[env['SQL_RESULT_OBJECT']] = __import__('json').dumps(result)
                return Response()
        def adapter(db): return SqlExecutionService(db, session=Session(), storage=storage)
        env = dict(GENHIRE_ASSESSMENT_EXECUTION_ENABLED='true', GENHIRE_SQL_PROJECT='genhire-test-project', GENHIRE_SQL_ARTIFACT_BUCKET='genhire-test-bucket',
            GENHIRE_SQL_REGION='europe-west1', GENHIRE_SQL_POSTGRESQL_JOB='oa-test-pg', GENHIRE_SQL_MYSQL_JOB='oa-test-mysql')
        with patch.dict(os.environ, env), patch('services.assessment_execution_service.SqlExecutionService', side_effect=adapter):
            self.evaluation.tick()
            for _ in range(2): self.evaluation.execution.tick(); self.advance()
            self.evaluation.tick()
        self.assertEqual(self.report()['score'], 100)
        self.assertEqual(self.db.sql_execution_dispatches.count_documents({'state': 'completed'}), 2)
        self.assertEqual(self.db.sql_execution_limits.find_one({'_id': 'active'})['count'], 0)
        self.assertNotIn('9371', json.dumps(self.report(), default=str))

    def test_postgresql_dataset_dispatch_and_hash_bound_result_collection(self): self._sql_grade('postgresql')
    def test_mysql_dataset_dispatch_and_hash_bound_result_collection(self): self._sql_grade('mysql')

    def test_poll_errors_back_off_keep_provider_identity_and_do_not_fail_candidate(self):
        self.submit(coding(), dict(language='python', source='candidate source'))
        self.fake.transport.fail_get = True
        self.evaluation.tick(); self.evaluation.execution.tick()
        for _ in range(8):
            task = self.db.assessment_execution_tasks.find_one({}); self.evaluation.execution.poll(task)
        task = self.db.assessment_execution_tasks.find_one({})
        self.assertEqual(task['state'], 'running'); self.assertTrue(task['needs_review'])
        self.assertEqual(len(self.fake.transport.calls), 1); self.assertEqual(task['provider_id'], 101)
        self.assertIsNone(self.report()); self.assertEqual(self.wallet()['reserved_credits'], 5)
        self.fake.transport.fail_get = False
        self.evaluation.execution.reconcile(self.admin, str(task['_id']), 'resume_poll', 'resume-known-poll', 'Provider account and access have been verified restored.')
        self.evaluation.execution.tick(); self.advance(); self.evaluation.tick()
        self.assertEqual(self.report()['score'], 100)

    def test_per_attempt_case_budget_rejected_before_credit_reservation(self):
        q = coding(); q['coding']['tests'].append(dict(q['coding']['tests'][1], id='hidden2'))
        with patch.dict(os.environ, {'GENHIRE_OA_GRADING_CASE_LIMIT': '1'}):
            with self.assertRaises(WorkflowError) as error: self.submit(q, dict(language='python', source='candidate source'))
        self.assertEqual(error.exception.code, 'grading_case_limit'); self.assertEqual(self.wallet()['reserved_credits'], 0)

    def test_evaluation_http_report_withholding_and_admin_operations_scope(self):
        self.submit(answer={'option_ids': ['optionA']}); self.evaluation.tick()
        from flask import Flask
        from routes.hiring_progression_routes import create_hiring_progression_routes
        actor = [self.base.candidate]
        def auth(fn):
            def wrapped(*args, **kwargs): return fn(actor[0], *args, **kwargs)
            wrapped.__name__ = fn.__name__; return wrapped
        with patch('routes.hiring_progression_routes.token_required', auth), patch('routes.hiring_progression_routes.AssessmentRuntimeService', return_value=self.runtime):
            app = Flask(__name__); app.register_blueprint(create_hiring_progression_routes(self.db))
        client = app.test_client(); path = '/api/assessment-attempts/'+self.attempt_id
        response = client.get(path+'/evaluation')
        self.assertEqual(response.status_code, 200); self.assertNotIn('score', json.dumps(response.json))
        self.assertEqual(client.get('/api/assessment-evaluation-operations').status_code, 403)
        actor[0] = self.base.actor
        self.assertEqual(client.get(path+'/evaluation').json['report']['score'], 100)
        actor[0] = dict(self.base.actor, _id=ObjectId())
        self.assertEqual(client.get(path+'/evaluation').status_code, 403)
        actor[0] = self.admin
        self.assertEqual(client.get('/api/assessment-evaluation-operations').status_code, 200)
        self.assertEqual(client.post(path+'/platform-failure', json=dict(operation_key='cannot-refund-usable', reason='This is an already usable evaluated attempt.')).status_code, 409)

    def test_sql_artifact_failure_reuses_unposted_reservation_without_new_quota(self):
        from services.sql_execution_service import SqlExecutionService
        engine = self.evaluation.execution
        task = engine.enqueue('sql-artifact-recovery', sql(), 'hidden1', 'sql', 'SELECT 1', 'grading', 'fixture-attempt')
        env = dict(GENHIRE_ASSESSMENT_EXECUTION_ENABLED='true', GENHIRE_SQL_PROJECT='genhire-test-project', GENHIRE_SQL_ARTIFACT_BUCKET='genhire-test-bucket',
            GENHIRE_SQL_REGION='europe-west1', GENHIRE_SQL_POSTGRESQL_JOB='oa-test-pg')
        with patch.dict(os.environ, env), patch.object(SqlExecutionService, 'dispatch', side_effect=WorkflowError('sql_artifact_unavailable', 'TEST_ONLY_FAKE unavailable artifact', 503)):
            engine.dispatch(engine.claim())
        first = self.db.assessment_execution_tasks.find_one({'_id': task['_id']})
        self.assertEqual(first['state'], 'queued'); self.assertEqual(first['retries'], 0)
        self.advance()
        with patch.dict(os.environ, env), patch.object(SqlExecutionService, 'dispatch', return_value={'state': 'running'}): engine.dispatch(engine.claim())
        second = self.db.assessment_execution_tasks.find_one({'_id': task['_id']})
        self.assertEqual(second['state'], 'running'); self.assertEqual(second['provider_id'], first['provider_id'])
        self.assertEqual(self.db.sql_execution_dispatches.count_documents({}), 1)
        self.assertEqual(self.db.sql_execution_limits.find_one({'_id': 'active'})['count'], 1)


if __name__ == '__main__': unittest.main()
