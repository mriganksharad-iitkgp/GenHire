"""Immutable-submission evaluation, lease fencing and atomic result settlement."""
from copy import deepcopy
from datetime import timedelta
import os
from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import PyMongoError
from core.mongo_transactions import atomic
from models.assessment_content import validate_question, blueprint_match
from models.hiring_workflow import WorkflowError
from services.assessment_authoring_service import object_id
from services.assessment_execution_service import AssessmentExecutionService, ensure_execution_indexes
from services.assessment_scoring import fixtures, score
from services.hiring_progression_service import utc
from services.workflow_service import operation_key, request_identity


def ensure_evaluation_indexes(db):
    ensure_execution_indexes(db)
    db.assessment_evaluation_jobs.create_index('attempt_id', unique=True)
    db.assessment_evaluation_jobs.create_index([('state', 1), ('next_attempt_at', 1), ('lease_until', 1)])
    db.assessment_evaluation_reports.create_index('attempt_id', unique=True)
    db.assessment_evaluation_actions.create_index([('actor_id', 1), ('key', 1)], unique=True)
    db.assessment_submissions.create_index([('state', 1), ('recorded_at', 1)])


def grading_case_limit():
    try: limit = int(os.getenv('GENHIRE_OA_GRADING_CASE_LIMIT', '200'))
    except ValueError: limit = 0
    if not 1 <= limit <= 400: raise WorkflowError('invalid_case_limit', 'Grading case limit must be 1–400.', 503)
    return limit


