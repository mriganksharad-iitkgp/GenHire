from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
import json
import os
import unittest
from unittest.mock import patch
from bson import ObjectId
import test_hiring_progression as progression
from assessment_test_fixtures import coding, sql
from models.assessment_content import candidate_question
from models.hiring_workflow import WorkflowError
from services.assessment_runtime_service import AssessmentRuntimeService, ensure_runtime_indexes
from services.assessment_public_run_service import AssessmentPublicRunService
from services.assessment_harness import function_source
from services.assessment_execution_service import ensure_execution_indexes
from services.workflow_service import request_identity


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.base = progression.ProgressionTransactionTests(methodName='runTest')
        self.addCleanup(self.base.doCleanups)
        self.base.setUp()
        self.db = self.base.db
        ensure_runtime_indexes(self.db)
        ensure_execution_indexes(self.db)
        self.flags = patch.dict(os.environ, dict(GENHIRE_OA_RUNTIME_ENABLED='true', GENHIRE_OA_EVALUATION_ACCEPTED='true', GENHIRE_OA_SECURITY_ACCEPTED='true'))
        self.flags.start(); self.addCleanup(self.flags.stop)
        # Foundation tests deliberately exercise the pre-integrity runtime. No
        # production bypass flag is introduced; Step 7 separately tests real gates.
        self.foundation = patch.object(AssessmentRuntimeService, 'candidate_runtime_ready', property(lambda value: all(os.getenv(k, '').lower() == 'true' for k in (
            'GENHIRE_OA_RUNTIME_ENABLED', 'GENHIRE_OA_EVALUATION_ACCEPTED', 'GENHIRE_OA_SECURITY_ACCEPTED'))))
        self.foundation.start(); self.addCleanup(self.foundation.stop)
        self.runtime = AssessmentRuntimeService(self.db, lambda: self.base.now)
        self.runtime._billing = self.base.billing
        self.invitation = self.base.invitation()
        self.base.now = progression.utc(self.invitation['start_closes_at']) - timedelta(seconds=1)
        self.actor = self.base.candidate

    def start(self):
        result = self.runtime.start(self.actor, str(self.invitation['_id']), 'runtime-start-key', 'oa-v1')
        self.identifier = result['attempt_id']
        self.qid = self.runtime.view(self.actor, self.identifier)['questions'][0]['id']
        return result

    def test_invitation_landing_summary_contains_only_public_format(self):
        value=self.runtime.invitation(self.actor,str(self.invitation['_id']))
        summary=value['assessment_summary']
        self.assertGreater(summary['question_count'],0)
        self.assertTrue(all(set(section)<={'type','count','duration_minutes'} for section in summary['sections']))
        self.assertNotIn('reference_solutions',json.dumps(summary))
        self.assertNotIn('question_version_ids',json.dumps(summary))

    def save(self, revision=0, key='runtime-save-key', value=None):
        return self.runtime.save(self.actor, self.identifier, revision, key, {self.qid: value or {'option_ids': ['optionA']}})

    def test_atomic_start_pins_safe_content_and_full_duration_once(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.runtime.start(self.actor, str(self.invitation['_id']), 'runtime-start-key', 'oa-v1'), range(2)))
        self.assertEqual(results[0]['attempt_id'], results[1]['attempt_id'])
        attempt = self.db.assessment_attempts.find_one({})
        self.assertEqual(progression.utc(attempt['deadline'])-self.base.now, timedelta(minutes=5))
        self.assertEqual(self.db.assessment_attempts.count_documents({}), 1)
        self.assertEqual(self.db.credit_wallets.find_one({})['reserved_credits'], 5)
        view = self.runtime.view(self.actor, str(attempt['_id']))
        self.assertNotIn('correct_option_ids', json.dumps(view, default=str))
        self.assertNotIn('Private explanation', json.dumps(view, default=str))

    def test_consent_and_launch_gate_do_not_reserve_credits(self):
        with self.assertRaises(WorkflowError) as error: self.runtime.start(self.actor, str(self.invitation['_id']), 'runtime-start-key', False)
        self.assertEqual(error.exception.code, 'consent_required')
        with patch.dict(os.environ, {'GENHIRE_OA_SECURITY_ACCEPTED': 'false'}):
            with self.assertRaises(WorkflowError): self.start()
        self.assertEqual(self.db.assessment_attempts.count_documents({}), 0)
        self.assertEqual(self.db.credit_wallets.find_one({})['reserved_credits'], 0)

    def test_failed_preparation_rolls_back_reservation(self):
        self.db.question_versions.delete_many({})
        with self.assertRaises(WorkflowError): self.start()
        self.assertEqual(self.db.credit_wallets.find_one({})['reserved_credits'], 0)
        self.assertEqual(self.db.assessment_attempts.count_documents({}), 0)

    def test_revisioned_ack_replay_conflict_and_resumed_answers(self):
        result = self.start(); first = self.save()
        self.assertEqual(first, self.save())
        self.assertEqual(first['revision'], 1)
        with self.assertRaises(WorkflowError) as stale: self.save(key='runtime-second-save')
        self.assertEqual(stale.exception.code, 'stale_revision')
        with self.assertRaises(WorkflowError) as conflict: self.save(value={'option_ids': ['optionB']})
        self.assertEqual(conflict.exception.code, 'idempotency_conflict')
        self.assertEqual(self.runtime.view(self.actor, self.identifier)['answers'][self.qid]['option_ids'], ['optionA'])
        self.base.now += timedelta(seconds=20)
        self.assertEqual(self.runtime.start(self.actor, str(self.invitation['_id']), 'runtime-reconnect', 'oa-v1')['deadline'], result['deadline'])

    def test_concurrent_different_saves_have_one_winner(self):
        self.start()
        def write(index):
            try: self.save(key=f'concurrent-save-{index}'); return 'saved'
            except WorkflowError as exc: return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(write, range(2)))
        self.assertCountEqual(results, ['saved', 'stale_revision'])

    def test_owner_checks_invalid_mcq_and_withdrawal(self):
        self.start()
        with self.assertRaises(WorkflowError): self.runtime.view(dict(_id=ObjectId(), user_type='candidate'), self.identifier)
        for value in ({'option_ids': ['optionA', 'optionB']}, {'option_ids': ['unknown']}, {'option_ids': [], 'score': 100}):
            with self.assertRaises(WorkflowError): self.save(value=value)
        self.db.applications.update_one({'_id': self.base.app_id}, {'$set': {'workflow.lifecycle': 'withdrawn'}})
        with self.assertRaises(WorkflowError): self.save()

    def test_server_deadline_finalizes_without_browser_exactly_once(self):
        self.start(); self.save()
        attempt = self.db.assessment_attempts.find_one({})
        self.base.now = progression.utc(attempt['deadline'])
        with self.assertRaises(WorkflowError): self.save(1, 'late-save-request')
        self.assertEqual(self.runtime.expire_due(), 1)
        self.assertEqual(self.runtime.expire_due(), 0)
        submission = self.db.assessment_submissions.find_one({})
        self.assertEqual(submission['answers'][self.qid]['option_ids'], ['optionA'])
        self.assertEqual(submission['state'], 'awaiting_evaluator')
        self.assertEqual(self.db.credit_wallets.find_one({})['reserved_credits'], 5)
        self.assertEqual(next(s for s in self.base.app()['workflow']['stages'] if s['type'] == 'oa')['state'], 'submitted')

    def test_submit_requires_latest_ack_and_locks_answers(self):
        self.start(); self.save()
        with self.assertRaises(WorkflowError): self.runtime.finalize(self.identifier, 'candidate', self.actor, 0)
        result = self.runtime.finalize(self.identifier, 'candidate', self.actor, 1)
        self.assertEqual(result, self.runtime.finalize(self.identifier, 'candidate', self.actor, 1))
        with self.assertRaises(WorkflowError): self.save(2, 'after-submit-save')
        self.assertEqual(self.db.assessment_submissions.count_documents({}), 1)

    def test_section_windows_hide_future_content_and_reject_closed_writes(self):
        self.start()
        attempt = self.db.assessment_attempts.find_one({}); boundary = self.base.now + timedelta(minutes=2)
        second = deepcopy(attempt['questions'][0]); second['id'] = str(ObjectId())
        sections = [dict(index=0, type='mcq', opens_at=self.base.now, closes_at=boundary, question_ids=[self.qid]),
            dict(index=1, type='mcq', opens_at=boundary, closes_at=attempt['deadline'], question_ids=[second['id']])]
        self.db.assessment_attempts.update_one({'_id': attempt['_id']}, {'$set': {'configuration.timer_mode': 'section', 'sections': sections, 'questions': [attempt['questions'][0], second]}})
        self.assertEqual([q['id'] for q in self.runtime.view(self.actor, self.identifier)['questions']], [self.qid])
        self.save(); self.base.now = boundary
        self.assertEqual([q['id'] for q in self.runtime.view(self.actor, self.identifier)['questions']], [second['id']])
        with self.assertRaises(WorkflowError) as error: self.save(1, 'closed-section-save')
        self.assertEqual(error.exception.code, 'section_locked')

    def test_saved_reads_and_deadline_cleanup_survive_disabled_rollout(self):
        self.start(); self.save()
        with patch.dict(os.environ, {'GENHIRE_OA_RUNTIME_ENABLED': 'false', 'GENHIRE_SCHEDULING_ENABLED': 'false'}):
            self.assertEqual(self.runtime.view(self.actor, self.identifier)['revision'], 1)
            self.assertEqual(self.runtime.invitation(self.actor, str(self.invitation['_id']))['attempt_id'], self.identifier)
            self.base.now += timedelta(minutes=6)
            self.assertEqual(self.runtime.expire_due(), 1)

    def test_public_run_is_durable_private_idempotent_and_bounded(self):
        self.start()
        q = coding('function'); qid = str(ObjectId())
        self.db.question_versions.insert_one(dict(_id=ObjectId(qid), question_id=qid, revision=1, content=q))
        self.db.assessment_attempts.update_one({'_id': ObjectId(self.identifier)}, {'$set': {'questions': [dict(id=qid, **candidate_question(q))], 'question_bindings': [dict(question_version_id=qid, content_hash=request_identity(q))]}})
        runs = AssessmentPublicRunService(self.runtime)
        answer = dict(language='python', source='def solve(value):\n    return value + 1')
        with patch.object(runs.executor, 'capabilities', return_value={'available': False}):
            with self.assertRaises(WorkflowError) as unavailable: runs.create(self.actor, self.identifier, 'public-run-unavailable', qid, answer)
        self.assertEqual(unavailable.exception.code, 'executor_unavailable')
        with patch.object(runs.executor, 'capabilities', return_value={'available': True}):
            result = runs.create(self.actor, self.identifier, 'public-run-first', qid, answer, {'value': 42})
            self.assertEqual(result, runs.create(self.actor, self.identifier, 'public-run-first', qid, answer, {'value': 42}))
            with self.assertRaises(WorkflowError): runs.create(self.actor, self.identifier, 'public-run-other', qid, answer)
            with self.assertRaises(WorkflowError): runs.create(self.actor, self.identifier, 'public-run-first', qid, answer, {'value': 9})
        public = json.dumps(runs.result(self.actor, self.identifier, result['run_id']))
        self.assertNotIn('9371', public); self.assertNotIn('reference_solutions', public)
        def execute(identity,q,case_id,language,purpose):
            source=function_source(q,language,case_id)
            self.assertIn('42',source);self.assertNotIn('9371',source);self.assertIn('value + 1',source)
            return dict(status='ok',stdout='43')
        with patch.object(runs.executor,'capabilities',return_value={'available':True}),patch.object(runs.executor,'profile_hash',return_value='TEST_ONLY_FAKE'),patch.object(runs.executor,'execute_case',side_effect=execute),patch.object(runs.executor,'execution_result',return_value=dict(status='ok',stdout='43')):
            runs.tick()
        self.assertEqual(runs.result(self.actor,self.identifier,result['run_id'])['result'],dict(status='ok',stdout='43'))
        with patch.dict(os.environ,{'OA_MAX_PRACTICE_RUNS_PER_QUESTION':'1'}),patch.object(runs.executor,'capabilities',return_value={'available':True}):
            with self.assertRaises(WorkflowError) as quota:runs.create(self.actor,self.identifier,'public-run-quota',qid,answer)
            self.assertEqual(quota.exception.code,'run_limit')

    def test_http_workspace_contract_and_cross_candidate_denial(self):
        self.start()
        from flask import Flask
        actor = [self.actor]
        def auth(fn):
            def wrapped(*args, **kwargs): return fn(actor[0], *args, **kwargs)
            wrapped.__name__ = fn.__name__; return wrapped
        from routes.hiring_progression_routes import create_hiring_progression_routes
        with patch('routes.hiring_progression_routes.token_required', auth), patch('routes.hiring_progression_routes.AssessmentRuntimeService', return_value=self.runtime):
            app = Flask(__name__); app.register_blueprint(create_hiring_progression_routes(self.db))
        client = app.test_client(); path = '/api/assessment-attempts/'+self.identifier
        response = client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response.headers['Cache-Control'])
        response = client.post(path+'/answers', json=dict(expected_revision=0, operation_key='http-answer-save', answers={self.qid: {'option_ids': ['optionA']}}))
        self.assertEqual(response.status_code, 200); self.assertEqual(response.json['revision'], 1)
        self.assertEqual(client.post(path+'/submit', json={'expected_revision': 0}).status_code, 409)
        actor[0] = dict(_id=ObjectId(), user_type='candidate')
        self.assertEqual(client.get(path).status_code, 404)
        self.assertEqual(client.post(path+'/submit', json={'expected_revision': 1}).status_code, 404)
        actor[0] = self.actor
        self.assertEqual(client.post(path+'/submit', json={'expected_revision': 1}).json['state'], 'submitted')

    def test_unknown_external_post_is_not_automatically_resubmitted(self):
        self.start(); q = coding(); qid = str(ObjectId())
        self.db.question_versions.insert_one(dict(_id=ObjectId(qid), question_id=qid, revision=1, content=q))
        self.db.assessment_attempts.update_one({'_id': ObjectId(self.identifier)}, {'$set': {'questions': [dict(id=qid, **candidate_question(q))], 'question_bindings': [dict(question_version_id=qid, content_hash=request_identity(q))]}})
        runs = AssessmentPublicRunService(self.runtime)
        def unknown(identity,*args):
            self.db.oa_provider_requests.insert_one(dict(_id=identity,state='dispatch_unknown'))
            raise RuntimeError('TEST_ONLY_FAKE ambiguous network result')
        with patch.object(runs.executor,'capabilities',return_value={'available':True}),patch.object(runs.executor,'profile_hash',return_value='TEST_ONLY_FAKE'),patch.object(runs.executor,'execute_case',side_effect=unknown) as execute:
            result=runs.create(self.actor,self.identifier,'unknown-public-run',qid,dict(language='python',source='print(input())'))
            runs.tick();runs.tick()
            self.assertEqual(execute.call_count,1)
            self.assertEqual(runs.result(self.actor,self.identifier,result['run_id'])['state'],'dispatch_unknown')
            with self.assertRaises(WorkflowError):runs.create(self.actor,self.identifier,'unknown-next-run',qid,dict(language='python',source='print(2)'))

    def test_both_sql_public_run_payloads_exclude_hidden_datasets(self):
        self.start(); runs = AssessmentPublicRunService(self.runtime)
        for engine in ['sqlite','duckdb']:
            with self.subTest(engine=engine):
                q=sql(engine);qid=str(ObjectId())
                self.db.question_versions.insert_one(dict(_id=ObjectId(qid),question_id=qid,revision=1,content=q))
                self.db.assessment_attempts.update_one({'_id':ObjectId(self.identifier)},{'$set':{'questions':[dict(id=qid,**candidate_question(q))],'question_bindings':[dict(question_version_id=qid,content_hash=request_identity(q))]}})
                with patch.object(runs.executor,'capabilities',return_value={'available':True,'sql_available':True}),patch.object(runs.executor,'profile_hash',return_value='TEST_ONLY_FAKE'),patch.object(runs.executor.provider,'run_sql',return_value=dict(status='ok',columns=['n'],rows=[[1]])) as execute,patch.object(runs.executor,'execution_result',return_value=dict(status='ok',columns=['n'],rows=[[1]])):
                    q['sql']['engine_version']={'sqlite':'sqlite-3','duckdb':'duckdb-1.5'}[engine]
                    self.db.question_versions.update_one({'_id':ObjectId(qid)},{'$set':{'content':q}})
                    self.db.assessment_attempts.update_one({'_id':ObjectId(self.identifier)},{'$set':{'question_bindings':[dict(question_version_id=qid,content_hash=request_identity(q))]}})
                    result=runs.create(self.actor,self.identifier,'sql-run-'+engine,qid,dict(language='sql',source='SELECT 1'))
                    runs.tick()
                args=execute.call_args.args
                self.assertEqual(args[1]['sql']['engine'],engine);self.assertNotIn('9371',args[2]['seed_sql']);self.assertEqual(args[1]['sql']['reference_query'],'SELECT 1')
                self.assertEqual(runs.result(self.actor,self.identifier,result['run_id'])['result']['rows'],[[1]])


