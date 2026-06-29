import sys
import io
import os
import warnings

# Force UTF-8 encoding for standard output/error to prevent crash on printing emojis in Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
elif hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Suppress pydantic warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Optional: add console handler if missing
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(ch)
# ── Silence all TF / MediaPipe / glog noise before any import triggers them ──
# TF C++ backend: 0=DEBUG 1=INFO 2=WARNING 3=ERROR(only)
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
# glog (Google Logging used by MediaPipe/TFLite): 0=INFO 1=WARNING 2=ERROR 3=FATAL
os.environ["GLOG_minloglevel"] = "2"
# abseil-py
os.environ["ABSL_MIN_LOG_LEVEL"] = "3"
# suppress Python-level TF / tf_keras / absl loggers
logging.getLogger("tensorflow").setLevel(logging.ERROR)
logging.getLogger("tf_keras").setLevel(logging.ERROR)
logging.getLogger("absl").setLevel(logging.ERROR)
logging.getLogger("mediapipe").setLevel(logging.ERROR)
# suppress absl-py programmatic API if available
try:
    import absl.logging as _absl_log
    _absl_log.set_verbosity(_absl_log.ERROR)
except Exception:
    pass
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="tensorflow")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="tf_keras")

from flask import Flask, request, jsonify, Response
from utils.gaze_recorder_service import GazeRecorderService
from flask_socketio import SocketIO, join_room
from werkzeug.utils import secure_filename
import datetime
import uuid
import base64
from bson import ObjectId

import numpy as np
import time

try:
    from security_check import analyze_frame_for_proctoring
    _proctoring_available = True
except Exception:
    _proctoring_available = False

# Import configuration
from config.env_loader import load_environment
from config.database import db_config
from middleware.cors_middleware import setup_cors
from flask_cors import CORS

# Import route blueprints
from routes.auth_routes import auth_bp
from routes.profile_routes import profile_bp
from routes.job_routes import job_bp
from routes.application_routes import application_bp
from routes.file_routes import file_bp
from routes.practice_routes import practice_bp
from routes.cv_routes import create_cv_routes
from routes.admin_routes import admin_bp, init_admin_routes
from routes.invite_routes import invite_bp

try:
    from google.cloud import speech
    print("--- DEBUG: google.cloud.speech imported before speech_routes in app.py ---")
except ImportError as e:
    print(f"--- DEBUG: google.cloud.speech FAILED before speech_routes in app.py: {e} ---")
from routes.speech_routes import speech_bp

import threading
from services.cv_scoring_service import CVScoringService
from services.email_service import EmailService
from services.usage_telemetry_service import record_usage_event
from controllers.admin_controller import AdminController
from payment_module.services.subscription_service import SubscriptionService
from payment_module.services.wallet_service import WalletService
from payment_module.config.settings import PaymentConfig
from interview.core.cost_tracker import CostTracker
from interview.core.llm_wrapper import call_llm_with_tracking, get_cost_summary
from interview.core.speech_cost_tracker import process_stt, process_tts

# Optional import - RecordingAnalyzer has heavy dependencies that may conflict
# try:
#     from gpu_intensive_task.recording_analysis_service import RecordingAnalyzer
#     RECORDING_ANALYZER_AVAILABLE = True
#     print("✓ RecordingAnalyzer loaded successfully")
# except Exception as e:
#     print(f"⚠ Warning: RecordingAnalyzer not available: {str(e)[:100]}")
#     RecordingAnalyzer = None
#     RECORDING_ANALYZER_AVAILABLE = False
RECORDING_ANALYZER_AVAILABLE = False


# Import payment module
try:
    from payment_module.routes import payment_bp, init_payment_routes
    from payment_module.services.subscription_service import SubscriptionService
    from payment_module.services.wallet_service import WalletService
    from payment_module.config.settings import PaymentConfig

    PAYMENT_MODULE_AVAILABLE = True
    print("[OK] Payment module loaded successfully")
except ImportError as e:
    print(f"[WARN] Payment module not available: {e}")
    PAYMENT_MODULE_AVAILABLE = False
    SubscriptionService = None
    WalletService = None
    PaymentConfig = None

# Load environment variables
load_environment()


# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "your-flask-secret-key")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB — rejects oversized request bodies before they're read

