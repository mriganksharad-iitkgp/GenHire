"""Durable bounded case dispatcher shared by public runs and private grading.

Only read-only polling retries automatically. Ambiguous POSTs retain capacity
and identity for reconciliation; stale workers cannot overwrite newer results.
"""
from copy import deepcopy
from datetime import timedelta
import os
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from core.mongo_transactions import atomic
from models.hiring_workflow import WorkflowError
from services.assessment_scoring import comparison
from services.managed_assessment_validator import ManagedAssessmentValidator
from services.workflow_service import request_identity
from services.workflow_service import operation_key


def ensure_execution_indexes(db):
    db.assessment_execution_tasks.create_index('identity', unique=True)
    db.oa_provider_requests.create_index([('purpose',1),('created_at',-1)])
    db.oa_provider_limits.create_index('expires_at',expireAfterSeconds=120)
    db.assessment_execution_tasks.create_index([('state', 1), ('next_poll_at', 1), ('created_at', 1)])
    db.assessment_execution_audit.create_index([('task_id', 1), ('occurred_at', 1)])
    db.assessment_execution_audit.create_index([('actor_id', 1), ('key', 1)], unique=True)


def capacity_limit():
    try: value = int(os.getenv('OA_MAX_CONCURRENT_EXECUTIONS', '2'))
    except ValueError: value = 0
    if not 1 <= value <= 100: raise WorkflowError('invalid_execution_capacity', 'Execution concurrency must be 1-100.', 503)
    return value


