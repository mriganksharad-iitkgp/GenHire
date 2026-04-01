import datetime
from bson import ObjectId
from pymongo.errors import DuplicateKeyError


CANDIDATE_FREE_LIFETIME_CREDITS = 2
CANDIDATE_USAGE_COLLECTION = "candidate_practice_credit_usage"


def _safe_object_id(value):
    try:
        return ObjectId(str(value))
    except Exception:
        return None


def _get_month_key(now):
    return now.strftime("%Y-%m")


def _ensure_usage_indexes(db):
    collection = db[CANDIDATE_USAGE_COLLECTION]
    collection.create_index(
        [("candidate_id", 1), ("session_id", 1), ("usage_month", 1)],
        unique=True,
        name="uniq_candidate_session_month_usage",
    )
    collection.create_index(
        [("candidate_id", 1), ("usage_month", 1), ("source", 1)],
        name="idx_candidate_month_source",
    )


def _find_active_candidate_subscription(db, candidate_id, now):
    candidate_str = str(candidate_id)
    candidate_obj = _safe_object_id(candidate_id)

    base_filters = [
        {
            "employer_id": candidate_str,
            "status": "active",
            "plan_snapshot.audience": "candidate",
        },
        {
            "employer_id": candidate_str,
            "status": "active",
            "plan_snapshot.slug": {"$regex": "^candidate-"},
        },
    ]

    if candidate_obj:
        base_filters.extend(
            [
                {
                    "employer_id": candidate_obj,
                    "status": "active",
                    "plan_snapshot.audience": "candidate",
                },
                {
                    "employer_id": candidate_obj,
                    "status": "active",
                    "plan_snapshot.slug": {"$regex": "^candidate-"},
                },
            ]
        )

    subscription = db.subscriptions.find_one({"$or": base_filters})
    if not subscription:
        return None

    expires_at = subscription.get("expires_at")
    if isinstance(expires_at, datetime.datetime) and expires_at < now:
        return None

    return subscription


def _usage_counts(db, candidate_id, month_key):
    usage_collection = db[CANDIDATE_USAGE_COLLECTION]
    base_plan = {"candidate_id": str(candidate_id), "usage_month": month_key, "source": "plan"}
    base_free = {"candidate_id": str(candidate_id), "source": "free"}

    return {
        "plan_used": usage_collection.count_documents(base_plan),
        "free_used": usage_collection.count_documents(base_free),
    }

def get_candidate_practice_quota(db, candidate_id, now=None):
    now = now or datetime.datetime.utcnow()
    month_key = _get_month_key(now)

    _ensure_usage_indexes(db)

    subscription = _find_active_candidate_subscription(db, candidate_id, now)
    usage = _usage_counts(db, candidate_id, month_key)

    plan_name = "Free Tier"
    plan_interviews_allowed = 0
    plan_used = int(usage["plan_used"])
    free_used = int(usage["free_used"])

    if subscription:
        snapshot = subscription.get("plan_snapshot") or {}
        plan_name = snapshot.get("name") or "Candidate Plan"
        plan_interviews_allowed = int(
            subscription.get("interviews_allowed", snapshot.get("interviews_allowed", 0))
            or 0
        )

    if plan_interviews_allowed > 0:
        plan_remaining = max(0, plan_interviews_allowed - plan_used)
        free_allowed = 0
        free_remaining = 0
        total_allowed = plan_interviews_allowed
        total_used = plan_used
        total_remaining = plan_remaining
        can_start = plan_remaining > 0
        quota_mode = "paid"
    else:
        plan_remaining = 0
        free_allowed = CANDIDATE_FREE_LIFETIME_CREDITS
        free_remaining = max(0, free_allowed - free_used)
        total_allowed = free_allowed
        total_used = free_used
        total_remaining = free_remaining
        can_start = free_remaining > 0
        quota_mode = "free"

    error_code = None
    error_message = None
    if not can_start:
        error_code = "CANDIDATE_PRACTICE_LIMIT_REACHED"
        error_message = "You've reached your free practice interview limit. Upgrade your plan to continue."

    return {
        "quota_mode": quota_mode,
        "plan_owner": "candidate",
        "plan_name": plan_name,
        "can_start_interview": can_start,
        "month_key": month_key,
        "subscription_id": subscription.get("_id") if subscription else None,
        "is_unlimited": False,
        "plan_interviews_allowed": plan_interviews_allowed,
        "plan_interviews_used": plan_used,
        "plan_interviews_remaining": plan_remaining,
        "free_interviews_allowed": free_allowed,
        "free_interviews_used": free_used,
        "free_interviews_remaining": free_remaining,
        "interviews_allowed": total_allowed,
        "interviews_used": total_used,
        "interviews_remaining": total_remaining,
        "error_code": error_code,
        "error_message": error_message,
    }


def consume_candidate_practice_credit(
    db,
    candidate_id,
    session_id,
    quota_snapshot=None,
    now=None,
):
    now = now or datetime.datetime.utcnow()
    month_key = _get_month_key(now)

    _ensure_usage_indexes(db)
    usage_collection = db[CANDIDATE_USAGE_COLLECTION]

    candidate_str = str(candidate_id)
    session_str = str(session_id)

    existing = usage_collection.find_one(
        {
            "candidate_id": candidate_str,
            "session_id": session_str,
            "usage_month": month_key,
        }
    )
    if existing:
        return True

    quota = quota_snapshot or get_candidate_practice_quota(db, candidate_str, now=now)
    if not quota.get("can_start_interview", False):
        return False

    source = "plan" if int(quota.get("plan_interviews_remaining", 0) or 0) > 0 else "free"

    document = {
        "candidate_id": candidate_str,
        "session_id": session_str,
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
