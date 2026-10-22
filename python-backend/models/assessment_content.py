"""Private question contracts shared by manual entry and generated content.

No question text is evaluated or rendered as HTML. Executable content belongs
exclusively in an isolated validator, never in the Flask process.
"""
from copy import deepcopy
import json
import math
import re
from models.job_setup import fields, text, choice, integer, number, LANGUAGES, invalid

TYPES = ('integer', 'number', 'string', 'boolean', 'integer[]', 'number[]', 'string[]', 'boolean[]')
RESERVED = set('class public private protected static void return def import from function var let const new int double boolean bool string String for while if else switch case default try catch throw throws null None true false True False main self this args'.split())
RESERVED.update('abstract assert break byte char continue do enum extends final finally float implements import instanceof interface long native package short strictfp super synchronized transient volatile struct namespace template typename using unsigned signed auto delete operator virtual friend union typedef constexpr nullptr sizeof include yield await async lambda pass raise with as except global nonlocal and or not in is print'.split())
BASE = {'schema_version', 'type', 'title', 'statement', 'difficulty', 'topics', 'marks', 'explanation'}
PAYLOADS = {'mcq': 'mcq', 'coding': 'coding', 'sql': 'sql'}


def identifier(value, label):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_]{0,39}', value) or value in RESERVED or value.startswith('gh'):
        invalid(f'{label} must be a nonreserved identifier (1–40 characters).')
    return value


def bounded_text(value, label, limit, required=True):
    result = text(value, label, limit)
    if required and not result:
        invalid(f'{label} cannot be empty.')
    return result


def strings(value, label, limit=20):
    if not isinstance(value, list) or len(value) > limit:
        invalid(f'{label} must be a list of at most {limit} strings.')
    result = [bounded_text(item, label, 100) for item in value]
    if len(set(result)) != len(result):
        invalid(f'{label} cannot contain duplicates.')
    return result


def typed_value(value, kind, label):
    if kind.endswith('[]'):
        if not isinstance(value, list) or len(value) > 1000:
            invalid(f'{label} must be an array of at most 1000 values.')
        for item in value:
            typed_value(item, kind[:-2], label)
    elif kind == 'integer':
        integer(value, label, -2147483648, 2147483647)
    elif kind == 'number':
        number(value, label, -1e12, 1e12)
    elif kind == 'boolean':
        if type(value) is not bool:
            invalid(f'{label} must be a boolean.')
    else:
        text(value, label, 20000)


def signature(value):
    fields(value, {'name', 'parameters', 'return_type'}, 'Function signature', {'name', 'parameters', 'return_type'})
    identifier(value['name'], 'Function name')
    choice(value['return_type'], TYPES, 'return type')
    params = value['parameters']
    if not isinstance(params, list) or not 1 <= len(params) <= 8:
        invalid('Functions need 1–8 parameters.')
    names = set()
    for param in params:
        fields(param, {'name', 'type'}, 'Parameter', {'name', 'type'})
        identifier(param['name'], 'Parameter name')
        choice(param['type'], TYPES, 'parameter type')
        if param['name'] in names:
            invalid('Parameter names must be unique.')
        names.add(param['name'])
    return value


def test_cases(value, contract, sig=None):
    if not isinstance(value, list) or not 2 <= len(value) <= 40:
        invalid('Provide 2–40 tests, including at least one sample and one hidden test.')
    ids, visibility = set(), set()
    for test in value:
        fields(test, {'id', 'visibility', 'input', 'expected', 'weight', 'explanation'}, 'Test case',
               {'id', 'visibility', 'input', 'expected', 'weight', 'explanation'})
        identifier(test['id'], 'Test ID')
        if test['id'] in ids: invalid('Test IDs must be unique.')
        ids.add(test['id'])
        visibility.add(choice(test['visibility'], {'sample', 'hidden'}, 'test visibility'))
        number(test['weight'], 'Test weight', 0.01, 1000)
        bounded_text(test['explanation'], 'Test explanation', 2000, required=False)
        if contract == 'stdin_stdout':
            text(test['input'], 'Standard input', 20000)
            text(test['expected'], 'Expected output', 20000)
        else:
            params = sig['parameters']
            fields(test['input'], {p['name'] for p in params}, 'Function arguments', {p['name'] for p in params})
            for param in params: typed_value(test['input'][param['name']], param['type'], 'Function argument')
            typed_value(test['expected'], sig['return_type'], 'Expected return')
    if visibility != {'sample', 'hidden'}:
        invalid('At least one sample and one hidden test are required.')


