"""Account-only purchase APIs; attempts use the shared scoped OA endpoints."""
from datetime import datetime
from functools import wraps
import os
from bson import ObjectId
from flask import Blueprint, jsonify, request
from middleware.auth_middleware import token_required
from core.mongo_transactions import AtomicityUnavailable
from models.hiring_workflow import WorkflowError
from models.job_setup import TEMPLATE_IDS, template, default_setup
from services.practice_assessment_service import PracticeAssessmentService, mock_enabled
from services.hiring_progression_service import utc
from services.assessment_pricing_service import pricing_catalog, operation_history
from payment_module.services.billing_operation_service import BillingOperationError


def create_practice_assessment_routes(db):
    bp = Blueprint('practice_assessment', __name__, url_prefix='/api')
    service = PracticeAssessmentService(db)
    def value(item):
        if isinstance(item, ObjectId): return str(item)
        if isinstance(item, datetime): return utc(item).isoformat(timespec='milliseconds')
        if isinstance(item, dict): return {k:value(v) for k,v in item.items()}
        if isinstance(item,list): return [value(v) for v in item]
        return item
    @bp.after_request
    def private(response):
        response.headers['Cache-Control']='private, no-store'; return response
    def endpoint(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            try: return jsonify(value(fn(*args, **kwargs)))
            except WorkflowError as exc: return jsonify(error=str(exc),error_code=exc.code),exc.status
            except BillingOperationError as exc: return jsonify(error=str(exc),error_code='billing_operation_failed'),409
            except AtomicityUnavailable: return jsonify(error='Transactional practice storage is unavailable.',error_code='atomicity_unavailable'),503
        return token_required(wrapped)
    def body(fields):
        data=request.get_json(silent=True)
        if not isinstance(data,dict) or set(data)-set(fields): raise WorkflowError('invalid_request','Unsupported request fields.',400)
        return data
    @bp.get('/pricing/catalog')
    def pricing():
        try:return jsonify(value(pricing_catalog(db)))
        except WorkflowError as exc:return jsonify(error=str(exc),error_code=exc.code),exc.status
    @bp.get('/billing-operations')
    @endpoint
    def billing(actor): return operation_history(db,actor,request.args.get('after'))
    @bp.get('/billing-operations/<identifier>')
    @endpoint
    def billing_one(actor,identifier): return operation_history(db,actor,identifier=identifier)
    @bp.get('/practice/assessments/catalog')
    @endpoint
    def catalog(actor):
        service.candidate(actor)
        try:
            service.available()
            purchase_ready, unavailable_reason = True, None
        except WorkflowError as exc:
            purchase_ready, unavailable_reason = False, str(exc)
        executor = service.validator.capabilities()
        return dict(enabled=mock_enabled(), templates=[template(k) for k in TEMPLATE_IDS], defaults=default_setup()['oa'], pricing=pricing_catalog(db),
            runtime_ready=service.runtime.candidate_runtime_ready, executor=executor,
            purchase_ready=purchase_ready, unavailable_reason=unavailable_reason,
            section_availability=dict(mcq=True, coding=executor['available'], sql=executor['available']),
            media_ready=all(os.getenv(k,'').lower()=='true' for k in ('GENHIRE_OA_MEDIA_ENABLED','GENHIRE_OA_MEDIA_ACCEPTED')),
            includes=['Objective grading','Question explanations','AI educational advice'], start_within_days=30)
    @bp.post('/practice/assessments/quotes')
    @bp.post('/pricing/quote')
    @endpoint
    def quote(actor): return service.quote(actor,body(('configuration',)).get('configuration'))
    @bp.post('/practice/assessments')
    @endpoint
    def purchase(actor):
        data=body(('quote_id','operation_key','accepted')); return service.purchase(actor,data.get('quote_id'),data.get('operation_key'),data.get('accepted'))
    @bp.get('/practice/assessments')
    @endpoint
    def history(actor): return service.history(actor,request.args.get('after'))
    @bp.get('/practice/assessments/<identifier>/report')
    @endpoint
    def report(actor,identifier):
        attempt=db.assessment_attempts.find_one({'_id':ObjectId(identifier)}) if ObjectId.is_valid(identifier) else None
        if not attempt or attempt.get('pool')!='practice': raise WorkflowError('not_found','Practice attempt not found.',404)
        return service.report(actor,attempt)
    @bp.get('/admin/practice-assessments/<candidate_id>')
    @endpoint
    def admin_history(actor,candidate_id):
        if actor.get('user_type')!='admin' or not ({'*','applications.read'} & set(actor.get('permissions',[]))): raise WorkflowError('forbidden','Authorized administrator required.',403)
        from services.assessment_authoring_service import object_id
        user=db.users.find_one({'_id':object_id(candidate_id)})
        if not user: raise WorkflowError('not_found','Candidate not found.',404)
        result=service.history(user,request.args.get('after'))
        for purchase in result['purchases']:
            if purchase['invitation_id']:
                invitation=db.assessment_invitations.find_one({'_id':ObjectId(purchase['invitation_id'])})
                purchase['invitation']=service.invitation(user,invitation)
        db.assessment_evidence_access.insert_one(dict(candidate_id=candidate_id,actor_id=str(actor['_id']),action='practice_operations_read',occurred_at=service.clock()))
        return result
    @bp.post('/practice/assessments/<purchase_id>/platform-failure')
    @endpoint
    def platform_failure(actor,purchase_id):
        data=body(('operation_key','reason'));return service.platform_failure(actor,purchase_id,data.get('operation_key'),data.get('reason'))
    return bp
