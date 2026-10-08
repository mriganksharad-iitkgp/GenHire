"""HTTP routes for the candidate invite system.

Recruiter-facing (auth required):
  POST /api/recruiter/jobs/<job_id>/invites/preview  - parse + classify a list
  POST /api/recruiter/jobs/<job_id>/invites          - send invites
  GET  /api/recruiter/jobs/<job_id>/invites          - list already-invited candidates

Public (no auth):
  GET  /api/invite/redeem?token=<raw>                - lookup an invite token
  POST /api/invite/redeem                            - consume token + set password
"""

from flask import Blueprint, jsonify, request
from flask_cors import cross_origin

from config.database import db_config
from controllers.invite_controller import InviteController
from middleware.auth_middleware import (
    recruiter_required,
    token_required,
    verified_required,
)
from middleware.rate_limiter import rate_limit


invite_bp = Blueprint("invites", __name__, url_prefix="/api")

_collections = db_config.get_collections()
_invite_controller = InviteController(_collections)


@invite_bp.route("/recruiter/jobs/<job_id>/invites/preview", methods=["POST"])
@cross_origin()
@token_required
@recruiter_required
@verified_required
def preview_invites(current_user, job_id):
    file_storage = request.files.get("file")
    text_blob = request.form.get("text") or request.form.get("bulk")
    single_email = request.form.get("email")

    # Allow JSON-only requests too (no file upload).
    if file_storage is None and text_blob is None and single_email is None and request.is_json:
        body = request.get_json(silent=True) or {}
        text_blob = body.get("text") or body.get("bulk")
        single_email = body.get("email")
        emails_list = body.get("emails")
        if isinstance(emails_list, list):
            text_blob = (text_blob or "") + "\n" + "\n".join(str(e) for e in emails_list)

    result = _invite_controller.preview_emails(
        file_storage=file_storage,
        text_blob=text_blob,
        single_email=single_email,
    )
    return jsonify(result), 200


@invite_bp.route("/recruiter/jobs/<job_id>/invites", methods=["POST"])
@cross_origin()
@token_required
@recruiter_required
@verified_required
def send_invites(current_user, job_id):
    body = request.get_json(silent=True) or {}
    emails = body.get("emails") or []
    invite_type = (body.get("invite_type") or "apply").strip().lower()
    source = (body.get("source") or "manual").strip().lower()
    validity_days = body.get("validity_days")

    if not isinstance(emails, list):
        return jsonify({"error": "emails must be a list"}), 400

    response, status_code = _invite_controller.send_invites(
        recruiter=current_user,
        job_id=job_id,
        emails=emails,
        invite_type=invite_type,
        source=source,
        validity_days=validity_days,
    )
    result = jsonify(response)
    if response.get("retry_after"):
        result.headers["Retry-After"] = str(response["retry_after"])
    return result, status_code


@invite_bp.route("/recruiter/jobs/<job_id>/invites", methods=["GET"])
@cross_origin()
@token_required
@recruiter_required
@verified_required
def list_invited_candidates(current_user, job_id):
    """All candidates ever invited to this job — shown in the invite modal so
    the recruiter knows who already holds an invite before sending more."""
    response, status_code = _invite_controller.list_invited_candidates(
        recruiter=current_user,
        job_id=job_id,
    )
    return jsonify(response), status_code


@invite_bp.route("/recruiter/jobs/<job_id>/invites/batches/<batch_id>", methods=["GET"])
@cross_origin()
@token_required
@recruiter_required
@verified_required
def get_invite_batch_status(current_user, job_id, batch_id):
    """Poll-friendly progress endpoint for a bulk invite batch started via
    send_invites — that route now returns immediately once emails start
    sending in the background instead of waiting for all of them."""
    response, status_code = _invite_controller.get_batch_status(
        recruiter=current_user,
        batch_id=batch_id,
    )
    return jsonify(response), status_code


@invite_bp.route("/invite/redeem", methods=["GET"])
@cross_origin()
@rate_limit(max_calls=20, window_seconds=3600)
def lookup_invite_route():
    raw_token = request.args.get("token", "")
    response, status_code = _invite_controller.lookup_invite(raw_token)
    return jsonify(response), status_code


@invite_bp.route("/invite/redeem", methods=["POST"])
@cross_origin()
@rate_limit(max_calls=20, window_seconds=3600)
def redeem_invite_route():
    body = request.get_json(silent=True) or {}
    raw_token = body.get("token", "")
    response, status_code = _invite_controller.redeem_invite(raw_token)
    return jsonify(response), status_code