def validate_question(value):
    if not isinstance(value, dict) or not isinstance(value.get('type'), str) or value.get('type') not in PAYLOADS:
        invalid('Choose MCQ, coding or SQL question type.')
    kind = value['type']
    keys = BASE | {PAYLOADS[kind]}
    result = deepcopy(fields(value, keys, 'Question', keys))
    integer(result['schema_version'], 'Question schema version', 1, 1)
    result['title'] = bounded_text(result['title'], 'Question title', 200)
    result['statement'] = bounded_text(result['statement'], 'Problem statement', 20000)
    choice(result['difficulty'], {'easy', 'medium', 'hard'}, 'difficulty')
    result['topics'] = strings(result['topics'], 'Topics')
    number(result['marks'], 'Question marks', 0.01, 1000)
    result['explanation'] = bounded_text(result['explanation'], 'Private answer explanation', 10000)
    if kind == 'mcq':
        mcq = fields(result['mcq'], {'selection', 'options', 'correct_option_ids'}, 'MCQ', {'selection', 'options', 'correct_option_ids'})
        choice(mcq['selection'], {'single', 'multiple'}, 'MCQ selection')
        if not isinstance(mcq['options'], list) or not 2 <= len(mcq['options']) <= 8:
            invalid('MCQs need 2–8 options.')
        ids, contents = [], []
        for option in mcq['options']:
            fields(option, {'id', 'text'}, 'Option', {'id', 'text'})
            ids.append(identifier(option['id'], 'Option ID'))
            option['text'] = bounded_text(option['text'], 'Option text', 2000)
            contents.append(option['text'].casefold())
        correct = strings(mcq['correct_option_ids'], 'Correct option IDs', 8)
        if len(set(ids)) != len(ids) or len(set(contents)) != len(contents) or not correct or not set(correct) <= set(ids):
            invalid('Options must be unique and the answer key must select existing options.')
        if mcq['selection'] == 'single' and len(correct) != 1:
            invalid('Single-correct questions need exactly one correct option.')
    elif kind == 'coding':
        keys = {'contract', 'signature', 'harness_version', 'input_format', 'output_format', 'constraints', 'languages',
                'runtime_versions', 'starter_code', 'reference_solutions', 'limits', 'comparison', 'tests'}
        coding = fields(result['coding'], keys, 'Coding question', keys)
        contract = choice(coding['contract'], {'stdin_stdout', 'function'}, 'coding contract')
        choice(coding['harness_version'], {'genhire_fn_v1'}, 'harness version')
        if contract == 'function': signature(coding['signature'])
        elif coding['signature'] is not None: invalid('Input/output questions have no function signature.')
        for name in ('input_format', 'output_format', 'constraints'):
            coding[name] = bounded_text(coding[name], name, 8000)
        languages = strings(coding['languages'], 'Languages', len(LANGUAGES))
        if not languages or not set(languages) <= set(LANGUAGES): invalid('Select supported coding languages.')
        if contract == 'function' and 'c' in languages: invalid('C questions use the stdin/stdout contract.')
        for name in ('runtime_versions', 'starter_code', 'reference_solutions'):
            fields(coding[name], languages, name, languages)
            for language, content in coding[name].items(): bounded_text(content, name, 64000 if name != 'runtime_versions' else 80)
        fields(coding['limits'], {'time_ms', 'memory_mb', 'output_kb'}, 'Execution limits', {'time_ms', 'memory_mb', 'output_kb'})
        integer(coding['limits']['time_ms'], 'Time limit', 100, 10000)
        integer(coding['limits']['memory_mb'], 'Memory limit', 64, 512)
        integer(coding['limits']['output_kb'], 'Output limit', 1, 64)
        choice(coding['comparison'], {'exact', 'trim_trailing_whitespace'}, 'output comparison')
        test_cases(coding['tests'], contract, coding['signature'])
    else:
        keys = {'engine', 'engine_version', 'schema_sql', 'reference_query', 'datasets', 'ordered', 'numeric_tolerance', 'time_ms'}
        sql = fields(result['sql'], keys, 'SQL question', keys)
        choice(sql['engine'], {'sqlite', 'duckdb', 'postgresql', 'mysql'}, 'SQL engine')
        bounded_text(sql['engine_version'], 'SQL engine version', 80)
        bounded_text(sql['schema_sql'], 'Schema SQL', 20000)
        bounded_text(sql['reference_query'], 'Reference query', 64000)
        if type(sql['ordered']) is not bool: invalid('SQL ordering must be a boolean.')
        number(sql['numeric_tolerance'], 'Numeric tolerance', 0, 0.001)
        integer(sql['time_ms'], 'SQL time limit', 100, 10000)
        datasets = sql['datasets']
        if not isinstance(datasets, list) or not 2 <= len(datasets) <= 20:
            invalid('SQL requires 2–20 datasets including sample and hidden fixtures.')
        ids, visibility, columns = set(), set(), None
        for data in datasets:
            keys = {'id', 'visibility', 'seed_sql', 'columns', 'expected_rows', 'weight', 'explanation'}
            fields(data, keys, 'SQL dataset', keys)
            identifier(data['id'], 'Dataset ID')
            if data['id'] in ids: invalid('Dataset IDs must be unique.')
            ids.add(data['id'])
            visibility.add(choice(data['visibility'], {'sample', 'hidden'}, 'dataset visibility'))
            bounded_text(data['seed_sql'], 'Seed SQL', 20000, required=False)
            cols = strings(data['columns'], 'Expected column names', 30)
            if not cols or (columns is not None and columns != cols): invalid('Datasets must declare consistent result columns.')
            columns = cols
            rows = data['expected_rows']
            if not isinstance(rows, list) or len(rows) > 1000: invalid('Expected results are limited to 1000 rows.')
            if sql['numeric_tolerance'] > 0 and len(rows) > 100:
                invalid('Positive numeric tolerance supports at most 100 expected rows per dataset.')
            for row in rows:
                if not isinstance(row, list) or len(row) != len(cols): invalid('Result row width must match columns.')
                for cell in row:
                    if cell is None: continue
                    if type(cell) in (int, float):
                        if not math.isfinite(cell) or abs(cell) > 1e12: invalid('Invalid SQL numeric result.')
                    elif type(cell) is not bool and (not isinstance(cell, str) or len(cell) > 2000): invalid('Unsupported SQL result value.')
            number(data['weight'], 'Dataset weight', 0.01, 1000)
            bounded_text(data['explanation'], 'Dataset explanation', 2000, required=False)
        if visibility != {'sample', 'hidden'}: invalid('SQL requires sample and hidden datasets.')
    if len(json.dumps(result, ensure_ascii=False, allow_nan=False).encode('utf-8')) > 512000:
        invalid('Question content exceeds 500 KiB.')
    return result


