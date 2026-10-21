"""Versioned recruitment activation, qualification and scheduling.

All times are server times; accepted OA deadlines are independent of entry
cutoffs. Nothing here executes candidate code or assumes an available OA UI.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import math
import os
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from config.workflow import workflow_enabled, managed
from core.mongo_transactions import atomic
from models.hiring_workflow import WorkflowError, validate_stages, legacy_snapshot, projection, ATTEMPT_POLICY
from models.job_setup import pipeline_stages, validate_setup
from services.workflow_service import WorkflowService, operation_key, request_identity, public_workflow
from services.job_setup_service import JobSetupService, prices
from services.assessment_authoring_service import AssessmentAuthoringService, object_id


def utc(value):
    if isinstance(value, str): value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if not isinstance(value, datetime): raise WorkflowError('invalid_schedule', 'A valid stored schedule is required.', 503)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def now_utc(): return datetime.now(timezone.utc)


def scheduling_enabled():
    return workflow_enabled() and os.getenv('GENHIRE_SCHEDULING_ENABLED', 'false').lower() == 'true'


def ensure_progression_indexes(db):
    db.hiring_action_receipts.create_index([('actor_id', 1), ('operation_key', 1)], unique=True)
    db.hiring_activation_quotes.create_index('expires_at', expireAfterSeconds=86400)
    db.screening_result_events.create_index([('interview_id', 1), ('evidence_hash', 1)], unique=True)
    db.assessment_invitations.create_index([('application_id', 1), ('stage_id', 1)], unique=True)
    db.assessment_invitations.create_index([('state', 1), ('start_closes_at', 1)])
    db.assessment_attempts.create_index('invitation_id', unique=True)
    db.hiring_outbox.create_index('dedupe_key', unique=True)
    db.hiring_outbox.create_index([('state', 1), ('due_at', 1)])
    db.applications.create_index([('hiring_enrollment_version_id', 1), ('processing_status', 1)])


def qualification(document, policy, closes_at):
    """Missing/partial evidence always holds. Zero is a genuine score."""
    evaluation = document.get('evaluation') or {}
    def score(v): return type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 100
    value = document.get('interview_score', document.get('final_score'))
    proctor = document.get('proctoring_score')
    if document.get('status') == 'terminated': return 'review_required', 'monitoring_interrupted'
    if document.get('status') != 'completed': return 'pending', 'evaluation_pending'
    if evaluation.get('pending_answers') or evaluation.get('score_status') == 'pending':
        return 'pending', 'evaluation_pending'
    if evaluation.get('score_status') == 'partial': return 'review_required', 'interview_evidence_incomplete'
    finished = document.get('finished_at')
    if not finished: return 'review_required', 'finish_time_unavailable'
    if utc(finished) > utc(closes_at): return 'review_required', 'screening_finished_late'
    if not score(value) or evaluation.get('score_status') in {'unavailable', 'error'}:
        return 'review_required', 'interview_score_unavailable'
    if policy.get('require_proctoring') and (document.get('proctoring_status') != 'complete' or not score(proctor)):
        return 'review_required', 'proctoring_evidence_unavailable'
    minimum = policy.get('interview_minimum')
    if minimum is None: return 'review_required', 'recruiter_decision_required'
    if value < minimum: return 'not_cleared', 'interview_below_minimum'
    if policy.get('require_proctoring') and proctor < policy['proctoring_minimum']:
        return 'not_cleared', 'proctoring_below_minimum'
    return 'cleared', 'screening_thresholds_met'


class HiringProgressionService:
    # Step 5 must supply the real attempt runtime before HTTP start is exposed.
    candidate_runtime_ready = False

    def __init__(self, db, clock=now_utc):
        self.db, self.clock = db, clock
        self.workflow, self.setup = WorkflowService(db), JobSetupService(db)
        self._billing = None

    @property
    def billing(self):
        if self._billing is None:
            from payment_module.services.billing_operation_service import BillingOperationService
            self._billing = BillingOperationService(self.db)
        return self._billing

    @staticmethod
    def enabled():
        if not scheduling_enabled(): raise WorkflowError('scheduling_disabled', 'Hiring scheduling rollout is disabled.', 503)

    def mutation(self, actor, key, payload, callback):
        self.enabled(); self.setup.actor(actor, write=True)
        key = operation_key(key)
        identity = dict(actor_id=str(actor['_id']), operation_key=key)
        digest = request_identity(payload)
        def run(session):
            old = self.db.hiring_action_receipts.find_one(identity, session=session)
            if old:
                if old['request_hash'] != digest: raise WorkflowError('idempotency_conflict', 'Operation key reused with different details.')
                return old['result']
            result = callback(session)
            self.db.hiring_action_receipts.insert_one(dict(identity, request_hash=digest, result=result, created_at=self.clock()), session=session)
            return result
        try: return atomic(self.db, run)
        except DuplicateKeyError: return atomic(self.db, run)

    def version(self, version_id, session=None):
        version = self.db.hiring_workflow_versions.find_one({'_id': object_id(version_id)}, session=session)
        if not version or not version.get('setup_version_id'):
            raise WorkflowError('schedule_not_active', 'This workflow has no activated hiring schedule.')
        return version

    def outbox(self, app, kind, identity, due, session):
        self.db.hiring_outbox.update_one({'dedupe_key': identity}, {'$setOnInsert': dict(application_id=str(app['_id']),
            job_id=app['job_id'], recipient_id=app['student_id'], kind=kind, state='queued', due_at=due, created_at=self.clock())}, upsert=True, session=session)

    def write(self, app, workflow, action, key, reason, session, actor_id='system', fields=None):
        workflow['revision'] += 1
        result = dict(workflow_version_id=app['workflow_version_id'], revision=workflow['revision'], **projection(workflow))
        event = dict(application_id=str(app['_id']), job_id=app['job_id'], workflow_version_id=app['workflow_version_id'],
            revision=workflow['revision'], operation_key=key, action=action, actor_id=actor_id, reason=reason,
            occurred_at=self.clock(), result=result)
        self.workflow.repo.write_snapshot(app, workflow, dict(fields or {}, status=result['status'], workflow_label=result['workflow_label'], updated_at=self.clock()), event, session)
        return result

    def activation_quote(self, actor, job_id, assessment_version_id=None):
        self.enabled(); self.setup.actor(actor, write=True)
        job = self.setup.job(job_id, actor, True)
        version = self.db.job_setup_versions.find_one({'_id': object_id(job.get('hiring_setup_version_id'))})
        config = validate_setup(version['configuration'])
        from services.interview_flow_service import normalize_proctoring_config
        screening_proctoring = normalize_proctoring_config(job.get('proctoring_config'))
        p = prices()
        if config['pipeline']['oa_enabled'] and p['oa_attempt'] is None:
            raise WorkflowError('attempt_price_required', 'Configure the recruiter OA attempt price before activation.', 503)
        if config['pipeline']['oa_enabled']: self.check_integrity_features(version, actor)
        content_id = assessment_version_id if config['pipeline']['oa_enabled'] else None
        if content_id: self.checked_content(version, content_id, actor)
        elif config['pipeline']['oa_enabled']: raise WorkflowError('assessment_not_ready', 'Select published, reviewed assessment content.')
        funding = self.db.assessment_setup_funding.find_one({'_id': job_id})
        cost = config['pipeline']['oa_enabled'] and (not funding or funding['state'] != 'captured')
        # Existing generation hold carries its approved amount, not a newly invented price.
        amount = funding['credits'] if cost and funding and funding['state'] == 'reserved' else p['oa_setup'] if cost else 0
        quote = dict(_id=ObjectId(), actor_id=str(actor['_id']), owner_id=str(job['created_by']), job_id=job_id,
            setup_version_id=str(version['_id']), expected_workflow_revision=job.get('workflow_revision', 0),
            assessment_version_id=content_id, setup_credits=amount, attempt_credits=(p['oa_attempt'] + (p['dual_proctoring'] if config['oa']['proctoring_level'] == 'dual' else p['camera_proctoring'] if config['oa']['proctoring_level'] == 'camera' else 0)) if content_id else None,
            price_hash=request_identity(p), funding_state=(funding or {}).get('state'), funding_cycle=(funding or {}).get('cycle'),
            screening_proctoring_config=screening_proctoring,
            expires_at=self.clock()+timedelta(minutes=15), created_at=self.clock(), binding=True)
        self.db.hiring_activation_quotes.insert_one(quote)
        return JobSetupService.serialize(quote)

    def check_integrity_features(self, setup, actor, session=None):
        oa = setup['configuration']['oa']
        if oa['advanced_analytics'] or oa['plagiarism_check']:
            raise WorkflowError('optional_feature_unavailable', 'Enriched analytics remain unavailable. Similarity is a separate opt-in quoted report after evaluation.', 503)
        if oa['proctoring_level'] in {'camera', 'dual'} and not all(os.getenv(k, '').lower() == 'true' for k in ('GENHIRE_OA_INTEGRITY_ENABLED', 'GENHIRE_OA_MEDIA_ENABLED', 'GENHIRE_OA_MEDIA_ACCEPTED')):
            raise WorkflowError('optional_feature_unavailable', 'Camera capture/retention acceptance must pass before activation or charging.', 503)
        if oa['variant_count'] > 1:
            pool = self.db.assessment_variant_pools.find_one({'_id': str(setup['_id'])}, session=session)
            if os.getenv('GENHIRE_OA_VARIANTS_ENABLED', '').lower() != 'true' or not pool or len(pool['version_ids']) != oa['variant_count']:
                raise WorkflowError('validated_pool_required', 'Publish and approve the exact reviewed variant pool before activation.', 503)
            for identifier in pool['version_ids']: self.checked_content(setup, identifier, actor, session)

    def checked_content(self, setup, content_id, actor, session=None):
        content = self.db.assessment_versions.find_one({'_id': object_id(content_id), 'setup_version_id': str(setup['_id']),
            'owner_id': setup['owner_id'], 'state': 'published', 'pool': 'recruitment'}, session=session)
        if not content: raise WorkflowError('assessment_not_ready', 'Published content must belong to this exact job setup.')
        authoring = AssessmentAuthoringService(self.db)
        # Reapply Step 3 gates, including latest review and live profile, in this transaction.
        for reference in content['review_evidence']:
            q = self.db.question_versions.find_one({'_id': object_id(reference['question_version_id'])}, session=session)
            head = self.db.question_quality.find_one({'_id': q['_id']}, session=session) if q else None
            review = self.db.question_reviews.find_one({'_id': object_id(reference['review_id'])}, session=session)
            validation = self.db.question_validations.find_one({'_id': object_id(reference['validation_id'])}, session=session)
            if (not head or head.get('validation_id') != reference['validation_id'] or head.get('review_id') != reference['review_id']
                    or not review or review['decision'] != 'approve' or not validation or not validation['passed']):
                raise WorkflowError('review_required', 'Assessment approval has changed; validate/review and republish content.')
            if q['content']['type'] != 'mcq':
                capabilities = authoring.validator.capabilities()
                if not capabilities['available'] or validation['evidence'].get('execution_id') != capabilities['profile_hash']+':'+q['content_hash']:
                    raise WorkflowError('live_validation_required', 'Current real executor validation is required.', 503)
                if session:
                    changed = self.db.assessment_executor_attestations.update_one(dict(profile_hash=capabilities['profile_hash'], state='passed',
                        expires_at={'$gt': self.clock()}), {'$inc': {'activation_fence': 1}}, session=session)
                    if not changed.matched_count: raise WorkflowError('live_validation_required', 'Executor acceptance expired.', 503)
            if session: self.db.question_quality.update_one({'_id': q['_id']}, {'$inc': {'activation_fence': 1}}, session=session)
        return content

    def activate(self, actor, quote_id, key, accepted):
        if accepted is not True: raise WorkflowError('approval_required', 'Explicit activation quote approval is required.', 400)
        self.enabled(); self.setup.actor(actor, write=True)
        billing = self.billing  # Construct indexes outside the transaction.
        def activate(session):
            quote = self.db.hiring_activation_quotes.find_one({'_id': object_id(quote_id), 'actor_id': str(actor['_id'])}, session=session)
            if not quote: raise WorkflowError('not_found', 'Activation quote not found.', 404)
            job = self.setup.job(quote['job_id'], actor, True, session)
            if quote.get('result'): return quote['result']
            if utc(quote['expires_at']) <= self.clock(): raise WorkflowError('quote_expired', 'Preview a fresh activation quote.')
            if job.get('hiring_setup_version_id') != quote['setup_version_id'] or job.get('workflow_revision', 0) != quote['expected_workflow_revision']:
                raise WorkflowError('stale_revision', 'Job setup or active workflow changed; preview again.')
            if request_identity(prices()) != quote['price_hash']: raise WorkflowError('price_changed', 'Server prices changed; preview again.')
            setup = self.db.job_setup_versions.find_one({'_id': object_id(quote['setup_version_id'])}, session=session)
            config = setup['configuration']
            if config['pipeline']['oa_enabled']: self.check_integrity_features(setup, actor, session)
            control = self.db.assessment_generation_controls.find_one({'_id': quote['job_id']}, session=session) or {}
            if control.get('active_job_id'): raise WorkflowError('generation_busy', 'Finish generation or hold release before activation.')
            self.db.assessment_generation_controls.update_one({'_id': quote['job_id']}, {'$inc': {'activation_fence': 1}}, upsert=True, session=session)
            if job.get('status') not in {'draft', 'active'}:
                raise WorkflowError('job_not_active', 'Reopen this job explicitly before activating a new hiring version.')
            if job.get('status') != 'active' and utc(config['schedule']['application_closes_at']) <= self.clock():
                raise WorkflowError('application_window_closed', 'New hiring activation needs a future application closing date.')
            if quote['assessment_version_id']: self.checked_content(setup, quote['assessment_version_id'], actor, session)
            from services.interview_flow_service import normalize_proctoring_config
            screening_proctoring = normalize_proctoring_config(job.get('proctoring_config'))
            if screening_proctoring != quote['screening_proctoring_config']:
                raise WorkflowError('monitoring_changed', 'Screening monitoring changed; preview activation again.')
            if config['qualification']['require_proctoring'] and not any(screening_proctoring.values()):
                raise WorkflowError('required_proctoring_disabled', 'Enable required screening monitoring before activation.')
            funding = self.db.assessment_setup_funding.find_one({'_id': quote['job_id']}, session=session)
            if ((funding or {}).get('state') != quote['funding_state'] or (funding or {}).get('cycle') != quote['funding_cycle']):
                raise WorkflowError('funding_changed', 'Setup funding changed; preview again.')
            if quote['setup_credits']:
                if funding and funding['state'] == 'reserved':
                    billing_key = funding['key']
                else:
                    billing_key = 'oa-activation:' + str(quote['_id'])
                    billing.reserve(quote['owner_id'], 'recruiter', quote['setup_credits'], billing_key, 'oa_job_setup', session=session)
                billing.settle(quote['owner_id'], 'recruiter', billing_key, 'capture', session=session)
                self.db.assessment_setup_funding.update_one({'_id': quote['job_id']}, {'$set': dict(state='captured', key=billing_key,
                    credits=quote['setup_credits'], cycle=(funding or {}).get('cycle', 0), updated_at=self.clock())}, upsert=True, session=session)
            elif quote['assessment_version_id'] and (not funding or funding['state'] != 'captured'):
                self.db.assessment_setup_funding.update_one({'_id': quote['job_id']}, {'$set': dict(state='captured', key=None,
                    credits=0, cycle=(funding or {}).get('cycle', 0), updated_at=self.clock())}, upsert=True, session=session)
            revision = job.get('workflow_revision', 0)+1
            version = dict(_id=ObjectId(), job_id=quote['job_id'], owner_id=quote['owner_id'], revision=revision, schema_version=1,
                stages=validate_stages(pipeline_stages(config)), attempt_policy=deepcopy(ATTEMPT_POLICY), setup_version_id=str(setup['_id']),
                configuration=deepcopy(config), assessment_version_id=quote['assessment_version_id'], attempt_credits=quote['attempt_credits'],
                screening_proctoring_config=screening_proctoring,
                operation_key='activation:'+str(quote['_id']), created_by=str(actor['_id']), created_at=self.clock())
            self.db.hiring_workflow_versions.insert_one(version, session=session)
            self.db.jobs.update_one({'_id': job['_id']}, {'$set': dict(workflow_version_id=str(version['_id']), workflow_revision=revision,
                active_hiring_version_id=str(version['_id']), hiring_setup_status='active', status='active', deadline=config['schedule']['application_closes_at'])}, session=session)
            self.db.job_setup_versions.update_one({'_id': setup['_id']}, {'$set': {'status': 'active'}}, session=session)
            result = dict(version_id=str(version['_id']), workflow_revision=revision, setup_version_id=str(setup['_id']),
                assessment_version_id=quote['assessment_version_id'], setup_credits_captured=quote['setup_credits'], existing_applications_changed=0)
            self.db.hiring_activation_quotes.update_one({'_id': quote['_id']}, {'$set': {'result': result}}, session=session)
            return result
        return self.mutation(actor, key, dict(action='activate', quote_id=quote_id), activate)

    def enroll(self, application_id, actor=None, key=None, expected_revision=None):
        self.enabled()
        def enroll(session):
            app = self.workflow.repo.application(application_id, session)
            job = self.db.jobs.find_one({'_id': object_id(app['job_id'])}, session=session)
            if actor: self.workflow.access(app, actor, True, session)
            target = job.get('active_hiring_version_id') if actor else app.get('hiring_enrollment_version_id')
            version = self.version(target, session)
            if version['job_id'] != app['job_id']: raise WorkflowError('invalid_version', 'Wrong job workflow.')
            if managed(app) and app['workflow_version_id'] == target: return dict(enrolled=True, version_id=target, changed=False)
            if not actor and managed(app): return dict(enrolled=True, changed=False)
            if app.get('processing_status') not in {None, 'completed'}: raise WorkflowError('cv_processing', 'Complete application processing before enrollment.')
            if app.get('interview_start_lease') or self.db.interviews.find_one({'application_id': application_id,
                    'status': {'$in': ['setup', 'active', 'finishing', 'identity_blocked']}}, session=session):
                raise WorkflowError('active_screening', 'Cannot replace a workflow during screening.')
            if managed(app):
                if type(expected_revision) is not int or app['workflow']['revision'] != expected_revision:
                    raise WorkflowError('stale_revision', 'Refresh the current application revision.')
                if self.db.assessment_invitations.find_one({'application_id': application_id}, session=session):
                    raise WorkflowError('protected_invitation', 'Invited/downstream candidates retain their accepted version.')
                old_stage = next(s for s in app['workflow']['stages'] if s['stage_id'] == app['workflow']['current_stage_id'])
                if old_stage['type'] not in {'application_review', 'screening', 'oa'} or (old_stage['type'] == 'oa' and old_stage['state'] != 'eligible'):
                    raise WorkflowError('protected_stage', 'Downstream work cannot be rewritten.')
                if app['workflow']['lifecycle'] != 'active': raise WorkflowError('terminal_application', 'Application is not active.')
                snapshot = legacy_snapshot(app, version['stages'])
                # Preserve screening decisions and evidence; new policy must not retroactively clear/fail them.
                for stage in snapshot['stages']:
                    prior = next((s for s in app['workflow']['stages'] if s['stage_id'] == stage['stage_id'] and s['type'] in {'application_review', 'screening'}), None)
                    if prior: stage.update(deepcopy(prior))
                    if prior and prior['state'] == 'completed' and prior['outcome'] == 'cleared': stage['qualification_frozen'] = True
                snapshot.update(revision=app['workflow']['revision'], lifecycle='active', current_stage_id='screening' if old_stage['type'] in {'screening', 'oa'} else old_stage['stage_id'])
            else:
                snapshot = legacy_snapshot(app, version['stages'])
                snapshot['revision'] = -1
                if app.get('status') in {'screening_cleared', 'selected'}:
                    next(s for s in snapshot['stages'] if s['type'] == 'screening')['decision_source'] = 'recruiter'
            snapshot['provenance'] = 'hiring_enrollment'
            self.db.jobs.update_one({'_id': job['_id']}, {'$inc': {'enrollment_fence': 1}}, session=session)
            # write_snapshot checks old revision but writes the requested new version.
            app['workflow_version_id'] = target
            result = self.write(app, snapshot, 'enroll', 'enroll:'+target, 'Enrolled into an explicitly activated hiring version.', session,
                str(actor['_id']) if actor else 'system', dict(workflow_version_id=target, hiring_enrollment_version_id=target))
            self.extend_access(app['student_id'], utc(version['configuration']['schedule']['screening_closes_at'])+timedelta(days=1), session)
            return dict(enrolled=True, changed=True, **result)
        if actor:
            return self.mutation(actor, key, dict(action='enroll', application_id=application_id, revision=expected_revision), enroll)
        try: return atomic(self.db, enroll)
        except DuplicateKeyError: return atomic(self.db, enroll)

    def screening_start(self, application, candidate_id):
        if application.get('hiring_enrollment_version_id') and not managed(application):
            self.enroll(str(application['_id'])); application = self.workflow.repo.application(str(application['_id']))
        if not managed(application): return None
        self.enabled()
        if application.get('student_id') != str(candidate_id): raise WorkflowError('forbidden', 'Wrong candidate.', 403)
        version = self.version(application['workflow_version_id'])
        stage = next(s for s in application['workflow']['stages'] if s['stage_id'] == application['workflow']['current_stage_id'])
        schedule = version['configuration']['schedule']
        now = self.clock()
        if application['workflow']['lifecycle'] != 'active' or stage['type'] != 'screening' or stage['state'] not in {'eligible', 'in_progress'}:
            raise WorkflowError('interview_not_eligible', 'Screening is not the current eligible stage.')
        if not utc(schedule['screening_opens_at']) <= now < utc(schedule['screening_closes_at']):
            raise WorkflowError('screening_window_closed', 'Screening must start and finish within its hiring window.')
        return dict(version_id=str(version['_id']), revision=application['workflow']['revision'], closes_at=schedule['screening_closes_at'])

    def ingest_screening(self, interview_id):
        self.enabled()
        def ingest(session):
            doc = self.db.interviews.find_one({'_id': object_id(interview_id)}, session=session)
            if not doc or not doc.get('application_id') or doc.get('is_practice'): return dict(ignored=True)
            app = self.workflow.repo.application(doc['application_id'], session)
            if not managed(app): return dict(ignored=True)
            version = self.version(app['workflow_version_id'], session)
            if doc.get('workflow_version_id') and doc['workflow_version_id'] != app['workflow_version_id']: return dict(ignored=True)
            if str(doc.get('user_id')) != app['student_id']: raise WorkflowError('forbidden', 'Screening candidate mismatch.', 403)
            def safe_score(value): return value if type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 100 else None
            evidence = {k: doc.get(k) for k in ('status', 'proctoring_status')}
            evidence.update({k: safe_score(doc.get(k)) for k in ('final_score', 'interview_score', 'proctoring_score')})
            evidence.update(score_status=(doc.get('evaluation') or {}).get('score_status'), pending=bool((doc.get('evaluation') or {}).get('pending_answers')))
            evidence['finished_at'] = utc(doc['finished_at']).isoformat() if doc.get('finished_at') else None
            digest = request_identity(evidence)
            identity = dict(interview_id=interview_id, evidence_hash=digest)
            if self.db.screening_result_events.find_one(identity, session=session): return dict(replayed=True)
            workflow = deepcopy(app['workflow'])
            stage = next(s for s in workflow['stages'] if s['type'] == 'screening')
            current = next(s for s in workflow['stages'] if s['stage_id'] == workflow['current_stage_id'])
            if workflow['lifecycle'] != 'active' or current['type'] not in {'screening'}: return dict(ignored=True)
            if stage.get('decision_source') == 'recruiter' or stage.get('qualification_frozen'): return dict(ignored=True)
            policy = next(s['policy'] for s in version['stages'] if s['type'] == 'screening')
            outcome, reason = qualification(doc, policy, version['configuration']['schedule']['screening_closes_at'])
            if outcome == 'pending': state = 'evaluating'
            else: state = 'completed'
            stage.update(state=state, outcome='pending' if outcome == 'pending' else outcome, decision_source='screening_policy',
                result_interview_id=interview_id, evidence_hash=digest, reason=reason)
            score = doc.get('interview_score', doc.get('final_score'))
            fields = dict(interview_score=score if type(score) in (int, float) and math.isfinite(score) and 0 <= score <= 100 else None,
                proctoring_score=safe_score(doc.get('proctoring_score')), proctoring_status=doc.get('proctoring_status'), screening_result_reason=reason)
            result = self.write(app, workflow, 'screening_result', 'screening:'+request_identity(identity), reason, session, fields=fields)
            self.db.screening_result_events.insert_one(dict(identity, application_id=doc['application_id'], outcome=outcome, reason=reason, created_at=self.clock()), session=session)
            if outcome != 'pending': self.outbox(app, 'screening_result', 'screening-result:'+doc['application_id']+':'+digest, self.clock(), session)
            return result
        try: return atomic(self.db, ingest)
        except DuplicateKeyError: return atomic(self.db, ingest)

    def invite(self, actor, application_id, expected_revision, key, reason):
        if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 1000: raise WorkflowError('reason_required', 'Document the invitation reason.', 400)
        def invite(session):
            app = self.workflow.repo.application(application_id, session)
            self.workflow.access(app, actor, True, session)
            return self.invite_in_session(app, session, expected_revision, str(actor['_id']), key, reason)
        return self.mutation(actor, key, dict(action='invite', application_id=application_id, revision=expected_revision, reason=reason), invite)

    def invite_in_session(self, app, session, expected_revision, actor_id, key, reason):
        old = self.db.assessment_invitations.find_one({'application_id': str(app['_id'])}, session=session)
        if old: return dict(invitation_id=str(old['_id']), state=old['state'], replayed=True)
        if not managed(app) or app['workflow']['revision'] != expected_revision: raise WorkflowError('stale_revision', 'Refresh the application revision.')
        workflow = deepcopy(app['workflow'])
        if workflow['lifecycle'] != 'active': raise WorkflowError('terminal_application', 'Application is not active.')
        screening = next(s for s in workflow['stages'] if s['type'] == 'screening')
        stage = next((s for s in workflow['stages'] if s['type'] == 'oa' and s['enabled']), None)
        current = next(s for s in workflow['stages'] if s['stage_id'] == workflow['current_stage_id'])
        if screening['state'] != 'completed' or screening['outcome'] != 'cleared' or not stage or stage['state'] not in {'not_ready', 'eligible'} or current['type'] not in {'screening', 'oa'}:
            raise WorkflowError('screening_not_cleared', 'A completed cleared screening and an uninvited OA stage are required.')
        version = self.version(app['workflow_version_id'], session)
        job = self.db.jobs.find_one({'_id': object_id(app['job_id'])}, session=session)
        if not job or job.get('status') != 'active': raise WorkflowError('job_not_active', 'This job is not open for new assessment invitations.')
        schedule = version['configuration']['schedule']
        schedule = dict(schedule, **self.window(version, session))
        if not version.get('assessment_version_id'): raise WorkflowError('assessment_not_ready', 'No activated assessment content.')
        if utc(schedule['oa_start_closes_at']) <= self.clock(): raise WorkflowError('oa_entry_closed', 'OA entry has closed; explicitly reschedule before inviting.')
        manual_open = self.db.oa_window_activations.find_one({'_id': app['workflow_version_id']}, session=session)
        if schedule['oa_activation'] == 'manual' and (manual_open or {}).get('opened') is not True:
            raise WorkflowError('oa_not_opened', 'Recruiter must explicitly open this OA cohort.')
        invitation = dict(_id=ObjectId(), application_id=str(app['_id']), job_id=app['job_id'], candidate_id=app['student_id'], stage_id=stage['stage_id'],
            workflow_version_id=app['workflow_version_id'], assessment_version_id=version['assessment_version_id'], state='invited', revision=1,
            opens_at=utc(schedule['oa_opens_at']), start_closes_at=utc(schedule['oa_start_closes_at']), duration_minutes=version['configuration']['oa']['duration_minutes'],
            attempt_credits=version['attempt_credits'], created_at=self.clock(), created_by=actor_id)
        pool = self.db.assessment_variant_pools.find_one({'_id': version['setup_version_id']}, session=session)
        if pool:
            import secrets
            counts = pool['allocation_counts']; minimum = min(counts)
            index = secrets.choice([i for i, count in enumerate(counts) if count == minimum])
            setup = self.db.job_setup_versions.find_one({'_id': object_id(version['setup_version_id'])}, session=session)
            self.checked_content(setup, pool['version_ids'][index], None, session)
            invitation.update(assessment_version_id=pool['version_ids'][index], variant_pool_id=pool['_id'], variant_index=index)
            self.db.assessment_variant_pools.update_one({'_id': pool['_id']}, {'$inc': {f'allocation_counts.{index}': 1}}, session=session)
        self.db.assessment_invitations.insert_one(invitation, session=session)
        stage.update(state='invited', outcome='pending', invitation_id=str(invitation['_id']))
        workflow['current_stage_id'] = stage['stage_id']
        self.write(app, workflow, 'oa_invited', 'oa-invite:'+str(invitation['_id']), reason, session, actor_id)
        self.extend_access(app['student_id'], invitation['start_closes_at']+timedelta(minutes=invitation['duration_minutes']), session)
        self.outbox(app, 'oa_invitation', 'oa-invitation:'+str(invitation['_id']), self.clock(), session)
        self.outbox(app, 'oa_reminder', 'oa-reminder:'+str(invitation['_id'])+':1', max(self.clock(), invitation['start_closes_at']-timedelta(hours=4)), session)
        return dict(invitation_id=str(invitation['_id']), state='invited', replayed=False)

    def extend_access(self, candidate_id, until, session):
        # Extending account access does not extend any stage deadline.
        self.db.users.update_one({'_id': object_id(candidate_id), 'is_invite_only': True}, {'$max': {'access_expires_at': until}}, session=session)

    def invitation(self, actor, invitation_id):
        value = self.db.assessment_invitations.find_one({'_id': object_id(invitation_id)})
        if not value: raise WorkflowError('not_found', 'Invitation not found.', 404)
        app = self.workflow.repo.application(value['application_id'])
        self.workflow.access(app, actor)
        return dict(invitation_id=str(value['_id']), application_id=value['application_id'], job_id=value['job_id'], state=value['state'], revision=value['revision'],
            opens_at=utc(value['opens_at']).isoformat(), start_closes_at=utc(value['start_closes_at']).isoformat(), duration_minutes=value['duration_minutes'],
            attempt_deadline=utc(value['attempt_deadline']).isoformat() if value.get('attempt_deadline') else None, runtime_ready=self.candidate_runtime_ready)

    def accept(self, actor, invitation_id, key):
        self.enabled(); operation_key(key)
        if not self.candidate_runtime_ready: raise WorkflowError('oa_runtime_not_ready', 'The candidate OA workspace is not enabled yet.', 503)
        if actor.get('user_type') not in {'candidate', 'student'}: raise WorkflowError('forbidden', 'Only the invited candidate can start.', 403)
        billing = self.billing
        def accept(session):
            invitation = self.db.assessment_invitations.find_one({'_id': object_id(invitation_id), 'candidate_id': str(actor['_id'])}, session=session)
            if not invitation: raise WorkflowError('not_found', 'Invitation not found.', 404)
            app = self.workflow.repo.application(invitation['application_id'], session)
            if app['workflow']['lifecycle'] != 'active': raise WorkflowError('terminal_application', 'Application is not active.')
            old = self.db.assessment_attempts.find_one({'invitation_id': invitation_id}, session=session)
            if old: return dict(attempt_id=str(old['_id']), deadline=utc(old['deadline']).isoformat(), replayed=True)
            job = self.db.jobs.find_one({'_id': object_id(app['job_id'])}, session=session)
            if not job or job.get('status') != 'active': raise WorkflowError('job_not_active', 'This job is not accepting new OA attempts.')
            now = self.clock()
            if invitation['state'] != 'invited' or not utc(invitation['opens_at']) <= now < utc(invitation['start_closes_at']):
                raise WorkflowError('oa_entry_closed', 'New OA attempts require an open invitation window.')
            version = self.version(invitation['workflow_version_id'], session)
            owner_id = version['owner_id']; amount = invitation['attempt_credits']
            if type(amount) is not int or amount < 0: raise WorkflowError('attempt_price_required', 'A valid accepted attempt price is required.', 503)
            billing_key = 'oa-attempt:'+invitation_id
            attempt = dict(_id=ObjectId(), invitation_id=invitation_id, application_id=invitation['application_id'], candidate_id=str(actor['_id']),
                assessment_version_id=invitation['assessment_version_id'], workflow_version_id=invitation['workflow_version_id'], state='in_progress',
                started_at=now, deadline=now+timedelta(minutes=invitation['duration_minutes']), billing_key=billing_key if amount else None,
                owner_id=owner_id, credits=amount, revision=0)
            prepare = getattr(self, 'prepare_attempt', None)
            if prepare: prepare(attempt, invitation, session, actor=actor)
            # Validate/read the immutable workspace before taking the shared
            # recruiter wallet's write lock. Reservation and accepted attempt
            # still commit atomically; invalid content never holds that lock.
            if amount: billing.reserve(owner_id, 'recruiter', amount, billing_key, 'oa_candidate_attempt', session=session)
            self.db.assessment_attempts.insert_one(attempt, session=session)
            self.db.assessment_invitations.update_one({'_id': invitation['_id']}, {'$set': {'state': 'accepted', 'attempt_deadline': attempt['deadline'],
                'attempt_id': str(attempt['_id'])}, '$inc': {'revision': 1}}, session=session)
            workflow = deepcopy(app['workflow']); stage = next(s for s in workflow['stages'] if s['type'] == 'oa')
            stage.update(state='in_progress', attempt_id=str(attempt['_id']))
            self.write(app, workflow, 'oa_started', 'oa-start:'+invitation_id, 'Candidate accepted the timed attempt.', session, str(actor['_id']))
            self.extend_access(str(actor['_id']), attempt['deadline']+timedelta(days=1), session)
            return dict(attempt_id=str(attempt['_id']), deadline=attempt['deadline'].isoformat(), replayed=False)
        try: result = atomic(self.db, accept, contention_backoff=True)
        except DuplicateKeyError: result = atomic(self.db, accept, contention_backoff=True)
        # A four-hour invite handoff token must not cut short a valid five-hour
        # OA. Keep the same user permissions and bound refresh to this deadline.
        import jwt
        from core.security import get_jwt_secret
        expiry = utc(result['deadline'])+timedelta(minutes=15)
        result['access_token'] = jwt.encode(dict(user_id=str(actor['_id']), exp=expiry), get_jwt_secret(), algorithm='HS256')
        return result

    def window(self, version, session=None):
        override = self.db.oa_window_activations.find_one({'_id': str(version['_id'])}, session=session) or {}
        return {k: override[k] for k in ('oa_opens_at', 'oa_start_closes_at') if k in override}

    def change_window(self, actor, version_id, key, reason, expected_revision=0, opens_at=None, closes_at=None):
        if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 1000: raise WorkflowError('reason_required', 'Document the window change.', 400)
        if type(expected_revision) is not int or expected_revision < 0: raise WorkflowError('invalid_revision', 'Provide the current window revision.', 400)
        reschedule = opens_at is not None or closes_at is not None
        if reschedule:
            for value in (opens_at, closes_at):
                try: parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
                except (ValueError, TypeError, AttributeError): raise WorkflowError('invalid_schedule', 'Use timezone-aware ISO dates.', 400) from None
                if parsed.tzinfo is None: raise WorkflowError('invalid_schedule', 'Use timezone-aware ISO dates.', 400)
            opening, closing = utc(opens_at), utc(closes_at)
            if closing <= max(opening, self.clock()) or closing-opening > timedelta(days=7):
                raise WorkflowError('invalid_schedule', 'Choose a future entry close after opening, with at most seven days to enter.', 400)
        def change(session):
            version = self.version(version_id, session)
            self.setup.job(version['job_id'], actor, True, session)
            previous = self.db.oa_window_activations.find_one({'_id': version_id}, session=session) or {}
            if previous.get('revision', 0) != expected_revision: raise WorkflowError('stale_revision', 'OA window changed; refresh before retrying.')
            if not version.get('assessment_version_id'): raise WorkflowError('assessment_not_ready', 'This hiring version has no activated OA.')
            if reschedule and opening < utc(version['configuration']['schedule']['screening_closes_at']):
                raise WorkflowError('invalid_schedule', 'OA cannot open before the screening window closes.', 400)
            values = dict(revision=expected_revision+1, updated_by=str(actor['_id']), updated_at=self.clock())
            if reschedule: values.update(oa_opens_at=opening, oa_start_closes_at=closing)
            else: values['opened'] = True
            self.db.oa_window_activations.update_one({'_id': version_id}, {'$set': values}, upsert=True, session=session)
            self.db.hiring_window_events.insert_one(dict(workflow_version_id=version_id, actor_id=str(actor['_id']), reason=reason.strip(),
                previous=previous, change=values, created_at=self.clock()), session=session)
            changed = 0
            if reschedule:
                if self.db.assessment_invitations.count_documents({'workflow_version_id': version_id, 'state': {'$in': ['invited', 'expired']}}, session=session) > 500:
                    raise WorkflowError('cohort_limit', 'The pilot supports rescheduling at most 500 unstarted invitations per window.', 429)
                # Accepted attempts are deliberately excluded, regardless of their deadline.
                for invitation in self.db.assessment_invitations.find({'workflow_version_id': version_id, 'state': {'$in': ['invited', 'expired']}}, session=session):
                    app = self.workflow.repo.application(invitation['application_id'], session)
                    if app['workflow']['lifecycle'] != 'active': continue
                    self.db.hiring_outbox.update_many({'application_id': invitation['application_id'],
                        'kind': {'$in': ['oa_invitation', 'oa_reminder', 'oa_rescheduled']}, 'state': {'$in': ['queued', 'preparing']}},
                        {'$set': {'state': 'cancelled', 'cancel_reason': 'rescheduled'}}, session=session)
                    self.db.assessment_invitations.update_one({'_id': invitation['_id']}, {'$set': {'opens_at': opening, 'start_closes_at': closing, 'state': 'invited'},
                        '$inc': {'revision': 1}}, session=session)
                    wf = deepcopy(app['workflow']); stage = next(s for s in wf['stages'] if s['type'] == 'oa')
                    stage.update(state='invited', outcome='pending')
                    self.write(app, wf, 'oa_rescheduled', 'oa-reschedule:'+str(invitation['_id'])+':'+str(expected_revision+1), reason, session, str(actor['_id']))
                    self.extend_access(invitation['candidate_id'], closing+timedelta(minutes=invitation['duration_minutes']), session)
                    self.outbox(app, 'oa_rescheduled', 'oa-rescheduled:'+str(invitation['_id'])+':'+str(expected_revision+1), self.clock(), session)
                    self.outbox(app, 'oa_reminder', 'oa-reminder:'+str(invitation['_id'])+':'+str(invitation['revision']+1), max(self.clock(), closing-timedelta(hours=4)), session)
                    changed += 1
            return dict(window_revision=values['revision'], unstarted_invitations_changed=changed, active_attempts_changed=0)
        return self.mutation(actor, key, dict(action='change_window', version=version_id, revision=expected_revision,
            opens_at=opens_at, closes_at=closes_at, reason=reason), change)

    def automatic_invite(self, application_id):
        self.enabled()
        def invite(session):
            app = self.workflow.repo.application(application_id, session)
            version = self.version(app['workflow_version_id'], session)
            policy = next(s['policy'] for s in version['stages'] if s['type'] == 'screening')
            if not policy.get('auto_invite') or not version.get('assessment_version_id'): return dict(ignored=True)
            owner = self.db.users.find_one({'_id': object_id(version['owner_id'])}, session=session)
            if not owner or owner.get('is_verified') is not True or owner.get('is_active') is False:
                raise WorkflowError('verification_required', 'Automatic invitations require an active verified recruiter.', 403)
            return self.invite_in_session(app, session, app['workflow']['revision'], 'system:auto', 'auto-invite:'+application_id, 'Recruiter opted into automatic OA invitations.')
        try: return atomic(self.db, invite)
        except DuplicateKeyError: return atomic(self.db, invite)

    def expire_invitation(self, invitation_id):
        self.enabled()
        def expire(session):
            invitation = self.db.assessment_invitations.find_one({'_id': object_id(invitation_id)}, session=session)
            if not invitation or invitation.get('pool') == 'practice' or invitation['state'] != 'invited' or utc(invitation['start_closes_at']) > self.clock(): return False
            app = self.workflow.repo.application(invitation['application_id'], session)
            # Both start and expiry mutate this invitation, preventing an accepted-start race.
            self.db.assessment_invitations.update_one({'_id': invitation['_id']}, {'$set': {'state': 'expired'}, '$inc': {'revision': 1}}, session=session)
            if app['workflow']['lifecycle'] == 'active':
                wf = deepcopy(app['workflow']); stage = next(s for s in wf['stages'] if s['type'] == 'oa')
                stage.update(state='expired', outcome='pending')
                self.write(app, wf, 'oa_entry_expired', 'oa-expire:'+invitation_id+':'+str(invitation['revision']), 'OA was not started before the entry cutoff.', session)
            return True
        return atomic(self.db, expire)

    def progress(self, actor, application_id):
        app = self.workflow.repo.application(application_id)
        self.workflow.access(app, actor)
        invitation = self.db.assessment_invitations.find_one({'application_id': application_id})
        version = self.version(app['workflow_version_id']) if managed(app) and self.db.hiring_workflow_versions.find_one({'_id': object_id(app['workflow_version_id']), 'setup_version_id': {'$exists': True}}) else None
        schedule = version['configuration']['schedule'] if version else None
        return dict(application_id=application_id, workflow=public_workflow(app),
            schedule=JobSetupService.serialize(dict(schedule, **self.window(version))) if schedule else None,
            invitation=self.invitation(actor, str(invitation['_id'])) if invitation else None,
            screening_result_reason=app.get('screening_result_reason'), scheduling_enabled=scheduling_enabled())

    def expire_screening(self, application_id):
        self.enabled()
        def expire(session):
            app = self.workflow.repo.application(application_id, session)
            wf = deepcopy(app['workflow'])
            stage = next(s for s in wf['stages'] if s['stage_id'] == wf['current_stage_id'])
            if wf['lifecycle'] != 'active' or stage['type'] != 'screening' or stage['state'] in {'completed', 'expired', 'evaluating'}: return False
            version = self.version(app['workflow_version_id'], session)
            close = utc(version['configuration']['schedule']['screening_closes_at'])
            if self.clock() < close: return False
            doc = self.db.interviews.find_one({'application_id': application_id, 'status': {'$in': ['finishing', 'completed']}}, sort=[('_id', -1)], session=session)
            if doc and doc.get('finished_at') and utc(doc['finished_at']) <= close:
                stage.update(state='evaluating', outcome='pending', reason='evaluation_pending')
            else: stage.update(state='expired', outcome='review_required', reason='screening_window_expired')
            self.write(app, wf, 'screening_window_closed', 'screening-close:'+str(version['_id']), stage['reason'], session)
            return True
        return atomic(self.db, expire)

    def screening_notices(self, application_id):
        self.enabled()
        def queue(session):
            app = self.workflow.repo.application(application_id, session)
            version = self.version(app['workflow_version_id'], session)
            stage = next(s for s in app['workflow']['stages'] if s['stage_id'] == app['workflow']['current_stage_id'])
            if app['workflow']['lifecycle'] != 'active' or stage['type'] != 'screening' or stage['state'] not in {'eligible', 'in_progress'}: return
            schedule = version['configuration']['schedule']; close = utc(schedule['screening_closes_at'])
            if close <= self.clock(): return
            for kind, due in [('screening_invitation', self.clock()), ('screening_reminder', max(self.clock(), close-timedelta(hours=24)))]:
                self.outbox(app, kind, kind+':'+application_id+':'+str(version['_id']), due, session)
        return atomic(self.db, queue)

    def persist_screening_session(self, application_id, candidate_id, document):
        self.enabled()
        def save(session):
            app = self.workflow.repo.application(application_id, session)
            version = self.version(app['workflow_version_id'], session)
            wf = deepcopy(app['workflow']); stage = next(s for s in wf['stages'] if s['stage_id'] == wf['current_stage_id'])
            close = utc(version['configuration']['schedule']['screening_closes_at'])
            if app['student_id'] != str(candidate_id) or wf['lifecycle'] != 'active' or stage['type'] != 'screening' or stage['state'] not in {'eligible', 'in_progress'}:
                raise WorkflowError('interview_not_eligible', 'Application eligibility changed during setup.')
            if self.clock() >= close: raise WorkflowError('screening_window_closed', 'Screening closed during setup.')
            if self.db.interviews.find_one({'application_id': application_id, 'status': {'$in': ['setup', 'active', 'finishing', 'completed', 'terminated']}}, session=session):
                raise WorkflowError('interview_already_started', 'A screening attempt already exists.')
            document.update(workflow_version_id=app['workflow_version_id'], screening_finish_by=close)
            result = self.db.interviews.insert_one(document, session=session)
            stage.update(state='in_progress', result_interview_id=str(result.inserted_id))
            self.write(app, wf, 'screening_started', 'screening-start:'+str(result.inserted_id), 'Candidate started screening within the hiring window.', session, str(candidate_id))
            self.extend_access(str(candidate_id), close+timedelta(days=1), session)
            return result.inserted_id
        return atomic(self.db, save)


def sync_completed_screening(collection, interview_id):
    """Best-effort immediate adapter; the durable scheduler rescans saved evidence."""
    if not scheduling_enabled(): return
    if collection.name != 'interviews': return
    try:
        result = HiringProgressionService(collection.database).ingest_screening(str(interview_id))
        if not result.get('ignored') and not result.get('replayed'):
            doc = collection.find_one({'_id': object_id(interview_id)}, {'application_id': 1})
            if doc: notify_hiring_progress(collection.database, doc['application_id'])
    except Exception:
        import logging
        logging.getLogger(__name__).warning('Screening progression deferred to the durable scheduler.')


def sync_application_enrollment(collection, application_id):
    if not scheduling_enabled(): return
    try:
        app = collection.find_one({'_id': object_id(application_id)})
        if app and app.get('hiring_enrollment_version_id') and not managed(app):
            HiringProgressionService(collection.database).enroll(application_id)
    except Exception:
        import logging
        logging.getLogger(__name__).warning('Hiring enrollment deferred to the durable scheduler.')


def application_timing(db, app):
    """Small candidate-safe schedule projection, independent of rollout flag."""
    version_id = app.get('workflow_version_id') or app.get('hiring_enrollment_version_id')
    if not version_id: return None
    version = db.hiring_workflow_versions.find_one({'_id': object_id(version_id)})
    if not version or not version.get('configuration'): return None
    schedule = version['configuration']['schedule']
    return {k: schedule[k] for k in ('timezone', 'screening_opens_at', 'screening_closes_at')}


def notify_hiring_progress(db, application_id):
    """Refresh hint after commit; failures cannot undo authoritative storage."""
    try:
        from core.extensions import socketio
        app = db.applications.find_one({'_id': object_id(application_id)})
        if not app: return
        payload = {k: app.get(k) for k in ('job_id', 'status', 'workflow_version_id', 'workflow_label', 'workflow', 'interview_score', 'proctoring_score', 'proctoring_status')}
        payload['_id'] = application_id
        payload['hiring_enrollment_version_id'] = app.get('hiring_enrollment_version_id')
        payload['hiring_timing'] = application_timing(db, app)
        for room in {app.get('student_id'), app.get('recruiter_id')} - {None, ''}:
            socketio.emit('application_update', {'type': 'status_changed', 'application': payload}, room=str(room))
    except Exception: pass
