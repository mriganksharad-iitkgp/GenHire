from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
import unittest
from unittest.mock import patch
from bson import ObjectId
from workflow_test_support import MongoTestCase
from assessment_test_fixtures import mcq
from models.hiring_workflow import WorkflowError
from models.job_setup import default_setup
from services.job_setup_service import JobSetupService, ensure_setup_indexes
from services.assessment_authoring_service import ensure_authoring_indexes
from services.assessment_generation_service import AssessmentGenerationService, ensure_generation_indexes, parse_generated, source_material


class StrictGenerationTests(unittest.TestCase):
    def test_pasted_source_is_bounded_requires_text_and_never_fetches_links(self):
        base=dict(statement='Given a list of integers, return their sum.',test_strategy='generate_and_review',reference_url='https://example.test/problem')
        with patch('requests.get',side_effect=AssertionError('Problem URLs must not be fetched')):
            self.assertEqual(source_material(base)['reference_url'],base['reference_url'])
        for patch_values in [dict(statement='https://example.test'),dict(statement=''),dict(statement='x'*8001),
                             dict(reference_url='https://name:password@example.test/'),dict(reference_url='file:///private'),
                             dict(test_strategy='use_provided_cases'),dict(test_strategy='reference_solution')]:
            with self.subTest(patch_values=patch_values),self.assertRaises(WorkflowError):source_material(dict(base,**patch_values))
        self.assertEqual(source_material(dict(base,test_strategy='use_provided_cases',provided_tests='input: 2 3, output: 5'))['provided_tests'],'input: 2 3, output: 5')
    def test_malformed_duplicate_keys_nonfinite_and_wrong_slots_are_rejected(self):
        spec = [dict(type='mcq', difficulty='easy', marks=1)]
        for raw in ('{"questions":[],"questions":[]}', '{"questions":NaN}', '```json\n{}\n```',
                    json.dumps({'questions': [dict(mcq(), marks=2)]}), json.dumps({'questions': []})):
            with self.subTest(raw=raw), self.assertRaises(WorkflowError): parse_generated(raw, spec)
        self.assertEqual(parse_generated(json.dumps({'questions': [mcq()]}), spec), [mcq()])