def candidate_question(value):
    """Allowlist-only serializer. Never call this an authorization check."""
    q = validate_question(value)
    public = {key: deepcopy(q[key]) for key in ('schema_version', 'type', 'title', 'statement', 'difficulty', 'topics', 'marks')}
    if q['type'] == 'mcq':
        public['mcq'] = {key: deepcopy(q['mcq'][key]) for key in ('selection', 'options')}
    elif q['type'] == 'coding':
        private = q['coding']
        public['coding'] = {key: deepcopy(private[key]) for key in ('contract', 'signature', 'harness_version', 'input_format',
            'output_format', 'constraints', 'languages', 'runtime_versions', 'starter_code', 'limits', 'comparison')}
        public['coding']['examples'] = [{key: deepcopy(test[key]) for key in ('input', 'expected', 'explanation')}
            for test in private['tests'] if test['visibility'] == 'sample']
    else:
        private = q['sql']
        public['sql'] = {key: deepcopy(private[key]) for key in ('engine', 'engine_version', 'schema_sql', 'ordered', 'numeric_tolerance', 'time_ms')}
        public['sql']['examples'] = [{key: deepcopy(data[key]) for key in ('seed_sql', 'columns', 'expected_rows', 'explanation')}
            for data in private['datasets'] if data['visibility'] == 'sample']
    return public


def blueprint_match(configuration, questions):
    """A publishable version exactly fulfils the recruiter's configured slots."""
    if not isinstance(questions, list) or len(questions) > 120: invalid('Invalid assessment questions.')
    for section in configuration['sections']:
        selected = [q for q in questions if q['type'] == section['type']]
        if len(selected) != section['count']: invalid('Question counts must match the saved OA blueprint.')
        for difficulty, count in section['difficulty'].items():
            if sum(q['difficulty'] == difficulty for q in selected) != count: invalid('Question difficulties must match the blueprint.')
        if [q['marks'] for q in selected] != section['marks']: invalid('Question marks must match the configured slot marks.')
    if any(q['type'] not in {s['type'] for s in configuration['sections']} for q in questions): invalid('Unexpected question type.')
    for q in questions:
        if q['type'] == 'coding' and (q['coding']['languages'] != configuration['languages'] or q['coding']['contract'] != configuration['coding_contract']):
            invalid('Coding contract and languages must match the blueprint.')
        if q['type'] == 'sql' and q['sql']['engine'] != configuration['sql_engine']: invalid('SQL dialect must match the blueprint.')
        if q['type'] == 'mcq' and configuration['mcq_mode'] != 'mixed' and q['mcq']['selection'] != configuration['mcq_mode']:
            invalid('MCQ selection mode must match the blueprint.')
