"""Service layer for the candidate invite system.

Responsibilities:
  - Parse CSV/XLSX/manual/bulk-paste email lists from recruiter input.
  - Generate unique usernames and temporary passwords for burner accounts.
  - Hash and verify magic-link tokens (sha256 + INVITE_TOKEN_SECRET pepper).
  - Branch invite creation across new email / existing temp / regular candidate /
    non-candidate (recruiter or admin) cases.
  - Insert application skeletons (status='shortlisted' for interview invites).
  - Insert audit `invite_batches` documents.

The controller layer wraps the result dicts and dispatches the appropriate
EmailService.send_invite_* method per row.
"""

import csv
import datetime as _dt
import hashlib
import io
import os
import re
import secrets
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from werkzeug.security import generate_password_hash


_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_SPLIT_RE = re.compile(r"[\s,;]+")


def normalize_email(value: Any) -> str:
    return str(value or "").strip().lower()


def is_valid_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(value or ""))


def hash_invite_token(raw: str) -> str:
    secret = os.getenv("INVITE_TOKEN_SECRET", "")
    return hashlib.sha256((raw + secret).encode("utf-8")).hexdigest()


def generate_temp_password() -> str:
    return secrets.token_urlsafe(10)


def parse_emails_from_text(blob: str) -> List[str]:
    if not blob:
        return []
    parts = [p for p in _SPLIT_RE.split(blob) if p]
    seen = set()
    out = []
    for p in parts:
        e = normalize_email(p)
        if not e or e in seen:
            continue
        seen.add(e)
        out.append(e)
    return out


def _read_csv_emails(file_bytes: bytes) -> List[str]:
    text = file_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []
    header = [str(c).strip().lower() for c in rows[0]]
    if "email" in header:
        idx = header.index("email")
        return [str(r[idx]).strip() for r in rows[1:] if len(r) > idx and str(r[idx]).strip()]
    flat: List[str] = []
    for row in rows:
        for cell in row:
            cell = str(cell or "").strip()
            if cell and "@" in cell:
                flat.append(cell)
    return flat


def _read_xlsx_emails(file_bytes: bytes) -> List[str]:
    try:
        from openpyxl import load_workbook
    except ImportError as e:
        raise RuntimeError("openpyxl is required to parse XLSX uploads") from e

    wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.active
    if ws is None:
        return []

    rows = ws.iter_rows(values_only=True)
    try:
        first = next(rows)
    except StopIteration:
        return []

    header = [str(c).strip().lower() if c is not None else "" for c in first]
    if "email" in header:
        idx = header.index("email")
        out: List[str] = []
        for r in rows:
            if idx < len(r) and r[idx] is not None:
                cell = str(r[idx]).strip()
                if cell:
                    out.append(cell)
        return out

    flat: List[str] = []
    for cell in first:
        if cell and "@" in str(cell):
            flat.append(str(cell).strip())
    for r in rows:
        for cell in r:
            cell = "" if cell is None else str(cell).strip()
            if cell and "@" in cell:
                flat.append(cell)
    return flat


def parse_emails_from_file(filename: str, file_bytes: bytes) -> List[str]:
    """Return a list of raw email strings (not yet validated/normalized)."""
    name = (filename or "").lower()
    if name.endswith(".xlsx") or name.endswith(".xlsm"):
        return _read_xlsx_emails(file_bytes)
    return _read_csv_emails(file_bytes)


def classify_emails(raw_list: List[str]) -> Dict[str, List[str]]:
    """Split a raw list into valid/invalid/duplicate buckets, all normalized."""
    valid: List[str] = []
    invalid: List[str] = []
    duplicates: List[str] = []
    seen = set()
    for raw in raw_list:
        candidate = normalize_email(raw)
        if not candidate:
            continue
        if not is_valid_email(candidate):
            invalid.append(raw.strip() if isinstance(raw, str) else str(raw))
            continue
        if candidate in seen:
            duplicates.append(candidate)
            continue
        seen.add(candidate)
        valid.append(candidate)
    return {"valid": valid, "invalid": invalid, "duplicates": duplicates}


