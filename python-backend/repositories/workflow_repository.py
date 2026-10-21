"""Workflow storage. Snapshot, stage views and immutable events commit together."""
from bson import ObjectId
from pymongo import ReturnDocument
from models.hiring_workflow import WorkflowError


def ensure_workflow_indexes(db):
    db.hiring_workflow_versions.create_index([('job_id', 1), ('revision', 1)], unique=True)
    db.hiring_workflow_versions.create_index([('job_id', 1), ('operation_key', 1)], unique=True)
    db.application_stages.create_index([('application_id', 1), ('stage_id', 1)], unique=True)
    db.application_stages.create_index([('job_id', 1), ('type', 1), ('outcome', 1)])
    db.stage_events.create_index([('application_id', 1), ('operation_key', 1)], unique=True)
    db.stage_events.create_index([('application_id', 1), ('revision', 1)], unique=True)
    db.applications.create_index([('job_id', 1), ('workflow.lifecycle', 1), ('workflow.current_stage_id', 1)])


class WorkflowRepository:
    def __init__(self, db):
        self.db = db

    def application(self, application_id, session=None):
        try:
            oid = ObjectId(application_id)
        except Exception:
            raise WorkflowError('invalid_id', 'Invalid application ID.', 400) from None
        application = self.db.applications.find_one({'_id': oid}, session=session)
        if not application:
            raise WorkflowError('not_found', 'Application not found.', 404)
        return application

    def write_snapshot(self, application, workflow, fields, event, session):
        old = application.get('workflow')
        query = {'_id': application['_id'], 'status': application.get('status')}
        if old:
            query['workflow.revision'] = old['revision']
        else:
            query['workflow_version_id'] = {'$in': [None, '']}
        changed = self.db.applications.find_one_and_update(query,
            {'$set': dict(fields, workflow=workflow)}, session=session, return_document=ReturnDocument.AFTER)
        if not changed:
            raise WorkflowError('stale_revision', 'Application changed; refresh before retrying.')
        self.db.application_stages.update_many({'application_id': str(application['_id']),
            'stage_id': {'$nin': [s['stage_id'] for s in workflow['stages']]}}, {'$set': {'is_current': False}}, session=session)
        for stage in workflow['stages']:
            identity = dict(application_id=str(application['_id']), stage_id=stage['stage_id'])
            self.db.application_stages.update_one(identity, {'$set': dict(stage,
                job_id=application['job_id'], workflow_version_id=changed['workflow_version_id'], is_current=True,
                revision=workflow['revision'])}, upsert=True, session=session)
        self.db.stage_events.insert_one(event, session=session)
        return changed

    def counts(self, job_id):
        """Derived current-stage funnel: avoids drift-prone incremented counters."""
        return list(self.db.applications.aggregate([
            {'$match': {'job_id': str(job_id), 'workflow_version_id': {'$type': 'string', '$ne': ''}}},
            {'$group': {'_id': {'stage': '$workflow.current_stage_id', 'lifecycle': '$workflow.lifecycle'},
                        'count': {'$sum': 1}}},
            {'$sort': {'_id.stage': 1, '_id.lifecycle': 1}},
        ]))