# Setup Security Headers (Helmet equivalent) — optional
try:
    from flask_talisman import Talisman
    Talisman(app, content_security_policy=None, force_https=False)
    print("[OK] Flask-Talisman loaded")
except ImportError:
    print("[WARN] flask-talisman not installed, skipping security headers. Install with: pip install Flask-Talisman")

# Setup Rate Limiting — optional
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    
    # In development, we use very high limits to avoid rate limiting developers
    is_development = os.getenv("FLASK_ENV") == "development"
    default_limits = ["100000 per day", "10000 per hour"] if is_development else ["200 per day", "50 per hour"]
    
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=default_limits,
        storage_uri="memory://"
    )
    print(f"[OK] Flask-Limiter loaded with limits: {default_limits}")
except ImportError:
    limiter = None
    print("[WARN] flask-limiter not installed, skipping rate limiting. Install with: pip install Flask-Limiter")


# Custom JSON provider so any bson.ObjectId returned by a route auto-serializes.
# Without this, Flask's default encoder raises 500 on ObjectIds nested inside
# any response dict (cv_snapshot.metadata, recruiter_id stored as ObjectId on
# legacy docs, etc.) -- and because the 500 short-circuits before
# after_request runs, the browser also reports a CORS error as a side effect.
from flask.json.provider import DefaultJSONProvider as _DefaultJSONProvider


class _ObjectIdSafeJSONProvider(_DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        return super().default(obj)


app.json = _ObjectIdSafeJSONProvider(app)

# Initialize extensions
socketio = SocketIO(app, cors_allowed_origins="*")

# Configure CORS to allow all origins
CORS(
    app,
    resources={
        r"/*": {
            "origins": "*",
            "allow_headers": [
                "Content-Type",
                "Authorization",
                "Access-Control-Allow-Credentials",
            ],
            "supports_credentials": True,
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
            "expose_headers": ["Content-Type", "Authorization"],
        }
    },
)

from werkzeug.exceptions import HTTPException
import traceback

@app.errorhandler(Exception)
def handle_exception(e):
    # Pass through HTTP errors
    if isinstance(e, HTTPException):
        return jsonify(error=e.description, code=e.code), e.code
    
    # Log and return standard JSON for unhandled errors
    logger.error(f"Unhandled Exception: {str(e)}")
    logger.error(traceback.format_exc())
    return jsonify(error="Internal Server Error", message="An unexpected error occurred.", code=500), 500


# Handle preflight OPTIONS requests
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = app.make_default_options_response()
        headers = response.headers
        headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
        headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        )
        headers["Access-Control-Allow-Headers"] = (
            "Content-Type, Authorization, Access-Control-Allow-Credentials"
        )
        headers["Access-Control-Allow-Credentials"] = "true"
        return response


# Add CORS headers to all responses
@app.after_request
def after_request(response):
    origin = request.headers.get("Origin")
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        )
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


# Initialize database
db = db_config.connect()
collections = db_config.get_collections()

# Get collections for interview system
users_collection = collections["users"]
interviews_collection = collections["interviews"]
applications_collection = collections["applications"]
jobs_collection = collections["jobs"]
openai_cost_logs_collection = db.get_collection("openai_cost_logs")
speech_cost_logs_collection = db.get_collection("speech_cost_logs")

if PAYMENT_MODULE_AVAILABLE and WalletService:
    try:
        granted, skipped = WalletService(db).bootstrap_signup_bonus_for_all_users(
            users_collection
        )
        print(
            f"[OK] Startup wallet signup bonus bootstrap complete. Granted={granted}, skipped={skipped}"
        )
    except Exception as e:
        print(f"[WARN] Startup wallet bonus bootstrap skipped: {e}")

# Initialize and start background processor for CV scoring
from services.background_processor import get_background_processor

background_processor = get_background_processor()
background_processor.start()
logger.info("[OK] Background processor started for async CV scoring")

# Initialize and start the invite cleanup scheduler (purges dormant burner accounts)
from services.invite_cleanup_scheduler import get_invite_cleanup_scheduler

invite_cleanup_scheduler = get_invite_cleanup_scheduler(collections)
invite_cleanup_scheduler.start()
logger.info("[OK] Invite cleanup scheduler started")

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(job_bp)
app.register_blueprint(application_bp)
app.register_blueprint(file_bp)
app.register_blueprint(practice_bp)

