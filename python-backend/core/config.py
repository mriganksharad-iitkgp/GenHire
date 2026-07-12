"""Typed accessors for app-level environment configuration.

Central home for the env vars the composition root reads. Domain modules keep
their own settings objects (payment_module/config, interview/config); values
here are the cross-cutting server ones. Other os.getenv call sites migrate
here opportunistically as their modules get touched.
"""

import os


def flask_env() -> str:
    return os.getenv("FLASK_ENV", "").strip().lower()


def is_production() -> bool:
    return flask_env() == "production"


def flask_secret_key() -> str:
    """Flask session secret; refuses to boot in production without one."""
    secret = os.getenv("FLASK_SECRET_KEY")
    if not secret:
        if is_production():
            raise RuntimeError(
                "FLASK_SECRET_KEY is not set. Refusing to start in production with a "
                "guessable default secret — set this env var before starting the app."
            )
        print("[WARN] FLASK_SECRET_KEY is not set — using an insecure development-only default. "
              "This MUST be set before deploying to production.")
        secret = "your-flask-secret-key"
    return secret


def allowed_origins() -> list:
    """Origins allowed to call this API / hold a Socket.IO connection to it.

    Trailing slashes are stripped: a browser's Origin header is always
    scheme://host[:port] with NO trailing slash, so an env value like
    "https://genhire.in/" would otherwise never match and silently break
    CORS in production."""
    return [
        o.strip().rstrip("/")
        for o in os.getenv("CORS_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000").split(",")
        if o.strip().rstrip("/")
    ]


def force_https() -> bool:
    return os.getenv("FORCE_HTTPS", "false").strip().lower() == "true"


def redis_url() -> str:
    # `or` (not a getenv default) so REDIS_URL= (set but empty) still means
    # "no Redis" rather than an empty connection string.
    return os.getenv("REDIS_URL") or "memory://"


def jobs_disabled() -> bool:
    """Tooling (route manifest, scripts) sets GENHIRE_DISABLE_JOBS=1 so
    importing the app doesn't spawn background worker threads."""
    return os.getenv("GENHIRE_DISABLE_JOBS") == "1"

def mobile_recording_enabled() -> bool:
    """Feature toggle for the mobile companion camera (QR pairing + upload).
    MOBILE_RECORDING_ENABLED=false hides the pairing UI and rejects uploads."""
    return (os.getenv("MOBILE_RECORDING_ENABLED", "true") or "true").strip().lower() == "true"