class PublicRunPreparationTests(unittest.TestCase):
    def test_function_custom_input_all_languages_never_wraps_hidden_case(self):
        for language in ['python', 'javascript', 'java', 'cpp']:
            q = coding('function'); answer = dict(language=language, source=q['coding']['reference_solutions'][language])
            prepared, case = AssessmentPublicRunService.prepare(q, answer, {'value': 42})
            source = function_source(prepared, language, case)
            self.assertIn('42', source); self.assertNotIn('9371', source)
            with self.assertRaises(WorkflowError): AssessmentPublicRunService.prepare(q, answer, {'value': 'invalid integer'})

    def test_stdout_and_sql_use_public_cases_and_candidate_source(self):
        q, case = AssessmentPublicRunService.prepare(coding(), dict(language='python', source='print(input())'), 'hello')
        self.assertEqual(next(c for c in q['coding']['tests'] if c['id'] == case)['input'], 'hello')
        for engine in ['sqlite', 'duckdb']:
            q, case = AssessmentPublicRunService.prepare(sql(engine), dict(language='sql', source='SELECT 1'), None)
            self.assertEqual(case, 'sample1'); self.assertEqual(q['sql']['reference_query'], 'SELECT 1')
            public = json.dumps(candidate_question(q))
            self.assertNotIn('9371', public); self.assertNotIn('reference_query', public)


if __name__ == '__main__': unittest.main()
