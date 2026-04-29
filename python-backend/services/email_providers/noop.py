from typing import Optional

from services.email_providers.base import EmailProvider


class NoopEmailProvider(EmailProvider):
    """Dev-only provider: prints a summary of what would be sent and returns success.

    Used when EMAIL_PROVIDER is unset or the chosen provider has missing credentials,
    so local development isn't blocked by missing keys.
    """

    name = "noop"

    def send(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        *,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> bool:
        body_preview = (text_content or html_content or "")[:200].replace("\n", " ")
        print(
            f"[email:noop] to={to_email} subject={subject!r} preview={body_preview!r}"
        )
        return True
