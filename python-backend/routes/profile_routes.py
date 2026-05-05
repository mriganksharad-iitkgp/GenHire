from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from controllers.profile_controller import ProfileController
from middleware.auth_middleware import token_required, recruiter_required
from config.database import db_config
from datetime import datetime, timedelta
from payment_module.services.wallet_service import WalletService

profile_bp = Blueprint("profile", __name__, url_prefix="/api")

# Initialize profile controller
collections = db_config.get_collections()
profile_controller = ProfileController(collections)


def _format_tx_timestamp(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    text = str(value or "")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return text


def _get_tx_month(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m")
    text = str(value or "")
    if len(text) >= 7:
        return text[:7]
    return datetime.utcnow().strftime("%Y-%m")


def _humanize_tx_type(tx_type):
    label_map = {
        "signup_bonus": "Signup Bonus",
        "recharge": "Wallet Recharge",
        "ai_jd_generation": "AI JD Generation",
        "real_interview_recruiter": "Real Interview",
        "real_interview_candidate_audit": "Real Interview Audit",
        "practice_interview": "Practice Interview",
        "manual_interview_use": "Manual Interview Use",
    }
    return label_map.get(str(tx_type or ""), str(tx_type or "activity").replace("_", " ").title())


DEDUCTION_ACTIVITY_TYPES = {
    "practice_interview",
    "ai_jd_generation",
    "real_interview_recruiter",
}

RECHARGE_ACTIVITY_TYPES = {"recharge", "migration_recharge"}


def _is_proctored(tx):
    metadata = tx.get("metadata") or {}
    if "proctoring_enabled" in metadata:
        return bool(metadata.get("proctoring_enabled"))
    proctoring_config = metadata.get("proctoring_config")
    if isinstance(proctoring_config, dict):
        return any(bool(value) for value in proctoring_config.values())
    return False


def _credit_activity_label(tx):
    tx_type = str(tx.get("transaction_type") or "")
    if tx_type == "practice_interview":
        return (
            "Practice Interview (Proctored)"
            if _is_proctored(tx)
            else "Practice Interview (Non-Proctored)"
        )
    if tx_type == "real_interview_recruiter":
        return (
            "Real Interview (Proctored)"
            if _is_proctored(tx)
            else "Real Interview (Non-Proctored)"
        )
    if tx_type == "ai_jd_generation":
        return "AI JD Generation"
    if tx_type == "migration_recharge":
        return "Migration Recharge"
    return _humanize_tx_type(tx_type)


def _tx_reference(tx):
    return (
        f"{tx.get('reference_type')}:{tx.get('reference_id')}"
        if tx.get("reference_type") and tx.get("reference_id")
        else "-"
    )


def _format_activity_row(tx):
    delta = int(tx.get("delta_credits", 0) or 0)
    return {
        "id": tx.get("id"),
        "activity_type": _credit_activity_label(tx),
        "action": _credit_activity_label(tx),
        "transaction_type": tx.get("transaction_type"),
        "reference": _tx_reference(tx),
        "credits_deducted": abs(delta) if delta < 0 else 0,
        "delta_credits": delta,
        "balance_after": int(tx.get("balance_after", 0) or 0),
        "remaining_balance": int(tx.get("balance_after", 0) or 0),
        "timestamp": _format_tx_timestamp(tx.get("created_at")),
    }


def _format_recharge_row(tx):
    return {
        "id": tx.get("id"),
        "activity_type": _credit_activity_label(tx),
        "action": _credit_activity_label(tx),
        "transaction_type": tx.get("transaction_type"),
        "reference": _tx_reference(tx),
        "credits_added": max(0, int(tx.get("delta_credits", 0) or 0)),
        "delta_credits": int(tx.get("delta_credits", 0) or 0),
        "balance_after": int(tx.get("balance_after", 0) or 0),
        "remaining_balance": int(tx.get("balance_after", 0) or 0),
        "timestamp": _format_tx_timestamp(tx.get("created_at")),
    }


@profile_bp.route("/profile", methods=["GET"])
@cross_origin()
@token_required
def get_profile(current_user):
    """Get user profile data"""
    result, status_code = profile_controller.get_profile(str(current_user["_id"]))
    return jsonify(result), status_code


@profile_bp.route("/profile", methods=["PUT"])
@cross_origin()
@token_required
def update_profile(current_user):
    """Update user profile data"""
    data = request.get_json()
    result, status_code = profile_controller.update_profile(
        str(current_user["_id"]), data
    )
    return jsonify(result), status_code


@profile_bp.route("/company-profile", methods=["PUT"])
@cross_origin()
@token_required
def update_company_profile(current_user):
    """Update company profile data for recruiters"""
    data = request.get_json()
    result, status_code = profile_controller.update_company_profile(
        str(current_user["_id"]), data
    )
    return jsonify(result), status_code


@profile_bp.route("/cv-details", methods=["GET"])
@cross_origin()
@token_required
def get_cv_details(current_user):
    """Get CV details for the current user"""
    result, status_code = profile_controller.get_cv_details(str(current_user["_id"]))
    return jsonify(result), status_code


@profile_bp.route("/cv-details", methods=["PUT"])
@cross_origin()
@token_required
def update_cv_details(current_user):
    """Update CV details for the current user"""
    data = request.get_json()
    result, status_code = profile_controller.update_cv_details(
        str(current_user["_id"]), data
    )
    return jsonify(result), status_code


@profile_bp.route("/recruiter/cost-statistics", methods=["GET"])
@cross_origin()
@token_required
def get_recruiter_cost_statistics(current_user):
    """Get recruiter dashboard with wallet-backed credit activity only."""
    try:
        if str(current_user.get("user_type") or "").strip().lower() != "recruiter":
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Only recruiters can access cost statistics",
                    }
                ),
                403,
            )

        recruiter_id = str(current_user["_id"])
        db = db_config.get_db()
        wallet_service = WalletService(db)

        jobs = list(db.jobs.find({"created_by": recruiter_id}))
        job_ids = [str(job["_id"]) for job in jobs]
        applications = (
            list(db.applications.find({"job_id": {"$in": job_ids}, "is_visible": True}))
            if job_ids
            else []
        )

        wallet = wallet_service.get_wallet_summary(recruiter_id, "recruiter")
        tx_list = wallet_service.get_transactions(
            recruiter_id, "recruiter", limit=100, kind="deductions"
        )
        recharge_list = wallet_service.get_recharge_history(
            recruiter_id, "recruiter", limit=100
        )

        monthly_map = {}
        for tx in tx_list:
            delta = int(tx.get("delta_credits", 0) or 0)
            if delta >= 0:
                continue
            month_key = _get_tx_month(tx.get("created_at"))
            monthly_map[month_key] = int(monthly_map.get(month_key, 0) or 0) + abs(delta)

        usage_history = [
            {"month": key, "interviews": monthly_map[key]}
            for key in sorted(monthly_map.keys())
        ]

        recent_activity = [
            _format_activity_row(tx)
            for tx in tx_list
            if str(tx.get("transaction_type") or "") in DEDUCTION_ACTIVITY_TYPES
            and int(tx.get("delta_credits", 0) or 0) < 0
        ][:20]
        recharge_history = [
            _format_recharge_row(tx)
            for tx in recharge_list
            if str(tx.get("transaction_type") or "") in RECHARGE_ACTIVITY_TYPES
            and int(tx.get("delta_credits", 0) or 0) > 0
        ][:20]

        plan_name = (
            ((wallet.get("latest_recharge") or {}).get("plan_name"))
            or "Recruiter Wallet"
        )
        credits_allocated = int(wallet.get("total_credited", 0) or 0)
        credits_used = int(wallet.get("total_debited", 0) or 0)
        credits_remaining = int(wallet.get("credits_balance", 0) or 0)

        cost_data = {
            "recruiter": {
                "name": current_user.get("name", "Recruiter"),
                "email": current_user.get("email", ""),
                "company": current_user.get("company_name", "Company"),
                "joinedDate": (
                    current_user.get("created_at", datetime.utcnow()).strftime("%Y-%m-%d")
                    if isinstance(current_user.get("created_at"), datetime)
                    else str(current_user.get("created_at", ""))[:10]
                ),
            },
            "plan": {
                "name": plan_name,
                "credits_allocated": credits_allocated,
                "credits_used": credits_used,
                "credits_remaining": credits_remaining,
                "total_credits_allocated": credits_allocated,
                "total_credits_used": credits_used,
                "current_balance": credits_remaining,
                # Backward-compatible aliases used by current recruiter UI
                "interviews_allowed": credits_allocated,
                "interviews_used": credits_used,
                "interviews_remaining": credits_remaining,
                "plan_interviews_allowed": credits_allocated,
                "plan_interviews_used": credits_used,
                "plan_interviews_remaining": credits_remaining,
                "free_interviews_allowed": 0,
                "free_interviews_used": 0,
                "free_interviews_remaining": 0,
                "signup_bonus_granted": bool(wallet.get("signup_bonus_granted", False)),
                "signup_bonus_credits": 100,
                "expires_at": None,
            },
            "usageHistory": usage_history,
            "recentActivity": recent_activity,
            "rechargeHistory": recharge_history,
            "summary": {
                "totalJobs": len(jobs),
                "totalApplicants": len(applications),
                "totalInterviews": len(
                    [
                        app
                        for app in applications
                        if str(app.get("status", "")).lower()
                        in ["interviewed", "selected", "rejected"]
                    ]
                ),
                "activeJobs": len(
                    [
                        job
                        for job in jobs
                        if str(job.get("status", "active")).lower() == "active"
                    ]
                ),
            },
        }

        return jsonify({"success": True, "data": cost_data}), 200
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@profile_bp.route("/candidate/cost-statistics", methods=["GET"])
@cross_origin()
@token_required
def get_candidate_cost_statistics(current_user):
    """Get candidate dashboard with wallet-backed credit activity only."""
    try:
        user_type = str((current_user.get("user_type") or "candidate")).strip().lower()
        if user_type not in ["candidate", "student"]:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Only candidates can access cost statistics",
                    }
                ),
                403,
            )

        candidate_id = str(current_user["_id"])
        db = db_config.get_db()
        wallet_service = WalletService(db)

        wallet = wallet_service.get_wallet_summary(candidate_id, "candidate")
        tx_list = wallet_service.get_transactions(
            candidate_id, "candidate", limit=100, kind="deductions"
        )
        recharge_list = wallet_service.get_recharge_history(
            candidate_id, "candidate", limit=100
        )

        six_months_ago = datetime.utcnow() - timedelta(days=180)
        practice_sessions = list(
            db.practice_sessions.find(
                {
                    "user_id": candidate_id,
                    "is_practice": True,
                    "created_at": {"$gte": six_months_ago},
                }
            ).sort("created_at", 1)
        )

        monthly_map = {}
        for session in practice_sessions:
            created_at = session.get("created_at")
            if not isinstance(created_at, datetime):
                continue

            month_key = created_at.strftime("%Y-%m")
            current = monthly_map.get(
                month_key,
                {
                    "month": month_key,
                    "total_sessions": 0,
                    "completed_sessions": 0,
                    "credits_used": 0,
                },
            )

            current["total_sessions"] += 1

            usage_deduction = session.get("usage_deduction") or {}
            try:
                credits_deducted = int(usage_deduction.get("credits_deducted", 0) or 0)
            except (TypeError, ValueError):
                credits_deducted = 0
            current["credits_used"] += max(0, credits_deducted)

            if str(session.get("status", "")).lower() == "completed":
                current["completed_sessions"] += 1

            monthly_map[month_key] = current

        monthly_usage = [monthly_map[key] for key in sorted(monthly_map.keys())]

        # Prefer transaction-derived monthly debits if available.
        tx_monthly_map = {}
        for tx in tx_list:
            delta = int(tx.get("delta_credits", 0) or 0)
            if delta >= 0:
                continue
            month_key = _get_tx_month(tx.get("created_at"))
            tx_monthly_map[month_key] = int(tx_monthly_map.get(month_key, 0) or 0) + abs(delta)
        if tx_monthly_map:
            monthly_usage = [
                {
                    "month": key,
                    "total_sessions": 0,
                    "completed_sessions": 0,
                    "credits_used": tx_monthly_map[key],
                }
                for key in sorted(tx_monthly_map.keys())
            ]

        completed_sessions = [
            s
            for s in practice_sessions
            if str(s.get("status", "")).lower() == "completed"
        ]

        avg_interview_score = 0
        if completed_sessions:
            score_values = [
                int(s.get("interview_score", 0) or 0)
                for s in completed_sessions
                if s.get("interview_score") is not None
            ]
            if score_values:
                avg_interview_score = round(sum(score_values) / len(score_values), 1)

        recent_activity = [
            _format_activity_row(tx)
            for tx in tx_list
            if str(tx.get("transaction_type") or "") == "practice_interview"
            and int(tx.get("delta_credits", 0) or 0) < 0
        ][:20]
        recharge_history = [
            _format_recharge_row(tx)
            for tx in recharge_list
            if str(tx.get("transaction_type") or "") in RECHARGE_ACTIVITY_TYPES
            and int(tx.get("delta_credits", 0) or 0) > 0
        ][:20]

        plan_name = (
            ((wallet.get("latest_recharge") or {}).get("plan_name"))
            or "Candidate Wallet"
        )
        credits_allocated = int(wallet.get("total_credited", 0) or 0)
        credits_remaining = int(wallet.get("credits_balance", 0) or 0)
        credits_used = int(wallet.get("total_debited", 0) or 0)
        plan_credits_allocated = credits_allocated
        plan_credits_used = credits_used
        plan_credits_remaining = credits_remaining
        free_credits_allocated = 0
        free_credits_used = 0
        free_credits_remaining = 0

        cost_data = {
            "candidate": {
                "name": current_user.get("name", "Candidate"),
                "email": current_user.get("email", ""),
                "joinedDate": (
                    current_user.get("created_at", datetime.utcnow()).strftime(
                        "%Y-%m-%d"
                    )
                    if isinstance(current_user.get("created_at"), datetime)
                    else str(current_user.get("created_at", ""))[:10]
                ),
            },
            "plan": {
                "name": plan_name,
                "credits_allocated": credits_allocated,
                "credits_remaining": credits_remaining,
                "credits_used": credits_used,
                "total_credits_allocated": credits_allocated,
                "total_credits_used": credits_used,
                "current_balance": credits_remaining,
                "plan_credits_allocated": plan_credits_allocated,
                "plan_credits_used": plan_credits_used,
                "plan_credits_remaining": plan_credits_remaining,
                "free_credits_allocated": free_credits_allocated,
                "free_credits_used": free_credits_used,
                "free_credits_remaining": free_credits_remaining,
                "signup_bonus_granted": bool(wallet.get("signup_bonus_granted", False)),
                "signup_bonus_credits": 100,
                "expires_at": (
                    None
                ),
            },
            "monthlyUsage": monthly_usage,
            "recentActivity": recent_activity,
            "rechargeHistory": recharge_history,
            "summary": {
                "totalPracticeSessions": len(practice_sessions),
                "completedPracticeSessions": len(completed_sessions),
                "avgInterviewScore": avg_interview_score,
                "totalPracticeCreditsUsed": credits_used,
                "totalUsageCostUsd": 0.0,
            },
        }

        return jsonify({"success": True, "data": cost_data}), 200

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500
