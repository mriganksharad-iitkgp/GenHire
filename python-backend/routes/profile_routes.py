from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from controllers.profile_controller import ProfileController
from middleware.auth_middleware import token_required, recruiter_required
from config.database import db_config
import random
from datetime import datetime, timedelta
from services.interview_quota_service import get_recruiter_interview_quota
from services.candidate_practice_quota_service import get_candidate_practice_quota

profile_bp = Blueprint("profile", __name__, url_prefix="/api")

# Initialize profile controller
collections = db_config.get_collections()
profile_controller = ProfileController(collections)


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
    """Get cost statistics for the logged in recruiter based on their actual data"""
    try:
        from services.credit_service import (
            calculate_recruiter_credits,
            generate_usage_history,
            generate_job_breakdown,
        )

        # Verify user is a recruiter
        if current_user.get("user_type") != "recruiter":
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

        # Get recruiter's jobs - query with string ID (consistent with admin portal)
        jobs = list(db.jobs.find({"created_by": recruiter_id}))

        # Debug log
        print(f"[Cost Stats] Recruiter {recruiter_id} has {len(jobs)} jobs")

        # Get applications for recruiter's jobs (only visible ones - CV scoring complete)
        job_ids = [str(job["_id"]) for job in jobs]
        all_applications = (
            list(db.applications.find({"job_id": {"$in": job_ids}, "is_visible": True}))
            if job_ids
            else []
        )
        applications_count = len(all_applications)

        # Count ALL interviews (for summary/overview stats)
        all_interviews_count = len(
            [
                app
                for app in all_applications
                if str(app.get("status", "")).lower()
                in ["interviewed", "selected", "rejected"]
            ]
        )

        # Count interviews in the LAST 30 DAYS only (for credit/quota calculation)
        # Use updated_at (when status was changed to interviewed), not applied_at (when candidate applied)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        interviews_count_last_30_days = len(
            [
                app
                for app in all_applications
                if str(app.get("status", "")).lower()
                in ["interviewed", "selected", "rejected"]
                and app.get("updated_at", datetime.min) >= thirty_days_ago
            ]
        )

        # Debug log
        print(
            f"[Cost Stats] Applications: {applications_count}, All Interviews: {all_interviews_count}, Last 30 days: {interviews_count_last_30_days}"
        )

        # Shared quota snapshot (same source used by interview start enforcement)
        quota = get_recruiter_interview_quota(db, recruiter_id)

        # Get recruiter's subscription for metadata (plan name / expiry) if available
        subscription = None
        if quota.get("subscription_id"):
            subscription = db.subscriptions.find_one({"_id": quota["subscription_id"]})

        # Get plan details if subscription exists
        plan = None
        if subscription and subscription.get("plan_id"):
            plan = db.plans.find_one({"_id": subscription["plan_id"]})

        # Calculate credits using shared service (uses last-30-days interviews for quota)
        credits_data = calculate_recruiter_credits(
            recruiter=current_user,
            jobs=jobs,
            applications_count=applications_count,
            interviews_count=interviews_count_last_30_days,
            plan=plan,
            add_variation=True,
        )

        # Generate usage history from real interview data
        usage_history = generate_usage_history(
            credits_data["breakdown"]["cloudflare"],
            credits_data["breakdown"]["nlp"],
            credits_data["breakdown"]["llm"],
            weeks=6,
            db=db,
            job_ids=job_ids,
        )

        # Use centralized quota values to prevent drift from start-interview logic
        interviews_used_for_quota = int(quota.get("interviews_used", 0) or 0)
        interviews_allowed_for_quota = int(quota.get("interviews_allowed", 2) or 2)
        interviews_remaining_for_quota = int(quota.get("interviews_remaining", 0) or 0)
        plan_interviews_allowed = int(quota.get("plan_interviews_allowed", 0) or 0)
        plan_interviews_used = int(quota.get("plan_interviews_used", 0) or 0)
        plan_interviews_remaining = int(quota.get("plan_interviews_remaining", 0) or 0)
        free_interviews_allowed = int(quota.get("free_interviews_allowed", 2) or 2)
        free_interviews_used = int(quota.get("free_interviews_used", 0) or 0)
        free_interviews_remaining = int(quota.get("free_interviews_remaining", 0) or 0)

        # Keep overview in sync with the same monthly quota window
        interviews_count_last_30_days = interviews_used_for_quota

        # Build monthly pipeline quality data (interviewed/selected/rejected)
        monthly_pipeline_map = {}
        for app in all_applications:
            status = str(app.get("status", "")).lower()
            if status not in ["interviewed", "selected", "rejected"]:
                continue

            status_time = app.get("updated_at") or app.get("applied_at")
            if not isinstance(status_time, datetime):
                continue

            month_key = status_time.strftime("%Y-%m")
            if month_key not in monthly_pipeline_map:
                monthly_pipeline_map[month_key] = {
                    "month": month_key,
                    "interviewed": 0,
                    "selected": 0,
                    "rejected": 0,
                }

            monthly_pipeline_map[month_key][status] += 1

        monthly_pipeline = [
            monthly_pipeline_map[k] for k in sorted(monthly_pipeline_map.keys())
        ]

        # Generate job breakdown
        job_breakdown = generate_job_breakdown(jobs, max_jobs=10)

        # Generate recent activity based on applications
        recent_activity = []
        # Fixed credit costs per activity type (deterministic)
        activity_types = [
            ("CV Analysis", "nlp", 27),
            ("Video Interview", "cloudflare", 80),
            ("Interview Evaluation", "llm", 42),
            ("Job Description Matching", "nlp", 15),
        ]

        sorted_applications = sorted(
            all_applications,
            key=lambda x: x.get("applied_at", datetime.min),
            reverse=True,
        )[:10]
        for i, app in enumerate(sorted_applications):
            activity_type = activity_types[i % len(activity_types)]
            job = next((j for j in jobs if str(j["_id"]) == app.get("job_id")), None)

            recent_activity.append(
                {
                    "id": i + 1,
                    "action": activity_type[0],
                    "job": job.get("title", "Unknown Job") if job else "Unknown Job",
                    "credits": activity_type[2],
                    "service": activity_type[1],
                    "timestamp": app.get("applied_at", datetime.utcnow()).strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                }
            )

        # If no applications, show placeholder activity based on jobs
        today = datetime.utcnow()
        if not recent_activity:
            for i in range(min(6, max(1, len(jobs)))):
                activity_type = activity_types[i % len(activity_types)]
                # Deterministic timestamp offset based on index
                timestamp = today - timedelta(hours=(i + 1) * 12)
                recent_activity.append(
                    {
                        "id": i + 1,
                        "action": activity_type[0],
                        "job": (
                            jobs[i % len(jobs)].get("title", "Sample Job")
                            if jobs
                            else "No Jobs Yet"
                        ),
                        "credits": activity_type[2],
                        "service": activity_type[1],
                        "timestamp": timestamp.strftime("%Y-%m-%d %H:%M"),
                    }
                )

        cost_data = {
            "recruiter": {
                "name": current_user.get("name", "Recruiter"),
                "email": current_user.get("email", ""),
                "company": current_user.get("company_name", "Company"),
                "joinedDate": (
                    current_user.get("created_at", datetime.utcnow()).strftime(
                        "%Y-%m-%d"
                    )
                    if isinstance(current_user.get("created_at"), datetime)
                    else str(current_user.get("created_at", ""))[:10]
                ),
            },
            "plan": {
                "name": credits_data["plan"]["name"],
                "interviews_allowed": interviews_allowed_for_quota,
                "interviews_remaining": interviews_remaining_for_quota,
                "interviews_used": interviews_used_for_quota,
                "plan_interviews_allowed": plan_interviews_allowed,
                "plan_interviews_used": plan_interviews_used,
                "plan_interviews_remaining": plan_interviews_remaining,
                "free_interviews_allowed": free_interviews_allowed,
                "free_interviews_used": free_interviews_used,
                "free_interviews_remaining": free_interviews_remaining,
                "expires_at": (
                    subscription.get("expires_at").strftime("%Y-%m-%d")
                    if subscription and subscription.get("expires_at")
                    else None
                ),
            },
            "credits": {
                "allocated": credits_data["allocated"],
                "used": credits_data["used"],
                "available": credits_data["available"],
                "usage_percentage": credits_data["usage_percentage"],
                "cloudflare": {
                    "allocated": credits_data["allocation"]["cloudflare"],
                    "used": credits_data["breakdown"]["cloudflare"],
                },
                "nlp": {
                    "allocated": credits_data["allocation"]["nlp"],
                    "used": credits_data["breakdown"]["nlp"],
                },
                "llm": {
                    "allocated": credits_data["allocation"]["llm"],
                    "used": credits_data["breakdown"]["llm"],
                },
            },
            "usageHistory": usage_history,
            "monthlyPipeline": monthly_pipeline,
            "recentActivity": recent_activity,
            "jobBreakdown": job_breakdown,
            "summary": {
                "totalJobs": credits_data["activity"]["total_jobs"],
                "totalApplicants": credits_data["activity"]["total_applicants"],
                "totalInterviews": interviews_count_last_30_days,
                "activeJobs": credits_data["activity"]["active_jobs"],
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
    """Get candidate practice subscription and usage statistics."""
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

        quota = get_candidate_practice_quota(db, candidate_id)
        subscription = None
        if quota.get("subscription_id"):
            subscription = db.subscriptions.find_one({"_id": quota["subscription_id"]})

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

        recent_activity = []
        total_practice_credits_used = 0
        total_usage_cost_usd = 0.0
        for index, session in enumerate(reversed(practice_sessions[-10:])):
            created_at = session.get("created_at")
            usage_deduction = session.get("usage_deduction") or {}
            usage_summary = session.get("usage_summary") or {}
            try:
                credits_deducted = int(usage_deduction.get("credits_deducted", 0) or 0)
            except (TypeError, ValueError):
                credits_deducted = 0
            try:
                usage_cost = float(
                    usage_summary.get(
                        "total_cost", usage_deduction.get("usage_cost_usd", 0.0)
                    )
                    or 0.0
                )
            except (TypeError, ValueError):
                usage_cost = 0.0

            total_practice_credits_used += max(0, credits_deducted)
            total_usage_cost_usd += max(0.0, usage_cost)

            recent_activity.append(
                {
                    "id": index + 1,
                    "action": "Practice Interview",
                    "role": session.get("role", "general"),
                    "status": session.get("status", "active"),
                    "credits_deducted": max(0, credits_deducted),
                    "usage_cost_usd": round(max(0.0, usage_cost), 6),
                    "timestamp": (
                        created_at.strftime("%Y-%m-%d %H:%M")
                        if isinstance(created_at, datetime)
                        else ""
                    ),
                }
            )

        plan_name = quota.get("plan_name", "Free Tier")
        subscription_credits_allocated = int(
            (subscription or {}).get(
                "interviews_allowed", (subscription or {}).get("credits_allocated", 0)
            )
            or 0
        )
        subscription_credits_remaining = int(
            (subscription or {}).get(
                "interviews_remaining", (subscription or {}).get("credits_remaining", 0)
            )
            or 0
        )
        subscription_credits_used = int(
            (subscription or {}).get(
                "interviews_used", (subscription or {}).get("credits_used", 0)
            )
            or 0
        )
        has_paid_subscription = (
            subscription is not None and subscription_credits_allocated > 0
        )

        if has_paid_subscription:
            credits_allocated = subscription_credits_allocated
            credits_remaining = subscription_credits_remaining
            credits_used = subscription_credits_used
            plan_credits_allocated = subscription_credits_allocated
            plan_credits_used = subscription_credits_used
            plan_credits_remaining = subscription_credits_remaining
            free_credits_allocated = int(quota.get("free_interviews_allowed", 0) or 0)
            free_credits_used = int(quota.get("free_interviews_used", 0) or 0)
            free_credits_remaining = int(quota.get("free_interviews_remaining", 0) or 0)
        else:
            credits_allocated = int(quota.get("interviews_allowed", 1500) or 1500)
            credits_remaining = int(quota.get("interviews_remaining", 0) or 0)
            credits_used = int(quota.get("interviews_used", 0) or 0)
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
                "plan_credits_allocated": plan_credits_allocated,
                "plan_credits_used": plan_credits_used,
                "plan_credits_remaining": plan_credits_remaining,
                "free_credits_allocated": free_credits_allocated,
                "free_credits_used": free_credits_used,
                "free_credits_remaining": free_credits_remaining,
                "expires_at": (
                    subscription.get("expires_at").strftime("%Y-%m-%d")
                    if subscription and subscription.get("expires_at")
                    else None
                ),
            },
            "monthlyUsage": monthly_usage,
            "recentActivity": recent_activity,
            "summary": {
                "totalPracticeSessions": len(practice_sessions),
                "completedPracticeSessions": len(completed_sessions),
                "avgInterviewScore": avg_interview_score,
                "totalPracticeCreditsUsed": total_practice_credits_used,
                "totalUsageCostUsd": round(total_usage_cost_usd, 6),
            },
        }

        return jsonify({"success": True, "data": cost_data}), 200

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500