class AssessmentEvaluationService:
    def __init__(self, runtime):
        self.runtime, self.db, self.clock = runtime, runtime.db, runtime.clock
        self.execution = AssessmentExecutionService(self.db, self.clock)

    def content(self, attempt, submission, session=None):
        if submission['assessment_version_id'] != attempt['assessment_version_id'] or submission['content_hash'] != request_identity(submission['answers']):
            raise WorkflowError('submission_changed', 'Immutable submission identity changed.', 503)
        version = self.db.assessment_versions.find_one({'_id': object_id(attempt['assessment_version_id']), 'state': 'published'}, session=session)
        bindings = attempt.get('question_bindings', [])
        if not version or version.get('pool', 'recruitment') != attempt.get('pool', 'recruitment') or [b['question_version_id'] for b in bindings] != version['question_version_ids'] or request_identity(version['configuration']) != request_identity(attempt['configuration']):
            raise WorkflowError('content_changed', 'Pinned content/configuration does not match publication.', 503)
        questions = {}
        for binding in bindings:
            record = self.db.question_versions.find_one({'_id': object_id(binding['question_version_id']), 'pool': attempt.get('pool', 'recruitment'), 'owner_id': attempt['owner_id']}, session=session)
            if not record or record['content_hash'] != binding['content_hash'] or request_identity(record['content']) != binding['content_hash']:
                raise WorkflowError('content_changed', 'Pinned question hash no longer matches.', 503)
            questions[binding['question_version_id']] = validate_question(record['content'])
        blueprint_match(attempt['configuration'], list(questions.values()))
        if set(submission['answers']) - set(questions): raise WorkflowError('invalid_submission', 'Submission contains an unexpected question.', 503)
        for identifier, answer in submission['answers'].items(): self.runtime.answer(questions[identifier], answer)
        if sum(len(fixtures(q)) for q in questions.values()) > grading_case_limit(): raise WorkflowError('grading_case_limit', 'Assessment exceeds the configured grading budget.', 503)
        return questions

    def enqueue(self, submission_id):
        def create(session):
            submission = self.db.assessment_submissions.find_one({'_id': object_id(submission_id)}, session=session)
            if not submission: raise WorkflowError('not_found', 'Submission not found.', 404)
            old = self.db.assessment_evaluation_jobs.find_one({'_id': submission['_id']}, session=session)
            if old: return old
            attempt = self.db.assessment_attempts.find_one({'_id': object_id(submission['attempt_id'])}, session=session)
            questions = self.content(attempt, submission, session)
            job = dict(_id=submission['_id'], attempt_id=submission['attempt_id'], state='queued', next_attempt_at=self.clock(),
                lease_until=self.clock(), created_at=self.clock(), failures=0, question_ids=list(questions),
                input_hash=request_identity(dict(answers=submission['answers'], bindings=attempt['question_bindings'], configuration=attempt['configuration'], policy='oa-score-v1')))
            self.db.assessment_evaluation_jobs.insert_one(job, session=session)
            self.db.assessment_submissions.update_one({'_id': submission['_id']}, {'$set': {'state': 'evaluating'}}, session=session)
            self.db.assessment_attempts.update_one({'_id': attempt['_id']}, {'$set': {'state': 'evaluating'}}, session=session)
            if attempt.get('pool') == 'practice': self.runtime.practice_state(attempt, 'evaluating', session)
            else:
                app = self.runtime.workflow.repo.application(attempt['application_id'], session)
                workflow = deepcopy(app['workflow']); next(s for s in workflow['stages'] if s['type'] == 'oa')['state'] = 'evaluating'
                self.runtime.write(app, workflow, 'oa_evaluating', 'oa-evaluate:'+submission['attempt_id'], 'Submitted answers queued for objective evaluation.', session)
            return job
        return atomic(self.db, create)

    def reconcile(self, limit=50):
        for submission in self.db.assessment_submissions.find({'state': 'awaiting_evaluator'}).sort('recorded_at', 1).limit(limit):
            try: self.enqueue(str(submission['_id']))
            except PyMongoError: raise
            except Exception as exc:
                # A corrupt/oversized submission must not starve every later cohort.
                self.db.assessment_submissions.update_one({'_id': submission['_id'], 'state': 'awaiting_evaluator'},
                    {'$set': {'state': 'needs_review', 'error_code': exc.code if isinstance(exc, WorkflowError) else 'invalid_submission'}})

    def claim(self):
        now = self.clock()
        return self.db.assessment_evaluation_jobs.find_one_and_update({'state': {'$in': ['queued', 'waiting', 'blocked']},
            'next_attempt_at': {'$lte': now}, 'lease_until': {'$lte': now}},
            {'$set': {'lease_token': str(ObjectId()), 'lease_until': now+timedelta(seconds=60)}},
            sort=[('next_attempt_at', 1), ('_id', 1)], return_document=ReturnDocument.AFTER)

    def heartbeat(self, job):
        return self.db.assessment_evaluation_jobs.update_one({'_id': job['_id'], 'lease_token': job['lease_token'], 'lease_until': {'$gt': self.clock()}},
            {'$set': {'lease_until': self.clock()+timedelta(seconds=60)}}).matched_count == 1

    def process(self, job):
        attempt = self.db.assessment_attempts.find_one({'_id': object_id(job['attempt_id'])})
        submission = self.db.assessment_submissions.find_one({'_id': job['_id']})
        questions = self.content(attempt, submission)
        fingerprint = request_identity(dict(answers=submission['answers'], bindings=attempt['question_bindings'], configuration=attempt['configuration'], policy='oa-score-v1'))
        if fingerprint != job['input_hash']: raise WorkflowError('submission_changed', 'Evaluation input changed.', 503)
        needs_execution = any(q['type'] != 'mcq' and submission['answers'].get(i, {}).get('source', '').strip() for i, q in questions.items())
        if needs_execution and not self.execution.executor.capabilities()['available']:
            self.defer(job, 'blocked', 'executor_unavailable', 30); return
        results, pending, blocked = {}, False, False
        for identifier, question in questions.items():
            answer = submission['answers'].get(identifier)
            if question['type'] == 'mcq' or not answer or not answer.get('source', '').strip(): continue
            for case in fixtures(question):
                if not self.heartbeat(job): raise WorkflowError('evaluation_lease_lost', 'Evaluation worker lease expired.', 409)
                # Only DB work in this transaction; external execution happens later.
                def enqueue_case(session):
                    current = self.db.assessment_evaluation_jobs.find_one({'_id': job['_id'], 'lease_token': job['lease_token'], 'lease_until': {'$gt': self.clock()}}, session=session)
                    if not current or current['state'] not in {'queued', 'waiting', 'blocked'}: raise WorkflowError('evaluation_lease_lost', 'Evaluation lease changed.', 409)
                    return self.execution.enqueue('grade:'+str(job['_id'])+':'+identifier+':'+case['id'], question, case['id'], answer['language'], answer['source'], 'grading', job['attempt_id'], session)
                task = atomic(self.db, enqueue_case)
                if task['state'] == 'complete': results[identifier, case['id']] = task['result']
                else:
                    pending = True
                    blocked = blocked or task['state'] in {'blocked', 'dispatch_unknown'} or task.get('needs_review', False)
        if pending:
            self.defer(job, 'blocked' if blocked else 'waiting', 'execution_review_required' if blocked else 'execution_pending', 30 if blocked else 2)
            return
        report = score(attempt['configuration'], questions, submission['answers'], results)
        self.finish(job, report)

    def defer(self, job, state, code, seconds):
        self.db.assessment_evaluation_jobs.update_one({'_id': job['_id'], 'lease_token': job['lease_token'], 'lease_until': {'$gt': self.clock()},
            'state': {'$in': ['queued', 'waiting', 'blocked']}}, {'$set': dict(state=state, error_code=code,
                lease_until=self.clock(), next_attempt_at=self.clock()+timedelta(seconds=seconds))})

    def finish(self, job, report):
        billing = self.runtime.billing  # Construct indexes outside the transaction.
        def finish(session):
            current = self.db.assessment_evaluation_jobs.find_one({'_id': job['_id']}, session=session)
            if current['state'] in {'complete', 'unavailable'}: return
            if current.get('lease_token') != job['lease_token'] or utc(current['lease_until']) <= self.clock():
                raise WorkflowError('evaluation_lease_lost', 'Stale evaluation cannot publish or settle.', 409)
            attempt = self.db.assessment_attempts.find_one({'_id': object_id(job['attempt_id'])}, session=session)
            submission = self.db.assessment_submissions.find_one({'_id': job['_id']}, session=session)
            questions = self.content(attempt, submission, session)
            expected_hash = request_identity(dict(answers=submission['answers'], bindings=attempt['question_bindings'], configuration=attempt['configuration'], policy='oa-score-v1'))
            if expected_hash != current['input_hash']: raise WorkflowError('submission_changed', 'Evaluation input changed.', 503)
            # Recompute from durable verdicts in the settlement transaction: no
            # caller-supplied score or stale in-memory report can settle a wallet.
            evidence = {}
            for identifier, question in questions.items():
                for case in fixtures(question):
                    task = self.db.assessment_execution_tasks.find_one({'identity': 'grade:'+str(job['_id'])+':'+identifier+':'+case['id']}, session=session)
                    if task and task['state'] == 'complete': evidence[identifier, case['id']] = task['result']
            actual = score(attempt['configuration'], questions, submission['answers'], evidence)
            if actual != report: raise WorkflowError('evaluation_changed', 'Durable evaluation evidence changed.', 409)
            complete = actual['state'] == 'complete'
            practice = attempt.get('pool') == 'practice'
            version = None if practice else self.runtime.version(attempt['workflow_version_id'], session)
            minimum = None if practice else version['configuration']['qualification']['oa_minimum']
            recommendation = 'review_required' if not complete or minimum is None else 'cleared' if actual['score'] >= minimum else 'not_cleared'
            actual.update(attempt_id=job['attempt_id'], application_id=attempt.get('application_id'), owner_id=attempt['owner_id'], pool=attempt.get('pool', 'recruitment'),
                recommendation=recommendation, released=False, created_at=self.clock(), input_hash=current['input_hash'],
                billing_action=('included_in_practice_purchase' if practice else 'capture') if complete else ('practice_refund' if practice else 'release'))
            if practice:
                from services.practice_assessment_service import PracticeAssessmentService
                PracticeAssessmentService(self.db, self.clock, runtime=self.runtime).evaluation_finished(attempt, complete, session)
            if attempt.get('billing_key'): billing.settle(attempt['owner_id'], 'recruiter', attempt['billing_key'], actual['billing_action'], session=session)
            self.db.assessment_evaluation_reports.insert_one(actual, session=session)
            state = 'complete' if complete else 'unavailable'
            self.db.assessment_evaluation_jobs.update_one({'_id': job['_id']}, {'$set': dict(state=state, completed_at=self.clock(), lease_until=self.clock())}, session=session)
            self.db.assessment_submissions.update_one({'_id': job['_id']}, {'$set': {'state': state}}, session=session)
            self.db.assessment_attempts.update_one({'_id': attempt['_id']}, {'$set': {'state': 'completed' if complete else 'unavailable'}}, session=session)
            if practice: self.runtime.practice_state(attempt, 'completed' if complete else 'unavailable', session)
            else:
                app = self.runtime.workflow.repo.application(attempt['application_id'], session)
                workflow = deepcopy(app['workflow']); stage = next(s for s in workflow['stages'] if s['type'] == 'oa')
                # Recommendation and numeric result are private until recruiter release.
                stage.update(state='completed', outcome='pending' if complete else 'review_required', result_release_pending=complete)
                self.runtime.write(app, workflow, 'oa_evaluated', 'oa-evaluated:'+job['attempt_id'], 'Objective assessment evaluation recorded; company advancement requires recruiter action.', session)
        atomic(self.db, finish)

    def tick(self):
        if os.getenv('GENHIRE_OA_EVALUATION_ENABLED', '').lower() != 'true': return False
        self.reconcile()
        job = self.claim()
        if not job: return False
        try: self.process(job)
        except Exception as exc:
            code = exc.code if isinstance(exc, WorkflowError) else 'evaluation_internal_error'
            if code == 'execution_queue_full':
                self.defer(job, 'blocked', code, 30); return True
            failures = job.get('failures', 0)+1
            self.db.assessment_evaluation_jobs.update_one({'_id': job['_id'], 'lease_token': job['lease_token'], 'lease_until': {'$gt': self.clock()}}, {'$set': dict(
                failures=failures, error_code=code, state='needs_review' if failures >= 8 or code in {'content_changed', 'submission_changed'} else 'blocked',
                lease_until=self.clock(), next_attempt_at=self.clock()+timedelta(seconds=min(300, 2**min(failures, 8))))})
        return True

    def report(self, actor, attempt_id):
        attempt = self.db.assessment_attempts.find_one({'_id': object_id(attempt_id)})
        if not attempt: raise WorkflowError('not_found', 'Attempt not found.', 404)
        self.runtime.context_access(attempt, actor)
        if attempt.get('pool') == 'practice':
            from services.practice_assessment_service import PracticeAssessmentService
            return PracticeAssessmentService(self.db, self.clock, runtime=self.runtime).report(actor, attempt)
        report = self.db.assessment_evaluation_reports.find_one({'attempt_id': attempt_id})
        if actor.get('user_type') in {'candidate', 'student'}:
            if report and report.get('released') and report.get('released_summary'):
                return dict(attempt_id=attempt_id, state=attempt['state'], result_available=True, summary=report['released_summary'])
            return dict(attempt_id=attempt_id, state=attempt['state'], result_available=False, message='The recruiter will confirm the result and next step.')
        job = self.db.assessment_evaluation_jobs.find_one({'attempt_id': attempt_id})
        safe = {k: report[k] for k in ('state', 'score', 'sections', 'questions', 'recommendation', 'released', 'created_at', 'billing_action')} if report else None
        return dict(attempt_id=attempt_id, state=(job or {}).get('state', 'awaiting_evaluator'), error_code=(job or {}).get('error_code'), report=safe)

    def platform_failure(self, actor, attempt_id, key, reason, session=None):
        operation_key(key)
        if actor.get('user_type') != 'admin' or not ({'*', 'applications.write'} & set(actor.get('permissions', []))):
            raise WorkflowError('forbidden', 'Platform failure settlement requires an authorized administrator.', 403)
        if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 1000: raise WorkflowError('reason_required', 'Document the verified platform failure.', 400)
        billing = self.runtime.billing
        def close(session):
            identity = dict(actor_id=str(actor['_id']), key=key)
            fingerprint = request_identity(dict(attempt_id=attempt_id, reason=reason))
            old = self.db.assessment_evaluation_actions.find_one(identity, session=session)
            if old:
                if old['fingerprint'] != fingerprint: raise WorkflowError('idempotency_conflict', 'Action key was reused.')
                return old['result']
            attempt = self.db.assessment_attempts.find_one({'_id': object_id(attempt_id)}, session=session)
            if not attempt: raise WorkflowError('not_found', 'Attempt not found.', 404)
            job = self.db.assessment_evaluation_jobs.find_one({'attempt_id': attempt_id}, session=session)
            submission = self.db.assessment_submissions.find_one({'attempt_id': attempt_id}, session=session)
            if not submission or (job and job['state'] in {'complete', 'unavailable'}): raise WorkflowError('settlement_conflict', 'A terminal/usable evaluation cannot be refunded through this action.')
            if attempt.get('billing_key'): billing.settle(attempt['owner_id'], 'recruiter', attempt['billing_key'], 'release', session=session)
            queued = self.db.assessment_execution_tasks.count_documents({'attempt_id': attempt_id, 'purpose': 'grading', 'state': 'queued'}, session=session)
            self.db.assessment_execution_tasks.update_many({'attempt_id': attempt_id, 'purpose': 'grading', 'state': {'$in': ['queued', 'blocked']}}, {'$set': {'state': 'cancelled'}}, session=session)
            if queued: self.db.assessment_execution_capacity.update_one({'_id': 'queue'}, {'$inc': {'count': -queued}}, session=session)
            if job: self.db.assessment_evaluation_jobs.update_one({'_id': job['_id']}, {'$set': dict(state='unavailable', lease_token=str(ObjectId()), lease_until=self.clock())}, session=session)
            self.db.assessment_submissions.update_one({'_id': submission['_id']}, {'$set': {'state': 'unavailable'}}, session=session)
            self.db.assessment_attempts.update_one({'_id': attempt['_id']}, {'$set': {'state': 'unavailable'}}, session=session)
            if attempt.get('pool') == 'practice':
                from services.practice_assessment_service import PracticeAssessmentService
                PracticeAssessmentService(self.db, self.clock, runtime=self.runtime).evaluation_finished(attempt, False, session)
                self.runtime.practice_state(attempt, 'unavailable', session)
            else:
                app = self.runtime.workflow.repo.application(attempt['application_id'], session)
                workflow = deepcopy(app['workflow']); next(s for s in workflow['stages'] if s['type'] == 'oa').update(state='completed', outcome='review_required')
                self.runtime.write(app, workflow, 'oa_platform_failure', 'oa-platform-failure:'+attempt_id, reason.strip(), session, str(actor['_id']))
            result = dict(state='unavailable', billing_action='refund' if attempt.get('pool')=='practice' else 'release')
            self.db.assessment_evaluation_actions.insert_one(dict(identity, fingerprint=fingerprint, reason=reason.strip(), result=result, occurred_at=self.clock()), session=session)
            return result
        return close(session) if session is not None else atomic(self.db, close)
