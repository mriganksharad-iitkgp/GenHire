"""Recruiter-only question bank and content review; no candidate question endpoint."""
from functools import wraps
from flask import Blueprint, jsonify, request
from middleware.auth_middleware import token_required
from core.mongo_transactions import AtomicityUnavailable
from models.hiring_workflow import WorkflowError
from services.assessment_authoring_service import AssessmentAuthoringService


def create_assessment_authoring_routes(db):
    bp = Blueprint('assessment_authoring', __name__, url_prefix='/api')
    service = AssessmentAuthoringService(db)
    from services.assessment_generation_service import AssessmentGenerationService
    generation = AssessmentGenerationService(db)
    from services.assessment_validation_jobs import AssessmentValidationJobs
    validation_jobs = AssessmentValidationJobs(db)

    def endpoint(fn):
        @wraps(fn)
        def wrapped(actor, *args, **kwargs):
            try:
                service.authorize(actor)
                return jsonify(fn(actor, *args, **kwargs))
            except WorkflowError as exc:
                return jsonify(error=str(exc), error_code=exc.code), exc.status
            except AtomicityUnavailable:
                return jsonify(error='Transactional content storage is unavailable.', error_code='atomicity_unavailable'), 503
        return token_required(wrapped)

    def body(keys):
        value = request.get_json(silent=True)
        if not isinstance(value, dict) or set(value) - set(keys):
            raise WorkflowError('invalid_request', 'Provide a JSON object with supported fields.', 400)
        return value

    @bp.get('/question-bank')
    @endpoint
    def bank(actor):
        try: limit = int(request.args.get('limit', 20))
        except ValueError: raise WorkflowError('invalid_limit', 'Invalid page size.', 400)
        return service.bank(actor, request.args.get('after'), limit, request.args.get('type'))

    @bp.post('/question-bank/versions')
    @endpoint
    def create_question(actor):
        data = body({'content', 'operation_key', 'previous_version_id', 'blueprint_id', 'suite_policy'})
        return {'question': service.save_question(actor, data.get('content'), data.get('operation_key'),
            data.get('previous_version_id'), data.get('blueprint_id'), data.get('suite_policy'))}

    @bp.get('/question-bank/versions/<version_id>')
    @endpoint
    def get_question(actor, version_id):
        return {'question': service.get_question(actor, version_id)}

    @bp.post('/question-bank/versions/<version_id>/validate')
    @endpoint
    def validate(actor, version_id):
        data = body({'operation_key'})
        if service.question(version_id, actor, True)['content']['type'] != 'mcq':
            return {'job': validation_jobs.enqueue(actor, version_id, data.get('operation_key'))}
        return {'validation': service.validate(actor, version_id, data.get('operation_key'))}

    @bp.get('/assessment-validation-jobs/<job_id>')
    @endpoint
    def validation_status(actor, job_id):
        return {'job': validation_jobs.get(actor, job_id)}

    @bp.post('/question-bank/versions/<version_id>/review')
    @endpoint
    def review(actor, version_id):
        data = body({'operation_key', 'validation_id', 'decision', 'reason'})
        return {'review': service.review(actor, version_id, data.get('validation_id'), data.get('decision'), data.get('reason'), data.get('operation_key'))}

    @bp.get('/assessment-blueprints/<blueprint_id>/content')
    @endpoint
    def get_workspace(actor, blueprint_id):
        return service.workspace(actor, blueprint_id)

    @bp.put('/assessment-blueprints/<blueprint_id>/content')
    @endpoint
    def save_workspace(actor, blueprint_id):
        data = body({'operation_key', 'expected_revision', 'question_version_ids'})
        return {'workspace': service.save_workspace(actor, blueprint_id, data.get('question_version_ids'), data.get('expected_revision'), data.get('operation_key'))}

    @bp.post('/assessment-blueprints/<blueprint_id>/publish')
    @endpoint
    def publish(actor, blueprint_id):
        data = body({'operation_key', 'expected_revision', 'approved'})
        return {'version': service.publish(actor, blueprint_id, data.get('expected_revision'), data.get('operation_key'), data.get('approved'))}

    @bp.post('/assessment-blueprints/<blueprint_id>/generation-quotes')
    @endpoint
    def generation_quote(actor, blueprint_id):
        data = body({'requests', 'instructions', 'problem_source'})
        return {'quote': generation.create_quote(actor, blueprint_id, data.get('requests'), data.get('instructions', ''), data.get('problem_source'))}

    @bp.post('/assessment-generation-jobs')
    @endpoint
    def generation_job(actor):
        data = body({'quote_id', 'operation_key', 'accepted'})
        return {'job': generation.enqueue(actor, data.get('quote_id'), data.get('operation_key'), data.get('accepted'))}

    @bp.get('/assessment-generation-jobs/<job_id>')
    @endpoint
    def get_generation_job(actor, job_id):
        return {'job': generation.get(actor, job_id)}

    @bp.post('/assessment-blueprints/<blueprint_id>/release-setup-hold')
    @endpoint
    def release_setup_hold(actor, blueprint_id):
        data = body({'operation_key'})
        return {'job': generation.release_setup_hold(actor, blueprint_id, data.get('operation_key'))}

    return bp
