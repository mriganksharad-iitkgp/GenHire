"""Owner-authorized primary API proctoring, used by browser and kiosk."""
import datetime
import logging
import os
import threading
import time

from flask import request
from flask_socketio import join_room
from extensions import socketio
from interview.runtime import live_sessions
from services.proctoring_service import build_proctoring_report, mobile_is_ready, observe_mobile_coverage, record_manual_violation, record_observation, requires_mobile
from sockets.session_access import bound_context, mobile_disconnect, owner_session, socket_contexts

logger = logging.getLogger(__name__)


@socketio.on("connect")
def handle_connect(auth=None):
    from middleware.auth_middleware import decode_user_from_token
    auth = auth if isinstance(auth, dict) else {}
    token = auth.get("token")
    if not token:
        # Anonymous handshakes are allowed only so phones can present a signed
        # pairing token. Every event independently enforces the bound role.
        socket_contexts[request.sid] = {"role": "anonymous"}
        return
    current_user, error = decode_user_from_token(token)
    if error:
        return False
    user_id = str(current_user["_id"])
    socket_contexts[request.sid] = {"role": "desktop", "user_id": user_id}
    join_room(user_id)


@socketio.on("disconnect")
def handle_disconnect(reason=None):
    session_id = mobile_disconnect(request.sid)
    if session_id:
        state = live_sessions.get(session_id)
        if state and state.get("monitoring"):
            with state.setdefault("analysis_lock", threading.Lock()):
                state["mobile_coverage_gaps"] = state.get("mobile_coverage_gaps", 0) + 1
                state["mobile_camera_ready"] = False
                state.setdefault("events", []).append({"type": "mobile_camera_disconnected", "source": "mobile", "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(), "message": "Companion camera disconnected; this is a recording coverage gap, not a cheating verdict."})
                state["events"] = state["events"][-500:]
        socketio.emit("mobile_disconnected", {"status": "disconnected", "camera_ready": False, "microphone_ready": False, "ready": False}, room=session_id)


@socketio.on("join_interview_session")
def handle_join_interview_session(data):
    if not isinstance(data, dict):
        return {"ok": False, "error_code": "invalid_request"}
    context = socket_contexts.get(request.sid) or {}
    collection, doc = owner_session(data.get("session_id"), context.get("user_id"))
    if context.get("role") != "desktop" or not doc:
        return {"ok": False, "error_code": "unauthorized_session"}
    context.update({"session_id": data["session_id"], "monitoring": False})
    join_room(data["session_id"])
    mobile = doc.get("mobile_proctoring") or {}
    socketio.emit("mobile_status_dashboard", {
        "status": mobile.get("status", "not_connected"), "camera_ready": mobile.get("camera_ready", False),
        "microphone_ready": mobile.get("microphone_ready", False), "ready": mobile_is_ready(doc),
    }, room=request.sid)
    return {"ok": True, "session_status": doc.get("status"), "mobile_ready": mobile_is_ready(doc)}


@socketio.on("start_proctoring")
def handle_start_proctoring(data):
    if not isinstance(data, dict):
        return {"ok": False, "error_code": "invalid_request"}
    context = socket_contexts.get(request.sid) or {}
    collection, doc = owner_session(data.get("session_id"), context.get("user_id"))
    if context.get("role") != "desktop" or not doc:
        return {"ok": False, "error_code": "unauthorized_session"}
    if doc.get("status") != "active":
        return {"ok": False, "error_code": "interview_not_active"}
    state = live_sessions.get(data["session_id"])
    if not state or not state.get("registered_face"):
        return {"ok": False, "error_code": "face_registration_required"}
    if requires_mobile(doc) and not mobile_is_ready(doc):
        return {"ok": False, "error_code": "mobile_camera_not_ready"}
    state.setdefault("proctoring_config", doc.get("proctoring_config") or {})
    state.setdefault("owner_id", str(doc.get("user_id")))
    state["monitoring"] = True
    if requires_mobile(doc):
        state["mobile_camera_ready"] = True
    context.update({"session_id": data["session_id"], "monitoring": True})
    join_room(data["session_id"])
    socketio.emit("proctoring_status", {"available": None, "status": "starting", "analyzed_frames": state.get("analyzed_frames", 0)}, room=request.sid)
    return {"ok": True}


def process_camera_frame(data, source="desktop"):
    if not isinstance(data, dict):
        return {"ok": False, "error_code": "invalid_request"}
    session_id = data.get("session_id")
    if not isinstance(session_id, str):
        return {"ok": False, "error_code": "invalid_request"}
    context = bound_context(request.sid, session_id, "mobile" if source == "mobile" else "desktop")
    state = live_sessions.get(session_id)
    if not context or not state or not state.get("monitoring"):
        return {"ok": False, "error_code": "proctoring_not_started"}
    if source == "desktop" and not context.get("monitoring"):
        return {"ok": False, "error_code": "proctoring_not_started"}
    collection, doc = owner_session(session_id, state.get("owner_id"))
    if not doc or doc.get("status") != "active":
        state["monitoring"] = False
        return {"ok": False, "error_code": "interview_not_active"}
    lock = state.setdefault("analysis_lock", threading.Lock())
    if not lock.acquire(blocking=False):
        return {"ok": True, "accepted": False, "reason": "busy"}
    try:
        if observe_mobile_coverage(state, doc):
            socketio.emit("mobile_status_dashboard", {"status": "disconnected", "camera_ready": False, "microphone_ready": False, "ready": False}, room=session_id)
        now = time.monotonic()
        last = state.setdefault("last_frame_at", {}).get(source)
        if last is not None and now - last < 0.7:
            return {"ok": True, "accepted": False, "reason": "rate_limited"}
        state["last_frame_at"][source] = now
        from security_check import analyze_frame, decode_frame
        frame = decode_frame(data.get("image"))
        reference = state.get("registered_face_np")
        if reference is None:
            reference = state.get("registered_face")
        check_identity = source == "desktop" and os.getenv("PROCTORING_IDENTITY_ENABLED", "false").lower() == "true" and now - state.get("last_identity_at", -20) >= 20
        if check_identity:
            state["last_identity_at"] = now
        result = analyze_frame(frame, reference, state.get("proctoring_config"), source, check_identity)
        alerts = record_observation(state, result, source, now)
        for alert in alerts:
            alert["session_id"] = session_id
            socketio.emit("proctoring_alert", alert, room=session_id)
        socketio.emit("proctoring_status", {
            "session_id": session_id, "available": result["available"], "source": source,
            "capabilities": result["capabilities"], "analyzed_frames": state.get("analyzed_frames", 0),
            "score": state.get("proctoring_score") if state.get("desktop_analyzed_frames", 0) else None,
            "active_warnings": [item["type"] for item in alerts],
        }, room=session_id)
        # Preserve report evidence across HTTP workers/restarts rather than
        # requiring /end to happen in the socket's worker process.
        if now - state.get("last_persist_at", -5) >= 5:
            if doc:
                report = build_proctoring_report(state, doc)
                collection.update_one({"_id": doc["_id"]}, {"$set": {
                    "proctoring_report": report, "proctoring_score": report["final_score"],
                    "proctoring_status": report["status"], "proctoring_updated_at": datetime.datetime.now(datetime.timezone.utc),
                }})
            state["last_persist_at"] = now
        return {"ok": True, "accepted": True, "available": result["available"]}
    except Exception as exc:
        logger.warning("Camera analysis unavailable for %s: %s", session_id, type(exc).__name__)
        state["analysis_errors"] = state.get("analysis_errors", 0) + 1
        socketio.emit("proctoring_status", {"available": False, "source": source, "status": "unavailable", "message": "Camera analysis is unavailable. Your recording will still be retained for review."}, room=session_id)
        return {"ok": False, "error_code": "analysis_unavailable"}
    finally:
        lock.release()


@socketio.on("proctoring_frame")
def handle_proctoring_frame(data):
    return process_camera_frame(data)


@socketio.on("proctoring_violation")
def handle_proctoring_violation(data):
    if not isinstance(data, dict) or not isinstance(data.get("session_id"), str):
        return {"ok": False, "error_code": "invalid_request"}
    context = bound_context(request.sid, data.get("session_id"), "desktop")
    state = live_sessions.get(data.get("session_id"))
    if not context or not context.get("monitoring") or not state or not state.get("monitoring"):
        return {"ok": False, "error_code": "unauthorized_session"}
    with state.setdefault("analysis_lock", threading.Lock()):
        alert = record_manual_violation(state, data.get("type"))
    if alert:
        socketio.emit("proctoring_alert", alert, room=data["session_id"])
    return {"ok": bool(alert)}


@socketio.on("stop_proctoring")
def handle_stop_proctoring(data):
    if not isinstance(data, dict) or not isinstance(data.get("session_id"), str):
        return {"ok": False, "error_code": "invalid_request"}
    session_id = data["session_id"]
    context = bound_context(request.sid, session_id, "desktop")
    state = live_sessions.get(session_id)
    if not context or not state:
        return {"ok": False, "error_code": "unauthorized_session"}
    collection, doc = owner_session(session_id, context.get("user_id"))
    if not doc:
        return {"ok": False, "error_code": "unauthorized_session"}
    with state.setdefault("analysis_lock", threading.Lock()):
        state["monitoring"] = False
        context["monitoring"] = False
        report = build_proctoring_report(state, doc)
        collection.update_one({"_id": doc["_id"]}, {"$set": {"proctoring_report": report, "proctoring_score": report["final_score"], "proctoring_status": report["status"]}})
    return {"ok": True, "report": report}
