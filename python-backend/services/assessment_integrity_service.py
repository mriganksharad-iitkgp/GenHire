"""OA-only launch capabilities, durable evidence and reasoned accommodations.

Client/kiosk reports are evidence, never device attestation or a cheating verdict.
No objective marks are changed by this service.
"""
from copy import deepcopy
from datetime import timedelta
import hashlib
import os
import secrets
import jwt
from bson import ObjectId
from core.mongo_transactions import atomic
from core.security import get_jwt_secret
from models.hiring_workflow import WorkflowError
from services.assessment_authoring_service import object_id
from services.hiring_progression_service import utc
from services.workflow_service import operation_key, request_identity


def enabled(): return os.getenv('GENHIRE_OA_INTEGRITY_ENABLED', '').lower() == 'true'
def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def bounded_setting(name, default, minimum, maximum):
    try: value = int(os.getenv(name, str(default)))
    except ValueError: value = -1
    if not minimum <= value <= maximum: raise WorkflowError('invalid_integrity_configuration', 'Integrity retention configuration is invalid.', 503)
    return value


def ensure_integrity_indexes(db):
    db.assessment_launch_grants.create_index('code_hash', unique=True)
    db.assessment_launch_grants.create_index('expires_at', expireAfterSeconds=86400)
    db.assessment_security_sessions.create_index([('invitation_id', 1), ('created_at', -1)])
    db.assessment_security_sessions.create_index('expires_at', expireAfterSeconds=0)
    db.assessment_integrity_events.create_index([('attempt_id', 1), ('source', 1), ('key', 1)], unique=True)
    db.assessment_integrity_events.create_index([('attempt_id', 1), ('received_at', 1)])
    db.assessment_integrity_actions.create_index([('actor_id', 1), ('key', 1)], unique=True)
    db.assessment_media.create_index('object_path', unique=True)
    db.assessment_media.create_index([('state', 1), ('delete_after', 1)])
    db.assessment_integrity_summaries.create_index('attempt_id', unique=True)
    db.assessment_integrity_summaries.create_index('delete_after')
    db.assessment_evidence_access.create_index([('attempt_id', 1), ('occurred_at', 1)])
    db.assessment_question_exposures.create_index([('attempt_id', 1), ('question_version_id', 1)], unique=True)
    db.assessment_mobile_sessions.create_index('token_hash', unique=True)
    db.assessment_mobile_sessions.create_index('expires_at', expireAfterSeconds=0)
    db.assessment_mobile_sessions.create_index([('security_session_id', 1), ('ready_at', 1)])
    db.assessment_integrity_quotes.create_index('expires_at', expireAfterSeconds=86400)


