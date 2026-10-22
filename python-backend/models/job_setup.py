"""Role presets and strict hiring/OA configuration contracts (no question content)."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import math
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from models.hiring_workflow import WorkflowError, validate_stages

LANGUAGES = ['python', 'javascript', 'java', 'cpp', 'c', 'nodejs']
JOB_FIELDS = {'title', 'department', 'location', 'type', 'experience', 'salary', 'description',
              'skills', 'responsibilities', 'requirements', 'benefits', 'deadline', 'status',
              'minimum_cv_score', 'proctoring_config', 'gaze_proctoring'}
DATE_FIELDS = ('application_closes_at', 'screening_opens_at', 'screening_closes_at', 'oa_opens_at', 'oa_start_closes_at')


def invalid(message):
    raise WorkflowError('invalid_job_setup', message, 400)


def integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        invalid(f'{name} must be an integer from {low} to {high}.')
    return value


def number(value, name, low=0, high=100, optional=False):
    if value is None and optional:
        return None
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        invalid(f'{name} must be a finite number from {low} to {high}.')
    return value


def fields(value, allowed, name, required=None):
    if not isinstance(value, dict) or set(value) - set(allowed) or (required and not set(required) <= set(value)):
        invalid(f'{name} has missing or unsupported fields.')
    return value


def choice(value, options, name):
    if not isinstance(value, str) or value not in options:
        invalid(f'Unsupported {name}.')
    return value


def boolean(value, name):
    if type(value) is not bool:
        invalid(f'{name} must be a boolean.')
    return value


def text(value, name, limit):
    if not isinstance(value, str) or len(value) > limit:
        invalid(f'{name} must be text of at most {limit} characters.')
    return value.strip()


def instant(value, zone, name):
    if not isinstance(value, str) or len(value) > 40:
        invalid(f'{name} must be a date/time.')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        invalid(f'{name} must use ISO date/time format.')
    if parsed.tzinfo is None:
        first, second = parsed.replace(tzinfo=zone, fold=0), parsed.replace(tzinfo=zone, fold=1)
        if first.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != parsed:
            invalid(f'{name} is a nonexistent local time in this timezone.')
        if first.utcoffset() != second.utcoffset():
            invalid(f'{name} is ambiguous; choose another local time or supply an explicit UTC offset.')
        parsed = first
    return parsed.astimezone(timezone.utc)


def iso(value):
    return value.isoformat().replace('+00:00', 'Z')


def default_schedule(now=None, zone_name='Asia/Kolkata'):
    now = now or datetime.now(timezone.utc)
    zone = ZoneInfo(zone_name)
    close = now + timedelta(days=7)
    screening_close = close + timedelta(days=3)
    opening = (screening_close.astimezone(zone) + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    return dict(timezone=zone_name, application_mode='cohort', screening_mode='cohort', oa_activation='scheduled',
                application_closes_at=iso(close), screening_opens_at=iso(close), screening_closes_at=iso(screening_close),
                oa_opens_at=iso(opening.astimezone(timezone.utc)), oa_start_closes_at=iso(opening.astimezone(timezone.utc) + timedelta(hours=24)))


def section(kind, count, difficulty, marks, weight, minutes):
    return dict(type=kind, count=count, difficulty=dict(zip(('easy', 'medium', 'hard'), difficulty)),
                marks=marks, weight=weight, duration_minutes=minutes)


def template(template_id):
    presets = {
        'sde': ('Software Development Engineer', [section('coding', 3, (1, 1, 1), [20, 30, 50], 70, 60), section('mcq', 20, (5, 10, 5), [1]*20, 30, 30)]),
        'web_developer': ('Frontend / Backend / Full-Stack', [section('coding', 2, (1, 1, 0), [30, 50], 60, 60), section('mcq', 20, (5, 10, 5), [1]*20, 40, 30)]),
        'data_analyst': ('Data Analyst', [section('sql', 2, (1, 1, 0), [25, 25], 60, 40), section('mcq', 20, (5, 10, 5), [1]*20, 40, 30)]),
        'data_scientist': ('Data Science / ML Engineer', [section('coding', 2, (0, 2, 0), [50, 50], 50, 50), section('sql', 1, (0, 1, 0), [30], 20, 20), section('mcq', 20, (5, 10, 5), [1]*20, 30, 30)]),
        'devops': ('DevOps / Site Reliability Engineer', [section('coding', 1, (0, 1, 0), [40], 40, 30), section('mcq', 25, (5, 15, 5), [1]*25, 60, 40)]),
        'product': ('Product Manager', [section('mcq', 25, (5, 15, 5), [1]*25, 100, 45)]),
        'qa': ('QA / Automation Engineer', [section('coding', 1, (0, 1, 0), [40], 40, 30), section('mcq', 20, (5, 10, 5), [1]*20, 60, 30)]),
        'business_analyst': ('Business Analyst', [section('mcq', 25, (5, 15, 5), [1]*25, 100, 45)]),
        'ux_design': ('UX / Product Designer', [section('mcq', 20, (5, 10, 5), [1]*20, 100, 40)]),
        'security': ('Security Analyst', [section('mcq', 25, (5, 15, 5), [1]*25, 100, 45)]),
        'marketing': ('Marketing Specialist', [section('mcq', 20, (5, 10, 5), [1]*20, 100, 40)]),
        'sales': ('Sales Executive', [section('mcq', 20, (5, 10, 5), [1]*20, 100, 35)]),
        'hr': ('Human Resources Specialist', [section('mcq', 20, (5, 10, 5), [1]*20, 100, 35)]),
        'customer_support': ('Customer Support Specialist', [section('mcq', 20, (5, 10, 5), [1]*20, 100, 35)]),
        'finance': ('Finance Analyst', [section('mcq', 25, (5, 15, 5), [1]*25, 100, 45)]),
        'custom': ('Other / Custom Role', [section('mcq', 20, (5, 10, 5), [1]*20, 100, 40)]),
    }
    if template_id not in presets:
        invalid('Unknown role template.')
    name, sections = presets[template_id]
    return dict(id=template_id, name=name, sections=deepcopy(sections), duration_minutes=sum(s['duration_minutes'] for s in sections))


TEMPLATE_IDS = ['sde', 'web_developer', 'data_analyst', 'data_scientist', 'devops', 'product', 'qa', 'business_analyst',
                'ux_design', 'security', 'marketing', 'sales', 'hr', 'customer_support', 'finance', 'custom']


def default_setup(now=None):
    preset = template('sde')
    return dict(schema_version=1,
        pipeline=dict(oa_enabled=False, advancement='manual', company_stages=[]),
        qualification=dict(interview_minimum=60, require_proctoring=False, proctoring_minimum=70, oa_minimum=None),
        oa=dict(template_id='sde', specialization='general', source='ai', instructions='', languages=LANGUAGES[:4],
            sql_engine='sqlite', coding_contract='stdin_stdout', mcq_mode='single', sections=preset['sections'],
            timer_mode='shared', duration_minutes=preset['duration_minutes'], revisit_allowed=True,
            proctoring_level='basic', variant_count=1, advanced_analytics=False, plagiarism_check=False),
        schedule=default_schedule(now))


def validate_setup(value):
    result = deepcopy(fields(value, {'schema_version', 'pipeline', 'qualification', 'oa', 'schedule'}, 'Configuration',
                             {'schema_version', 'pipeline', 'qualification', 'oa', 'schedule'}))
    integer(result['schema_version'], 'Schema version', 1, 1)
    pipeline = fields(result['pipeline'], {'oa_enabled', 'advancement', 'company_stages'}, 'Pipeline', {'oa_enabled', 'advancement', 'company_stages'})
    boolean(pipeline['oa_enabled'], 'OA enabled')
    choice(pipeline['advancement'], {'manual', 'automatic'}, 'advancement mode')
    if not isinstance(pipeline['company_stages'], list) or len(pipeline['company_stages']) > 8:
        invalid('Provide at most eight company-managed stages.')
    for stage in pipeline['company_stages']:
        fields(stage, {'id', 'name'}, 'Company stage', {'id', 'name'})
        stage['name'] = text(stage['name'], 'Stage name', 80)
    qualification = fields(result['qualification'], {'interview_minimum', 'require_proctoring', 'proctoring_minimum', 'oa_minimum'}, 'Qualification',
                           {'interview_minimum', 'require_proctoring', 'proctoring_minimum', 'oa_minimum'})
    for key, fallback in (('interview_minimum', 60), ('proctoring_minimum', 70)):
        if qualification[key] is None:
            qualification[key] = fallback
    for key in ('interview_minimum', 'proctoring_minimum', 'oa_minimum'):
        number(qualification[key], key, optional=True)
    boolean(qualification['require_proctoring'], 'Require proctoring')
    if pipeline['advancement'] == 'automatic' and qualification['interview_minimum'] is None:
        invalid('Automatic advancement requires an explicit interview minimum.')
    if qualification['require_proctoring'] and qualification['proctoring_minimum'] is None:
        invalid('Required proctoring needs an explicit minimum.')
    oa = fields(result['oa'], set(default_setup()['oa']), 'OA', set(default_setup()['oa']))
    choice(oa['template_id'], TEMPLATE_IDS, 'template')
    choice(oa['specialization'], {'general', 'frontend', 'backend', 'full_stack'}, 'specialization')
    choice(oa['source'], {'ai', 'manual', 'hybrid'}, 'question source')
    oa['instructions'] = text(oa['instructions'], 'Assessment instructions', 4000)
    if not isinstance(oa['languages'], list) or any(not isinstance(x, str) or x not in LANGUAGES for x in oa['languages']) or len(set(oa['languages'])) != len(oa['languages']):
        invalid('Choose unique supported programming languages.')
    choice(oa['sql_engine'], {'sqlite', 'duckdb', 'postgresql', 'mysql'}, 'SQL engine')
    choice(oa['coding_contract'], {'stdin_stdout', 'function'}, 'coding contract')
    if oa['coding_contract']=='function' and 'c' in oa['languages']: invalid('C questions use standard input/output.')
    choice(oa['mcq_mode'], {'single', 'multiple', 'mixed'}, 'MCQ mode')
    choice(oa['timer_mode'], {'shared', 'section'}, 'timer mode')
    choice(oa['proctoring_level'], {'basic', 'camera', 'dual'}, 'proctoring level')
    integer(oa['duration_minutes'], 'Total OA minutes', 5, 300)
    integer(oa['variant_count'], 'Variant count', 1, 5)
    for key in ('revisit_allowed', 'advanced_analytics', 'plagiarism_check'):
        boolean(oa[key], key)
    if oa['timer_mode'] == 'section' and oa['revisit_allowed']:
        invalid('Fixed section timers cannot allow return to closed sections.')
    if not isinstance(oa['sections'], list) or not 1 <= len(oa['sections']) <= 3:
        invalid('Provide one to three objective sections.')
    types, total, weights, minutes = set(), 0, 0, 0
    for item in oa['sections']:
        fields(item, {'type', 'count', 'difficulty', 'marks', 'weight', 'duration_minutes'}, 'Section',
               {'type', 'count', 'difficulty', 'marks', 'weight', 'duration_minutes'})
        kind = choice(item['type'], {'coding', 'mcq', 'sql'}, 'section type')
        if kind in types:
            invalid('Each section type may appear only once.')
        types.add(kind)
        count = integer(item['count'], 'Question count', 0, 100 if kind == 'mcq' else 10)
        diff = fields(item['difficulty'], {'easy', 'medium', 'hard'}, 'Difficulty distribution', {'easy', 'medium', 'hard'})
        if sum(integer(v, 'Difficulty count', 0, 100) for v in diff.values()) != count:
            invalid('Difficulty counts must sum to the section question count.')
        if not isinstance(item['marks'], list) or len(item['marks']) != count:
            invalid('Provide exactly one mark value per question.')
        for mark in item['marks']:
            number(mark, 'Question marks', 0.01, 1000)
        number(item['weight'], 'Section weight')
        integer(item['duration_minutes'], 'Section minutes', 0 if count == 0 else 1, 300)
        if count == 0 and (item['weight'] != 0 or item['duration_minutes'] != 0):
            invalid('Empty sections must have zero weight and zero duration.')
        if count and item['weight'] <= 0:
            invalid('Nonempty sections need a positive score weight.')
        total += count
        weights += item['weight']
        minutes += item['duration_minutes']
        if kind == 'coding' and count and not oa['languages']:
            invalid('Coding questions require at least one supported language.')
    if total > 120 or (pipeline['oa_enabled'] and total == 0):
        invalid('An enabled OA needs 1–120 questions within section limits.')
    if total and not math.isclose(weights, 100, abs_tol=1e-8):
        invalid('Nonempty section weights must sum to 100%.')
    if oa['timer_mode'] == 'section' and minutes != oa['duration_minutes']:
        invalid('Section durations must sum to the total OA duration.')
    schedule = fields(result['schedule'], set(DATE_FIELDS) | {'timezone', 'application_mode', 'screening_mode', 'oa_activation'}, 'Schedule',
                      set(DATE_FIELDS) | {'timezone', 'application_mode', 'screening_mode', 'oa_activation'})
    try:
        zone = ZoneInfo(text(schedule['timezone'], 'Timezone', 80))
    except (ZoneInfoNotFoundError, ValueError):
        invalid('Choose a valid IANA timezone.')
    schedule['timezone'] = zone.key
    choice(schedule['application_mode'], {'cohort', 'rolling'}, 'application mode')
    choice(schedule['screening_mode'], {'cohort', 'rolling'}, 'screening mode')
    choice(schedule['oa_activation'], {'scheduled', 'manual'}, 'OA activation')
    dates = {key: instant(schedule[key], zone, key) for key in DATE_FIELDS}
    if schedule['screening_mode'] == 'cohort' and dates['screening_opens_at'] < dates['application_closes_at']:
        invalid('Cohort screening cannot open before applications close.')
    if dates['screening_closes_at'] <= dates['screening_opens_at']:
        invalid('Screening must close after it opens.')
    if dates['oa_opens_at'] < dates['screening_closes_at'] or dates['oa_start_closes_at'] <= dates['oa_opens_at']:
        invalid('OA must open after screening and close entry after opening.')
    schedule.update({key: iso(val) for key, val in dates.items()})
    validate_stages(pipeline_stages(result))
    return result


def pipeline_stages(setup):
    q = setup['qualification']
    policy = {key: q[key] for key in ('interview_minimum', 'require_proctoring', 'proctoring_minimum')}
    policy['auto_invite'] = setup['pipeline']['advancement'] == 'automatic'
    stages = [dict(id='application_review', type='application_review', name='Application review'),
              dict(id='screening', type='screening', name='AI screening', policy=policy)]
    if setup['pipeline']['oa_enabled']:
        stages.append(dict(id='oa', type='oa', name='Online assessment'))
    stages += [dict(s, type='company') for s in setup['pipeline']['company_stages']]
    return stages


def validate_job_fields(value):
    fields(value, JOB_FIELDS, 'Job draft')
    result = deepcopy(value)
    for key, val in result.items():
        if key == 'minimum_cv_score':
            # Existing forms send numeric input values as strings.
            try:
                if type(val) is bool:
                    invalid('Invalid CV minimum.')
                number(float(val), key)
            except (ValueError, TypeError):
                invalid('Invalid CV minimum.')
        elif key in {'proctoring_config', 'gaze_proctoring'}:
            from services.interview_flow_service import normalize_proctoring_config, DEFAULT_PROCTORING_CONFIG
            if key == 'proctoring_config':
                fields(val, DEFAULT_PROCTORING_CONFIG, 'Screening proctoring')
                try:
                    normalize_proctoring_config(val)
                except ValueError as exc:
                    invalid(str(exc))
            else:
                boolean(val, key)
        elif isinstance(val, list) and key in {'skills', 'responsibilities', 'requirements', 'benefits'}:
            if len(val) > 200:
                invalid('Too many job list items.')
            for item in val:
                text(item, key, 2000)
        else:
            text(val, key, 20000 if key in {'description', 'responsibilities', 'requirements', 'benefits'} else 500)
    return result
