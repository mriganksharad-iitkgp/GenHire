import os
from typing import Optional

import requests

from services.email_providers.base import EmailProvider


class ZeptoMailProvider(EmailProvider):
    name = "zeptomail"

    API_URL = "https://api.zeptomail.in/v1.1/email"

    def __init__(self):
        self.api_key = os.getenv("ZEPTOMAIL_API_KEY", "").strip()
        self.default_from_email = os.getenv("ZEPTOMAIL_FROM_EMAIL", "").strip()
        self.default_from_name = os.getenv("ZEPTOMAIL_FROM_NAME", "").strip()

    def _auth_header(self) -> str:
        key = self.api_key
        if key.lower().startswith("zoho-enczapikey "):
            return key
        return f"Zoho-enczapikey {key}"

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
        if not self.api_key or not (from_email or self.default_from_email):
            print("[email:zeptomail] credentials or from-address not configured; cannot send")
            return False

        sender_addr = from_email or self.default_from_email
        sender_name = from_name or self.default_from_name or sender_addr

        payload = {
            "from": {"address": sender_addr, "name": sender_name},
            "to": [{"email_address": {"address": to_email, "name": to_email}}],
            "subject": subject,
            "htmlbody": html_content,
        }
        if text_content:
            payload["textbody"] = text_content
        if reply_to:
            payload["reply_to"] = [{"address": reply_to, "name": reply_to}]

        headers = {
            "Authorization": self._auth_header(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            response = requests.post(
                self.API_URL,
                json=payload,
                headers=headers,
                timeout=15,
            )
        except Exception as e:
            print(f"[email:zeptomail] transport error: {e}")
            return False

        if response.status_code in (200, 201):
            print(f"[email:zeptomail] sent to {to_email}")
            return True

        print(
            f"[email:zeptomail] failed ({response.status_code}): {response.text[:500]}"
        )
        return False

    def healthcheck(self) -> bool:
        return bool(self.api_key and self.default_from_email)
