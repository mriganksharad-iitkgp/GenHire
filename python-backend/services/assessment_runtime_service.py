"""Candidate-scoped timed workspace. The browser never owns a deadline or score."""
from copy import deepcopy
from datetime import timedelta
import json
import os
from core.mongo_transactions import atomic
from models.assessment_content import candidate_question
from models.hiring_workflow import WorkflowError
from services.assessment_authoring_service import object_id
from services.hiring_progression_service import HiringProgressionService, utc
from services.workflow_service import operation_key, request_identity


def ensure_runtime_indexes(db):
    db.assessment_attempts.create_index([('state', 1), ('deadline', 1)])
    db.assessment_answer_receipts.create_index([('attempt_id', 1), ('key', 1)], unique=True)
    db.assessment_submissions.create_index('attempt_id', unique=True)
    db.assessment_public_runs.create_index([('attempt_id', 1), ('key', 1)], unique=True)
    db.assessment_public_runs.create_index([('state', 1), ('created_at', 1)])


class AssessmentRuntimeService(HiringProgressionService):
    def context_access(self, record, actor, write=False, session=None):
        if record.get('pool') == 'practice':
            own = not write and actor.get('user_type') in {'candidate', 'student'} and record['candidate_id'] == str(actor['_id'])
            admin = actor.get('user_type') == 'admin' and ({'*', 'applications.write' if write else 'applications.read'} & set(actor.get('permissions', [])))
            if not (own or admin): raise WorkflowError('forbidden', 'Practice records are private to their candidate and authorized administrators.', 403)
            return
        app = self.workflow.repo.application(record['application_id'], session)
        self.workflow.access(app, actor, write, session)

    def participation_active(self, attempt, session=None):
        if attempt.get('pool') == 'practice':
            purchase = self.db.practice_assessment_purchases.find_one({'_id': object_id(attempt['purchase_id'])}, session=session)
            return bool(purchase and purchase['state'] == 'started')
        return self.workflow.repo.application(attempt['application_id'], session)['workflow']['lifecycle'] == 'active'

    def practice_state(self, attempt, state, session):
        self.db.practice_assessment_purchases.update_one({'_id': object_id(attempt['purchase_id'])}, {'$set': {'state': state, 'updated_at': self.clock()}}, session=session)

    def invitation(self, actor, invitation_id):
        value = self.db.assessment_invitations.find_one({'_id': object_id(invitation_id)})
        if value and value.get('pool') == 'practice':
            from services.practice_assessment_service import PracticeAssessmentService
            return PracticeAssessmentService(self.db, self.clock, runtime=self).invitation(actor, value)
        result = super().invitation(actor, invitation_id)
        value = self.db.assessment_invitations.find_one({'_id': object_id(invitation_id)})
        result['attempt_id'] = value.get('attempt_id')
        from services.assessment_integrity_service import AssessmentIntegrityService, enabled
        result['security_required'] = enabled()
        if enabled(): result['integrity_policy'] = AssessmentIntegrityService(self).policy(value)
        return result

    @property
    def candidate_runtime_ready(self):
        # Separate launch approval from implementation availability. Step 6/7 must
        # establish evaluation and security acceptance before a real cohort starts.
        return all(os.getenv(k, '').lower() == 'true' for k in (
            'GENHIRE_OA_RUNTIME_ENABLED', 'GENHIRE_OA_EVALUATION_ACCEPTED', 'GENHIRE_OA_SECURITY_ACCEPTED', 'GENHIRE_OA_INTEGRITY_ENABLED'))

    def prepare_attempt(self, attempt, invitation, session, actor=None):
        content = self.db.assessment_versions.find_one({'_id': object_id(invitation['assessment_version_id']), 'state': 'published'}, session=session)
        if not content: raise WorkflowError('content_unavailable', 'Published assessment is unavailable.', 503)
        configuration = deepcopy(content['configuration'])
        questions, bindings, grading_cases = [], [], 0
        for identifier in content['question_version_ids']:
            q = self.db.question_versions.find_one({'_id': object_id(identifier), 'pool': attempt.get('pool', 'recruitment'), 'owner_id': attempt['owner_id']}, session=session)
            if not q: raise WorkflowError('content_unavailable', 'Question version is unavailable.', 503)
            questions.append(dict(id=identifier, **candidate_question(q['content'])))
            bindings.append(dict(question_version_id=identifier, content_hash=q['content_hash']))
            from services.assessment_scoring import fixtures
            grading_cases += len(fixtures(q['content']))
        from services.assessment_evaluation_service import grading_case_limit
        if grading_cases > grading_case_limit(): raise WorkflowError('grading_case_limit', 'Assessment exceeds the configured grading budget.', 503)
        if len(json.dumps(questions, ensure_ascii=False).encode()) > 5 * 1024 * 1024:
            raise WorkflowError('content_too_large', 'Candidate content exceeds the pilot workspace limit.', 503)
        if any(q['type'] != 'mcq' for q in questions):
            from services.managed_assessment_validator import ManagedAssessmentValidator
            if not ManagedAssessmentValidator(self.db).capabilities()['available']:
                raise WorkflowError('executor_unavailable', 'Live execution acceptance is required.', 503)
        sections, opening = [], attempt['started_at']
        for index, section in enumerate(configuration['sections']):
            closing = opening + timedelta(minutes=section['duration_minutes']) if configuration['timer_mode'] == 'section' else attempt['deadline']
            sections.append(dict(index=index, type=section['type'], opens_at=opening, closes_at=closing,
                question_ids=[q['id'] for q in questions if q['type'] == section['type']]))
            if configuration['timer_mode'] == 'section': opening = closing
        attempt.update(runtime_version=1, configuration=configuration, questions=questions, question_bindings=bindings,
            sections=sections, answers={}, consent_version='oa-v1')
        from services.assessment_integrity_service import AssessmentIntegrityService
        AssessmentIntegrityService(self).prepare(attempt, invitation, actor, session)

    def start(self, actor, invitation_id, key, consent):
        if consent != 'oa-v1': raise WorkflowError('consent_required', 'Accept the assessment rules before starting.', 400)
        from services.assessment_integrity_service import enabled
        if enabled():
            bound = actor.get('_oa_session')
            if not bound or bound['invitation_id'] != invitation_id or not bound.get('ready') or not bound.get('consent'):
                raise WorkflowError('secure_session_required', 'Complete scoped secure-browser preflight before starting.', 403)
        invitation = self.db.assessment_invitations.find_one({'_id': object_id(invitation_id)})
        if invitation and invitation.get('pool') == 'practice':
            from services.practice_assessment_service import PracticeAssessmentService
            return PracticeAssessmentService(self.db, self.clock, runtime=self).accept(actor, invitation_id, key)
        return self.accept(actor, invitation_id, key)

    def owned(self, actor, identifier, session=None):
        attempt = self.db.assessment_attempts.find_one({'_id': object_id(identifier), 'candidate_id': str(actor['_id'])}, session=session)
        if not attempt or actor.get('user_type') not in {'candidate', 'student'}:
            raise WorkflowError('not_found', 'Attempt not found.', 404)
        if attempt.get('runtime_version') != 1: raise WorkflowError('runtime_unavailable', 'This attempt needs operator review.', 503)
        if attempt.get('integrity_policy'):
            bound = actor.get('_oa_session')
            current = self.db.assessment_security_sessions.find_one({'_id': bound['_id']}, session=session) if bound else None
            if not current or current['state'] == 'revoked' or current['invitation_id'] != attempt['invitation_id'] or not current.get('ready') or not current.get('consent'):
                raise WorkflowError('secure_session_required', 'Resume this attempt through its scoped secure assessment session.', 403)
            if session is not None: self.db.assessment_security_sessions.update_one({'_id': current['_id']}, {'$inc': {'access_fence': 1}}, session=session)
        return attempt

    def view(self, actor, identifier):
        attempt = self.owned(actor, identifier)
        if attempt['state'] == 'in_progress' and self.clock() >= utc(attempt['deadline']):
            self.finalize(identifier, 'deadline'); attempt = self.owned(actor, identifier)
        now = self.clock()
        sections = attempt['sections']
        visible = {q for section in sections if attempt['configuration']['timer_mode'] != 'section' or utc(section['opens_at']) <= now < utc(section['closes_at']) for q in section['question_ids']}
        latest_run = self.db.assessment_public_runs.find_one({'attempt_id': identifier}, sort=[('created_at', -1), ('_id', -1)])
        return dict(attempt_id=identifier, state=attempt['state'], revision=attempt['revision'], server_now=now,
            deadline=attempt['deadline'], sections=sections, timer_mode=attempt['configuration']['timer_mode'],
            questions=[q for q in attempt['questions'] if q['id'] in visible],
            latest_run=dict(run_id=str(latest_run['_id']), state=latest_run['state'], result=latest_run.get('result')) if latest_run else None,
            answers={k: v for k, v in attempt['answers'].items() if k in visible}, submitted_at=attempt.get('submitted_at'))

    def writable(self, attempt, question_id=None, session=None):
        now = self.clock()
        if not self.participation_active(attempt, session): raise WorkflowError('terminal_application', 'Participation is no longer active.')
        if attempt['state'] != 'in_progress' or now >= utc(attempt['deadline']):
            raise WorkflowError('attempt_locked', 'The attempt is submitted or its deadline has passed.')
        if question_id and attempt['configuration']['timer_mode'] == 'section':
            if not any(question_id in s['question_ids'] and utc(s['opens_at']) <= now < utc(s['closes_at']) for s in attempt['sections']):
                raise WorkflowError('section_locked', 'This section is outside its server window.')

    @staticmethod
    def answer(question, value):
        if not isinstance(value, dict): raise WorkflowError('invalid_answer', 'Provide an answer object.', 400)
        if question['type'] == 'mcq':
            ids = value.get('option_ids')
            if set(value) != {'option_ids'} or not isinstance(ids, list) or any(not isinstance(i, str) for i in ids) or len(set(ids)) != len(ids) or not set(ids) <= {o['id'] for o in question['mcq']['options']} or (question['mcq']['selection'] == 'single' and len(ids) > 1):
                raise WorkflowError('invalid_answer', 'Select valid answer options.', 400)
        elif set(value) != {'language', 'source'} or not isinstance(value['source'], str) or len(value['source'].encode()) > 64000 or value['language'] not in (question['coding']['languages'] if question['type'] == 'coding' else ['sql']):
            raise WorkflowError('invalid_answer', 'Provide supported source and language (maximum 64 KB).', 400)
        return deepcopy(value)

    def save(self, actor, identifier, revision, key, answers):
        operation_key(key)
        if type(revision) is not int or not isinstance(answers, dict) or not 1 <= len(answers) <= 120:
            raise WorkflowError('invalid_request', 'Provide the acknowledged revision and answers.', 400)
        try: fingerprint = request_identity(dict(revision=revision, answers=answers))
        except (ValueError, TypeError): raise WorkflowError('invalid_answer', 'Answers must contain finite JSON values.', 400) from None
        def write(session):
            attempt = self.owned(actor, identifier, session)
            old = self.db.assessment_answer_receipts.find_one({'attempt_id': identifier, 'key': key}, session=session)
            if old:
                if old['fingerprint'] != fingerprint: raise WorkflowError('idempotency_conflict', 'Save key was reused for different answers.')
                return old['result']
            self.writable(attempt, session=session)
            if revision != attempt['revision']: raise WorkflowError('stale_revision', 'Another save changed the attempt. Reload and reconcile your local draft.')
            questions = {q['id']: q for q in attempt['questions']}
            merged = deepcopy(attempt['answers'])
            for qid, value in answers.items():
                if qid not in questions: raise WorkflowError('invalid_question', 'Question is outside this attempt.', 400)
                self.writable(attempt, qid, session); merged[qid] = self.answer(questions[qid], value)
            self.db.assessment_attempts.update_one({'_id': attempt['_id'], 'revision': revision}, {'$set': {'answers': merged}, '$inc': {'revision': 1}}, session=session)
            result = dict(revision=revision+1, saved_at=self.clock().isoformat(timespec='milliseconds'))
            self.db.assessment_answer_receipts.insert_one(dict(attempt_id=identifier, key=key, fingerprint=fingerprint, result=result), session=session)
            return result
        return atomic(self.db, write)

    def finalize(self, identifier, reason, actor=None, revision=None, session=None):
        def submit(session):
            attempt = self.owned(actor, identifier, session) if actor else self.db.assessment_attempts.find_one({'_id': object_id(identifier)}, session=session)
            if not attempt: raise WorkflowError('not_found', 'Attempt not found.', 404)
            if attempt['state'] != 'in_progress': return dict(state=attempt['state'], revision=attempt['revision'])
            if reason == 'deadline' and self.clock() < utc(attempt['deadline']): raise WorkflowError('not_due', 'Deadline has not passed.')
            if reason != 'deadline' and revision != attempt['revision']: raise WorkflowError('stale_revision', 'Save and acknowledge all answers before submitting.')
            now = self.clock()
            self.db.assessment_submissions.insert_one(dict(attempt_id=identifier, answers=deepcopy(attempt['answers']),
                assessment_version_id=attempt['assessment_version_id'], answer_revision=attempt['revision'],
                reason='deadline' if now >= utc(attempt['deadline']) else reason, submitted_at=min(now, utc(attempt['deadline'])),
                recorded_at=now, state='awaiting_evaluator', content_hash=request_identity(attempt['answers'])), session=session)
            if attempt.get('integrity_policy'):
                from services.assessment_integrity_service import AssessmentIntegrityService
                summary = AssessmentIntegrityService(self).summarize(attempt, session)
                self.db.assessment_integrity_summaries.update_one({'attempt_id': identifier}, {'$setOnInsert': summary}, upsert=True, session=session)
                self.db.assessment_media.update_many({'attempt_id': identifier, 'state': {'$ne': 'deleted'}},
                    {'$set': {'delete_after': min(now, utc(attempt['deadline']))+timedelta(days=attempt['integrity_policy']['raw_retention_days'])}}, session=session)
            self.db.assessment_attempts.update_one({'_id': attempt['_id']}, {'$set': {'state': 'submitted', 'submitted_at': min(now, utc(attempt['deadline']))}, '$inc': {'revision': 1}}, session=session)
            if attempt.get('pool') == 'practice': self.practice_state(attempt, 'submitted', session)
            else:
                app = self.workflow.repo.application(attempt['application_id'], session)
                workflow = deepcopy(app['workflow'])
                next(s for s in workflow['stages'] if s['type'] == 'oa').update(state='submitted')
                self.write(app, workflow, 'oa_submitted', 'oa-submit:'+identifier, 'Assessment locked for evaluation.', session)
            return dict(state='submitted', revision=attempt['revision']+1)
        return submit(session) if session is not None else atomic(self.db, submit)

    def expire_due(self, limit=50):
        ids = [str(a['_id']) for a in self.db.assessment_attempts.find({'runtime_version': 1, 'state': 'in_progress', 'deadline': {'$lte': self.clock()}}, {'_id': 1}).sort('deadline', 1).limit(limit)]
        for identifier in ids: self.finalize(identifier, 'deadline')
        return len(ids)
