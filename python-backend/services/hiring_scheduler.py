"""Bounded durable scheduling; ambiguous email outcomes are never auto-retried."""
from datetime import timedelta
from html import escape
import os
from bson import ObjectId
from pymongo import ReturnDocument
from config.workflow import managed
from models.hiring_workflow import WorkflowError
from services.hiring_progression_service import HiringProgressionService, scheduling_enabled, utc


class HiringScheduler:
    def __init__(self, db, service=None, sender=None):
        self.db, self.service, self.sender = db, service or HiringProgressionService(db), sender

    def tick(self, limit=50):
        if not scheduling_enabled(): return dict(disabled=True)
        stats = dict(enrolled=0, reconciled=0, invited=0, expired=0, held=0)
        # Rotate independently through each category so one held candidate cannot
        # starve later cohorts. A crash replays the batch safely.
        queries = dict(enroll={'hiring_enrollment_version_id': {'$type': 'string'}, 'workflow_version_id': {'$in': [None, '']}, 'processing_status': 'completed'},
            reconcile={'workflow_version_id': {'$type': 'string', '$ne': ''}, 'workflow.lifecycle': 'active'})
        for name, base in queries.items():
            cursor = self.db.hiring_scheduler_cursors.find_one({'_id': name}) or {}
            query = dict(base)
            if cursor.get('after'): query['_id'] = {'$gt': cursor['after']}
            batch = list(self.db.applications.find(query).sort('_id', 1).limit(limit))
            if not batch and cursor.get('after'):
                batch = list(self.db.applications.find(base).sort('_id', 1).limit(limit))
            for app in batch:
                try:
                    if name == 'enroll':
                        self.service.enroll(str(app['_id'])); stats['enrolled'] += 1
                    else:
                        version = self.db.hiring_workflow_versions.find_one({'_id': ObjectId(app['workflow_version_id'])})
                        if not version or not version.get('setup_version_id'): continue
                        stage = next(s for s in app['workflow']['stages'] if s['stage_id'] == app['workflow']['current_stage_id'])
                        if stage['type'] == 'screening':
                            self.service.screening_notices(str(app['_id']))
                            doc = self.db.interviews.find_one({'application_id': str(app['_id']), 'status': {'$in': ['completed', 'terminated']}}, sort=[('_id', -1)])
                            if doc: self.service.ingest_screening(str(doc['_id'])); stats['reconciled'] += 1
                            self.service.expire_screening(str(app['_id']))
                            fresh = self.service.workflow.repo.application(str(app['_id']))
                            screening = next(s for s in fresh['workflow']['stages'] if s['type'] == 'screening')
                            if screening['outcome'] == 'cleared':
                                result = self.service.automatic_invite(str(app['_id']))
                                if result.get('invitation_id') and not result.get('replayed'): stats['invited'] += 1
                    fresh = self.db.applications.find_one({'_id': app['_id']})
                    if (fresh.get('workflow') or {}).get('revision') != (app.get('workflow') or {}).get('revision'):
                        from services.hiring_progression_service import notify_hiring_progress
                        notify_hiring_progress(self.db, str(app['_id']))
                except WorkflowError: stats['held'] += 1
            self.db.hiring_scheduler_cursors.update_one({'_id': name}, {'$set': {'after': batch[-1]['_id'] if batch else None}}, upsert=True)
        for invitation in self.db.assessment_invitations.find({'pool': {'$ne': 'practice'}, 'state': 'invited', 'start_closes_at': {'$lte': self.service.clock()}}).sort('start_closes_at', 1).limit(limit):
            if self.service.expire_invitation(str(invitation['_id'])): stats['expired'] += 1
        return stats

    def deliver_once(self):
        if not scheduling_enabled() or os.getenv('GENHIRE_HIRING_EMAILS_ENABLED', 'false').lower() != 'true': return False
        now, token = self.service.clock(), str(ObjectId())
        notice = self.db.hiring_outbox.find_one_and_update({'$or': [dict(state='queued', due_at={'$lte': now}),
            dict(state='preparing', lease_until={'$lte': now})]}, {'$set': dict(state='preparing', lease_token=token, lease_until=now+timedelta(minutes=2))},
            sort=[('due_at', 1)], return_document=ReturnDocument.AFTER)
        if not notice: return False
        identity = dict(_id=notice['_id'], lease_token=token, state='preparing')
        app = self.db.applications.find_one({'_id': ObjectId(notice['application_id'])})
        recipient = self.db.users.find_one({'_id': ObjectId(notice['recipient_id'])})
        invitation = self.db.assessment_invitations.find_one({'application_id': notice['application_id']})
        obsolete = (not app or not managed(app) or app['workflow']['lifecycle'] != 'active' or not recipient or recipient.get('is_active') is False)
        if notice['kind'] == 'oa_time_extended':
            attempt = self.db.assessment_attempts.find_one({'application_id': notice['application_id']})
            obsolete = obsolete or not attempt or attempt['state'] != 'in_progress' or utc(attempt['deadline']) <= now
        elif notice['kind'].startswith('oa_'):
            obsolete = obsolete or not invitation or invitation['state'] != 'invited' or utc(invitation['start_closes_at']) <= now
        screening_schedule = None
        if notice['kind'] in {'screening_invitation', 'screening_reminder'} and not obsolete:
            version = self.service.version(app['workflow_version_id'])
            screening_schedule = version['configuration']['schedule']
            stage = next(s for s in app['workflow']['stages'] if s['stage_id'] == app['workflow']['current_stage_id'])
            obsolete = stage['type'] != 'screening' or stage['state'] not in {'eligible', 'in_progress'} or utc(screening_schedule['screening_closes_at']) <= now
        if obsolete or not recipient.get('email'):
            self.db.hiring_outbox.update_one(identity, {'$set': {'state': 'cancelled'}}); return True
        message = 'Your application status is now: ' + str(app.get('workflow_label', 'Awaiting recruiter decision')) + '.'
        if notice['kind'] == 'oa_time_extended':
            message += f" Your approved assessment deadline is now {utc(attempt['deadline']).isoformat()}. Reconnecting does not reset it."
        elif notice['kind'].startswith('oa_'):
            message += f" OA entry opens {utc(invitation['opens_at']).isoformat()} and closes {utc(invitation['start_closes_at']).isoformat()}. A timely start receives the full {invitation['duration_minutes']}-minute attempt duration."
        if screening_schedule:
            message += f" Screening opens {utc(screening_schedule['screening_opens_at']).isoformat()} and must finish by {utc(screening_schedule['screening_closes_at']).isoformat()}."
        message += ' Sign in to GenHire and open your applications for details.'
        if self.sender is None:
            from services.email_service import EmailService
            self.sender = EmailService().send_email
        # Persist intent before calling an external provider. A process death or
        # False/exception may mean delivery happened: require operator reconciliation.
        claimed = self.db.hiring_outbox.update_one(identity, {'$set': {'state': 'dispatching', 'dispatch_started_at': now}})
        if not claimed.matched_count: return True
        state = 'delivery_unknown'
        try:
            if self.sender(recipient['email'], 'GenHire application update', '<p>'+escape(message)+'</p>', message): state = 'sent'
        except Exception: pass
        self.db.hiring_outbox.update_one({'_id': notice['_id'], 'lease_token': token, 'state': 'dispatching'},
            {'$set': {'state': state, 'updated_at': self.service.clock()}})
        return True
