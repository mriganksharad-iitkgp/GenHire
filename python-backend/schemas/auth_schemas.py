"""Auth request schemas.

Typed parsing for register/login payloads. Validation intentionally delegates
to middleware/input_validator (the existing single source of truth for the
rules) and replicates the previous inline checks in the same order, so every
error body and status code is byte-identical to the hand-rolled version these
schemas replaced.

Fields are deliberately `Any`: the legacy code accepted arbitrary JSON types
and rejected them inside the validators (isinstance checks), so strict typing
here would change which error a malformed payload gets.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from middleware.input_validator import validate_email, validate_name, validate_password
from schemas.common import err


def _normalize_email(email):
    return str(email or '').strip().lower()


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    name: Any = None
    email: Any = None
    password: Any = None
    confirm_password: Any = Field(None, alias="confirmPassword")
    user_type: Any = Field("candidate", alias="userType")

    @property
    def normalized_email(self) -> str:
        return _normalize_email(self.email)

    @property
    def normalized_user_type(self) -> str:
        return str(self.user_type or 'candidate').strip().lower()

    def first_error(self):
        """The previous inline validation — same checks, same order.
        Returns an (error_dict, status) tuple or None."""
        if not all([self.name, self.normalized_email, self.password, self.confirm_password]):
            return err('All fields are required', 400)

        error = validate_name(self.name)
        if error:
            return err(error, 400)
        error = validate_email(self.normalized_email)
        if error:
            return err(error, 400)
        error = validate_password(self.password)
        if error:
            return err(error, 400)

        if self.password != self.confirm_password:
            return err('Passwords do not match', 400)

        # Only candidate and recruiter registration (admins created manually)
        if self.normalized_user_type not in ['candidate', 'recruiter']:
            return err('Invalid user type', 400)

        return None


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    identifier: Any = None
    email: Any = None
    username: Any = None
    password: Any = None
    user_type: Any = Field("candidate", alias="userType")

    @property
    def resolved_identifier(self):
        """Preferred `identifier`, falling back to legacy `email`/`username`."""
        return self.identifier or self.email or self.username

    @property
    def normalized_user_type(self) -> str:
        return str(self.user_type or 'candidate').strip().lower()
