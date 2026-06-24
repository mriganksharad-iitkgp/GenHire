import os
from pathlib import Path

from dotenv import load_dotenv


_LOADED = False


def load_environment() -> None:
    """Load local dotenv config without overriding platform env vars."""
    global _LOADED
    if _LOADED:
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
    _LOADED = True