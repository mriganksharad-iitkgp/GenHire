"""Authoritative workflow mutations, independent of interview/media runtime."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from config.workflow import workflow_enabled, managed
from core.mongo_transactions import atomic
from models.hiring_workflow import WorkflowError, validate_stages, legacy_snapshot, projection, ATTEMPT_POLICY
from repositories.workflow_repository import WorkflowRepository


def request_identity(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def operation_key(value):
    if not isinstance(value, str) or not 8 <= len(value) <= 128:
        raise WorkflowError('invalid_operation_key', 'Provide an 8–128 character operation key.', 400)
    return value


def public_workflow(application):
    if not managed(application):
        return None
    workflow = application['workflow']
    return dict(workflow_version_id=application['workflow_version_id'], revision=workflow['revision'],
                lifecycle=workflow['lifecycle'], current_stage_id=workflow['current_stage_id'],
                stages=deepcopy(workflow['stages']), **projection(workflow))


class WorkflowService:
    def __init__(self, db):
        self.db, self.repo = db, WorkflowRepository(db)

    @staticmethod
    def require_enabled():
        if not workflow_enabled():
            raise WorkflowError('workflow_disabled', 'Dynamic workflow rollout is disabled.', 404)

    def job(self, job_id, actor, write=False, session=None):
        try:
            job = self.db.jobs.find_one({'_id': ObjectId(job_id)}, session=session)
        except Exception as exc:
            if not ObjectId.is_valid(job_id):
                raise WorkflowError('invalid_id', 'Invalid job ID.', 400) from exc
            raise
        if not job:
            raise WorkflowError('not_found', 'Job not found.', 404)
        role, permissions = actor.get('user_type'), actor.get('permissions', [])
        admin = role == 'admin' and ('*' in permissions or ('applications.write' if write else 'applications.read') in permissions)
        owner = role == 'recruiter' and str(job.get('created_by')) == str(actor.get('_id'))
        if not (admin or owner):
            raise WorkflowError('forbidden', 'You do not have access to this job.', 403)
        if write and owner and actor.get('is_verified') is not True:
            raise WorkflowError('verification_required', 'Recruiter verification is required.', 403)
        return job

    def access(self, application, actor, write=False, session=None):
        if not write and actor.get('user_type') in {'candidate', 'student'}:
            if str(application.get('student_id')) == str(actor.get('_id')):
                return
            raise WorkflowError('forbidden', 'You do not have access to this application.', 403)
        self.job(application['job_id'], actor, write=write, session=session)

    def publish_version(self, job_id, actor, stages, expected_revision, key):
        self.require_enabled()
        stages, key = validate_stages(stages), operation_key(key)
        if type(expected_revision) is not int or expected_revision < 0:
            raise WorkflowError('invalid_revision', 'A nonnegative expected_revision is required.', 400)
        fingerprint = request_identity(dict(stages=stages, revision=expected_revision))
        version_id = ObjectId()
        def publish(session):
            job = self.job(job_id, actor, write=True, session=session)
            if job.get('active_hiring_version_id'):
                raise WorkflowError('use_hiring_activation', 'Activated jobs require a reviewed hiring setup activation.')
            old = self.db.hiring_workflow_versions.find_one(dict(job_id=str(job['_id']), operation_key=key), session=session)
            if old:
                if old['request_hash'] != fingerprint:
                    raise WorkflowError('idempotency_conflict', 'Operation key reused with different content.')
                return {'version_id': str(old['_id']), 'revision': old['revision'], 'replayed': True}
            if job.get('workflow_revision', 0) != expected_revision:
                raise WorkflowError('stale_revision', 'Job workflow changed; refresh before retrying.')
            version = dict(_id=version_id, schema_version=1, job_id=str(job['_id']), owner_id=str(job['created_by']),
                revision=expected_revision + 1, stages=stages, attempt_policy=deepcopy(ATTEMPT_POLICY), operation_key=key, request_hash=fingerprint,
                created_by=str(actor['_id']), created_at=datetime.now(timezone.utc))
            self.db.hiring_workflow_versions.insert_one(version, session=session)
            self.db.jobs.update_one({'_id': job['_id']}, {'$set': {'workflow_version_id': str(version_id),
                'workflow_revision': version['revision']}}, session=session)
            # Existing applications retain their version; no bulk mutation/invitation.
            return {'version_id': str(version_id), 'revision': version['revision'], 'replayed': False}
        try:
            return atomic(self.db, publish)
        except DuplicateKeyError:
            return atomic(self.db, publish)

    def adoption_preview(self, application, version):
        """Pure/read-only classification; apply rechecks all conditions in a transaction."""
        if managed(application):
            return None, 'already_managed'
        if application.get('processing_status') not in {None, 'completed'}:
            return None, 'processing_not_complete'
        if application.get('interview_start_lease'):
            return None, 'interview_start_lease_present'
        active = self.db.interviews.find_one({'application_id': str(application['_id']),
            'status': {'$in': ['setup', 'active', 'finishing', 'identity_blocked']}})
        if active:
            return None, 'active_interview'
        completed = self.db.interviews.find_one({'application_id': str(application['_id']), 'status': 'completed'}, sort=[('_id', -1)])
        if completed:
            if (completed.get('evaluation') or {}).get('pending_answers'):
                return None, 'screening_evaluation_pending'
            if application.get('interview_score') is None or application.get('status') not in {'interviewed', 'screening_cleared', 'selected', 'rejected'}:
                return None, 'screening_result_not_synchronized'
            report_score = completed.get('interview_score', completed.get('final_score'))
            if report_score is not None and report_score != application.get('interview_score'):
                return None, 'screening_result_not_synchronized'
        if self.db.interviews.find_one({'application_id': str(application['_id']), 'status': 'terminated'}):
            return None, 'terminated_attempt_requires_review'
        try:
            return legacy_snapshot(application, version['stages']), None
        except WorkflowError as exc:
            return None, exc.code

    def adopt(self, application_id, actor, version_id, key):
        self.require_enabled()
        key = operation_key(key)
        def adopt(session):
            app = self.repo.application(application_id, session)
            self.access(app, actor, write=True, session=session)
            old = self.db.stage_events.find_one(dict(application_id=str(app['_id']), operation_key=key), session=session)
            if old:
                if old.get('action') != 'import' or old.get('workflow_version_id') != version_id:
                    raise WorkflowError('idempotency_conflict', 'Operation key reused.')
                return old['result']
            if managed(app):
                raise WorkflowError('already_managed', 'Application already has a workflow snapshot.')
            version = self.db.hiring_workflow_versions.find_one({'_id': ObjectId(version_id), 'job_id': app['job_id']}, session=session)
            if not version:
                raise WorkflowError('invalid_version', 'Workflow version does not belong to this job.', 400)
            workflow, problem = self.adoption_preview(app, version)
            if problem:
                raise WorkflowError('unsafe_adoption', f'Application cannot be adopted: {problem}.')
            # Persisted lease/start writers touch this same application document,
            # so concurrent adoption/start conflicts are retried and revalidated.
            result = dict(workflow_version_id=version_id, **workflow, **projection(workflow))
            event = dict(application_id=str(app['_id']), job_id=app['job_id'], revision=0,
                workflow_version_id=version_id, operation_key=key, action='import', actor_id=str(actor['_id']),
                reason='Imported legacy snapshot; historical transition times unknown.',
                occurred_at=datetime.now(timezone.utc), result=result)
            self.repo.write_snapshot(app, workflow, dict(workflow_version_id=version_id,
                workflow_label=result['workflow_label']), event, session)
            return result
        try:
            return atomic(self.db, adopt)
        except DuplicateKeyError:
            return atomic(self.db, adopt)

    def transition(self, application_id, actor, action, expected_revision, key, reason):
        self.require_enabled()
        key = operation_key(key)
        if type(expected_revision) is not int or expected_revision < 0:
            raise WorkflowError('invalid_revision', 'A nonnegative expected_revision is required.', 400)
        if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 1000:
            raise WorkflowError('reason_required', 'Provide a reason of 3–1000 characters.', 400)
        if action not in {'clear', 'not_clear', 'review', 'advance', 'withdraw', 'reject', 'hire', 'close'}:
            raise WorkflowError('invalid_action', 'Unsupported workflow action.', 400)
        fingerprint = request_identity(dict(action=action, revision=expected_revision, reason=reason))
        def change(session):
            app = self.repo.application(application_id, session)
            candidate_withdrawal = action == 'withdraw' and actor.get('user_type') in {'candidate', 'student'}
            self.access(app, actor, write=not candidate_withdrawal, session=session)
            if not managed(app):
                raise WorkflowError('not_managed', 'Application has not been adopted into a workflow.')
            previous = self.db.stage_events.find_one(dict(application_id=str(app['_id']), operation_key=key), session=session)
            if previous:
                if previous.get('request_hash') != fingerprint or previous.get('actor_id') != str(actor['_id']):
                    raise WorkflowError('idempotency_conflict', 'Operation key reused with different action/actor.')
                return previous['result']
            workflow = deepcopy(app['workflow'])
            if workflow['revision'] != expected_revision:
                raise WorkflowError('stale_revision', 'Application changed; refresh before retrying.')
            if workflow['lifecycle'] != 'active':
                raise WorkflowError('terminal_application', 'Application is no longer active.')
            stage = next(s for s in workflow['stages'] if s['stage_id'] == workflow['current_stage_id'])
            before = deepcopy(stage)
            if action in {'withdraw', 'reject', 'hire', 'close'}:
                if action == 'hire' and (stage['type'] != 'company' or stage['outcome'] != 'cleared'):
                    raise WorkflowError('illegal_transition', 'Hiring requires a cleared company-managed stage.')
                workflow['lifecycle'] = {'withdraw': 'withdrawn', 'reject': 'rejected', 'hire': 'hired', 'close': 'closed'}[action]
            elif action == 'advance':
                if stage['type'] == 'oa':
                    raise WorkflowError('use_company_action', 'OA advancement requires the reviewed company decision endpoint.')
                if stage['state'] != 'completed' or stage['outcome'] != 'cleared':
                    raise WorkflowError('illegal_transition', 'Only a completed cleared stage can advance.')
                following = [s for s in workflow['stages'][workflow['stages'].index(stage)+1:] if s['enabled']]
                if not following:
                    raise WorkflowError('no_next_stage', 'There is no enabled next stage.')
                following[0]['state'] = 'eligible'
                workflow['current_stage_id'] = following[0]['stage_id']
            else:
                if stage['type'] == 'oa':
                    raise WorkflowError('assessment_not_ready', 'OA decisions require the assessment evaluation workflow.')
                if stage['type'] == 'screening' and stage['state'] != 'completed':
                    raise WorkflowError('result_required', 'A completed screening result is required.')
                if stage['state'] not in {'eligible', 'completed'}:
                    raise WorkflowError('illegal_transition', 'Stage is not ready for a recruiter decision.')
                stage['state'] = 'completed'
                stage['outcome'] = {'clear': 'cleared', 'not_clear': 'not_cleared', 'review': 'review_required'}[action]
                stage['decision_source'] = 'recruiter'
            workflow['revision'] += 1
            result = dict(workflow_version_id=app['workflow_version_id'], revision=workflow['revision'],
                lifecycle=workflow['lifecycle'], current_stage_id=workflow['current_stage_id'], **projection(workflow))
            event = dict(application_id=str(app['_id']), job_id=app['job_id'], workflow_version_id=app['workflow_version_id'],
                revision=workflow['revision'], operation_key=key, action=action, actor_id=str(actor['_id']),
                actor_role=actor.get('user_type'), reason=reason.strip(), request_hash=fingerprint,
                from_stage=before, to_stage=next(s for s in workflow['stages'] if s['stage_id'] == workflow['current_stage_id']),
                occurred_at=datetime.now(timezone.utc), result=result)
            self.repo.write_snapshot(app, workflow, dict(status=result['status'], workflow_label=result['workflow_label'],
                updated_at=event['occurred_at'], updated_by=str(actor['_id'])), event, session)
            return result
        try:
            return atomic(self.db, change)
        except DuplicateKeyError:
            return atomic(self.db, change)

    def history(self, application_id, actor, after_revision=-1, limit=100):
        if type(after_revision) is not int or after_revision < -1 or type(limit) is not int or not 1 <= limit <= 250:
            raise WorkflowError('invalid_pagination', 'Provide after_revision >= -1 and limit from 1 to 250.', 400)
        app = self.repo.application(application_id)
        self.access(app, actor)
        events = list(self.db.stage_events.find({'application_id': str(app['_id']), 'revision': {'$gt': after_revision}},
            {'_id': 0, 'result': 0, 'request_hash': 0}).sort('revision', 1).limit(limit + 1))
        has_more = len(events) > limit
        events = events[:limit]
        if actor.get('user_type') in {'candidate', 'student'}:
            events = [{k: e[k] for k in ('revision', 'action', 'occurred_at') if k in e} for e in events]
            for event in events:
                if event.get('action') in {'company_qualify', 'company_not_qualify', 'company_hold'}:
                    event['action'] = 'oa_review_updated'
        return {'workflow': public_workflow(app), 'events': events, 'has_more': has_more,
                'next_after_revision': events[-1]['revision'] if events else after_revision}
