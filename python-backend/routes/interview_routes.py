"""Interview REST API routes.

The interview engine's HTTP surface (start/question/answer/end, gaze recorder,
recording uploads, face registration/verification) moved verbatim from app.py.
Handlers are module-level functions sharing module state injected once via
init_interview_routes() from the composition root, matching the
init_admin_routes() pattern.

Decomposing these ~1,400 lines into a proper controller/service split is a
follow-up; this module is a pure move so the diff stays reviewable.
"""

import base64
import datetime
import logging
import os
import re
import threading
import time

from bson import ObjectId
from flask import Blueprint, Response, jsonify, request
from werkzeug.utils import secure_filename

from config.database import db_config
from extensions import socketio
from interview.core.cost_tracker import CostTracker
from core import config as app_config
from interview.runtime import (
    M_RECORDING_FOLDER,
    PROCTORING_FOLDER,
    RECORDING_FOLDER,
    TMP_FOLDER,
    gaze_recorder_service,
    interview_manager,
    live_sessions,
)
from middleware.auth_middleware import token_required
from payment_module.config.settings import PaymentConfig
from payment_module.services.wallet_service import WalletService
from services import face_verification_service as face_service
from services import face_match_service
from services import identity_card_service
from services import interview_credit_service
from services import interview_integrity_service as integrity
from services.cv_scoring_service import CVScoringService
from services.email_service import EmailService
from services.usage_telemetry_service import record_usage_event
from services.llm_fallback_service import default_model_for, get_provider_priority
from services.interview_voice_policy import voice_policy
from services.interview_flow_service import (
    normalize_proctoring_config, percentage, result_payload, serialized_session, evaluation_percentage, cached_answer_result, schedule_evaluation_refresh, stop_companion,
)
from services.proctoring_service import (
    create_mobile_pairing_token, validate_mobile_pairing_token,
    mobile_is_ready, build_proctoring_report,
)

logger = logging.getLogger(__name__)

interview_bp = Blueprint("interviews", __name__)

# Module state injected by init_interview_routes() before registration.
db = None
collections = None
users_collection = None
interviews_collection = None
applications_collection = None
jobs_collection = None


def init_interview_routes(database, colls):
    """Inject the connected database/collections (call before registering)."""
    global db, collections, users_collection, interviews_collection
    global applications_collection, jobs_collection
    db = database
    collections = colls
    users_collection = colls["users"]
    interviews_collection = colls["interviews"]
    applications_collection = colls["applications"]
    jobs_collection = colls["jobs"]


# Optional import - RecordingAnalyzer has heavy dependencies that may conflict
# (import disabled long ago; the stub preserves the runtime no-op behavior).
RecordingAnalyzer = None
RECORDING_ANALYZER_AVAILABLE = False

# Optional CV formatter (does not run AI scoring here)
try:
    cv_service = CVScoringService()
except Exception as e:
    print(f"Warning initializing CVScoringService for formatting: {e}")
    cv_service = None

# Initialize RecordingAnalyzer if available
if RECORDING_ANALYZER_AVAILABLE and RecordingAnalyzer is not None:
    try:
        recording_analyzer = RecordingAnalyzer()
        print("[OK] RecordingAnalyzer initialized successfully")
    except Exception as e:
        print(f"[WARN] Warning initializing RecordingAnalyzer: {e}")
        recording_analyzer = None
else:
    recording_analyzer = None
    print("â„¹ RecordingAnalyzer not available - recording analysis features disabled")


def _format_cv_from_details(cv_details: dict) -> str:
    parts = []
    if not isinstance(cv_details, dict):
        return ""
    pi = cv_details.get("personalInfo", {})
    if pi:
        parts.append("PERSONAL INFORMATION")
        for k in ["fullName", "email", "phone", "location", "linkedin", "github"]:
            v = pi.get(k)
            if v:
                parts.append(str(v))
    if cv_details.get("professionalSummary"):
        parts.append(cv_details.get("professionalSummary"))
    for edu in cv_details.get("education", []) or []:
        line = " ".join(
            filter(
                None,
                [edu.get("degree"), edu.get("institution"), str(edu.get("year") or "")],
            )
        )
        if line.strip():
            parts.append(line)
        if edu.get("description"):
            parts.append(edu["description"])
    for exp in cv_details.get("workExperience", []) or []:
        line = " ".join(
            filter(
                None,
                [
                    exp.get("jobTitle"),
                    exp.get("company"),
                    str(exp.get("duration") or ""),
                ],
            )
        )
        if line.strip():
            parts.append(line)
        if exp.get("description"):
            parts.append(exp["description"])
    skills = cv_details.get("skills", {})
    for key in ["technical", "soft", "languages"]:
        arr = skills.get(key)
        if arr:
            parts.append(", ".join(arr))
    for proj in cv_details.get("projects", []) or []:
        if proj.get("title"):
            parts.append(proj["title"])
        if proj.get("description"):
            parts.append(proj["description"])
    return "\n".join(parts)


def _format_job_from_doc(job: dict) -> str:
    if not isinstance(job, dict):
        return ""
    parts = []
    for k in [
        "title",
        "company",
        "department",
        "location",
        "type",
        "experience",
        "salary",
    ]:
        v = job.get(k)
        if v:
            parts.append(str(v))
    if job.get("description"):
        parts.append(job["description"])
    for sec in ["skills", "responsibilities", "requirements", "benefits"]:
        vals = job.get(sec) or []
        if isinstance(vals, list) and vals:
            parts.append("\n".join([str(x) for x in vals]))
    return "\n".join(parts)


@interview_bp.route("/api/interviews/start", methods=["POST"])
@token_required
def start_interview(current_user):
    """Lease creation in MongoDB so retries cannot create two paid attempts."""
    import uuid
    application_id = (request.get_json(silent=True) or {}).get("application_id")
    try:
        app_id = ObjectId(application_id)
    except Exception:
        return jsonify({"error": "Invalid application_id"}), 400
    owner = str(current_user["_id"])
    application = applications_collection.find_one({"_id": app_id, "student_id": owner})
    if not application:
        return jsonify({"error": "Application not found"}), 404
    if application.get("interview_attempt_locked") or interviews_collection.find_one({
            "application_id": application_id, "user_id": owner, "status": "terminated"}):
        return jsonify({"error": "This interview attempt ended under the monitoring policy. Another attempt for this application is not available.",
                        "error_code": "interview_attempt_locked"}), 409
    existing = interviews_collection.find_one({"application_id": application_id,
        "user_id": owner, "status": {"$in": ["setup", "active"]}})
    if existing:
        return jsonify(_session_payload(existing)), 200
    if str(application.get("status", "")).strip().lower() not in {"shortlisted", "pending interview", "pending_interview"}:
        return jsonify({"error": "You can start this interview after the recruiter shortlists your application.",
            "error_code": "interview_not_eligible"}), 409
    lease_id = uuid.uuid4().hex
    now = datetime.datetime.utcnow()
    claimed = applications_collection.update_one({"_id": app_id, "student_id": owner, "interview_attempt_locked": {"$ne": True},
        "$or": [{"interview_start_lease": {"$exists": False}},
                {"interview_start_lease.expires_at": {"$lt": now}}]},
        {"$set": {"interview_start_lease": {"id": lease_id,
            "expires_at": now + datetime.timedelta(minutes=2)}}})
    if not claimed.modified_count:
        return jsonify({"error": "Interview setup is already starting. Please retry in a moment.",
            "error_code": "interview_start_in_progress"}), 409
    try:
        # Another worker may have finished between our initial read and lease.
        existing = interviews_collection.find_one({"application_id": application_id,
            "user_id": owner, "status": {"$in": ["setup", "active"]}})
        if existing:
            return jsonify(_session_payload(existing)), 200
        return _start_interview(current_user)
    finally:
        applications_collection.update_one({"_id": app_id, "interview_start_lease.id": lease_id},
            {"$unset": {"interview_start_lease": ""}})


