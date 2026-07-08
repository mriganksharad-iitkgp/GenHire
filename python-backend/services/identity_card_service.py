"""Identity-card storage and access.

The candidate uploads a government/institutional ID photo ONCE; it becomes the
reference image the interview-start face verification matches against (see
services/face_match_service.py). Candidates cannot replace it themselves —
only the admin panel can replace or reset it.

Files live in GridFS (same store as face captures); the user document carries
the pointer under `identity_card`:

    identity_card: {
        image_file_id: <gridfs id str>,
        content_type, original_filename,
        uploaded_at, uploaded_by: 'candidate' | 'admin:<admin_id>',
    }
"""

import datetime

import gridfs
from bson import ObjectId

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
MAX_BYTES = 5 * 1024 * 1024  # 5 MB


def validate_upload(image_bytes, content_type):
    """Return an error string or None."""
    if not image_bytes:
        return "No image data received"
    if len(image_bytes) > MAX_BYTES:
        return "Identity card image must be 5 MB or smaller"
    if content_type and content_type.lower() not in ALLOWED_CONTENT_TYPES:
        return "Identity card must be a JPEG, PNG, or WebP image"
    return None


def store_identity_card(db, image_bytes, *, user_id, content_type, original_filename, uploaded_by):
    """Persist the ID image in GridFS; returns the file id as a string."""
    fs = gridfs.GridFS(db)
    file_id = fs.put(
        image_bytes,
        filename=f"identity_card_{user_id}",
        content_type=content_type or "image/jpeg",
        metadata={
            "user_id": str(user_id),
            "purpose": "identity_card",
            "original_filename": original_filename or "",
            "uploaded_by": uploaded_by,
            "uploaded_at": datetime.datetime.utcnow().isoformat(),
        },
    )
    return str(file_id)


def load_identity_card(db, file_id):
    """Fetch stored ID image bytes; returns (bytes, content_type)."""
    fs = gridfs.GridFS(db)
    grid_out = fs.get(ObjectId(str(file_id)))
    return grid_out.read(), (grid_out.content_type or "image/jpeg")


def delete_identity_card_file(db, file_id):
    """Best-effort removal of a replaced/reset card's file."""
    try:
        fs = gridfs.GridFS(db)
        fs.delete(ObjectId(str(file_id)))
    except Exception:
        pass


def build_card_record(file_id, *, content_type, original_filename, uploaded_by):
    return {
        "image_file_id": file_id,
        "content_type": content_type or "image/jpeg",
        "original_filename": original_filename or "",
        "uploaded_at": datetime.datetime.utcnow(),
        "uploaded_by": uploaded_by,
    }


def public_status(user_doc):
    """The candidate-visible status payload (no file ids leaked)."""
    card = (user_doc or {}).get("identity_card") or {}
    uploaded = bool(card.get("image_file_id"))
    return {
        "uploaded": uploaded,
        "uploaded_at": card.get("uploaded_at").isoformat() if uploaded and card.get("uploaded_at") else None,
        "original_filename": card.get("original_filename") if uploaded else None,
        # One-time upload: once present, only an admin can change it.
        "locked": uploaded,
    }
