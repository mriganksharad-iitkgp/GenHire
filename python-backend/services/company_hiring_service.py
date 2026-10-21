"""Recruiter decisions and company handoff; never rewrites objective grades."""
from copy import deepcopy
from datetime import timedelta
from html import escape
import os
import re
from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from config.workflow import managed, workflow_enabled
from core.mongo_transactions import atomic
from models.hiring_workflow import WorkflowError, projection
from services.workflow_service import WorkflowService, operation_key, request_identity
from services.hiring_progression_service import now_utc, utc
from services.assessment_authoring_service import object_id


def ensure_company_indexes(db):
    db.company_actions.create_index([('actor_id', 1), ('key', 1)], unique=True)
    db.company_bulk_operations.create_index([('actor_id', 1), ('key', 1)], unique=True)
    db.company_decisions.create_index('application_id', unique=True)
    db.company_previews.create_index('expires_at', expireAfterSeconds=86400)
    db.company_previews.create_index([('actor_id', 1), ('operation_key', 1)], unique=True, partialFilterExpression={'operation_key': {'$type': 'string'}})
    db.company_messages.create_index([('batch_id', 1), ('email', 1)], unique=True)
    db.company_messages.create_index([('state', 1), ('created_at', 1)])
    db.assessment_evaluation_reports.create_index('application_id')


