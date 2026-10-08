"""Signed companion pairing, measured readiness, and secondary-camera frames."""
import datetime
import time

from flask import request
from flask_socketio import join_room
from extensions import socketio
from interview.runtime import live_sessions
from services.proctoring_service import mobile_is_ready, requires_mobile, validate_mobile_pairing_token
from sockets.session_access import bound_context, contexts_lock, owner_session, session_record, socket_contexts, TERMINAL_STATUSES


@socketio.on("join_mobile_session")
def handle_mobile_join(data):
    from core import config as app_config
    if not app_config.mobile_recording_enabled():
        return {"ok": False, "error_code": "mobile_recording_disabled"}
    if not isinstance(data, dict):
        return {"ok": False, "error_code": "invalid_request"}
    session_id = data.get("session_id")
    collection, doc = session_record(session_id)
    if not doc:
        return {"ok": False, "error_code": "session_unavailable"}
    if not validate_mobile_pairing_token(data.get("pairing_token"), session_id, doc.get("user_id")):
        return {"ok": False, "error_code": "invalid_pairing_token"}
    # A companion that missed the stop command may reconnect solely to learn
    # completion and upload its buffered recording using the signed capability.
    # It receives no live-room membership or ready/recording context.
    if doc.get("status") in TERMINAL_STATUSES:
        return {"ok": True, "session_status": doc["status"], "terminal": True}
    if not requires_mobile(doc):
        return {"ok": False, "error_code": "dual_camera_not_enabled"}
    context = {"role": "mobile", "session_id": session_id, "user_id": str(doc.get("user_id"))}
    with contexts_lock:
        previous_sid = (doc.get("mobile_proctoring") or {}).get("socket_id")
        if previous_sid and previous_sid != request.sid:
            socket_contexts.pop(previous_sid, None)
        socket_contexts[request.sid] = context
    if previous_sid and previous_sid != request.sid:
        # Removing only the context would leave the replaced phone subscribed
        # to private room updates. Disconnect the old transport as well.
        socketio.server.disconnect(previous_sid, namespace="/")
    mobile = {"socket_id": request.sid, "status": "connected", "camera_ready": False, "microphone_ready": False, "last_seen_at": datetime.datetime.now(datetime.timezone.utc)}
    collection.update_one({"_id": doc["_id"]}, {"$set": {"mobile_proctoring": mobile}})
    join_room(session_id)
    socketio.emit("mobile_connected", {"status": "connected", "camera_ready": False, "microphone_ready": False, "ready": False}, room=session_id)
    return {"ok": True, "session_status": doc.get("status")}


@socketio.on("control_mobile_recording")
def handle_mobile_control(data):
    if not isinstance(data, dict) or data.get("action") not in {"start", "stop"}:
        return {"ok": False, "error_code": "invalid_request"}
    context = bound_context(request.sid, data.get("session_id"), "desktop")
    if not context:
        return {"ok": False, "error_code": "unauthorized_session"}
    collection, doc = session_record(data["session_id"])
    if not doc or str(doc.get("user_id")) != context.get("user_id"):
        return {"ok": False, "error_code": "unauthorized_session"}
    if data["action"] == "start" and (doc.get("status") != "active" or not mobile_is_ready(doc)):
        return {"ok": False, "error_code": "mobile_camera_not_ready"}
    mobile_sid = (doc.get("mobile_proctoring") or {}).get("socket_id")
    if mobile_sid:
        # Commands only reach the authorized companion, not every observer
        # subscribed to the desktop's room.
        socketio.emit("mobile_recording_action", {"action": data["action"]}, room=mobile_sid)
    return {"ok": bool(mobile_sid)}


@socketio.on("mobile_status_update")
def handle_mobile_status(data):
    if not isinstance(data, dict):
        return {"ok": False, "error_code": "invalid_request"}
    session_id = data.get("session_id")
    context = bound_context(request.sid, session_id, "mobile")
    if not context:
        return {"ok": False, "error_code": "unauthorized_session"}
    status = data.get("status")
    if status not in {"connected", "ready", "recording", "uploading", "uploaded", "completed", "camera_error", "upload_failed", "disconnected"}:
        return {"ok": False, "error_code": "invalid_mobile_status"}
    collection, doc = session_record(session_id)
    if not doc or (doc.get("mobile_proctoring") or {}).get("socket_id") != request.sid:
        return {"ok": False, "error_code": "companion_replaced"}
    now = datetime.datetime.now(datetime.timezone.utc)
    mobile = {
        "socket_id": request.sid, "status": status,
        "camera_ready": data.get("camera_ready") is True,
        "microphone_ready": data.get("microphone_ready") is True,
        "last_seen_at": now,
        "preview_frame_received_at": (doc.get("mobile_proctoring") or {}).get("preview_frame_received_at"),
    }
    # Completion/error reports cannot claim readiness even if a stale caller
    # supplied the camera flags from its earlier successful permission check.
    if status not in {"ready", "recording"}:
        mobile["camera_ready"] = mobile["microphone_ready"] = False
    collection.update_one({"_id": doc["_id"], "mobile_proctoring.socket_id": request.sid}, {"$set": {"mobile_proctoring": mobile}})
    doc["mobile_proctoring"] = mobile
    socketio.emit("mobile_status_dashboard", {
        "status": status, "camera_ready": mobile["camera_ready"], "microphone_ready": mobile["microphone_ready"],
        "last_seen_at": now.isoformat(), "ready": mobile_is_ready(doc),
    }, room=session_id)
    return {"ok": True, "ready": mobile_is_ready(doc)}


@socketio.on("mobile_proctoring_frame")
def handle_mobile_frame(data):
    if not isinstance(data, dict):
        return {"ok": False, "error_code": "invalid_request"}
    session_id = data.get("session_id")
    context = bound_context(request.sid, session_id, "mobile")
    if not context:
        return {"ok": False, "error_code": "unauthorized_session"}
    now_monotonic = time.monotonic()
    if now_monotonic - context.get("last_preview_at", -1) < 0.7:
        return {"ok": True, "accepted": False, "reason": "rate_limited"}
    collection, doc = session_record(session_id)
    if not doc or doc.get("status") in TERMINAL_STATUSES or (doc.get("mobile_proctoring") or {}).get("socket_id") != request.sid:
        return {"ok": False, "error_code": "session_unavailable"}
    try:
        # Setup previews prove camera capture works, without changing score.
        from security_check import decode_frame
        decode_frame(data.get("image"))
        context["last_preview_at"] = now_monotonic
    except Exception:
        return {"ok": False, "error_code": "invalid_camera_frame"}
    now = datetime.datetime.now(datetime.timezone.utc)
    collection.update_one({"_id": doc["_id"], "mobile_proctoring.socket_id": request.sid}, {"$set": {"mobile_proctoring.preview_frame_received_at": now}})
    mobile = doc.get("mobile_proctoring") or {}
    mobile["preview_frame_received_at"] = now
    socketio.emit("mobile_status_dashboard", {
        "status": mobile.get("status"), "camera_ready": mobile.get("camera_ready", False),
        "microphone_ready": mobile.get("microphone_ready", False), "last_seen_at": mobile.get("last_seen_at").isoformat() if mobile.get("last_seen_at") else None,
        "ready": mobile_is_ready(doc),
    }, room=session_id)
    if not (live_sessions.get(session_id) or {}).get("monitoring"):
        return {"ok": True, "preview_received": True}
    from sockets.proctoring_sockets import process_camera_frame
    return process_camera_frame(data, source="mobile")
