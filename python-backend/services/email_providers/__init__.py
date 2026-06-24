import os

from services.email_providers.base import EmailProvider
from services.email_providers.mailgun import MailgunProvider
from services.email_providers.noop import NoopEmailProvider
from services.email_providers.zeptomail import ZeptoMailProvider

_PROVIDERS = {
    "zeptomail": ZeptoMailProvider,
    "mailgun": MailgunProvider,
    "noop": NoopEmailProvider,
}


def _strict_email_config() -> bool:
    configured = (os.getenv("EMAIL_FAIL_FAST") or "").strip().lower()
    if configured in {"1", "true", "yes", "on"}:
        return True
    if configured in {"0", "false", "no", "off"}:
        return False
    return (os.getenv("FLASK_ENV") or "").strip().lower() == "production"


def get_email_provider() -> EmailProvider:
    """Build an EmailProvider based on the EMAIL_PROVIDER env var.

    The noop provider is only used when explicitly configured, or as a
    development fallback when credentials are missing.
    """
    name = (os.getenv("EMAIL_PROVIDER") or "zeptomail").strip().lower()
    provider_cls = _PROVIDERS.get(name)

    if provider_cls is None:
        message = (
            f"[email] unknown EMAIL_PROVIDER={name!r}. "
            f"Valid: {', '.join(sorted(_PROVIDERS))}"
        )
        if _strict_email_config():
            raise RuntimeError(message)
        print(f"{message}; falling back to noop")
        return NoopEmailProvider()

    provider = provider_cls()
    if provider.healthcheck():
        print(f"[email] provider active: {provider.name}")
        return provider

    message = f"[email] provider {name!r} configured but credentials are missing"
    if name == "noop":
        print("[email] provider active: noop")
        return provider
    if _strict_email_config():
        raise RuntimeError(message)

    print(f"{message}; falling back to noop for development")
    return NoopEmailProvider()


__all__ = ["EmailProvider", "get_email_provider"]
