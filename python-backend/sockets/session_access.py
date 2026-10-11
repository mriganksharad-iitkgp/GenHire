"""Shared connection bindings; an anonymous phone can only use its capability."""
import datetime
import threading

socket_contexts = {}
contexts_lock = threading.Lock()
TERMINAL_STATUSES = {"completed", "ended", "cancelled", "abandoned", "failed", "expired", "terminated"}


def session_record(session_id):
    if not isinstance(session_id, str) or not session_id or len(session_id) > 128:
        return None, None
    from config.database import db_config
    collections = db_config.get_collections()
    for name in ("interviews", "practice_sessions"):
        collection = collections[name]
        doc = collection.find_one({"session_id": session_id})
        if doc:
            return collection, doc
    return None, None


def owner_session(session_id, user_id):
    if not user_id:
        return None, None
    collection, doc = session_record(session_id)
    if not doc or str(doc.get("user_id")) != str(user_id) or doc.get("status") in TERMINAL_STATUSES:
        return None, None
    return collection, doc


def bound_context(sid, session_id, role):
    context = socket_contexts.get(sid) or {}
    if context.get("role") != role or context.get("session_id") != session_id:
        return None
    return context


def mobile_disconnect(sid):
    with contexts_lock:
        context = socket_contexts.pop(sid, None)
    if not context or context.get("role") != "mobile":
        return None
    session_id = context["session_id"]
    collection, doc = session_record(session_id)
    if doc:
        # A reconnect may have replaced this socket. The old disconnect must
        # not turn the replacement's working camera into a false failure.
        collection.update_one({"_id": doc["_id"], "mobile_proctoring.socket_id": sid}, {"$set": {
            "mobile_proctoring.status": "disconnected", "mobile_proctoring.camera_ready": False,
            "mobile_proctoring.microphone_ready": False,
            "mobile_proctoring.last_seen_at": datetime.datetime.now(datetime.timezone.utc),
        }})
        if (doc.get("mobile_proctoring") or {}).get("socket_id") != sid:
            return None
    return session_id