class AssessmentExecutionService:
    def __init__(self, db, clock, executor=None):
        self.db, self.clock = db, clock
        self.executor = executor or ManagedAssessmentValidator(db)

    def enqueue(self, identity, question, case_id, language, source, purpose, attempt_id, session=None):
        if session is None:
            return atomic(self.db, lambda tx: self.enqueue(identity, question, case_id, language, source, purpose, attempt_id, tx))
        q = deepcopy(question)
        if q['type'] == 'coding': q['coding']['reference_solutions'][language] = source
        else: q['sql']['reference_query'] = source
        record = dict(_id=ObjectId(), identity=identity, question=q, case_id=case_id, language=language, purpose=purpose, provider='onlinecompiler',
            attempt_id=attempt_id, state='queued', created_at=self.clock(), next_poll_at=self.clock(), retries=0,
            payload_hash=request_identity(dict(question=q, case_id=case_id, language=language, purpose=purpose, attempt_id=attempt_id)))
        attempt=self.db.assessment_attempts.find_one({'_id':ObjectId(attempt_id)}, {'pool':1,'owner_id':1},session=session) if ObjectId.is_valid(attempt_id) else None
        record.update(pool=(attempt or {}).get('pool','recruitment'),owner_id=(attempt or {}).get('owner_id'))
        old = self.db.assessment_execution_tasks.find_one({'identity': identity}, session=session)
        if old:
            if old['payload_hash'] != record['payload_hash']: raise WorkflowError('execution_identity_conflict', 'Execution identity does not match immutable content.')
            return old
        try: queue_limit = int(os.getenv('GENHIRE_OA_EXECUTION_QUEUE_LIMIT', '1000'))
        except ValueError: queue_limit = 0
        if not 1 <= queue_limit <= 5000: raise WorkflowError('invalid_queue_limit', 'Queue limit must be 1–5000.', 503)
        queue = self.db.assessment_execution_capacity.find_one({'_id': 'queue'}, session=session) or {}
        if queue.get('count', 0) >= queue_limit: raise WorkflowError('execution_queue_full', 'Execution queue is full; evaluation remains pending.', 429)
        self.db.assessment_execution_capacity.update_one({'_id': 'queue'}, {'$inc': {'count': 1}}, upsert=True, session=session)
        self.db.assessment_execution_tasks.insert_one(record, session=session)
        return record

    def release(self, task, fields, session):
        if task.get('slot_held'):
            changed = self.db.assessment_execution_capacity.update_one({'_id': 'global', 'active': {'$gte': 1}}, {'$inc': {'active': -1}}, session=session)
            if changed.matched_count != 1: raise WorkflowError('capacity_invariant', 'Execution capacity needs reconciliation.', 503)
        self.db.assessment_execution_tasks.update_one({'_id': task['_id']}, {'$set': dict(fields, slot_held=False)}, session=session)

    def claim(self):
        limit = capacity_limit()
        def claim(session):
            capacity = self.db.assessment_execution_capacity.find_one({'_id': 'global'}, session=session) or {}
            if capacity.get('active', 0) >= limit: return None
            task = self.db.assessment_execution_tasks.find_one({'state': 'queued', 'next_poll_at': {'$lte': self.clock()}, 'provider':'onlinecompiler'}, sort=[('created_at', 1), ('_id', 1)], session=session)
            if not task: return None
            token = str(ObjectId())
            self.db.assessment_execution_capacity.update_one({'_id': 'global'}, {'$inc': {'active': 1}}, upsert=True, session=session)
            self.db.assessment_execution_capacity.update_one({'_id': 'queue', 'count': {'$gte': 1}}, {'$inc': {'count': -1}}, session=session)
            self.db.assessment_execution_tasks.update_one({'_id': task['_id']}, {'$set': dict(state='dispatching', slot_held=True,
                dispatch_token=token, dispatched_at=self.clock(), profile_hash=self.executor.profile_hash())}, session=session)
            return self.db.assessment_execution_tasks.find_one({'_id': task['_id']}, session=session)
        try: return atomic(self.db, claim)
        except DuplicateKeyError: return atomic(self.db, claim)

    def dispatch(self, task):
        q, token = task['question'], task['dispatch_token']
        identity = 'oa-case:'+str(task['_id'])+':'+str(task['retries'])
        self.db.assessment_execution_tasks.update_one({'_id':task['_id'],'dispatch_token':token},
            {'$set':{'provider_id':identity}})
        try:
            if hasattr(self.executor,'provider'):
                self.executor.provider.context={key:task.get(key) for key in ('attempt_id','pool','owner_id')}
            self.executor.execute_case(identity,q,task['case_id'],task['language'],task['purpose'])
            self.db.assessment_execution_tasks.update_one({'_id':task['_id'],'dispatch_token':token,'state':'dispatching'},
                {'$set':dict(state='running',next_poll_at=self.clock(),poll_errors=0)})
        except Exception as exc:
            journal=self.db.oa_provider_requests.find_one({'_id':identity})
            code=exc.code if isinstance(exc,WorkflowError) else 'executor_unavailable'
            def fail(session):
                current=self.db.assessment_execution_tasks.find_one({'_id':task['_id'],'dispatch_token':token,'state':'dispatching'},session=session)
                if not current:return
                retryable=code in {'provider_rate_limit','provider_capacity'} and (not journal or journal['state']=='rejected')
                if retryable:
                    self.db.assessment_execution_capacity.update_one({'_id':'queue'},{'$inc':{'count':1}},upsert=True,session=session)
                    self.release(current,dict(state='queued',error_code=code,next_poll_at=self.clock()+timedelta(seconds=60)),session)
                elif journal and journal['state']!='rejected':
                    self.db.assessment_execution_tasks.update_one({'_id':task['_id']},
                        {'$set':dict(state='running' if journal['state']=='complete' else 'dispatch_unknown',error_code=code)},session=session)
                else:self.release(current,dict(state='blocked',error_code=code),session)
            atomic(self.db,fail)

    def output(self, task):
        result=self.executor.execution_result(task['provider_id'],task['question'])
        if not isinstance(result,dict) or result.get('status') not in {'ok','runtime_error','compile_error','time_limit','memory_limit','output_limit','infrastructure_error'}:
            raise WorkflowError('invalid_execution_result','execution provider result is invalid.',503)
        if task['question']['type']=='coding' and task['purpose']=='grading' and result['status']=='ok' and not result.get('native_judged') and not {'time_ms','memory_kb'} <= result.keys():
            raise WorkflowError('invalid_execution_result','Resource evidence is missing.',503)
        allowed=('status','stdout','columns','rows','time_ms','memory_kb','passed','native_judged')
        if task['purpose']=='public':allowed+=('diagnostics',)
        return {k:result[k] for k in allowed if k in result}

    def poll(self, task):
        try:
            if task['profile_hash'] != self.executor.profile_hash(): raise WorkflowError('executor_profile_changed', 'Original executor profile must be restored.', 503)
            output = self.output(task)
            if output is None:
                self.db.assessment_execution_tasks.update_one({'_id': task['_id'], 'state': 'running'}, {'$set': {'next_poll_at': self.clock()+timedelta(seconds=2)}})
                return
            if task['purpose'] == 'grading':
                cases = task['question'].get('coding', {}).get('tests', []) or task['question'].get('sql', {}).get('datasets', [])
                case = next(c for c in cases if c['id'] == task['case_id'])
                # Store only verdict/resource evidence, never hidden actual output.
                output = dict(status=output['status'], passed=output['passed'] if output.get('native_judged') is True and type(output.get('passed')) is bool else comparison(task['question'], case, output),
                    **{k: output[k] for k in ('time_ms', 'memory_kb') if k in output})
            def complete(session):
                current = self.db.assessment_execution_tasks.find_one({'_id': task['_id'], 'state': 'running', 'dispatch_token': task['dispatch_token']}, session=session)
                if not current: return
                if task['purpose'] == 'grading' and output['status'] == 'infrastructure_error' and current.get('retries', 0) < 2:
                    queue = self.db.assessment_execution_capacity.find_one({'_id': 'queue'}, session=session) or {}
                    if queue.get('count', 0) < int(os.getenv('GENHIRE_OA_EXECUTION_QUEUE_LIMIT', '1000')):
                        self.db.assessment_execution_capacity.update_one({'_id': 'queue'}, {'$inc': {'count': 1}}, upsert=True, session=session)
                        history = current.get('retry_history', [])+[dict(provider_id=current['provider_id'], status='infrastructure_error', completed_at=self.clock())]
                        self.release(current, dict(state='queued', retries=current.get('retries', 0)+1, retry_history=history,
                            next_poll_at=self.clock()+timedelta(seconds=5*(current.get('retries', 0)+1))), session)
                        return
                self.release(current, dict(state='complete', result=output, completed_at=self.clock()), session)
            atomic(self.db, complete)
        except Exception as exc:
            errors = task.get('poll_errors', 0)+1
            code = exc.code if isinstance(exc, WorkflowError) else 'executor_unavailable'
            self.db.assessment_execution_tasks.update_one({'_id': task['_id'], 'state': 'running', 'dispatch_token': task['dispatch_token']},
                {'$set': dict(poll_errors=errors, error_code=code, next_poll_at=self.clock()+timedelta(seconds=min(300, 2**min(errors, 8))),
                    needs_review=errors >= 8)})

    def tick(self):
        def retire(session):
            changed=self.db.assessment_execution_tasks.update_many({'state':'queued','provider':{'$ne':'onlinecompiler'}},
                {'$set':{'state':'blocked','error_code':'retired_provider_reconciliation_required'}},session=session)
            if changed.modified_count:
                self.db.assessment_execution_capacity.update_one({'_id':'queue','count':{'$gte':changed.modified_count}},
                    {'$inc':{'count':-changed.modified_count}},session=session)
        atomic(self.db,retire)
        self.db.assessment_execution_tasks.update_many({'provider':{'$ne':'onlinecompiler'},'state':{'$in':['running','dispatching','dispatch_unknown']}},
            {'$set':{'needs_review':True,'error_code':'retired_provider_reconciliation_required'}})
        if not self.executor.capabilities()['available']: return False
        self.db.assessment_execution_tasks.update_many({'provider':'onlinecompiler','state': 'dispatching', 'dispatched_at': {'$lte': self.clock()-timedelta(minutes=5)}},
            {'$set': {'state': 'dispatch_unknown', 'error_code': 'stale_dispatch'}})
        task = self.claim()
        if task: self.dispatch(task)
        # Recover a result persisted before a worker died, without another POST.
        for unknown in self.db.assessment_execution_tasks.find({'provider':'onlinecompiler','state':'dispatch_unknown','provider_id':{'$exists':True}}).limit(20):
            journal=self.db.oa_provider_requests.find_one({'_id':unknown['provider_id'],'state':'complete'})
            if journal:self.db.assessment_execution_tasks.update_one({'_id':unknown['_id'],'state':'dispatch_unknown'},
                {'$set':dict(state='running',next_poll_at=self.clock())})
        for running in self.db.assessment_execution_tasks.find({'provider':'onlinecompiler','state': 'running', 'next_poll_at': {'$lte': self.clock()}}).sort('next_poll_at', 1).limit(20):
            self.poll(running)
        return bool(task)

    def reconcile(self, actor, task_id, action, key, reason, provider_id=None):
        operation_key(key)
        if actor.get('user_type') != 'admin' or not ({'*', 'applications.write'} & set(actor.get('permissions', []))):
            raise WorkflowError('forbidden', 'Execution reconciliation requires an authorized administrator.', 403)
        if action not in {'bind_provider', 'retry_confirmed', 'resume_poll'} or not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 1000:
            raise WorkflowError('invalid_reconciliation', 'Choose a supported action and document verified provider evidence.', 400)
        task = self.db.assessment_execution_tasks.find_one({'_id': ObjectId(task_id)}) if ObjectId.is_valid(task_id) else None
        if not task: raise WorkflowError('not_found', 'Execution task not found.', 404)
        if task.get('provider')!='onlinecompiler':
            raise WorkflowError('retired_provider_reconciliation_required','Review this historical task with its original provider evidence; it cannot be retried or rebound on the new provider.',409)
        if action == 'bind_provider':
            if not isinstance(provider_id,str) or provider_id!=task.get('provider_id'):
                raise WorkflowError('invalid_provider_binding','Bind only this task?s original completed execution provider journal.',400)
            if task.get('profile_hash')!=self.executor.profile_hash():raise WorkflowError('executor_profile_changed','Restore the original executor profile.',503)
            self.executor.execution_result(provider_id,task['question'])
        fingerprint = request_identity(dict(task_id=task_id, action=action, reason=reason, provider_id=provider_id))
        def reconcile(session):
            identity = dict(actor_id=str(actor['_id']), key=key)
            previous = self.db.assessment_execution_audit.find_one(identity, session=session)
            if previous:
                if previous['fingerprint'] != fingerprint: raise WorkflowError('idempotency_conflict', 'Reconciliation key reused with different evidence.')
                return previous['result']
            current = self.db.assessment_execution_tasks.find_one({'_id': task['_id']}, session=session)
            job = self.db.assessment_evaluation_jobs.find_one({'attempt_id': current['attempt_id']}, session=session)
            if job and job['state'] in {'complete', 'unavailable'} and action == 'retry_confirmed':
                raise WorkflowError('settled_evaluation', 'A settled evaluation cannot start another paid execution.')
            if action == 'bind_provider':
                if current['state'] != 'dispatch_unknown' or not current.get('slot_held'): raise WorkflowError('reconciliation_conflict', 'Task does not hold an unknown dispatch.')
                fields = dict(state='running', provider_id=provider_id, dispatch_token=str(ObjectId()), next_poll_at=self.clock(), poll_errors=0, needs_review=False)
            elif action == 'resume_poll':
                if current['state'] != 'running' or not current.get('provider_id'): raise WorkflowError('reconciliation_conflict', 'Only a known running execution can resume polling.')
                fields = dict(next_poll_at=self.clock(), poll_errors=0, needs_review=False)
            else:
                if current.get('slot_held') or current['state'] not in {'blocked', 'complete'} or (current['state'] == 'complete' and current.get('result', {}).get('status') != 'infrastructure_error') or current.get('retries', 0) >= 2:
                    raise WorkflowError('unsafe_execution_retry', 'Retry only a known pre-dispatch block or confirmed terminal infrastructure error, at most twice.')
                queue = self.db.assessment_execution_capacity.find_one({'_id': 'queue'}, session=session) or {}
                if queue.get('count', 0) >= int(os.getenv('GENHIRE_OA_EXECUTION_QUEUE_LIMIT', '1000')): raise WorkflowError('execution_queue_full', 'Execution queue is full.', 429)
                self.db.assessment_execution_capacity.update_one({'_id': 'queue'}, {'$inc': {'count': 1}}, upsert=True, session=session)
                fields = dict(state='queued', retries=current.get('retries', 0)+1, next_poll_at=self.clock(), needs_review=False)
            self.db.assessment_execution_tasks.update_one({'_id': current['_id']}, {'$set': fields}, session=session)
            if job and job['state'] not in {'complete', 'unavailable'}:
                self.db.assessment_evaluation_jobs.update_one({'_id': job['_id']}, {'$set': dict(state='waiting', next_attempt_at=self.clock(), lease_until=self.clock(), lease_token=str(ObjectId()), failures=0)}, session=session)
            result = dict(task_id=task_id, state=fields.get('state', current['state']))
            self.db.assessment_execution_audit.insert_one(dict(identity, task_id=task_id, fingerprint=fingerprint, action=action,
                reason=reason.strip(), result=result, occurred_at=self.clock()), session=session)
            return result
        return atomic(self.db, reconcile)
