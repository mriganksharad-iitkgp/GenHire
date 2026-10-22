"""Hiring configuration drafts and nonbinding price previews."""
import json
from functools import wraps
from flask import Blueprint, jsonify, request
from middleware.auth_middleware import token_required
from core.mongo_transactions import AtomicityUnavailable
from models.hiring_workflow import WorkflowError
from services.job_setup_service import JobSetupService, catalog, quote


def create_job_setup_routes(db):
    bp = Blueprint('job_setup', __name__, url_prefix='/api')
    service = JobSetupService(db)
    from services.job_draft_generation_service import JobDraftGenerationService
    generation = JobDraftGenerationService(db)

    def endpoint(fn):
        @wraps(fn)
        def wrapped(actor, *args, **kwargs):
            try:
                service.actor(actor)
                return jsonify(fn(actor, *args, **kwargs))
            except WorkflowError as exc:
                return jsonify(error=str(exc), error_code=exc.code), exc.status
            except AtomicityUnavailable:
                return jsonify(error='Transactional storage is unavailable; draft was not partially saved.',
                               error_code='atomicity_unavailable'), 503
        return token_required(wrapped)

    def body(allowed):
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or set(data) - set(allowed):
            raise WorkflowError('invalid_request', 'Provide a JSON object with supported fields.', 400)
        return data

    @bp.post('/job-draft-generations')
    @endpoint
    def create_ai_draft(actor):
        if request.is_json:
            data = body({'prompt', 'configuration', 'operation_key', 'accepted_credits'})
            document = ''
        else:
            try:
                data = dict(prompt=request.form.get('prompt', ''), configuration=json.loads(request.form.get('configuration', 'null')),
                    operation_key=request.form.get('operation_key'), accepted_credits=json.loads(request.form.get('accepted_credits', 'null')))
            except (ValueError, TypeError):
                raise WorkflowError('invalid_request', 'Invalid AI drafting configuration.', 400) from None
            file = request.files.get('jd_file')
            document = ''
            if file:
                if len(file.read(10 * 1024 * 1024 + 1)) > 10 * 1024 * 1024:
                    raise WorkflowError('invalid_file', 'JD files must be at most 10MB.', 400)
                file.seek(0)
                from routes.job_routes import job_controller
                document = job_controller._extract_jd_file_text(file)
                if not document:
                    raise WorkflowError('invalid_file', 'Upload a readable PDF/TXT document.', 400)
                document = document[:12000]
        return {'generation': generation.enqueue(actor, data.get('prompt'), data.get('configuration'),
            data.get('operation_key'), data.get('accepted_credits'), document)}

    @bp.get('/job-draft-generations/<key>')
    @endpoint
    def get_ai_draft(actor, key):
        return {'generation': generation.get(actor, key)}

    @bp.get('/job-draft-generations/active')
    @endpoint
    def active_ai_draft(actor):
        return {'generation': generation.active(actor)}

    @bp.post('/job-draft-generations/<key>/cancel')
    @endpoint
    def cancel_ai_draft(actor, key):
        return {'generation': generation.cancel(actor, key)}

    @bp.post('/job-setup/templates/<role>/apply')
    @endpoint
    def apply_role_template(actor, role):
        from services.assessment_authoring_service import AssessmentAuthoringService
        from services.role_assessment_templates import apply_template
        data = body({'operation_key', 'sql_engine', 'languages', 'specialization'})
        return apply_template(AssessmentAuthoringService(db), actor, role, data.get('operation_key'),
            data.get('sql_engine', 'sqlite'), data.get('languages'), data.get('specialization', 'general'))

    @bp.get('/job-setup/catalog')
    @endpoint
    def get_catalog(actor):
        return catalog()

    @bp.post('/job-setup/preview')
    @endpoint
    def preview(actor):
        service.enabled()
        from models.job_setup import validate_setup, pipeline_stages
        data = body({'configuration'})
        configuration = validate_setup(data.get('configuration'))
        return dict(configuration=configuration, pipeline=pipeline_stages(configuration), quote=quote(configuration))

    @bp.get('/job-setup-drafts/latest')
    @endpoint
    def latest(actor):
        return {'draft': service.read_latest(actor, request.args.get('job_id') or None)}

    @bp.post('/job-setup-drafts')
    @endpoint
    def create(actor):
        data = body({'configuration', 'job_fields', 'operation_key', 'job_id'})
        return {'draft': service.save(actor, data.get('configuration'), data.get('job_fields'), data.get('operation_key'), job_id=data.get('job_id'))}

    @bp.put('/job-setup-drafts/<draft_id>')
    @endpoint
    def update(actor, draft_id):
        data = body({'configuration', 'job_fields', 'operation_key', 'expected_revision', 'job_id'})
        return {'draft': service.save(actor, data.get('configuration'), data.get('job_fields'), data.get('operation_key'),
            draft_id=draft_id, expected_revision=data.get('expected_revision'), job_id=data.get('job_id'))}

    @bp.get('/jobs/<job_id>/hiring-setup')
    @endpoint
    def get_setup(actor, job_id):
        return service.get_job_setup(job_id, actor)

    return bp
