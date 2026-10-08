"""Lightweight proctoring policy, companion credentials, and honest reports.

This module deliberately has no ML, database, or application-startup imports.
Socket handlers and HTTP routes share these rules; detection failures are
coverage gaps, never evidence of misconduct.
"""

import base64
import datetime
import hashlib
import hmac
import json
import os
import time

MOBILE_PAIRING_TTL_SECONDS = 3 * 60 * 60
MOBILE_HEARTBEAT_TIMEOUT_SECONDS = 15
PENALTIES = {
    "no_face": 0.5, "multiple_faces": 2.0, "head_turn": 0.5,
    "identity_mismatch": 5.0, "phone_detected": 2.0,
    "prohibited_object": 1.0, "manual_tab_switch": 1.0,
    "manual_window_blur": 0.5, "manual_fullscreen_exit": 1.0,
}
MANUAL_VIOLATIONS = {"tab_switch", "window_blur", "fullscreen_exit"}


def _signing_key():
    from core.security import get_jwt_secret
    return get_jwt_secret().encode("utf-8")


def _encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def create_mobile_pairing_token(session_id, user_id):
    """Signed session-and-owner capability; it grants no account access."""
    payload = _encode(json.dumps({
        "session_id": str(session_id), "user_id": str(user_id),
        "issued_at": int(time.time()), "purpose": "mobile-proctoring",
    }, separators=(",", ":")).encode())
    signature = _encode(hmac.new(_signing_key(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def validate_mobile_pairing_token(token, session_id, user_id=None):
    if not isinstance(token, str) or len(token) > 2048:
        return False
    try:
        payload, signature = token.split(".")
        expected = _encode(hmac.new(_signing_key(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return False
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        age = time.time() - int(claims["issued_at"])
        return (
            claims.get("purpose") == "mobile-proctoring"
            and claims.get("session_id") == str(session_id)
            and (user_id is None or claims.get("user_id") == str(user_id))
            and -30 <= age <= MOBILE_PAIRING_TTL_SECONDS
        )
    except (ValueError, TypeError, KeyError, UnicodeDecodeError):
        return False


def requires_mobile(session_doc):
    doc = session_doc or {}
    return doc.get("dual_proctoring_required") is True or (doc.get("proctoring_config") or {}).get("dual_camera") is True


def mobile_is_ready(session_doc, now=None):
    mobile = (session_doc or {}).get("mobile_proctoring") or {}
    last_seen = mobile.get("last_seen_at")
    if isinstance(last_seen, str):
        try:
            last_seen = datetime.datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
        except ValueError:
            return False
    if not isinstance(last_seen, datetime.datetime):
        return False
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=datetime.timezone.utc)
    elapsed = (now - last_seen).total_seconds()
    preview_at = mobile.get("preview_frame_received_at")
    if isinstance(preview_at, str):
        try:
            preview_at = datetime.datetime.fromisoformat(preview_at.replace("Z", "+00:00"))
        except ValueError:
            return False
    if not isinstance(preview_at, datetime.datetime):
        return False
    if preview_at.tzinfo is None:
        preview_at = preview_at.replace(tzinfo=datetime.timezone.utc)
    preview_age = (now - preview_at).total_seconds()
    return (
        mobile.get("status") in {"ready", "recording"}
        and mobile.get("camera_ready") is True
        and mobile.get("microphone_ready") is True
        and 0 <= elapsed <= MOBILE_HEARTBEAT_TIMEOUT_SECONDS
        and 0 <= preview_age <= MOBILE_HEARTBEAT_TIMEOUT_SECONDS
    )


def record_observation(state, observation, source="desktop", now=None):
    """Confirm repeated observations and charge at most once per 15 seconds.

    A one-frame miss/false positive does not reduce scores. An active violation
    still produces an alert during its cooldown so a warning stays visible.
    """
    now = time.monotonic() if now is None else now
    capabilities = observation.get("capabilities") or {}
    state.setdefault("capabilities_by_source", {}).setdefault(source, {}).update({key: value for key, value in capabilities.items() if value})
    all_capabilities = state.setdefault("capabilities", {})
    for key, value in capabilities.items():
        all_capabilities[key] = all_capabilities.get(key, False) or value
    if observation.get("available"):
        state["analyzed_frames"] = state.get("analyzed_frames", 0) + 1
        key = f"{source}_analyzed_frames"
        state[key] = state.get(key, 0) + 1
    elif not observation.get("manual"):
        state["analysis_errors"] = state.get("analysis_errors", 0) + 1

    streaks = state.setdefault("observation_streaks", {}).setdefault(source, {})
    found = {v["type"]: v for v in observation.get("violations", []) if v.get("type") in PENALTIES}
    for key in list(streaks) if not observation.get("manual") else []:
        if key not in found:
            streaks[key] = 0
    alerts = []
    for kind, violation in found.items():
        streaks[kind] = streaks.get(kind, 0) + 1
        if streaks[kind] < 2:
            continue
        cooldown_key = f"{source}:{kind}"
        last = state.setdefault("last_penalties", {}).get(cooldown_key)
        if last is None or now - last >= 15:
            counts = state.setdefault("infractions", {})
            counts[kind] = counts.get(kind, 0) + 1
            state["last_penalties"][cooldown_key] = now
            event = {"type": kind, "source": source, "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(), "message": violation.get("message", kind)}
            state.setdefault("events", []).append(event)
            state["events"] = state["events"][-500:]
        state["proctoring_score"] = score_from_infractions(state.get("infractions", {}))
        alerts.append({"type": kind, "status": violation.get("message", kind), "score": state["proctoring_score"], "source": source})
    return alerts


def observe_mobile_coverage(state, session_doc):
    """Record a heartbeat/capture gap once until the companion recovers."""
    if not requires_mobile(session_doc):
        return None
    ready = mobile_is_ready(session_doc)
    previous = state.get("mobile_camera_ready", True)
    state["mobile_camera_ready"] = ready
    if ready or not previous:
        return None
    state["mobile_coverage_gaps"] = state.get("mobile_coverage_gaps", 0) + 1
    event = {"type": "mobile_camera_unavailable", "source": "mobile",
             "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
             "message": "Companion camera heartbeat or preview stopped; reconnect the phone to restore recording coverage."}
    state.setdefault("events", []).append(event)
    state["events"] = state["events"][-500:]
    return event


def record_manual_violation(state, kind, now=None):
    if kind not in MANUAL_VIOLATIONS:
        return None
    # Browser focus events are discrete and often duplicated by visibility and
    # blur listeners. Use the same cooldown but do not require a second event.
    observation = {"manual": True, "violations": [{"type": f"manual_{kind}", "message": f"Interview window: {kind.replace('_', ' ')}"}]}
    state.setdefault("observation_streaks", {}).setdefault("desktop", {})[f"manual_{kind}"] = 1
    alerts = record_observation(state, observation, now=now)
    return alerts[0] if alerts else None


def score_from_infractions(infractions):
    return round(max(0, 100 - sum(PENALTIES.get(kind, 0) * count for kind, count in infractions.items())), 2)


def build_proctoring_report(live_session, session_doc=None):
    state = live_session or {}
    persisted = (session_doc or {}).get("proctoring_report") or {}
    if not state and persisted:
        coverage = persisted.get("coverage") or {}
        state = {
            "desktop_analyzed_frames": coverage.get("desktop_analyzed_frames", 0),
            "mobile_analyzed_frames": coverage.get("mobile_analyzed_frames", 0),
            "analyzed_frames": coverage.get("desktop_analyzed_frames", 0) + coverage.get("mobile_analyzed_frames", 0),
            "infractions": persisted.get("infraction_counts") or {}, "events": persisted.get("events") or [],
            "capabilities": persisted.get("capabilities") or {}, "analysis_errors": coverage.get("analysis_errors", 0),
            "mobile_coverage_gaps": coverage.get("mobile_coverage_gaps", 0),
        }
    config = (session_doc or {}).get("proctoring_config")
    disabled = isinstance(config, dict) and not any(config.values())
    desktop_frames = state.get("desktop_analyzed_frames", 0)
    mobile_frames = state.get("mobile_analyzed_frames", 0)
    total_frames = state.get("analyzed_frames", 0)
    dual = requires_mobile(session_doc)
    status = "disabled" if disabled else "incomplete" if total_frames == 0 or desktop_frames == 0 else "partial" if dual and (mobile_frames == 0 or state.get("mobile_coverage_gaps", 0)) else "complete"
    capabilities = state.get("capabilities", {})
    missing = []
    if status not in {"disabled", "incomplete"}:
        if not capabilities.get("face_detection"):
            missing.append("face_detection")
        if os.getenv("PROCTORING_IDENTITY_ENABLED", "false").lower() == "true" and not capabilities.get("identity_continuity"):
            missing.append("identity_continuity")
        if (config or {}).get("object_detection", True) and not capabilities.get("object_detection"):
            missing.append("object_detection")
        for feature in ("eyeball_tracking", "voice_detection", "gaze_heatmap"):
            if (config or {}).get(feature, True) and not capabilities.get(feature):
                missing.append(feature)
        if missing:
            status = "partial"
    counts = dict(state.get("infractions", {}))
    return {
        "final_score": score_from_infractions(counts) if desktop_frames > 0 and not disabled else None,
        "status": status, "infraction_counts": counts,
        "events": list(state.get("events", [])), "capabilities": dict(capabilities),
        "missing_checks": missing,
        "coverage": {"desktop_analyzed_frames": desktop_frames, "mobile_analyzed_frames": mobile_frames, "dual_camera_required": dual, "analysis_errors": state.get("analysis_errors", 0), "mobile_coverage_gaps": state.get("mobile_coverage_gaps", 0)},
        "summary": "Proctoring checks were disabled for this interview." if disabled else "Proctoring could not analyze the laptop camera; no score is available." if desktop_frames == 0 else "Some proctoring checks were unavailable; review camera coverage and warnings." if status == "partial" else "No proctoring warnings detected." if not counts else "Proctoring warnings require human review; detections are not a cheating verdict.",
    }
