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

from flask import Flask, request, jsonify, Response, g
from extensions import socketio
from werkzeug.utils import secure_filename
import datetime
import uuid
import base64
from bson import ObjectId

import time

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
from services import face_verification_service as face_service
from services.email_service import EmailService
from services.usage_telemetry_service import record_usage_event
from controllers.admin_controller import AdminController
from payment_module.services.subscription_service import SubscriptionService
from payment_module.services.wallet_service import WalletService
from payment_module.config.settings import PaymentConfig
from interview.core.cost_tracker import CostTracker

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

# Error tracking — sentry-sdk has been a listed dependency with no actual
# init call anywhere in the codebase. Safe to call unconditionally: the SDK
# is explicitly designed to no-op when dsn is empty/None, so this does
# nothing until a real SENTRY_DSN is supplied.
try:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration

    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[FlaskIntegration()],
        environment=os.getenv("FLASK_ENV", "development"),
        traces_sample_rate=0.1,
    )
    if os.getenv("SENTRY_DSN"):
        print("[OK] Sentry error tracking initialized")
except Exception as e:
    print(f"[WARN] Sentry initialization skipped: {e}")


# Initialize Flask app
app = Flask(__name__)

_flask_env = os.getenv("FLASK_ENV", "").strip().lower()
_is_production = _flask_env == "production"

_flask_secret = os.getenv("FLASK_SECRET_KEY")
if not _flask_secret:
    if _is_production:
        raise RuntimeError(
            "FLASK_SECRET_KEY is not set. Refusing to start in production with a "
            "guessable default secret — set this env var before starting the app."
        )
    print("[WARN] FLASK_SECRET_KEY is not set — using an insecure development-only default. "
          "This MUST be set before deploying to production.")
    _flask_secret = "your-flask-secret-key"
app.config["SECRET_KEY"] = _flask_secret
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB — rejects oversized request bodies before they're read

# Origins allowed to call this API / hold a Socket.IO connection to it. Reads
# the CORS_ORIGINS env var (already documented in .env.example but never
# actually wired up) instead of the previous hardcoded wildcard, which is
# invalid to combine with supports_credentials=True in the first place.
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000").split(",")
    if o.strip()
]

# Setup Security Headers (Helmet equivalent) — optional
try:
    from flask_talisman import Talisman

    # force_https defaults off so local HTTP dev keeps working; set
    # FORCE_HTTPS=true in production to enable the HTTPS redirect + HSTS.
    _force_https = os.getenv("FORCE_HTTPS", "false").strip().lower() == "true"
    # Scoped to what this backend actually serves itself (a JSON API plus one
    # small server-rendered page, /api/interviews/<id>/gaze-recorder-page,
    # which loads three GazeCloudAPI/GazeRecorderAPI scripts from
    # app.gazerecorder.com plus an inline <script> block) — NOT the React SPA,
    # which this Flask app never serves and which is hosted separately.
    _csp = {
        "default-src": "'self'",
        "script-src": ["'self'", "'unsafe-inline'", "https://app.gazerecorder.com"],
        "style-src": ["'self'", "'unsafe-inline'"],
        "connect-src": ["'self'", "https://app.gazerecorder.com", "wss://app.gazerecorder.com"],
        "img-src": ["'self'", "data:", "https://app.gazerecorder.com"],
        "media-src": ["'self'", "https://app.gazerecorder.com"],
        "frame-src": ["'self'", "https://app.gazerecorder.com"],
    }
    Talisman(app, content_security_policy=_csp, force_https=_force_https)
    print(f"[OK] Flask-Talisman loaded (force_https={_force_https})")
except ImportError:
    print("[WARN] flask-talisman not installed, skipping security headers. Install with: pip install Flask-Talisman")

# Setup Rate Limiting — optional
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    # In development, we use very high limits to avoid rate limiting developers
    is_development = os.getenv("FLASK_ENV") == "development"
    default_limits = ["100000 per day", "10000 per hour"] if is_development else ["200 per day", "50 per hour"]

    # Falls back to in-process memory storage (today's behavior, fine for a
    # single worker) automatically when REDIS_URL isn't set — set it to make
    # limits shared/accurate across multiple workers or containers.
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=default_limits,
        storage_uri=os.getenv("REDIS_URL", "memory://")
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

