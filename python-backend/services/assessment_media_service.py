"""Bounded OA camera snapshots and private GCS evidence lifecycle.

This is sampled camera evidence, not a claim of continuous audiovisual recording.
No source, screen content or clipboard contents are collected.
"""
import base64
from datetime import timedelta
import os
import secrets
from bson import ObjectId
from core.mongo_transactions import atomic
from models.hiring_workflow import WorkflowError
from services.assessment_authoring_service import object_id
from services.assessment_integrity_service import digest
from services.hiring_progression_service import utc
from services.workflow_service import operation_key, request_identity


class AssessmentMediaService:
    def __init__(self, integrity, storage=None, analyzer=None):
        self.integrity, self.db, self.clock = integrity, integrity.db, integrity.clock
        self.storage, self.analyzer = storage, analyzer

    def bucket(self):
        if self.storage is not None: return self.storage
        from services.gcs_service import _get_bucket
        return _get_bucket()

    def pair(self, actor, identifier):
        self.integrity.authorize_path(actor, invitation_id=identifier)
        bound = actor.get('_oa_session')
        if not bound or bound['policy']['tier'] != 'dual' or bound['policy']['camera_waived']:
            raise WorkflowError('mobile_not_required', 'Companion capture is not required by this session.', 409)
        attempt = self.db.assessment_attempts.find_one({'invitation_id': identifier})
        if attempt and attempt['state'] != 'in_progress': raise WorkflowError('attempt_locked', 'Companion capture has ended.')
        code = secrets.token_urlsafe(32)
        self.db.assessment_mobile_sessions.insert_one(dict(_id=ObjectId(), token_hash=digest(code), security_session_id=str(bound['_id']),
            candidate_id=str(actor['_id']), invitation_id=identifier, expires_at=utc(attempt['deadline'])+timedelta(minutes=15) if attempt else self.clock()+timedelta(minutes=10), created_at=self.clock()))
        return dict(pairing_token=code, expires_at=utc(attempt['deadline'])+timedelta(minutes=15) if attempt else self.clock()+timedelta(minutes=10))

    def mobile_actor(self, token):
        phone = self.db.assessment_mobile_sessions.find_one({'token_hash': digest(token)}) if isinstance(token, str) and len(token) <= 128 else None
        if not phone or utc(phone['expires_at']) <= self.clock(): raise WorkflowError('mobile_expired', 'Companion link expired. Pair again from the assessment.', 401)
        bound = self.db.assessment_security_sessions.find_one({'_id': object_id(phone['security_session_id'])})
        user = self.db.users.find_one({'_id': object_id(phone['candidate_id'])})
        if not bound or bound['state'] == 'revoked' or not user or user.get('is_active') is False: raise WorkflowError('forbidden', 'Companion session is unavailable.', 403)
        return dict(user, _oa_session=bound, _oa_mobile=phone)

    def frame(self, actor, identifier, key, image):
        operation_key(key); self.integrity.authorize_path(actor, invitation_id=identifier)
        bound = actor.get('_oa_session'); source = 'mobile' if actor.get('_oa_mobile') else 'desktop'
        if not bound or not bound.get('consent'): raise WorkflowError('consent_required', 'Accept camera collection before sending frames.', 403)
        if bound['policy']['tier'] not in {'camera', 'dual'} or bound['policy']['camera_waived']: raise WorkflowError('camera_not_required', 'Camera collection is not enabled for this session.', 409)
        if not all(os.getenv(k, '').lower() == 'true' for k in ('GENHIRE_OA_MEDIA_ENABLED', 'GENHIRE_OA_MEDIA_ACCEPTED')):
            raise WorkflowError('media_unavailable', 'Camera evidence is unavailable.', 503)
        if not isinstance(image, str) or len(image) > 400000: raise WorkflowError('invalid_frame', 'Provide a bounded JPEG camera frame.', 400)
        try: raw = base64.b64decode(image.removeprefix('data:image/jpeg;base64,'), validate=True)
        except ValueError: raise WorkflowError('invalid_frame', 'Invalid camera encoding.', 400) from None
        if len(raw) > 250000 or not raw.startswith(b'\xff\xd8'): raise WorkflowError('invalid_frame', 'Provide a JPEG camera frame of at most 250 KB.', 400)
        attempt = self.db.assessment_attempts.find_one({'invitation_id': identifier})
        if attempt:
            if not self.integrity.runtime.participation_active(attempt): raise WorkflowError('attempt_locked', 'Participation has ended.')
        if attempt and (attempt['state'] != 'in_progress' or self.clock() >= utc(attempt['deadline'])): raise WorkflowError('attempt_locked', 'Camera collection has ended.')
        # Pre-start capture supports actual readiness, but is still consented and
        # retained for at most the short preflight cleanup window if abandoned.
        media_id = request_identity(dict(session=str(bound['_id']), key=key, source=source))[:24]
        object_path = f'oa-evidence/{bound["_id"]}/{media_id}.jpg'
        def reserve(session):
            previous = self.db.assessment_media.find_one({'_id': object_id(media_id)}, session=session)
            if previous:
                if previous['content_hash'] != request_identity(image): raise WorkflowError('idempotency_conflict', 'Frame key was reused.')
                if previous['state'] == 'stored': return False
                raise WorkflowError('frame_pending', 'Frame upload requires reconciliation; it will not be duplicated.', 409)
            current = self.db.assessment_security_sessions.find_one({'_id': bound['_id']}, session=session)
            last = current.get(source+'_frame_at')
            if last and self.clock()-utc(last) < timedelta(seconds=10): raise WorkflowError('frame_rate_limit', 'Camera sampling is limited to once per ten seconds.', 429)
            if current.get('frame_count', 0) >= 4000: raise WorkflowError('frame_limit', 'Camera evidence limit reached.', 429)
            slot = self.db.assessment_frame_slots.find_one({'lease_until': {'$gt': self.clock()}}, session=session)
            # One distributed analysis slot limits CPU/GCS concurrency; a bounded
            # lease releases capacity after worker death without spawning workers.
            if slot: raise WorkflowError('camera_capacity', 'Camera analysis is busy; retry later.', 429)
            self.db.assessment_frame_slots.update_one({'_id': 'global'}, {'$set': {'lease_until': self.clock()+timedelta(seconds=30), 'owner': media_id}}, upsert=True, session=session)
            self.db.assessment_security_sessions.update_one({'_id': bound['_id']}, {'$set': {source+'_frame_at': self.clock()}, '$inc': {'frame_count': 1}}, session=session)
            self.db.assessment_media.insert_one(dict(_id=object_id(media_id), security_session_id=str(bound['_id']), invitation_id=identifier,
                attempt_id=str(attempt['_id']) if attempt else None, source=source, object_path=object_path, state='uploading',
                content_hash=request_identity(image), created_at=self.clock(), delete_after=(utc(attempt['deadline'])+timedelta(days=bound['policy']['raw_retention_days'])) if attempt else self.clock()+timedelta(hours=1)), session=session)
            return True
        if not atomic(self.db, reserve): return dict(stored=True, replayed=True)
        try:
            if self.analyzer is None:
                from security_check import decode_frame, analyze_frame
                decoded = decode_frame(image)
                observation = analyze_frame(decoded, config=dict(object_detection=True, eyeball_tracking=True, dual_camera=bound['policy']['tier'] == 'dual'), source=source)
            else: observation = self.analyzer(image, source)
            self.bucket().blob(object_path).upload_from_string(raw, content_type='image/jpeg', if_generation_match=0, timeout=15)
            self.db.assessment_media.update_one({'_id': object_id(media_id), 'state': 'uploading'}, {'$set': {'state': 'stored',
                'analysis_available': observation.get('available') is True, 'capabilities': observation.get('capabilities', {}),
                'observations': [v['type'] for v in observation.get('violations', []) if v.get('type') in {'no_face', 'multiple_faces', 'head_turn', 'phone_detected', 'prohibited_object'}]}})
            if source == 'mobile': self.db.assessment_mobile_sessions.update_one({'_id': actor['_oa_mobile']['_id']}, {'$set': {'ready_at': self.clock()}})
            else: self.db.assessment_security_sessions.update_one({'_id': bound['_id']}, {'$set': {'camera_frame_ready_at': self.clock()}})
            return dict(stored=True, analysis_available=observation.get('available') is True, review_required=bool(observation.get('violations')))
        except Exception:
            # Upload intent/object path persists for cleanup even if outcome is
            # ambiguous. Never turn detector/storage failure into misconduct.
            self.db.assessment_media.update_one({'_id': object_id(media_id)}, {'$set': {'coverage_gap': True}})
            raise WorkflowError('camera_unavailable', 'Camera evidence is unavailable; your assessment timer continues.', 503) from None
        finally:
            self.db.assessment_frame_slots.update_one({'_id': 'global', 'owner': media_id}, {'$set': {'lease_until': self.clock()}})

    def evidence_access(self, actor, attempt_id, media_id=None, after=None):
        attempt = self.db.assessment_attempts.find_one({'_id': object_id(attempt_id)})
        if not attempt: raise WorkflowError('not_found', 'Attempt not found.', 404)
        if actor.get('user_type') not in {'recruiter', 'admin'}: raise WorkflowError('forbidden', 'Raw evidence is reviewer-only.', 403)
        self.integrity.runtime.context_access(attempt, actor)
        self.db.assessment_evidence_access.insert_one(dict(attempt_id=attempt_id, actor_id=str(actor['_id']), action='media_read', occurred_at=self.clock()))
        if media_id:
            media = self.db.assessment_media.find_one({'_id': object_id(media_id), 'attempt_id': attempt_id, 'state': 'stored'})
            if not media: raise WorkflowError('not_found', 'Evidence is unavailable or has expired.', 404)
            from services.gcs_service import generate_signed_url
            try: url = generate_signed_url(media['object_path'], expiration_minutes=5)
            except Exception: raise WorkflowError('evidence_unavailable', 'Private evidence signing is unavailable. Retry or contact the administrator.', 503) from None
            return dict(url=url, expires_in_seconds=300)
        query = {'attempt_id': attempt_id, 'state': 'stored'}
        if after: query['_id'] = {'$gt': object_id(after)}
        items = list(self.db.assessment_media.find(query).sort('_id', 1).limit(201))
        return dict(items=[dict(media_id=str(m['_id']), source=m['source'], created_at=m['created_at'], analysis_available=m.get('analysis_available'), observations=m.get('observations', [])) for m in items[:200]],
            next_cursor=str(items[199]['_id']) if len(items) > 200 else None)

    def privacy_action(self, actor, attempt_id, key, action, reason, hold_days=0):
        operation_key(key)
        if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 1000 or action not in {'request_deletion', 'purge', 'preserve'} or type(hold_days) is not int or not 0 <= hold_days <= 180:
            raise WorkflowError('invalid_privacy_action', 'Document the requested privacy action and bounded preservation period.', 400)
        fingerprint = request_identity(dict(attempt=attempt_id, action=action, reason=reason, hold_days=hold_days))
        def change(session):
            identity = dict(actor_id=str(actor['_id']), key=key)
            old = self.db.assessment_integrity_actions.find_one(identity, session=session)
            if old:
                if old['fingerprint'] != fingerprint: raise WorkflowError('idempotency_conflict', 'Privacy key reused.')
                return old['result']
            attempt = self.db.assessment_attempts.find_one({'_id': object_id(attempt_id)}, session=session)
            if not attempt: raise WorkflowError('not_found', 'Attempt not found.', 404)
            self.integrity.runtime.context_access(attempt, actor, write=action != 'request_deletion', session=session)
            if action != 'request_deletion' and attempt['state'] == 'in_progress': raise WorkflowError('attempt_active', 'Evidence disposition waits until the attempt is terminal.')
            if action == 'preserve':
                self.db.assessment_integrity_lifecycle.update_one({'_id': attempt_id}, {'$inc': {'revision': 1}}, upsert=True, session=session)
                if self.db.assessment_integrity_expirations.find_one({'_id': attempt_id}, session=session): raise WorkflowError('preservation_conflict', 'Expired evidence cannot be restored by a hold.')
                if hold_days < 1 or self.db.assessment_media.find_one({'attempt_id': attempt_id, 'state': 'deleting'}, session=session): raise WorkflowError('preservation_conflict', 'Preservation must precede deletion and have an expiry.')
                self.db.assessment_preservation_holds.update_one({'_id': attempt_id}, {'$set': dict(owner_id=str(actor['_id']), reason=reason.strip(), expires_at=self.clock()+timedelta(days=hold_days))}, upsert=True, session=session)
            if action == 'purge':
                if self.db.assessment_preservation_holds.find_one({'_id': attempt_id, 'expires_at': {'$gt': self.clock()}}, session=session): raise WorkflowError('preservation_hold', 'An active reasoned preservation hold prevents deletion.')
                self.db.assessment_media.update_many({'attempt_id': attempt_id, 'state': {'$ne': 'deleted'}}, {'$set': {'delete_after': self.clock()}}, session=session)
                self.db.assessment_integrity_summaries.update_one({'attempt_id': attempt_id}, {'$set': {'delete_after': self.clock()}}, session=session)
            result = dict(state='requested' if action == 'request_deletion' else 'scheduled', action=action)
            self.db.assessment_integrity_actions.insert_one(dict(identity, fingerprint=fingerprint, result=result, attempt_id=attempt_id, reason=reason.strip(), occurred_at=self.clock()), session=session)
            return result
        return atomic(self.db, change)

    def retention_tick(self, limit=20):
        from google.api_core.exceptions import NotFound
        cursor = self.db.assessment_integrity_cursors.find_one({'_id': 'participation'}) or {}
        query = {'state': 'in_progress', 'integrity_policy': {'$exists': True}}
        batch = list(self.db.assessment_attempts.find(dict(query, **({'_id': {'$gt': cursor['after']}} if cursor.get('after') else {}))).sort('_id', 1).limit(50))
        if not batch and cursor.get('after'): batch = list(self.db.assessment_attempts.find(query).sort('_id', 1).limit(50))
        for attempt in batch:
            if not self.integrity.runtime.participation_active(attempt):
                try: self.integrity.runtime.finalize(str(attempt['_id']), 'participation_ended', revision=attempt['revision'])
                except WorkflowError: pass
        self.db.assessment_integrity_cursors.update_one({'_id': 'participation'}, {'$set': {'after': batch[-1]['_id'] if batch else None}}, upsert=True)
        count = 0
        for media in self.db.assessment_media.find({'state': {'$in': ['stored', 'uploading', 'deleting']}, 'delete_after': {'$lte': self.clock()}}).sort('delete_after', 1).limit(limit):
            def claim(session):
                if media.get('attempt_id'): self.db.assessment_integrity_lifecycle.update_one({'_id': media['attempt_id']}, {'$inc': {'revision': 1}}, upsert=True, session=session)
                if self.db.assessment_preservation_holds.find_one({'_id': media.get('attempt_id'), 'expires_at': {'$gt': self.clock()}}, session=session): return False
                return self.db.assessment_media.update_one({'_id': media['_id'], 'delete_after': {'$lte': self.clock()}}, {'$set': {'state': 'deleting'}}, session=session).matched_count == 1
            if not atomic(self.db, claim): continue
            try: self.bucket().blob(media['object_path']).delete(timeout=15)
            except NotFound: pass
            except Exception: continue
            self.db.assessment_media.update_one({'_id': media['_id'], 'state': 'deleting'}, {'$set': {'state': 'deleted', 'deleted_at': self.clock()}, '$unset': {'object_path': '', 'observations': '', 'capabilities': ''}})
            count += 1
        for summary in self.db.assessment_integrity_summaries.find({'delete_after': {'$lte': self.clock()}}).limit(limit):
            identifier = summary['attempt_id']
            def expire(session):
                self.db.assessment_integrity_lifecycle.update_one({'_id': identifier}, {'$inc': {'revision': 1}}, upsert=True, session=session)
                if self.db.assessment_preservation_holds.find_one({'_id': identifier, 'expires_at': {'$gt': self.clock()}}, session=session): return
                self.db.assessment_integrity_events.delete_many({'attempt_id': identifier}, session=session)
                self.db.assessment_integrity_live.delete_one({'_id': identifier}, session=session)
                self.db.assessment_integrity_summaries.delete_one({'_id': summary['_id']}, session=session)
                self.db.assessment_integrity_expirations.update_one({'_id': identifier}, {'$set': {'expired_at': self.clock()}}, upsert=True, session=session)
            atomic(self.db, expire)
        for report in self.db.assessment_similarity_reports.find({'delete_after': {'$lte': self.clock()}}).limit(limit):
            def expire_similarity(session):
                self.db.assessment_integrity_lifecycle.update_one({'_id': report['_id']}, {'$inc': {'revision': 1}}, upsert=True, session=session)
                if not self.db.assessment_preservation_holds.find_one({'_id': report['_id'], 'expires_at': {'$gt': self.clock()}}, session=session):
                    self.db.assessment_similarity_reports.delete_one({'_id': report['_id'], 'delete_after': {'$lte': self.clock()}}, session=session)
            atomic(self.db, expire_similarity)
        return count
