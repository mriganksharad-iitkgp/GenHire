"""Durable interruption policy. Coverage failures are not cheating verdicts."""
import copy
import datetime as dt
import logging
import threading
import sys

from services.proctoring_service import mobile_is_ready, requires_mobile

LIMIT = 5
HEARTBEAT_SECONDS = 20
RECOVERY_SECONDS = 60
REASONS = {
    "tab_switch": "The interview tab was left.",
    "window_blur": "Another window was opened.",
    "fullscreen_exit": "The interview left fullscreen.",
    "device_lost": "The laptop camera or microphone stopped.",
    "desktop_unavailable": "Laptop monitoring stopped receiving updates.",
    "mobile_unavailable": "Phone monitoring stopped. Keep its page visible and screen unlocked.",
}
logger = logging.getLogger(__name__)


def enabled(doc):
    return not doc.get("is_practice") or doc.get("proctoring_enabled") is True


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def age(value, now):
    if not isinstance(value, dt.datetime):
        return float("inf")
    return (now - (value.replace(tzinfo=dt.timezone.utc) if value.tzinfo is None else value)).total_seconds()


def policy_payload(doc):
    policy = doc.get("integrity") or {}
    return {"count": policy.get("count", 0), "limit": LIMIT,
            "remaining": max(0, LIMIT - policy.get("count", 0)),
            "losses": {key: {"reason": value["reason"], "message": REASONS.get(value["reason"], "Monitoring interrupted.")}
                       for key, value in (policy.get("losses") or {}).items()},
            "terminated": doc.get("status") == "terminated",
            "termination_reason": doc.get("termination_reason"),
            "recovery_seconds": RECOVERY_SECONDS, "enabled": enabled(doc)}


def _publish(collection, doc, changed=False):
    payload = dict(policy_payload(doc), session_id=doc["session_id"])
    if payload["terminated"] and changed:
        # The session itself is the primary lock; this application flag also
        # makes the restriction visible to recruiters and the start endpoint.
        if doc.get("application_id"):
            from bson import ObjectId
            collection.database["applications"].update_one(
                {"_id": ObjectId(doc["application_id"])}, {"$set": {
                    "interview_attempt_locked": True, "terminated_session_id": doc["session_id"],
                    "interview_termination_reason": doc.get("termination_reason")}})
        from services.interview_flow_service import stop_companion
        stop_companion(doc)
    if changed:
        from extensions import socketio
        try:
            socketio.emit("interview_integrity", payload, room=doc["session_id"])
        except Exception:
            logger.warning("Monitoring notification unavailable; durable policy remains enforced")
    return payload


def reconcile(collection, doc, losses=None, restored=(), now=None):
    """CAS persists one count per source outage until healthy again.

    Blur/visibility/fullscreen callbacks during one absence and repeated stale
    heartbeats cannot inflate the count. Separate episodes require recovery.
    """
    now = now or utcnow()
    if not enabled(doc) or doc.get("status") != "active":
        return _publish(collection, doc)
    if not doc.get("integrity") and not losses:
        return policy_payload(doc)
    for _ in range(8):
        old = doc.get("integrity") or {}
        policy = copy.deepcopy(old)
        policy.setdefault("count", 0)
        policy.setdefault("losses", {})
        policy.setdefault("events", [])
        for source in restored:
            policy["losses"].pop(source, None)
        for source, reason in (losses or {}).items():
            if source not in policy["losses"]:
                policy["count"] += 1
                policy["losses"][source] = {"since": now, "reason": reason}
                policy["events"].append({"source": source, "reason": reason, "at": now,
                                         "count": policy["count"], "message": REASONS[reason]})
        policy["events"] = policy["events"][-100:]
        expired = any(age(value["since"], now) >= RECOVERY_SECONDS for value in policy["losses"].values())
        terminal = policy["count"] >= LIMIT or expired
        if policy == old and not terminal:
            return policy_payload(doc)
        version = old.get("version", 0)
        policy["version"] = version + 1
        values = {"integrity": policy}
        if terminal:
            values.update(status="terminated", ended_at=now, updated_at=now,
                          termination_reason="interruption_limit" if policy["count"] >= LIMIT else "monitoring_not_restored",
                          proctoring_status="interrupted")
            from services.proctoring_service import build_proctoring_report
            runtime = sys.modules.get("interview.runtime")
            state = getattr(runtime, "live_sessions", {}).get(doc["session_id"])
            if state:
                state["monitoring"] = False
            report = build_proctoring_report(state, dict(doc, integrity=policy))
            report["status"] = "interrupted"
            values["proctoring_report"] = report
        query = {"_id": doc["_id"], "status": "active"}
        query["integrity.version"] = version if "version" in old else {"$exists": False}
        if collection.update_one(query, {"$set": values}).matched_count:
            doc.update(values)
            return _publish(collection, doc, changed=True)
        doc = collection.find_one({"_id": doc["_id"]})
        if not doc or doc.get("status") != "active":
            return policy_payload(doc or {})
    raise RuntimeError("Monitoring state changed repeatedly; retry the request")


def check_health(collection, doc, now=None):
    now = now or utcnow()
    if doc.get("status") != "active" or not enabled(doc):
        return _publish(collection, doc)
    loss, restored = {}, []
    desktop = doc.get("desktop_monitoring") or {}
    # Activation has a short grace period to establish the first heartbeat.
    if age(doc.get("activated_at", now), now) > HEARTBEAT_SECONDS:
        if (age(desktop.get("last_seen_at"), now) > HEARTBEAT_SECONDS
                or age(desktop.get("frame_at"), now) > HEARTBEAT_SECONDS):
            loss["desktop"] = "desktop_unavailable"
        elif desktop.get("visible") is not True:
            loss["desktop"] = "tab_switch"
        elif desktop.get("devices_ready") is not True:
            loss["desktop"] = "device_lost"
        elif desktop.get("secure_view") is not True:
            loss["desktop"] = "fullscreen_exit"
        elif desktop.get("focused") is not True:
            loss["desktop"] = "window_blur"
        elif desktop.get("focused") is True:
            restored.append("desktop")
    if requires_mobile(doc):
        if mobile_is_ready(doc, now):
            restored.append("mobile")
        else:
            loss["mobile"] = "mobile_unavailable"
    return reconcile(collection, doc, loss, restored, now)


class IntegrityWatchdog:
    """Continues enforcing coverage when a browser closes or stops polling."""
    def __init__(self, collections):
        self.collections = collections
        self.stop_event = threading.Event()

    def start(self):
        def run():
            while not self.stop_event.wait(5):
                for name in ("interviews", "practice_sessions"):
                    try:
                        for doc in self.collections[name].find({"status": "active"}):
                            check_health(self.collections[name], doc)
                    except Exception:
                        logger.warning("Interview monitoring sweep failed", exc_info=True)
        self.thread = threading.Thread(target=run, daemon=True, name="interview-integrity")
        self.thread.start()

    def stop(self):
        self.stop_event.set()
