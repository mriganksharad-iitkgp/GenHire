"""Shared cache behavior with independent workers and no live credentials."""
import os
import time
import unittest
from datetime import datetime, timedelta
from threading import Event
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import fakeredis
import mongomock
from bson import ObjectId
from services.shared_cache import SharedCache, MISSING


class SharedCacheTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'REDIS_URL': 'redis://synthetic', 'FLASK_ENV': 'production',
                                          'DATABASE_NAME': 'cache_tests', 'RATE_LIMIT_NAMESPACE': 'tests'})
        self.env.start(); self.addCleanup(self.env.stop)
        server = fakeredis.FakeServer()
        self.redis = fakeredis.FakeRedis(server=server)
        self.first, self.second = SharedCache(), SharedCache()
        for cache in (self.first, self.second):
            p = patch.object(cache, '_client', return_value=fakeredis.FakeRedis(server=server))
            p.start(); self.addCleanup(p.stop)

    def test_independent_workers_share_json_ttl_and_never_share_mutable_references(self):
        self.first.set('fixture', ['owner'], {'items': [0, False, None]}, 60)
        found = self.second.get('fixture', ['owner'])
        found['items'].append('local edit')
        self.assertEqual(self.first.get('fixture', ['owner']), {'items': [0, False, None]})
        key = self.first.key('fixture', ['owner'])
        self.assertGreater(self.redis.ttl(key), 0)
        self.redis.expire(key, 0)
        # fakeredis expires on the next clock tick rather than synchronously.
        time.sleep(0.01)
        self.assertIs(self.second.get('fixture', ['owner']), MISSING)

    def test_keys_hash_private_inputs_and_partition_environment_database_and_account(self):
        key = self.first.key('fixture', ['private-api-credential', 'candidate@example.test'])
        self.assertNotIn('private-api', key); self.assertNotIn('candidate', key)
        with patch.dict(os.environ, {'FLASK_ENV': 'development'}):
            self.assertNotEqual(key, self.first.key('fixture', ['private-api-credential', 'candidate@example.test']))
        with patch.dict(os.environ, {'DATABASE_NAME': 'another_tenant'}):
            self.assertNotEqual(key, self.first.key('fixture', ['private-api-credential', 'candidate@example.test']))

    def test_corrupt_and_oversized_entries_are_misses_and_writes_are_bounded(self):
        key = self.first.key('fixture', [1])
        self.redis.set(key, b'not-json', ex=10)
        self.assertIs(self.first.get('fixture', [1]), MISSING)
        self.assertFalse(self.first.set('fixture', [2], 'x' * self.first.max_bytes, 10))
        self.assertFalse(self.redis.exists(self.first.key('fixture', [2])))
        with self.assertRaises(ValueError): self.first.set('fixture', [], {}, 3601)

    def test_redis_outage_bypasses_without_memory_fallback_or_credential_logging(self):
        cache = SharedCache()
        broken = MagicMock(); broken.mget.side_effect = ConnectionError('rediss://secret-password@host')
        with patch('middleware.rate_limiter.store._client', return_value=broken), self.assertLogs('services.shared_cache') as logs:
            self.assertEqual(cache.remember('fixture', [], lambda: {'fresh': 1}, 60), {'fresh': 1})
            self.assertEqual(cache.remember('fixture', [], lambda: {'fresh': 2}, 60), {'fresh': 2})
        self.assertNotIn('secret-password', ''.join(logs.output))
        self.assertFalse(hasattr(cache, 'values'))
        broken.mget.assert_called_once()

    def test_distributed_fill_lease_avoids_duplicate_provider_reads(self):
        entered, finish = Event(), Event()
        def load():
            entered.set(); self.assertTrue(finish.wait(5)); return {'cost': 0}
        with ThreadPoolExecutor(2) as pool:
            work = pool.submit(self.first.remember, 'fixture', ['account'], load, 60)
            self.assertTrue(entered.wait(5))
            self.assertIsNone(self.second.remember('fixture', ['account'], lambda: self.fail('duplicate load'), 60))
            finish.set(); self.assertEqual(work.result(), {'cost': 0})
        self.assertEqual(self.second.remember('fixture', ['account'], lambda: self.fail('cache miss'), 60), {'cost': 0})

    def test_lease_release_cannot_delete_a_new_owner_and_missing_is_negative_cached(self):
        lease = self.first.key('fixture', []) + ':loading'
        def load(): self.redis.set(lease, 'new-owner', ex=60); return None
        self.assertIsNone(self.first.remember('fixture', [], load, 60))
        self.assertEqual(self.redis.get(lease), b'new-owner')
        self.assertIsNone(self.second.remember('fixture', [], lambda: self.fail('negative cache miss'), 60))
        self.assertLessEqual(self.redis.ttl(self.first.key('fixture', [])), 15)

    def test_company_cache_is_display_only_and_profile_invalidation_fences_old_readers(self):
        from utils.company_resolver import load_company_map
        from controllers.profile_controller import ProfileController
        users = mongomock.MongoClient().tenant.users
        owner = ObjectId(); users.insert_one({'_id': owner, 'user_type': 'recruiter', 'company_name': 'Before', 'company_logo': 'logo', 'permissions': ['private']})
        parts = [users.database.name, str(owner), '0']
        with patch('utils.company_resolver.cache', self.first), patch.object(users, 'find', wraps=users.find) as find:
            self.assertEqual(load_company_map(users, [owner])[str(owner)]['company_name'], 'Before')
            self.assertEqual(set(load_company_map(users, [owner])[str(owner)]), {'company_name', 'company_logo'})
            self.assertEqual(find.call_count, 1)
            controller = ProfileController({'users': users, 'jobs': users.database.jobs})
            self.assertEqual(controller.update_company_profile(str(owner), {'company_name': 'After'})[1], 200)
            # A pre-update reader finishing late can only populate the old key.
            self.first.set('company-display', parts, {'company_name': 'Before'}, 60)
            self.assertEqual(load_company_map(users, [owner])[str(owner)]['company_name'], 'After')

    def test_provider_cache_rotates_with_credentials_and_preserves_zero_spend(self):
        from services.openai_billing_service import fetch_openai_costs_usd
        start = datetime(2026, 10, 1); end = start + timedelta(days=1)
        response = MagicMock(status_code=200); response.json.return_value = {'data': [], 'has_more': False}
        with patch('services.openai_billing_service.cache', self.first), patch('services.openai_billing_service.requests.get', return_value=response) as get:
            with patch.dict(os.environ, {'OPENAI_ADMIN_API_KEY': 'synthetic-account-one'}):
                self.assertEqual(fetch_openai_costs_usd(start, end), 0)
                self.assertEqual(fetch_openai_costs_usd(start, end), 0)
                self.assertEqual(get.call_count, 1)
            with patch.dict(os.environ, {'OPENAI_ADMIN_API_KEY': 'synthetic-account-two'}):
                self.assertEqual(fetch_openai_costs_usd(start, end), 0)
                self.assertEqual(get.call_count, 2)

    def test_preparation_key_includes_the_entire_document_not_only_a_shared_prefix(self):
        from interview.core.prompt_based_question_generator import PromptBasedQuestionGenerator
        prefix = 'shared text ' * 400
        first = PromptBasedQuestionGenerator._init_cache_key(prefix + 'React', 'JD')
        second = PromptBasedQuestionGenerator._init_cache_key(prefix + 'Python', 'JD')
        self.assertNotEqual(first, second)

    def test_heuristic_preparation_is_shared_and_cannot_reuse_llm_preparation(self):
        from interview.core.prompt_based_question_generator import PromptBasedQuestionGenerator
        from types import SimpleNamespace
        def generator():
            result = object.__new__(PromptBasedQuestionGenerator)
            result.llm = SimpleNamespace(model_name='synthetic-model')
            values = {'_fallback_extract_cv_keywords': ['python'], '_fallback_assess_skill_level': 'intermediate',
                      '_classify_role_difficulty': 'medium', '_extract_job_title': 'Engineer', '_extract_job_role': 'sde',
                      '_load_question_banks_for_role': None, '_extract_candidate_name': 'Candidate',
                      '_extract_experiences': [], '_extract_projects': [], '_extract_cv_keywords': ['python'],
                      '_extract_jd_keywords': ['python'], '_assess_initial_skill_level': 'intermediate',
                      '_analyze_jd_difficulty_distribution': {'easy': 0.3, 'medium': 0.4, 'hard': 0.3}}
            for method, value in values.items(): setattr(result, method, MagicMock(return_value=value))
            result._filter_keywords_by_role = lambda keywords, role: keywords
            return result
        first, second = generator(), generator()
        with patch('interview.core.prompt_based_question_generator.cache', self.first):
            first.initialize_conversation({'skills': 'Python'}, 'Engineer', use_llm=False)
            second.initialize_conversation({'skills': 'Python'}, 'Engineer', use_llm=False)
            second._fallback_extract_cv_keywords.assert_not_called()
            second.initialize_conversation({'skills': 'Python'}, 'Engineer', use_llm=True)
            second._extract_cv_keywords.assert_called_once()


if __name__ == '__main__': unittest.main()
