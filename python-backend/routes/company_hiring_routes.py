"""Account-authenticated company reporting, decisions and previewed communications."""
from functools import wraps
from datetime import datetime
from bson import ObjectId
from flask import Blueprint, jsonify, request, Response
from middleware.auth_middleware import token_required
from core.mongo_transactions import AtomicityUnavailable
from models.hiring_workflow import WorkflowError
from services.company_hiring_service import CompanyHiringService
from services.hiring_progression_service import notify_hiring_progress
from services.hiring_progression_service import utc


def create_company_hiring_routes(db):
    bp = Blueprint('company_hiring', __name__, url_prefix='/api')
    service = CompanyHiringService(db)

    def json_value(value):
        if isinstance(value, ObjectId): return str(value)
        if isinstance(value, datetime): return utc(value).isoformat(timespec='milliseconds')
        if isinstance(value, dict): return {k: json_value(v) for k, v in value.items()}
        if isinstance(value, list): return [json_value(v) for v in value]
        return value

    @bp.after_request
    def private(response):
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    def endpoint(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            try:
                value = fn(*args, **kwargs)
                return value if isinstance(value, Response) else jsonify(json_value(value))
            except WorkflowError as exc: return jsonify(error=str(exc), error_code=exc.code), exc.status
            except AtomicityUnavailable: return jsonify(error='Transactional company storage is unavailable.', error_code='atomicity_unavailable'), 503
        return token_required(wrapped)

    def body(fields):
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or set(data)-set(fields): raise WorkflowError('invalid_request', 'Unsupported request fields.', 400)
        return data

    def filters(): return {key: request.args.get(key) for key in ('stage', 'lifecycle', 'qualification')}

    @bp.get('/jobs/<job_id>/company-candidates')
    @endpoint
    def candidates(actor, job_id):
        try: limit = int(request.args.get('limit', '100'))
        except ValueError: raise WorkflowError('invalid_pagination', 'Limit must be an integer.', 400) from None
        return service.rows(actor, job_id, after=request.args.get('after'), limit=limit, **filters())

    @bp.get('/applications/<application_id>/company-review')
    @endpoint
    def detail(actor, application_id): return service.detail(actor, application_id)

    @bp.post('/applications/<application_id>/company-actions')
    @endpoint
    def action(actor, application_id):
        data = body(('action', 'expected_revision', 'operation_key', 'reason', 'name'))
        value = service.action(actor, application_id, data.get('action'), data.get('expected_revision'), data.get('operation_key'), data.get('reason'), data.get('name'))
        notify_hiring_progress(db, application_id)
        return value

    @bp.post('/jobs/<job_id>/bulk-stage-actions')
    @endpoint
    def bulk(actor, job_id):
        data = body(('items', 'action', 'operation_key', 'reason'))
        value = service.bulk(actor, job_id, data.get('items'), data.get('action'), data.get('operation_key'), data.get('reason'))
        for item in value['outcomes']:
            if item['ok']: notify_hiring_progress(db, item['application_id'])
        return value

    @bp.get('/jobs/<job_id>/exports')
    @endpoint
    def export(actor, job_id):
        extension = request.args.get('format', 'csv')
        if extension not in {'csv', 'xlsx'}: raise WorkflowError('invalid_format', 'Choose CSV or XLSX.', 400)
        rows = service.export(actor, job_id, **filters())
        from services.screening_export_service import build_stage_export
        content = build_stage_export(rows, extension)
        response = Response(content, mimetype='text/csv' if extension == 'csv' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response.headers['Content-Disposition'] = 'attachment; filename="company_candidates.'+extension+'"'
        return response

    @bp.post('/jobs/<job_id>/communications/preview')
    @endpoint
    def preview(actor, job_id):
        data = body(('application_ids', 'subject', 'message'))
        return service.preview(actor, job_id, data.get('application_ids'), data.get('subject'), data.get('message'))

    @bp.post('/jobs/<job_id>/communications')
    @endpoint
    def queue(actor, job_id):
        data = body(('preview_id', 'operation_key', 'accepted'))
        return service.queue(actor, job_id, data.get('preview_id'), data.get('operation_key'), data.get('accepted'))

    @bp.get('/jobs/<job_id>/communications/<batch_id>')
    @endpoint
    def deliveries(actor, job_id, batch_id): return service.deliveries(actor, job_id, batch_id)

    @bp.post('/company-communications/<message_id>/reconcile')
    @endpoint
    def reconcile(actor, message_id):
        data = body(('disposition', 'reason', 'operation_key'))
        return service.reconcile_delivery(actor, message_id, data.get('disposition'), data.get('reason'), data.get('operation_key'))

    return bp