@app.route("/api/files/<gridfs_id>")
def serve_gridfs_file(gridfs_id):
    try:
        import gridfs
        fs = gridfs.GridFS(db)
        file_data = fs.get(ObjectId(gridfs_id))
        return Response(
            file_data.read(),
            mimetype=file_data.content_type,
            headers={"Content-Disposition": f"inline; filename={file_data.filename}"}
        )
    except Exception as e:
        return jsonify({"error": "File not found"}), 404

# Register CV routes (requires collections, so created after database initialization)
cv_bp = create_cv_routes(collections)
app.register_blueprint(cv_bp, url_prefix="/api/cv")

# Initialize and register admin routes
admin_controller = AdminController(collections)
init_admin_routes(admin_controller)
app.register_blueprint(admin_bp, url_prefix="/api/admin")
app.register_blueprint(speech_bp, url_prefix="/api/speech")
app.register_blueprint(invite_bp)
logger.info("[OK] Admin routes registered at /api/admin")
logger.info("[OK] Invite routes registered")

# Define a dictionary to hold a detector instance for each session
# Define a dictionary to hold a detector instance for each session
# proctoring_detectors = {}  # Moved to separate service

# Initialize interview system with proper configuration
from interview.config.settings import InterviewConfig, LLMConfig, LLMProvider
from interview.core.session_manager import InterviewSessionManager

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Use default configurations but override for GROQ
interview_config = InterviewConfig()
llm_config = LLMConfig()

# Initialize interview session manager with proper config
interview_manager = InterviewSessionManager(
    config=interview_config, llm_config=llm_config
)

# === INTERVIEW SYSTEM (REMAINS IN APP.PY) ===
# All interview-related routes and Socket.IO handlers remain here

# In-memory store: session_id -> { registered_face_bytes, proctoring_score, infractions }
live_sessions = {}

# Define directories for storing files
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
PROCTORING_FOLDER = os.path.join(UPLOAD_FOLDER, "proctoring")

# Ensure folders exist
os.makedirs(PROCTORING_FOLDER, exist_ok=True)
RECORDING_FOLDER = os.path.join(UPLOAD_FOLDER, "recordings")
M_RECORDING_FOLDER = os.path.join(UPLOAD_FOLDER, "mobile_recordings")
os.makedirs(RECORDING_FOLDER, exist_ok=True)
os.makedirs(M_RECORDING_FOLDER, exist_ok=True)
TMP_FOLDER = os.path.join(UPLOAD_FOLDER, "tmp")
os.makedirs(TMP_FOLDER, exist_ok=True)

app.config["PROCTORING_FOLDER"] = PROCTORING_FOLDER
app.config["RECORDING_FOLDER"] = RECORDING_FOLDER
app.config["TMP_FOLDER"] = TMP_FOLDER

GAZE_RECORDER_FOLDER = os.path.join(PROCTORING_FOLDER, "gaze_recorder")
os.makedirs(GAZE_RECORDER_FOLDER, exist_ok=True)
gaze_recorder_service = GazeRecorderService(output_dir=GAZE_RECORDER_FOLDER)

# Import middleware for interview routes
from middleware.auth_middleware import token_required

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
    print("ℹ RecordingAnalyzer not available - recording analysis features disabled")


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


# Initialize payment module
if PAYMENT_MODULE_AVAILABLE:
    try:
        init_payment_routes(db)
        app.register_blueprint(payment_bp)
        print("[OK] Payment routes registered at /api/payment")
    except Exception as e:
        print(f"[WARN] Failed to register payment routes: {e}")
    try:
        subscription_billing_service = SubscriptionService(db)
    except Exception as e:
        print(f"[WARN] Failed to initialize subscription billing service: {e}")
        subscription_billing_service = None
else:
    subscription_billing_service = None



# health check route
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"}), 200


# Direct tracked chat endpoint (actual cost from response.usage only)
@app.route("/chat", methods=["POST"])
@app.route("/api/chat", methods=["POST"])
def chat_with_cost_tracking():
    data = request.get_json() or {}
    messages = data.get("messages")
    model = data.get("model", "gpt-4o-mini")
    user_id = data.get("user_id")

    if not isinstance(messages, list) or not messages:
        return jsonify({"error": "messages (non-empty list) is required"}), 400

    try:
        response, cost, log_data = call_llm_with_tracking(
            model=model,
            messages=messages,
            user_id=user_id,
            logs_collection=openai_cost_logs_collection,
        )
    except Exception as exc:
        logger.exception("Tracked chat request failed")
        return jsonify({"error": "LLM request failed", "details": str(exc), "cost": None}), 500

    content = ""
    try:
        choice = (getattr(response, "choices", None) or [None])[0]
        message = getattr(choice, "message", None) if choice is not None else None
        content = getattr(message, "content", "") if message is not None else ""
    except Exception:
        content = ""

    return jsonify(
        {
            "response": content,
            "cost": cost,
            "request_id": log_data.get("request_id"),
        }
    )


