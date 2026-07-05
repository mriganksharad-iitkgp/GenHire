"""
Account-level candidate identity verification.

On a candidate's first real interview the captured webcam photo is enrolled as
the account's canonical face (stored in GridFS, referenced from the user
document's ``face_profile``). Every later real interview capture is verified
against that canonical photo with DeepFace before the interview may proceed,
so different people cannot take interviews from the same account. Practice
interviews capture but never enroll or block.

All heavy imports (DeepFace / cv2 / numpy) are lazy so the API still boots on
deployments without the face stack installed — verification then degrades to
storage-only and reports itself honestly as unavailable.
"""

import datetime
import logging
import os

import gridfs
from bson import ObjectId

logger = logging.getLogger(__name__)

FACE_MODEL_NAME = "VGG-Face"
FACE_DETECTOR_BACKEND = "opencv"
MAX_IMAGE_BYTES = 8 * 1024 * 1024
# extract_faces(enforce_detection=False) returns one whole-image region with
# confidence 0 when nothing was detected — anything above this is a real face.
MIN_FACE_CONFIDENCE = 0.1

_DEEPFACE_STATE = {"checked": False, "available": False}


def get_mode() -> str:
    """enforce (block on mismatch) | monitor (record only) | off (skip checks)."""
    mode = (os.getenv("FACE_VERIFICATION_MODE", "enforce") or "enforce").strip().lower()
    return mode if mode in ("enforce", "monitor", "off") else "enforce"


def get_max_attempts() -> int:
    try:
        return max(1, int(os.getenv("FACE_VERIFY_MAX_ATTEMPTS", "3")))
    except ValueError:
        return 3


def deepface_available() -> bool:
    if not _DEEPFACE_STATE["checked"]:
        try:
            import cv2  # noqa: F401
            import numpy  # noqa: F401
            from deepface import DeepFace  # noqa: F401

            _DEEPFACE_STATE["available"] = True
        except Exception as exc:
            logger.warning(
                "DeepFace stack unavailable — face verification degrades to storage-only: %s",
                exc,
            )
            _DEEPFACE_STATE["available"] = False
        _DEEPFACE_STATE["checked"] = True
    return _DEEPFACE_STATE["available"]


def decode_image(image_bytes):
    """Decode raw JPEG/PNG bytes to a BGR ndarray, or None if undecodable.

    DeepFace does not accept raw ``bytes`` — every caller that hands an image
    to DeepFace must go through this first.
    """
    if not image_bytes or not deepface_available():
        return None
    try:
        import cv2
        import numpy as np

        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception as exc:
        logger.warning("Face image decode failed: %s", exc)
        return None


def assess_face_image(image_bytes) -> dict:
    """Quality-gate a capture: decodable, and exactly one real face visible.

    Returns {"ok": True} when acceptable (or when the check can't run so we
    must not reject), else {"ok": False, "error_code", "message"}.
    """
    if not image_bytes:
        return {
            "ok": False,
            "error_code": "invalid_image",
            "message": "The captured image was empty. Please try again.",
        }
    if len(image_bytes) > MAX_IMAGE_BYTES:
        return {
            "ok": False,
            "error_code": "invalid_image",
            "message": "The captured image is too large. Please try again.",
        }
    if not deepface_available():
        return {"ok": True, "skipped": True, "face_count": None}

    frame = decode_image(image_bytes)
    if frame is None:
        return {
            "ok": False,
            "error_code": "invalid_image",
            "message": "The captured image could not be read. Please try again.",
        }

    try:
        from deepface import DeepFace

        faces = DeepFace.extract_faces(
            img_path=frame,
            detector_backend=FACE_DETECTOR_BACKEND,
            enforce_detection=False,
        )
        real_faces = [
            f for f in faces if float(f.get("confidence") or 0) > MIN_FACE_CONFIDENCE
        ]
    except Exception as exc:
        # Detection itself failing must not lock candidates out.
        logger.warning("Face detection failed during quality gate: %s", exc)
        return {"ok": True, "skipped": True, "face_count": None}

    if len(real_faces) == 0:
        return {
            "ok": False,
            "error_code": "no_face_detected",
            "message": "No face detected. Please center your face in the camera, ensure good lighting, and try again.",
        }
    if len(real_faces) > 1:
        return {
            "ok": False,
            "error_code": "multiple_faces_detected",
            "message": "Multiple faces detected. Please make sure only you are visible in the camera.",
            "face_count": len(real_faces),
        }
    return {"ok": True, "face_count": 1}


def verify_face_images(reference_bytes, candidate_bytes) -> dict:
    """DeepFace-verify a new capture against the canonical reference photo.

    Returns availability separately from the verdict so callers can
    distinguish "system couldn't check" from "checked and mismatched".
    """
    unavailable = {
        "available": False,
        "verified": None,
        "distance": None,
        "threshold": None,
        "model": FACE_MODEL_NAME,
    }
    if not deepface_available():
        return unavailable

    reference = decode_image(reference_bytes)
    candidate = decode_image(candidate_bytes)
    if reference is None or candidate is None:
        return unavailable

    try:
        from deepface import DeepFace

        result = DeepFace.verify(
            img1_path=reference,
            img2_path=candidate,
            model_name=FACE_MODEL_NAME,
            detector_backend=FACE_DETECTOR_BACKEND,
            enforce_detection=False,
        )
        distance = result.get("distance")
        threshold = result.get("threshold")
        return {
            "available": True,
            "verified": bool(result.get("verified")),
            "distance": float(distance) if distance is not None else None,
            "threshold": float(threshold) if threshold is not None else None,
            "model": FACE_MODEL_NAME,
        }
    except Exception as exc:
        logger.error("DeepFace verification failed: %s", exc)
        return unavailable


def store_face_image(db, image_bytes, *, user_id, session_id, purpose) -> str:
    """Persist a face capture in GridFS; returns the file id as a string."""
    fs = gridfs.GridFS(db)
    file_id = fs.put(
        image_bytes,
        filename=f"face_{purpose}_{user_id}_{session_id}.jpg",
        content_type="image/jpeg",
        metadata={
            "user_id": str(user_id),
            "session_id": str(session_id),
            "purpose": purpose,
            "uploaded_at": datetime.datetime.utcnow().isoformat(),
        },
    )
    return str(file_id)


def load_face_image(db, file_id):
    """Fetch stored face image bytes; returns (bytes, content_type)."""
    fs = gridfs.GridFS(db)
    grid_out = fs.get(ObjectId(str(file_id)))
    return grid_out.read(), (grid_out.content_type or "image/jpeg")
