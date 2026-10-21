"""Pure deterministic OA scoring. No provider, database or AI dependencies."""
from decimal import Decimal, ROUND_HALF_UP
import json
from models.assessment_content import typed_value
from models.hiring_workflow import WorkflowError
from services.assessment_validation import stdout_equal, sql_rows_equal


def decimal(value):
    return Decimal(str(value))


def rounded(value):
    return float(value.quantize(Decimal('.0001'), rounding=ROUND_HALF_UP))


def fixtures(question):
    # Coding marks use hidden tests only. SQL uses its explicitly weighted
    # validated datasets, including the public sample, as saved by the author.
    if question['type'] == 'coding': return [t for t in question['coding']['tests'] if t['visibility'] == 'hidden']
    if question['type'] == 'sql': return question['sql']['datasets']
    return []


def comparison(question, case, output):
    if output.get('status') != 'ok': return False
    if question['type'] == 'sql':
        sql = question['sql']
        return output.get('columns') == case['columns'] and sql_rows_equal(output.get('rows'), case['expected_rows'], sql['ordered'], sql['numeric_tolerance'])
    coding = question['coding']
    if coding['contract'] == 'stdin_stdout': return stdout_equal(output.get('stdout'), case['expected'], coding['comparison'])
    try:
        value = json.loads(output['stdout'], parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        typed_value(value, coding['signature']['return_type'], 'Candidate return')
        return value == case['expected']
    except (ValueError, TypeError, KeyError, WorkflowError): return False


def score(configuration, questions, answers, results):
    """No partial overall score: absent/unavailable execution keeps it pending."""
    rows, precise = [], {}
    for identifier, question in questions.items():
        maximum = decimal(question['marks']); answer = answers.get(identifier)
        earned, state = Decimal(0), 'unanswered'
        if question['type'] == 'mcq':
            if answer and answer.get('option_ids'):
                earned = maximum if set(answer['option_ids']) == set(question['mcq']['correct_option_ids']) else Decimal(0)
                state = 'graded'
        elif answer and answer.get('source', '').strip():
            cases = fixtures(question); evidence = [results.get((identifier, c['id'])) for c in cases]
            if any(not r or r.get('status') == 'infrastructure_error' or type(r.get('passed')) is not bool for r in evidence):
                earned = None; state = 'unavailable'
            else:
                total = sum((decimal(c['weight']) for c in cases), Decimal(0))
                earned = maximum * sum((decimal(c['weight']) for c, r in zip(cases, evidence) if r['passed']), Decimal(0)) / total
                state = 'graded'
        precise[identifier] = earned
        rows.append(dict(question_version_id=identifier, type=question['type'], marks=rounded(maximum), earned=rounded(earned) if earned is not None else None, state=state))
    sections, aggregate, complete = [], Decimal(0), True
    for section in configuration['sections']:
        selected = [r for r in rows if r['type'] == section['type']]
        possible = sum((decimal(r['marks']) for r in selected), Decimal(0))
        available = all(precise[r['question_version_id']] is not None for r in selected)
        earned = sum((precise[r['question_version_id']] for r in selected), Decimal(0)) if available else None
        percentage = earned / possible * 100 if earned is not None and possible else None
        complete = complete and percentage is not None
        if percentage is not None: aggregate += percentage * decimal(section['weight']) / 100
        sections.append(dict(type=section['type'], possible=rounded(possible), earned=rounded(earned) if earned is not None else None,
            percentage=rounded(percentage) if percentage is not None else None, weight=section['weight']))
    return dict(schema_version=1, state='complete' if complete else 'unavailable', score=rounded(aggregate) if complete else None, questions=rows, sections=sections)
