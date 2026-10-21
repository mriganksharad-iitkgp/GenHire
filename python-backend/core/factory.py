"""Application factory — the composition root.

create_app() builds the Flask app in the exact phase order the old
module-level app.py used: Sentry → Flask + secrets/limits → Talisman/Limiter →
JSON provider → Socket.IO → CORS + request hooks + error handler → database →
background jobs → blueprints → socket handlers.

Module-level import order below also mirrors the old app.py deliberately
(blueprints before load_environment(), the google.cloud.speech probe before
speech_routes) — several modules read env or initialize clients at import
time, so the order is behavior, not style.
"""

import core.bootstrap  # noqa: F401  (must run before heavy imports)

import logging
import os
import traceback
import uuid

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
_ch = logging.StreamHandler()
_ch.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(_ch)

from flask import Flask, request, jsonify, g
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from core import config as app_config
from core.extensions import socketio
from core.json_provider import ObjectIdSafeJSONProvider

# Import configuration
from config.env_loader import load_environment
from config.database import db_config

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
from routes.identity_routes import identity_bp

try:
    from google.cloud import speech  # noqa: F401
    print("--- DEBUG: google.cloud.speech imported before speech_routes ---")
except ImportError as e:
    print(f"--- DEBUG: google.cloud.speech FAILED before speech_routes: {e} ---")
from routes.speech_routes import speech_bp

from controllers.admin_controller import AdminController

# Import payment module
try:
    from payment_module.routes import payment_bp, init_payment_routes
    from payment_module.services.subscription_service import SubscriptionService

    PAYMENT_MODULE_AVAILABLE = True
    print("[OK] Payment module loaded successfully")
except ImportError as e:
    print(f"[WARN] Payment module not available: {e}")
    PAYMENT_MODULE_AVAILABLE = False
    SubscriptionService = None

# Load environment variables
load_environment()

# Error tracking — no-ops until a real SENTRY_DSN is supplied.
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


