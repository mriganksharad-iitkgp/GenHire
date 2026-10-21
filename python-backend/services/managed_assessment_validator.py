"""Managed-only reference validation. No code/SQL ever executes on the web host."""
from datetime import datetime, timezone
import json
import math
import os
import time
from pymongo.errors import DuplicateKeyError
from core.mongo_transactions import atomic
from config.assessment_execution import enabled, runtime_profiles, execution_status
from models.assessment_content import validate_question
from models.hiring_workflow import WorkflowError
from services.assessment_harness import function_source
from services.sphere_engine_service import SphereEngineClient
from services.sql_execution_service import SqlExecutionService
from services.workflow_service import request_identity


class ManagedAssessmentValidator:
    def __init__(self, db, validation_mode=False):
        self.db, self.validation_mode = db, validation_mode

    def acceptance_fence(self,session,now):
        """Serialize content purchase/start with revocation of actual acceptance."""
        changed=self.db.assessment_executor_attestations.update_one(dict(profile_hash=self.profile_hash(),state='passed',expires_at={'$gt':now}),{'$inc':{'activation_fence':1}},session=session)
        if not changed.matched_count:raise WorkflowError('live_validation_required','Current real executor acceptance is required.',503)

    @staticmethod
    def profile_hash():
        return request_identity(dict(execution_contract='oa_cases_v2', runtimes=runtime_profiles(), compilers=os.getenv('SPHERE_COMPILERS_ENDPOINT', ''),
            problems=os.getenv('SPHERE_PROBLEMS_ENDPOINT', ''), project=os.getenv('GENHIRE_SQL_PROJECT', ''),
            region=os.getenv('GENHIRE_SQL_REGION', 'europe-west1'), bucket=os.getenv('GENHIRE_SQL_ARTIFACT_BUCKET', ''), postgresql_job=os.getenv('GENHIRE_SQL_POSTGRESQL_JOB', ''),
            mysql_job=os.getenv('GENHIRE_SQL_MYSQL_JOB', ''), isolation_policy=os.getenv('GENHIRE_EXECUTOR_ISOLATION_POLICY_ID', '')))

    def capabilities(self):
        status = execution_status()
        try: profile_hash = self.profile_hash()
        except WorkflowError: profile_hash = None
        ready = status['enabled'] and status['sphere_configured'] and status['sql_configured'] and profile_hash and bool(os.getenv('GENHIRE_EXECUTOR_ISOLATION_POLICY_ID'))
        if ready and not self.validation_mode:
            ready = self.db.assessment_executor_attestations.find_one({'profile_hash': profile_hash, 'state': 'passed',
                'expires_at': {'$gt': datetime.now(timezone.utc)}}) is not None
        return dict(available=bool(ready), profile_hash=profile_hash,
            reason='Real Sphere Engine runtime and Cloud Run SQL correctness/isolation checks are required before code/SQL approval.')

    def client(self, product):
        return SphereEngineClient(os.getenv(f'SPHERE_{product.upper()}_ENDPOINT'), os.getenv(f'SPHERE_{product.upper()}_TOKEN'), product)

    def heartbeat(self):
        hook = getattr(self, 'progress_hook', None)
        if hook and not hook(): raise WorkflowError('execution_lease_lost', 'Execution worker lease expired; no further dispatches will be made.', 409)

    def reserve_submission(self, key):
        """Count dispatch intent once, including unknown outcomes; never overdraw."""
        try: limit = int(os.getenv('GENHIRE_SPHERE_MONTHLY_SUBMISSION_LIMIT', '500'))
        except ValueError: raise WorkflowError('invalid_sphere_quota', 'Invalid Sphere Engine quota.', 503) from None
        if not 1 <= limit <= 500: raise WorkflowError('invalid_sphere_quota', 'Sphere pilot quota must be 1–500 submissions/month.', 503)
        month = datetime.now(timezone.utc).strftime('%Y-%m')
        def reserve(session):
            old = self.db.assessment_executor_dispatches.find_one({'_id': key}, session=session)
            if old: return False
            counter = self.db.assessment_executor_limits.find_one({'_id': month}, session=session)
            if (counter or {}).get('count', 0) >= limit:
                raise WorkflowError('sphere_monthly_limit', 'Monthly Sphere Engine submission quota reached.', 429)
            self.db.assessment_executor_limits.update_one({'_id': month}, {'$inc': {'count': 1}}, upsert=True, session=session)
            self.db.assessment_executor_dispatches.insert_one(dict(_id=key, state='dispatching', month=month,
                created_at=datetime.now(timezone.utc)), session=session)
            return True
        try: return atomic(self.db, reserve)
        except DuplicateKeyError: return atomic(self.db, reserve)

    def validate(self, question, content_hash):
        if not self.capabilities()['available']: raise WorkflowError('validator_unavailable', 'Execution is unconfigured or has not passed live validation. Manual drafts remain available.', 503)
        q = validate_question(question)
        if request_identity(q) != content_hash: raise WorkflowError('content_changed', 'Question content hash changed.')
        profile_hash = self.profile_hash()
        runs = []
        if q['type'] == 'coding':
            client, profiles = self.client('compilers'), runtime_profiles()
            for language in q['coding']['languages']:
                profile = profiles[language]
                if q['coding']['runtime_versions'][language] != profile['runtime_label']:
                    raise WorkflowError('unsupported_runtime', 'Question runtime does not match the verified account profile.', 400)
                for case in q['coding']['tests']:
                    self.heartbeat()
                    key = request_identity(dict(profile=profile_hash, content=content_hash, runtime=language, case=case['id']))
                    record = self.db.assessment_executor_dispatches.find_one({'_id': key})
                    if not record:
                        if not self.reserve_submission(key):
                            raise WorkflowError('dispatch_pending', 'This reference execution is already being dispatched.', 409) from None
                        source = function_source(q, language, case['id']) if q['coding']['contract'] == 'function' else q['coding']['reference_solutions'][language]
                        try:
                            submission = client.create_submission(source, profile['compiler_id'], profile['version_id'],
                                '' if q['coding']['contract'] == 'function' else case['input'], math.ceil(q['coding']['limits']['time_ms'] / 1000))
                        except Exception:
                            self.db.assessment_executor_dispatches.update_one({'_id': key}, {'$set': {'state': 'dispatch_unknown'}})
                            raise
                        self.db.assessment_executor_dispatches.update_one({'_id': key}, {'$set': {'state': 'running', 'submission_id': submission}})
                        record = self.db.assessment_executor_dispatches.find_one({'_id': key})
                    if record['state'] == 'complete': runs.append(record['run']); continue
                    if record['state'] != 'running': raise WorkflowError('dispatch_reconciliation_required', 'An uncertain Sphere Engine submission needs reconciliation; it will not be resubmitted.', 503)
                    deadline = time.monotonic() + 180
                    while True:
                        self.heartbeat()
                        result = client.submission(record['submission_id'])
                        if not result['executing']: break
                        if time.monotonic() >= deadline: raise WorkflowError('execution_pending', 'Reference execution is still pending; its submission ID is retained.', 503)
                        time.sleep(2)
                    status = {11: 'compile_error', 12: 'runtime_error', 13: 'time_limit', 15: 'ok', 17: 'memory_limit', 19: 'runtime_error'}.get(result['status_code'])
                    if result.get('compiler_id') != profile['compiler_id'] or result.get('compiler_version_id') != profile['version_id']:
                        raise WorkflowError('runtime_evidence_mismatch', 'Reference execution did not use the pinned runtime.', 503)
                    if status is None: raise WorkflowError('executor_unavailable', 'Provider could not produce a usable execution result.', 503)
                    run = dict(runtime=language, runtime_version=profile['runtime_label'], case_id=case['id'],
                        contract=q['coding']['contract'], harness_version=q['coding']['harness_version'], status=status)
                    if status == 'ok':
                        limits = q['coding']['limits']
                        if not isinstance(result['output_size'], int) or result['output_size'] > limits['output_kb'] * 1024: run['status'] = 'output_limit'
                        elif result['memory_kb'] is None or result['time'] is None: raise WorkflowError('executor_invalid_response', 'Resource evidence is missing.', 503)
                        elif result['memory_kb'] > limits['memory_mb'] * 1024: run['status'] = 'memory_limit'
                        elif result['time'] * 1000 > limits['time_ms']: run['status'] = 'time_limit'
                        else:
                            output = client.output(record['submission_id'], limits['output_kb'] * 1024)
                            if q['coding']['contract'] == 'function':
                                try: run['value'] = json.loads(output, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
                                except ValueError: run['status'] = 'runtime_error'
                            else: run['stdout'] = output
                    self.db.assessment_executor_dispatches.update_one({'_id': key, 'state': 'running'}, {'$set': {'state': 'complete', 'run': run}})
                    runs.append(run)
        elif q['type'] == 'sql':
            adapter = SqlExecutionService(self.db)
            for case in q['sql']['datasets']:
                self.heartbeat()
                request_id = request_identity(dict(profile=profile_hash, content=content_hash, case=case['id']))[:24]
                adapter.reserve(request_id, q, case['id']); adapter.dispatch(request_id)
                deadline = time.monotonic() + 180
                while True:
                    self.heartbeat()
                    try: result = adapter.result(request_id); break
                    except WorkflowError as exc:
                        if exc.code != 'sql_result_pending' or time.monotonic() >= deadline: raise
                        time.sleep(2)
                if result.get('execution_evidence_version') != 2:
                    raise WorkflowError('sql_evidence_upgrade_required', 'SQL runner evidence v2 is required before approval.', 503)
                runs.append(dict(runtime=q['sql']['engine'], runtime_version=q['sql']['engine_version'], case_id=case['id'],
                    status=result['status'], columns=result.get('columns'), rows=result.get('rows')))
        else: raise WorkflowError('invalid_type', 'Use structural validation for MCQs.', 400)
        return dict(adapter_id='sphere-v4-cloud-run-sql-v2', execution_id=profile_hash + ':' + content_hash,
            isolation_policy_id=os.getenv('GENHIRE_EXECUTOR_ISOLATION_POLICY_ID', ''), question_hash=content_hash, runs=runs)
