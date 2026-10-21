"""Operator-only live acceptance. Never imports test fixtures or fabricates results.

Isolation configuration/escape testing needs a separate operator security review;
these correctness canaries cannot prove that a third-party sandbox is secure.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import os
import time
import uuid
from models.assessment_content import validate_question
from models.hiring_workflow import WorkflowError
from services.assessment_validation import verify_reference_results
from services.managed_assessment_validator import ManagedAssessmentValidator
from services.workflow_service import request_identity


TARGETS = dict(python='3.12', javascript='22', java='21', cpp='C++20')
REVIEW_CHECKS = ('code_network_denied', 'code_filesystem_isolated', 'code_hard_resource_limits',
    'sql_network_denied', 'sql_file_access_denied', 'sql_role_escape_denied',
    'sql_output_limit_verified', 'sql_crash_recovery_verified', 'images_scanned_and_digest_pinned')


def security_review(value, policy):
    if (not policy or not isinstance(value, dict) or value.get('policy_id') != policy
            or any(value.get(k) is not True for k in REVIEW_CHECKS)
            or any(not isinstance(value.get(k), str) or not 5 <= len(value[k]) <= 200 for k in ('reviewed_by', 'evidence_reference'))):
        raise WorkflowError('isolation_review_required', 'A complete operator isolation review matching the configured policy is required.', 503)
    try: reviewed = datetime.fromisoformat(value['reviewed_at'].replace('Z', '+00:00'))
    except (KeyError, TypeError, ValueError):
        raise WorkflowError('isolation_review_required', 'Review timestamp must be recent and timezone-aware.', 503) from None
    now = datetime.now(timezone.utc)
    if reviewed.tzinfo is None or not now - timedelta(days=7) <= reviewed <= now:
        raise WorkflowError('isolation_review_required', 'Isolation review must be within the past seven days.', 503)
    return deepcopy(value)


def canaries(run_id):
    base = dict(schema_version=1, title='Live executor acceptance ' + run_id, statement='Return the supplied integer.',
        difficulty='easy', topics=['Executor acceptance'], marks=1, explanation='Operator-only fixture.')
    references = dict(python='def solve(value):\n    return value', javascript='function solve(value) { return value; }',
        java='class Solution { public int solve(int value) { return value; } }',
        cpp='class Solution { public: int solve(int value) { return value; } };')
    stdin = dict(python='import sys\nassert sys.version_info[:2] == (3, 12)\nprint(int(input()))',
        javascript="if (process.versions.node.split('.')[0] !== '22') throw Error();\nconsole.log(Number(require('fs').readFileSync(0,'utf8').trim()));",
        java='class Main { public static void main(String[] args) { if (Runtime.version().feature()!=21) throw new RuntimeException(); System.out.println(new java.util.Scanner(System.in).nextInt()); } }',
        cpp='#include <iostream>\nstatic_assert(__cplusplus >= 202002L);\nint main(){int n; std::cin>>n; std::cout<<n;}')
    result = []
    for contract in ('stdin_stdout', 'function'):
        q = dict(base, type='coding')
        q['coding'] = dict(contract=contract, signature=dict(name='solve', parameters=[dict(name='value', type='integer')], return_type='integer') if contract == 'function' else None,
            harness_version='genhire_fn_v1', input_format='One integer', output_format='One integer', constraints='32-bit signed integer.',
            languages=list(TARGETS), runtime_versions=dict(TARGETS), starter_code=dict(references),
            reference_solutions=references if contract == 'function' else stdin,
            limits=dict(time_ms=2000, memory_mb=512, output_kb=64), comparison='trim_trailing_whitespace', tests=[
                dict(id=name, visibility=visibility, input=dict(value=n) if contract == 'function' else str(n),
                    expected=n if contract == 'function' else str(n), weight=1, explanation='')
                for name, visibility, n in [('sample1', 'sample', 2), ('hidden1', 'hidden', -9371)]])
        result.append((contract, validate_question(q), True, None))
    bad = deepcopy(result[0][1]); bad['title'] += ' wrong answer'
    for case in bad['coding']['tests']: case['expected'] = '99999'
    result.append(('wrong_answer', bad, False, 'output_mismatch'))
    timeout = deepcopy(result[0][1]); timeout['title'] += ' timeout'
    timeout['coding'].update(languages=['python'], runtime_versions={'python': '3.12'}, starter_code={'python': '# acceptance fixture'},
        reference_solutions={'python': 'while True: pass'})
    timeout['coding']['limits']['time_ms'] = 1000
    result.append(('code_timeout', timeout, False, 'time_limit'))
    for engine, version in [('postgresql', '17'), ('mysql', '8.4')]:
        q = dict(base, type='sql', sql=dict(engine=engine, engine_version=version, schema_sql='CREATE TABLE values_table (value INTEGER);',
            reference_query='SELECT value FROM values_table ORDER BY value', ordered=True, numeric_tolerance=0, time_ms=1000,
            datasets=[dict(id=name, visibility=visibility, seed_sql=f'INSERT INTO values_table VALUES ({n});', columns=['value'],
                expected_rows=[[n]], weight=1, explanation='') for name, visibility, n in [('sample1', 'sample', 2), ('hidden1', 'hidden', -9371)]]))
        result.append((engine, validate_question(q), True, None))
        denied = deepcopy(q); denied['title'] += ' reader DDL denial'; denied['sql']['reference_query'] = 'DROP TABLE values_table'
        result.append((engine + '_read_only', denied, False, 'runtime_error'))
        slow = deepcopy(q); slow['title'] += ' timeout'
        slow['sql']['reference_query'] = 'SELECT pg_sleep(5)' if engine == 'postgresql' else 'SELECT SLEEP(5)'
        result.append((engine + '_timeout', slow, False, ('time_limit', 'runtime_error')))
    return result


class ExecutorPreflight:
    def __init__(self, db):
        self.db = db
        self.validator = ManagedAssessmentValidator(db, validation_mode=True)

    def check_budget(self):
        """Read-only early guard; dispatches retain their atomic quota checks.

        Other traffic can consume quota after this snapshot. This prevents an
        already impossible recheck from spending calls or revoking acceptance.
        """
        questions = [question for _, question, _, _ in canaries('quota-plan')]
        needed = dict(sphere=2+sum(len(q['coding']['languages'])*len(q['coding']['tests']) for q in questions if q['type']=='coding'),
                      sql=sum(len(q['sql']['datasets']) for q in questions if q['type']=='sql'))
        month = datetime.now(timezone.utc).strftime('%Y-%m')
        for label, collection, key, maximum in (
            ('sphere', self.db.assessment_executor_limits, 'GENHIRE_SPHERE_MONTHLY_SUBMISSION_LIMIT', 500),
            ('sql', self.db.sql_execution_limits, 'GENHIRE_SQL_MONTHLY_EXECUTION_LIMIT', 200)):
            try: limit = int(os.getenv(key, str(maximum)))
            except ValueError: limit = 0
            if not 1 <= limit <= maximum: raise WorkflowError('invalid_preflight_quota', 'Configure supported pilot submission quotas before live acceptance.', 503)
            consumed = (collection.find_one({'_id': month}) or {}).get('count', 0)
            if type(consumed) is not int or consumed < 0: raise WorkflowError('invalid_preflight_quota', 'Usage counter requires operator reconciliation.', 503)
            if limit-consumed < needed[label]:
                raise WorkflowError('preflight_budget_insufficient', f'Full acceptance needs at least {needed["sphere"]} Sphere submissions and {needed["sql"]} SQL executions available; no canaries dispatched. Review quota/renewal policy.', 429)
        return needed

    def run(self, review):
        from config.assessment_execution import runtime_profiles
        review = security_review(review, os.getenv('GENHIRE_EXECUTOR_ISOLATION_POLICY_ID', ''))
        if not self.validator.capabilities()['available']:
            raise WorkflowError('execution_not_configured', 'Configure both managed providers and all four runtime pins before live acceptance.', 503)
        profile_hash = self.validator.profile_hash()
        self.check_budget()
        run_id = uuid.uuid4().hex
        self.db.assessment_executor_preflights.insert_one(dict(_id=run_id, profile_hash=profile_hash, state='running',
            security_review=review, created_at=datetime.now(timezone.utc)))
        self.db.assessment_executor_attestations.update_many({'profile_hash': profile_hash}, {'$set': {'state': 'checking'}})
        try:
            profiles = runtime_profiles()
            for product in ('compilers', 'problems'):
                catalog = self.validator.client(product).compilers()
                for language, profile in profiles.items():
                    compiler = next((c for c in catalog if c['id'] == profile['compiler_id']), None)
                    if (profile['runtime_label'] != TARGETS[language] or not compiler
                            or not any(v['id'] == profile['version_id'] and v['name'] == profile['version_name'] for v in compiler['versions'])):
                        raise WorkflowError('runtime_pin_mismatch', 'Configured runtime pins must match both live account catalogs and the approved targets.', 503)
            for name, q, expected, reason in canaries(run_id):
                evidence = verify_reference_results(q, self.validator.validate(q, request_identity(q)))
                allowed = reason if isinstance(reason, tuple) else (reason,)
                if (evidence['passed'] is not expected or (not expected and len(evidence['failures']) != evidence['cases_checked'])
                        or (reason and any(f['reason'] not in allowed for f in evidence['failures']))):
                    raise WorkflowError('live_canary_failed', 'A live executor correctness, timeout or privilege canary failed.', 503)
                self.db.assessment_executor_preflights.update_one({'_id': run_id}, {'$push': {'checks': dict(name=name, evidence=evidence)}})
            self.problems_canary(run_id)
            if self.validator.profile_hash() != profile_hash:
                raise WorkflowError('execution_profile_changed', 'Executor settings changed during validation.', 409)
            now = datetime.now(timezone.utc)
            self.db.assessment_executor_attestations.update_one({'profile_hash': profile_hash}, {'$set': dict(state='passed',
                preflight_id=run_id, verified_at=now, expires_at=now + timedelta(hours=24))}, upsert=True)
            self.db.assessment_executor_preflights.update_one({'_id': run_id}, {'$set': {'state': 'passed', 'completed_at': now}})
            return dict(preflight_id=run_id, state='passed', expires_in_hours=24)
        except Exception as exc:
            self.db.assessment_executor_preflights.update_one({'_id': run_id}, {'$set': {'state': 'failed',
                'error_code': exc.code if isinstance(exc, WorkflowError) else 'preflight_failed'}})
            # A failed recheck revokes prior acceptance for this exact profile.
            self.db.assessment_executor_attestations.update_many({'profile_hash': profile_hash}, {'$set': {'state': 'failed'}})
            raise

    def problems_canary(self, run_id):
        """Create a private operator fixture; record IDs before subsequent calls.

        Interrupted creation is never retried automatically. Retain IDs for
        account-side reconciliation/cleanup; these are not recruitment problems.
        """
        from config.assessment_execution import runtime_profiles
        client = self.validator.client('problems')
        try: master, judge = int(os.environ['SPHERE_MASTER_JUDGE_ID']), int(os.environ['SPHERE_TESTCASE_JUDGE_ID'])
        except (KeyError, ValueError): raise WorkflowError('judge_not_configured', 'Account-approved master/testcase judge IDs are required.', 503) from None
        self.db.assessment_executor_preflights.update_one({'_id': run_id}, {'$set': {'problem_dispatch': 'dispatching'}})
        problem_id = client.create_problem('GenHire acceptance ' + run_id, 'Echo one integer.', master)
        self.db.assessment_executor_preflights.update_one({'_id': run_id}, {'$set': {'problem_id': problem_id, 'problem_dispatch': 'created'}})
        numbers = [client.create_testcase(problem_id, str(n), str(n), 2, judge) for n in (2, -9371)]
        profile = runtime_profiles()['python']
        for correct in (True, False):
            key = request_identity(dict(preflight=run_id, problems=correct))
            if not self.validator.reserve_submission(key): raise WorkflowError('dispatch_pending', 'Canary already dispatched.', 409)
            source = 'print(int(input()))' if correct else 'print(99999)'
            submission_id = client.create_submission(source, profile['compiler_id'], profile['version_id'], problem_id=problem_id)
            self.db.assessment_executor_dispatches.update_one({'_id': key}, {'$set': {'state': 'running', 'submission_id': submission_id, 'product': 'problems'}})
            deadline = time.monotonic() + 180
            while True:
                time.sleep(2)
                result = client.submission(submission_id)
                if not result['executing']: break
                if time.monotonic() > deadline: raise WorkflowError('execution_pending', 'Problems canary is pending; reconcile recorded IDs.', 503)
            cases = result['testcases']
            passed = (len(cases) == len(numbers) and {c['number'] for c in cases} == set(numbers)
                and all(c['status_code'] == 15 for c in cases) and result['status_code'] == 15)
            if correct != passed or (not correct and not any(c['status_code'] == 14 for c in cases)):
                raise WorkflowError('problems_canary_failed', 'Problems API did not accept the reference and reject the wrong answer.', 503)
            self.db.assessment_executor_dispatches.update_one({'_id': key}, {'$set': {'state': 'complete', 'acceptance_check': True}})
