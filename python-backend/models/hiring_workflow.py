"""Validated, versioned workflow contracts. No media/provider imports."""
from copy import deepcopy
import math
import re

STATES = {'not_ready', 'eligible', 'invited', 'in_progress', 'submitted',
          'evaluating', 'completed', 'expired', 'cancelled', 'skipped'}
OUTCOMES = {'pending', 'cleared', 'not_cleared', 'review_required'}
TYPES = {'application_review', 'screening', 'oa', 'company'}
LIFECYCLES = {'active', 'withdrawn', 'rejected', 'hired', 'closed'}
ATTEMPT_POLICY = {
    'schema_version': 1,
    'recruitment_attempts': 1,
    'oa_start_cutoff_exclusive': True,
    'oa_full_duration_after_valid_start': True,
    'screening_finish_by_close': True,
    'disconnect_pauses_timer': False,
    'technical_retake_requires_review': True,
}


class WorkflowError(ValueError):
    def __init__(self, code, message, status=409):
        super().__init__(message)
        self.code, self.status = code, status


def validate_stages(stages):
    if not isinstance(stages, list) or not 2 <= len(stages) <= 12:
        raise WorkflowError('invalid_pipeline', 'Provide 2–12 stages.', 400)
    result, ids = [], set()
    for stage in stages:
        if not isinstance(stage, dict) or set(stage) - {'id', 'type', 'name', 'enabled', 'policy'}:
            raise WorkflowError('invalid_pipeline', 'Unknown stage fields.', 400)
        sid, kind = stage.get('id'), stage.get('type')
        name = stage.get('name')
        if (not isinstance(sid, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,47}', sid)
                or sid in ids or kind not in TYPES or not isinstance(name, str)
                or not 1 <= len(name.strip()) <= 80 or not isinstance(stage.get('enabled', True), bool)):
            raise WorkflowError('invalid_pipeline', 'Invalid stage identity/type/name/enabled.', 400)
        ids.add(sid)
        policy = deepcopy(stage.get('policy', {}))
        if not isinstance(policy, dict) or set(policy) - {'interview_minimum', 'proctoring_minimum', 'require_proctoring', 'auto_invite'}:
            raise WorkflowError('invalid_policy', 'Unknown qualification policy fields.', 400)
        for key in ('interview_minimum', 'proctoring_minimum'):
            value = policy.get(key)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (float, int))
                                      or not math.isfinite(value) or not 0 <= value <= 100):
                raise WorkflowError('invalid_policy', 'Thresholds must be finite numbers from 0 to 100.', 400)
        for key in ('require_proctoring', 'auto_invite'):
            if key in policy and not isinstance(policy[key], bool):
                raise WorkflowError('invalid_policy', 'Policy flags must be booleans.', 400)
        if policy.get('require_proctoring') and policy.get('proctoring_minimum') is None:
            raise WorkflowError('invalid_policy', 'Required proctoring needs an explicit minimum.', 400)
        if policy.get('auto_invite') and policy.get('interview_minimum') is None:
            raise WorkflowError('invalid_policy', 'Automatic progression needs an explicit interview minimum.', 400)
        result.append(dict(id=sid, type=kind, name=name.strip(), enabled=stage.get('enabled', True), policy=policy))
    kinds = [s['type'] for s in result]
    if (kinds[:2] != ['application_review', 'screening'] or not all(s['enabled'] for s in result[:2])
            or any(kinds.count(k) != 1 for k in ('application_review', 'screening')) or kinds.count('oa') > 1
            or ('oa' in kinds and 'company' in kinds and kinds.index('oa') > kinds.index('company'))):
        raise WorkflowError('invalid_pipeline', 'Start with review and screening; optional OA precedes company stages.', 400)
    return result


def screening_only():
    return validate_stages([
        {'id': 'application_review', 'type': 'application_review', 'name': 'Application review'},
        {'id': 'screening', 'type': 'screening', 'name': 'AI screening'},
    ])


