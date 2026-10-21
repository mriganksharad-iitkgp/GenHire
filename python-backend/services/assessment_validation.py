"""Check trusted isolated-executor evidence against immutable private fixtures.

There is intentionally no local execution fallback. A configured managed adapter
must return actual per-case results; a boolean 'passed' is never evidence.
"""
from collections import Counter
import json
import math
from models.assessment_content import typed_value, validate_question
from models.hiring_workflow import WorkflowError
from services.workflow_service import request_identity


def unavailable():
    raise WorkflowError('invalid_validator_evidence', 'Executor evidence is incomplete or incompatible; publication remains blocked.', 503)


def stdout_equal(actual, expected, mode):
    if not isinstance(actual, str): return False
    if mode == 'exact': return actual == expected
    normalize = lambda s: '\n'.join(line.rstrip(' \t') for line in s.replace('\r\n', '\n').split('\n')).rstrip('\n')
    return normalize(actual) == normalize(expected)


def sql_rows_equal(actual, expected, ordered, tolerance):
    if not isinstance(actual, list) or len(actual) != len(expected): return False
    if not all(isinstance(row, list) and len(row) == (len(expected[0]) if expected else 0) for row in actual): return False
    def row_equal(a, b):
        for x, y in zip(a, b):
            if type(x) in (int, float) and type(y) in (int, float):
                if not math.isfinite(x) or abs(x - y) > tolerance: return False
            elif type(x) is not type(y) or x != y: return False
        return True
    if ordered: return all(row_equal(a, b) for a, b in zip(actual, expected))
    if tolerance == 0:
        # Tag bool/null/string separately; numeric 1 and 1.0 are equivalent.
        def key(row):
            return tuple(('number', cell) if type(cell) in (int, float) else (type(cell).__name__, cell) for cell in row)
        try: return Counter(map(key, actual)) == Counter(map(key, expected))
        except (TypeError, ValueError): return False
    # Exact bipartite matching preserves duplicates and handles overlapping numeric
    # tolerances. Positive-tolerance fixtures are capped at 100 rows by the schema.
    if len(actual) > 100: return False
    edges = [[j for j, row in enumerate(expected) if row_equal(value, row)] for value in actual]
    matched = {}
    def visit(i, seen):
        for j in edges[i]:
            if j not in seen:
                seen.add(j)
                if j not in matched or visit(matched[j], seen):
                    matched[j] = i
                    return True
        return False
    return all(visit(i, set()) for i in range(len(actual)))


def verify_reference_results(question, result):
    q = validate_question(question)
    if q['type'] == 'mcq': unavailable()
    if not isinstance(result, dict) or result.get('question_hash') != request_identity(q): unavailable()
    for name in ('adapter_id', 'execution_id', 'isolation_policy_id'):
        if not isinstance(result.get(name), str) or not 1 <= len(result[name]) <= 200: unavailable()
    runs = result.get('runs')
    coding = q.get('coding')
    cases = coding['tests'] if coding else q['sql']['datasets']
    languages = coding['languages'] if coding else [q['sql']['engine']]
    if not isinstance(runs, list) or len(runs) != len(cases) * len(languages): unavailable()
    expected = {(language, case['id']): case for language in languages for case in cases}
    failures, seen = [], set()
    for run in runs:
        if not isinstance(run, dict): unavailable()
        language, case_id = run.get('runtime'), run.get('case_id')
        if not isinstance(language, str) or not isinstance(case_id, str): unavailable()
        identity = language, case_id
        if identity not in expected or identity in seen: unavailable()
        seen.add(identity)
        version = coding['runtime_versions'][language] if coding else q['sql']['engine_version']
        if run.get('runtime_version') != version: unavailable()
        if coding and (run.get('contract') != coding['contract'] or run.get('harness_version') != coding['harness_version']): unavailable()
        status = run.get('status')
        if not isinstance(status, str) or status not in {'ok', 'time_limit', 'memory_limit', 'compile_error', 'runtime_error', 'output_limit'}: unavailable()
        passed = status == 'ok'
        case = expected[identity]
        if passed and coding:
            if coding['contract'] == 'stdin_stdout':
                passed = stdout_equal(run.get('stdout'), case['expected'], coding['comparison'])
            else:
                try:
                    typed_value(run.get('value'), coding['signature']['return_type'], 'Reference return')
                    passed = run['value'] == case['expected']
                except WorkflowError: passed = False
        elif passed:
            sql = q['sql']
            passed = run.get('columns') == case['columns'] and sql_rows_equal(run.get('rows'), case['expected_rows'], sql['ordered'], sql['numeric_tolerance'])
        if not passed: failures.append(dict(runtime=language, case_id=case_id, reason=status if status != 'ok' else 'output_mismatch'))
    return dict(passed=not failures, execution_verified=True, validator=result['adapter_id'],
        execution_id=result['execution_id'], isolation_policy_id=result['isolation_policy_id'],
        question_hash=result['question_hash'], coverage=[f'{lang}:{case}' for lang, case in sorted(seen)],
        cases_checked=len(runs), failures=failures)