def _start_interview(current_user):
    data = request.json or {}
    application_id = data.get("application_id")
    if not application_id:
        return jsonify({"error": "application_id is required"}), 400

    try:
        app_doc = applications_collection.find_one({"_id": ObjectId(application_id)})
    except Exception:
        return jsonify({"error": "Invalid application_id"}), 400

    if not app_doc:
        return jsonify({"error": "Application not found"}), 404

    app_student_id = str(app_doc.get("student_id", ""))
    current_user_id = str(current_user.get("_id", ""))
    if app_student_id != current_user_id:
        return jsonify({"error": "Unauthorized"}), 403

    # Block invite skeletons: a pre-shortlisted candidate must upload a CV
    # (i.e. complete the apply step) before the interview can start.
    if (
        app_doc.get("processing_status") == "awaiting_candidate"
        or not app_doc.get("cv_snapshot")
    ):
        return jsonify({
            "error": "Please complete your application by uploading your CV before starting the interview.",
            "error_code": "application_incomplete",
            "redirect": f"/jobs/{app_doc.get('job_id')}" if app_doc.get('job_id') else "/dashboard",
        }), 400

    student = current_user
    job = jobs_collection.find_one({"_id": ObjectId(app_doc["job_id"])})

    if not job:
        return jsonify({"error": "Job not found"}), 404

    # --- CV check (before charging credits) ---
    # For PDF CV applications, text is in cv_snapshot.text.
    # For manual-entry applications, build from structured cv_details.
    cv_snapshot = app_doc.get("cv_snapshot") or {}
    cv_text_prefetched = cv_snapshot.get("text", "").strip() if cv_snapshot else ""
    cv_details = (
        cv_snapshot.get("details")          # manual-entry snapshot stores details here
        or app_doc.get("cv_details")        # legacy / direct field
        or student.get("cv_details")        # profile fallback
    )
    if not cv_text_prefetched and not cv_details:
        return jsonify({"error": "CV not found for this application. Please re-apply with your CV before starting the interview."}), 400

    # --- Identity-card check (before charging credits) ---
    # Real interviews similarity-score the candidate's face against their
    # uploaded ID in the background at register-face time (score-only, never
    # blocking); without a card on file there is nothing to score against, so
    # the interview cannot start. Applies to every account type, including
    # recruiter-invited (burner) candidates.
    if face_service.get_mode() != "off":
        id_holder = users_collection.find_one(
            {"_id": current_user["_id"]}, {"identity_card": 1}
        ) or {}
        if not (id_holder.get("identity_card") or {}).get("image_file_id"):
            return (
                jsonify(
                    {
                        "error": "Please upload your identity card in your profile before starting an interview. Your face is verified against it when the interview begins.",
                        "error_code": "identity_card_required",
                    }
                ),
                403,
            )

    proctoring_config = normalize_proctoring_config(job.get("proctoring_config"))
    if proctoring_config["dual_camera"] and not app_config.mobile_recording_enabled():
        return jsonify({"error": "This job requires two cameras, but the mobile service is unavailable. Please contact the recruiter.",
            "error_code": "mobile_recording_disabled"}), 503

    proctoring_enabled = any(bool(v) for v in (proctoring_config or {}).values())
    recruiter_interview_cost = (
        int(PaymentConfig.RECRUITER_REAL_INTERVIEW_PROCTORED_CREDITS)
        if proctoring_enabled
        else int(PaymentConfig.RECRUITER_REAL_INTERVIEW_CREDITS)
    )
    recruiter_deduction = None
    # Refund-aware idempotency: after a refunded attempt the counter changes
    # the debit key so the next genuine attempt is charged again, while plain
    # retries of the same attempt still dedupe (see interview_credit_service).
    interview_refund_count = int(app_doc.get("interview_refund_count") or 0)
    debit_idempotency_key = interview_credit_service.real_interview_debit_key(
        application_id, interview_refund_count
    )

    # --- Interview start credit pre-check and deduction ---
    if job:
        recruiter_id = job.get("created_by")
        if recruiter_id:
            db = db_config.get_db()
            wallet_service = WalletService(db)
            availability = wallet_service.check_credit_availability(
                owner_id=str(recruiter_id),
                audience="recruiter",
                min_required_credits=recruiter_interview_cost,
            )

            if not availability.get("can_start_interview", False):
                return (
                    jsonify(
                        {
                            "error": availability.get("error")
                            or "Interview is currently unavailable for this job. The recruiter has exhausted interview credits on their plan.",
                            "error_code": availability.get("error_code")
                            or "RECRUITER_INTERVIEW_CREDITS_EXHAUSTED",
                            "plan_owner": "recruiter",
                            "can_start_interview": False,
                            "credits_required": recruiter_interview_cost,
                            "credits_remaining": availability.get(
                                "credits_remaining", 0
                            ),
                        }
                    ),
                    403,
                )

            recruiter_deduction = wallet_service.debit_wallet(
                owner_id=str(recruiter_id),
                audience="recruiter",
                credits=recruiter_interview_cost,
                transaction_type="real_interview_recruiter",
                reference_type="application",
                reference_id=str(application_id),
                metadata={
                    "application_id": str(application_id),
                    "job_id": str(job.get("_id")),
                    "proctoring_enabled": proctoring_enabled,
                    "proctoring_config": proctoring_config or {},
                    "attempt": interview_refund_count,
                },
                idempotency_key=debit_idempotency_key,
            )

            if not recruiter_deduction.get("success"):
                return (
                    jsonify(
                        {
                            "error": "Insufficient recruiter credits to start interview",
                            "error_code": recruiter_deduction.get("error_code", "insufficient_credits"),
                            "plan_owner": "recruiter",
                            "credits_required": recruiter_interview_cost,
                            "credits_remaining": recruiter_deduction.get("credits_remaining", 0),
                        }
                    ),
                    403,
                )

            wallet_service.add_audit_transaction(
                owner_id=str(current_user.get("_id")),
                audience="candidate",
                transaction_type="real_interview_candidate_audit",
                reference_type="application",
                reference_id=str(application_id),
                metadata={
                    "application_id": str(application_id),
                    "job_id": str(job.get("_id")),
                    "recruiter_id": str(recruiter_id),
                    "credits_impact": 0,
                },
                idempotency_key=(
                    f"real-interview-candidate-audit:{application_id}"
                    if interview_refund_count <= 0
                    else f"real-interview-candidate-audit:{application_id}:r{interview_refund_count}"
                ),
            )

    def _refund_start_debit(reason):
        """Reverse the just-taken recruiter debit when the start attempt dies
        before a usable session exists â€” credits used to simply vanish here."""
        if not (recruiter_deduction and recruiter_deduction.get("success")):
            return
        try:
            interview_credit_service.refund_recruiter_debit(
                db_config.get_db(),
                applications_collection,
                application_id=str(application_id),
                recruiter_id=(
                    str(job.get("created_by")) if job and job.get("created_by") else None
                ),
                deduction=recruiter_deduction,
                debit_key=debit_idempotency_key,
                session_id=None,
                reason=reason,
            )
        except Exception:
            logger.error(
                "Start-failure refund failed for application %s",
                application_id,
                exc_info=True,
            )

    # Build plain-text CV â€” prefer snapshot text (PDF CVs), fall back to structured details
    if cv_text_prefetched:
        cv_text = cv_text_prefetched
    elif cv_details:
        cv_text = (
            cv_service.format_cv_details(cv_details)
            if cv_service
            else _format_cv_from_details(cv_details)
        )
    else:
        _refund_start_debit("start_failed_empty_cv")
        return jsonify({"error": "CV content is empty. Please re-apply with a valid CV."}), 400

    try:
        jd_text = (
            cv_service.format_job_description(job)
            if cv_service
            else _format_job_from_doc(job)
        )

        # Persist as temporary .txt files for the interview document pipeline
        import uuid as _uuid

        cv_txt_path = os.path.join(TMP_FOLDER, f"{_uuid.uuid4()}_cv.txt")
        jd_txt_path = os.path.join(TMP_FOLDER, f"{_uuid.uuid4()}_jd.txt")
        with open(cv_txt_path, "w", encoding="utf-8") as f:
            f.write(cv_text)
        with open(jd_txt_path, "w", encoding="utf-8") as f:
            f.write(jd_text)

        # pre_validated=True: we just wrote these files from trusted MongoDB data
        # so there is no need to re-read and validate them inside create_session.
        session_details = interview_manager.create_session(
            cv_path=cv_txt_path,
            jd_path=jd_txt_path,
            reference_paths=[],
            proctoring_config=proctoring_config,
            pre_validated=True,
        )

        if "error" in session_details:
            _refund_start_debit("start_failed_session_creation")
            return jsonify(session_details), 400

        cv_score = app_doc.get("cv_score")
        sim_score = (
            (float(cv_score) / 100.0) if isinstance(cv_score, (int, float)) else None
        )

        interview_doc = {
            "user_id": str(current_user["_id"]),
            "session_id": session_details["session_id"],
            "cv_path": cv_txt_path,
            "jd_path": jd_txt_path,
            "reference_paths": [],
            "source_documents": {"cv_text": cv_text, "jd_text": jd_text},
            "engine_checkpoint": interview_manager.checkpoint(session_details["session_id"]),
            "application_id": application_id,
            "recruiter_id": (
                str(job.get("created_by")) if job and job.get("created_by") else None
            ),
            "status": "setup",
            "similarity_score": sim_score,
            "cv_score": percentage(cv_score),
            "dual_proctoring_required": proctoring_config["dual_camera"],
            "setup_required": True,
            "proctoring_config": proctoring_config,
            # Initialized here (not just at /end) so a crashed/abandoned interview
            # still has an auditable record instead of no proctoring data at all.
            "proctoring_score": None,
            "proctoring_status": "pending",
            "usage_deduction": recruiter_deduction,
            # Persisted so refunds can reverse exactly this debit later (the
            # transaction payload stored above doesn't carry the key).
            "debit_idempotency_key": debit_idempotency_key,
            "questions_answered_count": 0,
            "created_at": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow(),
            "start_time": time.time(),
        }

        interview_id = interviews_collection.insert_one(interview_doc).inserted_id
    except Exception:
        # Any unexpected failure between the debit and a persisted session
        # doc means no interview can ever happen for this charge â€” refund,
        # then let the global 500 handler answer the client.
        _refund_start_debit("start_failed_unexpected_error")
        raise

    return jsonify(
        {
            "interview_id": str(interview_id),
            "session_id": session_details["session_id"],
            "initial_questions": [session_details["first_question"]],
            "similarity_score": sim_score,
            "conversation_context": session_details.get("conversation_context", {}),
            "question_timeout_seconds": session_details.get("question_timeout_seconds"),
            "question_deadline": None,
            "voice_policy": voice_policy(),
            "max_questions": session_details.get("max_questions"),
            "proctoring_config": interview_doc["proctoring_config"],
            "credits_deducted": recruiter_interview_cost,
            "usage_deduction": recruiter_deduction,
            "status": "setup",
            "setup_required": True,
            "cv_score": percentage(cv_score),
            "dual_proctoring_required": proctoring_config["dual_camera"],
            "mobile_recording_enabled": proctoring_config["dual_camera"],
            "mobile_pairing_token": create_mobile_pairing_token(session_details["session_id"], str(current_user["_id"])) if proctoring_config["dual_camera"] else None,
            "recruiter_wallet_balance": (recruiter_deduction or {}).get("transaction", {}).get("balance_after"),
        }
    )


