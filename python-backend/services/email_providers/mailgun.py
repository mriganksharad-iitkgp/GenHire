import os
from typing import Optional

import requests

from services.email_providers.base import EmailProvider


class MailgunProvider(EmailProvider):
    name = "mailgun"

    def __init__(self):
        self.api_key = os.getenv("MAILGUN_API_KEY")
        self.domain = os.getenv("MAILGUN_DOMAIN")
        self.api_url = (
            f"https://api.mailgun.net/v3/{self.domain}/messages" if self.domain else None
        )
        self.default_from_email = os.getenv(
            "MAILGUN_FROM_EMAIL",
            f"noreply@{self.domain}" if self.domain else "",
        )
        self.default_from_name = os.getenv("MAILGUN_FROM_NAME", "")

    def _format_from(self, from_email: Optional[str], from_name: Optional[str]) -> str:
        addr = from_email or self.default_from_email
        name = from_name or self.default_from_name
        return f"{name} <{addr}>" if name else addr

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
        if not self.api_key or not self.domain:
            self.last_error = "mailgun credentials not configured"
            print("[email:mailgun] credentials not configured; cannot send")
            return False

        data = {
            "from": self._format_from(from_email, from_name),
            "to": to_email,
            "subject": subject,
            "html": html_content,
        }
        if text_content:
            data["text"] = text_content
        if reply_to:
            data["h:Reply-To"] = reply_to

        try:
            response = requests.post(
                self.api_url,
                auth=("api", self.api_key),
                data=data,
                timeout=15,
            )
        except Exception as e:
            self.last_error = f"mailgun transport error: {e}"
            print(f"[email:mailgun] transport error: {e}")
            return False

        if response.status_code == 200:
            self.last_error = None
            print(f"[email:mailgun] sent to {to_email}")
            return True

        self.last_error = f"mailgun {response.status_code}: {response.text[:300]}"
        print(
            f"[email:mailgun] failed ({response.status_code}): {response.text[:300]}"
        )
        return False

    def healthcheck(self) -> bool:
        return bool(self.api_key and self.domain)