class CompanyHiringService:
    def __init__(self, db, clock=now_utc):
        self.db, self.clock, self.workflow = db, clock, WorkflowService(db)

    def require_enabled(self):
        self.workflow.require_enabled()
        if os.getenv('GENHIRE_COMPANY_HIRING_ENABLED', 'false').lower() != 'true':
            raise WorkflowError('company_hiring_disabled', 'Company hiring controls are not enabled.', 503)

    def evidence(self, app, session=None):
        attempt = self.db.assessment_attempts.find_one({'application_id': str(app['_id'])}, session=session)
        report = self.db.assessment_evaluation_reports.find_one({'attempt_id': str(attempt['_id'])}, session=session) if attempt else None
        summary = self.db.assessment_integrity_summaries.find_one({'attempt_id': str(attempt['_id'])}, session=session) if attempt else None
        review = (summary or {}).get('review') or {}
        integrity_hold = bool(attempt and attempt.get('integrity_policy') and review.get('decision') != 'reviewed_clear')
        return attempt, report, summary, integrity_hold

    def record(self, app, wf, actor, action, key, reason, session):
        wf['revision'] += 1
        result = dict(revision=wf['revision'], lifecycle=wf['lifecycle'], current_stage_id=wf['current_stage_id'], **projection(wf))
        event = dict(application_id=str(app['_id']), job_id=app['job_id'], workflow_version_id=app['workflow_version_id'],
            revision=wf['revision'], operation_key='company:'+str(actor['_id'])+':'+key, action=action,
            actor_id=str(actor['_id']), actor_role=actor.get('user_type'), reason=reason, occurred_at=self.clock(), result=result)
        event['from_stage'] = next(s for s in app['workflow']['stages'] if s['stage_id'] == app['workflow']['current_stage_id'])
        event['to_stage'] = next(s for s in wf['stages'] if s['stage_id'] == wf['current_stage_id'])
        event['added_stages'] = [s for s in wf['stages'] if s['stage_id'] not in {old['stage_id'] for old in app['workflow']['stages']}]
        self.workflow.repo.write_snapshot(app, wf, dict(status=result['status'], workflow_label=result['workflow_label'], updated_at=self.clock()), event, session)
        return result

    def mutate(self, actor, key, payload, callback):
        self.require_enabled(); operation_key(key)
        identity = dict(actor_id=str(actor['_id']), key=key)
        fingerprint = request_identity(payload)
        def change(session):
            # Authorization always runs before replay too.
            app = self.workflow.repo.application(payload['application_id'], session)
            self.workflow.access(app, actor, True, session)
            old = self.db.company_actions.find_one(identity, session=session)
            if old:
                if old['fingerprint'] != fingerprint: raise WorkflowError('idempotency_conflict', 'Operation key reused with different content.')
                return old['result']
            if not managed(app): raise WorkflowError('not_managed', 'A canonical workflow is required.')
            if type(payload.get('expected_revision')) is not int or app['workflow']['revision'] != payload['expected_revision']:
                raise WorkflowError('stale_revision', 'Application changed; reload before acting.')
            reason = payload.get('reason')
            if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 1000:
                raise WorkflowError('reason_required', 'Provide a reason of 10–1000 characters.', 400)
            result = callback(app, session, reason.strip())
            self.db.company_actions.insert_one(dict(identity, fingerprint=fingerprint, result=result, created_at=self.clock()), session=session)
            return result
        try: return atomic(self.db, change)
        except DuplicateKeyError: return atomic(self.db, change)

    def action(self, actor, application_id, action, expected_revision, key, reason, name=None):
        payload = dict(application_id=application_id, action=action, expected_revision=expected_revision, reason=reason, name=name)
        if action not in {'qualify', 'not_qualify', 'hold', 'release', 'advance', 'add_company_stage', 'revoke_release'}:
            raise WorkflowError('invalid_action', 'Unsupported company action.', 400)
        def change(app, session, reason):
            wf = deepcopy(app['workflow']); stage = next(s for s in wf['stages'] if s['stage_id'] == wf['current_stage_id'])
            attempt, report, summary, integrity_hold = self.evidence(app, session)
            decision = self.db.company_decisions.find_one({'application_id': application_id}, session=session)
            oa = next((s for s in wf['stages'] if s['type'] == 'oa' and s['enabled']), None)
            if action in {'qualify', 'not_qualify', 'hold'}:
                if wf['lifecycle'] != 'active' or stage['type'] != 'oa' or stage['state'] != 'completed':
                    raise WorkflowError('decision_locked', 'OA decisions require a completed current OA on an active application.')
                if not report or report['state'] != 'complete' or report.get('score') is None:
                    raise WorkflowError('result_unavailable', 'A usable objective evaluation is required; missing execution is not a failed score.')
                if action == 'qualify' and integrity_hold:
                    raise WorkflowError('integrity_hold', 'Resolve the integrity review before qualifying this candidate.')
                outcome = {'qualify': 'cleared', 'not_qualify': 'not_cleared', 'hold': 'review_required'}[action]
                binding = dict(input_hash=report['input_hash'], integrity_revision=(summary or {}).get('review_revision', 0))
                self.db.company_decisions.update_one({'application_id': application_id}, {'$set': dict(outcome=outcome,
                    attempt_id=str(attempt['_id']), binding=binding, reason=reason, actor_id=str(actor['_id']), decided_at=self.clock())}, upsert=True, session=session)
                # Decisions stay private until separately released. Changing one
                # withdraws any previously published snapshot atomically.
                self.db.assessment_evaluation_reports.update_one({'_id': report['_id']}, {'$set': {'released': False}, '$unset': {'released_summary': ''}}, session=session)
                stage.update(outcome='pending', result_release_pending=True)
            elif action in {'release', 'revoke_release'}:
                if not report or report['state'] != 'complete' or not decision:
                    raise WorkflowError('decision_required', 'Record a usable OA decision before releasing its summary.')
                if action == 'release':
                    self.check_decision(decision, report, summary, integrity_hold)
                    # This is the only candidate-facing result payload. No per-
                    # question grades, hidden fixtures, peer data or notes.
                    released = dict(score=report['score'], outcome=decision['outcome'], sections=[{k: s[k] for k in ('type', 'earned', 'possible', 'weight')} for s in report['sections']], released_at=self.clock())
                    self.db.assessment_evaluation_reports.update_one({'_id': report['_id']}, {'$set': dict(released=True, released_summary=released)}, session=session)
                    oa.update(outcome=decision['outcome'], result_release_pending=False)
                else:
                    self.db.assessment_evaluation_reports.update_one({'_id': report['_id']}, {'$set': {'released': False}, '$unset': {'released_summary': ''}}, session=session)
                    oa.update(outcome='pending', result_release_pending=True)
            elif action == 'add_company_stage':
                if wf['lifecycle'] != 'active' or stage['state'] not in {'completed', 'eligible'} or stage['type'] not in {'screening', 'oa', 'company'}:
                    raise WorkflowError('stage_locked', 'Add company stages after screening or at a company handoff.')
                if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80 or len(wf['stages']) >= 12:
                    raise WorkflowError('invalid_stage', 'Provide a company stage name; at most 12 total stages.', 400)
                wf['stages'].append(dict(stage_id='company_'+str(ObjectId()), type='company', name=name.strip(), enabled=True, state='not_ready', outcome='pending'))
            else:
                if wf['lifecycle'] != 'active' or stage['state'] != 'completed': raise WorkflowError('advance_locked', 'A completed active stage is required.')
                if stage['type'] == 'oa':
                    self.check_decision(decision, report, summary, integrity_hold)
                    if decision['outcome'] != 'cleared': raise WorkflowError('not_qualified', 'Only an approved qualified candidate can advance.')
                elif stage['outcome'] != 'cleared': raise WorkflowError('not_qualified', 'Clear the current stage before advancing.')
                following = [s for s in wf['stages'][wf['stages'].index(stage)+1:] if s['enabled']]
                if not following or following[0]['type'] != 'company': raise WorkflowError('company_stage_required', 'Configure the next company-managed stage first.')
                following[0]['state'] = 'eligible'; wf['current_stage_id'] = following[0]['stage_id']
            # Serialize with review changes, not just application changes.
            if summary and action in {'qualify', 'release', 'advance'}:
                self.db.assessment_integrity_summaries.update_one({'_id': summary['_id']}, {'$inc': {'decision_fence': 1}}, session=session)
            return self.record(app, wf, actor, 'company_'+action, key, reason, session)
        return self.mutate(actor, key, payload, change)

    @staticmethod
    def check_decision(decision, report, summary, integrity_hold):
        if not decision or not report or report['state'] != 'complete': raise WorkflowError('decision_required', 'A completed evaluation and recruiter decision are required.')
        binding = dict(input_hash=report['input_hash'], integrity_revision=(summary or {}).get('review_revision', 0))
        if decision['binding'] != binding: raise WorkflowError('decision_stale', 'Evaluation or integrity review changed; record a new decision.')
        if decision['outcome'] == 'cleared' and integrity_hold: raise WorkflowError('integrity_hold', 'Integrity review must be resolved first.')

    def detail(self, actor, application_id):
        app = self.workflow.repo.application(application_id); self.workflow.access(app, actor)
        if actor.get('user_type') in {'candidate', 'student'}: raise WorkflowError('forbidden', 'Reviewer access is required.', 403)
        self.db.company_access.insert_one(dict(application_id=application_id, actor_id=str(actor['_id']), action='company_review_read', occurred_at=self.clock()))
        attempt, report, summary, hold = self.evidence(app)
        decision = self.db.company_decisions.find_one({'application_id': application_id}, {'_id': 0})
        return dict(application_id=application_id, revision=app.get('workflow', {}).get('revision'), decision=decision,
            objective_recommendation=(report or {}).get('recommendation', 'pending'), integrity_hold=hold,
            review_revision=(summary or {}).get('review_revision'), released=bool((report or {}).get('released')),
            enabled=os.getenv('GENHIRE_COMPANY_HIRING_ENABLED', 'false').lower() == 'true')

    def bulk(self, actor, job_id, items, action, key, reason):
        self.require_enabled(); self.workflow.job(job_id, actor, True); operation_key(key)
        if not isinstance(items, list) or not 1 <= len(items) <= 100 or any(not isinstance(i, dict) or set(i) != {'application_id', 'expected_revision'} or not isinstance(i.get('application_id'), str) or type(i.get('expected_revision')) is not int for i in items):
            raise WorkflowError('invalid_items', 'Select 1–100 application/revision pairs.', 400)
        if len({i['application_id'] for i in items}) != len(items): raise WorkflowError('duplicate_items', 'Select each application once.', 400)
        identity = dict(actor_id=str(actor['_id']), key=key)
        fingerprint = request_identity(dict(job_id=job_id, items=items, action=action, reason=reason))
        def bind(session):
            old = self.db.company_bulk_operations.find_one(identity, session=session)
            if old:
                if old['fingerprint'] != fingerprint: raise WorkflowError('idempotency_conflict', 'Bulk key reused with different selection or decisions.')
            else: self.db.company_bulk_operations.insert_one(dict(identity, fingerprint=fingerprint, created_at=self.clock()), session=session)
        try: atomic(self.db, bind)
        except DuplicateKeyError: atomic(self.db, bind)
        outcomes = []
        for item in items:
            identifier = item['application_id']
            try:
                app = self.workflow.repo.application(identifier)
                if app['job_id'] != job_id: raise WorkflowError('wrong_job', 'Application does not belong to this job.', 403)
                item_key = 'bulk:'+request_identity(dict(key=key, job=job_id, application=identifier))
                if action in {'clear', 'not_clear', 'review', 'reject', 'hire', 'close'}:
                    result = self.workflow.transition(identifier, actor, action, item['expected_revision'], item_key, reason)
                else: result = self.action(actor, identifier, action, item['expected_revision'], item_key, reason)
                outcomes.append(dict(application_id=identifier, ok=True, result=result))
            except WorkflowError as exc: outcomes.append(dict(application_id=identifier, ok=False, error_code=exc.code, error=str(exc)))
        return dict(outcomes=outcomes)

    def rows(self, actor, job_id, stage=None, lifecycle=None, after=None, limit=100, qualification=None):
        self.workflow.job(job_id, actor)
        if type(limit) is not int or not 1 <= limit <= 200: raise WorkflowError('invalid_pagination', 'Limit must be 1–200.', 400)
        query = dict(job_id=job_id, workflow_version_id={'$type': 'string', '$ne': ''})
        if stage: query['workflow.current_stage_id'] = stage
        if lifecycle:
            if lifecycle not in {'active', 'hired', 'rejected', 'withdrawn', 'closed'}: raise WorkflowError('invalid_filter', 'Invalid lifecycle.', 400)
            query['workflow.lifecycle'] = lifecycle
        if qualification:
            if qualification not in {'cleared', 'not_cleared', 'review_required', 'pending'}: raise WorkflowError('invalid_filter', 'Invalid OA recommendation.', 400)
            # Lookup inside the query, before pagination. Never filter an already
            # paginated page and pretend it represents the full cohort.
            pipeline = [{'$match': query}, {'$addFields': {'application_key': {'$toString': '$_id'}}},
                {'$lookup': {'from': 'assessment_evaluation_reports', 'localField': 'application_key', 'foreignField': 'application_id', 'as': 'oa_reports'}},
                {'$match': {'oa_reports.recommendation': qualification}}]
            if after: pipeline.append({'$match': {'_id': {'$gt': object_id(after)}}})
            apps = list(self.db.applications.aggregate(pipeline+[{'$sort': {'_id': 1}}, {'$limit': limit+1}]))
        else:
            if after: query['_id'] = {'$gt': object_id(after)}
            apps = list(self.db.applications.find(query).sort('_id', 1).limit(limit+1))
        rows = []
        for app in apps[:limit]:
            attempt, report, summary, hold = self.evidence(app)
            stage_doc = next(s for s in app['workflow']['stages'] if s['stage_id'] == app['workflow']['current_stage_id'])
            decision = self.db.company_decisions.find_one({'application_id': str(app['_id'])}) or {}
            rows.append(dict(application_id=str(app['_id']), name=app.get('student_name', ''), email=app.get('student_email', ''),
                revision=app['workflow']['revision'], lifecycle=app['workflow']['lifecycle'], stage_id=stage_doc['stage_id'], stage=stage_doc['name'],
                state=stage_doc['state'], outcome=stage_doc['outcome'], label=projection(app['workflow'])['workflow_label'],
                cv_score=app.get('cv_score'), interview_score=app.get('interview_score'), screening_proctoring_score=app.get('proctoring_score'),
                oa_score=(report or {}).get('score'), oa_recommendation=(report or {}).get('recommendation', 'pending'),
                integrity_hold=hold, recruiter_decision=decision.get('outcome', 'pending'), result_released=bool((report or {}).get('released'))))
        return dict(rows=rows, has_more=len(apps)>limit, next_after=rows[-1]['application_id'] if rows else after, funnel=self.workflow.repo.counts(job_id))

    def export(self, actor, job_id, stage=None, lifecycle=None, qualification=None):
        # Explicit bound; refuse truncation rather than silently dropping people.
        rows, after = [], None
        for _ in range(25):
            page = self.rows(actor, job_id, stage, lifecycle, after, 200, qualification); rows += page['rows']; after = page['next_after']
            if not page['has_more']: break
        if page['has_more']: raise WorkflowError('export_too_large', 'Narrow the filter to at most 5000 candidates.', 400)
        self.db.company_access.insert_one(dict(actor_id=str(actor['_id']), job_id=job_id, action='stage_export', count=len(rows), occurred_at=self.clock()))
        return rows

    def preview(self, actor, job_id, items, subject, message):
        self.require_enabled(); self.workflow.job(job_id, actor, True)
        if not isinstance(items, list) or not 1 <= len(items) <= 100 or any(not isinstance(i, str) for i in items) or len(set(items)) != len(items):
            raise WorkflowError('invalid_items', 'Choose 1–100 distinct application IDs.', 400)
        if not isinstance(subject, str) or not 1 <= len(subject.strip()) <= 160 or '\n' in subject or '\r' in subject or not isinstance(message, str) or not 10 <= len(message.strip()) <= 10000:
            raise WorkflowError('invalid_message', 'Provide a single-line subject and a 10–10000 character plain-text message.', 400)
        recipients, skipped, seen = [], [], set()
        for identifier in items:
            app = self.workflow.repo.application(identifier)
            if app['job_id'] != job_id: raise WorkflowError('wrong_job', 'Recipient application is outside this job.', 403)
            user = self.db.users.find_one({'_id': object_id(app['student_id'])}) or {}
            email = str(user.get('email') or '').strip().lower()
            if not managed(app) or user.get('is_active') is False or app['workflow']['lifecycle'] == 'withdrawn' or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or email in seen:
                skipped.append(dict(application_id=identifier, reason='unavailable_withdrawn_or_duplicate')); continue
            seen.add(email); recipients.append(dict(application_id=identifier, candidate_id=app['student_id'], email=email, name=app.get('student_name', ''), revision=app['workflow']['revision']))
        if not recipients: raise WorkflowError('no_recipients', 'No eligible unique recipients.', 400)
        document = dict(job_id=job_id, actor_id=str(actor['_id']), subject=subject.strip(), message=message.strip(), recipients=recipients,
            skipped=skipped, created_at=self.clock(), expires_at=self.clock()+timedelta(minutes=10))
        identifier = self.db.company_previews.insert_one(document).inserted_id
        return dict(preview_id=str(identifier), recipients=recipients, skipped=skipped, subject=document['subject'], message=document['message'], expires_at=document['expires_at'])

    def queue(self, actor, job_id, preview_id, key, accepted):
        self.require_enabled(); self.workflow.job(job_id, actor, True); operation_key(key)
        if accepted is not True: raise WorkflowError('approval_required', 'Explicit recipient/content approval is required.', 400)
        def queue(session):
            preview = self.db.company_previews.find_one({'_id': object_id(preview_id), 'job_id': job_id, 'actor_id': str(actor['_id'])}, session=session)
            if not preview: raise WorkflowError('not_found', 'Preview not found.', 404)
            # Replay is bound to this immutable preview, independent of expiry.
            if preview.get('batch_id'):
                if preview['operation_key'] != key: raise WorkflowError('already_queued', 'This preview was already queued.')
                return dict(batch_id=preview['batch_id'], queued=len(preview['recipients']))
            other = self.db.company_previews.find_one({'actor_id': str(actor['_id']), 'operation_key': key}, session=session)
            if other: raise WorkflowError('idempotency_conflict', 'Queue operation key was reused.')
            if utc(preview['expires_at']) <= self.clock(): raise WorkflowError('preview_expired', 'Preview again before sending.')
            batch_id = str(ObjectId())
            for recipient in preview['recipients']:
                app = self.workflow.repo.application(recipient['application_id'], session)
                user = self.db.users.find_one({'_id': object_id(recipient['candidate_id'])}, session=session) or {}
                if app['workflow']['revision'] != recipient['revision'] or app['workflow']['lifecycle'] == 'withdrawn' or user.get('is_active') is False or str(user.get('email', '')).strip().lower() != recipient['email']:
                    raise WorkflowError('preview_stale', 'A recipient changed; preview the batch again.')
                self.db.applications.update_one({'_id': app['_id']}, {'$inc': {'company_message_fence': 1}}, session=session)
                self.db.users.update_one({'_id': user['_id']}, {'$inc': {'company_message_fence': 1}}, session=session)
                self.db.company_messages.insert_one(dict(recipient, job_id=job_id, batch_id=batch_id, owner_id=str(actor['_id']),
                    subject=preview['subject'], message=preview['message'], state='queued', created_at=self.clock()), session=session)
            self.db.company_previews.update_one({'_id': preview['_id']}, {'$set': dict(batch_id=batch_id, operation_key=key)}, session=session)
            return dict(batch_id=batch_id, queued=len(preview['recipients']))
        try: return atomic(self.db, queue)
        except DuplicateKeyError: return atomic(self.db, queue)

    def deliveries(self, actor, job_id, batch_id):
        self.workflow.job(job_id, actor)
        self.db.company_access.insert_one(dict(actor_id=str(actor['_id']), job_id=job_id, action='company_delivery_read', batch_id=batch_id, occurred_at=self.clock()))
        return dict(messages=list(self.db.company_messages.find(dict(job_id=job_id, batch_id=batch_id), {'_id': 1, 'email': 1, 'application_id': 1, 'state': 1, 'updated_at': 1}).limit(100)))

    def deliver_once(self, sender=None):
        # Separate explicit worker; never sends from a web request or a test.
        if not workflow_enabled() or os.getenv('GENHIRE_COMPANY_HIRING_ENABLED', 'false').lower() != 'true' or os.getenv('GENHIRE_HIRING_EMAILS_ENABLED', 'false').lower() != 'true': return False
        if sender is None:
            from services.email_service import EmailService
            mailer = EmailService()
            if getattr(mailer.provider, 'name', 'noop') == 'noop': return False
            sender = mailer.send_email
        now, token = self.clock(), str(ObjectId())
        doc = self.db.company_messages.find_one_and_update({'$or': [dict(state='queued'), dict(state='preparing', lease_until={'$lte': now})]},
            {'$set': dict(state='preparing', lease_token=token, lease_until=now+timedelta(minutes=2))}, sort=[('created_at', 1)], return_document=ReturnDocument.AFTER)
        if not doc: return False
        identity = dict(_id=doc['_id'], state='preparing', lease_token=token)
        app = self.db.applications.find_one({'_id': object_id(doc['application_id'])})
        user = self.db.users.find_one({'_id': object_id(doc['candidate_id'])}) or {}
        initiator = self.db.users.find_one({'_id': object_id(doc['owner_id'])}) or {}
        authorized = initiator.get('is_active') is not False
        try: self.workflow.job(doc['job_id'], initiator, True)
        except WorkflowError: authorized = False
        # Approved content/recipient snapshots cannot silently follow stage edits.
        if not authorized or not app or app['workflow']['revision'] != doc['revision'] or app['workflow']['lifecycle'] == 'withdrawn' or user.get('is_active') is False or str(user.get('email', '')).strip().lower() != doc['email']:
            self.db.company_messages.update_one(identity, {'$set': dict(state='cancelled', updated_at=now)}); return True
        if not self.db.company_messages.update_one(identity, {'$set': dict(state='dispatching', dispatch_started_at=now)}).matched_count: return True
        state = 'delivery_unknown'
        try:
            if sender(doc['email'], doc['subject'], '<p>'+escape(doc['message']).replace('\n', '<br>')+'</p>', doc['message']): state = 'sent'
        except Exception: pass
        self.db.company_messages.update_one({'_id': doc['_id'], 'lease_token': token, 'state': 'dispatching'}, {'$set': dict(state=state, updated_at=self.clock())})
        return True

    def reconcile_delivery(self, actor, message_id, disposition, reason, key):
        # Ambiguous delivery is never retried without provider-side evidence.
        if actor.get('user_type') != 'admin' or not ({'*', 'applications.write'} & set(actor.get('permissions', []))): raise WorkflowError('forbidden', 'Delivery reconciliation requires an administrator.', 403)
        operation_key(key)
        if disposition not in {'confirmed_sent', 'confirmed_not_sent'} or not isinstance(reason, str) or not 20 <= len(reason.strip()) <= 1000:
            raise WorkflowError('evidence_required', 'Record provider evidence and a confirmed delivery disposition.', 400)
        def change(session):
            identity = dict(actor_id=str(actor['_id']), key=key)
            fingerprint = request_identity(dict(message_id=message_id, disposition=disposition, reason=reason))
            old = self.db.company_actions.find_one(identity, session=session)
            if old:
                if old['fingerprint'] != fingerprint: raise WorkflowError('idempotency_conflict', 'Key reused.')
                return old['result']
            doc = self.db.company_messages.find_one({'_id': object_id(message_id)}, session=session)
            if not doc: raise WorkflowError('not_found', 'Message not found.', 404)
            if doc['state'] not in {'dispatching', 'delivery_unknown'} or (doc['state'] == 'dispatching' and utc(doc['lease_until']) > self.clock()):
                raise WorkflowError('delivery_locked', 'Only stale dispatch/unknown delivery can be reconciled.')
            state = 'sent' if disposition == 'confirmed_sent' else 'cancelled'
            self.db.company_messages.update_one({'_id': doc['_id']}, {'$set': dict(state=state, updated_at=self.clock())}, session=session)
            result = dict(state=state)
            self.db.company_actions.insert_one(dict(identity, fingerprint=fingerprint, result=result, reason=reason.strip(), message_id=message_id, created_at=self.clock()), session=session)
            return result
        return atomic(self.db, change)