def legacy_snapshot(application, stages):
    """Import only defensible evidence; never fabricate historical timestamps."""
    status = application.get('status', 'pending')
    status = 'screening_cleared' if status == 'selected' else status
    if status not in {'pending', 'reviewed', 'shortlisted', 'interviewed', 'screening_cleared', 'rejected'}:
        raise WorkflowError('ambiguous_legacy', 'Unknown legacy application status.')
    score = application.get('interview_score')
    has_score = (not isinstance(score, bool) and isinstance(score, (float, int))
                 and math.isfinite(score) and 0 <= score <= 100)
    if status in {'interviewed', 'screening_cleared'} and not has_score:
        raise WorkflowError('ambiguous_legacy', 'Screening status has no usable interview result.')
    if status == 'rejected' and not has_score and not application.get('status_reason'):
        raise WorkflowError('ambiguous_legacy', 'Rejection stage cannot be inferred without evidence.')
    instances = []
    for definition in stages:
        state, outcome = 'not_ready', 'pending'
        if definition['type'] == 'application_review':
            state = 'completed' if status not in {'pending'} else 'eligible'
            outcome = 'not_cleared' if status == 'rejected' and not has_score else ('cleared' if state == 'completed' else 'pending')
        elif definition['type'] == 'screening':
            state = 'completed' if has_score else ('eligible' if status == 'shortlisted' else 'not_ready')
            outcome = ('cleared' if status == 'screening_cleared' else 'not_cleared' if status == 'rejected'
                       else 'review_required') if has_score else 'pending'
        instances.append(dict(stage_id=definition['id'], type=definition['type'], name=definition['name'],
                              enabled=definition['enabled'], state=state if definition['enabled'] else 'skipped', outcome=outcome))
    current = stages[0]['id'] if status in {'pending', 'reviewed'} or (status == 'rejected' and not has_score) else stages[1]['id']
    return dict(schema_version=1, revision=0, current_stage_id=current,
                lifecycle='rejected' if status == 'rejected' else 'active', stages=instances,
                imported_status=application.get('status'), provenance='legacy_snapshot')


def projection(workflow):
    """Legacy status is a compatibility projection, never the workflow source."""
    stage = next(s for s in workflow['stages'] if s['stage_id'] == workflow['current_stage_id'])
    if workflow['lifecycle'] == 'rejected':
        status = 'rejected'
    elif stage['type'] in {'oa', 'company'}:
        status = 'screening_cleared'
    elif stage['type'] == 'screening':
        status = 'screening_cleared' if stage['outcome'] == 'cleared' else 'interviewed' if stage['state'] == 'completed' else 'shortlisted'
    else:
        status = 'reviewed' if stage['state'] == 'completed' else 'pending'
    if workflow['lifecycle'] != 'active':
        label = {'withdrawn': 'Application withdrawn', 'rejected': 'Not progressing',
                 'hired': 'Hired — recorded by recruiter', 'closed': 'Application closed'}[workflow['lifecycle']]
    elif stage['type'] == 'screening' and stage['state'] == 'expired':
        label = 'Screening window expired — awaiting recruiter review'
    elif stage['outcome'] == 'review_required':
        label = f"{stage['name']} — awaiting recruiter review"
    elif stage['outcome'] == 'cleared':
        label = ('Screening cleared' if stage['type'] == 'screening' else f"{stage['name']} cleared") + ' — awaiting recruiter decision'
    elif stage['outcome'] == 'not_cleared':
        label = f"{stage['name']} not cleared"
    elif stage['type'] == 'oa' and stage['state'] == 'eligible':
        label = 'OA eligible — awaiting invitation'
    elif stage['type'] == 'oa' and stage['state'] == 'invited':
        label = 'Invited to online assessment — check your entry window'
    elif stage['type'] == 'oa' and stage['state'] == 'expired':
        label = 'OA entry window expired — awaiting recruiter decision'
    elif stage['type'] == 'oa' and stage['state'] == 'in_progress':
        label = 'Online assessment in progress'
    elif stage['type'] == 'oa' and stage.get('result_release_pending'):
        label = 'OA evaluated — awaiting recruiter result release'
    else:
        label = f"{stage['name']} — {stage['state'].replace('_', ' ')}"
    return dict(status=status, workflow_label=label)
