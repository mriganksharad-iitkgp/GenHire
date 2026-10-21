from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
import os
import unittest
from unittest.mock import patch
from bson import ObjectId
from flask import Flask
from pymongo.collection import Collection
from workflow_test_support import MongoTestCase
from assessment_test_fixtures import mcq, coding, sql, executor_results
from models.assessment_content import validate_question, candidate_question, blueprint_match
from models.hiring_workflow import WorkflowError
from models.job_setup import default_setup
from services.assessment_authoring_service import AssessmentAuthoringService, ensure_authoring_indexes
from services.assessment_harness import function_source
from services.assessment_validation import verify_reference_results, sql_rows_equal, stdout_equal
from services.job_setup_service import JobSetupService, ensure_setup_indexes


class AssessmentContractTests(unittest.TestCase):
    def test_manual_and_generated_contract_matrix(self):
        for q in [mcq(), coding(), coding('function'), sql(), sql('mysql')]:
            with self.subTest(type=q['type']):
                self.assertEqual(validate_question(q), q)
                self.assertEqual(validate_question(json.loads(json.dumps(q))), q)

    def test_private_content_is_never_in_candidate_serializer(self):
        for q in [mcq(), coding(), coding('function'), sql(), sql('mysql')]:
            public = candidate_question(q)
            encoded = json.dumps(public)
            for secret in ('9371', 'PRIVATE_', 'correct_option_ids', 'reference_solutions', 'reference_query', 'Private explanation'):
                self.assertNotIn(secret, encoded)
            if q['type'] == 'coding': self.assertEqual(len(public['coding']['examples']), 1)
            if q['type'] == 'sql': self.assertEqual(len(public['sql']['examples']), 1)

    def test_bad_mcq_keys_and_duplicate_options_are_rejected(self):
        for update in [dict(correct_option_ids=[]), dict(correct_option_ids=['missing']), dict(correct_option_ids=['optionA', 'optionB']),
                       dict(options=[dict(id='optionA', text='2'), dict(id='optionA', text='3')]),
                       dict(options=[dict(id='optionA', text='Same'), dict(id='optionB', text='same')])]:
            q = mcq(); q['mcq'].update(update)
            with self.subTest(update=update), self.assertRaises(WorkflowError): validate_question(q)
        q = mcq(); q['mcq'].update(selection='multiple', correct_option_ids=['optionA', 'optionB'])
        validate_question(q)

    def test_invalid_types_unknown_fields_and_nonfinite_marks_rejected(self):
        for value in [None, [], {'type': []}, dict(mcq(), marks=True), dict(mcq(), marks=float('nan')),
                      dict(mcq(), private_override=True), dict(mcq(), statement=''), dict(mcq(), topics=['x', 'x'])]:
            with self.subTest(value=value), self.assertRaises(WorkflowError): validate_question(value)

    def test_function_signature_and_typed_tests(self):
        for name in ['__proto__', 'class', 'return', 'ghArgs', 'a;system()', 'extends']:
            q = coding('function'); q['coding']['signature']['name'] = name
            with self.subTest(name=name), self.assertRaises(WorkflowError): validate_question(q)
        for value in [True, 1.5, 2147483648, {}, None]:
            q = coding('function'); q['coding']['tests'][0]['input']['value'] = value
            with self.subTest(value=value), self.assertRaises(WorkflowError): validate_question(q)
        q = coding('function'); q['coding']['signature']['parameters'][0]['type'] = 'integer[]'
        with self.assertRaises(WorkflowError): validate_question(q)
        for t in q['coding']['tests']: t['input']['value'] = [1, 2, 3]
        validate_question(q)

    def test_sql_shape_and_required_hidden_data(self):
        for engine in ('postgresql', 'mysql'):
            q = sql(engine); q['sql']['datasets'][1]['visibility'] = 'sample'
            with self.assertRaises(WorkflowError): validate_question(q)
            q = sql(engine); q['sql']['datasets'][0]['expected_rows'] = [[1, 2]]
            with self.assertRaises(WorkflowError): validate_question(q)
            q = sql(engine); q['sql']['datasets'][0]['expected_rows'] = [[float('inf')]]
            with self.assertRaises(WorkflowError): validate_question(q)

    def test_harness_source_is_generated_for_all_languages_without_host_execution(self):
        q = coding('function')
        for language in q['coding']['languages']:
            source = function_source(q, language, 'sample1')
            self.assertIn(q['coding']['reference_solutions'][language], source)
            self.assertIn('solve', source)
            self.assertIn('2', source)
        with self.assertRaises(ValueError): function_source(q, 'ruby', 'sample1')

    def test_incomplete_or_wrong_runtime_executor_evidence_cannot_approve(self):
        q = coding('function')
        r = executor_results(q)
        self.assertTrue(verify_reference_results(q, r)['passed'])
        for result in [{'passed': True}, dict(r, question_hash='wrong'), dict(r, runs=r['runs'][:-1]), dict(r, runs=[r['runs'][0]] * len(r['runs']))]:
            with self.assertRaises(WorkflowError): verify_reference_results(q, result)
        r = executor_results(q); r['runs'][0]['runtime_version'] = 'other'
        with self.assertRaises(WorkflowError): verify_reference_results(q, r)
        r = executor_results(q); r['runs'][0]['value'] = False
        evidence = verify_reference_results(q, r)
        self.assertFalse(evidence['passed'])
        self.assertNotIn('9371', json.dumps(evidence))

    def test_real_result_comparison_preserves_duplicate_sql_rows_and_types(self):
        self.assertTrue(stdout_equal('2 \r\n', '2', 'trim_trailing_whitespace'))
        self.assertFalse(stdout_equal(' 2', '2', 'trim_trailing_whitespace'))
        self.assertFalse(stdout_equal('2\n', '2', 'exact'))
        self.assertTrue(sql_rows_equal([[2], [1], [1]], [[1], [1], [2]], False, 0))
        self.assertFalse(sql_rows_equal([[2], [2], [1]], [[1], [1], [2]], False, 0))
        self.assertFalse(sql_rows_equal([[False]], [[0]], False, 0))
        self.assertFalse(sql_rows_equal([[2], [1]], [[1], [2]], True, 0))
        self.assertTrue(sql_rows_equal([[1.0001], [1.0002]], [[1.0002], [1.0001]], False, 0.00001))
        for q in (coding(), sql(), sql('mysql')):
            self.assertTrue(verify_reference_results(q, executor_results(q))['passed'])


