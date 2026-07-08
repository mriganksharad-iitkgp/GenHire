"""JWT signing-secret resolution — the single source of truth.

Previously three modules (auth middleware, auth controller, invite controller)
each read JWT_SECRET_KEY with their own copy of the insecure dev fallback
string. All three now call get_jwt_secret(); the first call resolves and
caches the value so every signer/verifier in the process agrees on one secret.

The dev fallback string is kept verbatim so tokens issued by older dev
processes stay verifiable.
"""

import os

_UNSET = object()
_cached = _UNSET


def get_jwt_secret() -> str:
    global _cached
    if _cached is not _UNSET:
        return _cached

    flask_env = os.getenv("FLASK_ENV", "").strip().lower()
    secret = os.getenv("JWT_SECRET_KEY")
    if not secret:
        if flask_env == "production":
            raise RuntimeError(
                "JWT_SECRET_KEY is not set. Refusing to start in production with a "
                "guessable default secret — set this env var before starting the app."
            )
        print("[WARN] JWT_SECRET_KEY is not set — using an insecure development-only default. "
              "This MUST be set before deploying to production.")
        secret = "your-secret-key-here"

    _cached = secret
    return _cached
