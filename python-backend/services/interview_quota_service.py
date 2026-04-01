import datetime
from bson import ObjectId
from pymongo.errors import DuplicateKeyError


FREE_LIFETIME_CREDITS = 2
PRO_MONTHLY_CREDITS = 100
MAX_MONTHLY_CREDITS = 300
USAGE_COLLECTION = "interview_credit_usage"


def _safe_object_id(value):
    try:
        return ObjectId(str(value))
    except Exception:
        return None


def _build_subscription_query(recruiter_id):
    recruiter_str = str(recruiter_id)
    query = {
        "status": "active",
        "$or": [{"employer_id": recruiter_str}],
    }
    recruiter_obj = _safe_object_id(recruiter_id)
    if recruiter_obj:
        query["$or"].append({"employer_id": recruiter_obj})
    return query


def _ensure_usage_indexes(db):
    collection = db[USAGE_COLLECTION]
    collection.create_index(
        [("recruiter_id", 1), ("application_id", 1), ("usage_month", 1)],
        unique=True,
        name="uniq_recruiter_app_month_usage",
    )
    collection.create_index(
        [("recruiter_id", 1), ("usage_month", 1), ("source", 1)],
        name="idx_recruiter_month_source",
    )


def _get_month_key(now):
    return now.strftime("%Y-%m")


def _get_month_bounds(now):
    month_start = datetime.datetime(now.year, now.month, 1)
    if now.month == 12:
        month_end = datetime.datetime(now.year + 1, 1, 1)
    else:
        month_end = datetime.datetime(now.year, now.month + 1, 1)
    return month_start, month_end


def _get_recruiter_job_ids(db, recruiter_id):
    recruiter_str = str(recruiter_id)
    created_by_conditions = []
    created_by_conditions.append({"created_by": recruiter_str})
    recruiter_obj = _safe_object_id(recruiter_id)
    if recruiter_obj:
        created_by_conditions.append({"created_by": recruiter_obj})

    job_query = {"$or": created_by_conditions}

    return [str(job["_id"]) for job in db.jobs.find(job_query, {"_id": 1})]


def _get_active_subscription(db, recruiter_id, now):
    subscription = db.subscriptions.find_one(_build_subscription_query(recruiter_id))
    if not subscription:
        return None

    expires_at = subscription.get("expires_at")
    if isinstance(expires_at, datetime.datetime) and expires_at < now:
        return None

    return subscription


def _is_recruiter_max(subscription):
    if not subscription:
        return False
    snapshot = subscription.get("plan_snapshot") or {}
    slug = str(snapshot.get("slug", "")).lower()
    name = str(snapshot.get("name", "")).lower()
    interviews_allowed = int(subscription.get("interviews_allowed", 0) or 0)
    return "recruiter-max" in slug or "max" in name or interviews_allowed >= MAX_MONTHLY_CREDITS


def _plan_monthly_credits(subscription):
    if not subscription:
        return 0
    if _is_recruiter_max(subscription):
        return MAX_MONTHLY_CREDITS

    # Pro monthly credits by policy; fallback to stored value if higher.
    stored = int(subscription.get("interviews_allowed", 0) or 0)
    return max(PRO_MONTHLY_CREDITS, stored)


def _ledger_usage_counts(db, recruiter_id, month_key):
    usage_collection = db[USAGE_COLLECTION]
    base_plan = {"recruiter_id": str(recruiter_id), "usage_month": month_key, "source": "plan"}
    base_free = {"recruiter_id": str(recruiter_id), "source": "free"}
    return {
        "plan_used": usage_collection.count_documents(base_plan),
        "free_used": usage_collection.count_documents(base_free),
    }


def _legacy_monthly_usage_total(db, recruiter_id, month_start):
    recruiter_job_ids = _get_recruiter_job_ids(db, recruiter_id)
    if not recruiter_job_ids:
        return 0

    recruiter_application_ids = [
        str(app["_id"])
        for app in db.applications.find({"job_id": {"$in": recruiter_job_ids}}, {"_id": 1})
    ]
    if not recruiter_application_ids:
        return 0

    # Distinct applications where an interview started this month.
    app_ids_with_interviews = db.interviews.distinct(
        "application_id",
        {
            "application_id": {"$in": recruiter_application_ids},
            "status": {"$in": ["active", "completed"]},
            "created_at": {"$gte": month_start},
        },
    )
    total = len(app_ids_with_interviews)

    if total == 0:
        total = db.applications.count_documents(
            {
                "job_id": {"$in": recruiter_job_ids},
                "is_visible": True,
                "status": {"$in": ["interviewed", "selected", "rejected"]},
                "updated_at": {"$gte": month_start},
            }
        )

    return int(total)


