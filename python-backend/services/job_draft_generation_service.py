"""One billed, resumable operation for JD and optional private OA drafts.

Draft generation does not execute code, validate reference outputs or publish.
Unknown interrupted provider calls fail with released funds, never blind replay.
"""
from config.assessment_execution import SQL_RUNTIMES, runtime_profiles
from datetime import datetime, timedelta, timezone
import json
import logging
from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from core.mongo_transactions import atomic
from models.hiring_workflow import WorkflowError
from models.job_setup import fields, text, validate_setup, validate_job_fields, JOB_FIELDS
from services.job_setup_service import JobSetupService, credit_setting
from services.workflow_service import operation_key, request_identity
from services.assessment_generation_service import question_contract, parse_generated, generation_enabled
from services.assessment_generation_schema import question_response_schema
from payment_module.services.billing_operation_service import BillingOperationService, BillingOperationError


logger = logging.getLogger(__name__)


class JobDraftGenerationService:
    def __init__(self, db, llm=None, jd_generator=None):
        self.db, self.llm, self.jd_generator = db, llm, jd_generator
        self.billing = BillingOperationService(db)
        db.job_draft_generations.create_index([('owner_id', 1), ('operation_key', 1)], unique=True)
        db.job_draft_generations.create_index([('state', 1), ('lease_until', 1), ('created_at', 1)])

    def enqueue(self, actor, prompt, configuration, key, accepted_credits, document=''):
        JobSetupService.actor(actor, write=True)
        key = operation_key(key)
        prompt = text(prompt, 'Recruiter brief', 2000)
        document = text(document, 'JD document', 12000)
        if len((prompt + document).strip()) < 3:
            raise WorkflowError('invalid_brief', 'Describe the job or upload a JD.', 400)
        configuration = validate_setup(configuration)
        if configuration['pipeline']['oa_enabled']:
            JobSetupService.enabled()
            if not generation_enabled():
                raise WorkflowError('generation_disabled', 'AI question generation is disabled. Manual authoring remains available.', 503)
        configuration['oa']['source'] = 'ai'
        cost = credit_setting('RECRUITER_AI_JD_CREDITS', 10)
        if type(accepted_credits) is not int or accepted_credits != cost or cost <= 0:
            raise WorkflowError('price_changed', 'Reload the displayed AI drafting price before generating.', 409)
        owner = str(actor['_id'])
        signature = request_identity(dict(prompt=prompt, document=document, configuration=configuration, cost=cost))
        allocated, now = ObjectId(), datetime.now(timezone.utc)

        def create(session):
            existing = self.db.job_draft_generations.find_one(dict(owner_id=owner, operation_key=key), session=session)
            if existing:
                if existing.get('error_code') == 'cancelled':
                    raise WorkflowError('cancelled', 'This request was cancelled. Start a new generation deliberately.', 409)
                if existing['signature'] != signature:
                    raise WorkflowError('idempotency_conflict', 'This generation key belongs to another brief.', 409)
                return self.public(existing)
            control = self.db.job_draft_generation_controls.find_one({'_id': owner}, session=session)
            if control and control.get('active_job_id'):
                raise WorkflowError('generation_busy', 'Your previous AI draft is still running. Reopen it before starting another.', 409)
            billing_key = f'job-draft:{allocated}'
            self.billing.reserve(owner, 'recruiter', cost, billing_key, 'ai_job_and_oa_draft', session=session)
            record = dict(_id=allocated, owner_id=owner, operation_key=key, signature=signature, prompt=prompt,
                document=document, configuration=configuration, credits=cost, billing_key=billing_key,
                state='queued', completed_questions=0, total_questions=sum(s['count'] for s in configuration['oa']['sections'])
                    if configuration['pipeline']['oa_enabled'] else 0, created_at=now, lease_until=now)
            self.db.job_draft_generations.insert_one(record, session=session)
            self.db.job_draft_generation_controls.update_one({'_id': owner}, {'$set': {'active_job_id': str(allocated)}}, upsert=True, session=session)
            return self.public(record)
        try:
            return atomic(self.db, create)
        except DuplicateKeyError:
            return atomic(self.db, create)
        except BillingOperationError as exc:
            raise WorkflowError('insufficient_credits', 'Insufficient credits for the complete AI draft.', 402) from exc

    @staticmethod
    def public(job):
        value = {key: job.get(key) for key in ('state', 'completed_questions', 'total_questions', 'credits', 'error_code', 'failure_stage', 'phase', 'retry_at')}
        value['id'] = str(job['_id'])
        value['operation_key'] = job['operation_key']
        value['credits_released'] = job['state'] == 'failed'
        if job['state'] == 'completed':
            value.update(job_data=job['job_data'], configuration=job['configuration'], questions=job['questions'])
        return value

    def get(self, actor, key):
        JobSetupService.actor(actor)
        record = self.db.job_draft_generations.find_one(dict(owner_id=str(actor['_id']), operation_key=operation_key(key)))
        if not record:
            raise WorkflowError('not_found', 'AI draft request was not found. Retry the same brief without changing its request key.', 404)
        return self.public(record)

    def active(self, actor):
        JobSetupService.actor(actor)
        record = self.db.job_draft_generations.find_one(dict(owner_id=str(actor['_id']), state={'$in':['queued','generating']}))
        if not record:
            raise WorkflowError('not_found', 'No pending AI draft was found.', 404)
        return self.public(record)

    def cancel(self, actor, key):
        JobSetupService.actor(actor, write=True)
        key, owner = operation_key(key), str(actor['_id'])
        def cancel(session):
            record = self.db.job_draft_generations.find_one(dict(owner_id=owner,operation_key=key),session=session)
            if record and record['state']=='completed':
                raise WorkflowError('already_completed','This draft is already complete; its fields are ready to review.',409)
            if record and record['state']=='failed':
                return self.public(record)
            if not record:
                # A cancellation tombstone also stops a delayed, uncertain POST
                # from reserving credits after the user has cancelled its key.
                record=dict(_id=ObjectId(),owner_id=owner,operation_key=key,state='failed',error_code='cancelled',credits=0,
                    completed_questions=0,total_questions=0,created_at=datetime.now(timezone.utc))
                self.db.job_draft_generations.insert_one(record,session=session)
            else:
                self.billing.settle(owner,'recruiter',record['billing_key'],'release',session=session)
                self.db.job_draft_generations.update_one({'_id':record['_id']},{'$set':dict(state='failed',error_code='cancelled'), '$unset': {'checkpoint':'','retry_at':''}},session=session)
                record.update(state='failed',error_code='cancelled')
                self.db.job_draft_generation_controls.update_one({'_id':owner,'active_job_id':str(record['_id'])},{'$set':{'active_job_id':None}},session=session)
            return self.public(record)
        try:return atomic(self.db,cancel)
        except DuplicateKeyError:return atomic(self.db,cancel)

    def run_once(self):
        now, token = datetime.now(timezone.utc), str(ObjectId())
        job = self.db.job_draft_generations.find_one_and_update(
            {'state': {'$in': ['queued', 'generating']}, 'lease_until': {'$lte': now}},
            {'$set': {'lease_token': token, 'lease_until': now + timedelta(minutes=10)}},
            sort=[('created_at', 1)], return_document=ReturnDocument.AFTER)
        if not job:
            return False
        identity = dict(_id=job['_id'], lease_token=token)

        def heartbeat(**extra):
            result = self.db.job_draft_generations.update_one(dict(identity, state={'$in':['queued','generating']}, lease_until={'$gt': datetime.now(timezone.utc)}),
                {'$set': dict(lease_until=datetime.now(timezone.utc) + timedelta(minutes=10), **extra)})
            if result.matched_count != 1:
                raise WorkflowError('lease_lost', 'Draft generation lease expired.', 409)

        stage = 'job_details'
        try:
            if job['state'] == 'generating':
                raise WorkflowError('external_outcome_unknown', 'Interrupted generation was released; start a new request.', 503)
            actor = self.db.users.find_one({'_id': ObjectId(job['owner_id'])})
            if not actor:
                raise WorkflowError('actor_unavailable', 'Recruiter is unavailable.', 403)
            JobSetupService.actor(actor, write=True)
            oa = job['configuration']['oa']
            if job['configuration']['pipeline']['oa_enabled']:
                JobSetupService.enabled()
            if job['configuration']['pipeline']['oa_enabled'] and not generation_enabled():
                raise WorkflowError('generation_disabled', 'AI generation is disabled.', 503)
            checkpoint = job.get('checkpoint') or {}
            heartbeat(state='generating', phase='job_details')
            if self.jd_generator is None:
                from controllers.job_controller import JobController
                controller = JobController({name: self.db[name] for name in ('jobs', 'applications', 'users')})
                self.jd_generator = lambda brief, owner: controller.generate_jd_with_ai(brief, owner, charge_credits=False, defer_rate_limits=True)
            brief = job['prompt'] + ('\nUploaded JD (source material):\n' + job['document'] if job['document'] else '')
            result, status = (dict(job_data=checkpoint['job_data']), 200) if checkpoint else self.jd_generator(brief, job['owner_id'])
            if status != 200:
                raise WorkflowError('jd_generation_failed', 'AI JD generation failed.', 503)
            if not isinstance(result.get('job_data'), dict):
                raise WorkflowError('invalid_generated_job_details', 'AI did not return job fields.', 422)
            job_data = validate_job_fields({k:v for k,v in result['job_data'].items() if k in JOB_FIELDS})
            job_data['status'] = 'draft'
            for key in ('title', 'department', 'location', 'experience', 'salary', 'description'):
                if not isinstance(job_data.get(key), str) or not job_data[key].strip():
                    raise WorkflowError('invalid_generation', 'AI returned incomplete job details.', 422)
            if not job_data.get('skills'):
                raise WorkflowError('invalid_generation', 'AI returned no job skills.', 422)
            heartbeat()
            questions = checkpoint.get('questions', [])
            completed_slots = 0
            coding_progress = checkpoint.get('coding_progress', {})
            if job['total_questions']:
                if self.llm is None:
                    from services.llm_fallback_service import get_assessment_llm_service
                    self.llm = get_assessment_llm_service()
                for section in oa['sections']:
                    slots = [difficulty for difficulty in ('easy', 'medium', 'hard') for _ in range(section['difficulty'][difficulty])]
                    specs = [dict(type=section['type'], difficulty=difficulty, marks=section['marks'][index])
                        for index, difficulty in enumerate(slots)]
                    batch_size = 3 if section['type'] == 'mcq' else 1
                    section_start = completed_slots
                    completed_slots += len(specs)
                    completed_in_section = min(len(specs),max(0,len(questions)-section_start))
                    for offset in range(completed_in_section, len(specs), batch_size):
                        batch = specs[offset:offset + batch_size]
                        context = dict(job=job_data, brief=job['prompt'], instructions=oa['instructions'], requests=batch,
                            coding_contract=oa['coding_contract'], languages=oa['languages'], mcq_mode=oa['mcq_mode'],
                            runtime_versions={language:runtime_profiles()[language]['runtime_label'] for language in oa['languages']},
                            sql_engine=oa['sql_engine'], sql_engine_version=SQL_RUNTIMES.get(oa['sql_engine'],'18'),
                            previous_question_titles=[q['title'] for q in questions])
                        stage = section['type']
                        heartbeat(phase=stage)
                        contract = question_contract(stage) + '\nDraft only; execution validation follows later. Avoid repeated questions.\n'
                        options = dict(json_mode=True, defer_rate_limits=True)
                        schema = question_response_schema(stage, oa['languages'], oa['coding_contract'])
                        if schema:
                            options['response_schema'] = schema
                        if stage == 'mcq':
                            options['max_output_tokens'] = 2048 if len(batch) == 1 else 4096
                        if stage == 'coding':
                            from services.coding_draft_generation import generate_coding_draft
                            generated = [generate_coding_draft(self.llm,context,coding_progress,lambda:heartbeat(phase='coding'))]
                            coding_progress = {}
                        else:
                            from services.coding_draft_generation import bounded_draft
                            generated = bounded_draft(self.llm,contract+json.dumps(context),options,
                                lambda content:parse_generated(content,batch),lambda:heartbeat(phase=stage))
                        for question in generated:
                            if question['type'] == 'coding' and (question['coding']['contract'] != oa['coding_contract'] or question['coding']['languages'] != oa['languages']):
                                raise WorkflowError('invalid_generation', 'Coding languages or format differ from the request.', 422)
                            if question['type'] == 'sql' and question['sql']['engine'] != oa['sql_engine']:
                                raise WorkflowError('invalid_generation', 'SQL engine differs from the request.', 422)
                            if question['type'] == 'mcq' and oa['mcq_mode'] != 'mixed' and question['mcq']['selection'] != oa['mcq_mode']:
                                raise WorkflowError('invalid_generation', 'MCQ mode differs from the request.', 422)
                            if request_identity(question) in {request_identity(q) for q in questions}:
                                raise WorkflowError('invalid_generation', 'AI repeated a question.', 422)
                            questions.append(question)
                        if len(json.dumps(questions).encode('utf-8')) > 4_000_000:
                            raise WorkflowError('draft_size_limit','Generated questions exceed the complete-draft storage limit.',422)
                        heartbeat(completed_questions=len(questions))

            if job['total_questions']:
                from models.assessment_content import blueprint_match
                blueprint_match(oa,questions)
            stage = 'saving'
            heartbeat(phase='saving')
            def complete(session):
                current = self.db.job_draft_generations.find_one(identity, session=session)
                if not current or current['state'] != 'generating' or current['lease_until'].replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
                    raise WorkflowError('lease_lost', 'Generation lease was lost.', 409)
                current_actor = self.db.users.find_one({'_id': actor['_id']}, session=session)
                JobSetupService.actor(current_actor or {}, write=True)
                if job['configuration']['pipeline']['oa_enabled']:
                    JobSetupService.enabled()
                saved = []
                for content in questions:
                    qid = ObjectId()
                    self.db.question_versions.insert_one(dict(_id=qid, question_id=str(qid), revision=1, owner_id=job['owner_id'],
                        pool='recruitment', content=content, content_hash=request_identity(content), source='ai',
                        created_by=job['owner_id'], created_at=datetime.now(timezone.utc), generation_job_id=str(job['_id'])), session=session)
                    self.db.assessment_content_audit.insert_one(dict(actor_id=job['owner_id'],owner_id=job['owner_id'],action='question_version_created',target_id=str(qid),created_at=datetime.now(timezone.utc)),session=session)
                    saved.append(dict(_id=str(qid), content=content, title=content['title'], type=content['type']))
                self.billing.settle(job['owner_id'], 'recruiter', job['billing_key'], 'capture', session=session)
                self.db.job_draft_generations.update_one(identity, {'$set': dict(state='completed', job_data=job_data, questions=saved), '$unset': {'checkpoint':'','retry_at':''}}, session=session)
                self.db.job_draft_generation_controls.update_one({'_id': job['owner_id'], 'active_job_id': str(job['_id'])}, {'$set': {'active_job_id': None}}, session=session)
            atomic(self.db, complete)
        except Exception as exc:
            from services.llm_fallback_service import LLMRateLimitDeferred
            if isinstance(exc, LLMRateLimitDeferred) and job.get('rate_limit_retries', 0) < max(20, job['total_questions'] * 2) and (
                    datetime.now(timezone.utc) - job['created_at'].replace(tzinfo=timezone.utc)) < timedelta(minutes=30):
                # Only a definite provider refusal is resumable. A lost worker with
                # an unknown in-flight call still follows the compensation path above.
                retry_at = datetime.now(timezone.utc) + timedelta(seconds=exc.retry_after)
                heartbeat(state='queued', phase='waiting_provider', retry_at=retry_at,
                    checkpoint=dict(job_data=job_data, questions=questions, coding_progress=coding_progress) if stage != 'job_details' else checkpoint,
                    completed_questions=len(questions) if stage != 'job_details' else 0, rate_limit_retries=job.get('rate_limit_retries', 0) + 1)
                self.db.job_draft_generations.update_one(dict(identity, state='queued'), {'$set': {'lease_until': retry_at}})
                logger.info('JD/OA draft deferred after temporary rate limit: ready=%s total=%s retry_after=%s',
                    len(questions) if stage != 'job_details' else 0, job['total_questions'], exc.retry_after)
                return True
            code = 'provider_rate_limit_exhausted' if isinstance(exc, LLMRateLimitDeferred) else exc.code if isinstance(exc, WorkflowError) else 'generation_failed'
            from services.llm_fallback_service import LLMAllProvidersExhaustedError
            if isinstance(exc, LLMAllProvidersExhaustedError):
                from services.coding_draft_generation import invalid_output
                code = 'provider_invalid_json' if invalid_output(exc) else 'providers_unavailable'
            if code == 'invalid_job_setup':
                code = 'invalid_generated_job_details' if stage == 'job_details' else 'invalid_generated_question'
            logger.warning('JD/OA generation failed: stage=%s code=%s type=%s', stage, code, type(exc).__name__)
            def fail(session):
                current = self.db.job_draft_generations.find_one(identity, session=session)
                if not current or current['state'] not in {'queued', 'generating'}:
                    return
                self.billing.settle(job['owner_id'], 'recruiter', job['billing_key'], 'release', session=session)
                self.db.job_draft_generations.update_one(identity, {'$set': dict(state='failed', error_code=code, failure_stage=stage), '$unset': {'checkpoint':'','retry_at':''}}, session=session)
                self.db.job_draft_generation_controls.update_one({'_id': job['owner_id'], 'active_job_id': str(job['_id'])}, {'$set': {'active_job_id': None}}, session=session)
            atomic(self.db, fail)
        return True
