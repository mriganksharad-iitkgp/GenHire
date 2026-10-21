"""Private pilot workflow endpoints; execution/invitations arrive in later steps."""
from functools import wraps
from flask import Blueprint, jsonify, request
from middleware.auth_middleware import token_required
from core.mongo_transactions import AtomicityUnavailable
from models.hiring_workflow import WorkflowError
from services.workflow_service import WorkflowService


def create_workflow_routes(db):
    bp = Blueprint('workflow', __name__, url_prefix='/api')
    service = WorkflowService(db)

    def notify(application_id):
        # Best-effort refresh hint after commit; REST remains authoritative.
        try:
            from core.extensions import socketio
            application = service.repo.application(application_id)
            payload = {key: application.get(key) for key in ('job_id', 'status', 'workflow_version_id', 'workflow_label', 'workflow')}
            payload['_id'] = str(application['_id'])
            for owner in {application.get('student_id'), application.get('recruiter_id')} - {None, ''}:
                socketio.emit('application_update', {'type': 'status_changed', 'application': payload}, room=str(owner))
        except Exception:
            from flask import current_app
            current_app.logger.warning('Workflow refresh hint unavailable; committed state is retained.')

    def endpoint(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            try:
                return jsonify(fn(*args, **kwargs))
            except WorkflowError as exc:
                return jsonify(error=str(exc), error_code=exc.code), exc.status
            except AtomicityUnavailable:
                return jsonify(error='Transactional storage is unavailable; no workflow change was committed.',
                               error_code='atomicity_unavailable'), 503
        return token_required(wrapped)

    def body(allowed):
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or set(data) - set(allowed):
            raise WorkflowError('invalid_request', 'Provide a JSON object with supported fields.', 400)
        return data

    @bp.route('/jobs/<job_id>/workflow', methods=['POST'])
    @endpoint
    def publish(actor, job_id):
        data = body(('stages', 'expected_revision', 'operation_key'))
        return service.publish_version(job_id, actor, data.get('stages'), data.get('expected_revision'), data.get('operation_key'))

    @bp.route('/jobs/<job_id>/workflow', methods=['GET'])
    @endpoint
    def job_workflow(actor, job_id):
        service.require_enabled()
        job = service.job(job_id, actor)
        from bson import ObjectId
        version = db.hiring_workflow_versions.find_one({'_id': ObjectId(job['workflow_version_id'])}) if job.get('workflow_version_id') else None
        if version:
            version['_id'] = str(version['_id'])
            for field in ('operation_key', 'request_hash'):
                version.pop(field, None)
        return {'version': version, 'funnel': service.repo.counts(job_id)}

    @bp.route('/applications/<application_id>/workflow-adoption', methods=['POST'])
    @endpoint
    def adopt(actor, application_id):
        data = body(('version_id', 'operation_key'))
        from bson import ObjectId
        if not isinstance(data.get('version_id'), str) or not ObjectId.is_valid(data['version_id']):
            raise WorkflowError('invalid_version', 'A valid workflow version ID is required.', 400)
        result = service.adopt(application_id, actor, data['version_id'], data.get('operation_key'))
        notify(application_id)
        return result

    @bp.route('/applications/<application_id>/stages', methods=['GET'])
    @endpoint
    def history(actor, application_id):
        try:
            after = int(request.args.get('after_revision', '-1'))
            limit = int(request.args.get('limit', '100'))
        except ValueError:
            raise WorkflowError('invalid_pagination', 'Pagination values must be integers.', 400) from None
        return service.history(application_id, actor, after, limit)

    @bp.route('/applications/<application_id>/stage-actions', methods=['POST'])
    @endpoint
    def transition(actor, application_id):
        data = body(('action', 'expected_revision', 'operation_key', 'reason'))
        result = service.transition(application_id, actor, data.get('action'), data.get('expected_revision'),
                                    data.get('operation_key'), data.get('reason'))
        notify(application_id)
        return result

    return bp
