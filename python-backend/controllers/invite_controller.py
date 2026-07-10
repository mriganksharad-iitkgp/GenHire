"""Flask-facing controller wrapping InviteService.

Glues HTTP requests to:
  - parsing/dedupe of recruiter-supplied email lists,
  - per-row branching via InviteService.create_or_refresh_invite,
  - dispatch to the appropriate EmailService.send_invite_* method,
  - magic-link redeem (lookup + consume).
"""

import datetime
import logging
import os
import threading
from typing import Any, Dict, List, Optional

import jwt as pyjwt
from bson import ObjectId

from core.security import get_jwt_secret
from services.email_service import EmailService
from services.invite_service import (
    InviteService,
    classify_emails,
    parse_emails_from_file,
    parse_emails_from_text,
)

logger = logging.getLogger(__name__)


class InviteController:
    def __init__(self, db_collections: Dict[str, Any]):
        self.users = db_collections["users"]
        self.jobs = db_collections["jobs"]
        self.applications = db_collections["applications"]
        self.invite_service = InviteService(db_collections)
        self.email_service = EmailService()

    # ----- recruiter-facing -----------------------------------------------

    def preview_emails(
        self,
        *,
        file_storage=None,
        text_blob: Optional[str] = None,
        single_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        raw: List[str] = []
        if file_storage is not None and getattr(file_storage, "filename", ""):
            file_bytes = file_storage.read()
            raw.extend(parse_emails_from_file(file_storage.filename, file_bytes))
        if text_blob:
            raw.extend(parse_emails_from_text(text_blob))
        if single_email:
            raw.append(single_email)

        buckets = classify_emails(raw)
        return {
            "valid": buckets["valid"],
            "invalid": buckets["invalid"],
            "duplicates": buckets["duplicates"],
            "total": len(buckets["valid"]) + len(buckets["invalid"]) + len(buckets["duplicates"]),
        }

    def send_invites(
        self,
        *,
        recruiter: Dict[str, Any],
        job_id: str,
        emails: List[str],
        invite_type: str,
        source: str = "manual",
        validity_days: Optional[int] = None,
    ):
        if invite_type not in ("apply", "interview"):
            return {"error": "invite_type must be 'apply' or 'interview'"}, 400
        if not emails:
            return {"error": "No emails provided"}, 400

        try:
            job = self.jobs.find_one({"_id": ObjectId(job_id)})
        except Exception:
            return {"error": "Invalid job id"}, 400
        if not job:
            return {"error": "Job not found"}, 404

        # Authorization: only the job's recruiter (or admin) can invite for it.
        recruiter_id = str(recruiter.get("_id"))
        if recruiter.get("user_type") == "recruiter" and str(job.get("created_by")) != recruiter_id:
            return {"error": "You can only invite candidates to jobs you posted"}, 403

        # Normalize and de-dupe upfront.
        buckets = classify_emails(emails)
        valid_emails = buckets["valid"]
        if not valid_emails:
            return {
                "error": "No valid emails to invite",
                "invalid": buckets["invalid"],
                "duplicates": buckets["duplicates"],
            }, 400

        # The DB-row half (bulk_invite) is plain Mongo writes — fast even at
        # 2000 rows — so it stays synchronous. Only the email-sending half
        # (one blocking provider call per row) moves to a background thread;
        # otherwise a 2000-row batch would hold this request open for as long
        # as it takes to send 2000 emails, well past any reasonable timeout.
        batch_id, rows = self.invite_service.bulk_invite(
            recruiter=recruiter,
            job=job,
            emails=valid_emails,
            invite_type=invite_type,
            source=source,
            validity_days=validity_days,
        )

        recruiter_company = recruiter.get("company_name") or "GenHire"
        job_title = job.get("title", "")

        # Rows already resolved during the DB phase (no email to send) —
        # reflect them immediately so a poller sees an accurate total right away.
        pre_skipped = [
            {"email": r["email"], "reason": r["reason"]}
            for r in rows
            if r["action"] == "skipped"
        ]
        pre_failed = [
            {"email": r["email"], "error": r["reason"]}
            for r in rows
            if r["action"] == "failed"
        ]
        rows_to_email = [r for r in rows if r["action"] not in ("skipped", "failed")]

        self.invite_service.finalize_batch(
            batch_id=batch_id,
            sent_count=0,
            skipped_count=len(pre_skipped),
            failed_count=len(pre_failed),
            failures=pre_failed,
            skipped=pre_skipped,
            status="processing",
        )

        threading.Thread(
            target=self._dispatch_invite_emails,
            args=(batch_id, rows_to_email, recruiter_company, job_title, pre_skipped, pre_failed),
            daemon=True,
        ).start()

        return {
            "batch_id": str(batch_id),
            "status": "processing",
            "total": len(rows),
            "message": "Invites are being sent in the background — poll the batch status endpoint for progress.",
        }, 202

    def _dispatch_invite_emails(
        self,
        batch_id,
        rows: List[Dict[str, Any]],
        recruiter_company: str,
        job_title: str,
        pre_skipped: List[Dict[str, Any]],
        pre_failed: List[Dict[str, Any]],
    ) -> None:
        """
        Runs on a background thread — sends one invite email per row and
        updates the `invite_batches` document after every row so a recruiter
        polling the batch status endpoint sees live progress, not just a
        final result once everything is done.
        """
        sent: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = list(pre_skipped)
        failed: List[Dict[str, Any]] = list(pre_failed)

        for row in rows:
            action = row["action"]
            invite_type = row["invite_type"]
            email_ok = False
            try:
                # "created" and "refreshed" both carry full fresh credentials
                # (new burner vs re-invite of the same email+job) — the invitee
                # gets the same credentials email either way.
                if action in ("created", "refreshed"):
                    send_fn = (
                        self.email_service.send_invite_interview_email
                        if invite_type == "interview"
                        else self.email_service.send_invite_apply_email
                    )
                    email_ok = send_fn(
                        to_email=row["email"],
                        recruiter_company=recruiter_company,
                        job_title=job_title,
                        invite_id=row["invite_id"],
                        temp_password=row["temp_password"],
                        raw_token=row["raw_token"],
                        valid_until=row.get("valid_until"),
                        validity_days=row.get("validity_days"),
                    )
            except Exception as e:
                email_ok = False
                row["reason"] = f"email_send_error: {e}"

            if email_ok:
                sent.append(
                    {
                        "email": row["email"],
                        "action": action,
                        "invite_id": row.get("invite_id"),
                    }
                )
            else:
                # Surface the real provider error instead of a generic marker,
                # and keep the magic link so the recruiter can share it
                # manually — a failed email must never strand a created burner.
                failure = {
                    "email": row["email"],
                    "error": (
                        row.get("reason")
                        or self.email_service.last_error()
                        or "email_send_failed"
                    ),
                }
                if row.get("raw_token"):
                    failure["invite_url"] = self.email_service.invite_redeem_link(
                        row["raw_token"]
                    )
                failed.append(failure)

            try:
                self.invite_service.finalize_batch(
                    batch_id=batch_id,
                    sent_count=len(sent),
                    skipped_count=len(skipped),
                    failed_count=len(failed),
                    failures=failed,
                    skipped=skipped,
                    status="processing",
                )
            except Exception:
                logger.warning("Failed to update invite batch progress", exc_info=True)

        try:
            self.invite_service.finalize_batch(
                batch_id=batch_id,
                sent_count=len(sent),
                skipped_count=len(skipped),
                failed_count=len(failed),
                failures=failed,
                skipped=skipped,
                status="completed",
            )
        except Exception:
            logger.warning("Failed to finalize invite batch", exc_info=True)

    def get_batch_status(self, *, recruiter: Dict[str, Any], batch_id: str):
        """Poll-friendly status for a bulk invite batch (used by the frontend
        progress UI instead of waiting for one long final response)."""
        try:
            batch = self.invite_service.invite_batches.find_one({"_id": ObjectId(batch_id)})
        except Exception:
            return {"error": "Invalid batch id"}, 400
        if not batch:
            return {"error": "Batch not found"}, 404

        recruiter_id = str(recruiter.get("_id"))
        if recruiter.get("user_type") == "recruiter" and str(batch.get("recruiter_id")) != recruiter_id:
            return {"error": "Unauthorized"}, 403

        return {
            "batch_id": str(batch["_id"]),
            "status": batch.get("status", "processing"),
            "total": batch.get("total", 0),
            "totals": {
                "sent": batch.get("sent_count", 0),
                "skipped": batch.get("skipped_count", 0),
                "failed": batch.get("failed_count", 0),
            },
            # Kept as two separate lists (rather than one merged "failures")
            # to match the shape the frontend's send-summary detail view
            # already renders (skipped reasons vs. failed errors).
            "skipped": batch.get("skipped", []),
            "failed": batch.get("failures", []),
        }, 200

    # ----- public redeem flow ---------------------------------------------

    def lookup_invite(self, raw_token: str):
        ctx = self.invite_service.lookup_token(raw_token)
        if not ctx:
            return {"error": "This invite link is invalid or has expired."}, 410

        token = ctx["token"]
        user = ctx["user"]
        job = ctx["job"] or {}
        recruiter = self.users.find_one(
            {"_id": ObjectId(token["recruiter_id"])} if token.get("recruiter_id") else None
        ) if token.get("recruiter_id") else None

        return {
            "user": {
                "id": str(user["_id"]),
                "name": user.get("name") or "",
                "email": user.get("email"),
                "invite_id": user.get("invite_id") or user.get("username"),
            },
            "job": {
                "id": str(job.get("_id")) if job.get("_id") else token.get("job_id"),
                "title": job.get("title", ""),
                "company": job.get("company") or (recruiter.get("company_name") if recruiter else ""),
                "location": job.get("location", ""),
            },
            "invite_type": token.get("invite_type"),
            "expires_at": token.get("expires_at").isoformat() if token.get("expires_at") else None,
        }, 200

    def redeem_invite(self, raw_token: str):
        """Consume the magic-link token and auto-log the candidate in.
        No password reset is required: the temp password from the invite email
        remains the account's password and stays valid for /login afterward."""
        if not raw_token:
            return {"error": "Token is required"}, 400

        ctx = self.invite_service.consume_token(raw_token=raw_token)
        if not ctx:
            return {"error": "This invite link is invalid, expired, or has already been used."}, 410

        user = ctx["user"]
        token_doc = ctx["token"]
        job_id = token_doc.get("job_id")

        # Mint a handoff JWT with TTL = INVITE_SCOPED_JWT_TTL_HOURS so a stale link
        # can't grant indefinite access. After this, the user logs in with their
        # new password as usual.
        try:
            ttl_hours = max(1, int(os.getenv("INVITE_SCOPED_JWT_TTL_HOURS", "4")))
        except ValueError:
            ttl_hours = 4

        secret_key = get_jwt_secret()
        jwt_token = pyjwt.encode(
            {
                "user_id": str(user["_id"]),
                "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=ttl_hours),
            },
            secret_key,
            algorithm="HS256",
        )

        return {
            "message": "Password set successfully",
            "token": jwt_token,
            "redirect": f"/job/{job_id}" if job_id else "/dashboard",
            "user": {
                "id": str(user["_id"]),
                "name": user.get("name") or "",
                "email": user.get("email"),
                "invite_id": user.get("invite_id") or user.get("username"),
                "user_type": user.get("user_type", "candidate"),
                "is_invite_only": bool(user.get("is_invite_only")),
                "invited_job_ids": [str(j) for j in (user.get("invited_job_ids") or [])],
                "email_verified": True,
                "is_verified": user.get("is_verified", True),
                "permissions": user.get("permissions", []),
            },
        }, 200
