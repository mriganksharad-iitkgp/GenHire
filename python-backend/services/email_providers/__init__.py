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


def get_email_provider() -> EmailProvider:
    """Build an EmailProvider based on the EMAIL_PROVIDER env var.

    Falls back to the noop provider with a warning if the configured provider
    is missing credentials so dev environments don't crash on startup.
    """
    name = (os.getenv("EMAIL_PROVIDER") or "zeptomail").strip().lower()
    provider_cls = _PROVIDERS.get(name)

    if provider_cls is None:
        print(
            f"[email] unknown EMAIL_PROVIDER={name!r}; falling back to noop. "
            f"Valid: {', '.join(sorted(_PROVIDERS))}"
        )
        return NoopEmailProvider()

    provider = provider_cls()
    if not provider.healthcheck():
        # print(
        #     f"[email] provider {name!r} configured but credentials missing; "
        #     f"falling back to noop. Set the appropriate env vars to enable real sending."
        # )
        return NoopEmailProvider()

    return provider


__all__ = ["EmailProvider", "get_email_provider"]
