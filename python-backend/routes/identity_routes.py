"""Candidate identity-card routes.

POST is one-time: once a card exists on the account the candidate gets a 409
and must contact an admin (the admin panel has replace/reset endpoints under
/api/admin/candidates/<id>/identity-card).
"""

import logging

from flask import Blueprint, Response, jsonify, request

from config.database import db_config
from middleware.auth_middleware import candidate_required, token_required
from services import identity_card_service

logger = logging.getLogger(__name__)

identity_bp = Blueprint("identity", __name__, url_prefix="/api")


@identity_bp.route("/identity-card", methods=["GET"])
@token_required
def get_identity_card_status(current_user):
    """The current user's identity-card status (used by the pre-interview gate)."""
    return jsonify(identity_card_service.public_status(current_user_doc(current_user))), 200


@identity_bp.route("/identity-card", methods=["POST"])
@token_required
@candidate_required
def upload_identity_card(current_user):
    """One-time identity-card upload for the logged-in candidate."""
    users = db_config.get_collections()["users"]

    existing = users.find_one({"_id": current_user["_id"]}, {"identity_card": 1}) or {}
    if (existing.get("identity_card") or {}).get("image_file_id"):
        return (
            jsonify(
                {
                    "error": "An identity card is already on file. Contact an administrator to change it.",
                    "error_code": "identity_card_locked",
                }
            ),
            409,
        )

    file = request.files.get("identity_card")
    if file is None or not file.filename:
        return jsonify({"error": "No identity card file provided", "error_code": "invalid_file"}), 400

    image_bytes = file.read()
    content_type = (file.mimetype or "").lower()
    error = identity_card_service.validate_upload(image_bytes, content_type)
    if error:
        return jsonify({"error": error, "error_code": "invalid_file"}), 400

    db = db_config.get_db()
    file_id = identity_card_service.store_identity_card(
        db,
        image_bytes,
        user_id=current_user["_id"],
        content_type=content_type,
        original_filename=file.filename,
        uploaded_by="candidate",
    )
    card = identity_card_service.build_card_record(
        file_id,
        content_type=content_type,
        original_filename=file.filename,
        uploaded_by="candidate",
    )
    users.update_one({"_id": current_user["_id"]}, {"$set": {"identity_card": card}})
    logger.info("Identity card uploaded for user %s", current_user["_id"])

    return (
        jsonify(
            {
                "message": "Identity card uploaded. It can now only be changed by an administrator.",
                "status": identity_card_service.public_status({"identity_card": card}),
            }
        ),
        201,
    )


@identity_bp.route("/identity-card/image", methods=["GET"])
@token_required
def view_identity_card(current_user):
    """Stream the current user's own identity-card image."""
    card = current_user_doc(current_user).get("identity_card") or {}
    file_id = card.get("image_file_id")
    if not file_id:
        return jsonify({"error": "No identity card on file", "error_code": "not_found"}), 404
    try:
        image_bytes, content_type = identity_card_service.load_identity_card(
            db_config.get_db(), file_id
        )
    except Exception:
        return jsonify({"error": "Identity card image unavailable", "error_code": "not_found"}), 404
    return Response(
        image_bytes,
        mimetype=content_type,
        headers={"Cache-Control": "private, max-age=300"},
    )


def current_user_doc(current_user):
    """Re-read the user with the identity_card field (the auth projection
    used by token_required does not include it)."""
    users = db_config.get_collections()["users"]
    return users.find_one({"_id": current_user["_id"]}, {"identity_card": 1}) or {}