@app.route("/cost-summary", methods=["GET"])
@app.route("/api/cost-summary", methods=["GET"])
def cost_summary():
    user_id = request.args.get("user_id")
    summary = get_cost_summary(
        logs_collection=openai_cost_logs_collection,
        user_id=user_id,
    )
    return jsonify(summary), 200


@app.route("/stt-cost", methods=["POST"])
@app.route("/api/stt-cost", methods=["POST"])
def stt_cost():
    data = request.get_json() or {}
    cost = process_stt(
        data.get("audio_seconds"),
        user_id=data.get("user_id"),
        logs_collection=speech_cost_logs_collection,
    )
    return jsonify({"cost": cost}), 200


@app.route("/tts-cost", methods=["POST"])
@app.route("/api/tts-cost", methods=["POST"])
def tts_cost():
    data = request.get_json() or {}
    cost = process_tts(
        data.get("text"),
        data.get("voice_type", "standard"),
        data.get("user_id"),
        logs_collection=speech_cost_logs_collection,
    )
    return jsonify({"cost": cost}), 200


# basic index route
@app.route("/")
def index():
    return "Welcome to the Interview System API. Please use the /api endpoints to interact with the system."


# Interview System API Routes
@app.route("/api/interviews/start", methods=["POST"])
@token_required
def start_interview(current_user):
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
            "redirect": f"/job/{app_doc.get('job_id')}" if app_doc.get('job_id') else "/dashboard",
        }), 400

    student = current_user
    job = jobs_collection.find_one({"_id": ObjectId(app_doc["job_id"])})

    if not job:
        return jsonify({"error": "Job not found"}), 404

    proctoring_config = job.get("proctoring_config", {
        "voice_detection": True,
        "object_detection": True,
        "eyeball_tracking": True,
        "gaze_heatmap": True,
    }) if job else {}

    proctoring_enabled = any(bool(v) for v in (proctoring_config or {}).values())
    recruiter_interview_cost = (
        int(PaymentConfig.RECRUITER_REAL_INTERVIEW_PROCTORED_CREDITS)
        if proctoring_enabled
        else int(PaymentConfig.RECRUITER_REAL_INTERVIEW_CREDITS)
    )
    recruiter_deduction = None

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
                },
                idempotency_key=f"real-interview:{application_id}",
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
                idempotency_key=f"real-interview-candidate-audit:{application_id}",
            )

    cv_details = student.get("cv_details")
    if not cv_details:
        return jsonify({"error": "CV details not found for this candidate"}), 400

    # Build plain-text CV and JD from stored structured data
    cv_text = (
        cv_service.format_cv_details(cv_details)
        if cv_service
        else _format_cv_from_details(cv_details)
    )
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
        return jsonify(session_details), 400

    cv_score = app_doc.get("cv_score")
    sim_score = (
        (float(cv_score) / 100.0) if isinstance(cv_score, (int, float)) else 0.75
    )

    interview_doc = {
        "user_id": str(current_user["_id"]),
        "session_id": session_details["session_id"],
        "cv_path": cv_txt_path,
        "jd_path": jd_txt_path,
        "reference_paths": [],
        "application_id": application_id,
        "recruiter_id": (
            str(job.get("created_by")) if job and job.get("created_by") else None
        ),
        "status": "active",
        "similarity_score": sim_score,
        "proctoring_config": proctoring_config,
        "usage_deduction": recruiter_deduction,
        "created_at": datetime.datetime.utcnow(),
        "updated_at": datetime.datetime.utcnow(),
        "start_time": time.time(),
    }

    interview_id = interviews_collection.insert_one(interview_doc).inserted_id

    return jsonify(
        {
            "interview_id": str(interview_id),
            "session_id": session_details["session_id"],
            "initial_questions": [session_details["first_question"]],
            "similarity_score": sim_score,
            "conversation_context": session_details.get("conversation_context", {}),
            "proctoring_config": interview_doc["proctoring_config"],
            "credits_deducted": recruiter_interview_cost,
            "usage_deduction": recruiter_deduction,
            "recruiter_wallet_balance": (recruiter_deduction or {}).get("transaction", {}).get("balance_after"),
        }
    )