def _owned_session(user_id, session_id):
    doc = interviews_collection.find_one({"session_id": session_id, "user_id": str(user_id)})
    if doc:
        return doc, interviews_collection, interview_manager
    doc = collections["practice_sessions"].find_one({"session_id": session_id, "user_id": str(user_id)})
    if doc:
        # Practice uses its own manager; do not accidentally activate a real session.
        from routes.practice_routes import practice_controller
        return doc, collections["practice_sessions"], (practice_controller.interview_api.session_manager
            if practice_controller.interview_api else None)
    return None, None, None


def _session_payload(doc, manager=None):
    if manager is None:
        _, _, manager = _owned_session(doc["user_id"], doc["session_id"])
    _restore_engine(doc, manager)
    session = manager.sessions.get(doc["session_id"]) if manager else None
    dual = bool((doc.get("proctoring_config") or {}).get("dual_camera"))
    payload = {
        "session_id": doc["session_id"], "interview_id": str(doc.get("_id", "")),
        "application_id": doc.get("application_id"), "status": doc.get("status"),
        "is_practice": bool(doc.get("is_practice")),
        "setup_required": doc.get("status") == "setup",
        "voice_policy": voice_policy(),
        "identity_captured": bool(doc.get("identity_verification")) and (doc.get("status") != "setup" or bool(live_sessions.get(doc["session_id"]))),
        "initial_questions": [session.current_question] if session else [],
        "current_question": session.current_question if session else None,
        "questions_asked": session.questions_asked if session else len(doc.get("qa_pairs") or []),
        "question_count": min((session.questions_asked if session else len(doc.get("qa_pairs") or []))
            + (0 if doc.get("status") in {"completed", "abandoned"} else 1), session.max_questions if session else (doc.get("engine_checkpoint") or {}).get("max_questions", 10)),
        "question_timeout_seconds": manager.config.question_timeout_seconds if manager else None,
        "max_questions": session.max_questions if session else (doc.get("engine_checkpoint") or {}).get("max_questions", 10),
        "question_deadline": (session.question_served_at + manager.config.question_timeout_seconds)
            if session and session.question_served_at else None,
        "cv_score": percentage(doc.get("cv_score"), normalized=bool(doc.get("is_practice"))),
        "cv_score_status": doc.get("cv_score_status"),
        "similarity_score": doc.get("similarity_score"),
        "proctoring_config": doc.get("proctoring_config") or {},
        "proctoring_enabled": doc.get("proctoring_enabled", any((doc.get("proctoring_config") or {}).values())),
        "dual_proctoring_required": dual, "mobile_recording_enabled": dual and app_config.mobile_recording_enabled(),
        "mobile_pairing_token": create_mobile_pairing_token(doc["session_id"], doc["user_id"]) if dual else None,
        "mobile_ready": mobile_is_ready(doc),
        "engine_available": session is not None,
        "last_answer": doc.get("last_answer"),
        "integrity": integrity.policy_payload(doc),
        "interview_complete": bool((session and session.is_complete) or doc.get("status") == "finishing"
            or ((doc.get("last_answer") or {}).get("result") or {}).get("interview_complete")),
    }
    if doc.get("status") in {"completed", "abandoned", "terminated"}:
        terminal = result_payload(doc)
        payload.update(terminal)
        payload["result_status"] = terminal["status"]
        payload["status"] = doc["status"]
    return payload


def _restore_engine(doc, manager):
    if not manager or doc.get("status") not in {"setup", "active", "finishing"}:
        return
    from services.interview_flow_service import session_lock
    with session_lock(doc["session_id"]):
        current = manager.sessions.get(doc["session_id"])
        newer_checkpoint = (doc.get("engine_checkpoint") or {}).get("questions_asked", 0) > getattr(current, "questions_asked", 0)
        if (current is None or newer_checkpoint) and hasattr(manager, "restore_session"):
            source = doc.get("source_documents") or {}
            if not source.get("cv_text") and doc.get("application_id"):
                application = applications_collection.find_one({"_id": ObjectId(doc["application_id"])}) or {}
                job = jobs_collection.find_one({"_id": ObjectId(application["job_id"])}) if application.get("job_id") else {}
                snapshot = application.get("cv_snapshot") or {}
                source = {"cv_text": snapshot.get("text") or _format_cv_from_details(snapshot.get("details") or application.get("cv_details") or {}),
                          "jd_text": _format_job_from_doc(job or {})}
            if not source.get("cv_text") or not source.get("jd_text"):
                return
            try:
                manager.restore_session(doc, source["cv_text"], source["jd_text"])
            except Exception:
                logger.warning("Owned interview checkpoint could not be restored: %s", doc["session_id"], exc_info=True)
                return
        if doc["session_id"] not in live_sessions and doc.get("identity_verification"):
            captured = (doc.get("identity_verification") or {}).get("captured_image_file_id")
            if captured:
                import gridfs
                try:
                    image = gridfs.GridFS(db).get(ObjectId(captured)).read()
                except Exception:
                    logger.warning("Saved face reference unavailable for %s", doc["session_id"])
                    return
                live_sessions[doc["session_id"]] = {"owner_id": str(doc["user_id"]),
                    "proctoring_config": doc.get("proctoring_config") or {},
                    "registered_face": image, "registered_face_np": face_service.decode_image(image),
                    "proctoring_score": doc.get("proctoring_score"), "infractions": {}, "analyzed_frames": 0}
                report = doc.get("proctoring_report") or {}
                coverage = report.get("coverage") or {}
                live_sessions[doc["session_id"]].update({
                    "infractions": report.get("infraction_counts") or {}, "events": report.get("events") or [],
                    "capabilities": report.get("capabilities") or {},
                    "desktop_analyzed_frames": coverage.get("desktop_analyzed_frames", 0),
                    "mobile_analyzed_frames": coverage.get("mobile_analyzed_frames", 0),
                    "analyzed_frames": coverage.get("desktop_analyzed_frames", 0) + coverage.get("mobile_analyzed_frames", 0),
                    "mobile_coverage_gaps": coverage.get("mobile_coverage_gaps", 0)})


@interview_bp.route("/api/interviews/<session_id>/session", methods=["GET"])
@token_required
def get_interview_session(current_user, session_id):
    doc, collection, manager = _owned_session(current_user["_id"], session_id)
    if not doc:
        return jsonify({"error": "Session not found"}), 404
    integrity.check_health(collection, doc)
    if doc.get("status") == "active":
        doc = collection.find_one({"_id": doc["_id"]})
    return jsonify(_session_payload(doc, manager))


@interview_bp.route("/api/interviews/<session_id>/monitoring", methods=["POST"])
@token_required
def update_monitoring(current_user, session_id):
    doc, collection, _ = _owned_session(current_user["_id"], session_id)
    if not doc:
        return jsonify({"error": "Session not found"}), 404
    data = request.get_json(silent=True) or {}
    if doc.get("status") == "active":
        values = {"desktop_monitoring.last_seen_at": integrity.utcnow(),
            "desktop_monitoring.visible": data.get("visible") is True,
            "desktop_monitoring.focused": data.get("focused") is True,
            "desktop_monitoring.secure_view": data.get("secure_view") is True,
            "desktop_monitoring.devices_ready": data.get("devices_ready") is True}
        collection.update_one({"_id": doc["_id"], "status": "active"}, {"$set": values})
        doc = collection.find_one({"_id": doc["_id"]})
        reason = data.get("interruption")
        if reason in {"tab_switch", "window_blur", "fullscreen_exit", "device_lost"}:
            integrity.reconcile(collection, doc, {"desktop": reason})
            doc = collection.find_one({"_id": doc["_id"]})
    return jsonify({"integrity": integrity.check_health(collection, doc)})


