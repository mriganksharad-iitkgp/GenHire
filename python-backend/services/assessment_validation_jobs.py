"""Durable validation jobs keep external execution out of Flask requests."""
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from pymongo import ReturnDocument
from models.hiring_workflow import WorkflowError
from services.assessment_authoring_service import AssessmentAuthoringService, object_id


class AssessmentValidationJobs:
    def __init__(self, db, validator=None):
        self.db, self.authoring = db, AssessmentAuthoringService(db, validator)

    @staticmethod
    def public(job):
        return dict(id=str(job['_id']), state=job['state'], question_version_id=job['question_version_id'],
            validation_id=job.get('validation_id'), error_code=job.get('error_code'))

    def enqueue(self, actor, version_id, key):
        q = self.authoring.question(version_id, actor, True)
        if not self.authoring.validator.capabilities()['available']:
            raise WorkflowError('validator_unavailable', 'Managed execution is unavailable or awaits live validation. Manual drafts remain available.', 503)
        allocated = ObjectId()
        def create(session):
            self.authoring.question(version_id, actor, True, session)
            record = dict(_id=allocated, owner_id=q['owner_id'], actor_id=str(actor['_id']), question_version_id=version_id,
                state='queued', lease_until=datetime.now(timezone.utc), created_at=datetime.now(timezone.utc))
            self.db.assessment_validation_jobs.insert_one(record, session=session)
            return self.public(record)
        return self.authoring.mutate(actor, key, dict(action='enqueue_validation', version=version_id), create)

    def get(self, actor, job_id):
        job = self.db.assessment_validation_jobs.find_one({'_id': object_id(job_id)})
        if not job: raise WorkflowError('not_found', 'Validation job not found.', 404)
        self.authoring.question(job['question_version_id'], actor)
        return self.public(job)

    def run_once(self):
        now, token = datetime.now(timezone.utc), str(ObjectId())
        job = self.db.assessment_validation_jobs.find_one_and_update({'state': {'$in': ['queued', 'running']}, 'lease_until': {'$lte': now}},
            {'$set': {'state': 'running', 'lease_token': token, 'lease_until': now + timedelta(minutes=10)}},
            sort=[('created_at', 1)], return_document=ReturnDocument.AFTER)
        if not job: return False
        identity = dict(_id=job['_id'], lease_token=token)
        try:
            actor = self.db.users.find_one({'_id': ObjectId(job['actor_id'])})
            if not actor: raise WorkflowError('actor_unavailable', 'Validation actor is no longer authorized.', 403)
            def heartbeat():
                now = datetime.now(timezone.utc)
                return self.db.assessment_validation_jobs.update_one(dict(identity, state='running', lease_until={'$gt': now}),
                    {'$set': {'lease_until': now + timedelta(minutes=10)}}).matched_count == 1
            self.authoring.validator.progress_hook = heartbeat
            def commit_guard(session):
                current_actor = self.db.users.find_one({'_id': ObjectId(job['actor_id'])}, session=session)
                if not current_actor: return False
                self.authoring.question(job['question_version_id'], current_actor, True, session)
                return self.db.assessment_validation_jobs.update_one(dict(identity, state='running', lease_until={'$gt': datetime.now(timezone.utc)}),
                    {'$set': {'commit_guard_at': datetime.now(timezone.utc)}}, session=session).matched_count == 1
            validation = self.authoring.validate(actor, job['question_version_id'], 'validation-job:' + str(job['_id']), commit_guard=commit_guard)
            self.db.assessment_validation_jobs.update_one(identity, {'$set': {'state': 'completed', 'validation_id': validation['_id']}})
        except Exception as exc:
            self.db.assessment_validation_jobs.update_one(identity, {'$set': {'state': 'failed',
                'error_code': exc.code if isinstance(exc, WorkflowError) else 'validation_failed'}})
        return True
