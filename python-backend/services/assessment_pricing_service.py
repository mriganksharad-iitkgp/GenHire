"""Public server price catalog and private ledger-backed OA operation history."""
from bson import ObjectId
import os
from models.hiring_workflow import WorkflowError
from services.job_setup_service import prices
from services.workflow_service import request_identity
from services.assessment_authoring_service import object_id


def pricing_catalog(db=None):
    from payment_module.config.settings import PaymentConfig
    from services.practice_assessment_service import mock_enabled
    p = prices()
    legacy = dict(practice_interview=PaymentConfig.CANDIDATE_PRACTICE_CREDITS,
        practice_interview_proctored=PaymentConfig.CANDIDATE_PRACTICE_PROCTORED_CREDITS,
        ai_jd=PaymentConfig.RECRUITER_AI_JD_CREDITS, screening=PaymentConfig.RECRUITER_REAL_INTERVIEW_CREDITS,
        screening_proctored=PaymentConfig.RECRUITER_REAL_INTERVIEW_PROCTORED_CREDITS,
        candidate_invite=PaymentConfig.RECRUITER_INVITE_CREDITS_PER_CANDIDATE, signup_bonus=PaymentConfig.SIGNUP_BONUS_CREDITS)
    packs={}
    if db is not None:
        from payment_module.models.plan import PlanSchema
        packs={doc['slug'].replace('-','_'):{k:doc[k] for k in ('name','price_paise','credits_allocated') if k in doc} for doc in db[PlanSchema.COLLECTION_NAME].find({'is_active':True})}
    return dict(credits=dict(p, **legacy), packs=packs, currency=PaymentConfig.CURRENCY, price_version=request_identity(dict(oa=p, legacy=legacy,packs=packs)),
        extras=dict(camera_available=all(os.getenv(k,'').lower()=='true' for k in ('GENHIRE_OA_INTEGRITY_ENABLED','GENHIRE_OA_MEDIA_ENABLED','GENHIRE_OA_MEDIA_ACCEPTED')),
            variants_available=os.getenv('GENHIRE_OA_VARIANTS_ENABLED','').lower()=='true',
            recruitment_similarity_available=os.getenv('GENHIRE_OA_SIMILARITY_ENABLED','').lower()=='true'),
        mock_oa_enabled=mock_enabled(), units=dict(mock_oa='one_validated_generation_and_attempt_with_base_feedback', oa_setup='once_per_job_activation',
            oa_attempt='per_accepted_recruitment_attempt', variants='per_extra_reviewed_batch', plagiarism='per_quoted_recruitment_report'),
        unavailable=['descriptive_ai_response_grading', 'ai_authorship_detection', 'enriched_oa_analytics', 'practice_similarity'],
        note='Catalog is informational. A binding operation quote and explicit approval control OA purchases; accepted prices are frozen.')


def operation_history(db, actor, after=None, identifier=None):
    role = actor.get('user_type')
    audience = 'candidate' if role in {'candidate', 'student'} else 'recruiter' if role=='recruiter' else None
    if audience is None: raise WorkflowError('forbidden', 'Use the payer account for billing history.', 403)
    query = dict(owner_id=str(actor['_id']), audience=audience)
    if identifier: query['_id'] = object_id(identifier)
    elif after: query['_id'] = {'$lt': object_id(after)}
    docs = list(db.billing_operations.find(query).sort('_id', -1).limit(21))
    if identifier and not docs: raise WorkflowError('not_found', 'Billing operation not found.', 404)
    keys = ('credits','purpose','state','refunded_credits','created_at','updated_at','price_snapshot','purchase_id')
    def view(doc):
        refunds = list(db.billing_refunds.find({'operation_id':str(doc['_id'])}, {'_id':0, 'credits':1, 'reason':1, 'occurred_at':1}).limit(20))
        return dict(operation_id=str(doc['_id']), **{k:doc[k] for k in keys if k in doc}, refunds=refunds)
    return dict(operations=[view(doc) for doc in docs[:20]], next_cursor=str(docs[19]['_id']) if len(docs)>20 else None)
