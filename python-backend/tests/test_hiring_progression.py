from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib
import os
import unittest
from unittest.mock import patch
from bson import ObjectId
from flask import Flask
from workflow_test_support import MongoTestCase
from assessment_test_fixtures import mcq
from models.hiring_workflow import WorkflowError
from models.job_setup import default_setup
from services.job_setup_service import JobSetupService, ensure_setup_indexes
from services.assessment_authoring_service import AssessmentAuthoringService, ensure_authoring_indexes
from repositories.workflow_repository import ensure_workflow_indexes
from services.hiring_progression_service import HiringProgressionService, qualification, ensure_progression_indexes, utc
from services.hiring_scheduler import HiringScheduler


class ScreeningPolicyTests(unittest.TestCase):
    def test_separate_thresholds_pending_unknown_partial_zero_and_late_evidence(self):
        now = datetime.now(timezone.utc)
        policy = dict(interview_minimum=60, require_proctoring=True, proctoring_minimum=80)
        doc = dict(status='completed', finished_at=now, final_score=60, proctoring_score=80, proctoring_status='complete', evaluation={'score_status': 'complete'})
        self.assertEqual(qualification(doc, policy, now), ('cleared', 'screening_thresholds_met'))
        cases = [({'final_score': 59}, 'not_cleared'), ({'proctoring_score': 79}, 'not_cleared'),
            ({'proctoring_score': None}, 'review_required'), ({'proctoring_status': 'partial'}, 'review_required'),
            ({'final_score': float('nan')}, 'review_required'), ({'final_score': True}, 'review_required'),
            ({'evaluation': {'score_status': 'partial'}}, 'review_required'),
            ({'evaluation': {'pending_answers': 1}}, 'pending'), ({'finished_at': None}, 'review_required'),
            ({'finished_at': now+timedelta(microseconds=1)}, 'review_required'), ({'status': 'terminated'}, 'review_required')]
        for update, outcome in cases:
            with self.subTest(update=update): self.assertEqual(qualification(dict(doc, **update), policy, now)[0], outcome)
        self.assertEqual(qualification(dict(doc, final_score=0), dict(policy, interview_minimum=0), now)[0], 'cleared')
        self.assertEqual(qualification(doc, dict(policy, interview_minimum=None), now)[0], 'review_required')


