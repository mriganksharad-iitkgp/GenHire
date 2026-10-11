import os
from pathlib import Path

from dotenv import load_dotenv


_LOADED = False


def normalize_google_credential_overrides() -> None:
    """Treat blank optional overrides as absent before Google SDK discovery.

    google-auth treats GOOGLE_APPLICATION_CREDENTIALS="" as a credential file
    path and raises before trying the attached Cloud Run service identity.
    Preserve every nonblank override, including invalid ones: configuration
    errors must not silently switch to another identity.
    """
    for key in ("GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_APPLICATION_CREDENTIALS_JSON"):
        value = os.environ.get(key)
        if value is not None and not value.strip():
            os.environ.pop(key, None)


def load_environment() -> None:
    """Load local dotenv config without overriding platform env vars."""
    global _LOADED
    if _LOADED:
        normalize_google_credential_overrides()
        return

    backend_root = Path(__file__).resolve().parents[1]
    explicit_env_file = os.getenv("ENV_FILE") or os.getenv("DOTENV_PATH")

    if explicit_env_file:
        env_path = Path(explicit_env_file)
        if not env_path.is_absolute():
            env_path = backend_root / env_path
        load_dotenv(env_path, override=False)
    elif os.getenv("FLASK_ENV", "").strip().lower() == "production":
        load_dotenv(backend_root / ".env.production", override=False)

    load_dotenv(backend_root / ".env", override=False)
    normalize_google_credential_overrides()
    _LOADED = True