class AssessmentPersistenceTests(MongoTestCase):
    def setUp(self):
        super().setUp()
        ensure_setup_indexes(self.db); ensure_authoring_indexes(self.db)
        self.owner = dict(_id=ObjectId(), user_type='recruiter', is_verified=True)
        self.other = dict(_id=ObjectId(), user_type='recruiter', is_verified=True)
        c = default_setup()
        c['pipeline']['oa_enabled'] = True
        c['oa'].update(template_id='custom', sections=[dict(type='mcq', count=1, difficulty=dict(easy=1, medium=0, hard=0), marks=[1], weight=100, duration_minutes=5)], duration_minutes=5)
        setup = JobSetupService(self.db)
        draft = setup.save(self.owner, c, {}, 'assessment-setup-key')
        self.job = setup.attach(self.owner, draft['_id'], 1, dict(_id=ObjectId(), created_by=str(self.owner['_id']), status='draft'), 'job-hash', creating=True)
        self.bp = str(self.db.assessment_blueprints.find_one({})['_id'])
        self.service = AssessmentAuthoringService(self.db)

    def question(self): return self.service.save_question(self.owner, mcq(), 'first-question-key', blueprint_id=self.bp)

    def approve(self, q):
        v = self.service.validate(self.owner, q['_id'], 'validate-' + q['_id'])
        return self.service.review(self.owner, q['_id'], v['_id'], 'approve', 'Checked the answer and all ambiguous alternatives.', 'review-' + q['_id'])

    def test_private_versions_owner_boundaries_and_replay(self):
        q = self.question()
        self.assertEqual(self.question(), q)
        before = self.db.question_versions.find_one({})
        changed = mcq(); changed['title'] = 'New title'
        q2 = self.service.save_question(self.owner, changed, 'second-question-key', q['_id'], self.bp)
        self.assertEqual(q2['revision'], 2)
        self.assertEqual(before, self.db.question_versions.find_one({'_id': ObjectId(q['_id'])}))
        with self.assertRaises(WorkflowError): self.service.save_question(self.owner, changed, 'stale-question-key', q['_id'])
        for read in [lambda: self.service.get_question(self.other, q['_id']), lambda: self.service.workspace(self.other, self.bp)]:
            with self.assertRaises(WorkflowError): read()
        self.assertEqual(self.service.bank(self.other)['items'], [])
        bank = self.service.bank(self.owner)
        self.assertNotIn('mcq', bank['items'][0]['content'])
        self.assertGreater(self.db.assessment_content_audit.count_documents({}), 0)

    def test_publish_requires_exact_blueprint_validation_review_and_explicit_approval(self):
        q = self.question()
        self.service.save_workspace(self.owner, self.bp, [q['_id']], 0, 'selection-first-key')
        with self.assertRaises(WorkflowError): self.service.publish(self.owner, self.bp, 1, 'publish-first-key', False)
        with self.assertRaises(WorkflowError): self.service.publish(self.owner, self.bp, 1, 'publish-first-key', True)
        self.approve(q)
        version = self.service.publish(self.owner, self.bp, 1, 'publish-first-key', True)
        self.assertEqual(version, self.service.publish(self.owner, self.bp, 1, 'publish-first-key', True))
        self.assertEqual(self.db.assessment_versions.count_documents({}), 1)
        self.assertFalse(version['activated'])
        saved_job = self.db.jobs.find_one({'_id': self.job['_id']})
        self.assertEqual(saved_job['status'], 'draft')
        self.assertNotIn('workflow_version_id', saved_job)
        self.assertEqual(self.db.billing_operations.count_documents({}), 0)
        self.assertEqual(self.db.applications.count_documents({}), 0)

    def test_workspace_stale_or_duplicate_logical_question_is_rejected(self):
        q = self.question()
        newer = self.service.save_question(self.owner, mcq(), 'new-question-version', q['_id'])
        with self.assertRaises(WorkflowError): self.service.save_workspace(self.owner, self.bp, [q['_id'], newer['_id']], 0, 'bad-selection-key')
        self.service.save_workspace(self.owner, self.bp, [q['_id']], 0, 'good-selection-key')
        with self.assertRaises(WorkflowError): self.service.save_workspace(self.owner, self.bp, [], 0, 'stale-selection-key')
        self.assertEqual(self.service.workspace(self.owner, self.bp)['revision'], 1)

    def test_revalidation_invalidates_prior_approval_and_rejection_blocks_publication(self):
        q = self.question(); self.approve(q)
        self.service.save_workspace(self.owner, self.bp, [q['_id']], 0, 'selection-reviewed-key')
        self.service.validate(self.owner, q['_id'], 'validate-again-key')
        self.assertIsNone(self.service.get_question(self.owner, q['_id'])['review'])
        with self.assertRaises(WorkflowError): self.service.publish(self.owner, self.bp, 1, 'publish-invalidated', True)
        rejected = self.service.review(self.owner, q['_id'], None, 'reject', 'The question statement needs independent clarification.', 'reject-question-key')
        self.assertEqual(rejected['decision'], 'reject')
        with self.assertRaises(WorkflowError): self.service.publish(self.owner, self.bp, 1, 'publish-rejected-key', True)

    def test_no_validator_is_fail_closed_and_fake_pass_bool_is_not_evidence(self):
        q = self.service.save_question(self.owner, coding('function'), 'coding-question-key', blueprint_id=self.bp)
        with self.assertRaises(WorkflowError) as error: self.service.validate(self.owner, q['_id'], 'validate-coding-key')
        self.assertEqual(error.exception.status, 503)
        class Fake:
            def validate(self, *args): return dict(passed=True)
        with self.assertRaises(WorkflowError): AssessmentAuthoringService(self.db, Fake()).validate(self.owner, q['_id'], 'fake-validation-key')
        self.assertEqual(self.db.question_validations.count_documents({}), 0)

    def test_failed_review_is_atomic_and_does_not_change_quality_head(self):
        q = self.question(); v = self.service.validate(self.owner, q['_id'], 'validate-rollback-key')
        before = self.db.question_quality.find_one({})
        original = Collection.insert_one
        def fail(collection, *args, **kwargs):
            if collection.name == 'assessment_content_audit': raise RuntimeError('injected audit failure')
            return original(collection, *args, **kwargs)
        with patch.object(Collection, 'insert_one', fail):
            with self.assertRaises(RuntimeError): self.service.review(self.owner, q['_id'], v['_id'], 'approve', 'Reviewed exact answer correctness.', 'rollback-review-key')
        self.assertEqual(before, self.db.question_quality.find_one({}))
        self.assertEqual(self.db.question_reviews.count_documents({}), 0)

    def test_concurrent_save_and_publish_replays_do_not_duplicate_content(self):
        with ThreadPoolExecutor(max_workers=3) as pool: questions = list(pool.map(lambda _: self.question(), range(3)))
        self.assertTrue(all(q == questions[0] for q in questions))
        q = questions[0]; self.approve(q)
        self.service.save_workspace(self.owner, self.bp, [q['_id']], 0, 'concurrent-selection')
        with ThreadPoolExecutor(max_workers=3) as pool:
            versions = list(pool.map(lambda _: self.service.publish(self.owner, self.bp, 1, 'concurrent-publication', True), range(3)))
        self.assertTrue(all(v == versions[0] for v in versions))
        self.assertEqual(self.db.assessment_versions.count_documents({}), 1)

    def test_http_candidate_and_cross_owner_rejected_and_flag_off_read_preserved(self):
        actor = [self.owner]
        def auth(fn):
            def wrapped(*args, **kwargs): return fn(actor[0], *args, **kwargs)
            wrapped.__name__ = fn.__name__
            return wrapped
        with patch('middleware.auth_middleware.token_required', auth):
            from routes.assessment_authoring_routes import create_assessment_authoring_routes
            with patch('routes.assessment_authoring_routes.token_required', auth):
                app = Flask(__name__); app.register_blueprint(create_assessment_authoring_routes(self.db))
        q = self.question(); client = app.test_client()
        actor[0] = dict(_id=ObjectId(), user_type='candidate')
        self.assertEqual(client.get('/api/question-bank').status_code, 403)
        self.assertEqual(client.get('/api/question-bank/versions/' + q['_id']).status_code, 403)
        self.assertEqual(client.get('/api/assessment-blueprints/' + self.bp + '/content').status_code, 403)
        actor[0] = self.other
        self.assertEqual(client.get('/api/question-bank/versions/' + q['_id']).status_code, 403)
        self.assertEqual(client.get('/api/assessment-blueprints/' + self.bp + '/content').status_code, 403)
        actor[0] = self.owner
        with patch.dict(os.environ, {'GENHIRE_WORKFLOW_ENABLED': 'false'}):
            self.assertEqual(client.get('/api/question-bank/versions/' + q['_id']).status_code, 200)
            self.assertEqual(client.post('/api/question-bank/versions', json={'content': mcq(), 'operation_key': 'flag-disabled-key'}).status_code, 404)


if __name__ == '__main__': unittest.main()