@app.route("/api/interviews/<session_id>/question", methods=["GET"])
def get_interview_question(session_id):
    question_result = interview_manager.get_next_question(session_id)

    if "error" in question_result:
        return jsonify(question_result), 400

    return jsonify(question_result)


@app.route("/api/interviews/<session_id>/answer", methods=["POST"])
@token_required
def submit_answer(current_user, session_id):
    data = request.json or {}
    question = data.get("question")
    answer = data.get("answer")

    if not question or not answer:
        return jsonify({"error": "Question and answer are required"}), 400

    try:
        # Submit answer using new system
        result = interview_manager.submit_answer(session_id, question, answer)

        if "error" in result:
            return jsonify(result), 400

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

        return jsonify(serializable_result)

    except Exception as e:
        print(f"Error in submit_answer: {str(e)}")
        import traceback

        print(f"Full traceback: {traceback.format_exc()}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


@app.route("/api/interviews/<session_id>/end", methods=["POST"])
@token_required
def end_interview(current_user, session_id):
    data = request.json or {}
    tracking_data = data.get("tracking_data", [])

    def utc_now():
        return datetime.datetime.now(datetime.UTC)

    def normalize_utc(dt):
        if not isinstance(dt, datetime.datetime):
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=datetime.UTC)
        return dt.astimezone(datetime.UTC)
    
    # Get the final evaluation from the session manager if it exists
    session = interview_manager.sessions.get(session_id)
    final_evaluation = {}
    interview_transcript = []

    # Interview score will be computed from final_evaluation below
    interview_score = None  # Calculated after evaluation is generated
    usage_summary = CostTracker().end_session(session_id, clear_events=True)
    usage_deduction = None
    session_doc = interviews_collection.find_one(
        {"session_id": session_id, "user_id": str(current_user["_id"])}
    )

    if session:
        # If ended prematurely or completed normally, generate evaluation now
        try:
            final_evaluation = interview_manager._generate_final_evaluation(session)
        except Exception as e:
            print(f"⚠️ Error generating final evaluation: {e}")
            import traceback
            traceback.print_exc()
            final_evaluation = {
                "error": "Failed to generate AI evaluation.",
                "details": str(e),
                "final_score": 0
            }

        # Always extract transcript regardless of evaluation success
        if hasattr(session, "interview_data") and session.interview_data:
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

    # Compute interview_score from final_evaluation
    if final_evaluation:
        qs = final_evaluation.get("quantitative_scores", {})
        answer_score = qs.get("answer_score")
        language_score = qs.get("language_score")
        if answer_score is not None or language_score is not None:
            # Weighted: 70% answer quality, 30% language quality
            ans = float(answer_score or 0)
            lang = float(language_score or 0)
            interview_score = round((ans * 0.7 + lang * 0.3) * 100)
        elif final_evaluation.get("final_score") is not None:
            interview_score = final_evaluation["final_score"]
        else:
            # Try conversation_summary average scores as fallback
            conv = final_evaluation.get("conversation_summary", {})
            avg_ans = conv.get("average_answer_score")
            avg_lang = conv.get("average_language_score")
            if avg_ans is not None or avg_lang is not None:
                a = float(avg_ans or 0)
                l = float(avg_lang or 0)
                interview_score = round((a * 0.7 + l * 0.3) * 100)
            else:
                interview_score = 0
    else:
        interview_score = 0

    proctoring_score = (session_doc or {}).get("proctoring_score")
    if proctoring_score is None:
        proctoring_score = (session_doc or {}).get("gaze_recorder_score")

    manual_infractions = list((session_doc or {}).get("manual_infractions") or [])
    gaze_times = (session_doc or {}).get("gaze_metrics")
    gaze_plot_path = (session_doc or {}).get("gaze_plot_path")

    # Get proctoring data from external service
    proctoring_service_url = os.getenv(
        "PROCTORING_SERVICE_URL", "http://localhost:5001"
    )
    try:
        import requests

        resp = requests.get(
            f"{proctoring_service_url}/api/session/{session_id}/stats", timeout=2
        )
        if resp.status_code == 200:
            stats = resp.json()
            if stats.get("proctoring_score") is not None:
                proctoring_score = stats.get("proctoring_score")
            if stats.get("manual_infractions") is not None:
                manual_infractions = stats.get("manual_infractions", [])
            if stats.get("gaze_times") is not None:
                gaze_times = stats.get("gaze_times")
            gaze_plot_filename = stats.get("gaze_plot_filename")

            if gaze_plot_filename:
                gaze_plot_path = os.path.join(
                    app.config["PROCTORING_FOLDER"], gaze_plot_filename
                )
        else:
            if proctoring_score is None and not manual_infractions and not gaze_times:
                print(f"⚠️ Proctoring service returned {resp.status_code}")
            else:
                print(
                    f"ℹ️ Proctoring service returned {resp.status_code}; keeping stored kiosk proctoring data."
                )
    except Exception as e:
        if proctoring_score is None and not manual_infractions and not gaze_times:
            print(f"⚠️ Could not contact proctoring service: {e}")
        else:
            print(
                f"ℹ️ Could not contact proctoring service, using stored kiosk proctoring data instead: {e}"
            )

    if proctoring_score is None:
        proctoring_score = 90

    suspicious_activity_time = 0  # Not tracking this explicitly anymore in app.py

    # Calculate total interview duration for logging
    interview_duration = 0
    if session_doc and "created_at" in session_doc:
        start_time = normalize_utc(session_doc["created_at"])
        end_time = utc_now()
        if start_time is not None:
            interview_duration = (end_time - start_time).total_seconds()

        # Note: Proctoring score is currently hardcoded at 90%
        # Future: Will be calculated based on gaze metrics and infractions

    # Derive actual media usage from the transcript/session timing
    tts_characters = sum(
        len((item.get("text") or "").strip())
        for item in interview_transcript
        if item.get("role") == "assistant"
    )
    stt_seconds = max(0.0, float(interview_duration or 0.0))

    usage_summary = CostTracker().end_session(
        session_id,
        clear_events=True,
        fallback={
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_stt_seconds": stt_seconds,
            "total_tts_characters": int(tts_characters or 0),
            "model": "llama-3.3-70b-versatile",
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
            # Ensure folder exists
            os.makedirs(app.config["PROCTORING_FOLDER"], exist_ok=True)
            gaze_plot_path = os.path.join(app.config["PROCTORING_FOLDER"], gaze_plot_filename)
            plt.savefig(gaze_plot_path)
            plt.close()
        except Exception as e:
            print(f"⚠️ Failed to generate local gaze tracking plot: {e}")
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
                    f"❌ ERROR: Application with ID {application_id} NOT FOUND in database!"
                )
                return jsonify(
                    {
                        "status": "interview_ended",
                        "evaluation": final_evaluation,
                        "interview_score": interview_score,
                        "proctoring_score": proctoring_score,
                        "transcript": interview_transcript,
                        "usage_summary": usage_summary,
                        "usage_deduction": usage_deduction,
                        "error": "Application not found",
                    }
                )

            previous_status = str(existing_app.get("status", "pending")).lower()

            result = applications_collection.update_one(
                {"_id": ObjectId(application_id)},
                {
                    "$set": {
                        "interview_score": interview_score,  # Store interview performance score
                        "proctoring_score": proctoring_score,  # Store proctoring behavior score
                        "stt_seconds": stt_seconds,
                        "tts_characters": int(tts_characters or 0),
                        "usage_source": "actual",
                        "status": "interviewed",
                        "updated_at": utc_now(),
                    }
                },
            )

            # Keep recruiter job-card counters in sync with the application status transition
            status_counters = ["pending", "interviewed", "selected", "rejected"]
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

            # Fire-and-forget: notify the recruiter that the interview is done
            try:
                recruiter_doc = users_collection.find_one(
                    {"_id": ObjectId(recruiter_actor_id)},
                    {"email": 1, "name": 1},
                ) if recruiter_actor_id else None
                if recruiter_doc and recruiter_doc.get("email"):
                    _email_svc = EmailService()
                    _cand_name = current_user.get("name") or "A candidate"
                    _job_title = existing_app.get("job_title") or "the position"
                    _score = int(interview_score) if interview_score is not None else None
                    _rec_name = recruiter_doc.get("name") or "Recruiter"
                    _rec_email = recruiter_doc["email"]
                    _app_id = str(application_id)
                    threading.Thread(
                        target=_email_svc.send_interview_complete_notification,
                        args=(_rec_email, _rec_name, _cand_name, _job_title, _score, _app_id),
                        daemon=True,
                    ).start()
            except Exception as _notify_exc:
                print(f"⚠️ Interview completion notification failed: {_notify_exc}")

            if result.modified_count == 0:
                print(
                    f"❌ Warning: Application {application_id} was not updated (no documents modified)"
                )

            recruiter_actor_id = str(existing_app.get("recruiter_id") or "")

            record_usage_event(
                collections,
                action_type="ai_interview",
                actor_type="recruiter",
                actor_id=recruiter_actor_id,
                model="gpt-4o",
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
                model="gpt-5-mini",
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
            print(f"❌ Error updating application: {e}")
            import traceback

            traceback.print_exc()
    else:
        print(f"⚠️ WARNING: No application_id found in session document!")
        print(
            f"⚠️ Session doc keys: {session_doc.keys() if session_doc else 'No session doc'}"
        )

    return jsonify(
        {
            "status": "interview_ended",
            "evaluation": final_evaluation,
            "interview_score": interview_score,
            "proctoring_score": proctoring_score,
            "transcript": interview_transcript,
            "usage_summary": usage_summary,
            "usage_deduction": usage_deduction,
        }
    )


# ... (rest of app.py remains the same)


@app.route("/api/interviews/<session_id>/gaze-recorder-page", methods=["GET"])
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


@app.route("/api/interviews/<session_id>/gaze-recorder-results", methods=["POST"])
@token_required
def upload_gaze_recorder_results(current_user, session_id):
    """
    Receives raw GazeRecorder payloads and stores smart heatmap analysis.
    """
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
                "proctoring_score": max(
                    0, 100 - analysis_result.get("cheatingScore", 0)
                ),
                "proctoring_source": "gaze_recorder_api",
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


@app.route("/api/interviews/<session_id>/upload-recording", methods=["POST"])
@token_required
def upload_recording(current_user, session_id):
    if "recording" not in request.files:
        return jsonify({"error": "No recording file part"}), 400
    file = request.files["recording"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400
    if file:
        filename = secure_filename(f"{session_id}-{current_user['_id']}.webm")
        filepath = os.path.join(app.config["RECORDING_FOLDER"], filename)
        file.save(filepath)
        # Update the interview record with the path to the recording
        interviews_collection.update_one(
            {"session_id": session_id, "user_id": str(current_user["_id"])},
            {"$set": {"recording_path": filepath}},
        )
        if recording_analyzer:
            # Note: This might take some time to process.
            # For a production app, this should be a background task (Celery/Redis).
            try:
                recording_analyzer.run_full_analysis(filepath)
            except Exception as e:
                print(f"Error running post-interview analysis: {e}")
        return (
            jsonify({"message": "Recording uploaded successfully", "path": filepath}),
            200,
        )

    return jsonify({"error": "File upload failed"}), 500


# In app.py (add near your existing upload-recording route)


@app.route("/api/interviews/<session_id>/upload-mobile-recording", methods=["POST"])
# @token_required  <-- NOTE: You might need to relax auth or pass a temporary token via URL for the mobile device
def upload_mobile_recording(session_id):
    if "recording" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["recording"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if file:
        # Save with a specific suffix to distinguish from webcam
        filename = secure_filename(f"{session_id}_mobile_env.webm")
        filepath = os.path.join(app.config["M_RECORDING_FOLDER"], filename)
        file.save(filepath)

        # Update database with mobile recording path
        interviews_collection.update_one(
            {"session_id": session_id}, {"$set": {"mobile_recording_path": filepath}}
        )

        return jsonify({"message": "Mobile recording uploaded"}), 200


@app.route("/api/interviews", methods=["GET"])
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

        # Include user info for recruiters — use pre-fetched map, no extra queries
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


@app.route("/api/interviews/<session_id>/register-face", methods=["POST"])
@token_required
def register_face(current_user, session_id):
    data = request.get_json()
    if not data or "image" not in data:
        return jsonify({"error": "No image data provided"}), 400
    try:
        # Strip the data-URL prefix (e.g. "data:image/jpeg;base64,...")
        raw = data["image"]
        encoded = raw.split(",", 1)[1] if "," in raw else raw
        decoded_image = base64.b64decode(encoded)

        # Store face bytes and initialise proctoring state for this session
        live_sessions[session_id] = {
            "registered_face": decoded_image,
            "proctoring_score": 100,
            "infractions": {},
        }

        # Mark interview as active in the database
        interviews_collection.update_one(
            {"session_id": session_id, "user_id": str(current_user["_id"])},
            {"$set": {"status": "active"}},
        )
        return jsonify({"message": "Face registered successfully"}), 200
    except Exception as e:
        print(f"Error during face registration: {e}")
        return jsonify({"error": "Failed to process image"}), 500


@socketio.on("connect")
def handle_connect():
    pass


@socketio.on("disconnect")
def handle_disconnect():
    pass


@socketio.on("start_proctoring")
def handle_start_proctoring(data):
    """Desktop client signals it is ready to send proctoring frames."""
    session_id = data.get("session_id")
    if not session_id:
        return
    join_room(session_id)
    print(f"Proctoring started for session {session_id}")


@socketio.on("proctoring_frame")
def handle_proctoring_frame(data):
    """
    Receives a JPEG frame (base64) from the desktop client once per second,
    runs MediaPipe head-pose + DeepFace identity check, and emits a
    proctoring_alert back to the room if a violation is detected.
    """
    if not _proctoring_available:
        return

    session_id = data.get("session_id")
    image_data = data.get("image", "")
    if not session_id or not image_data:
        return

    session = live_sessions.get(session_id)
    if not session:
        return  # Face not registered yet — ignore frame

    try:
        # Decode base64 frame to numpy array
        encoded = image_data.split(",", 1)[1] if "," in image_data else image_data
        img_bytes = base64.b64decode(encoded)
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        import cv2
        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if frame is None:
            return

        result = analyze_frame_for_proctoring(
            current_frame=frame,
            registered_face_img=session["registered_face"],
            current_score=session["proctoring_score"],
            infractions=session["infractions"],
        )

        session["proctoring_score"] = result["score"]
        session["infractions"] = result["infractions"]

        if result["status"] != "Status: OK":
            socketio.emit(
                "proctoring_alert",
                {
                    "status": result["status"],
                    "score": result["score"],
                    "infractions": result["infractions"],
                },
                room=session_id,
            )
    except Exception as e:
        print(f"proctoring_frame error for {session_id}: {e}")


@socketio.on("proctoring_violation")
def handle_proctoring_violation(data):
    """Records a manual violation (tab switch, window blur) in the session store."""
    session_id = data.get("session_id")
    violation_type = data.get("type", "unknown")
    if not session_id:
        return
    session = live_sessions.get(session_id)
    if session:
        key = f"manual_{violation_type}"
        session["infractions"][key] = session["infractions"].get(key, 0) + 1
    print(f"Manual violation [{violation_type}] for session {session_id}")


@socketio.on("join_mobile_session")
def handle_mobile_join(data):
    session_id = data.get("session_id")
    join_room(session_id)
    socketio.emit("mobile_connected", {"status": "connected"}, room=session_id)


@socketio.on("control_mobile_recording")
def handle_mobile_control(data):
    session_id = data.get("session_id")
    action = data.get("action")  # 'start' or 'stop'

    # Relay the command to the mobile device in the room
    socketio.emit("mobile_recording_action", {"action": action}, room=session_id)


@socketio.on("mobile_status_update")
def handle_mobile_status(data):
    session_id = data.get("session_id")
    status = data.get("status")  # e.g., 'recording', 'uploading', 'completed'
    # Relay status back to desktop to show user
    socketio.emit("mobile_status_dashboard", {"status": status}, room=session_id)


if __name__ == "__main__":
    try:
        # Use socketio.run instead of app.run to enable WebSocket eventlet server
        socketio.run(app, debug=True, host="0.0.0.0", port=5000, use_reloader=True)
    finally:
        # Cleanup background processor on shutdown
        logger.info("Shutting down background processor...")
        background_processor.stop()
        logger.info("Background processor stopped")
        try:
            invite_cleanup_scheduler.stop()
            logger.info("Invite cleanup scheduler stopped")
        except Exception:
            pass
