"""Bounded public/custom runs, isolated from hidden grading and web-host execution."""
from copy import deepcopy
from bson import ObjectId
from core.mongo_transactions import atomic
from models.assessment_content import validate_question
from models.hiring_workflow import WorkflowError
from services.assessment_authoring_service import object_id
from services.managed_assessment_validator import ManagedAssessmentValidator
from services.workflow_service import operation_key, request_identity


class AssessmentPublicRunService:
    def __init__(self, runtime):
        self.runtime, self.db = runtime, runtime.db
        self.executor = ManagedAssessmentValidator(self.db)

    def create(self, actor, attempt_id, key, question_id, answer, custom_input=None):
        operation_key(key)
        try: fingerprint = request_identity(dict(question_id=question_id, answer=answer, custom_input=custom_input))
        except (ValueError, TypeError): raise WorkflowError('invalid_input', 'Run input must contain finite JSON values.', 400) from None
        allocated = ObjectId()
        def enqueue(session):
            attempt = self.runtime.owned(actor, attempt_id, session)
            old = self.db.assessment_public_runs.find_one({'attempt_id': attempt_id, 'key': key}, session=session)
            if old:
                if old['fingerprint'] != fingerprint: raise WorkflowError('idempotency_conflict', 'Run key reused for different content.')
                return str(old['_id'])
            self.runtime.writable(attempt, question_id, session)
            q = next((q for q in attempt['questions'] if q['id'] == question_id and q['type'] != 'mcq'), None)
            if not q: raise WorkflowError('invalid_question', 'Select a coding or SQL question.', 400)
            self.runtime.answer(q, answer)
            if not self.executor.capabilities()['available']: raise WorkflowError('executor_unavailable', 'Execution is unconfigured or awaiting live acceptance. Your saved work is retained.', 503)
            from config.assessment_execution import integer_setting
            limit=integer_setting('OA_MAX_PRACTICE_RUNS_PER_QUESTION',10,1,100)
            if self.db.assessment_public_runs.count_documents({'attempt_id':attempt_id,'question_id':question_id},session=session)>=limit:
                raise WorkflowError('run_limit','Practice run limit reached for this question.',429)
            from config.assessment_execution import sql_enabled
            if q['type']=='sql' and not sql_enabled(q['sql']['engine']):raise WorkflowError('sql_engine_unavailable','This SQL engine is unavailable for candidate execution.',503)
            if q['type']=='sql' and not self.executor.capabilities().get('sql_available'):
                raise WorkflowError('sql_acceptance_required','SQL execution needs live dataset isolation acceptance.',503)
            if self.db.assessment_public_runs.find_one({'attempt_id': attempt_id, 'state': {'$in': ['queued', 'dispatching', 'running', 'dispatch_unknown', 'blocked']}}, session=session):
                raise WorkflowError('run_pending', 'A run is already pending or requires operator reconciliation.', 409)
            record = self.db.question_versions.find_one({'_id': object_id(question_id)}, session=session)
            binding = next((b for b in attempt.get('question_bindings', []) if b['question_version_id'] == question_id), None)
            if not record or not binding or request_identity(record['content']) != binding['content_hash']:
                raise WorkflowError('content_changed', 'Pinned question content changed; operator review is required.', 503)
            private = record['content']
            prepared, case_id = self.prepare(private, answer, custom_input)
            self.db.assessment_attempts.update_one({'_id': attempt['_id']}, {'$inc': {'public_run_count': 1}}, session=session)
            self.db.assessment_public_runs.insert_one(dict(_id=allocated, attempt_id=attempt_id, key=key, fingerprint=fingerprint,
                question_id=question_id, question=prepared, case_id=case_id, language=answer['language'], state='queued', created_at=self.runtime.clock()), session=session)
            return str(allocated)
        return dict(run_id=atomic(self.db, enqueue))

    @staticmethod
    def prepare(private, answer, custom_input):
        q = deepcopy(private)
        section = q['coding'] if q['type'] == 'coding' else q['sql']
        cases = section['tests'] if q['type'] == 'coding' else section['datasets']
        case = next(c for c in cases if c['visibility'] == 'sample')
        if q['type'] == 'coding':
            section['reference_solutions'][answer['language']] = answer['source']
            if custom_input is not None: case['input'] = custom_input
        else:
            if custom_input is not None: raise WorkflowError('invalid_input', 'SQL runs use the displayed sample dataset.', 400)
            section['reference_query'] = answer['source']
        # Typed custom input is validated before any quota or external dispatch.
        validate_question(q)
        # This private job is never serialized to a candidate. Dispatch selects
        # exactly the public case above; result() is an explicit allowlist.
        return q, case['id']

    def result(self, actor, attempt_id, identifier):
        self.runtime.owned(actor, attempt_id)
        record = self.db.assessment_public_runs.find_one({'_id': object_id(identifier), 'attempt_id': attempt_id})
        if not record: raise WorkflowError('not_found', 'Run not found.', 404)
        return dict(run_id=identifier, question_id=record.get('question_id'), state=record['state'], result=record.get('result'))

    def tick(self):
        from services.assessment_execution_service import AssessmentExecutionService
        engine = AssessmentExecutionService(self.db, self.runtime.clock, self.executor)
        for record in self.db.assessment_public_runs.find({'state': 'queued'}).sort('created_at', 1).limit(10):
            q = record['question']
            source = q['coding']['reference_solutions'][record['language']] if q['type'] == 'coding' else q['sql']['reference_query']
            try:
                def enqueue(session):
                    task = engine.enqueue('public:'+str(record['_id']), q, record['case_id'], record['language'], source, 'public', record['attempt_id'], session)
                    self.db.assessment_public_runs.update_one({'_id': record['_id'], 'state': 'queued'},
                        {'$set': {'state': 'running', 'execution_task_id': str(task['_id'])}}, session=session)
                atomic(self.db, enqueue)
            except WorkflowError:
                # Admission is read-only with respect to vendors; queue backpressure
                # never turns into an automatic wrong answer or new paid POST.
                break
        engine.tick()
        for record in self.db.assessment_public_runs.find({'execution_task_id': {'$exists': True}, 'state': {'$nin': ['complete']}}).limit(50):
            task = self.db.assessment_execution_tasks.find_one({'_id': object_id(record['execution_task_id'])})
            if task:
                self.db.assessment_public_runs.update_one({'_id': record['_id']}, {'$set': dict(state=task['state'], **({'result': task['result']} if 'result' in task else {}))})
        # Retired-provider jobs cannot be rebound to a new paid execution.
        self.db.assessment_public_runs.update_many({'state':{'$in':['running','dispatching']},'execution_task_id':{'$exists':False}},
            {'$set':{'state':'blocked','error_code':'retired_provider_reconciliation_required'}})
