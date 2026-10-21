from copy import deepcopy
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from bson import ObjectId
import mongomock
from flask import Flask
from workflow_test_support import MongoTestCase
from config.workflow import managed, workflow_enabled
from models.hiring_workflow import WorkflowError, screening_only, validate_stages, legacy_snapshot, projection
from services.workflow_service import WorkflowService, public_workflow
from repositories.workflow_repository import ensure_workflow_indexes
from repositories.application_repository import ApplicationRepository


def migration_module():
    spec = importlib.util.spec_from_file_location('_workflow_migration',
        Path(__file__).resolve().parents[1] / 'scripts/migrations/migrate_hiring_workflows.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WorkflowModelTests(unittest.TestCase):
    def test_flag_defaults_off_and_requires_explicit_true(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(workflow_enabled())
        with patch.dict(os.environ, {'GENHIRE_WORKFLOW_ENABLED': 'false'}):
            self.assertFalse(workflow_enabled())

    def test_legacy_mapping_never_invents_screening_results(self):
        for status in ('pending', 'reviewed', 'shortlisted'):
            snap = legacy_snapshot({'status': status}, screening_only())
            self.assertNotEqual(snap['stages'][1]['state'], 'completed')
        for status in ('selected', 'screening_cleared'):
            snap = legacy_snapshot({'status': status, 'interview_score': 76}, screening_only())
            self.assertEqual(projection(snap)['status'], 'screening_cleared')
        for app in ({'status': 'rejected'}, {'status': 'interviewed', 'interview_score': None}):
            with self.assertRaises(WorkflowError):
                legacy_snapshot(app, screening_only())

    def test_invalid_pipelines_and_thresholds_are_rejected(self):
        for value in (float('nan'), float('inf'), True, -1, 101, '80'):
            stages = screening_only()
            stages[1]['policy'] = {'interview_minimum': value}
            with self.assertRaises(WorkflowError):
                validate_stages(stages)
        stages = screening_only()
        stages.append(dict(stages[0]))
        with self.assertRaises(WorkflowError):
            validate_stages(stages)

    def test_migration_dry_run_repeatable_read_only_and_reports_ambiguity(self):
        db = mongomock.MongoClient().db
        job = ObjectId()
        db.jobs.insert_one({'_id': job, 'created_by': str(ObjectId())})
        db.applications.insert_many([
            {'job_id': str(job), 'status': 'rejected'},
            {'job_id': str(job), 'status': 'screening_cleared', 'interview_score': 80, 'processing_status': 'completed'},
            {'job_id': str(job), 'status': 'pending', 'processing_status': 'processing'},
        ])
        before = {name: list(db[name].find()) for name in db.list_collection_names()}
        migrate = migration_module().migrate
        first = migrate(db, str(job))
        self.assertEqual(first, migrate(db, str(job)))
        self.assertEqual(first['counts'], {'ambiguous_legacy': 1, 'eligible': 1, 'processing_not_complete': 1})
        self.assertEqual(before, {name: list(db[name].find()) for name in db.list_collection_names()})


class WorkflowTransactionTests(MongoTestCase):
    def setUp(self):
        super().setUp()
        ensure_workflow_indexes(self.db)
        self.actor = dict(_id=ObjectId(), user_type='recruiter', is_verified=True)
        self.candidate = dict(_id=ObjectId(), user_type='candidate')
        self.job_id, self.app_id = ObjectId(), ObjectId()
        self.db.jobs.insert_one(dict(_id=self.job_id, created_by=str(self.actor['_id']), title='Engineer'))
        self.db.applications.insert_one(dict(_id=self.app_id, job_id=str(self.job_id), student_id=str(self.candidate['_id']),
            status='screening_cleared', interview_score=80, proctoring_score=95, processing_status='completed'))
        self.service = WorkflowService(self.db)
        self.stages = screening_only() + [dict(id='oa', type='oa', name='Online assessment', enabled=True, policy={}),
                                       dict(id='technical', type='company', name='Company technical', enabled=True, policy={})]
        self.version = self.service.publish_version(str(self.job_id), self.actor, self.stages, 0, 'publish:initial')['version_id']

    def adopt(self):
        return self.service.adopt(str(self.app_id), self.actor, self.version, 'import:initial')

    def action(self, action, revision, key='action:initial', reason='Reviewed results'):
        return self.service.transition(str(self.app_id), self.actor, action, revision, key, reason)

    def test_snapshot_is_versioned_and_existing_application_not_silently_changed(self):
        self.adopt()
        self.service.publish_version(str(self.job_id), self.actor, screening_only(), 1, 'publish:changed')
        app = self.db.applications.find_one({'_id': self.app_id})
        self.assertEqual(app['workflow_version_id'], self.version)
        self.assertEqual(len(app['workflow']['stages']), 4)
        self.assertEqual(self.db.application_stages.count_documents({'application_id': str(self.app_id)}), 4)

    def test_clearance_is_distinct_from_oa_eligibility_and_not_an_invitation(self):
        self.adopt()
        result = self.action('advance', 0)
        self.assertEqual(result['current_stage_id'], 'oa')
        app = self.db.applications.find_one({'_id': self.app_id})
        oa = app['workflow']['stages'][2]
        self.assertEqual((oa['state'], oa['outcome']), ('eligible', 'pending'))
        self.assertEqual(self.db.notification_outbox.count_documents({}), 0)
        with self.assertRaises(WorkflowError):
            self.action('clear', 1, 'action:clear-oa')

    def test_replay_stale_request_and_conflicting_key(self):
        self.adopt()
        first = self.action('advance', 0)
        self.assertEqual(first, self.action('advance', 0))
        self.assertEqual(self.db.stage_events.count_documents({}), 2)
        for action, revision, key in [('advance', 0, 'action:another'), ('review', 0, 'action:initial')]:
            with self.assertRaises(WorkflowError):
                self.action(action, revision, key)

    def test_permission_checks_precede_mutation_or_replay(self):
        self.adopt()
        for actor in (dict(_id=ObjectId(), user_type='recruiter', is_verified=True), self.candidate,
                      dict(_id=ObjectId(), user_type='admin', permissions=[]), dict(self.actor, is_verified=False)):
            with self.assertRaises(WorkflowError):
                self.service.transition(str(self.app_id), actor, 'advance', 0, 'action:forbidden', 'Reviewed result')
        self.assertEqual(self.db.stage_events.count_documents({}), 1)

    def test_candidate_withdrawal_preserves_history_and_terminal_state(self):
        self.adopt()
        self.service.transition(str(self.app_id), self.candidate, 'withdraw', 0, 'withdraw:own', 'I withdraw')
        self.assertEqual(self.db.applications.find_one({'_id': self.app_id})['workflow']['lifecycle'], 'withdrawn')
        with self.assertRaises(WorkflowError):
            self.action('advance', 1)
        self.assertIsNotNone(self.db.stage_events.find_one({'action': 'withdraw'}))

    def test_candidate_history_excludes_internal_reasons_actors_and_policy(self):
        self.adopt()
        history = self.service.history(str(self.app_id), self.candidate)
        self.assertEqual(set(history['events'][0]), {'revision', 'action', 'occurred_at'})
        self.assertNotIn('policy', str(history['workflow']))
        with self.assertRaises(WorkflowError):
            self.service.history(str(self.app_id), dict(_id=ObjectId(), user_type='candidate'))

    def test_failed_event_insert_rolls_back_application_and_stage_views(self):
        self.adopt()
        before = self.db.applications.find_one({'_id': self.app_id})
        from pymongo.collection import Collection
        original = Collection.insert_one
        def fail_event(collection, *args, **kwargs):
            if collection.name == 'stage_events':
                raise RuntimeError('injected crash before history write')
            return original(collection, *args, **kwargs)
        with patch.object(Collection, 'insert_one', fail_event):
            with self.assertRaises(RuntimeError):
                self.action('advance', 0)
        self.assertEqual(self.db.applications.find_one({'_id': self.app_id}), before)
        self.assertEqual(self.db.application_stages.find_one({'stage_id': 'oa'})['state'], 'not_ready')

    def test_concurrent_transitions_use_revision_and_idempotency(self):
        from concurrent.futures import ThreadPoolExecutor
        self.adopt()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.action('advance', 0), range(12)))
        self.assertTrue(all(r == results[0] for r in results))
        self.assertEqual(self.db.stage_events.count_documents({}), 2)

    def test_old_repository_is_fenced_even_after_flag_disabled(self):
        self.adopt()
        repo = ApplicationRepository(self.db.applications)
        with patch.dict(os.environ, {'GENHIRE_WORKFLOW_ENABLED': 'false'}):
            self.assertEqual(repo.update_by_id(self.app_id, {'$set': {'status': 'rejected'}}).matched_count, 0)
            self.assertEqual(repo.delete_by_id(self.app_id).deleted_count, 0)
            with self.assertRaises(WorkflowError):
                self.action('advance', 0)
            self.assertIsNotNone(self.service.history(str(self.app_id), self.candidate)['workflow'])

    def test_admin_legacy_update_delete_race_returns_conflict_and_keeps_history(self):
        from controllers.admin.application_admin import ApplicationAdmin
        from repositories.base_repository import BaseRepository
        admin = ApplicationAdmin()
        admin.application_repo = ApplicationRepository(self.db.applications)
        admin.job_repo = BaseRepository(self.db.jobs)
        legacy_read = self.db.applications.find_one({'_id': self.app_id})
        self.adopt()
        with patch.object(admin.application_repo, 'find_one_by_id', return_value=legacy_read):
            self.assertEqual(admin.update_application_status(self.actor, str(self.app_id), 'rejected')[1], 409)
            self.assertEqual(admin.update_application(self.actor, str(self.app_id), {'status': 'rejected'})[1], 409)
            self.assertEqual(admin.delete_application(self.actor, str(self.app_id))[1], 409)
        self.assertTrue(managed(self.db.applications.find_one({'_id': self.app_id})))
        self.assertEqual(self.db.stage_events.count_documents({}), 1)

    def test_legacy_repository_behavior_unchanged(self):
        repo = ApplicationRepository(self.db.applications)
        self.assertEqual(repo.update_by_id(self.app_id, {'$set': {'status': 'interviewed'}}).matched_count, 1)
        self.assertFalse(managed(repo.find_one_by_id(self.app_id)))

    def test_migration_apply_idempotent_and_refuses_active_interview(self):
        self.db.interviews.insert_one({'application_id': str(self.app_id), 'status': 'active'})
        with self.assertRaises(WorkflowError):
            self.adopt()
        self.db.interviews.delete_many({})
        migrate = migration_module().migrate
        report = migrate(self.db, str(self.job_id), apply=True, actor=self.actor)
        self.assertEqual(report['counts'], {'adopted': 1})
        self.assertEqual(migrate(self.db, str(self.job_id), apply=True, actor=self.actor)['counts'], {'already_managed': 1})
        self.assertEqual(self.db.stage_events.count_documents({}), 1)

    def test_pending_evaluation_and_unsynchronized_completed_interview_cannot_migrate(self):
        self.db.interviews.insert_one({'application_id': str(self.app_id), 'status': 'completed',
                                      'evaluation': {'pending_answers': 1}})
        with self.assertRaises(WorkflowError):
            self.adopt()
        self.db.interviews.update_one({}, {'$set': {'evaluation': {}}})
        self.db.applications.update_one({}, {'$set': {'interview_score': None, 'status': 'shortlisted'}})
        with self.assertRaises(WorkflowError):
            self.adopt()
        self.assertEqual(self.db.stage_events.count_documents({}), 0)

    def test_deferred_report_score_must_reach_application_before_adoption(self):
        self.db.interviews.insert_one({'application_id': str(self.app_id), 'status': 'completed', 'interview_score': 83})
        with self.assertRaises(WorkflowError):
            self.adopt()
        self.db.applications.update_one({}, {'$set': {'interview_score': 83}})
        self.adopt()
        self.assertTrue(managed(self.db.applications.find_one({'_id': self.app_id})))

    def test_history_is_bounded_and_reconciliation_detects_missing_stage_projection(self):
        self.adopt()
        self.action('advance', 0)
        first = self.service.history(str(self.app_id), self.candidate, limit=1)
        self.assertTrue(first['has_more'])
        second = self.service.history(str(self.app_id), self.candidate, first['next_after_revision'], limit=1)
        self.assertFalse(second['has_more'])
        self.assertEqual(second['events'][0]['revision'], 1)
        spec = importlib.util.spec_from_file_location('_foundation_audit',
            Path(__file__).resolve().parents[1] / 'scripts/admin/audit_workflow_foundation.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.audit(self.db, job_id=str(self.job_id))['workflow_issues'], [])
        self.db.application_stages.delete_one({'stage_id': 'oa'})
        report = module.audit(self.db, job_id=str(self.job_id))
        self.assertEqual(report['workflow_issues'][0]['issue'], 'stage_projection_mismatch')

    def test_different_concurrent_decisions_cannot_both_use_the_same_revision(self):
        from concurrent.futures import ThreadPoolExecutor
        self.adopt()
        def decide(action):
            try:
                return self.action(action, 0, 'action:race:' + action)
            except WorkflowError as exc:
                return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(decide, ['review', 'not_clear']))
        self.assertEqual(sum(isinstance(r, dict) for r in results), 1)
        self.assertIn('stale_revision', results)
        self.assertEqual(self.db.stage_events.count_documents({}), 2)

    def test_http_validation_flag_and_history_authorization(self):
        # Inject authenticated principals only; middleware JWT behavior has its
        # own regression tests. No production app/provider/database startup.
        from routes import workflow_routes
        def authenticated(fn):
            from functools import wraps
            @wraps(fn)
            def wrapped(*args, **kwargs):
                return fn(self.actor, *args, **kwargs)
            return wrapped
        app = Flask(__name__)
        with patch.object(workflow_routes, 'token_required', authenticated):
            app.register_blueprint(workflow_routes.create_workflow_routes(self.db))
        client = app.test_client()
        endpoint = f'/api/applications/{self.app_id}/stage-actions'
        self.assertEqual(client.post(endpoint, json=[]).status_code, 400)
        self.assertEqual(client.post(endpoint, json={'action': 'clear', 'score': 100}).status_code, 400)
        with patch.dict(os.environ, {'GENHIRE_WORKFLOW_ENABLED': 'false'}):
            self.assertEqual(client.post(endpoint, json={}).status_code, 404)


if __name__ == '__main__':
    unittest.main()