class AssessmentIntegrityService:
    def __init__(self, runtime): self.runtime, self.db, self.clock = runtime, runtime.db, runtime.clock

    def invitation(self, actor, identifier, session=None):
        value = self.db.assessment_invitations.find_one({'_id': object_id(identifier), 'candidate_id': str(actor['_id'])}, session=session)
        if not value or actor.get('user_type') not in {'candidate', 'student'}: raise WorkflowError('not_found', 'Invitation not found.', 404)
        return value

    def policy(self, invitation, session=None):
        accepted = self.db.assessment_attempts.find_one({'invitation_id': str(invitation['_id'])}, session=session)
        if accepted and accepted.get('integrity_policy'): return deepcopy(accepted['integrity_policy'])
        version = self.db.practice_assessment_purchases.find_one({'_id': object_id(invitation['purchase_id'])}, session=session) if invitation.get('pool') == 'practice' else self.runtime.version(invitation['workflow_version_id'], session)
        accommodation = self.db.assessment_accommodations.find_one({'_id': str(invitation['_id'])}, session=session) or {}
        tier = (version['configuration'] if invitation.get('pool') == 'practice' else version['configuration']['oa'])['proctoring_level']
        return dict(version='oa-integrity-v1', consent_version='oa-integrity-v1', tier=tier,
            mode='browser' if accommodation.get('browser_allowed') else 'kiosk',
            camera_waived=accommodation.get('camera_waived', False), accommodation_revision=accommodation.get('revision', 0),
            raw_retention_days=bounded_setting('GENHIRE_OA_RAW_RETENTION_DAYS', 30, 1, 90),
            summary_retention_days=bounded_setting('GENHIRE_OA_SUMMARY_RETENTION_DAYS', 180, 30, 730),
            clipboard='external_allowed' if accommodation.get('browser_allowed') else 'internal_editor', kiosk_release_id=os.getenv('GENHIRE_OA_KIOSK_RELEASE_ID', ''),
            extra_minutes=accommodation.get('extra_minutes', 0))

    def launch(self, actor, identifier, key, mode):
        if not enabled(): raise WorkflowError('integrity_disabled', 'OA secure launch is not enabled.', 404)
        operation_key(key)
        invitation = self.invitation(actor, identifier)
        policy = self.policy(invitation)
        if mode != policy['mode']: raise WorkflowError('accommodation_required', 'Browser use requires an approved accommodation.', 403)
        if mode == 'kiosk' and not policy['kiosk_release_id']: raise WorkflowError('kiosk_release_required', 'A reviewed kiosk release must be configured.', 503)
        if policy['tier'] in {'camera', 'dual'} and not policy['camera_waived']:
            if not all(os.getenv(k, '').lower() == 'true' for k in ('GENHIRE_OA_MEDIA_ENABLED', 'GENHIRE_OA_MEDIA_ACCEPTED')):
                raise WorkflowError('media_unavailable', 'Required media capture/retention acceptance is not available.', 503)
        now = self.clock()
        if invitation['state'] not in {'invited', 'accepted'} or (invitation['state'] == 'invited' and now >= utc(invitation['start_closes_at'])):
            raise WorkflowError('oa_entry_closed', 'Invitation is not available for launch.')
        # One-time opaque launch capability; no account JWT in the deep link.
        code = secrets.token_urlsafe(32)
        self.db.assessment_launch_grants.insert_one(dict(_id=ObjectId(), invitation_id=identifier, candidate_id=str(actor['_id']),
            code_hash=digest(code), policy=policy, state='issued', expires_at=now+timedelta(minutes=5), created_at=now))
        return dict(launch_code=code, invitation_id=identifier, mode=mode, expires_at=now+timedelta(minutes=5), policy=policy)

    def token(self, session, deadline=None):
        expiry = utc(deadline)+timedelta(minutes=15) if deadline else self.clock()+timedelta(minutes=30)
        return jwt.encode(dict(user_id=session['candidate_id'], aud='genhire-oa', purpose='oa_session',
            invitation_id=session['invitation_id'], security_session_id=str(session['_id']), exp=expiry), get_jwt_secret(), algorithm='HS256')

    def redeem(self, identifier, code, nonce, runtime_info):
        if not isinstance(code, str) or not 30 <= len(code) <= 128 or not isinstance(nonce, str) or not 16 <= len(nonce) <= 128:
            raise WorkflowError('invalid_launch', 'Provide a valid launch capability and device nonce.', 400)
        if not isinstance(runtime_info, dict) or set(runtime_info)-{'release_id', 'kiosk_active'}: raise WorkflowError('invalid_launch', 'Unsupported runtime information.', 400)
        def redeem(session):
            grant = self.db.assessment_launch_grants.find_one({'code_hash': digest(code), 'invitation_id': identifier}, session=session)
            if not grant or utc(grant['expires_at']) <= self.clock(): raise WorkflowError('launch_expired', 'Launch expired. Open the OA from your dashboard again.', 401)
            old = self.db.assessment_security_sessions.find_one({'_id': object_id(grant['session_id'])}, session=session) if grant.get('session_id') else None
            if old:
                if old['nonce_hash'] != digest(nonce): raise WorkflowError('launch_used', 'Launch is already bound to another session.', 409)
                return old
            self.db.assessment_security_controls.update_one({'_id': identifier}, {'$inc': {'revision': 1}}, upsert=True, session=session)
            policy = grant['policy']
            if policy['mode'] == 'kiosk' and (runtime_info.get('release_id') != policy['kiosk_release_id'] or runtime_info.get('kiosk_active') is not True):
                raise WorkflowError('kiosk_release_required', 'Open the required secure-browser release in assessment mode.', 403)
            value = dict(_id=ObjectId(), invitation_id=identifier, candidate_id=grant['candidate_id'], policy=policy,
                nonce_hash=digest(nonce), created_at=self.clock(), expires_at=self.clock()+timedelta(minutes=30), state='preflight', consent=False, ready=False)
            self.db.assessment_security_sessions.update_many({'invitation_id': identifier, 'state': {'$ne': 'revoked'}}, {'$set': {'state': 'revoked'}}, session=session)
            self.db.assessment_security_sessions.insert_one(value, session=session)
            self.db.assessment_launch_grants.update_one({'_id': grant['_id']}, {'$set': {'state': 'redeemed', 'session_id': str(value['_id'])}}, session=session)
            return value
        value = atomic(self.db, redeem)
        return dict(access_token=self.token(value), security_session_id=str(value['_id']), invitation_id=identifier, policy=value['policy'])

    def authenticate(self, bearer):
        try: claims = jwt.decode(bearer.removeprefix('Bearer '), get_jwt_secret(), algorithms=['HS256'], audience='genhire-oa')
        except (jwt.InvalidTokenError, AttributeError): raise WorkflowError('invalid_oa_session', 'OA session expired or invalid. Reopen from the dashboard.', 401) from None
        session = self.db.assessment_security_sessions.find_one({'_id': object_id(claims.get('security_session_id'))})
        user = self.db.users.find_one({'_id': object_id(claims.get('user_id'))})
        if claims.get('purpose') != 'oa_session' or not user or user.get('is_active') is False or not session or session['state'] == 'revoked' or utc(session['expires_at']) <= self.clock() or session['candidate_id'] != str(user['_id']) or session['invitation_id'] != claims.get('invitation_id'):
            raise WorkflowError('invalid_oa_session', 'OA session is not authorized.', 401)
        # This capability is accepted only by the OA route wrapper; account APIs
        # reject its audience. It cannot change jobs, profiles or other attempts.
        return dict(user, _oa_session=session)

    def authorize_path(self, actor, invitation_id=None, attempt_id=None):
        session = actor.get('_oa_session')
        if not session: return
        if attempt_id:
            attempt = self.db.assessment_attempts.find_one({'_id': object_id(attempt_id)})
            if not attempt or attempt['invitation_id'] != session['invitation_id']: raise WorkflowError('forbidden', 'OA session is scoped to its own invitation.', 403)
        if invitation_id and invitation_id != session['invitation_id']: raise WorkflowError('forbidden', 'OA session is scoped to its own invitation.', 403)

    def preflight(self, actor, identifier, consent, readiness):
        self.authorize_path(actor, invitation_id=identifier)
        bound = actor.get('_oa_session')
        if not bound: raise WorkflowError('secure_session_required', 'Open the secure assessment session first.', 403)
        if consent != 'oa-integrity-v1' or not isinstance(readiness, dict) or set(readiness)-{'camera_ready', 'microphone_ready', 'visible', 'kiosk_active'}:
            raise WorkflowError('consent_required', 'Accept the disclosed assessment and retention policy.', 400)
        policy = bound['policy']
        if readiness.get('visible') is not True or (policy['mode'] == 'kiosk' and readiness.get('kiosk_active') is not True):
            raise WorkflowError('preflight_required', 'The assessment must be visible in its required runtime.', 409)
        if policy['tier'] in {'camera', 'dual'} and not policy['camera_waived'] and not readiness.get('camera_ready'):
            raise WorkflowError('camera_required', 'Required camera is not ready; request an accommodation if needed.', 409)
        attempt = self.db.assessment_attempts.find_one({'invitation_id': identifier})
        expiry = utc(attempt['deadline'])+timedelta(minutes=15) if attempt else self.clock()+timedelta(minutes=30)
        self.db.assessment_security_sessions.update_one({'_id': bound['_id']}, {'$set': dict(consent=True, ready=True, preflight_at=self.clock(), readiness=readiness, expires_at=expiry)})
        return dict(ready=True, policy=policy)

    def prepare(self, attempt, invitation, actor, session):
        if not enabled(): return
        bound = actor.get('_oa_session') if actor else None
        current = self.db.assessment_security_sessions.find_one({'_id': bound['_id']}, session=session) if bound else None
        if not current or current['state'] == 'revoked' or current['candidate_id'] != attempt['candidate_id'] or current['invitation_id'] != str(invitation['_id']) or not current.get('ready') or not current.get('consent') or self.clock()-utc(current['preflight_at']) > timedelta(minutes=2):
            raise WorkflowError('secure_preflight_required', 'Complete secure OA preflight immediately before starting.', 403)
        if self.policy(invitation, session) != current['policy']: raise WorkflowError('policy_changed', 'Accommodation/policy changed; reopen preflight.', 409)
        policy = current['policy']
        if policy['tier'] in {'camera', 'dual'} and not policy['camera_waived'] and (not current.get('camera_frame_ready_at') or self.clock()-utc(current['camera_frame_ready_at']) > timedelta(seconds=20)):
            raise WorkflowError('camera_frame_required', 'A recent server-received camera frame is required before start.', 409)
        if policy['tier'] == 'dual' and not policy['camera_waived']:
            phone = self.db.assessment_mobile_sessions.find_one({'security_session_id': str(current['_id']), 'ready_at': {'$gte': self.clock()-timedelta(seconds=20)}}, session=session)
            if not phone: raise WorkflowError('mobile_required', 'A recent companion camera frame is required before start.', 409)
        extra = policy['extra_minutes']
        if extra:
            attempt['deadline'] += timedelta(minutes=extra)
            # Allocate extra section time proportionally, keeping exact total.
            sections = attempt['sections']; original = sum((utc(s['closes_at'])-utc(s['opens_at'])).total_seconds() for s in sections)
            if attempt['configuration']['timer_mode'] == 'section':
                opening, remaining = attempt['started_at'], extra*60
                for index, section in enumerate(sections):
                    duration = (utc(section['closes_at'])-utc(section['opens_at'])).total_seconds()
                    added = remaining if index == len(sections)-1 else int(extra*60*duration/original)
                    remaining -= added; section.update(opens_at=opening, closes_at=opening+timedelta(seconds=duration+added)); opening = section['closes_at']
            else:
                for section in sections: section['closes_at'] = attempt['deadline']
        attempt.update(integrity_policy=deepcopy(policy), security_session_id=str(current['_id']))
        attempt['integrity_consent'] = dict(version=policy['consent_version'], accepted_at=current['preflight_at'], policy_hash=request_identity(policy))
        self.db.assessment_security_sessions.update_one({'_id': current['_id']}, {'$set': {'state': 'active', 'attempt_id': str(attempt['_id']), 'deadline': attempt['deadline'], 'expires_at': attempt['deadline']+timedelta(minutes=15)}}, session=session)
        self.db.assessment_mobile_sessions.update_many({'security_session_id': str(current['_id'])}, {'$set': {'expires_at': attempt['deadline']+timedelta(minutes=15)}}, session=session)
        self.db.assessment_media.update_many({'security_session_id': str(current['_id']), 'attempt_id': None}, {'$set': {'attempt_id': str(attempt['_id']),
            'delete_after': attempt['deadline']+timedelta(days=policy['raw_retention_days'])}}, session=session)
        # Per-attempt server shuffle; order persists and never changes answer IDs.
        rng = secrets.SystemRandom()
        for section in attempt['sections']:
            rng.shuffle(section['question_ids'])
        order = [qid for s in attempt['sections'] for qid in s['question_ids']]
        attempt['questions'].sort(key=lambda q: order.index(q['id']))
        for question in attempt['questions']:
            if question['type'] == 'mcq': rng.shuffle(question['mcq']['options'])
            self.db.assessment_question_exposures.insert_one(dict(attempt_id=str(attempt['_id']), question_version_id=question['id'],
                assessment_version_id=attempt['assessment_version_id'], pool=attempt.get('pool', 'recruitment'), exposed_at=self.clock()), session=session)

    def events(self, actor, attempt_id, key, observations, source='desktop'):
        operation_key(key); self.authorize_path(actor, attempt_id=attempt_id)
        allowed = {'heartbeat', 'tab_hidden', 'window_blur', 'fullscreen_exit', 'external_paste_blocked', 'camera_gap', 'camera_ready', 'runtime_gap', 'display_count'}
        if not isinstance(observations, list) or not 1 <= len(observations) <= 20 or any(not isinstance(v, dict) or set(v)-{'type', 'value'} or v.get('type') not in allowed or ('value' in v and (type(v['value']) not in (bool, int) or abs(int(v['value'])) > 16)) for v in observations):
            raise WorkflowError('invalid_observation', 'Provide bounded integrity observations without source/clipboard content.', 400)
        fingerprint = request_identity(observations)
        def record(session):
            attempt = self.runtime.owned(actor, attempt_id, session)
            if attempt['state'] != 'in_progress' or self.clock() >= utc(attempt['deadline']): raise WorkflowError('attempt_locked', 'Integrity collection has ended.')
            if actor.get('_oa_session') and actor['_oa_session']['invitation_id'] != attempt['invitation_id']: raise WorkflowError('forbidden', 'Wrong OA session.', 403)
            old = self.db.assessment_integrity_events.find_one(dict(attempt_id=attempt_id, source=source, key=key), session=session)
            if old:
                if old['fingerprint'] != fingerprint: raise WorkflowError('idempotency_conflict', 'Observation key reused.')
                return dict(acknowledged=True, received_at=old['received_at'])
            summary = self.db.assessment_integrity_live.find_one({'_id': attempt_id}, session=session) or {}
            if summary.get('last_event_at') and self.clock()-utc(summary['last_event_at']) < timedelta(seconds=2): raise WorkflowError('observation_rate_limit', 'Retry observations later.', 429)
            if summary.get('event_count', 0) >= 3000: raise WorkflowError('observation_limit', 'Integrity event limit reached.', 429)
            self.db.assessment_integrity_events.insert_one(dict(attempt_id=attempt_id, source=source, key=key, fingerprint=fingerprint, observations=observations, received_at=self.clock()), session=session)
            counts = {'event_count': 1}
            for value in observations:
                if value['type'] != 'heartbeat': counts['counts.'+value['type']] = counts.get('counts.'+value['type'], 0)+1
            self.db.assessment_integrity_live.update_one({'_id': attempt_id}, {'$inc': counts, '$set': {'last_event_at': self.clock()}}, upsert=True, session=session)
            return dict(acknowledged=True, received_at=self.clock())
        return atomic(self.db, record)

    def accommodate(self, actor, identifier, key, revision, reason, browser_allowed, camera_waived, extra_minutes):
        operation_key(key)
        if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 1000 or type(revision) is not int or type(browser_allowed) is not bool or type(camera_waived) is not bool or type(extra_minutes) is not int or not 0 <= extra_minutes <= 180:
            raise WorkflowError('invalid_accommodation', 'Provide a reason, current revision, explicit modes and 0–180 extra minutes.', 400)
        fingerprint = request_identity(dict(invitation=identifier, revision=revision, reason=reason, browser=browser_allowed, camera=camera_waived, minutes=extra_minutes))
        def change(session):
            identity = dict(actor_id=str(actor['_id']), key=key)
            old = self.db.assessment_integrity_actions.find_one(identity, session=session)
            if old:
                if old['fingerprint'] != fingerprint: raise WorkflowError('idempotency_conflict', 'Accommodation key reused.')
                return old['result']
            invitation = self.db.assessment_invitations.find_one({'_id': object_id(identifier)}, session=session)
            if not invitation: raise WorkflowError('not_found', 'Invitation not found.', 404)
            self.runtime.context_access(invitation, actor, True, session)
            if invitation['state'] != 'invited' or self.db.assessment_attempts.find_one({'invitation_id': identifier}, session=session):
                raise WorkflowError('attempt_started', 'Mode/camera accommodations must be approved before start. Accepted deadlines never reset.')
            previous = self.db.assessment_accommodations.find_one({'_id': identifier}, session=session) or {}
            if previous.get('revision', 0) != revision: raise WorkflowError('stale_revision', 'Accommodation changed; reload.')
            result = dict(revision=revision+1, browser_allowed=browser_allowed, camera_waived=camera_waived, extra_minutes=extra_minutes)
            self.db.assessment_accommodations.update_one({'_id': identifier}, {'$set': result}, upsert=True, session=session)
            self.db.assessment_invitations.update_one({'_id': invitation['_id'], 'state': 'invited'}, {'$inc': {'revision': 1}}, session=session)
            self.db.assessment_integrity_actions.insert_one(dict(identity, fingerprint=fingerprint, result=result, reason=reason.strip(), invitation_id=identifier, occurred_at=self.clock()), session=session)
            return result
        return atomic(self.db, change)

    def summarize(self, attempt, session=None):
        identifier = str(attempt['_id']); live = self.db.assessment_integrity_live.find_one({'_id': identifier}, session=session) or {}
        # Coverage and review flags are honest; browser claims do not prove OS
        # lockdown. No numerical proctoring or misconduct score is invented.
        policy = attempt.get('integrity_policy', {})
        completed_at = utc(attempt['submitted_at']) if attempt.get('submitted_at') else min(self.clock(), utc(attempt['deadline']))
        frames = self.db.assessment_media.count_documents({'attempt_id': identifier, 'state': 'stored'}, session=session)
        analyzed = self.db.assessment_media.count_documents({'attempt_id': identifier, 'state': 'stored', 'analysis_available': True}, session=session)
        flagged = self.db.assessment_media.count_documents({'attempt_id': identifier, 'state': 'stored', 'observations.0': {'$exists': True}}, session=session)
        return dict(attempt_id=identifier, status='review_required' if live.get('counts') or flagged else 'coverage_unknown', counts=live.get('counts', {}),
            evidence_type='client_reported_events', objective_score_unchanged=True, cheating_verdict=None,
            camera_evidence=dict(stored_samples=frames, analyzed_samples=analyzed, samples_with_review_signals=flagged, coverage='sampled_partial' if frames else 'unknown'),
            raw_retention_days=policy.get('raw_retention_days', 30), delete_after=completed_at+timedelta(days=policy.get('summary_retention_days', 180)), completed_at=completed_at)

    def extend(self, actor, attempt_id, key, revision, minutes, reason):
        operation_key(key)
        if type(revision) is not int or type(minutes) is not int or not 1 <= minutes <= 180 or not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 1000:
            raise WorkflowError('invalid_extension', 'Provide the current answer revision, 1–180 minutes and a verified reason.', 400)
        fingerprint = request_identity(dict(attempt=attempt_id, revision=revision, minutes=minutes, reason=reason))
        def change(session):
            identity = dict(actor_id=str(actor['_id']), key=key)
            old = self.db.assessment_integrity_actions.find_one(identity, session=session)
            if old:
                if old['fingerprint'] != fingerprint: raise WorkflowError('idempotency_conflict', 'Extension key reused.')
                return old['result']
            attempt = self.db.assessment_attempts.find_one({'_id': object_id(attempt_id)}, session=session)
            if not attempt: raise WorkflowError('not_found', 'Attempt not found.', 404)
            self.runtime.context_access(attempt, actor, True, session)
            if attempt['state'] != 'in_progress' or self.clock() >= utc(attempt['deadline']) or not self.runtime.participation_active(attempt, session):
                raise WorkflowError('attempt_locked', 'Extensions cannot resurrect a closed/submitted attempt.')
            if attempt['revision'] != revision: raise WorkflowError('stale_revision', 'Answers changed; reload the attempt revision.')
            extra = attempt.get('approved_extension_minutes', 0)+minutes
            if extra+attempt.get('integrity_policy', {}).get('extra_minutes', 0) > 180: raise WorkflowError('extension_limit', 'Total approved extra time is limited to 180 minutes.')
            delta = timedelta(minutes=minutes); deadline = utc(attempt['deadline'])+delta; sections = deepcopy(attempt['sections'])
            for section in sections:
                if attempt['configuration']['timer_mode'] == 'shared': section['closes_at'] = deadline
                elif utc(section['closes_at']) > self.clock():
                    if utc(section['opens_at']) > self.clock(): section['opens_at'] = utc(section['opens_at'])+delta
                    section['closes_at'] = utc(section['closes_at'])+delta
            self.db.assessment_attempts.update_one({'_id': attempt['_id'], 'revision': revision}, {'$set': dict(deadline=deadline, sections=sections, approved_extension_minutes=extra), '$inc': {'revision': 1}}, session=session)
            self.db.assessment_invitations.update_one({'_id': object_id(attempt['invitation_id'])}, {'$set': {'attempt_deadline': deadline}}, session=session)
            self.db.assessment_security_sessions.update_many({'invitation_id': attempt['invitation_id']}, {'$set': {'deadline': deadline, 'expires_at': deadline+timedelta(minutes=15)}}, session=session)
            self.db.assessment_mobile_sessions.update_many({'invitation_id': attempt['invitation_id']}, {'$set': {'expires_at': deadline+timedelta(minutes=15)}}, session=session)
            self.runtime.extend_access(attempt['candidate_id'], deadline+timedelta(days=1), session)
            if attempt.get('pool') != 'practice':
                app = self.runtime.workflow.repo.application(attempt['application_id'], session)
                self.runtime.write(app, deepcopy(app['workflow']), 'oa_time_extended', 'oa-extension:'+key, reason.strip(), session, str(actor['_id']))
                self.runtime.outbox(app, 'oa_time_extended', 'oa-extension:'+key, self.clock(), session)
            result = dict(deadline=deadline.isoformat(timespec='milliseconds'), revision=revision+1, added_minutes=minutes)
            self.db.assessment_integrity_actions.insert_one(dict(identity, attempt_id=attempt_id, fingerprint=fingerprint, result=result, reason=reason.strip(), occurred_at=self.clock()), session=session)
            return result
        return atomic(self.db, change)

    def review(self, actor, attempt_id, key, revision, decision, reason):
        operation_key(key)
        if decision not in {'reviewed_clear', 'needs_followup', 'insufficient_evidence'} or type(revision) is not int or not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 1000:
            raise WorkflowError('invalid_review', 'Provide a reasoned integrity review decision and current revision.', 400)
        def change(session):
            identity = dict(actor_id=str(actor['_id']), key=key)
            fingerprint = request_identity(dict(attempt=attempt_id, revision=revision, decision=decision, reason=reason))
            old = self.db.assessment_integrity_actions.find_one(identity, session=session)
            if old:
                if old['fingerprint'] != fingerprint: raise WorkflowError('idempotency_conflict', 'Review key reused.')
                return old['result']
            attempt = self.db.assessment_attempts.find_one({'_id': object_id(attempt_id)}, session=session)
            if not attempt: raise WorkflowError('not_found', 'Attempt not found.', 404)
            self.runtime.context_access(attempt, actor, True, session)
            summary = self.db.assessment_integrity_summaries.find_one({'attempt_id': attempt_id}, session=session)
            if not summary or summary.get('review_revision', 0) != revision: raise WorkflowError('review_unavailable', 'Integrity summary is unavailable or changed.')
            result = dict(decision=decision, revision=revision+1, objective_score_unchanged=True)
            self.db.assessment_integrity_summaries.update_one({'_id': summary['_id']}, {'$set': {'review': dict(result, reason=reason.strip(), reviewer_id=str(actor['_id']), reviewed_at=self.clock()), 'review_revision': revision+1}}, session=session)
            self.db.assessment_integrity_actions.insert_one(dict(identity, fingerprint=fingerprint, result=result, reason=reason.strip(), occurred_at=self.clock()), session=session)
            return result
        return atomic(self.db, change)

    def report(self, actor, attempt_id):
        attempt = self.db.assessment_attempts.find_one({'_id': object_id(attempt_id)})
        if not attempt: raise WorkflowError('not_found', 'Attempt not found.', 404)
        self.runtime.context_access(attempt, actor)
        if actor.get('user_type') in {'candidate', 'student'}: return dict(attempt_id=attempt_id, status='recorded_for_review', objective_score_unchanged=True)
        self.db.assessment_evidence_access.insert_one(dict(attempt_id=attempt_id, actor_id=str(actor['_id']), action='integrity_summary_read', occurred_at=self.clock()))
        summary = self.db.assessment_integrity_summaries.find_one({'attempt_id': attempt_id})
        if self.db.assessment_integrity_expirations.find_one({'_id': attempt_id}): return dict(attempt_id=attempt_id, status='expired', objective_score_unchanged=True)
        return dict({k: v for k, v in (summary or self.summarize(attempt)).items() if k != '_id'}, attempt_revision=attempt['revision'], deadline=attempt['deadline'])