def get_recruiter_interview_quota(db, recruiter_id, now=None):
    """Single source of truth for monthly recruiter quota.

    Policy:
    - Free: 2 interviews per calendar month for every recruiter.
    - Pro: 100 interviews per calendar month during active validity.
    - Recruiter Max: 300 interviews per calendar month during active validity.
    - Consumption priority: plan credits first, then free credits.
    """
    now = now or datetime.datetime.utcnow()
    month_key = _get_month_key(now)
    month_start, month_end = _get_month_bounds(now)

    _ensure_usage_indexes(db)

    subscription = _get_active_subscription(db, recruiter_id, now)
    plan_is_unlimited = False
    plan_monthly_credits = _plan_monthly_credits(subscription)

    usage = _ledger_usage_counts(db, recruiter_id, month_key)
    plan_used = int(usage["plan_used"])
    free_used = int(usage["free_used"])

    # Bootstrap old data if ledger is not populated for this month.
    if plan_used == 0 and free_used == 0:
        legacy_total = _legacy_monthly_usage_total(db, recruiter_id, month_start)
        if plan_monthly_credits > 0:
            plan_used = min(legacy_total, plan_monthly_credits)
            free_used = max(0, legacy_total - plan_used)
        else:
            free_used = legacy_total

    plan_remaining = max(0, plan_monthly_credits - plan_used)
    can_use_plan = plan_remaining > 0

    free_remaining = max(0, FREE_LIFETIME_CREDITS - free_used)
    can_use_free = free_remaining > 0

    can_start = can_use_plan or can_use_free

    total_allowed = max(0, plan_monthly_credits) + FREE_LIFETIME_CREDITS
    total_used = plan_used + free_used
    total_remaining = max(0, total_allowed - total_used)
    quota_mode = "max" if plan_monthly_credits >= MAX_MONTHLY_CREDITS else ("pro" if plan_monthly_credits > 0 else "free")

    error_code = None
    error_message = None
    if not can_start:
        if plan_monthly_credits > 0:
            error_code = "RECRUITER_INTERVIEW_CREDITS_EXHAUSTED"
            error_message = "Interview is currently unavailable for this job. The recruiter has exhausted interview credits on their plan."
        else:
            error_code = "RECRUITER_INTERVIEW_LIMIT_REACHED"
            error_message = "Interview is currently unavailable for this job. The recruiter has reached the free interview limit on their account."

    return {
        "quota_mode": quota_mode,
        "plan_owner": "recruiter",
        "can_start_interview": can_start,
        "month_key": month_key,
        "month_start": month_start,
        "month_end": month_end,
        "is_unlimited": plan_is_unlimited,
        "subscription_id": subscription.get("_id") if subscription else None,
        "plan_interviews_allowed": -1 if plan_is_unlimited else int(max(0, plan_monthly_credits)),
        "plan_interviews_used": plan_used,
        "plan_interviews_remaining": plan_remaining,
        "free_interviews_allowed": FREE_LIFETIME_CREDITS,
        "free_interviews_used": free_used,
        "free_interviews_remaining": free_remaining,
        "interviews_allowed": total_allowed,
        "interviews_used": total_used,
        "interviews_remaining": total_remaining,
        "error_code": error_code,
        "error_message": error_message,
    }


def consume_interview_credit(db, recruiter_id, application_id, quota_snapshot=None, now=None):
    """Consume monthly credit idempotently for a specific application.

    - Uses plan credits first, then free credits.
    - One application consumes at most one credit per month.
    """
    now = now or datetime.datetime.utcnow()
    month_key = _get_month_key(now)
    recruiter_str = str(recruiter_id)
    application_str = str(application_id)

    _ensure_usage_indexes(db)
    usage_collection = db[USAGE_COLLECTION]

    existing = usage_collection.find_one(
        {
            "recruiter_id": recruiter_str,
            "application_id": application_str,
            "usage_month": month_key,
        }
    )
    if existing:
        return True

    quota = quota_snapshot or get_recruiter_interview_quota(db, recruiter_str, now=now)
    if not quota.get("can_start_interview", False):
        return False

    if quota.get("is_unlimited"):
        source = "plan"
    elif int(quota.get("plan_interviews_remaining", 0) or 0) > 0:
        source = "plan"
    elif int(quota.get("free_interviews_remaining", 0) or 0) > 0:
        source = "free"
    else:
        return False

    document = {
        "recruiter_id": recruiter_str,
        "application_id": application_str,
        "usage_month": month_key,
        "source": source,
        "subscription_id": quota.get("subscription_id"),
        "created_at": now,
    }

    try:
        usage_collection.insert_one(document)
        return True
    except DuplicateKeyError:
        return True

