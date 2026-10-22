"""Explicit recruitment activation and private progression operations."""
from functools import wraps
from datetime import datetime
from bson import ObjectId
from flask import Blueprint, jsonify, request
from middleware.auth_middleware import token_required
from core.mongo_transactions import AtomicityUnavailable
from models.hiring_workflow import WorkflowError
from services.hiring_progression_service import scheduling_enabled, utc
from services.assessment_runtime_service import AssessmentRuntimeService
from services.assessment_public_run_service import AssessmentPublicRunService
from services.assessment_evaluation_service import AssessmentEvaluationService
from services.assessment_integrity_service import AssessmentIntegrityService, enabled as integrity_enabled
from services.assessment_media_service import AssessmentMediaService
from services.assessment_integrity_extras import AssessmentIntegrityExtras
from services.job_setup_service import JobSetupService
from services.assessment_authoring_service import object_id
from payment_module.services.billing_operation_service import BillingOperationError


def create_hiring_progression_routes(db):
    bp = Blueprint('hiring_progression', __name__, url_prefix='/api')
    service = AssessmentRuntimeService(db)
    runs = AssessmentPublicRunService(service)
    evaluation = AssessmentEvaluationService(service)
    integrity = AssessmentIntegrityService(service)
    media = AssessmentMediaService(integrity)
    extras = AssessmentIntegrityExtras(service)
    @bp.after_request
    def private_response(response):
        response.headers['Cache-Control'] = 'private, no-store'
        return response

    def json_value(value):
        if isinstance(value, ObjectId): return str(value)
        if isinstance(value, datetime): return utc(value).isoformat(timespec='milliseconds')
        if isinstance(value, list): return [json_value(v) for v in value]
        if isinstance(value, dict): return {k: json_value(v) for k, v in value.items()}
        return value

    def endpoint(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            try:
                result = fn(*args, **kwargs)
                if request.method == 'POST' and kwargs.get('application_id'):
                    from services.hiring_progression_service import notify_hiring_progress
                    notify_hiring_progress(db, kwargs['application_id'])
                return jsonify(json_value(result))
            except WorkflowError as exc: return jsonify(error=str(exc), error_code=exc.code), exc.status
            except AtomicityUnavailable: return jsonify(error='Transactional hiring storage is unavailable.', error_code='atomicity_unavailable'), 503
            except BillingOperationError as exc: return jsonify(error=str(exc), error_code='billing_operation_failed'), 409
        account_endpoint = token_required(wrapped)
        @wraps(fn)
        def authorized(*args, **kwargs):
            bearer = request.headers.get('Authorization', '')
            if bearer.startswith('OA '):
                if fn.__name__ not in {'invitation', 'start', 'attempt', 'answers', 'submit', 'run', 'run_result', 'evaluation_report', 'secure_preflight', 'integrity_events', 'camera_frame', 'mobile_pair', 'refresh_secure_session', 'evidence_privacy'}:
                    return jsonify(error='OA session cannot access this operation.', error_code='forbidden'), 403
                try:
                    actor = integrity.authenticate(bearer[3:])
                    integrity.authorize_path(actor, kwargs.get('invitation_id'), kwargs.get('attempt_id'))
                except WorkflowError as exc: return jsonify(error=str(exc), error_code=exc.code), exc.status
                return wrapped(actor, *args, **kwargs)
            if bearer.startswith('OA-Mobile '):
                if fn.__name__ != 'camera_frame': return jsonify(error='Companion access is camera-only.', error_code='forbidden'), 403
                try:
                    actor = media.mobile_actor(bearer[10:]); integrity.authorize_path(actor, kwargs.get('invitation_id'))
                except WorkflowError as exc: return jsonify(error=str(exc), error_code=exc.code), exc.status
                return wrapped(actor, *args, **kwargs)
            return account_endpoint(*args, **kwargs)
        return authorized

    def body(allowed):
        value = request.get_json(silent=True)
        if not isinstance(value, dict) or set(value)-set(allowed): raise WorkflowError('invalid_request', 'Provide supported JSON fields.', 400)
        return value

    @bp.get('/jobs/<job_id>/hiring-operations')
    @endpoint
    def overview(actor, job_id):
        service.setup.actor(actor)
        job = service.setup.job(job_id, actor)
        version = db.hiring_workflow_versions.find_one({'_id': object_id(job['active_hiring_version_id'])}) if job.get('active_hiring_version_id') else None
        content = list(db.assessment_versions.find({'pool': {'$ne': 'practice'}, 'setup_version_id': job.get('hiring_setup_version_id'), 'state': 'published'},
            {'_id': 1, 'created_at': 1, 'workspace_revision': 1}).sort('created_at', -1).limit(20))
        groups = list(db.application_stages.aggregate([{'$match': {'job_id': job_id, 'is_current': {'$ne': False}}},
            {'$group': {'_id': {'type': '$type', 'state': '$state', 'outcome': '$outcome'}, 'count': {'$sum': 1}}}]))
        window = db.oa_window_activations.find_one({'_id': str(version['_id'])}) if version else None
        return JobSetupService.serialize(dict(scheduling_enabled=scheduling_enabled(), active_version_id=str(version['_id']) if version else None,
            active_setup_version_id=version.get('setup_version_id') if version else None,
            active_oa_enabled=bool(version and version.get('assessment_version_id')),
            active_schedule=dict(version['configuration']['schedule'], **service.window(version)) if version else None,
            window_revision=(window or {}).get('revision', 0), manual_oa_authorized=(window or {}).get('opened', False),
            published_content=content, stage_counts=groups, existing_application_count=db.applications.count_documents({'job_id': job_id}),
            impact='Activation changes the version for future applications. Existing candidates need explicit enrollment; invitations and accepted attempts retain their version.'))

    @bp.post('/jobs/<job_id>/hiring-activation-quotes')
    @endpoint
    def quote(actor, job_id):
        data = body(('assessment_version_id',))
        return {'quote': service.activation_quote(actor, job_id, data.get('assessment_version_id'))}

    @bp.post('/hiring-activations')
    @endpoint
    def activate(actor):
        data = body(('quote_id', 'operation_key', 'accepted'))
        return service.activate(actor, data.get('quote_id'), data.get('operation_key'), data.get('accepted'))

    @bp.post('/applications/<application_id>/hiring-enrollment')
    @endpoint
    def enroll(actor, application_id):
        data = body(('operation_key', 'expected_revision'))
        return service.enroll(application_id, actor, data.get('operation_key'), data.get('expected_revision'))

    @bp.get('/applications/<application_id>/hiring-progress')
    @endpoint
    def progress(actor, application_id): return service.progress(actor, application_id)

    @bp.post('/applications/<application_id>/oa-invitations')
    @endpoint
    def invite(actor, application_id):
        data = body(('expected_revision', 'operation_key', 'reason'))
        return service.invite(actor, application_id, data.get('expected_revision'), data.get('operation_key'), data.get('reason'))

    @bp.get('/assessment-invitations/<invitation_id>')
    @endpoint
    def invitation(actor, invitation_id): return service.invitation(actor, invitation_id)

    @bp.post('/assessment-invitations/<invitation_id>/secure-launch')
    @endpoint
    def secure_launch(actor, invitation_id):
        data = body(('operation_key', 'mode'))
        return integrity.launch(actor, invitation_id, data.get('operation_key'), data.get('mode'))

    @bp.post('/assessment-launches/redeem')
    def redeem_launch():
        try:
            data = body(('invitation_id', 'launch_code', 'nonce', 'runtime_info'))
            return jsonify(json_value(integrity.redeem(data.get('invitation_id'), data.get('launch_code'), data.get('nonce'), data.get('runtime_info'))))
        except WorkflowError as exc: return jsonify(error=str(exc), error_code=exc.code), exc.status
        except AtomicityUnavailable: return jsonify(error='Transactional launch storage unavailable.'), 503

    @bp.post('/assessment-invitations/<invitation_id>/preflight')
    @endpoint
    def secure_preflight(actor, invitation_id):
        data = body(('consent_version', 'readiness'))
        return integrity.preflight(actor, invitation_id, data.get('consent_version'), data.get('readiness'))

    @bp.post('/assessment-invitations/<invitation_id>/session-refresh')
    @endpoint
    def refresh_secure_session(actor, invitation_id):
        integrity.authorize_path(actor, invitation_id)
        bound = actor.get('_oa_session')
        if not bound: raise WorkflowError('secure_session_required', 'A scoped OA session is required.', 403)
        attempt = db.assessment_attempts.find_one({'invitation_id': invitation_id})
        return dict(access_token=integrity.token(bound, attempt['deadline'] if attempt else None))

    @bp.post('/assessment-invitations/<invitation_id>/mobile-pair')
    @endpoint
    def mobile_pair(actor, invitation_id): return media.pair(actor, invitation_id)

    @bp.post('/assessment-invitations/<invitation_id>/camera-frame')
    @endpoint
    def camera_frame(actor, invitation_id):
        data = body(('operation_key', 'image'))
        return media.frame(actor, invitation_id, data.get('operation_key'), data.get('image'))

    @bp.post('/assessment-invitations/<invitation_id>/accommodation')
    @endpoint
    def accommodation(actor, invitation_id):
        data = body(('operation_key', 'expected_revision', 'reason', 'browser_allowed', 'camera_waived', 'extra_minutes'))
        return integrity.accommodate(actor, invitation_id, data.get('operation_key'), data.get('expected_revision'), data.get('reason'),
            data.get('browser_allowed'), data.get('camera_waived'), data.get('extra_minutes'))

    @bp.post('/assessment-invitations/<invitation_id>/start')
    @endpoint
    def start(actor, invitation_id):
        data = body(('operation_key', 'consent_version'))
        result = service.start(actor, invitation_id, data.get('operation_key'), data.get('consent_version'))
        if actor.get('_oa_session'): result['access_token'] = integrity.token(actor['_oa_session'], result['deadline'])
        return result

    @bp.post('/assessment-attempts/<attempt_id>/integrity-events')
    @endpoint
    def integrity_events(actor, attempt_id):
        data = body(('operation_key', 'observations'))
        return integrity.events(actor, attempt_id, data.get('operation_key'), data.get('observations'))

    @bp.get('/assessment-attempts/<attempt_id>/integrity')
    @endpoint
    def integrity_report(actor, attempt_id): return integrity.report(actor, attempt_id)

    @bp.post('/assessment-attempts/<attempt_id>/integrity-review')
    @endpoint
    def integrity_review(actor, attempt_id):
        data = body(('operation_key', 'expected_revision', 'decision', 'reason'))
        return integrity.review(actor, attempt_id, data.get('operation_key'), data.get('expected_revision'), data.get('decision'), data.get('reason'))

    @bp.post('/assessment-attempts/<attempt_id>/time-extension')
    @endpoint
    def time_extension(actor, attempt_id):
        data = body(('operation_key', 'expected_revision', 'minutes', 'reason'))
        return integrity.extend(actor, attempt_id, data.get('operation_key'), data.get('expected_revision'), data.get('minutes'), data.get('reason'))

    @bp.get('/assessment-attempts/<attempt_id>/evidence')
    @endpoint
    def evidence(actor, attempt_id): return media.evidence_access(actor, attempt_id, after=request.args.get('after'))

    @bp.get('/assessment-attempts/<attempt_id>/evidence/<media_id>')
    @endpoint
    def evidence_download(actor, attempt_id, media_id): return media.evidence_access(actor, attempt_id, media_id)

    @bp.post('/assessment-attempts/<attempt_id>/evidence-privacy')
    @endpoint
    def evidence_privacy(actor, attempt_id):
        data = body(('operation_key', 'action', 'reason', 'hold_days'))
        return media.privacy_action(actor, attempt_id, data.get('operation_key'), data.get('action'), data.get('reason'), data.get('hold_days', 0))

    @bp.post('/assessment-integrity-quotes')
    @endpoint
    def integrity_quote(actor):
        data = body(('kind', 'target_id', 'version_ids'))
        return extras.quote(actor, data.get('kind'), data.get('target_id'), data.get('version_ids'))

    @bp.post('/assessment-integrity-purchases')
    @endpoint
    def integrity_purchase(actor):
        data = body(('quote_id', 'operation_key', 'accepted'))
        return extras.confirm(actor, data.get('quote_id'), data.get('operation_key'), data.get('accepted'))

    @bp.get('/assessment-attempts/<attempt_id>/similarity')
    @endpoint
    def similarity_report(actor, attempt_id): return extras.report(actor, attempt_id)

    @bp.get('/assessment-attempts/<attempt_id>')
    @endpoint
    def attempt(actor, attempt_id): return service.view(actor, attempt_id)

    @bp.post('/assessment-attempts/<attempt_id>/answers')
    @endpoint
    def answers(actor, attempt_id):
        data = body(('expected_revision', 'operation_key', 'answers'))
        return service.save(actor, attempt_id, data.get('expected_revision'), data.get('operation_key'), data.get('answers'))

    @bp.post('/assessment-attempts/<attempt_id>/submit')
    @endpoint
    def submit(actor, attempt_id):
        data = body(('expected_revision',))
        return service.finalize(attempt_id, 'candidate', actor, data.get('expected_revision'))

    @bp.post('/assessment-attempts/<attempt_id>/runs')
    @endpoint
    def run(actor, attempt_id):
        data = body(('operation_key', 'question_id', 'answer', 'custom_input'))
        return runs.create(actor, attempt_id, data.get('operation_key'), data.get('question_id'), data.get('answer'), data.get('custom_input'))

    @bp.get('/assessment-attempts/<attempt_id>/runs/<run_id>')
    @endpoint
    def run_result(actor, attempt_id, run_id): return runs.result(actor, attempt_id, run_id)

    @bp.get('/assessment-attempts/<attempt_id>/evaluation')
    @endpoint
    def evaluation_report(actor, attempt_id): return evaluation.report(actor, attempt_id)

    @bp.post('/assessment-attempts/<attempt_id>/platform-failure')
    @endpoint
    def platform_failure(actor, attempt_id):
        data = body(('operation_key', 'reason'))
        return evaluation.platform_failure(actor, attempt_id, data.get('operation_key'), data.get('reason'))

    @bp.post('/assessment-executions/<task_id>/reconcile')
    @endpoint
    def reconcile_execution(actor, task_id):
        data = body(('action', 'operation_key', 'reason', 'provider_id'))
        return evaluation.execution.reconcile(actor, task_id, data.get('action'), data.get('operation_key'), data.get('reason'), data.get('provider_id'))

    @bp.get('/assessment-evaluation-operations')
    @endpoint
    def evaluation_operations(actor):
        from services.onlinecompiler_execution_provider import usage_summary
        if actor.get('user_type') != 'admin' or not ({'*', 'applications.read'} & set(actor.get('permissions', []))):
            raise WorkflowError('forbidden', 'Evaluation operations require administrator access.', 403)
        return dict(jobs=list(db.assessment_evaluation_jobs.aggregate([{'$group': {'_id': '$state', 'count': {'$sum': 1}}}])),
            executions=list(db.assessment_execution_tasks.aggregate([{'$group': {'_id': '$state', 'count': {'$sum': 1}}}])),
            capacity=list(db.assessment_execution_capacity.find({})),
            provider_usage=usage_summary(db),
            oldest_queued=db.assessment_execution_tasks.find_one({'state': 'queued'}, {'created_at': 1}, sort=[('created_at', 1)]))

    @bp.post('/hiring-versions/<version_id>/oa-window')
    @endpoint
    def change_window(actor, version_id):
        data = body(('operation_key', 'reason', 'expected_revision', 'opens_at', 'closes_at'))
        return service.change_window(actor, version_id, data.get('operation_key'), data.get('reason'), data.get('expected_revision'), data.get('opens_at'), data.get('closes_at'))

    return bp
