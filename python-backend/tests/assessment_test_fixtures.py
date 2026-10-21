def mcq():
    return dict(schema_version=1, type='mcq', title='Choose the even number', statement='Which value is even?',
        difficulty='easy', topics=['Numeracy'], marks=1, explanation='Private explanation: even values are divisible by two.',
        mcq=dict(selection='single', options=[dict(id='optionA', text='2'), dict(id='optionB', text='3')], correct_option_ids=['optionA']))


def coding(contract='stdin_stdout'):
    q = mcq()
    q.pop('mcq')
    q.update(type='coding', title='Echo a value', statement='Return the supplied integer.', topics=['Functions'])
    languages = ['python', 'javascript', 'java', 'cpp']
    references = dict(python='def solve(value):\n    return value', javascript='function solve(value) { return value; }',
        java='class Solution { public int solve(int value) { return value; } }', cpp='class Solution { public: int solve(int value) { return value; } };')
    q['coding'] = dict(contract=contract, signature=dict(name='solve', parameters=[dict(name='value', type='integer')], return_type='integer') if contract == 'function' else None,
        harness_version='genhire_fn_v1', input_format='One integer', output_format='One integer', constraints='32-bit integer input.',
        languages=languages, runtime_versions=dict(python='3.12', javascript='22', java='21', cpp='C++20'),
        starter_code={l: '// public starter' for l in languages}, reference_solutions=references,
        limits=dict(time_ms=2000, memory_mb=256, output_kb=64), comparison='exact', tests=[
            dict(id='sample1', visibility='sample', input={'value': 2} if contract == 'function' else '2', expected=2 if contract == 'function' else '2', weight=1, explanation='Sample explanation.'),
            dict(id='hidden1', visibility='hidden', input={'value': 9371} if contract == 'function' else 'PRIVATE_INPUT_9371', expected=9371 if contract == 'function' else 'PRIVATE_OUTPUT_9371', weight=2, explanation='PRIVATE_HIDDEN_EXPLANATION')])
    return q


def sql(engine='postgresql'):
    q = mcq()
    q.pop('mcq')
    q.update(type='sql', title='List values', statement='Return values in ascending order.', topics=['SQL'])
    q['sql'] = dict(engine=engine, engine_version='17' if engine == 'postgresql' else '8.4', schema_sql='CREATE TABLE values_table (value INTEGER);',
        reference_query='SELECT value FROM values_table ORDER BY value', ordered=True, numeric_tolerance=0, time_ms=2000,
        datasets=[dict(id='sample1', visibility='sample', seed_sql='INSERT INTO values_table VALUES (2);', columns=['value'], expected_rows=[[2]], weight=1, explanation='Sample'),
            dict(id='hidden1', visibility='hidden', seed_sql='INSERT INTO values_table VALUES (9371);', columns=['value'], expected_rows=[[9371]], weight=2, explanation='PRIVATE_HIDDEN_EXPLANATION')])
    return q


def executor_results(q):
    from services.workflow_service import request_identity
    c = q.get('coding')
    runs = []
    for runtime in c['languages'] if c else [q['sql']['engine']]:
        for case in c['tests'] if c else q['sql']['datasets']:
            row = dict(runtime=runtime, runtime_version=c['runtime_versions'][runtime] if c else q['sql']['engine_version'], case_id=case['id'], status='ok')
            if c:
                row.update(contract=c['contract'], harness_version=c['harness_version'])
                row['value' if c['contract'] == 'function' else 'stdout'] = case['expected']
            else: row.update(columns=case['columns'], rows=case['expected_rows'])
            runs.append(row)
    return dict(adapter_id='TEST_ONLY_FAKE', execution_id='fixture-execution', isolation_policy_id='TEST_ONLY_NOT_REAL_ISOLATION', question_hash=request_identity(q), runs=runs)