# Initialize extensions (socketio instance is shared via extensions.py so
# controllers can emit without importing this module and causing a cycle)
socketio.init_app(app, cors_allowed_origins=ALLOWED_ORIGINS)

# Restrict CORS to known origins (see ALLOWED_ORIGINS above) — a wildcard
# origin combined with supports_credentials=True is invalid per the CORS spec
# and was allowing any site to make credentialed requests to this API.
CORS(
    app,
    resources={
        r"/*": {
            "origins": ALLOWED_ORIGINS,
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
    logger.error(f"Unhandled Exception [request_id={g.get('request_id', '-')}]: {str(e)}")
    logger.error(traceback.format_exc())
    return jsonify(error="Internal Server Error", message="An unexpected error occurred.", code=500), 500


# Request correlation id — reuses an inbound X-Request-ID (e.g. from a reverse
# proxy that already generates one) or mints a fresh one, so a single
# request's logs/Sentry events/response can all be tied together.
@app.before_request
def assign_request_id():
    g.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())


@app.after_request
def add_request_id_header(response):
    response.headers["X-Request-ID"] = g.get("request_id", "-")
    return response


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

# Interview runtime state (session manager singleton, live proctoring session
# store, upload folder layout, gaze recorder) lives in interview/runtime.py so
# the socket handlers, interview routes, and sweepers all share one instance.
from interview.runtime import (
    PROCTORING_FOLDER,
    RECORDING_FOLDER,
    TMP_FOLDER,
    gaze_recorder_service,
    interview_manager,
    live_sessions,
)

# Credit-lifecycle sweeper: refunds start-time debits for interviews that
# never produced a single answer (abandoned tab, identity block, crash) and
# auto-finalizes substantive-but-unended sessions into scored reports.
from services import interview_credit_service

interview_refund_sweeper = interview_credit_service.get_interview_refund_sweeper(
    collections, interview_manager
)
interview_refund_sweeper.start()
logger.info("[OK] Interview credit-refund sweeper started")

# === INTERVIEW REST ROUTES (extraction pending — see routes/interview_routes.py plan) ===

app.config["PROCTORING_FOLDER"] = PROCTORING_FOLDER
app.config["RECORDING_FOLDER"] = RECORDING_FOLDER
app.config["TMP_FOLDER"] = TMP_FOLDER

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



# System routes (index, /health, GridFS files) and cost-tracking routes
# (/chat, /cost-summary, /stt-cost, /tts-cost) moved to their own blueprints;
# registered here where they were previously defined.
from routes.system_routes import create_system_routes
from routes.cost_routes import create_cost_routes

app.register_blueprint(create_system_routes(db))
app.register_blueprint(create_cost_routes(db))


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
        before a usable session exists — credits used to simply vanish here."""
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

    # Build plain-text CV — prefer snapshot text (PDF CVs), fall back to structured details
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
        # doc means no interview can ever happen for this charge — refund,
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
            "question_deadline": session_details.get("question_deadline"),
            "max_questions": session_details.get("max_questions"),
            "proctoring_config": interview_doc["proctoring_config"],
            "credits_deducted": recruiter_interview_cost,
            "usage_deduction": recruiter_deduction,
            "recruiter_wallet_balance": (recruiter_deduction or {}).get("transaction", {}).get("balance_after"),
        }
    )


@app.route("/api/interviews/<session_id>/question", methods=["GET"])
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

    # `answer` may legitimately be an empty string — a client-side no-response
    # timeout auto-submits "" to advance the interview rather than leaving it
    # stuck. Only a missing question or a genuinely absent (None) answer is invalid.
    if not question or answer is None:
        return jsonify({"error": "Question and answer are required"}), 400

    try:
        # Submit answer using new system
        result = interview_manager.submit_answer(session_id, question, answer)

        if "error" in result:
            return jsonify(result), 400

        # Restart-safe evidence for the credit-refund policy: count
        # substantive answers on the interview doc itself. Repeat requests and
        # empty auto-skips deliberately don't count — an interview with zero
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

    # Interview score will be computed from final_evaluation below.
    # NOTE: CostTracker().end_session is called exactly once, further down,
    # after the fallback estimates are known — an earlier extra call here used
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

    # DB-stored score from GazeRecorder (third-party CDN eye-tracking, submitted
    # via /gaze-recorder-results while the interview was running — see
    # finalizeInlineGazeRecorder in Chat.jsx). Real, but depends on that CDN
    # script loading successfully in the candidate's browser.
    db_score = (session_doc or {}).get("proctoring_score")
    if db_score is None:
        db_score = (session_doc or {}).get("gaze_recorder_score")

    manual_infractions = list((session_doc or {}).get("manual_infractions") or [])
    gaze_times = (session_doc or {}).get("gaze_metrics")
    gaze_plot_path = (session_doc or {}).get("gaze_plot_path")

    # Live MediaPipe/DeepFace-based score computed in-process, in real time,
    # while frames streamed in over this same app's own Socket.IO connection
    # (see register_face / handle_proctoring_frame below) — an independent
    # signal from db_score, not a duplicate of it. Previously this was never
    # read at all; /end instead called a separate microservice
    # (gpu_intensive_task/proctoring_server.py, port 5001) that nothing in the
    # current frontend ever actually streams frames to, so it was always
    # either unreachable (wasted latency, fell through to a hardcoded 90) or
    # reachable-but-empty (silently overwrote a real score with its default of
    # 100 for a session_id it had never seen).
    live_session = live_sessions.get(session_id)
    live_score = live_session.get("proctoring_score") if live_session else None

    # Combine conservatively — either detection method catching a problem
    # should count, since they're independent signals (gaze/cheating-score vs.
    # head-pose/identity), not two measurements of the same thing.
    scores_available = [s for s in (db_score, live_score) if s is not None]
    if scores_available:
        proctoring_score = min(scores_available)
        proctoring_status = "complete"
    else:
        # Neither signal is available (camera/mic denied, GazeRecorder CDN
        # blocked, etc.) — be honest about it instead of awarding a fabricated
        # default score that would let a candidate whose proctoring pipeline
        # failed score as if nothing was wrong.
        proctoring_score = None
        proctoring_status = "incomplete"

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
                "proctoring_status": proctoring_status,  # "complete" or "incomplete" — never a fabricated fallback
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
                        "proctoring_status": proctoring_status,
                        "transcript": interview_transcript,
                        "usage_summary": usage_summary,
                        "usage_deduction": usage_deduction,
                        "error": "Application not found",
                    }
                )

            previous_status = str(existing_app.get("status", "pending")).lower()
            # Must be assigned before the notification block below uses it —
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

            # Push the finished interview's scores live — this write path is
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
                print(f"⚠️ Interview completion notification failed: {_notify_exc}")

            if result.modified_count == 0:
                print(
                    f"❌ Warning: Application {application_id} was not updated (no documents modified)"
                )

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
            "proctoring_status": proctoring_status,
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
# No JWT here on purpose: the mobile companion is opened from a QR link and
# has no token. The unguessable session_id acts as the capability; we at
# least require it to reference a real session before accepting a file.
def upload_mobile_recording(session_id):
    session_exists = interviews_collection.find_one(
        {"session_id": session_id}, {"_id": 1}
    ) or collections["practice_sessions"].find_one({"session_id": session_id}, {"_id": 1})
    if not session_exists:
        return jsonify({"error": "Session not found"}), 404

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


def _identity_summary(identity, session_id):
    """Compact copy of an identity_verification block for the application doc,
    so recruiter candidate lists can badge identity state without joining the
    interviews collection."""
    return {
        "status": identity.get("status"),
        "verified": identity.get("verified"),
        "distance": identity.get("distance"),
        "threshold": identity.get("threshold"),
        "session_id": session_id,
        "checked_at": identity.get("checked_at"),
    }


@app.route("/api/interviews/<session_id>/register-face", methods=["POST"])
@token_required
def register_face(current_user, session_id):
    """
    Capture the candidate's face before the interview starts.

    Real interviews enforce account-level identity: the first-ever real
    interview enrolls the capture as the account's canonical face; every later
    real interview must DeepFace-match that canonical photo (across any job /
    company) or the interview is blocked after a few attempts. The capture and
    verdict are stored on the interview + application so the recruiter can see
    exactly who sat the interview. Practice interviews only capture (for live
    proctoring) — they never enroll and never block.
    """
    data = request.get_json()
    if not data or "image" not in data:
        return jsonify({"error": "No image data provided", "error_code": "invalid_image"}), 400

    try:
        # Strip the data-URL prefix (e.g. "data:image/jpeg;base64,...")
        raw = data["image"]
        encoded = raw.split(",", 1)[1] if "," in raw else raw
        decoded_image = base64.b64decode(encoded)
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

    quality = face_service.assess_face_image(decoded_image)
    if not quality.get("ok"):
        return (
            jsonify(
                {
                    "error": quality.get("message", "Face image rejected"),
                    "error_code": quality.get("error_code", "invalid_image"),
                }
            ),
            400,
        )

    now = datetime.datetime.utcnow()
    mode = face_service.get_mode()
    identity = {
        "checked_at": now,
        "mode": mode,
        "model": face_service.FACE_MODEL_NAME,
    }

    try:
        user_doc = users_collection.find_one({"_id": current_user["_id"]}, {"face_profile": 1})
        face_profile = (user_doc or {}).get("face_profile") or {}
        reference_file_id = face_profile.get("image_file_id")

        if practice_doc is not None:
            # Practice: capture for live proctoring, softly verify against the
            # canonical identity when one exists, never enroll, never block.
            identity["status"] = "practice_captured"
            identity["verified"] = None
            if reference_file_id and mode != "off":
                try:
                    ref_bytes, _ = face_service.load_face_image(db, reference_file_id)
                    verdict = face_service.verify_face_images(ref_bytes, decoded_image)
                    if verdict.get("available"):
                        identity["verified"] = verdict["verified"]
                        identity["distance"] = verdict["distance"]
                        identity["threshold"] = verdict["threshold"]
                except Exception as exc:
                    print(f"Practice face soft-verify failed for {session_id}: {exc}")
            collections["practice_sessions"].update_one(
                {"_id": practice_doc["_id"]},
                {"$set": {"identity_verification": identity, "updated_at": now}},
            )
        else:
            prior = interview_doc.get("identity_verification") or {}
            attempts = int(prior.get("attempts") or 0)
            max_attempts = face_service.get_max_attempts()

            if mode == "off":
                identity.update({"status": "skipped", "verified": None, "attempts": attempts})
            elif not reference_file_id:
                # First real interview on this account — enroll this capture as
                # the canonical identity all future interviews are matched to.
                file_id = face_service.store_face_image(
                    db, decoded_image, user_id=user_id, session_id=session_id, purpose="enrollment"
                )
                users_collection.update_one(
                    {"_id": current_user["_id"]},
                    {
                        "$set": {
                            "face_profile": {
                                "image_file_id": file_id,
                                "registered_at": now,
                                "source_session_id": session_id,
                                "source_application_id": interview_doc.get("application_id"),
                            }
                        }
                    },
                )
                identity.update(
                    {
                        "status": "registered_new",
                        "verified": None,
                        "attempts": attempts,
                        "captured_image_file_id": file_id,
                        "reference_image_file_id": file_id,
                    }
                )
            else:
                identity["reference_image_file_id"] = reference_file_id
                ref_bytes = None
                try:
                    ref_bytes, _ = face_service.load_face_image(db, reference_file_id)
                except Exception as exc:
                    print(f"Failed to load canonical face {reference_file_id}: {exc}")

                verdict = (
                    face_service.verify_face_images(ref_bytes, decoded_image)
                    if ref_bytes
                    else {"available": False, "verified": None, "distance": None, "threshold": None}
                )

                if not verdict.get("available"):
                    # Face stack down / reference unreadable: fail open so a
                    # server-side dependency problem can't lock candidates out,
                    # but record the gap honestly for the recruiter.
                    captured_id = face_service.store_face_image(
                        db, decoded_image, user_id=user_id, session_id=session_id, purpose="capture"
                    )
                    identity.update(
                        {
                            "status": "unverified_system_unavailable",
                            "verified": None,
                            "attempts": attempts,
                            "captured_image_file_id": captured_id,
                        }
                    )
                elif verdict["verified"]:
                    captured_id = face_service.store_face_image(
                        db, decoded_image, user_id=user_id, session_id=session_id, purpose="capture"
                    )
                    identity.update(
                        {
                            "status": "verified",
                            "verified": True,
                            "distance": verdict["distance"],
                            "threshold": verdict["threshold"],
                            "attempts": attempts,
                            "captured_image_file_id": captured_id,
                        }
                    )
                else:
                    attempts += 1
                    identity.update(
                        {
                            "verified": False,
                            "distance": verdict["distance"],
                            "threshold": verdict["threshold"],
                            "attempts": attempts,
                        }
                    )
                    blocked = mode == "enforce" and attempts >= max_attempts

                    if mode == "monitor":
                        # Record the mismatch but let the interview proceed.
                        captured_id = face_service.store_face_image(
                            db, decoded_image, user_id=user_id, session_id=session_id, purpose="capture"
                        )
                        identity["status"] = "unverified_monitor"
                        identity["captured_image_file_id"] = captured_id
                    else:
                        if blocked:
                            evidence_id = face_service.store_face_image(
                                db,
                                decoded_image,
                                user_id=user_id,
                                session_id=session_id,
                                purpose="mismatch_evidence",
                            )
                            identity["status"] = "mismatch_blocked"
                            identity["captured_image_file_id"] = evidence_id
                        else:
                            identity["status"] = "mismatch"

                        update_fields = {"identity_verification": identity, "updated_at": now}
                        if blocked:
                            update_fields["status"] = "identity_blocked"
                        interviews_collection.update_one(
                            {"_id": interview_doc["_id"]}, {"$set": update_fields}
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

                        if blocked:
                            return (
                                jsonify(
                                    {
                                        "error": "Face verification failed repeatedly — this interview attempt has been locked because the captured face does not match this account's registered identity.",
                                        "error_code": "face_mismatch_blocked",
                                        "attempts_remaining": 0,
                                    }
                                ),
                                403,
                            )
                        return (
                            jsonify(
                                {
                                    "error": "The captured face does not match the identity registered on this account. Make sure you are the account owner, face the camera directly in good lighting, and try again.",
                                    "error_code": "face_mismatch",
                                    "attempts_remaining": max(0, max_attempts - attempts),
                                }
                            ),
                            403,
                        )

            # Allowed real-interview paths: persist verdict and activate session
            interviews_collection.update_one(
                {"_id": interview_doc["_id"]},
                {"$set": {"identity_verification": identity, "status": "active", "updated_at": now}},
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
            "registered_face": decoded_image,
            "registered_face_np": face_service.decode_image(decoded_image),
            "proctoring_score": 100,
            "infractions": {},
        }

        status = identity.get("status")
        if status == "registered_new":
            message = "Face registered successfully — this photo is now the verified identity for your account."
        elif status == "verified":
            message = "Identity verified successfully."
        else:
            message = "Face captured successfully."

        return (
            jsonify(
                {
                    "message": message,
                    "identity": {
                        "status": status,
                        "verified": identity.get("verified"),
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


@app.route("/api/interviews/<session_id>/face-image/<kind>", methods=["GET"])
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


# Socket.IO event handlers (proctoring stream + mobile companion) moved to
# sockets/; registering here preserves the original definition position.
import sockets

sockets.register_all()


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
        try:
            interview_refund_sweeper.stop()
            logger.info("Interview refund sweeper stopped")
        except Exception:
            pass
