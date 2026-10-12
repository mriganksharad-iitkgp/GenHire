"""Durable interruption accounting. Coverage failures are not cheating verdicts."""
import copy
import datetime as dt
import logging
import threading

from services.proctoring_service import mobile_is_ready, requires_mobile

HEARTBEAT_SECONDS = 20
REASONS = {
    "tab_switch": "The interview tab was left.",
    "window_blur": "Another window was opened.",
    "fullscreen_exit": "The interview left fullscreen.",
    "device_lost": "The laptop camera or microphone stopped.",
    "desktop_unavailable": "Laptop monitoring stopped receiving updates.",
    "mobile_unavailable": "Phone monitoring stopped. Keep its page visible and screen unlocked.",
}
REASON_PRIORITY = {"desktop_unavailable": 0, "window_blur": 1,
                   "fullscreen_exit": 2, "tab_switch": 3, "device_lost": 4}
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
    counts = dict(policy.get("counts_by_type") or {})
    if not counts:
        for event in policy.get("events") or []:
            reason = event.get("reason", "unknown")
            counts[reason] = counts.get(reason, 0) + 1
    return {"count": policy.get("count", 0), "counts_by_type": counts,
            "losses": {key: {"reason": value["reason"], "message": REASONS.get(value["reason"], "Monitoring interrupted.")}
                       for key, value in (policy.get("losses") or {}).items()},
            "auto_termination": False, "terminated": doc.get("status") == "terminated", "enabled": enabled(doc)}


def _publish(collection, doc, changed=False):
    payload = dict(policy_payload(doc), session_id=doc["session_id"])
    if changed:
        from extensions import socketio
        try:
            socketio.emit("interview_integrity", payload, room=doc["session_id"])
        except Exception:
            logger.warning("Monitoring notification unavailable; interruption counts remain saved")
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
        policy.setdefault("counts_by_type", policy_payload(doc)["counts_by_type"])
        for source in restored:
            policy["losses"].pop(source, None)
        for source, reason in (losses or {}).items():
            if source not in policy["losses"]:
                policy["count"] += 1
                policy["counts_by_type"][reason] = policy["counts_by_type"].get(reason, 0) + 1
                policy["losses"][source] = {"since": now, "reason": reason}
                policy["events"].append({"source": source, "reason": reason, "at": now,
                                         "count": policy["count"], "message": REASONS[reason]})
            else:
                previous = policy["losses"][source]["reason"]
                # A tab switch commonly fires blur first. Refine that same
                # episode's category rather than charging two interruptions.
                if REASON_PRIORITY.get(reason, 0) > REASON_PRIORITY.get(previous, 0):
                    policy["counts_by_type"][previous] = max(0, policy["counts_by_type"].get(previous, 1) - 1)
                    if not policy["counts_by_type"][previous]:
                        policy["counts_by_type"].pop(previous)
                    policy["counts_by_type"][reason] = policy["counts_by_type"].get(reason, 0) + 1
                    policy["losses"][source]["reason"] = reason
                    for event in reversed(policy["events"]):
                        if event["source"] == source and event["reason"] == previous:
                            event.update(reason=reason, message=REASONS[reason])
                            break
        policy["events"] = policy["events"][-100:]
        if policy == old:
            return policy_payload(doc)
        version = old.get("version", 0)
        policy["version"] = version + 1
        values = {"integrity": policy}
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
    """Continues measuring coverage when a browser closes or stops polling."""
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
