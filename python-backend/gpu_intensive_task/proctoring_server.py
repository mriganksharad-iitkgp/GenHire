"""Optional gaze worker. Candidate pairing/live scoring use the primary API.

Kept for deployments using extra gaze plots. All streams are owner scoped;
missing observations never become a default 100 score. Heavy gaze imports
are lazy so a missing optional MediaPipe stack does not break server boot.
"""
import datetime
import hmac
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, join_room
from core.config import allowed_origins, flask_secret_key
from security_check import decode_frame
from services.proctoring_service import record_manual_violation
from sockets.session_access import owner_session, session_record

logger = logging.getLogger(__name__)
app = Flask(__name__)
app.config["SECRET_KEY"] = flask_secret_key()
CORS(app, resources={r"/*": {"origins": allowed_origins()}})
socketio = SocketIO(app, cors_allowed_origins=allowed_origins(), async_mode="threading")
proctoring_detectors = {}
live_sessions = {}
connections = {}
PROCTORING_FOLDER = os.path.join(os.getenv("UPLOAD_FOLDER", "../uploads"), "proctoring")


@app.get("/")
def health_check():
    return jsonify({"status": "running", "service": "optional-gaze-worker", "mobile_pairing": "primary-api"})


@socketio.on("connect")
def handle_connect(auth=None):
    from middleware.auth_middleware import decode_user_from_token
    user, error = decode_user_from_token((auth or {}).get("token"))
    if error:
        return False
    connections[request.sid] = {"user_id": str(user["_id"])}


@socketio.on("disconnect")
def handle_disconnect(reason=None):
    connections.pop(request.sid, None)


@socketio.on("start_proctoring")
def handle_start_proctoring(data):
    if not isinstance(data, dict):
        return {"ok": False}
    context = connections.get(request.sid) or {}
    collection, doc = owner_session(data.get("session_id"), context.get("user_id"))
    if not doc or doc.get("status") != "active":
        return {"ok": False, "error_code": "unauthorized_session"}
    session_id = data["session_id"]
    if session_id not in proctoring_detectors:
        try:
            from gpu_intensive_task.cheating_detection import ProctoringGazeDetector
            proctoring_detectors[session_id] = ProctoringGazeDetector()
        except Exception as exc:
            logger.warning("Optional gaze model unavailable: %s", type(exc).__name__)
            return {"ok": False, "error_code": "gaze_detector_unavailable"}
    context["session_id"] = session_id
    live_sessions.setdefault(session_id, {"analyzed_frames": 0, "infractions": {}, "events": [], "owner_id": context["user_id"]})
    live_sessions[session_id]["monitoring"] = True
    join_room(session_id)
    return {"ok": True}


@socketio.on("proctoring_frame")
def handle_proctoring_frame(data):
    if not isinstance(data, dict):
        return {"ok": False}
    session_id = data.get("session_id")
    context = connections.get(request.sid) or {}
    state = live_sessions.get(session_id) or {}
    if context.get("session_id") != session_id or not state.get("monitoring"):
        return {"ok": False, "error_code": "unauthorized_session"}
    try:
        result = proctoring_detectors[session_id].process_frame(decode_frame(data.get("image")))
        state["analyzed_frames"] += 1
        state["gaze_times"] = result["gaze_times"]
        socketio.emit("gaze_data", {"session_id": session_id, **result}, room=session_id)
        return {"ok": True}
    except Exception as exc:
        logger.warning("Gaze analysis unavailable: %s", type(exc).__name__)
        return {"ok": False, "error_code": "analysis_unavailable"}


@socketio.on("proctoring_violation")
def handle_proctoring_violation(data):
    if not isinstance(data, dict):
        return {"ok": False}
    context = connections.get(request.sid) or {}
    state = live_sessions.get(data.get("session_id")) or {}
    if context.get("session_id") != data.get("session_id") or not state.get("monitoring"):
        return {"ok": False, "error_code": "unauthorized_session"}
    return {"ok": bool(record_manual_violation(state, data.get("type")))}


@app.get("/api/session/<session_id>/stats")
def get_session_stats(session_id):
    internal_key = os.getenv("PROCTORING_SERVICE_TOKEN")
    provided_key = request.headers.get("X-Proctoring-Service-Token", "")
    internal = bool(internal_key and hmac.compare_digest(internal_key, provided_key))
    if not internal:
        from middleware.auth_middleware import decode_user_from_token
        user, error = decode_user_from_token(request.headers.get("Authorization"))
        collection, doc = session_record(session_id)
        if error or not doc or str(doc.get("user_id")) != str(user["_id"]):
            return jsonify({"error": "Unauthorized session"}), 403
    state = live_sessions.get(session_id)
    if not state:
        return jsonify({"proctoring_score": None, "proctoring_status": "incomplete", "analyzed_frames": 0}), 404
    stats = {
        "proctoring_score": state.get("proctoring_score", 100) if state.get("analyzed_frames", 0) else None,
        "proctoring_status": "partial" if state.get("analyzed_frames", 0) else "incomplete",
        "analyzed_frames": state.get("analyzed_frames", 0), "gaze_times": state.get("gaze_times"),
        "infractions": state.get("infractions", {}),
    }
    detector = proctoring_detectors.get(session_id)
    if detector and state.get("analyzed_frames", 0):
        filename = f"{session_id}_gaze_plot.png"
        try:
            detector.generate_gaze_plot(output_dir=PROCTORING_FOLDER, filename=filename)
            stats["gaze_plot_filename"] = filename
        except Exception as exc:
            logger.warning("Gaze plot failed: %s", type(exc).__name__)
    return jsonify(stats)


if __name__ == "__main__":
    socketio.run(app, debug=False, port=5001)
