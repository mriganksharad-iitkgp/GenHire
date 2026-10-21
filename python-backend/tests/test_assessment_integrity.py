"""Real local Mongo and explicitly fake camera/storage evidence. No native claims."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
import base64
import json
import os
import unittest
from unittest.mock import patch
from bson import ObjectId
import jwt
import test_assessment_runtime as runtime_fixture
from models.hiring_workflow import WorkflowError
from services.assessment_integrity_service import AssessmentIntegrityService, ensure_integrity_indexes
from services.assessment_media_service import AssessmentMediaService
from services.assessment_integrity_extras import AssessmentIntegrityExtras, shingles


class Bucket:
    def __init__(self): self.objects, self.fail_delete = {}, False
    def blob(self, path):
        bucket = self
        class Blob:
            def upload_from_string(self, data, **kwargs): bucket.objects[path] = data
            def delete(self, **kwargs):
                if bucket.fail_delete: raise RuntimeError('TEST_ONLY_FAKE storage unavailable')
                bucket.objects.pop(path, None)
        return Blob()


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = runtime_fixture.RuntimeTests(methodName='runTest'); self.addCleanup(self.fixture.doCleanups); self.fixture.setUp()
        self.fixture.foundation.stop()  # Step 7 tests the real readiness property.
        self.db, self.runtime, self.base = self.fixture.db, self.fixture.runtime, self.fixture.base
        self.flag = patch.dict(os.environ, dict(GENHIRE_OA_INTEGRITY_ENABLED='true', GENHIRE_OA_KIOSK_RELEASE_ID='1.3.0',
            GENHIRE_OA_MEDIA_ENABLED='true', GENHIRE_OA_MEDIA_ACCEPTED='true', GENHIRE_OA_VARIANTS_ENABLED='true', GENHIRE_OA_SIMILARITY_ENABLED='true'))
        self.flag.start(); self.addCleanup(self.flag.stop); ensure_integrity_indexes(self.db)
        self.integrity = AssessmentIntegrityService(self.runtime); self.storage = Bucket()
        self.media = AssessmentMediaService(self.integrity, storage=self.storage, analyzer=lambda image, source: dict(available=True, capabilities={'face_detection': True}, violations=[]))
        self.extras = AssessmentIntegrityExtras(self.runtime)
        self.identifier = str(self.fixture.invitation['_id']); self.candidate = self.base.candidate
        self.image = 'data:image/jpeg;base64,'+base64.b64encode(b'\xff\xd8TEST_ONLY_FAKE_JPEG').decode()

    def secure(self, mode='kiosk'):
        self.grant = self.integrity.launch(self.candidate, self.identifier, 'secure-launch-key', mode)
        self.session = self.integrity.redeem(self.identifier, self.grant['launch_code'], 'device-nonce-fixture-12345', dict(release_id='1.3.0', kiosk_active=mode == 'kiosk'))
        self.actor = self.integrity.authenticate(self.session['access_token'])
        self.integrity.preflight(self.actor, self.identifier, 'oa-integrity-v1', dict(visible=True, kiosk_active=mode == 'kiosk', camera_ready=True))
        self.actor = self.integrity.authenticate(self.session['access_token'])
        return self.actor

    def start(self):
        if not hasattr(self, 'actor'): self.secure()
        result = self.runtime.start(self.actor, self.identifier, 'secure-attempt-start', 'oa-v1')
        self.attempt_id = result['attempt_id']; return result

    def tier(self, name):
        self.db.hiring_workflow_versions.update_one({'_id': ObjectId(self.fixture.invitation['workflow_version_id'])}, {'$set': {'configuration.oa.proctoring_level': name}})

    def complete(self):
        attempt = self.db.assessment_attempts.find_one({'_id': ObjectId(self.attempt_id)})
        return self.runtime.finalize(self.attempt_id, 'candidate', self.actor, attempt['revision'])

    def test_new_starts_require_integrity_flag_and_scoped_consent_before_reservation(self):
        with patch.dict(os.environ, {'GENHIRE_OA_INTEGRITY_ENABLED': 'false'}): self.assertFalse(self.runtime.candidate_runtime_ready)
        with self.assertRaises(WorkflowError): self.runtime.start(self.candidate, self.identifier, 'unscoped-start-key', 'oa-v1')
        self.assertEqual(self.db.credit_wallets.find_one({})['reserved_credits'], 0)
        self.secure(); self.start(); self.assertEqual(self.db.credit_wallets.find_one({})['reserved_credits'], 5)

    def test_opaque_launch_nonce_binding_expiry_and_no_stored_credentials(self):
        grant = self.integrity.launch(self.candidate, self.identifier, 'secure-launch-key', 'kiosk')
        saved = json.dumps(self.db.assessment_launch_grants.find_one({}), default=str)
        self.assertNotIn(grant['launch_code'], saved); self.assertNotIn('access_token', saved)
        with self.assertRaises(WorkflowError): self.integrity.redeem(self.identifier, grant['launch_code'], 'nonce-fixture-device-1', dict(release_id='old', kiosk_active=True))
        value = self.integrity.redeem(self.identifier, grant['launch_code'], 'nonce-fixture-device-1', dict(release_id='1.3.0', kiosk_active=True))
        self.assertEqual(value['security_session_id'], self.integrity.redeem(self.identifier, grant['launch_code'], 'nonce-fixture-device-1', dict(release_id='1.3.0', kiosk_active=True))['security_session_id'])
        with self.assertRaises(WorkflowError): self.integrity.redeem(self.identifier, grant['launch_code'], 'nonce-fixture-device-2', dict(release_id='1.3.0', kiosk_active=True))
        self.base.now += timedelta(minutes=6)
        with self.assertRaises(WorkflowError): self.integrity.redeem(self.identifier, grant['launch_code'], 'nonce-fixture-device-1', dict(release_id='1.3.0', kiosk_active=True))
        # Standard account decoder rejects the audience by default.
        from core.security import get_jwt_secret
        with self.assertRaises(jwt.InvalidAudienceError): jwt.decode(value['access_token'], get_jwt_secret(), algorithms=['HS256'])

    def test_scoped_session_cannot_read_another_invitation_or_account_route(self):
        self.secure(); self.start()
        from flask import Flask
        from routes.hiring_progression_routes import create_hiring_progression_routes
        with patch('routes.hiring_progression_routes.AssessmentRuntimeService', return_value=self.runtime):
            app = Flask(__name__); app.register_blueprint(create_hiring_progression_routes(self.db))
        client = app.test_client(); headers = {'Authorization': 'OA '+self.session['access_token']}
        self.assertEqual(client.get('/api/assessment-attempts/'+self.attempt_id, headers=headers).status_code, 200)
        self.assertEqual(client.get('/api/assessment-invitations/'+str(ObjectId()), headers=headers).status_code, 403)
        self.assertEqual(client.get('/api/jobs/'+self.base.job_id+'/hiring-operations', headers=headers).status_code, 403)
        with self.assertRaises(WorkflowError): self.runtime.view(self.candidate, self.attempt_id)

    def test_resume_revokes_old_device_without_resetting_attempt_deadline(self):
        self.secure(); original = self.start(); old = self.session['access_token']
        self.secure(); resumed = self.start()
        self.assertEqual(original['attempt_id'], resumed['attempt_id']); self.assertEqual(original['deadline'], resumed['deadline'])
        with self.assertRaises(WorkflowError): self.integrity.authenticate(old)
        self.assertEqual(self.db.assessment_attempts.count_documents({}), 1)

    def test_accommodation_is_owned_revisioned_and_frozen_before_start(self):
        with self.assertRaises(WorkflowError): self.integrity.accommodate(self.candidate, self.identifier, 'bad-accommodation', 0, 'Accessible browser mode was approved.', True, True, 15)
        result = self.integrity.accommodate(self.base.actor, self.identifier, 'good-accommodation', 0, 'Accessible browser mode was approved.', True, True, 15)
        self.assertEqual(result['revision'], 1)
        self.secure('browser'); self.start()
        attempt = self.db.assessment_attempts.find_one({})
        self.assertEqual(runtime_fixture.progression.utc(attempt['deadline'])-self.base.now, timedelta(minutes=20))
        with self.assertRaises(WorkflowError): self.integrity.accommodate(self.base.actor, self.identifier, 'late-accommodation', 1, 'Another mode change after accepted start.', False, False, 0)

    def test_policy_change_invalidates_preflight_and_rolls_back_billing(self):
        self.secure()
        self.integrity.accommodate(self.base.actor, self.identifier, 'changed-accommodation', 0, 'New accessible browser mode approval.', True, True, 10)
        with self.assertRaises(WorkflowError): self.start()
        self.assertEqual(self.db.assessment_attempts.count_documents({}), 0)
        self.assertEqual(self.db.credit_wallets.find_one({})['reserved_credits'], 0)

    def test_camera_and_dual_start_require_real_server_received_frames(self):
        self.tier('dual'); self.secure()
        with self.assertRaises(WorkflowError): self.start()
        self.media.frame(self.actor, self.identifier, 'camera-preflight-frame', self.image)
        with self.assertRaises(WorkflowError): self.start()
        pairing = self.media.pair(self.actor, self.identifier)
        phone = self.media.mobile_actor(pairing['pairing_token'])
        self.media.frame(phone, self.identifier, 'mobile-preflight-frame', self.image)
        self.start()
        self.assertEqual(self.db.assessment_media.count_documents({'attempt_id': self.attempt_id}), 2)
        self.assertEqual(len(self.storage.objects), 2)

    def test_media_missing_acceptance_is_not_billable_or_a_cheating_signal(self):
        self.tier('camera')
        with patch.dict(os.environ, {'GENHIRE_OA_MEDIA_ACCEPTED': 'false'}):
            with self.assertRaises(WorkflowError): self.integrity.launch(self.candidate, self.identifier, 'camera-launch-key', 'kiosk')
        self.assertEqual(self.db.credit_wallets.find_one({})['reserved_credits'], 0)

    def test_events_deduplicate_rate_limit_reject_contents_and_leave_scores_alone(self):
        self.start()
        first = self.integrity.events(self.actor, self.attempt_id, 'integrity-observation', [{'type': 'tab_hidden'}])
        replay = self.integrity.events(self.actor, self.attempt_id, 'integrity-observation', [{'type': 'tab_hidden'}])
        self.assertEqual(first['acknowledged'], replay['acknowledged'])
        with self.assertRaises(WorkflowError): self.integrity.events(self.actor, self.attempt_id, 'new-observation-key', [{'type': 'heartbeat'}])
        with self.assertRaises(WorkflowError): self.integrity.events(self.actor, self.attempt_id, 'invalid-observation', [{'type': 'clipboard', 'contents': 'PRIVATE'}])
        self.complete(); summary = self.db.assessment_integrity_summaries.find_one({})
        self.assertEqual(summary['counts']['tab_hidden'], 1); self.assertIsNone(summary['cheating_verdict'])
        self.assertNotIn('score', summary); self.assertEqual(self.db.assessment_submissions.find_one({})['answers'], {})

    def test_extra_time_is_reasoned_idempotent_and_cannot_resurrect_submission(self):
        result = self.start(); attempt = self.db.assessment_attempts.find_one({})
        extended = self.integrity.extend(self.base.actor, self.attempt_id, 'approved-time-extension', attempt['revision'], 10, 'Verified platform disruption affected this candidate.')
        self.assertEqual(runtime_fixture.progression.utc(extended['deadline']), runtime_fixture.progression.utc(result['deadline'])+timedelta(minutes=10))
        self.assertEqual(extended, self.integrity.extend(self.base.actor, self.attempt_id, 'approved-time-extension', attempt['revision'], 10, 'Verified platform disruption affected this candidate.'))
        self.assertEqual(self.db.hiring_outbox.count_documents({'kind': 'oa_time_extended'}), 1)
        self.complete()
        with self.assertRaises(WorkflowError): self.integrity.extend(self.base.actor, self.attempt_id, 'late-time-extension', 2, 10, 'A late request must not revive submitted answers.')

    def test_review_does_not_change_objective_result_and_is_reviewer_scoped(self):
        self.start(); self.complete()
        with self.assertRaises(WorkflowError): self.integrity.review(self.candidate, self.attempt_id, 'unauthorized-review', 0, 'reviewed_clear', 'Candidate cannot review their own integrity evidence.')
        self.integrity.review(self.base.actor, self.attempt_id, 'review-evidence-key', 0, 'insufficient_evidence', 'Monitoring evidence is too sparse for a conclusion.')
        self.assertEqual(self.integrity.report(self.base.actor, self.attempt_id)['review']['decision'], 'insufficient_evidence')
        self.assertNotIn('review', self.integrity.report(self.candidate, self.attempt_id))

    def test_retention_retries_honors_holds_and_preserves_scores_history(self):
        self.tier('camera'); self.secure(); self.media.frame(self.actor, self.identifier, 'retention-camera-frame', self.image); self.start(); self.complete()
        self.media.privacy_action(self.base.actor, self.attempt_id, 'preserve-evidence-key', 'preserve', 'Preserve evidence for a reasoned ongoing review.', 60)
        self.base.now += timedelta(days=31); self.assertEqual(self.media.retention_tick(), 0); self.assertEqual(len(self.storage.objects), 1)
        self.base.now += timedelta(days=31); self.storage.fail_delete = True
        self.assertEqual(self.media.retention_tick(), 0); self.assertEqual(self.db.assessment_media.find_one({})['state'], 'deleting')
        self.storage.fail_delete = False; self.assertEqual(self.media.retention_tick(), 1)
        self.assertEqual(len(self.storage.objects), 0); self.assertEqual(self.db.assessment_attempts.count_documents({}), 1)
        self.assertEqual(self.db.assessment_submissions.count_documents({}), 1)
        self.base.now += timedelta(days=120); self.media.retention_tick()
        self.assertEqual(self.integrity.report(self.base.actor, self.attempt_id)['status'], 'expired')

    def test_candidate_deletion_request_is_not_raw_evidence_access(self):
        self.start(); self.complete()
        value = self.media.privacy_action(self.candidate, self.attempt_id, 'request-erasure-key', 'request_deletion', 'Please review erasure of my retained camera evidence.')
        self.assertEqual(value['state'], 'requested')
        with self.assertRaises(WorkflowError): self.media.evidence_access(self.candidate, self.attempt_id)
        self.assertEqual(self.media.evidence_access(self.base.actor, self.attempt_id)['items'], [])
        self.assertEqual(self.db.assessment_evidence_access.count_documents({'action': 'media_read'}), 1)

    def test_paid_reviewed_pool_is_idempotent_and_preserves_existing_invitation(self):
        from assessment_test_fixtures import mcq
        setup_id = self.base.job['hiring_setup_version_id']
        self.db.job_setup_versions.update_one({'_id': ObjectId(setup_id)}, {'$set': {'configuration.oa.variant_count': 2}})
        self.db.assessment_blueprints.update_one({'_id': ObjectId(self.base.blueprint_id)}, {'$set': {'configuration.variant_count': 2}})
        self.db.assessment_versions.update_one({'_id': ObjectId(self.base.content['_id'])}, {'$set': {'configuration.variant_count': 2}})
        q = mcq(); q['statement'] = 'Select the number divisible by two in this distinct reviewed problem.'
        saved = self.base.authoring.save_question(self.base.actor, q, 'pool-new-question')
        validation = self.base.authoring.validate(self.base.actor, saved['_id'], 'pool-new-validation')
        self.base.authoring.review(self.base.actor, saved['_id'], validation['_id'], 'approve', 'Independently verified this distinct problem.', 'pool-new-review')
        self.base.authoring.save_workspace(self.base.actor, self.base.blueprint_id, [saved['_id']], 1, 'pool-new-selection')
        version = self.base.authoring.publish(self.base.actor, self.base.blueprint_id, 2, 'pool-new-publication', True)
        versions = [self.base.content['_id'], version['_id']]
        quote = self.extras.quote(self.base.actor, 'variants', setup_id, versions)
        self.assertEqual(quote['credits'], 10)
        result = self.extras.confirm(self.base.actor, quote['quote_id'], 'pool-purchase-key', True)
        self.assertEqual(result, self.extras.confirm(self.base.actor, quote['quote_id'], 'pool-purchase-key', True))
        self.assertEqual(self.db.credit_wallets.find_one({})['total_debited'], 40)
        self.assertEqual(self.db.assessment_invitations.find_one({'_id': ObjectId(self.identifier)})['assessment_version_id'], self.base.content['_id'])
        pool = self.db.assessment_variant_pools.find_one({}); self.assertEqual(pool['version_ids'], versions)

    def test_disabled_optional_features_and_uncomparable_similarity_are_not_charged(self):
        with patch.dict(os.environ, {'GENHIRE_OA_VARIANTS_ENABLED': 'false'}):
            with self.assertRaises(WorkflowError): self.extras.quote(self.base.actor, 'variants', self.base.job['hiring_setup_version_id'], [])
        self.start(); self.complete()
        self.db.assessment_attempts.update_one({'_id': ObjectId(self.attempt_id)}, {'$set': {'state': 'completed'}})
        self.db.assessment_submissions.update_one({'attempt_id': self.attempt_id}, {'$set': {'state': 'complete'}})
        with self.assertRaises(WorkflowError): self.extras.quote(self.base.actor, 'similarity', self.attempt_id)
        self.assertEqual(self.db.credit_wallets.find_one({})['total_debited'], 30)

    def test_similarity_purchase_is_private_atomic_and_never_changes_scores(self):
        from assessment_test_fixtures import coding
        from models.assessment_content import candidate_question
        from services.workflow_service import request_identity
        self.start(); self.complete()
        qid = str(ObjectId()); question = coding()
        self.db.question_versions.insert_one(dict(_id=ObjectId(qid), question_id=qid, revision=1, content=question))
        original = self.db.assessment_attempts.find_one({'_id': ObjectId(self.attempt_id)})
        self.db.assessment_attempts.update_one({'_id': original['_id']}, {'$set': {'state': 'completed', 'questions': [dict(id=qid, **candidate_question(question))]}})
        peer = deepcopy(original); peer['_id'] = ObjectId(); peer['invitation_id'] = str(ObjectId()); peer['state'] = 'completed'
        self.db.assessment_attempts.insert_one(peer)
        answers = {qid: dict(language='python', source='def solve(values):\n    return values[0] + values[1] + values[2]')}
        self.db.assessment_submissions.update_one({'attempt_id': self.attempt_id}, {'$set': dict(state='complete', answers=answers, content_hash=request_identity(answers))})
        self.db.assessment_submissions.insert_one(dict(attempt_id=str(peer['_id']), state='complete', answers=answers, content_hash=request_identity(answers)))
        quote = self.extras.quote(self.base.actor, 'similarity', self.attempt_id)
        self.extras.confirm(self.base.actor, quote['quote_id'], 'similarity-purchase', True)
        self.extras.confirm(self.base.actor, quote['quote_id'], 'similarity-purchase-retry', True)
        report = self.extras.report(self.base.actor, self.attempt_id)
        self.assertEqual(report['pairs'][0]['overlap_percentage'], 100); self.assertTrue(report['objective_score_unchanged'])
        self.assertNotIn('return values', json.dumps(report, default=str)); self.assertEqual(self.db.credit_wallets.find_one({})['total_debited'], 40)
        with self.assertRaises(WorkflowError): self.extras.report(self.candidate, self.attempt_id)

    def test_delayed_deadline_cleanup_uses_effective_completion_for_retention(self):
        self.start(); deadline = runtime_fixture.progression.utc(self.db.assessment_attempts.find_one({})['deadline'])
        self.base.now = deadline+timedelta(days=2); self.runtime.expire_due()
        summary = self.db.assessment_integrity_summaries.find_one({})
        self.assertEqual(runtime_fixture.progression.utc(summary['completed_at']), deadline)
        self.assertEqual(runtime_fixture.progression.utc(summary['delete_after']), deadline+timedelta(days=180))

    def test_withdrawal_retains_answers_and_closes_participation_without_refund(self):
        self.start()
        self.db.applications.update_one({'_id': self.base.app_id}, {'$set': {'workflow.lifecycle': 'withdrawn'}})
        self.media.retention_tick()
        self.assertEqual(self.db.assessment_attempts.find_one({})['state'], 'submitted')
        self.assertEqual(self.db.assessment_submissions.find_one({})['reason'], 'participation_ended')
        self.assertEqual(self.db.credit_wallets.find_one({})['reserved_credits'], 5)

    def test_concurrent_launches_leave_one_authorized_session(self):
        grants = [self.integrity.launch(self.candidate, self.identifier, 'concurrent-launch-'+str(index), 'kiosk') for index in range(2)]
        def redeem(index): return self.integrity.redeem(self.identifier, grants[index]['launch_code'], 'device-nonce-number-'+str(index), dict(release_id='1.3.0', kiosk_active=True))
        with ThreadPoolExecutor(max_workers=2) as pool: sessions = list(pool.map(redeem, range(2)))
        self.assertEqual(self.db.assessment_security_sessions.count_documents({'state': {'$ne': 'revoked'}}), 1)
        active = 0
        for session in sessions:
            try: self.integrity.authenticate(session['access_token']); active += 1
            except WorkflowError: pass
        self.assertEqual(active, 1)

    def test_private_evidence_links_are_short_lived_audited_and_fail_gracefully(self):
        self.tier('camera'); self.secure(); self.media.frame(self.actor, self.identifier, 'private-evidence-frame', self.image); self.start(); self.complete()
        media_id = str(self.db.assessment_media.find_one({})['_id'])
        with patch('services.gcs_service.generate_signed_url', return_value='https://storage.example.test/private-signed') as signer:
            value = self.media.evidence_access(self.base.actor, self.attempt_id, media_id)
            self.assertEqual(value['expires_in_seconds'], 300); self.assertEqual(signer.call_args.kwargs['expiration_minutes'], 5)
        with patch('services.gcs_service.generate_signed_url', side_effect=RuntimeError('TEST_ONLY_FAKE unavailable signer')):
            with self.assertRaises(WorkflowError) as error: self.media.evidence_access(self.base.actor, self.attempt_id, media_id)
            self.assertEqual(error.exception.code, 'evidence_unavailable')
        with self.assertRaises(WorkflowError): self.media.evidence_access(dict(self.base.actor, _id=ObjectId()), self.attempt_id, media_id)


class SimilarityPrimitiveTests(unittest.TestCase):
    def test_overlap_is_deterministic_and_excludes_unchanged_starter(self):
        self.assertEqual(shingles('starter', 'starter'), set())
        self.assertEqual(shingles('return values[0] + values[1];'), shingles('return   values[0] + values[1];'))
        self.assertNotEqual(shingles('return values[0] + values[1];'), shingles('while (true) { output(42); }'))


if __name__ == '__main__': unittest.main()
