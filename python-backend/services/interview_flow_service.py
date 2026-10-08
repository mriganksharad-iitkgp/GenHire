"""Small shared interview-policy helpers without media or model dependencies."""

import math
import logging
import threading
import time
import weakref
from dataclasses import asdict, is_dataclass
from enum import Enum
from functools import wraps

DEFAULT_PROCTORING_CONFIG = {
    "voice_detection": True,
    "object_detection": True,
    "eyeball_tracking": True,
    "gaze_heatmap": True,
    "ai_detection": False,
    "dual_camera": False,
}

_locks = weakref.WeakValueDictionary()
_locks_guard = threading.Lock()


def normalize_proctoring_config(value=None, base=None):
    """Preserve legacy defaults and require actual JSON booleans."""
    result = dict(DEFAULT_PROCTORING_CONFIG)
    if isinstance(base, dict):
        result.update({key: flag for key, flag in base.items()
                       if key in result and isinstance(flag, bool)})
    if value is None:
        return result
    if not isinstance(value, dict):
        raise ValueError("proctoring_config must be an object")
    for key in result:
        if key in value:
            if not isinstance(value[key], bool):
                raise ValueError(f"proctoring_config.{key} must be a boolean")
            result[key] = value[key]
    return result


def session_lock(key):
    # The interview engine is process-local; serialize mutations in that process.
    # Database leases separately protect real-interview creation across workers.
    with _locks_guard:
        return _locks.setdefault(str(key), threading.RLock())


def serialized_session(fn):
    @wraps(fn)
    def wrapped(current_user, session_id, *args, **kwargs):
        with session_lock(session_id):
            return fn(current_user, session_id, *args, **kwargs)
    return wrapped


def percentage(value, normalized=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value):
        return None
    return round(max(0.0, min(100.0, float(value) * (100 if normalized else 1))), 1)


def result_payload(doc):
    """Replay a terminal response without generating another evaluation/debit."""
    if doc.get("status") == "abandoned":
        return {"status": "interview_discarded", "session_id": doc["session_id"],
                "message": "No answers were recorded. This interview was not counted.",
                "refund": doc.get("credits_refund")}
    return {
        "status": "interview_ended", "session_id": doc["session_id"],
        "evaluation": doc.get("evaluation") or {},
        "interview_score": percentage(doc.get("interview_score", doc.get("final_score"))),
        "cv_score": percentage(doc.get("cv_score"), normalized=bool(doc.get("is_practice"))),
        "cv_score_status": doc.get("cv_score_status", "complete" if doc.get("cv_score") is not None else "unavailable"),
        "proctoring_score": percentage(doc.get("proctoring_score")),
        "proctoring_status": doc.get("proctoring_status", "incomplete"),
        "proctoring_report": doc.get("proctoring_report") or {},
        "identity_verification": identity_report(doc.get("identity_verification")),
        "recording_parts": doc.get("recording_parts") or [],
        "mobile_recording_parts": doc.get("mobile_recording_parts") or [],
        "transcript": doc.get("transcript") or [],
        "usage_summary": doc.get("usage_summary"),
        "usage_deduction": doc.get("usage_deduction"),
    }


def identity_report(identity):
    if not isinstance(identity, dict):
        return None
    fields = ("status", "verified", "matched", "score", "model", "match_reason",
              "distance", "threshold", "attempts", "checked_at", "scored_at")
    return dict({key: identity.get(key) for key in fields},
                has_captured_image=bool(identity.get("captured_image_file_id")),
                has_reference_image=bool(identity.get("reference_image_file_id")))


def stop_companion(doc):
    """The owner-authenticated end request stops the phone even without a desktop socket."""
    sid = (doc.get("mobile_proctoring") or {}).get("socket_id")
    if not sid:
        return
    try:
        from extensions import socketio
        socketio.emit("mobile_recording_action", {"action": "stop"}, room=sid)
    except Exception:
        logging.getLogger(__name__).warning("Companion stop notification failed for %s", doc.get("session_id"), exc_info=True)


def evaluation_percentage(evaluation):
    if not isinstance(evaluation, dict):
        return None
    scores = evaluation.get("quantitative_scores") or {}
    if isinstance(scores, dict):
        answer, language = scores.get("answer_score"), scores.get("language_score")
        if isinstance(answer, (int, float)) and isinstance(language, (int, float)):
            return percentage(answer * 0.7 + language * 0.3, normalized=True)
    return percentage(evaluation.get("final_score"))


def cached_answer_result(doc, question, answer):
    previous = doc.get("last_answer") or {}
    if (previous.get("question") == question and previous.get("answer") == answer
            and previous.get("result") and not previous["result"].get("repeated_question")):
        return dict(previous["result"], idempotent_replay=True)
    return None


def json_safe(value):
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return json_safe(asdict(value))
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def merge_usage_summaries(previous, additional):
    result = dict(previous or {})
    for key, value in (additional or {}).items():
        if (key.startswith("total_") or key in {"event_count", "llm_cost_usd", "stt_cost_usd", "tts_cost_usd"}) and isinstance(value, (int, float)):
            result[key] = (result.get(key) or 0) + value
    result["models"] = sorted(set((previous or {}).get("models") or []) | set((additional or {}).get("models") or []))
    return result


def schedule_evaluation_refresh(manager, session, collection, on_result=None):
    """Finish still-running rubrics after returning a truthful partial report."""
    events = list(getattr(session, "evaluation_events", []))
    if not events or getattr(session, "evaluation_refresh_scheduled", False):
        return
    session.evaluation_refresh_scheduled = True

    def refresh():
        try:
            deadline = time.monotonic() + 120
            for event in events:
                if not event.wait(max(0.0, deadline - time.monotonic())):
                    # Close the pending state after a bounded provider wait.
                    # Running workers may finish later, but a report must never
                    # advertise "still processing" indefinitely.
                    for item in session.interview_data:
                        evaluation = item.get("evaluation") or {}
                        if evaluation.get("evaluation_status") == "pending":
                            evaluation["evaluation_status"] = "unavailable"
                    for pending_event in events:
                        pending_event.set()
                    break
            with session.answer_lock:
                session.final_evaluation = None
                evaluation = manager._generate_final_evaluation(session)
                score = evaluation_percentage(evaluation)
            from interview.core.cost_tracker import CostTracker
            additional_usage = CostTracker().end_session(session.session_id, clear_events=True)
            saved = collection.find_one({"session_id": session.session_id}, {"usage_summary": 1}) or {}
            updated = collection.update_one({"session_id": session.session_id, "status": "completed"},
                {"$set": {"evaluation": evaluation, "final_score": score,
                    "interview_score": score, "qa_pairs": json_safe(session.interview_data),
                    "usage_summary": merge_usage_summaries(saved.get("usage_summary"), additional_usage)}})
            if updated.matched_count and on_result:
                on_result(score, evaluation)
        except Exception:
            logging.getLogger(__name__).warning("Deferred interview evaluation failed", exc_info=True)
        finally:
            manager.sessions.pop(session.session_id, None)
    threading.Thread(target=refresh, daemon=True, name="interview-report-refresh").start()