@interview_bp.route("/api/interviews/<session_id>/activate", methods=["POST"])
@token_required
@serialized_session
def activate_interview(current_user, session_id):
    doc, collection, manager = _owned_session(current_user["_id"], session_id)
    if not doc:
        return jsonify({"error": "Session not found"}), 404
    if doc.get("status") not in {"setup", "active"}:
        return jsonify({"error": "This interview has ended", "error_code": "session_ended"}), 409
    checks = request.get_json(silent=True) or {}
    if doc.get("status") == "setup":
        if not all(checks.get(key) is True for key in ("camera_ready", "microphone_ready", "speaker_ready")):
            return jsonify({"error": "Complete the laptop camera, microphone and speaker checks first.",
                "error_code": "device_checks_required"}), 409
        if not doc.get("identity_verification"):
            return jsonify({"error": "Capture your face before starting.", "error_code": "face_capture_required"}), 409
        if doc.get("dual_proctoring_required") or (doc.get("proctoring_config") or {}).get("dual_camera"):
            if not mobile_is_ready(doc):
                return jsonify({"error": "Connect the mobile camera and keep it open before starting.",
                    "error_code": "mobile_camera_required"}), 409
    if manager is None:
        return jsonify({"error": "The interview service is unavailable. Close this interrupted attempt safely before restarting.",
            "error_code": "engine_unavailable"}), 503
    _restore_engine(doc, manager)
    policy = integrity.check_health(collection, doc)
    if policy["terminated"]:
        return jsonify({"error": "Restore interview monitoring before continuing.", "error_code": "monitoring_required", "integrity": policy}), 409
    result = manager.activate_session(session_id)
    if "error" in result:
        return jsonify(result), 409
    if doc.get("status") == "active":
        if not doc.get("activated_at"):
            collection.update_one({"_id": doc["_id"], "status": "active", "activated_at": {"$exists": False}},
                {"$set": {"activated_at": integrity.utcnow(), "engine_checkpoint": manager.checkpoint(session_id) if hasattr(manager, "checkpoint") else None}})
        return jsonify(result)
    collection.update_one({"_id": doc["_id"]}, {"$set": {"status": "active",
        "activated_at": datetime.datetime.utcnow(), "device_checks": checks,
        "engine_checkpoint": manager.checkpoint(session_id) if hasattr(manager, "checkpoint") else None,
        "updated_at": datetime.datetime.utcnow()}})
    return jsonify(result)


@interview_bp.route("/api/interviews/<session_id>/question", methods=["GET"])
@token_required
def get_interview_question(current_user, session_id):
    # Only the candidate who owns this session may read its questions.
    user_id = str(current_user["_id"])
    owns_session = interviews_collection.find_one(
        {"session_id": session_id, "user_id": user_id}, {"_id": 1}
    ) or collections["practice_sessions"].find_one(
        {"session_id": session_id, "user_id": user_id}, {"_id": 1}
    )
    if not owns_session:
        return jsonify({"error": "Session not found"}), 404

    doc, _, manager = _owned_session(user_id, session_id)
    if doc.get("status") == "terminated":
        return jsonify({"error": "This interview has ended under the monitoring policy.", "error_code": "session_ended"}), 409
    _restore_engine(doc, manager)
    if manager is None:
        return jsonify({"error": "The interview service is unavailable.", "error_code": "engine_unavailable"}), 503
    question_result = manager.get_next_question(session_id)

    if "error" in question_result:
        return jsonify(question_result), 400

    return jsonify(question_result)


