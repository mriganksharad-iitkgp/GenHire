"""Owner-bound live captions; audio never enters another candidate's room."""
import re
import threading

from flask import request
from extensions import socketio
from middleware.rate_limiter import socket_limit
from sockets.session_access import bound_context, owner_session
from services.live_transcription_service import LiveTranscript

streams = {}
lock = threading.Lock()


def cancel_speech(sid):
    with lock:
        state = streams.pop(sid, None)
    if state:
        state.cancel()


@socketio.on("speech_live_start")
@socket_limit("socket_control")
def start_live_speech(data):
    if not isinstance(data, dict) or not re.fullmatch(r"[a-zA-Z0-9_-]{8,80}", str(data.get("stream_id", ""))):
        return {"ok": False, "error_code": "invalid_stream"}
    sid = request.sid
    session_id = data.get("session_id")
    context = bound_context(sid, session_id, "desktop")
    _, doc = owner_session(session_id, (context or {}).get("user_id"))
    if not doc or doc.get("status") != "active":
        return {"ok": False, "error_code": "unauthorized_session"}
    from routes.speech_routes import speech_controller
    service = speech_controller.speech_service
    if not service.groq_client and not service.speech_client:
        return {"ok": False, "error_code": "live_speech_unavailable"}
    def active():
        _, current = owner_session(session_id, context["user_id"])
        return bool(current and current.get("status") == "active")
    state = LiveTranscript(data["stream_id"], session_id,
        lambda pcm: service.speech_to_text(pcm, sample_rate_hertz=16000,
            language_code="en-US", encoding="LINEAR16", session_id=session_id),
        lambda payload: socketio.emit("speech_live_transcript", payload, room=sid), active)
    cancel_speech(sid)
    if not state.start():
        return {"ok": False, "error_code": "live_speech_busy"}
    with lock:
        streams[sid] = state
    return {"ok": True, "sample_rate": 16000, "window_seconds": 3}


@socketio.on("speech_live_audio")
def live_audio(data):
    state = streams.get(request.sid)
    if not isinstance(data, dict) or not state or data.get("stream_id") != state.stream_id or not bound_context(request.sid, state.session_id, "desktop"):
        return {"ok": False, "error_code": "invalid_stream"}
    if not state.add(data.get("sequence"), data.get("audio")):
        state.cancel()
        return {"ok": False, "error_code": "invalid_audio"}
    return {"ok": True}


@socketio.on("speech_live_cancel")
def cancel_live_speech(data):
    state = streams.get(request.sid)
    if isinstance(data, dict) and state and data.get("stream_id") == state.stream_id:
        cancel_speech(request.sid)
    return {"ok": True}


@socketio.on("speech_live_end")
@socket_limit("socket_control")
def end_live_speech(data):
    state = streams.get(request.sid)
    if not isinstance(data, dict) or not state or data.get("stream_id") != state.stream_id or not bound_context(request.sid, state.session_id, "desktop"):
        return {"ok": False, "error_code": "invalid_stream"}
    last = data.get("last_sequence")
    if not isinstance(last, int) or isinstance(last, bool) or last < -1:
        return {"ok": False, "error_code": "invalid_sequence"}
    result = state.finish(last)
    with lock:
        if streams.get(request.sid) is state:
            streams.pop(request.sid, None)
    return dict(result, ok=True)
