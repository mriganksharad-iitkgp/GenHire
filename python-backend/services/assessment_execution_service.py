"""Durable bounded case dispatcher shared by public runs and private grading.

Only read-only polling retries automatically. Ambiguous POSTs retain capacity
and identity for reconciliation; stale workers cannot overwrite newer results.
"""
from copy import deepcopy
from datetime import timedelta
import math
import os
from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from core.mongo_transactions import atomic
from config.assessment_execution import runtime_profiles
from models.hiring_workflow import WorkflowError
from services.assessment_harness import function_source
from services.assessment_scoring import comparison
from services.hiring_progression_service import utc
from services.managed_assessment_validator import ManagedAssessmentValidator
from services.sql_execution_service import SqlExecutionService
from services.workflow_service import request_identity
from services.workflow_service import operation_key


def ensure_execution_indexes(db):
    db.assessment_execution_tasks.create_index('identity', unique=True)
    db.assessment_execution_tasks.create_index([('state', 1), ('next_poll_at', 1), ('created_at', 1)])
    db.assessment_execution_audit.create_index([('task_id', 1), ('occurred_at', 1)])
    db.assessment_execution_audit.create_index([('actor_id', 1), ('key', 1)], unique=True)


def capacity_limit():
    try: value = int(os.getenv('GENHIRE_OA_EXECUTION_CONCURRENCY', '2'))
    except ValueError: value = 0
    if not 1 <= value <= 4: raise WorkflowError('invalid_execution_capacity', 'Pilot execution concurrency must be 1–4.', 503)
    return value


