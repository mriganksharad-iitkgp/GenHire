"""
Persistent AI usage telemetry recording for admin analytics transparency.

Stores per-action usage events so analytics can use actual captured values
(prompt/completion tokens, STT seconds, TTS characters) when available.
"""

from datetime import datetime
from typing import Any, Dict, Optional


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _clean_source(source: Optional[Dict[str, Any]]) -> Dict[str, str]:
    source = source or {}
    return {
        "type": str(source.get("type") or ""),
        "id": str(source.get("id") or ""),
        "label": str(source.get("label") or ""),
    }


def record_usage_event(
    db_collections: Dict[str, Any],
    *,
    action_type: str,
    actor_type: str,
    actor_id: Optional[str],
    model: str,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    stt_seconds: Optional[float] = None,
    tts_characters: Optional[int] = None,
    usage_source: str = "assumed",
    source: Optional[Dict[str, Any]] = None,
    occurred_at: Optional[datetime] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Insert one usage telemetry event. Swallows errors to avoid write-path disruption."""

    try:
        users_collection = db_collections.get("users")
        if users_collection is None:
            return

        events_collection = users_collection.database.get_collection("ai_usage_events")
        if events_collection is None:
            return

        event_doc = {
            "action_type": str(action_type or ""),
            "actor_type": str(actor_type or ""),
            "actor_id": str(actor_id or ""),
            "model": str(model or ""),
            "prompt_tokens": _to_int(prompt_tokens, 0),
            "completion_tokens": _to_int(completion_tokens, 0),
            "stt_seconds": _to_float(stt_seconds, 0.0),
            "tts_characters": _to_int(tts_characters, 0),
            "usage_source": "actual" if usage_source == "actual" else "assumed",
            "source": _clean_source(source),
            "occurred_at": occurred_at or datetime.utcnow(),
            "metadata": metadata or {},
            "created_at": datetime.utcnow(),
        }

        events_collection.insert_one(event_doc)
    except Exception:
        # Keep telemetry best-effort so primary workflow cannot fail.
        return


def extract_usage_from_response(response: Any) -> Dict[str, Any]:
    """Normalize SDK/LangChain usage, preserving zero tokens and cache counts."""
    usage = {"prompt_tokens": None, "completion_tokens": None, "usage_source": "assumed"}
    if response is None:
        return usage
    raw = getattr(response, "usage", None)
    if hasattr(raw, "model_dump"):
        raw = raw.model_dump()
    meta = getattr(response, "response_metadata", {}) or {}
    payloads = [raw, meta.get("token_usage"), meta.get("usage"),
                meta.get("usage_metadata"), getattr(response, "usage_metadata", None)]
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        for target, aliases in (("prompt_tokens", ("prompt_tokens", "input_tokens", "prompt_token_count")),
                                ("completion_tokens", ("completion_tokens", "output_tokens", "candidates_token_count"))):
            if usage[target] is None:
                for alias in aliases:
                    if payload.get(alias) is not None:
                        usage[target] = int(payload[alias])
                        break
        cached = payload.get("prompt_cache_hit_tokens")
        if cached is None:
            cached = (payload.get("prompt_tokens_details") or {}).get("cached_tokens")
        if cached is None:
            cached = (payload.get("input_token_details") or {}).get("cache_read")
        if cached is not None and "prompt_cache_hit_tokens" not in usage:
            usage["prompt_cache_hit_tokens"] = int(cached)
        if payload.get("prompt_cache_miss_tokens") is not None:
            usage["prompt_cache_miss_tokens"] = int(payload["prompt_cache_miss_tokens"])
    if usage["prompt_tokens"] is not None and usage["completion_tokens"] is not None:
        usage["usage_source"] = "actual"
    return usage
