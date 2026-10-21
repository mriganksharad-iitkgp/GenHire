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


def require_database_configuration() -> None:
    """Never let a worker/maintenance command default to localhost or another DB."""
    uri = os.getenv('MONGODB_URI', '').strip()
    if not uri.startswith(('mongodb://', 'mongodb+srv://')) or not os.getenv('DATABASE_NAME', '').strip():
        raise RuntimeError('Explicit MONGODB_URI and DATABASE_NAME are required for database operations; refusing MongoDB defaults.')


def load_environment(require_database=False) -> None:
    """Select one dotenv profile without overriding platform environment values."""
    global _LOADED
    if _LOADED:
        normalize_google_credential_overrides()
        if require_database:
            require_database_configuration()
        return

    backend_root = Path(__file__).resolve().parents[1]
    explicit_env_file = os.getenv("ENV_FILE") or os.getenv("DOTENV_PATH")

    if explicit_env_file:
        env_path = Path(explicit_env_file)
        if not env_path.is_absolute():
            env_path = backend_root / env_path
        if not env_path.is_file():
            raise RuntimeError('Explicit ENV_FILE/DOTENV_PATH does not exist; refusing fallback to another environment.')
        load_dotenv(env_path, override=False)
    elif os.getenv("FLASK_ENV", "").strip().lower() == "production":
        load_dotenv(backend_root / ".env.production", override=False)
    else:
        load_dotenv(backend_root / ".env", override=False)
    normalize_google_credential_overrides()
    _LOADED = True
    if require_database:
        require_database_configuration()
