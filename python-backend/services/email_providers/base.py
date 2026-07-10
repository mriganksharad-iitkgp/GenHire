from abc import ABC, abstractmethod
from typing import Optional


class EmailProvider(ABC):
    """Provider-agnostic interface for transactional email sending.

    Implementations should swallow transport errors and return False rather
    than raise, matching the contract used by callers in EmailService.
    """

    name: str = "base"

    # Human-readable reason for the most recent failed send (provider response
    # body / transport error). Cleared on success. Callers surface this to the
    # recruiter instead of a generic "email_send_failed".
    last_error: Optional[str] = None

    @abstractmethod
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
        ...

    def healthcheck(self) -> bool:
        return True