class GenerationTransactionTests(MongoTestCase):
    def setUp(self):
        super().setUp()
        self.settings = patch.dict(os.environ, {'GENHIRE_ASSESSMENT_GENERATION_ENABLED': 'true',
            'GENHIRE_OA_JOB_SETUP_CREDITS': '30', 'RECRUITER_AI_JD_CREDITS':'10', 'GENHIRE_OA_REGENERATION_CREDITS': '10'})
        self.settings.start(); self.addCleanup(self.settings.stop)
        ensure_setup_indexes(self.db); ensure_authoring_indexes(self.db); ensure_generation_indexes(self.db)
        self.actor = dict(_id=ObjectId(), user_type='recruiter', is_verified=True)
        self.db.users.insert_one(self.actor)
        setup = default_setup(); setup['pipeline']['oa_enabled'] = True
        setup['oa'].update(source='hybrid', template_id='custom', duration_minutes=5,
            sections=[dict(type='mcq', count=1, difficulty=dict(easy=1, medium=0, hard=0), marks=[1], weight=100, duration_minutes=5)])
        service = JobSetupService(self.db)
        draft = service.save(self.actor, setup, {}, 'gen-test-setup')
        self.job = service.attach(self.actor, draft['_id'], 1, dict(_id=ObjectId(), created_by=str(self.actor['_id']), status='draft'), 'gen-job-hash', creating=True)
        self.blueprint = str(self.db.assessment_blueprints.find_one({})['_id'])
        from payment_module.services.billing_operation_service import BillingOperationService
        self.billing = BillingOperationService(self.db)
        self.billing.wallet.credit_wallet(str(self.actor['_id']), 'recruiter', 100, 'recharge', idempotency_key='generation-initial-credit')
        class Llm:
            calls = 0
            def invoke(inner, *args, **kwargs):
                inner.calls += 1
                inner.prompt = args[0]
                return dict(content=json.dumps({'questions': [mcq()]}), provider='test-only')
        self.llm = Llm()
        self.service = AssessmentGenerationService(self.db, llm=self.llm, billing=self.billing)

    def wallet(self): return self.db.credit_wallets.find_one({'owner_id': str(self.actor['_id']), 'audience': 'recruiter'})

    def test_pasted_problem_quote_preserves_context_through_the_worker(self):
        source=dict(statement='Choose the even integer from the supplied options.',test_strategy='use_provided_cases',
                    provided_tests='Two is even, three is odd.',reference_url='https://example.test/problem')
        spec=dict(type='mcq',difficulty='easy',marks=1)
        quote=self.service.create_quote(self.actor,self.blueprint,[spec],problem_source=source)
        job=self.service.enqueue(self.actor,quote['_id'],'pasted-problem-job',True)
        self.assertEqual(self.db.assessment_generation_jobs.find_one({'_id':ObjectId(job['id'])})['problem_source']['statement'],source['statement'])
        self.assertTrue(self.service.run_once())
        self.assertIn(source['statement'],self.llm.prompt)
        self.assertIn('attribution only',self.llm.prompt)
        self.assertEqual(self.service.get(self.actor,job['id'])['state'],'completed')

    def quote(self, previous=None):
        spec = dict(type='mcq', difficulty='easy', marks=1)
        if previous: spec['previous_version_id'] = previous
        return self.service.create_quote(self.actor, self.blueprint, [spec])

    def start(self, previous=None, key='generate-initial-job'):
        quote = self.quote(previous)
        return self.service.enqueue(self.actor, quote['_id'], key, True)

    def test_quoted_concurrent_replay_generates_once_and_holds_setup_until_activation(self):
        quote = self.quote()
        self.assertEqual(quote['total_to_reserve'], 40)
        with self.assertRaises(WorkflowError): self.service.enqueue(self.actor, quote['_id'], 'approval-required', False)
        with ThreadPoolExecutor(max_workers=3) as pool:
            jobs = list(pool.map(lambda _: self.service.enqueue(self.actor, quote['_id'], 'same-generation-key', True), range(3)))
        self.assertTrue(all(j == jobs[0] for j in jobs))
        self.assertEqual(self.wallet()['balance'], 100)
        self.assertTrue(self.service.run_once())
        self.assertEqual(self.llm.calls, 1)
        self.assertEqual(self.service.get(self.actor, jobs[0]['id'])['state'], 'completed')
        self.assertEqual(self.wallet()['balance'], 60)
        self.assertEqual(self.wallet()['reserved_credits'], 30)
        self.assertEqual(self.wallet()['total_debited'], 10)
        q = self.db.question_versions.find_one({})
        self.assertEqual(q['source'], 'ai')
        self.assertIsNone(self.service.authoring.get_question(self.actor, str(q['_id']))['review'])
        other_key = self.service.enqueue(self.actor, quote['_id'], 'different-generation-key', True)
        self.assertEqual(other_key['id'], jobs[0]['id'])
        self.assertEqual(self.db.assessment_generation_jobs.count_documents({}), 1)
        self.assertFalse(self.service.run_once())

    def test_failed_generated_schema_releases_setup_reservation(self):
        job = self.start()
        self.llm.invoke = lambda *a, **k: dict(content='{"questions":[],"questions":[]}')
        self.service.run_once()
        self.assertEqual(self.service.get(self.actor, job['id'])['state'], 'failed')
        self.assertEqual(self.wallet()['balance'], 100)
        self.assertEqual(self.wallet()['reserved_credits'], 0)
        self.assertEqual(self.db.question_versions.count_documents({}), 0)

    def test_release_unactivated_hold_still_works_with_both_flags_disabled(self):
        self.start(); self.service.run_once()
        with patch.dict(os.environ, {'GENHIRE_WORKFLOW_ENABLED': 'false', 'GENHIRE_ASSESSMENT_GENERATION_ENABLED': 'false'}):
            release = self.service.release_setup_hold(self.actor, self.blueprint, 'release-held-setup')
            self.service.run_once()
            self.assertEqual(self.service.get(self.actor, release['id'])['state'], 'completed')
        self.assertEqual(self.wallet()['balance'], 90)
        self.assertEqual(self.wallet()['reserved_credits'], 0)
        self.assertEqual(self.db.question_versions.count_documents({}), 1)

    def test_regeneration_captures_only_quoted_extra_and_preserves_old_version(self):
        self.start(); self.service.run_once()
        old = self.db.question_versions.find_one({})
        quote = self.quote(str(old['_id']))
        self.assertEqual(quote['setup_hold_credits'], 0)
        self.assertEqual(quote['regeneration_credits'], 10)
        self.service.enqueue(self.actor, quote['_id'], 'regenerate-one-question', True)
        self.service.run_once()
        self.assertEqual(self.wallet()['balance'], 50)
        self.assertEqual(self.wallet()['total_debited'], 20)
        self.assertEqual(self.wallet()['reserved_credits'], 30)
        self.assertEqual(self.db.question_versions.count_documents({}), 2)
        self.assertEqual(self.db.question_versions.find_one({'_id': old['_id']}), old)

    def test_expired_external_call_lease_compensates_without_repeating_llm(self):
        job = self.start()
        saved = self.db.assessment_generation_jobs.find_one({'_id': ObjectId(job['id'])})
        self.billing.reserve(saved['owner_id'], 'recruiter', 30, saved['funding_key'], 'oa_initial_setup')
        self.db.assessment_generation_jobs.update_one({'_id': saved['_id']}, {'$set': {'state': 'generating', 'lease_until': datetime.now(timezone.utc) - timedelta(seconds=1)}})
        self.service.run_once()
        self.assertEqual(self.llm.calls, 0)
        self.assertEqual(self.wallet()['balance'], 100)
        self.assertEqual(self.service.get(self.actor, job['id'])['state'], 'failed')

    def test_settlement_retry_does_not_regenerate_or_charge_twice(self):
        self.start(); self.service.run_once()
        old = self.db.question_versions.find_one({})
        job = self.start(str(old['_id']), 'regenerate-settlement')
        original = self.billing.settle
        with patch.object(self.billing, 'settle', side_effect=RuntimeError('temporary settlement failure')):
            self.service.run_once()
        self.assertEqual(self.service.get(self.actor, job['id'])['state'], 'settling')
        calls = self.llm.calls
        self.db.assessment_generation_jobs.update_one({'_id': ObjectId(job['id'])}, {'$set': {'lease_until': datetime.now(timezone.utc)}})
        self.service.run_once()
        self.assertEqual(self.llm.calls, calls)
        self.assertEqual(self.service.get(self.actor, job['id'])['state'], 'completed')
        self.assertEqual(self.wallet()['total_debited'], 20)

    def test_revoked_actor_cannot_start_provider_work_and_changed_prices_requote(self):
        quote = self.quote()
        with patch.dict(os.environ, {'GENHIRE_OA_JOB_SETUP_CREDITS': '31'}):
            with self.assertRaises(WorkflowError): self.service.enqueue(self.actor, quote['_id'], 'stale-price-job', True)
        job = self.start()
        self.db.users.update_one({'_id': self.actor['_id']}, {'$set': {'is_verified': False}})
        self.service.run_once()
        self.assertEqual(self.llm.calls, 0)
        self.assertEqual(self.wallet()['balance'], 100)
        self.assertEqual(self.service.get(self.actor, job['id'])['state'], 'failed')


if __name__ == '__main__': unittest.main()