@interview_bp.route("/api/interviews/<session_id>/answer", methods=["POST"])
@token_required
@serialized_session
def submit_answer(current_user, session_id):
    doc = interviews_collection.find_one({"session_id": session_id, "user_id": str(current_user["_id"])})
    if not doc:
        return jsonify({"error": "Session not found"}), 404
    if doc.get("status") != "active":
        return jsonify({"error": "Start the interview after completing setup before answering.",
            "error_code": "session_not_active"}), 409
    policy = integrity.check_health(interviews_collection, doc)
    if policy["terminated"]:
        return jsonify({"error": "Restore monitoring before submitting another answer.", "error_code": "monitoring_required", "integrity": policy}), 409
    _restore_engine(doc, interview_manager)
    data = request.json or {}
    question = data.get("question")
    answer = data.get("answer")

    # `answer` may legitimately be an empty string â€” a client-side no-response
    # timeout auto-submits "" to advance the interview rather than leaving it
    # stuck. Only a missing question or a genuinely absent (None) answer is invalid.
    if not question or answer is None:
        return jsonify({"error": "Question and answer are required"}), 400
    if not isinstance(question, str) or not isinstance(answer, str) or len(question) > 12000 or len(answer) > 30000:
        return jsonify({"error": "Question and answer must be text within the allowed length."}), 400
    cached = cached_answer_result(doc, question, answer)
    if cached:
        return jsonify(cached)

    try:
        # Submit answer using new system
        result = interview_manager.submit_answer(session_id, question, answer)

        if "error" in result:
            return jsonify(result), 400

        # Restart-safe evidence for the credit-refund policy: count
        # substantive answers on the interview doc itself. Repeat requests and
        # empty auto-skips deliberately don't count â€” an interview with zero
        # real answers is refundable.
        if not result.get("repeated_question") and str(answer or "").strip():
            try:
                interviews_collection.update_one(
                    {"session_id": session_id, "user_id": str(current_user["_id"])},
                    {
                        "$inc": {"questions_answered_count": 1},
                        "$set": {"updated_at": datetime.datetime.utcnow()},
                    },
                )
            except Exception:
                logger.warning(
                    "questions_answered_count bump failed for %s", session_id
                )

        # Deep JSON serialization function to handle all types
        def make_json_serializable(obj):
            """Recursively convert an object to be JSON serializable."""
            from enum import Enum
            import datetime

            if isinstance(obj, dict):
                return {
                    key: make_json_serializable(value) for key, value in obj.items()
                }
            elif isinstance(obj, list):
                return [make_json_serializable(item) for item in obj]
            elif isinstance(obj, Enum):
                return obj.value
            elif hasattr(obj, "isoformat"):  # datetime objects
                return obj.isoformat()
            elif hasattr(obj, "__dict__"):  # custom objects with __dict__
                return make_json_serializable(obj.__dict__)
            elif isinstance(obj, (str, int, float, bool, type(None))):
                return obj
            else:
                # Convert other types to string as fallback
                return str(obj)

        # Apply deep serialization to the result
        serializable_result = make_json_serializable(result)

        if not result.get("repeated_question"):
            interviews_collection.update_one({"_id": doc["_id"]}, {
                "$push": {"qa_pairs": {"question": question, "answer": answer,
                    "evaluation": serializable_result.get("current_evaluation")},
                    "transcript": {"$each": [{"role": "assistant", "text": question},
                        {"role": "user", "text": answer}]}},
                "$set": {"last_answer": {"question": question, "answer": answer,
                    "result": serializable_result}, "engine_checkpoint": interview_manager.checkpoint(session_id) if hasattr(interview_manager, "checkpoint") else None,
                    "updated_at": datetime.datetime.utcnow()}})

        return jsonify(serializable_result)

    except Exception as e:
        print(f"Error in submit_answer: {str(e)}")
        import traceback

        print(f"Full traceback: {traceback.format_exc()}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


@interview_bp.route("/api/interviews/<session_id>/end", methods=["POST"])
@token_required
def end_interview(current_user, session_id):
    from services.interview_completion_service import complete_in_background
    doc = interviews_collection.find_one({"session_id": session_id, "user_id": str(current_user["_id"])})
    if not doc:
        return jsonify({"error": "Session not found"}), 404
    if doc.get("status") in {"completed", "abandoned", "terminated"}:
        return jsonify(result_payload(doc))
    data = request.get_json(silent=True)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return jsonify({"error": "Expected a JSON object"}), 400
    return complete_in_background(("interview", str(current_user["_id"]), session_id),
                                  lambda: _complete_interview(current_user, session_id, data), interviews_collection)


def _complete_interview(current_user, session_id, data):
    session_doc = interviews_collection.find_one({"session_id": session_id, "user_id": str(current_user["_id"])})
    if not session_doc:
        return jsonify({"error": "Session not found"}), 404
    if session_doc.get("status") in {"completed", "abandoned", "terminated"}:
        return jsonify(result_payload(session_doc))
    claimed = interviews_collection.update_one({"_id": session_doc["_id"], "status": {"$in": ["setup", "active"]}},
        {"$set": {"status": "finishing"}})
    if not claimed.matched_count:
        latest = interviews_collection.find_one({"_id": session_doc["_id"]})
        if latest and latest.get("status") == "terminated":
            return jsonify(result_payload(latest))
    tracking_data = data.get("tracking_data", [])

    def utc_now():
        return datetime.datetime.now(datetime.UTC)

    # A retry can reach a replacement Cloud Run worker; restore saved answers first.
    _restore_engine(session_doc, interview_manager)
    # Get the final evaluation from the session manager if it exists
    session = interview_manager.sessions.get(session_id)
    if live_sessions.get(session_id):
        live_sessions[session_id]["monitoring"] = False
    stop_companion(session_doc)
    final_evaluation = {}
    interview_transcript = list(session_doc.get("transcript") or [])

    # Interview score will be computed from final_evaluation below.
    # NOTE: CostTracker().end_session is called exactly once, further down,
    # after the fallback estimates are known â€” an earlier extra call here used
    # clear_events=True and wiped the real tracked usage before the billing
    # call could read it.
    interview_score = None  # Calculated after evaluation is generated
    usage_deduction = None
    session_doc = interviews_collection.find_one(
        {"session_id": session_id, "user_id": str(current_user["_id"])}
    )

    # --- Zero-answer discard -------------------------------------------------
    # The candidate ended (or lost) the interview without one substantive
    # answer: don't score it, don't mark the application interviewed, and
    # refund the recruiter's start-time debit so nobody pays for a screening
    # that never happened. The application stays in its prior status, so the
    # candidate can simply start again.
    answered_count = interview_credit_service.count_answered_questions(
        session, session_doc
    )
    if session_doc and answered_count == 0:
        refund = None
        if session_doc.get("usage_deduction"):
            refund = interview_credit_service.refund_recruiter_debit(
                db_config.get_db(),
                applications_collection,
                application_id=session_doc.get("application_id"),
                recruiter_id=session_doc.get("recruiter_id"),
                deduction=session_doc.get("usage_deduction"),
                debit_key=session_doc.get("debit_idempotency_key"),
                session_id=session_id,
                reason="ended_no_answers",
            )
        interviews_collection.update_one(
            {"_id": session_doc["_id"]},
            {
                "$set": {
                    "status": "abandoned",
                    "abandoned_reason": "ended_no_answers",
                    "credits_refund": refund,
                    "updated_at": utc_now(),
                }
            },
        )
        interview_manager.sessions.pop(session_id, None)
        CostTracker().end_session(session_id, clear_events=True)

        refunded_credits = 0
        if refund and refund.get("success"):
            refunded_credits = abs(
                int(((refund.get("transaction") or {}).get("delta_credits")) or 0)
            )
        return jsonify(
            {
                "status": "interview_discarded",
                "message": (
                    "No answers were recorded, so this interview was not counted. "
                    "The interview credits were refunded and the interview can be retaken."
                ),
                "refund": {
                    "success": bool(refund and refund.get("success")),
                    "credits_refunded": refunded_credits,
                },
            }
        )

    if session:
        # If ended prematurely or completed normally, generate evaluation now
        try:
            final_evaluation = interview_manager._generate_final_evaluation(session)
        except Exception as e:
            print(f"âš ï¸ Error generating final evaluation: {e}")
            import traceback
            traceback.print_exc()
            final_evaluation = {
                "error": "Failed to generate AI evaluation.",
                "details": str(e),
                "final_score": None
            }

        # Always extract transcript regardless of evaluation success
        if hasattr(session, "interview_data") and session.interview_data:
            interview_transcript = []
            for qa in session.interview_data:
                if qa.get("question"):
                    interview_transcript.append(
                        {"role": "assistant", "text": qa.get("question", "")}
                    )
                if qa.get("answer"):
                    interview_transcript.append(
                        {"role": "user", "text": qa.get("answer", ""), "ai_probability": (qa.get("evaluation") or {}).get("ai_probability")}
                    )
    else:
        final_evaluation = {
            "summary": "Evaluation not computed in this build.",
            "final_score": None,
        }

    interview_score = evaluation_percentage(final_evaluation)

    manual_infractions = list((session_doc or {}).get("manual_infractions") or [])
    gaze_times = (session_doc or {}).get("gaze_metrics")
    gaze_plot_path = (session_doc or {}).get("gaze_plot_path")

    # Primary server analysis (or its persisted snapshot) is authoritative.
    live_session = live_sessions.get(session_id)
    proctoring_report = build_proctoring_report(live_session, session_doc)
    live_score = proctoring_report.get("final_score")

    # Only server-analyzed camera evidence earns a proctoring score. Client
    # gaze uploads are supplemental context, not authoritative score input.
    scores_available = [live_score] if live_score is not None else []
    if scores_available:
        proctoring_score = min(scores_available)
        proctoring_status = proctoring_report.get("status", "partial")
    else:
        # Neither signal is available (camera/mic denied, GazeRecorder CDN
        # blocked, etc.) â€” be honest about it instead of awarding a fabricated
        # default score that would let a candidate whose proctoring pipeline
        # failed score as if nothing was wrong.
        proctoring_score = None
        proctoring_status = "incomplete"
    if proctoring_report.get("status") == "disabled":
        proctoring_score = None
        proctoring_status = "disabled"
    interview_score = percentage(interview_score)
    cv_score = percentage((session_doc or {}).get("cv_score"))

    # Derive actual media usage from the transcript. STT time must reflect the
    # candidate's SPOKEN answers, never wall-clock session duration â€” stale
    # sessions finalized hours/days later used to record absurd audio totals
    # (hundreds of thousands of "seconds") and blow up the cost statistics.
    tts_characters = sum(
        len((item.get("text") or "").strip())
        for item in interview_transcript
        if item.get("role") == "assistant"
    )
    answer_chars = sum(
        len((item.get("text") or "").strip())
        for item in interview_transcript
        if item.get("role") == "user"
    )
    # ~4 chars/token, ~0.4 s of speech per token (â‰ˆ150 wpm), capped at 2 h.
    stt_seconds = min((answer_chars / 4.0) * 0.4, 7200.0)

    usage_summary = CostTracker().end_session(
        session_id,
        clear_events=True,
        fallback={
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_stt_seconds": stt_seconds,
            "total_tts_characters": int(tts_characters or 0),
            "model": default_model_for(get_provider_priority()[0]),
        },
    )

    existing_app = None
    usage_deduction = (session_doc or {}).get("usage_deduction") or {
        "success": True,
        "credits_deducted": 0,
        "source": "deducted_at_start",
    }

    # --- NEW: Generate and save the gaze plot ---
    if tracking_data:
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            import uuid

            times = [float(d["time"]) for d in tracking_data if "time" in d]
            ratios = [float(d["gazeRatio"]) if d.get("gazeRatio") is not None else 0.0 for d in tracking_data if "time" in d]

            plt.figure(figsize=(10, 4))
            plt.plot(times, ratios, label='Gaze Ratio', color='#667eea')
            plt.axhline(0.35, color='r', linestyle='--', label='Right Boundary')
            plt.axhline(-0.35, color='r', linestyle='--', label='Left Boundary')
            plt.title('Eye Ball Tracking - Gaze Direction Over Time')
            plt.xlabel('Time (s)')
            plt.ylabel('Gaze Ratio')
            plt.legend()

            gaze_plot_filename = f"gaze_plot_{session_id}_{uuid.uuid4().hex[:6]}.png"
            # Staged locally only long enough to upload to GCS â€” the plot is
            # served back via /api/view-file, which redirects gs:// paths to a
            # signed URL. Best-effort: a plot-upload failure must never fail
            # end-interview (scores/refunds finalize below), so on failure the
            # plot is simply absent from the report.
            os.makedirs(PROCTORING_FOLDER, exist_ok=True)
            staging_plot_path = os.path.join(PROCTORING_FOLDER, gaze_plot_filename)
            plt.savefig(staging_plot_path)
            plt.close()
            try:
                from services import gcs_service
                gaze_plot_path = gcs_service.upload_from_path(
                    staging_plot_path,
                    f"proctoring/{gaze_plot_filename}",
                    content_type="image/png",
                )
            except Exception as upload_err:
                print(f"âš ï¸ GCS upload failed for gaze plot (report will omit it): {upload_err}")
                gaze_plot_path = None
            finally:
                try:
                    os.remove(staging_plot_path)
                except OSError:
                    pass
        except Exception as e:
            print(f"âš ï¸ Failed to generate local gaze tracking plot: {e}")
            if not gaze_plot_path:  # fallback to external one if available
                pass
    elif not gaze_plot_path:
        gaze_plot_path = None

    # Update the database record with final data
    interviews_collection.update_one(
        {"session_id": session_id, "user_id": str(current_user["_id"])},
        {
            "$set": {
                "status": "completed",
                "evaluation": final_evaluation,
                "final_score": interview_score,  # Store calculated interview score
                "proctoring_score": proctoring_score,  # Store calculated proctoring score
                "proctoring_status": proctoring_status,  # "complete" or "incomplete" â€” never a fabricated fallback
                "proctoring_report": proctoring_report,
                "transcript": interview_transcript,  # Store conversation transcript
                "manual_infractions": manual_infractions,
                "gaze_metrics": gaze_times,
                "gaze_plot_path": gaze_plot_path,
                "stt_seconds": stt_seconds,
                "tts_characters": int(tts_characters or 0),
                "usage_summary": usage_summary,
                "usage_deduction": usage_deduction,
                "updated_at": utc_now(),
            }
        },
    )

    # Also update the related application with both scores if linked
    if session_doc and session_doc.get("application_id"):
        try:
            application_id = session_doc["application_id"]
            # First, check if the application exists
            existing_app = existing_app or applications_collection.find_one(
                {"_id": ObjectId(application_id)}
            )
            if not existing_app:
                print(
                    f"âŒ ERROR: Application with ID {application_id} NOT FOUND in database!"
                )
                return jsonify(
                    {
                        "status": "interview_ended",
                        "evaluation": final_evaluation,
                        "interview_score": interview_score,
                        "proctoring_score": proctoring_score,
                        "proctoring_status": proctoring_status,
                        "transcript": interview_transcript,
                        "usage_summary": usage_summary,
                        "usage_deduction": usage_deduction,
                        "error": "Application not found",
                    }
                )

            previous_status = str(existing_app.get("status", "pending")).lower()
            # Must be assigned before the notification block below uses it â€”
            # it previously wasn't set until after that block, so the email
            # thread died on a NameError and no completion mail ever went out.
            recruiter_actor_id = str(existing_app.get("recruiter_id") or "")

            result = applications_collection.update_one(
                {"_id": ObjectId(application_id)},
                {
                    "$set": {
                        "interview_score": interview_score,  # Store interview performance score
                        "proctoring_score": proctoring_score,  # Store proctoring behavior score
                        "proctoring_status": proctoring_status,
                        "stt_seconds": stt_seconds,
                        "tts_characters": int(tts_characters or 0),
                        "usage_source": "actual",
                        "status": "interviewed",
                        "updated_at": utc_now(),
                    }
                },
            )

            # Push the finished interview's scores live â€” this write path is
            # raw pymongo directly in this route (not routed through
            # ApplicationController), so the controller's real-time sync never
            # covered it; reuses the exact same application_update event shape.
            try:
                _score_update_payload = {
                    "_id": str(application_id),
                    "job_id": str(existing_app.get("job_id", "")),
                    "status": "interviewed",
                    "interview_score": interview_score,
                    "proctoring_score": proctoring_score,
                    "proctoring_status": proctoring_status,
                }
                for _room in {
                    str(existing_app.get("student_id", "")),
                    str(existing_app.get("recruiter_id", "")),
                }:
                    if _room:
                        socketio.emit(
                            "application_update",
                            {"type": "score_updated", "application": _score_update_payload},
                            room=_room,
                        )
            except Exception:
                logger.warning("application_update emit failed at interview end", exc_info=True)

            # Keep recruiter job-card counters in sync with the application status transition
            status_counters = [
                "pending",
                "interviewed",
                "screening_cleared",
                "selected",  # legacy counter field on unmigrated job docs
                "rejected",
            ]
            job_counter_update = {}

            if previous_status in status_counters and previous_status != "interviewed":
                job_counter_update[previous_status] = -1
            if previous_status != "interviewed":
                job_counter_update["interviewed"] = (
                    job_counter_update.get("interviewed", 0) + 1
                )

            if job_counter_update:
                jobs_collection.update_one(
                    {"_id": ObjectId(existing_app["job_id"])},
                    {"$inc": job_counter_update},
                )

            # Fire-and-forget: notify the recruiter that the interview is done,
            # and separately notify the candidate their own results are ready
            # (previously only the recruiter side existed here).
            try:
                recruiter_doc = users_collection.find_one(
                    {"_id": ObjectId(recruiter_actor_id)},
                    {"email": 1, "name": 1},
                ) if recruiter_actor_id else None
                _cand_name = current_user.get("name") or "A candidate"
                _job_title = existing_app.get("job_title") or "the position"
                _score = int(interview_score) if interview_score is not None else None
                _app_id = str(application_id)
                _email_svc = EmailService()

                if recruiter_doc and recruiter_doc.get("email"):
                    _rec_name = recruiter_doc.get("name") or "Recruiter"
                    _rec_email = recruiter_doc["email"]
                    threading.Thread(
                        target=_email_svc.send_interview_complete_notification,
                        args=(_rec_email, _rec_name, _cand_name, _job_title, _score, _app_id),
                        daemon=True,
                    ).start()

                if current_user.get("email"):
                    threading.Thread(
                        target=_email_svc.send_interview_complete_candidate_email,
                        args=(current_user["email"], _cand_name, _job_title, _score),
                        daemon=True,
                    ).start()
            except Exception as _notify_exc:
                print(f"âš ï¸ Interview completion notification failed: {_notify_exc}")

            if result.modified_count == 0:
                print(
                    f"âŒ Warning: Application {application_id} was not updated (no documents modified)"
                )

            record_usage_event(
                collections,
                action_type="ai_interview",
                actor_type="recruiter",
                actor_id=recruiter_actor_id,
                model=default_model_for(get_provider_priority()[0]),
                stt_seconds=stt_seconds,
                tts_characters=int(tts_characters or 0),
                usage_source="actual",
                source={
                    "type": "application",
                    "id": str(application_id),
                    "label": existing_app.get("job_title") or "Interview",
                },
                occurred_at=utc_now(),
                metadata={
                    "session_id": session_id,
                    "proctoring_score": proctoring_score,
                },
            )

            record_usage_event(
                collections,
                action_type="ai_interview_evaluation",
                actor_type="recruiter",
                actor_id=recruiter_actor_id,
                model=default_model_for(get_provider_priority()[0]),
                usage_source="assumed",
                source={
                    "type": "application",
                    "id": str(application_id),
                    "label": existing_app.get("job_title") or "Interview Evaluation",
                },
                occurred_at=utc_now(),
                metadata={
                    "session_id": session_id,
                },
            )

        except Exception as e:
            print(f"âŒ Error updating application: {e}")
            import traceback

            traceback.print_exc()
    else:
        print(f"âš ï¸ WARNING: No application_id found in session document!")
        print(
            f"âš ï¸ Session doc keys: {session_doc.keys() if session_doc else 'No session doc'}"
        )

    if session and final_evaluation.get("pending_answers"):
        def publish_refresh(score, evaluation):
            application_id = session_doc.get("application_id")
            if application_id:
                applications_collection.update_one({"_id": ObjectId(application_id)},
                    {"$set": {"interview_score": score}})
                payload = {"type": "score_updated", "application": {"_id": application_id,
                    "interview_score": score, "status": "interviewed"}}
                for room in {session_doc.get("user_id"), session_doc.get("recruiter_id")} - {None, ""}:
                    socketio.emit("application_update", payload, room=room)
        schedule_evaluation_refresh(interview_manager, session, interviews_collection, publish_refresh)
    else:
        interview_manager.sessions.pop(session_id, None)
        live_sessions.pop(session_id, None)
    live_sessions.pop(session_id, None)
    return jsonify(
        {
            "status": "interview_ended",
            "evaluation": final_evaluation,
            "interview_score": interview_score,
            "proctoring_score": proctoring_score,
            "proctoring_status": proctoring_status,
            "proctoring_report": proctoring_report,
            "cv_score": cv_score,
            "transcript": interview_transcript,
            "usage_summary": usage_summary,
            "usage_deduction": usage_deduction,
        }
    )


# ... (rest of app.py remains the same)


@interview_bp.route("/api/interviews/<session_id>/gaze-recorder-page", methods=["GET"])
def get_gaze_recorder_page(session_id):
    """
    Serves a GazeRecorder + heatmap analysis page using the exact browser API flow.
    Optional query param: ?token=<jwt> for result submission.
    """
    auth_token = request.args.get("token", "")
    submit_url = f"{request.host_url.rstrip('/')}/api/interviews/{session_id}/gaze-recorder-results"
    html = gaze_recorder_service.build_session_page(
        session_id=session_id, submit_url=submit_url, auth_token=auth_token
    )
    return Response(html, mimetype="text/html")


@interview_bp.route("/api/interviews/<session_id>/gaze-recorder-results", methods=["POST"])
@token_required
def upload_gaze_recorder_results(current_user, session_id):
    """
    Receives raw GazeRecorder payloads and stores smart heatmap analysis.
    """
    owned_doc, _, _ = _owned_session(str(current_user["_id"]), session_id)
    if not owned_doc:
        return jsonify({"error": "Interview session not found"}), 404
    utc_now = lambda: datetime.datetime.now(datetime.UTC)
    data = request.get_json() or {}
    recording_data = data.get("recordingData")
    gaze_points = data.get("gazePoints", [])
    started_at_ms = data.get("startedAtMs")
    ended_at_ms = data.get("endedAtMs")
    viewport = data.get("viewport", {})
    width = int(viewport.get("width", 1920) or 1920)
    height = int(viewport.get("height", 1080) or 1080)

    if not isinstance(gaze_points, list) or len(gaze_points) == 0:
        return jsonify({"error": "gazePoints are required"}), 400

    analysis_result = gaze_recorder_service.analyze_gaze_patterns(
        gaze_points=gaze_points,
        window_width=width,
        window_height=height,
        started_at_ms=started_at_ms,
        ended_at_ms=ended_at_ms,
    )

    file_paths = gaze_recorder_service.save_payload_files(
        session_id=session_id,
        user_id=str(current_user["_id"]),
        recording_data=recording_data,
        analysis_result=analysis_result,
        gaze_points=gaze_points,
    )

    interviews_collection.update_one(
        {"session_id": session_id, "user_id": str(current_user["_id"])},
        {
            "$set": {
                "gaze_recorder_recording_path": file_paths.get("recording_path"),
                "gaze_recorder_analysis_path": file_paths["analysis_path"],
                "gaze_recorder_points_path": file_paths["points_path"],
                "gaze_recorder_analysis": analysis_result,
                "gaze_recorder_score": max(
                    0, 100 - analysis_result.get("cheatingScore", 0)
                ),
                "gaze_recorder_source": "client_reported_supplementary",
                "updated_at": utc_now(),
            }
        },
    )

    return (
        jsonify(
            {
                "message": "GazeRecorder results saved successfully",
                "analysis": analysis_result,
            }
        ),
        200,
    )


@interview_bp.route("/api/interviews/<session_id>/upload-recording", methods=["POST"])
@token_required
def upload_recording(current_user, session_id):
    request.max_content_length = 256 * 1024 * 1024
    session_doc, target_collection, _ = _owned_session(current_user["_id"], session_id)
    if not session_doc:
        return jsonify({"error": "Session not found"}), 404
    if "recording" not in request.files:
        return jsonify({"error": "No recording file part"}), 400
    file = request.files["recording"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400
    if file:
        part = request.form.get("recording_part", "0")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", part):
            return jsonify({"error": "Invalid recording part"}), 400
        media_type = "video/mp4" if file.mimetype == "video/mp4" else "video/webm"
        extension = "mp4" if media_type == "video/mp4" else "webm"
        # Recordings live in GCS only â€” staged briefly on disk (the analyzer
        # needs a local path), uploaded, then the staging file is deleted.
        # No local fallback: a failed GCS upload fails the request loudly.
        filename = secure_filename(f"{session_id}-{current_user['_id']}-{part}.{extension}")
        filepath = os.path.join(RECORDING_FOLDER, filename)
        file.save(filepath)
        try:
            if recording_analyzer:
                # Note: This might take some time to process.
                # For a production app, this should be a background task (Celery/Redis).
                try:
                    recording_analyzer.run_full_analysis(filepath)
                except Exception as e:
                    print(f"Error running post-interview analysis: {e}")

            from services import gcs_service
            gcs_object_path = f"recordings/{filename}"
            try:
                gcs_uri = gcs_service.upload_from_path(
                    filepath, gcs_object_path, content_type=media_type
                )
            except Exception as e:
                print(f"GCS upload failed for interview recording: {e}")
                return jsonify({"error": "Failed to store recording in cloud storage"}), 500

            target_collection.update_one(
                {"session_id": session_id, "user_id": str(current_user["_id"])},
                {"$set": {"recording_path": gcs_uri, "recording_gcs_path": gcs_object_path},
                    "$addToSet": {"recording_parts": {"part": part, "path": gcs_uri,
                        "content_type": media_type}}},
            )
            return (
                jsonify({"message": "Recording uploaded successfully", "path": gcs_uri, "part": part}),
                200,
            )
        finally:
            try:
                os.remove(filepath)
            except OSError:
                pass

    return jsonify({"error": "File upload failed"}), 500


# In app.py (add near your existing upload-recording route)


@interview_bp.route("/api/interviews/<session_id>/upload-mobile-recording", methods=["POST"])
# The phone uses its signed session-scoped pairing capability instead of a JWT.
def upload_mobile_recording(session_id):
    request.max_content_length = 256 * 1024 * 1024
    if not app_config.mobile_recording_enabled():
        return jsonify({
            "error": "Mobile recording is disabled on this server.",
            "error_code": "mobile_recording_disabled",
        }), 403

    target_collection = interviews_collection
    session_exists = target_collection.find_one({"session_id": session_id})
    if not session_exists:
        target_collection = collections["practice_sessions"]
        session_exists = target_collection.find_one({"session_id": session_id})
    if not session_exists:
        return jsonify({"error": "Session not found"}), 404
    pairing_token = request.headers.get("X-Mobile-Pairing-Token") or request.form.get("pairing_token")
    if not validate_mobile_pairing_token(pairing_token, session_id, session_exists.get("user_id")):
        return jsonify({"error": "The mobile pairing link is invalid or expired.", "error_code": "invalid_pairing_token"}), 403

    if "recording" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["recording"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if file:
        media_type = "video/mp4" if file.mimetype == "video/mp4" else "video/webm"
        extension = "mp4" if media_type == "video/mp4" else "webm"
        part = request.form.get("recording_part", "0")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", part):
            return jsonify({"error": "Invalid recording part"}), 400
        # Save with a specific suffix to distinguish from webcam. GCS only â€”
        # staged briefly on disk, uploaded, staging file deleted; a failed
        # upload fails the request (no local fallback).
        filename = secure_filename(f"{session_id}_mobile_env-{part}.{extension}")
        filepath = os.path.join(M_RECORDING_FOLDER, filename)
        file.save(filepath)
        try:
            from services import gcs_service
            gcs_object_path = f"mobile_recordings/{filename}"
            try:
                gcs_uri = gcs_service.upload_from_path(
                    filepath, gcs_object_path, content_type=media_type
                )
            except Exception as e:
                print(f"GCS upload failed for mobile recording: {e}")
                return jsonify({"error": "Failed to store mobile recording in cloud storage"}), 500

            target_collection.update_one(
                {"session_id": session_id},
                {"$set": {
                    "mobile_recording_path": gcs_uri,
                    "mobile_recording_gcs_path": gcs_object_path,
                }, "$addToSet": {"mobile_recording_parts": {"part": part, "path": gcs_uri,
                    "content_type": media_type}}},
            )
            return jsonify({"message": "Mobile recording uploaded"}), 200
        finally:
            try:
                os.remove(filepath)
            except OSError:
                pass


@interview_bp.route("/api/interviews", methods=["GET"])
@token_required
def get_user_interviews(current_user):
    user_type = current_user.get("user_type", "candidate")

    if user_type == "recruiter":
        # Recruiters can see all interviews
        user_interviews = list(interviews_collection.find({}))
    else:
        # Candidates can only see their own interviews
        user_interviews = list(
            interviews_collection.find({"user_id": str(current_user["_id"])})
        )

    # For recruiters: batch-fetch all candidate users in ONE query instead of
    # N+1 individual find_one() calls (one per interview). With 100 interviews
    # this reduces 101 MongoDB round-trips down to 2.
    candidate_map = {}
    if user_type == "recruiter" and user_interviews:
        candidate_ids = []
        for iv in user_interviews:
            try:
                candidate_ids.append(ObjectId(iv["user_id"]))
            except Exception:
                pass
        if candidate_ids:
            for u in users_collection.find(
                {"_id": {"$in": candidate_ids}},
                {"_id": 1, "name": 1, "email": 1},
            ):
                candidate_map[str(u["_id"])] = u

    # Format the interviews for JSON response
    formatted_interviews = []
    for interview in user_interviews:
        formatted_interview = {
            "id": str(interview["_id"]),
            "session_id": interview["session_id"],
            "status": interview["status"],
            "created_at": interview["created_at"].isoformat(),
            "updated_at": interview["updated_at"].isoformat(),
            "cv_path": interview.get("cv_path"),
            "jd_path": interview.get("jd_path"),
        }

        # Include user info for recruiters â€” use pre-fetched map, no extra queries
        if user_type == "recruiter":
            user_info = candidate_map.get(str(interview.get("user_id", "")))
            if user_info:
                formatted_interview["candidate"] = {
                    "name": user_info["name"],
                    "email": user_info["email"],
                }

        formatted_interviews.append(formatted_interview)

    return jsonify(formatted_interviews)



# ... other imports


def _identity_summary(identity, session_id):
    """Compact copy of an identity_verification block for the application doc,
    so recruiter candidate lists can badge identity state without joining the
    interviews collection."""
    return {
        "status": identity.get("status"),
        "verified": identity.get("verified"),
        "matched": identity.get("matched"),
        "score": identity.get("score"),
        "distance": identity.get("distance"),
        "threshold": identity.get("threshold"),
        "session_id": session_id,
        "checked_at": identity.get("checked_at"),
        "scored_at": identity.get("scored_at"),
        "captured_image_file_id": identity.get("captured_image_file_id"),
    }


def _score_identity_async(interview_id, application_id, card_file_id, capture_bytes, session_id, captured_id):
    """Background LLM face-similarity scoring (daemon thread).

    Compares the live capture against the uploaded identity card and stores
    the similarity score on the interview + application for the recruiter.
    Deliberately NEVER blocks or fails the interview â€” identity is advisory
    (score-only) for every account type; the recruiter judges from the score.
    """
    try:
        card_bytes = None
        card_content_type = None
        try:
            card_bytes, card_content_type = identity_card_service.load_identity_card(
                db, card_file_id
            )
        except Exception as exc:
            print(f"[identity-score] failed to load identity card {card_file_id}: {exc}")

        verdict = (
            face_match_service.compare_faces(card_bytes, card_content_type, capture_bytes)
            if card_bytes
            else {
                "available": False,
                "matched": None,
                "score": None,
                "threshold": face_match_service.get_threshold(),
                "model": face_match_service.get_model(),
                "reason": "identity card unreadable",
            }
        )

        now = datetime.datetime.utcnow()
        available = bool(verdict.get("available"))
        patch = {
            "identity_verification.status": "scored" if available else "score_unavailable",
            "identity_verification.verified": bool(verdict.get("matched")) if available else None,
            "identity_verification.matched": verdict.get("matched"),
            "identity_verification.score": verdict.get("score"),
            "identity_verification.threshold": verdict.get("threshold"),
            "identity_verification.model": verdict.get("model"),
            "identity_verification.match_reason": verdict.get("reason"),
            "identity_verification.scored_at": now,
            "updated_at": now,
        }
        # A retake may have replaced this photo while its advisory score was
        # running. An old score must never overwrite the candidate's new photo.
        capture_filter = {"_id": interview_id, "identity_verification.captured_image_file_id": captured_id}
        result = interviews_collection.update_one(capture_filter, {"$set": patch})
        if not result.matched_count:
            return

        if application_id:
            try:
                refreshed = interviews_collection.find_one(
                    capture_filter, {"identity_verification": 1}
                ) or {}
                if not refreshed:
                    return
                identity = refreshed.get("identity_verification") or {}
                applications_collection.update_one(
                    {"_id": ObjectId(str(application_id)), "identity_verification.captured_image_file_id": captured_id},
                    {
                        "$set": {
                            "identity_verification": _identity_summary(identity, session_id),
                            "updated_at": now,
                        }
                    },
                )
            except Exception as exc:
                print(f"[identity-score] failed to copy summary to application {application_id}: {exc}")
    except Exception as exc:
        print(f"[identity-score] scoring failed for session {session_id}: {exc}")


@interview_bp.route("/api/interviews/<session_id>/register-face", methods=["POST"])
@token_required
@serialized_session
def register_face(current_user, session_id):
    """
    Capture the candidate's face before the interview starts.

    Real interviews are similarity-scored (LLM) against the account's uploaded
    identity card IN THE BACKGROUND â€” the interview always proceeds
    immediately, nobody is ever blocked on a mismatch, and the score is
    surfaced to the recruiter on the candidate card and reports. The capture
    and score are stored on the interview + application so the recruiter can
    see exactly who sat the interview. Practice interviews only capture (for
    live proctoring) â€” they never score against the ID card and never block.
    """
    data = request.get_json()
    if not data or "image" not in data:
        return jsonify({"error": "No image data provided", "error_code": "invalid_image"}), 400

    try:
        # Strip the data-URL prefix (e.g. "data:image/jpeg;base64,...")
        raw = data["image"]
        encoded = raw.split(",", 1)[1] if "," in raw else raw
        if not isinstance(raw, str) or len(encoded) > 3_000_000:
            raise ValueError("Image too large")
        decoded_image = base64.b64decode(encoded, validate=True)
    except Exception:
        return jsonify({"error": "Invalid image data", "error_code": "invalid_image"}), 400

    user_id = str(current_user["_id"])

    interview_doc = interviews_collection.find_one(
        {"session_id": session_id, "user_id": user_id}
    )
    practice_doc = None
    if not interview_doc:
        practice_doc = collections["practice_sessions"].find_one(
            {"session_id": session_id, "user_id": user_id}
        )
        if not practice_doc:
            return jsonify({"error": "Interview session not found", "error_code": "session_not_found"}), 404

    owned_doc = interview_doc or practice_doc
    if owned_doc.get("status") != "setup":
        return jsonify({"error": "Face enrollment is only available during setup.", "error_code": "session_not_in_setup"}), 409
    quality = face_service.assess_face_image(decoded_image)
    if not quality.get("ok"):
        return (
            jsonify(
                {
                    "error": quality.get("message", "Face image rejected"),
                    "error_code": quality.get("error_code", "invalid_image"),
                }
            ),
            503 if quality.get("error_code") == "face_detection_unavailable" else 400,
        )

    now = datetime.datetime.utcnow()
    mode = face_service.get_mode()
    identity = {
        "checked_at": now,
        "mode": mode,
        "model": face_service.FACE_MODEL_NAME,
    }
    scoring_arguments = None

    try:
        if practice_doc is not None:
            # Practice: capture for live proctoring, softly verify against the
            # canonical identity when one exists, never enroll, never block.
            identity["status"] = "practice_captured"
            identity["verified"] = None
            identity["captured_image_file_id"] = face_service.store_face_image(db, decoded_image, user_id=user_id, session_id=session_id, purpose="capture")
            collections["practice_sessions"].update_one(
                {"_id": practice_doc["_id"]},
                {"$set": {"identity_verification": identity, "updated_at": now}},
            )
        else:
            if mode == "off":
                identity.update({"status": "skipped", "verified": None})
                identity["captured_image_file_id"] = face_service.store_face_image(db, decoded_image, user_id=user_id, session_id=session_id, purpose="capture")
            else:
                # The uploaded identity card is the reference identity. The
                # live capture is similarity-scored against it by an LLM in
                # the BACKGROUND (see _score_identity_async) â€” the interview
                # always proceeds immediately for every account type, and the
                # recruiter judges from the score. No blocking, no attempts.
                card_doc = users_collection.find_one(
                    {"_id": current_user["_id"]}, {"identity_card": 1}
                ) or {}
                card = card_doc.get("identity_card") or {}
                card_file_id = card.get("image_file_id")
                if not card_file_id:
                    return (
                        jsonify(
                            {
                                "error": "Please upload your identity card in your profile before starting an interview.",
                                "error_code": "identity_card_required",
                            }
                        ),
                        403,
                    )

                captured_id = face_service.store_face_image(
                    db, decoded_image, user_id=user_id, session_id=session_id, purpose="capture"
                )
                identity.update(
                    {
                        "method": "llm_id_card_match",
                        "reference_image_file_id": card_file_id,
                        "captured_image_file_id": captured_id,
                        "status": "score_pending",
                        "verified": None,
                        "score": None,
                        "threshold": face_match_service.get_threshold(),
                    }
                )
                scoring_arguments = (
                    interview_doc["_id"], interview_doc.get("application_id"),
                    card_file_id, decoded_image, session_id, captured_id,
                )

            # Persist identity state and activate the session
            interviews_collection.update_one(
                {"_id": interview_doc["_id"]},
                {"$set": {"identity_verification": identity, "updated_at": now}},
            )
            if interview_doc.get("application_id"):
                try:
                    applications_collection.update_one(
                        {"_id": ObjectId(interview_doc["application_id"])},
                        {
                            "$set": {
                                "identity_verification": _identity_summary(identity, session_id),
                                "updated_at": now,
                            }
                        },
                    )
                except Exception:
                    pass

        # Live proctoring reference for this session. Also keep a decoded
        # ndarray: DeepFace inside analyze_frame_for_proctoring does not accept
        # raw bytes, so the per-frame identity check needs the array form.
        live_sessions[session_id] = {
            "owner_id": user_id,
            "proctoring_config": owned_doc.get("proctoring_config") or {},
            "registered_face": decoded_image,
            "registered_face_np": face_service.decode_image(decoded_image),
            "proctoring_score": None,
            "analyzed_frames": 0,
            "infractions": {},
        }

        # Start after the capture is persisted, so a fast scorer cannot have
        # its result replaced by the route's pending-state write.
        if scoring_arguments:
            threading.Thread(target=_score_identity_async, args=scoring_arguments, daemon=True).start()

        status = identity.get("status")
        return (
            jsonify(
                {
                    "message": "Face captured successfully.",
                    "identity": {
                        "status": status,
                        "verified": identity.get("verified"),
                        "score": identity.get("score"),
                        "distance": identity.get("distance"),
                        "threshold": identity.get("threshold"),
                    },
                }
            ),
            200,
        )
    except Exception as e:
        print(f"Error during face registration: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": "Failed to process image"}), 500


@interview_bp.route("/api/interviews/<session_id>/face-image/<kind>", methods=["GET"])
@token_required
def get_interview_face_image(current_user, session_id, kind):
    """Serve the identity photos for a session to authorized viewers only:
    the candidate themself, the recruiter who owns the job, or an admin."""
    if kind not in ("captured", "reference"):
        return jsonify({"error": "Invalid image kind"}), 400

    doc = interviews_collection.find_one({"session_id": session_id})
    is_practice = False
    if not doc:
        doc = collections["practice_sessions"].find_one({"session_id": session_id})
        if not doc:
            return jsonify({"error": "Session not found"}), 404
        is_practice = True

    user_id = str(current_user["_id"])
    user_type = current_user.get("user_type", "candidate")
    is_owner = user_id == str(doc.get("user_id", ""))
    is_job_recruiter = (
        not is_practice
        and user_type == "recruiter"
        and user_id == str(doc.get("recruiter_id") or "")
    )
    if not (is_owner or is_job_recruiter or user_type == "admin"):
        return jsonify({"error": "Unauthorized"}), 403

    identity = doc.get("identity_verification") or {}
    file_id = identity.get(f"{kind}_image_file_id")
    if not file_id and kind == "reference":
        # Fall back to the account's canonical photo
        try:
            profile_doc = users_collection.find_one(
                {"_id": ObjectId(str(doc.get("user_id")))}, {"face_profile": 1}
            )
            file_id = ((profile_doc or {}).get("face_profile") or {}).get("image_file_id")
        except Exception:
            file_id = None
    if not file_id:
        return jsonify({"error": "Image not found"}), 404

    try:
        image_bytes, content_type = face_service.load_face_image(db, file_id)
    except Exception:
        return jsonify({"error": "Image not found"}), 404

    return Response(
        image_bytes,
        mimetype=content_type or "image/jpeg",
        headers={"Cache-Control": "private, max-age=300"},
    )
