"""Socket.IO handlers for the live proctoring stream.

Moved verbatim from app.py. The desktop interview client authenticates on
connect (joining a per-user room for realtime application updates), then
streams one JPEG frame per second which is analyzed for head-pose and
identity violations against the face registered at interview start.
"""

import base64

import numpy as np
from flask_socketio import join_room, disconnect

from extensions import socketio
from interview.runtime import live_sessions

try:
    from security_check import analyze_frame_for_proctoring
    _proctoring_available = True
except Exception:
    _proctoring_available = False


@socketio.on("connect")
def handle_connect(auth):
    """
    Join a per-user room when the client authenticates, so application/
    status/score updates can be pushed to exactly the candidate or recruiter
    they belong to (see application_controller.py emits).

    Connections WITHOUT a token are allowed but join no user room: the mobile
    companion page is opened from a QR link and has no JWT to present, and it
    only ever joins a session-id room via join_mobile_session below (which
    validates the session exists). A token that is present but invalid is
    still rejected outright — previously ANY tokenless connect was rejected,
    which silently killed the interview page's live proctoring stream and the
    entire mobile companion flow.
    """
    from middleware.auth_middleware import decode_user_from_token

    token = (auth or {}).get("token")
    if not token:
        return  # anonymous session-room-only connection (mobile companion)

    current_user, error = decode_user_from_token(token)
    if error:
        # Reject the handshake outright; client falls back to REST polling.
        disconnect()
        return False

    join_room(str(current_user["_id"]))


@socketio.on("disconnect")
def handle_disconnect():
    pass


@socketio.on("start_proctoring")
def handle_start_proctoring(data):
    """Desktop client signals it is ready to send proctoring frames."""
    session_id = data.get("session_id")
    if not session_id:
        return
    join_room(session_id)
    print(f"Proctoring started for session {session_id}")


@socketio.on("proctoring_frame")
def handle_proctoring_frame(data):
    """
    Receives a JPEG frame (base64) from the desktop client once per second,
    runs MediaPipe head-pose + DeepFace identity check, and emits a
    proctoring_alert back to the room if a violation is detected.
    """
    if not _proctoring_available:
        return

    session_id = data.get("session_id")
    image_data = data.get("image", "")
    if not session_id or not image_data:
        return

    session = live_sessions.get(session_id)
    if not session:
        return  # Face not registered yet — ignore frame

    try:
        # Decode base64 frame to numpy array
        encoded = image_data.split(",", 1)[1] if "," in image_data else image_data
        img_bytes = base64.b64decode(encoded)
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        import cv2
        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if frame is None:
            return

        # Prefer the decoded ndarray reference — DeepFace.verify inside
        # analyze_frame_for_proctoring does not accept raw bytes, which made
        # the identity check silently fail on every frame before.
        reference_face = session.get("registered_face_np")
        if reference_face is None:
            reference_face = session["registered_face"]

        result = analyze_frame_for_proctoring(
            current_frame=frame,
            registered_face_img=reference_face,
            current_score=session["proctoring_score"],
            infractions=session["infractions"],
        )

        session["proctoring_score"] = result["score"]
        session["infractions"] = result["infractions"]

        if result["status"] != "Status: OK":
            socketio.emit(
                "proctoring_alert",
                {
                    "status": result["status"],
                    "score": result["score"],
                    "infractions": result["infractions"],
                },
                room=session_id,
            )
    except Exception as e:
        print(f"proctoring_frame error for {session_id}: {e}")


@socketio.on("proctoring_violation")
def handle_proctoring_violation(data):
    """Records a manual violation (tab switch, window blur) in the session store."""
    session_id = data.get("session_id")
    violation_type = data.get("type", "unknown")
    if not session_id:
        return
    session = live_sessions.get(session_id)
    if session:
        key = f"manual_{violation_type}"
        session["infractions"][key] = session["infractions"].get(key, 0) + 1
    print(f"Manual violation [{violation_type}] for session {session_id}")