class InviteService:
    INVITE_ID_PREFIX = "inv_"
    APPLICATION_STATUS_INTERVIEW = "shortlisted"
    APPLICATION_STATUS_APPLY = "pending"

    def __init__(self, db_collections: Dict[str, Any]):
        self.users = db_collections["users"]
        self.applications = db_collections["applications"]
        self.jobs = db_collections["jobs"]
        invite_tokens = db_collections.get("invite_tokens")
        self.invite_tokens = (
            invite_tokens
            if invite_tokens is not None
            else db_collections["users"].database["invite_tokens"]
        )
        invite_batches = db_collections.get("invite_batches")
        self.invite_batches = (
            invite_batches
            if invite_batches is not None
            else db_collections["users"].database["invite_batches"]
        )

    # ----- helpers ---------------------------------------------------------

    def _ttl_minutes(self) -> int:
        try:
            return max(1, int(os.getenv("INVITE_MAGIC_LINK_TTL_MIN", "30")))
        except ValueError:
            return 30

    def _generate_unique_invite_id(self) -> str:
        for _ in range(8):
            candidate = f"{self.INVITE_ID_PREFIX}{secrets.token_urlsafe(6)}"
            cand_lower = candidate.lower()
            existing = self.users.find_one(
                {"invite_id_lower": cand_lower}, {"_id": 1}
            )
            if not existing:
                return candidate
        # Fall back to longer suffix if collisions are improbably persistent.
        return f"{self.INVITE_ID_PREFIX}{secrets.token_urlsafe(12)}"

    def _now(self) -> _dt.datetime:
        return _dt.datetime.utcnow()

    def _ensure_existing_application(
        self,
        *,
        user_id: ObjectId,
        user_doc: Dict[str, Any],
        job: Dict[str, Any],
        invite_type: str,
        batch_id: Optional[ObjectId],
    ) -> Tuple[ObjectId, bool]:
        """Find or create the application skeleton. Returns (app_id, was_created)."""
        student_id = str(user_id)
        job_id = str(job["_id"])
        existing = self.applications.find_one(
            {"job_id": job_id, "student_id": student_id}
        )
        if existing:
            return existing["_id"], False

        status = (
            self.APPLICATION_STATUS_INTERVIEW
            if invite_type == "interview"
            else self.APPLICATION_STATUS_APPLY
        )
        recruiter_raw = job.get("created_by")
        recruiter_id_str = str(recruiter_raw) if recruiter_raw else ""
        skeleton = {
            "job_id": job_id,
            "student_id": student_id,
            "student_name": user_doc.get("name", ""),
            "student_email": user_doc.get("email", ""),
            "cover_letter": "",
            "status": status,
            "status_reason": (
                "Pre-shortlisted via recruiter interview invite"
                if invite_type == "interview"
                else "Created via recruiter invite; awaiting candidate submission"
            ),
            "applied_at": self._now(),
            "updated_at": self._now(),
            "job_title": job.get("title", ""),
            "recruiter_id": recruiter_id_str,
            "cv_score": None,
            "cv_score_breakdown": None,
            "minimum_cv_score_required": job.get("minimum_cv_score", 50.0),
            "interview_score": None,
            "student_profile": {},
            "cv_id": None,
            "cv_snapshot": None,
            "jd_snapshot": None,
            "cv_source": None,
            "processing_status": "awaiting_candidate",
            "is_visible": invite_type == "interview",
            "cv_score_calculated_at": None,
            "processing_error": None,
            "auto_processed": True,
            # Invite-system flags
            "invite_type": invite_type,
            "invite_batch_id": str(batch_id) if batch_id else None,
            "auto_shortlisted_via_invite": invite_type == "interview",
        }
        result = self.applications.insert_one(skeleton)

        # NOTE: We deliberately do NOT bump the job's `applicants` counter here.
        # The counter reflects candidate-submitted applications. The bump happens
        # in application_controller.apply_for_job when the candidate actually
        # submits (whether via fresh insert or in-place skeleton update).

        return result.inserted_id, True

    def _insert_invite_token(
        self,
        *,
        user_id: ObjectId,
        application_id: ObjectId,
        job_id: str,
        invite_type: str,
        recruiter_id: str,
        batch_id: Optional[ObjectId],
    ) -> Tuple[str, ObjectId]:
        ttl = self._ttl_minutes()
        raw = secrets.token_urlsafe(32)
        token_hash = hash_invite_token(raw)
        now = self._now()
        doc = {
            "token_hash": token_hash,
            "user_id": user_id,
            "application_id": application_id,
            "job_id": job_id,
            "invite_type": invite_type,
            "recruiter_id": recruiter_id,
            "batch_id": batch_id,
            "created_at": now,
            "expires_at": now + _dt.timedelta(minutes=ttl),
            "consumed_at": None,
        }
        result = self.invite_tokens.insert_one(doc)
        return raw, result.inserted_id

    # ----- single-row branching -------------------------------------------

    def _find_real_account_for_email(self, normalized_email: str) -> Optional[Dict[str, Any]]:
        """Return a non-invite-only user matching this email (regular candidate,
        recruiter, or admin), or None. Invite-only burner accounts are ignored
        so multiple Invite IDs can coexist for the same email."""
        return self.users.find_one(
            {
                "$and": [
                    {"$or": [{"email_lower": normalized_email}, {"email": normalized_email}]},
                    {"is_invite_only": {"$ne": True}},
                ]
            }
        )

    def _find_burner_account_invited_to_job(
        self, normalized_email: str, job_id_str: str
    ) -> Optional[Dict[str, Any]]:
        """
        Return an existing burner (invite-only) account for this email that
        was already invited to this exact job, or None.

        Without this check, re-uploading the same candidate list for the same
        job (an accidental double-submit, or a deliberate re-send) would mint
        an entirely new burner account + invite_id + temp password + "you're
        invited" email every single time, since burner accounts are otherwise
        allowed to multiply per email by design (see _find_real_account_for_email).
        This scopes that dedup to (email, job) so an email can still receive
        separate burner invites across *different* jobs.
        """
        return self.users.find_one(
            {
                "$or": [{"email_lower": normalized_email}, {"email": normalized_email}],
                "is_invite_only": True,
                "invited_job_ids": job_id_str,
            }
        )

    def create_or_refresh_invite(
        self,
        *,
        recruiter: Dict[str, Any],
        job: Dict[str, Any],
        email: str,
        invite_type: str,
        batch_id: Optional[ObjectId],
    ) -> Dict[str, Any]:
        """Process a single email row. Returns a dict the controller uses
        to drive the email-send step.

        Behavior:
          - If the email belongs to a real (non-invite) recruiter/admin → skip.
          - If the email belongs to a real candidate → silent attach (no temp).
          - Otherwise → always mint a fresh burner temp account with its own
            unique invite_id. An email may hold any number of invite IDs.
        """
        recruiter_company = recruiter.get("company_name") or "GenHire"
        job_id_str = str(job["_id"])
        recruiter_id_str = str(recruiter.get("_id"))
        normalized = normalize_email(email)

        result: Dict[str, Any] = {
            "email": normalized,
            "action": "skipped",
            "reason": None,
            "invite_id": None,
            "temp_password": None,
            "raw_token": None,
            "application_id": None,
            "recruiter_company": recruiter_company,
            "job_id": job_id_str,
            "invite_type": invite_type,
        }

        if not is_valid_email(normalized):
            result["reason"] = "invalid_email"
            return result

        real_account = self._find_real_account_for_email(normalized)

        if real_account is not None:
            user_type = str(real_account.get("user_type", "candidate")).lower()
            if user_type != "candidate":
                # Recruiter or admin email → skip silently.
                result["reason"] = "non_candidate_account"
                return result

            # Real candidate → silent attach, no token, no password change.
            user_id = real_account["_id"]
            self.users.update_one(
                {"_id": user_id},
                {
                    "$addToSet": {"invited_by_recruiter_ids": recruiter_id_str},
                    "$set": {"updated_at": self._now()},
                },
            )
            app_id, _ = self._ensure_existing_application(
                user_id=user_id,
                user_doc=real_account,
                job=job,
                invite_type=invite_type,
                batch_id=batch_id,
            )
            result.update(
                action="attached_to_existing_account",
                application_id=str(app_id),
            )
            return result

        # An email may already have been invited to this exact job before via
        # a burner account (re-uploaded list, accidental double-submit, or a
        # deliberate re-send) — reuse that account/application instead of
        # minting a duplicate one with a brand new password.
        existing_burner = self._find_burner_account_invited_to_job(normalized, job_id_str)
        if existing_burner is not None:
            user_id = existing_burner["_id"]
            app_id, _ = self._ensure_existing_application(
                user_id=user_id,
                user_doc=existing_burner,
                job=job,
                invite_type=invite_type,
                batch_id=batch_id,
            )
            result.update(
                action="attached_to_existing_account",
                application_id=str(app_id),
            )
            return result

        # No real or previously-invited-to-this-job account exists — mint a
        # fresh burner account with its own invite_id. Each invite gets its
        # own ID, so an email may have many across *different* jobs.
        invite_id = self._generate_unique_invite_id()
        temp_password = generate_temp_password()
        now = self._now()
        user_doc = {
            "name": "",
            "email": normalized,
            "email_lower": normalized,
            "invite_id": invite_id,
            "invite_id_lower": invite_id.lower(),
            "password": generate_password_hash(temp_password),
            "user_type": "candidate",
            "email_verified": True,
            "is_verified": True,
            "verified_by": None,
            "verified_at": now,
            "permissions": [],
            "auth_provider": "invite",
            "created_via": "invite",
            "is_invite_only": True,
            "invite_first_login_required": True,
            "invited_job_ids": [job_id_str],
            "invited_by_recruiter_ids": [recruiter_id_str],
            "temp_password_set_at": now,
            "last_redeemed_at": None,
            "created_at": now,
            "updated_at": now,
        }
        try:
            user_id = self.users.insert_one(user_doc).inserted_id
        except DuplicateKeyError as e:
            # Surface the actual key/index that collided so future debugging
            # doesn't have to guess (was previously masked as 'invite_id_collision').
            details = (
                e.details if hasattr(e, "details") and isinstance(getattr(e, "details", None), dict) else {}
            )
            key_name = details.get("keyPattern") or str(details) or str(e)
            result["reason"] = f"duplicate_key: {key_name}"
            return result

        user_doc["_id"] = user_id
        app_id, _ = self._ensure_existing_application(
            user_id=user_id,
            user_doc=user_doc,
            job=job,
            invite_type=invite_type,
            batch_id=batch_id,
        )
        raw_token, _ = self._insert_invite_token(
            user_id=user_id,
            application_id=app_id,
            job_id=job_id_str,
            invite_type=invite_type,
            recruiter_id=recruiter_id_str,
            batch_id=batch_id,
        )
        result.update(
            action="created",
            invite_id=invite_id,
            temp_password=temp_password,
            raw_token=raw_token,
            application_id=str(app_id),
        )
        return result

    # ----- bulk -----------------------------------------------------------

    def bulk_invite(
        self,
        *,
        recruiter: Dict[str, Any],
        job: Dict[str, Any],
        emails: List[str],
        invite_type: str,
        source: str = "manual",
    ) -> Tuple[ObjectId, List[Dict[str, Any]]]:
        """Process a batch and return (batch_id, per-row results).

        The caller is responsible for iterating the results and dispatching the
        right EmailService method per row, then patching the batch summary with
        the email-send outcomes.
        """
        if invite_type not in ("apply", "interview"):
            raise ValueError("invite_type must be 'apply' or 'interview'")

        now = self._now()
        batch_doc = {
            "recruiter_id": str(recruiter.get("_id")),
            "job_id": str(job["_id"]),
            "invite_type": invite_type,
            "source": source,
            "total": len(emails),
            "sent_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "failures": [],
            "status": "processing",
            "created_at": now,
        }
        batch_id = self.invite_batches.insert_one(batch_doc).inserted_id

        results: List[Dict[str, Any]] = []
        for email in emails:
            try:
                row = self.create_or_refresh_invite(
                    recruiter=recruiter,
                    job=job,
                    email=email,
                    invite_type=invite_type,
                    batch_id=batch_id,
                )
            except Exception as e:
                row = {
                    "email": normalize_email(email),
                    "action": "failed",
                    "reason": f"server_error: {e}",
                    "raw_token": None,
                    "username": None,
                    "temp_password": None,
                    "application_id": None,
                    "recruiter_company": recruiter.get("company_name") or "GenHire",
                    "job_id": str(job["_id"]),
                    "invite_type": invite_type,
                }
            results.append(row)
        return batch_id, results

    def finalize_batch(
        self,
        *,
        batch_id: ObjectId,
        sent_count: int,
        skipped_count: int,
        failed_count: int,
        failures: List[Dict[str, str]],
        skipped: Optional[List[Dict[str, str]]] = None,
        status: str = "completed",
    ) -> None:
        """
        Updates the batch's running counts/detail rows. Despite the name,
        this is called repeatedly during background dispatch
        (status="processing") as well as once at the very end
        (status="completed") — it's a plain counter write, safe to call as
        often as needed for progress polling.
        """
        update = {
            "sent_count": sent_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
            "failures": failures,
            "status": status,
        }
        if skipped is not None:
            update["skipped"] = skipped
        self.invite_batches.update_one({"_id": batch_id}, {"$set": update})

    # ----- redemption -----------------------------------------------------

    def lookup_token(self, raw_token: str) -> Optional[Dict[str, Any]]:
        if not raw_token:
            return None
        token_hash = hash_invite_token(raw_token)
        token_doc = self.invite_tokens.find_one({"token_hash": token_hash})
        if not token_doc:
            return None
        if token_doc.get("consumed_at"):
            return None
        if token_doc.get("expires_at") and token_doc["expires_at"] < self._now():
            return None
        user = self.users.find_one({"_id": token_doc["user_id"]})
        if not user:
            return None
        try:
            job = self.jobs.find_one({"_id": ObjectId(token_doc["job_id"])})
        except Exception:
            job = None
        return {"token": token_doc, "user": user, "job": job}

    def consume_token(
        self,
        *,
        raw_token: str,
    ) -> Optional[Dict[str, Any]]:
        """Mark token consumed and stamp last_redeemed_at on the user.
        The user's password is NOT changed: the temp password we emailed
        them remains the account password.

        Returns None if the token is invalid/expired/consumed (caller renders 410).
        """
        ctx = self.lookup_token(raw_token)
        if not ctx:
            return None

        token_doc = ctx["token"]
        user = ctx["user"]
        now = self._now()

        # Consume token first; if another tab raced us we'll lose the update and bail.
        consumed = self.invite_tokens.update_one(
            {"_id": token_doc["_id"], "consumed_at": None},
            {"$set": {"consumed_at": now}},
        )
        if consumed.modified_count == 0:
            return None

        self.users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "invite_first_login_required": False,
                    "last_redeemed_at": now,
                    "updated_at": now,
                }
            },
        )
        user = self.users.find_one({"_id": user["_id"]})
        ctx["user"] = user
        return ctx