def create_app():
    # import_name "app" (not __name__) keeps Flask's root_path at the backend
    # root, exactly where the old module-level app lived.
    app = Flask("app")

    app.config["SECRET_KEY"] = app_config.flask_secret_key()
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB — rejects oversized request bodies before they're read

    allowed_origins = app_config.allowed_origins()

    # Setup Security Headers (Helmet equivalent) — optional
    try:
        from flask_talisman import Talisman

        # force_https defaults off so local HTTP dev keeps working; set
        # FORCE_HTTPS=true in production to enable the HTTPS redirect + HSTS.
        _force_https = app_config.force_https()
        # Scoped to what this backend actually serves itself (a JSON API plus
        # the server-rendered gaze-recorder page, which loads GazeRecorderAPI
        # scripts from app.gazerecorder.com) — NOT the React SPA, which this
        # Flask app never serves.
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

    # ObjectId/datetime-safe JSON serialization for every route
    app.json = ObjectIdSafeJSONProvider(app)

    # Initialize extensions (shared socketio instance from core.extensions)
    from middleware.rate_limiter import env_int
    socketio.init_app(app, cors_allowed_origins=app_config.origin_is_allowed,
                     max_http_buffer_size=env_int("SOCKET_MAX_MESSAGE_BYTES", 2 * 1024 * 1024, maximum=16 * 1024 * 1024))

    # Restrict CORS to known origins — a wildcard origin combined with
    # supports_credentials=True is invalid per the CORS spec.
    CORS(
        app,
        resources={
            r"/*": {
                "origins": allowed_origins + [app_config.KIOSK_ORIGIN_PATTERN],
                "allow_headers": [
                    "Content-Type",
                    "Authorization",
                    "X-Mobile-Pairing-Token",
                    "Access-Control-Allow-Credentials",
                ],
                "supports_credentials": True,
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
                "expose_headers": ["Content-Type", "Authorization", "Retry-After", "X-Request-ID"],
            }
        },
    )

    @app.errorhandler(Exception)
    def handle_exception(e):
        from core.mongo_transactions import AtomicityUnavailable
        if isinstance(e, AtomicityUnavailable):
            return jsonify(error="Transactional storage is unavailable. Please retry later.",
                           error_code="atomicity_unavailable"), 503
        from pydantic import ValidationError
        if isinstance(e, ValidationError):
            details = [{"field": ".".join(str(item) for item in issue["loc"]), "message": issue["msg"]}
                       for issue in e.errors(include_input=False)]
            return jsonify(error="Invalid request data.", details=details), 400
        from pymongo.errors import AutoReconnect, WaitQueueTimeoutError, ServerSelectionTimeoutError
        if isinstance(e, (AutoReconnect, WaitQueueTimeoutError, ServerSelectionTimeoutError)):
            from middleware.rate_limiter import rejection
            return rejection(503, "database_busy", 3, "database")
        # Pass through HTTP errors
        if isinstance(e, HTTPException):
            response = e.get_response()
            response.data = app.json.dumps({"error": e.description, "code": e.code})
            response.content_type = "application/json"
            return response

        # Log and return standard JSON for unhandled errors
        logger.error(f"Unhandled Exception [request_id={g.get('request_id', '-')}]: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify(error="Internal Server Error", message="An unexpected error occurred.", code=500), 500

    # Request correlation id — reuses an inbound X-Request-ID or mints one, so
    # a request's logs/Sentry events/response can be tied together.
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
            return app.make_default_options_response()

    # Add CORS headers to all responses
    @app.after_request
    def after_request(response):
        origin = request.headers.get("Origin")
        if origin and app_config.origin_is_allowed(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Expose-Headers"] = "Content-Type, Authorization, Retry-After, X-Request-ID"
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, DELETE, OPTIONS, PATCH"
            )
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Mobile-Pairing-Token"
        return response

    from middleware.rate_limiter import install_request_protection
    install_request_protection(app)

    # Initialize database
    db = db_config.connect()
    collections = db_config.get_collections()

    # GCS is REQUIRED (owner decision): every persistent artifact — CVs, JDs,
    # ID cards, interview/mobile recordings, gaze artifacts — lives in Cloud
    # Storage only; there is no local-disk fallback. Failing here at boot is
    # deliberate: a misconfigured deployment must not come up and silently
    # lose uploads.
    from services import gcs_service
    if not gcs_service.is_gcs_configured():
        raise RuntimeError(
            "Google Cloud Storage is not configured (GCS_BUCKET_NAME + "
            "the Cloud Run service identity or local GCS credentials). "
            "GCS is mandatory — all uploads are stored there, with no local fallback."
        )
    print("[OK] GCS storage configured (mandatory, no local fallback)")

    # Signup grants happen at registration. Legacy wallet backfills are explicit
    # maintenance (scripts/migrations/backfill_signup_bonuses.py), never a
    # blocking all-user scan on every worker boot.

    # Interview runtime state (session manager singleton, live proctoring
    # session store, upload folders, gaze recorder) — one instance per process.
    from interview.runtime import (
        PROCTORING_FOLDER,
        RECORDING_FOLDER,
        TMP_FOLDER,
        interview_manager,
    )

    # Background workers (CV scoring queue, invite cleanup, refund sweeper).
    # Honors GENHIRE_DISABLE_JOBS=1 for tooling imports.
    from jobs import runner as jobs_runner

    jobs_runner.start_all(collections, interview_manager)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(job_bp)
    app.register_blueprint(application_bp)
    from routes.workflow_routes import create_workflow_routes
    app.register_blueprint(create_workflow_routes(db))
    from routes.job_setup_routes import create_job_setup_routes
    app.register_blueprint(create_job_setup_routes(db))
    from routes.assessment_authoring_routes import create_assessment_authoring_routes
    app.register_blueprint(create_assessment_authoring_routes(db))
    from routes.hiring_progression_routes import create_hiring_progression_routes
    app.register_blueprint(create_hiring_progression_routes(db))
    from routes.company_hiring_routes import create_company_hiring_routes
    app.register_blueprint(create_company_hiring_routes(db))
    from routes.practice_assessment_routes import create_practice_assessment_routes
    app.register_blueprint(create_practice_assessment_routes(db))
    app.register_blueprint(file_bp)
    app.register_blueprint(practice_bp)

    # CV routes require the connected collections
    cv_bp = create_cv_routes(collections)
    app.register_blueprint(cv_bp, url_prefix="/api/cv")

    # Initialize and register admin routes
    admin_controller = AdminController(collections)
    init_admin_routes(admin_controller)
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(speech_bp, url_prefix="/api/speech")
    app.register_blueprint(invite_bp)
    app.register_blueprint(identity_bp)
    logger.info("[OK] Admin routes registered at /api/admin")
    logger.info("[OK] Invite routes registered")

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
            SubscriptionService(db)
        except Exception as e:
            print(f"[WARN] Failed to initialize subscription billing service: {e}")

    # System routes (index, /health, GridFS files) and cost-tracking routes
    from routes.system_routes import create_system_routes
    from routes.cost_routes import create_cost_routes

    app.register_blueprint(create_system_routes(db))
    app.register_blueprint(create_cost_routes(db))

    # Interview REST routes (the interview engine's HTTP surface)
    from routes.interview_routes import init_interview_routes, interview_bp

    init_interview_routes(db, collections)
    app.register_blueprint(interview_bp)

    # Socket.IO event handlers (proctoring stream + mobile companion)
    import sockets

    sockets.register_all()

    return app