class AssessmentExecutionService:
    def __init__(self, db, clock, executor=None, profiles=runtime_profiles):
        self.db, self.clock, self.profiles = db, clock, profiles
        self.executor = executor or ManagedAssessmentValidator(db)

    def enqueue(self, identity, question, case_id, language, source, purpose, attempt_id, session=None):
        if session is None:
            return atomic(self.db, lambda tx: self.enqueue(identity, question, case_id, language, source, purpose, attempt_id, tx))
        q = deepcopy(question)
        if q['type'] == 'coding': q['coding']['reference_solutions'][language] = source
        else: q['sql']['reference_query'] = source
        record = dict(_id=ObjectId(), identity=identity, question=q, case_id=case_id, language=language, purpose=purpose,
            attempt_id=attempt_id, state='queued', created_at=self.clock(), next_poll_at=self.clock(), retries=0,
            payload_hash=request_identity(dict(question=q, case_id=case_id, language=language, purpose=purpose, attempt_id=attempt_id)))
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
            task = self.db.assessment_execution_tasks.find_one({'state': 'queued', 'next_poll_at': {'$lte': self.clock()}}, sort=[('created_at', 1), ('_id', 1)], session=session)
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
        external_intent = False
        try:
            if q['type'] == 'coding':
                profile = self.profiles()[task['language']]
                if profile['runtime_label'] != q['coding']['runtime_versions'][task['language']]: raise WorkflowError('runtime_changed', 'Runtime profile changed.', 503)
                source = function_source(q, task['language'], task['case_id']) if q['coding']['contract'] == 'function' else q['coding']['reference_solutions'][task['language']]
                case = next(t for t in q['coding']['tests'] if t['id'] == task['case_id'])
                key = 'oa-case:'+str(task['_id'])+':'+str(task['retries'])
                if not self.executor.reserve_submission(key):
                    external_intent = True
                    raise WorkflowError('dispatch_unknown', 'Existing dispatch intent requires reconciliation.', 503)
                external_intent = True
                provider_id = self.executor.client('compilers').create_submission(source, profile['compiler_id'], profile['version_id'],
                    '' if q['coding']['contract'] == 'function' else case['input'], math.ceil(q['coding']['limits']['time_ms']/1000))
            else:
                # A fresh deterministic per-retry ID, never a repeated external POST.
                provider_id = request_identity(dict(task=str(task['_id']), retry=task['retries']))[:24]
                adapter = SqlExecutionService(self.db)
                adapter.reserve(provider_id, q, task['case_id'])
                self.db.assessment_execution_tasks.update_one({'_id': task['_id'], 'dispatch_token': token}, {'$set': {'provider_id': provider_id}})
                external_intent = True
                adapter.dispatch(provider_id)
            self.db.assessment_execution_tasks.update_one({'_id': task['_id'], 'dispatch_token': token, 'state': 'dispatching'},
                {'$set': dict(state='running', provider_id=provider_id, next_poll_at=self.clock(), poll_errors=0)})
        except Exception as exc:
            code = exc.code if isinstance(exc, WorkflowError) else 'dispatch_unknown'
            if q['type'] == 'sql' and external_intent:
                journal = self.db.sql_execution_dispatches.find_one({'_id': provider_id})
                if journal and journal['state'] == 'reserved':
                    # Artifact upload failed before the adapter's durable POST
                    # intent. Retry the same reserved identity, not a new SQL slot.
                    external_intent = False
                    code = 'sql_artifact_unavailable'
            def fail(session):
                current = self.db.assessment_execution_tasks.find_one({'_id': task['_id'], 'dispatch_token': token, 'state': 'dispatching'}, session=session)
                if not current: return
                if external_intent:
                    self.db.assessment_execution_tasks.update_one({'_id': task['_id']}, {'$set': dict(state='dispatch_unknown', error_code=code)}, session=session)
                else:
                    if code in {'sql_capacity', 'sql_artifact_unavailable', 'sphere_monthly_limit', 'sql_monthly_limit'}:
                        self.db.assessment_execution_capacity.update_one({'_id': 'queue'}, {'$inc': {'count': 1}}, upsert=True, session=session)
                    self.release(current, dict(state='queued' if code in {'sql_capacity', 'sql_artifact_unavailable', 'sphere_monthly_limit', 'sql_monthly_limit'} else 'blocked',
                        error_code=code, next_poll_at=self.clock()+timedelta(seconds=30)), session)
            atomic(self.db, fail)

    def output(self, task):
        q = task['question']
        if q['type'] == 'sql':
            result = SqlExecutionService(self.db).result(task['provider_id'])
            if task['purpose'] == 'grading' and result.get('execution_evidence_version') != 2:
                raise WorkflowError('sql_evidence_upgrade_required', 'SQL runner evidence v2 is required for grading.', 503)
            if result.get('status') not in {'ok', 'runtime_error', 'time_limit', 'output_limit', 'infrastructure_error'}:
                raise WorkflowError('invalid_execution_result', 'SQL result is invalid.', 503)
            if result['status'] == 'ok' and (not isinstance(result.get('columns'), list) or not isinstance(result.get('rows'), list)):
                raise WorkflowError('invalid_execution_result', 'SQL result is incomplete.', 503)
            return {k: result[k] for k in ('status', 'columns', 'rows') if k in result}
        client = self.executor.client('compilers'); raw = client.submission(task['provider_id'])
        if raw['executing']: return None
        if task['purpose'] == 'grading':
            profile = self.profiles()[task['language']]
            if raw.get('compiler_id') != profile['compiler_id'] or raw.get('compiler_version_id') != profile['version_id']:
                raise WorkflowError('runtime_evidence_mismatch', 'Execution runtime evidence does not match its pin.', 503)
        status = {11: 'compile_error', 12: 'runtime_error', 13: 'time_limit', 15: 'ok', 17: 'memory_limit', 19: 'runtime_error', 20: 'infrastructure_error'}.get(raw['status_code'])
        if not status: raise WorkflowError('invalid_execution_result', 'Unknown execution status.', 503)
        result = dict(status=status)
        if status == 'ok':
            limits = q['coding']['limits']
            if type(raw.get('output_size')) is not int or raw['output_size'] < 0: raise WorkflowError('invalid_execution_result', 'Output evidence is missing.', 503)
            if raw['output_size'] > limits['output_kb']*1024: result['status'] = 'output_limit'
            else:
                # Public output is useful even if the account omits timing. Private
                # scoring requires finite actual resource evidence, never guesses.
                if task['purpose'] == 'grading':
                    if any(type(raw.get(k)) not in (int, float) or not math.isfinite(raw[k]) or raw[k] < 0 for k in ('time', 'memory_kb')):
                        raise WorkflowError('invalid_execution_result', 'Resource evidence is missing.', 503)
                    result.update(time_ms=raw['time']*1000, memory_kb=raw['memory_kb'])
                    if result['time_ms'] > limits['time_ms']: result['status'] = 'time_limit'
                    elif result['memory_kb'] > limits['memory_mb']*1024: result['status'] = 'memory_limit'
                if result['status'] == 'ok': result['stdout'] = client.output(task['provider_id'], limits['output_kb']*1024)
        # Candidate diagnostics are public-run only. Hidden harness literals and
        # runtime exceptions must never enter any candidate result or report.
        if task['purpose'] == 'public' and status in {'compile_error', 'runtime_error'} and hasattr(client, 'diagnostics'):
            result['diagnostics'] = client.diagnostics(task['provider_id'], 'cmpinfo' if status == 'compile_error' else 'error')
        return result

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
                output = dict(status=output['status'], passed=comparison(task['question'], case, output),
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
        if not self.executor.capabilities()['available']: return False
        self.db.assessment_execution_tasks.update_many({'state': 'dispatching', 'dispatched_at': {'$lte': self.clock()-timedelta(minutes=5)}},
            {'$set': {'state': 'dispatch_unknown', 'error_code': 'stale_dispatch'}})
        task = self.claim()
        if task: self.dispatch(task)
        # A hash-bound private SQL artifact can resolve an ambiguous launch
        # without another POST. Sphere requires operator binding to a known ID.
        self.db.assessment_execution_tasks.update_many({'state': 'dispatch_unknown', 'question.type': 'sql', 'provider_id': {'$exists': True}},
            {'$set': {'state': 'running', 'next_poll_at': self.clock()}})
        for running in self.db.assessment_execution_tasks.find({'state': 'running', 'next_poll_at': {'$lte': self.clock()}}).sort('next_poll_at', 1).limit(20):
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
        if action == 'bind_provider':
            if task['question']['type'] != 'coding' or type(provider_id) is not int or provider_id <= 0:
                raise WorkflowError('invalid_provider_binding', 'Bind an account-verified Sphere submission ID.', 400)
            if task.get('profile_hash') != self.executor.profile_hash(): raise WorkflowError('executor_profile_changed', 'Restore the original executor profile before reconciliation.', 503)
            # Existence check is read-only, outside the transaction. The operator
            # must verify account-side source/input ownership in their stated evidence.
            self.executor.client('compilers').submission(provider_id)
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
