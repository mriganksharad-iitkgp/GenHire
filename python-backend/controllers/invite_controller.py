"""Flask-facing controller wrapping InviteService.

Glues HTTP requests to:
  - parsing/dedupe of recruiter-supplied email lists,
  - per-row branching via InviteService.create_or_refresh_invite,
  - dispatch to the appropriate EmailService.send_invite_* method,
  - magic-link redeem (lookup + consume).
"""

import datetime
import os
from typing import Any, Dict, List, Optional

import jwt as pyjwt
from bson import ObjectId

from services.email_service import EmailService
from services.invite_service import (
    InviteService,
    classify_emails,
    parse_emails_from_file,
    parse_emails_from_text,
)


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

        ttl_minutes = self.invite_service._ttl_minutes()

        batch_id, rows = self.invite_service.bulk_invite(
            recruiter=recruiter,
            job=job,
            emails=valid_emails,
            invite_type=invite_type,
            source=source,
        )

        sent: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []
        failed: List[Dict[str, Any]] = []
        recruiter_company = recruiter.get("company_name") or "GenHire"
        job_title = job.get("title", "")

        for row in rows:
            action = row["action"]
            if action == "skipped":
                skipped.append({"email": row["email"], "reason": row["reason"]})
                continue
            if action == "failed":
                failed.append({"email": row["email"], "error": row["reason"]})
                continue

            email_ok = False
            try:
                if action == "created":
                    if invite_type == "interview":
                        email_ok = self.email_service.send_invite_interview_email(
                            to_email=row["email"],
                            recruiter_company=recruiter_company,
                            job_title=job_title,
                            invite_id=row["invite_id"],
                            temp_password=row["temp_password"],
                            raw_token=row["raw_token"],
                            ttl_minutes=ttl_minutes,
                        )
                    else:
                        email_ok = self.email_service.send_invite_apply_email(
                            to_email=row["email"],
                            recruiter_company=recruiter_company,
                            job_title=job_title,
                            invite_id=row["invite_id"],
                            temp_password=row["temp_password"],
                            raw_token=row["raw_token"],
                            ttl_minutes=ttl_minutes,
                        )
                elif action == "attached_to_existing_account":
                    email_ok = self.email_service.send_existing_user_invite_email(
                        to_email=row["email"],
                        recruiter_company=recruiter_company,
                        job_title=job_title,
                        job_id=str(job["_id"]),
                        invite_type=invite_type,
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
                failed.append(
                    {"email": row["email"], "error": row.get("reason") or "email_send_failed"}
                )

        self.invite_service.finalize_batch(
            batch_id=batch_id,
            sent_count=len(sent),
            skipped_count=len(skipped),
            failed_count=len(failed),
            failures=failed,
        )

        return {
            "batch_id": str(batch_id),
            "sent": sent,
            "skipped": skipped,
            "failed": failed,
            "totals": {
                "sent": len(sent),
                "skipped": len(skipped),
                "failed": len(failed),
            },
        }, 201

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

        secret_key = os.getenv("JWT_SECRET_KEY", "your-secret-key-here")
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
