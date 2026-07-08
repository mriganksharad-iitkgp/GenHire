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

from flask import Flask, request, jsonify, g
from extensions import socketio
import datetime
import uuid
from bson import ObjectId

# Import configuration
from config.env_loader import load_environment
from config.database import db_config
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

from controllers.admin_controller import AdminController

# Import payment module
try:
    from payment_module.routes import payment_bp, init_payment_routes
    from payment_module.services.subscription_service import SubscriptionService
    from payment_module.services.wallet_service import WalletService

    PAYMENT_MODULE_AVAILABLE = True
    print("[OK] Payment module loaded successfully")
except ImportError as e:
    print(f"[WARN] Payment module not available: {e}")
    PAYMENT_MODULE_AVAILABLE = False
    SubscriptionService = None
    WalletService = None

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
    interview_manager,
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
# Interview REST routes (the interview engine's HTTP surface) live in
# routes/interview_routes.py; wired here after the DB and runtime exist.
from routes.interview_routes import init_interview_routes, interview_bp

init_interview_routes(db, collections)
app.register_blueprint(interview_bp)


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