class ProgressionTransactionTests(MongoTestCase):
    def setUp(self):
        super().setUp()
        self.flags = patch.dict(os.environ, dict(GENHIRE_SCHEDULING_ENABLED='true', GENHIRE_OA_ATTEMPT_CREDITS='5',
            GENHIRE_OA_JOB_SETUP_CREDITS='30', GENHIRE_HIRING_EMAILS_ENABLED='false'))
        self.flags.start(); self.addCleanup(self.flags.stop)
        for ensure in (ensure_setup_indexes, ensure_authoring_indexes, ensure_workflow_indexes, ensure_progression_indexes): ensure(self.db)
        self.now = datetime(2027, 1, 1, tzinfo=timezone.utc)
        self.actor = dict(_id=ObjectId(), user_type='recruiter', is_verified=True)
        self.candidate = dict(_id=ObjectId(), user_type='candidate', is_invite_only=True, email='candidate@example.test', access_expires_at=self.now)
        self.db.users.insert_many([self.actor, self.candidate])
        self.config = default_setup(self.now)
        self.config['pipeline'].update(oa_enabled=True)
        self.config['qualification'].update(interview_minimum=60, require_proctoring=True, proctoring_minimum=80)
        self.config['oa'].update(template_id='custom', source='manual', duration_minutes=5,
            sections=[dict(type='mcq', count=1, difficulty=dict(easy=1, medium=0, hard=0), marks=[1], weight=100, duration_minutes=5)])
        self.config['schedule'].update(application_closes_at=(self.now+timedelta(days=1)).isoformat(), screening_opens_at=(self.now+timedelta(days=1)).isoformat(),
            screening_closes_at=(self.now+timedelta(days=2)).isoformat(), oa_opens_at=(self.now+timedelta(days=3)).isoformat(), oa_start_closes_at=(self.now+timedelta(days=4)).isoformat())
        setup = JobSetupService(self.db)
        draft = setup.save(self.actor, self.config, {}, 'progression-setup')
        self.job = setup.attach(self.actor, draft['_id'], 1, dict(_id=ObjectId(), created_by=str(self.actor['_id']), status='draft',
            proctoring_config=dict(voice_detection=True)), 'progression-job-hash', creating=True)
        self.job_id = str(self.job['_id'])
        self.blueprint_id = str(self.db.assessment_blueprints.find_one({})['_id'])
        self.authoring = AssessmentAuthoringService(self.db)
        q = self.authoring.save_question(self.actor, mcq(), 'progression-question')
        validation = self.authoring.validate(self.actor, q['_id'], 'progression-validate')
        self.authoring.review(self.actor, q['_id'], validation['_id'], 'approve', 'Independently checked the correct answer.', 'progression-review')
        self.authoring.save_workspace(self.actor, self.blueprint_id, [q['_id']], 0, 'progression-selection')
        self.content = self.authoring.publish(self.actor, self.blueprint_id, 1, 'progression-content', True)
        self.service = HiringProgressionService(self.db, lambda: self.now)
        from payment_module.services.billing_operation_service import BillingOperationService
        self.billing = BillingOperationService(self.db)
        self.billing.wallet.credit_wallet(str(self.actor['_id']), 'recruiter', 100, 'recharge', idempotency_key='progression-initial-credit')
        self.service._billing = self.billing

    def activate(self):
        quote = self.service.activation_quote(self.actor, self.job_id, self.content['_id'])
        return self.service.activate(self.actor, quote['_id'], 'progression-activate', True)

    def app(self): return self.db.applications.find_one({'_id': self.app_id})

    def enroll(self):
        version = self.activate()
        self.version_id = version['version_id']
        self.app_id = ObjectId()
        self.db.applications.insert_one(dict(_id=self.app_id, job_id=self.job_id, student_id=str(self.candidate['_id']), recruiter_id=str(self.actor['_id']),
            status='shortlisted', processing_status='completed', cv_snapshot={'text': 'test fixture CV'}, hiring_enrollment_version_id=self.version_id))
        self.service.enroll(str(self.app_id))

    def completed(self, **updates):
        self.now = utc(self.config['schedule']['screening_closes_at'])
        doc = dict(_id=ObjectId(), application_id=str(self.app_id), user_id=str(self.candidate['_id']), status='completed', finished_at=self.now,
            final_score=70, proctoring_score=90, proctoring_status='complete', evaluation={'score_status': 'complete'}, workflow_version_id=self.version_id)
        doc.update(updates); self.db.interviews.insert_one(doc)
        self.service.ingest_screening(str(doc['_id']))
        return doc

    def invitation(self):
        self.enroll(); self.completed()
        result = self.service.invite(self.actor, str(self.app_id), self.app()['workflow']['revision'], 'progression-invite', 'Proceed to the approved online assessment.')
        return self.db.assessment_invitations.find_one({'_id': ObjectId(result['invitation_id'])})

    def test_activation_concurrent_quote_replay_captures_once_and_leaves_old_candidates(self):
        old_id = self.db.applications.insert_one(dict(job_id=self.job_id, student_id='legacy', status='pending')).inserted_id
        quote = self.service.activation_quote(self.actor, self.job_id, self.content['_id'])
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda k: self.service.activate(self.actor, quote['_id'], k, True), ['activation-retry-A', 'activation-retry-B']))
        self.assertEqual(results[0], results[1])
        wallet = self.db.credit_wallets.find_one({})
        self.assertEqual((wallet['balance'], wallet['reserved_credits'], wallet['total_debited']), (70, 0, 30))
        self.assertEqual(self.db.hiring_workflow_versions.count_documents({}), 1)
        self.assertNotIn('workflow_version_id', self.db.applications.find_one({'_id': old_id}))

    def test_activation_transaction_rolls_back_billing_and_version_on_write_failure(self):
        quote = self.service.activation_quote(self.actor, self.job_id, self.content['_id'])
        with patch.object(type(self.db.hiring_workflow_versions), 'insert_one', side_effect=RuntimeError('injected failure')):
            with self.assertRaises(RuntimeError): self.service.activate(self.actor, quote['_id'], 'activation-failure', True)
        self.assertEqual(self.db.credit_wallets.find_one({})['balance'], 100)
        self.assertEqual(self.db.billing_operations.count_documents({}), 0)
        self.assertEqual(self.db.jobs.find_one({})['status'], 'draft')

    def test_activation_uses_existing_generation_hold_without_second_debit(self):
        self.billing.reserve(str(self.actor['_id']), 'recruiter', 30, 'oa-existing-hold', 'oa_job_setup')
        self.db.assessment_setup_funding.insert_one(dict(_id=self.job_id, key='oa-existing-hold', state='reserved', cycle=1, credits=30))
        self.activate()
        self.assertEqual(self.db.credit_wallets.find_one({})['balance'], 70)
        self.assertEqual(self.db.billing_operations.count_documents({}), 1)
        self.assertEqual(self.db.assessment_setup_funding.find_one({})['state'], 'captured')

    def test_activation_requires_current_review_price_flag_and_owner(self):
        with patch.dict(os.environ, {'GENHIRE_OA_ATTEMPT_CREDITS': ''}):
            with self.assertRaises(WorkflowError): self.service.activation_quote(self.actor, self.job_id, self.content['_id'])
        other = dict(self.actor, _id=ObjectId())
        with self.assertRaises(WorkflowError): self.service.activation_quote(other, self.job_id, self.content['_id'])
        quote = self.service.activation_quote(self.actor, self.job_id, self.content['_id'])
        with patch.dict(os.environ, {'GENHIRE_OA_JOB_SETUP_CREDITS': '31'}):
            with self.assertRaises(WorkflowError): self.service.activate(self.actor, quote['_id'], 'activation-reprice', True)
        self.db.jobs.update_one({'_id': ObjectId(self.job_id)}, {'$set': {'proctoring_config.dual_camera': True}})
        with self.assertRaises(WorkflowError) as exc: self.service.activate(self.actor, quote['_id'], 'activation-monitoring-change', True)
        self.assertEqual(exc.exception.code, 'monitoring_changed')
        self.db.jobs.update_one({'_id': ObjectId(self.job_id)}, {'$unset': {'proctoring_config.dual_camera': ''}})
        q = self.db.question_versions.find_one({}); v = self.db.question_validations.find_one({})
        self.authoring.review(self.actor, str(q['_id']), str(v['_id']), 'reject', 'A corrected question is required.', 'activation-reject-question')
        with self.assertRaises(WorkflowError): self.service.activate(self.actor, quote['_id'], 'activation-rejected', True)
        self.assertEqual(self.db.credit_wallets.find_one({})['balance'], 100)

    def test_enrollment_window_and_managed_screening_persistence(self):
        self.enroll()
        frozen = self.db.hiring_workflow_versions.find_one({'_id': ObjectId(self.version_id)})['screening_proctoring_config']
        self.db.jobs.update_one({'_id': ObjectId(self.job_id)}, {'$set': {'proctoring_config': {k: False for k in frozen}}})
        self.assertEqual(self.service.version(self.version_id)['screening_proctoring_config'], frozen)
        with self.assertRaises(WorkflowError): self.service.screening_start(self.app(), str(self.candidate['_id']))
        self.now = utc(self.config['schedule']['screening_opens_at'])
        self.assertEqual(self.service.screening_start(self.app(), str(self.candidate['_id']))['version_id'], self.version_id)
        doc = dict(session_id='screening-fixture', user_id=str(self.candidate['_id']), application_id=str(self.app_id), status='setup')
        self.service.persist_screening_session(str(self.app_id), self.candidate['_id'], doc)
        self.assertEqual(self.app()['workflow']['stages'][1]['state'], 'in_progress')
        self.assertEqual(utc(self.db.interviews.find_one({})['screening_finish_by']), utc(self.config['schedule']['screening_closes_at']))
        with self.assertRaises(WorkflowError): self.service.persist_screening_session(str(self.app_id), self.candidate['_id'], dict(doc))

    def test_pending_refresh_is_deduplicated_and_manual_default_does_not_invite(self):
        self.enroll(); doc = self.completed(evaluation={'pending_answers': 1, 'score_status': 'partial'})
        self.assertEqual(self.app()['workflow']['stages'][1]['state'], 'evaluating')
        with self.assertRaises(WorkflowError): self.service.invite(self.actor, str(self.app_id), self.app()['workflow']['revision'], 'invite-premature', 'Try the next assessment.')
        self.db.interviews.update_one({'_id': doc['_id']}, {'$set': {'evaluation': {'pending_answers': 0, 'score_status': 'complete'}}})
        self.now += timedelta(days=1)  # Evaluation can finish after screening closes.
        with ThreadPoolExecutor(max_workers=2) as pool: list(pool.map(lambda _: self.service.ingest_screening(str(doc['_id'])), range(2)))
        self.assertEqual(self.app()['workflow']['stages'][1]['outcome'], 'cleared')
        self.assertIn('Screening cleared', self.app()['workflow_label'])
        self.assertEqual(self.db.screening_result_events.count_documents({}), 2)
        HiringScheduler(self.db, self.service).tick()
        self.assertEqual(self.db.assessment_invitations.count_documents({}), 0)

    def test_automatic_progression_invites_once_and_proctoring_unknown_holds(self):
        # Prepare a separate immutable active version with opted-in policy.
        self.enroll()
        self.db.hiring_workflow_versions.update_one({'_id': ObjectId(self.version_id)}, {'$set': {'stages.1.policy.auto_invite': True}})
        doc = self.completed(proctoring_score=None, proctoring_status='incomplete')
        scheduler = HiringScheduler(self.db, self.service)
        scheduler.tick(); self.assertEqual(self.db.assessment_invitations.count_documents({}), 0)
        self.db.interviews.update_one({'_id': doc['_id']}, {'$set': {'proctoring_score': 90, 'proctoring_status': 'complete'}})
        scheduler.tick(); scheduler.tick()
        self.assertEqual(self.db.assessment_invitations.count_documents({}), 1)
        self.assertEqual(self.app()['workflow']['stages'][2]['state'], 'invited')
        self.assertEqual(self.db.hiring_outbox.count_documents({'kind': 'oa_invitation'}), 1)

    def test_accepted_late_start_has_full_duration_and_survives_entry_expiry(self):
        invite = self.invitation()
        self.service.candidate_runtime_ready = True  # Test the foundation, not a shipped candidate UI.
        self.now = utc(invite['start_closes_at'])-timedelta(milliseconds=1)
        with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(lambda k: self.service.accept(self.candidate, str(invite['_id']), k), ['oa-start-A', 'oa-start-B']))
        self.assertEqual(results[0]['attempt_id'], results[1]['attempt_id'])
        deadline = utc(results[0]['deadline'])
        self.assertEqual(deadline, self.now+timedelta(minutes=5))
        self.assertGreater(deadline, utc(invite['start_closes_at']))
        self.now = utc(invite['start_closes_at'])+timedelta(seconds=1)
        self.assertFalse(self.service.expire_invitation(str(invite['_id'])))
        self.assertEqual(self.service.accept(self.candidate, str(invite['_id']), 'oa-start-replay')['deadline'], deadline.isoformat())
        wallet = self.db.credit_wallets.find_one({})
        self.assertEqual((wallet['balance'], wallet['reserved_credits']), (65, 5))
        self.assertGreaterEqual(utc(self.db.users.find_one({'_id': self.candidate['_id']})['access_expires_at']), deadline)
        import jwt
        refreshed = jwt.decode(results[0]['access_token'], options={'verify_signature': False})
        self.assertEqual(refreshed['user_id'], str(self.candidate['_id']))
        self.assertEqual(refreshed['exp'], int((deadline+timedelta(minutes=15)).timestamp()))

    def test_exact_entry_cutoff_expires_without_reservation_and_runtime_is_blocked(self):
        invite = self.invitation()
        with self.assertRaises(WorkflowError) as exc: self.service.accept(self.candidate, str(invite['_id']), 'oa-not-ready')
        self.assertEqual(exc.exception.code, 'oa_runtime_not_ready')
        self.service.candidate_runtime_ready = True
        self.now = utc(invite['start_closes_at'])
        with self.assertRaises(WorkflowError): self.service.accept(self.candidate, str(invite['_id']), 'oa-exact-cutoff')
        self.assertTrue(self.service.expire_invitation(str(invite['_id'])))
        self.assertEqual(self.db.credit_wallets.find_one({})['reserved_credits'], 0)
        self.assertIn('expired', self.app()['workflow_label'])

    def test_rescheduling_changes_only_unstarted_invitations_and_requires_manual_open(self):
        invite = self.invitation()
        self.db.hiring_workflow_versions.update_one({'_id': ObjectId(self.version_id)}, {'$set': {'configuration.schedule.oa_activation': 'manual'}})
        opening, closing = self.now+timedelta(days=2), self.now+timedelta(days=3)
        result = self.service.change_window(self.actor, self.version_id, 'reschedule-entry', 'Extend the cohort entry window.', 0, opening.isoformat(), closing.isoformat())
        self.assertEqual(result['unstarted_invitations_changed'], 1)
        result = self.service.change_window(self.actor, self.version_id, 'authorize-window', 'Authorize this OA window.', 1)
        self.assertEqual(result['window_revision'], 2)
        self.service.candidate_runtime_ready = True; self.now = opening
        attempt = self.service.accept(self.candidate, str(invite['_id']), 'rescheduled-start')
        self.service.change_window(self.actor, self.version_id, 'reschedule-protected', 'Move entry for other candidates.', 2,
            (opening+timedelta(hours=1)).isoformat(), (closing+timedelta(hours=1)).isoformat())
        self.assertEqual(utc(self.db.assessment_attempts.find_one({})['deadline']), utc(attempt['deadline']))

    def test_outbox_unknown_delivery_is_not_retried_and_disabled_flags_preserve_reads(self):
        invite = self.invitation()
        calls = []
        def sender(*args): calls.append(args); raise TimeoutError('provider response unknown')
        worker = HiringScheduler(self.db, self.service, sender)
        self.assertFalse(worker.deliver_once())
        with patch.dict(os.environ, {'GENHIRE_HIRING_EMAILS_ENABLED': 'true'}):
            self.assertTrue(worker.deliver_once())
            self.assertEqual(len(calls), 1)
            self.assertEqual(self.db.hiring_outbox.count_documents({'state': 'delivery_unknown'}), 1)
        with patch.dict(os.environ, {'GENHIRE_SCHEDULING_ENABLED': 'false'}):
            self.assertEqual(worker.tick(), {'disabled': True})
            self.assertEqual(self.service.invitation(self.candidate, str(invite['_id']))['state'], 'invited')
            with self.assertRaises(WorkflowError): self.service.invite(self.actor, str(self.app_id), self.app()['workflow']['revision'], 'disabled-new-invite', 'Invite after rollout.')

    def test_invitation_cross_owner_candidate_and_admin_http_permissions(self):
        invitation = self.invitation(); actor = [self.actor]
        def auth(fn):
            def wrapped(*args, **kwargs): return fn(actor[0], *args, **kwargs)
            wrapped.__name__ = fn.__name__; return wrapped
        with patch('middleware.auth_middleware.token_required', auth):
            from routes.hiring_progression_routes import create_hiring_progression_routes
            with patch('routes.hiring_progression_routes.token_required', auth):
                app = Flask(__name__); app.register_blueprint(create_hiring_progression_routes(self.db))
        client = app.test_client(); path = '/api/assessment-invitations/'+str(invitation['_id'])
        actor[0] = self.candidate
        response = client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('attempt_credits', response.json)
        self.assertNotIn('assessment_version_id', response.json)
        self.assertEqual(client.post('/api/jobs/'+self.job_id+'/hiring-activation-quotes', json={}).status_code, 403)
        actor[0] = dict(self.candidate, _id=ObjectId())
        self.assertEqual(client.get(path).status_code, 403)
        actor[0] = dict(self.actor, _id=ObjectId())
        self.assertEqual(client.get(path).status_code, 403)
        actor[0] = dict(_id=ObjectId(), user_type='admin', permissions=['applications.read'])
        self.assertEqual(client.get(path).status_code, 200)
        actor[0] = dict(_id=ObjectId(), user_type='admin', permissions=[])
        self.assertEqual(client.get(path).status_code, 403)
        actor[0] = self.actor
        overview = client.get('/api/jobs/'+self.job_id+'/hiring-operations')
        self.assertEqual(overview.status_code, 200)
        groups = {tuple(sorted(row['_id'].items())): row['count'] for row in overview.json['stage_counts']}
        self.assertEqual(groups[tuple(sorted(dict(type='screening', state='completed', outcome='cleared').items()))], 1)
        self.assertEqual(groups[tuple(sorted(dict(type='oa', state='invited', outcome='pending').items()))], 1)

    def test_explicit_reenrollment_preserves_decision_and_refuses_invited_work(self):
        self.enroll(); self.completed()
        old_version = self.version_id
        # A second published configuration is a new immutable hiring version.
        draft = JobSetupService(self.db).save(self.actor, self.config, {}, 'second-hiring-draft', job_id=self.job_id)
        # Reuse existing content only for this storage fixture: production checks
        # require authoring/publishing content for each exact setup version.
        new_setup = JobSetupService(self.db).attach(self.actor, draft['_id'], 1, dict(_id=ObjectId(self.job_id)), 'second-job-hash')
        blueprint = str(self.db.assessment_blueprints.find_one({'setup_version_id': new_setup['hiring_setup_version_id']})['_id'])
        q = self.db.question_versions.find_one({})
        self.authoring.save_workspace(self.actor, blueprint, [str(q['_id'])], 0, 'second-selection')
        content = self.authoring.publish(self.actor, blueprint, 1, 'second-content', True)
        quote = self.service.activation_quote(self.actor, self.job_id, content['_id'])
        activated = self.service.activate(self.actor, quote['_id'], 'second-activation', True)
        self.assertEqual(self.app()['workflow_version_id'], old_version)
        result = self.service.enroll(str(self.app_id), self.actor, 'explicit-reenroll', self.app()['workflow']['revision'])
        self.assertEqual(result['workflow_version_id'], activated['version_id'])
        self.assertEqual(self.app()['workflow']['stages'][1]['outcome'], 'cleared')
        self.assertEqual(self.db.credit_wallets.find_one({})['total_debited'], 30)
        invite = self.service.invite(self.actor, str(self.app_id), self.app()['workflow']['revision'], 'second-version-invite', 'Invite to the updated approved assessment.')
        # Third target emulates a later activated version, without mutating the
        # accepted application or the immutable prior version.
        clone = deepcopy(self.db.hiring_workflow_versions.find_one({'_id': ObjectId(activated['version_id'])}))
        clone.update(_id=ObjectId(), revision=3, operation_key='fixture-third-version')
        self.db.hiring_workflow_versions.insert_one(clone)
        self.db.jobs.update_one({'_id': ObjectId(self.job_id)}, {'$set': {'active_hiring_version_id': str(clone['_id'])}})
        with self.assertRaises(WorkflowError) as exc: self.service.enroll(str(self.app_id), self.actor, 'protected-reenroll', self.app()['workflow']['revision'])
        self.assertEqual(exc.exception.code, 'protected_invitation')
        self.assertEqual(self.db.assessment_invitations.find_one({})['_id'], ObjectId(invite['invitation_id']))

    def test_activation_and_queued_hold_release_cannot_both_consume_funding(self):
        self.billing.reserve(str(self.actor['_id']), 'recruiter', 30, 'oa-release-race', 'oa_job_setup')
        self.db.assessment_setup_funding.insert_one(dict(_id=self.job_id, key='oa-release-race', state='reserved', cycle=1, credits=30))
        quote = self.service.activation_quote(self.actor, self.job_id, self.content['_id'])
        from services.assessment_generation_service import AssessmentGenerationService
        AssessmentGenerationService(self.db).release_setup_hold(self.actor, self.blueprint_id, 'release-before-activation')
        with self.assertRaises(WorkflowError) as exc: self.service.activate(self.actor, quote['_id'], 'activation-release-race', True)
        self.assertEqual(exc.exception.code, 'generation_busy')
        self.assertEqual(self.db.billing_operations.find_one({})['state'], 'reserved')
        self.assertEqual(self.db.jobs.find_one({})['status'], 'draft')

    def test_screening_start_rolls_back_and_exact_close_expires_for_review(self):
        self.enroll(); self.now = utc(self.config['schedule']['screening_opens_at'])
        document = dict(session_id='failed-screening', application_id=str(self.app_id), user_id=str(self.candidate['_id']), status='setup')
        with patch.object(type(self.service.workflow.repo), 'write_snapshot', side_effect=RuntimeError('injected commit failure')):
            with self.assertRaises(RuntimeError): self.service.persist_screening_session(str(self.app_id), self.candidate['_id'], document)
        self.assertEqual(self.db.interviews.count_documents({}), 0)
        self.assertEqual(self.app()['workflow']['stages'][1]['state'], 'eligible')
        self.now = utc(self.config['schedule']['screening_closes_at'])
        with self.assertRaises(WorkflowError): self.service.screening_start(self.app(), str(self.candidate['_id']))
        self.service.expire_screening(str(self.app_id))
        self.assertEqual(self.app()['workflow']['stages'][1]['state'], 'expired')
        self.assertEqual(self.app()['workflow']['stages'][1]['outcome'], 'review_required')
        self.assertIn('window expired', self.app()['workflow_label'])

    def test_withdrawal_blocks_start_and_no_attempt_reservation_is_lost(self):
        invitation = self.invitation(); self.service.candidate_runtime_ready = True
        self.service.workflow.transition(str(self.app_id), self.candidate, 'withdraw', self.app()['workflow']['revision'], 'candidate-withdrawal', 'No longer pursuing this application.')
        self.now = utc(invitation['opens_at'])
        with self.assertRaises(WorkflowError): self.service.accept(self.candidate, str(invitation['_id']), 'withdrawn-start')
        self.assertEqual(self.db.assessment_attempts.count_documents({}), 0)
        self.assertEqual(self.db.credit_wallets.find_one({})['reserved_credits'], 0)

    def test_late_screening_and_manual_decision_are_not_automatically_overwritten(self):
        self.enroll(); doc = self.completed(finished_at=utc(self.config['schedule']['screening_closes_at'])+timedelta(seconds=1))
        self.assertEqual(self.app()['screening_result_reason'], 'screening_finished_late')
        self.service.workflow.transition(str(self.app_id), self.actor, 'clear', self.app()['workflow']['revision'], 'review-late-screening', 'Reviewed the late submission and approved progression.')
        self.db.interviews.update_one({'_id': doc['_id']}, {'$set': {'final_score': 20}})
        self.service.ingest_screening(str(doc['_id']))
        self.assertEqual(self.app()['workflow']['stages'][1]['outcome'], 'cleared')
        self.assertEqual(self.db.assessment_invitations.count_documents({}), 0)


if __name__ == '__main__': unittest.main()
