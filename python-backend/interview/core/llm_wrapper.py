import datetime
import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from interview.core.cost_tracker import calculate_cost

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - import safety for environments without SDK
    OpenAI = None

logger = logging.getLogger(__name__)

_client: Optional[Any] = None


def _get_client():
    global _client
    if _client is None:
        if OpenAI is None:
            raise RuntimeError("OpenAI SDK is not installed or failed to import.")
        _client = OpenAI()
    return _client


def _safe_usage_value(usage: Any, key: str) -> Optional[int]:
    if usage is None:
        return None
    if isinstance(usage, dict):
        value = usage.get(key)
    else:
        value = getattr(usage, key, None)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_log_data(
    request_id: str,
    user_id: Optional[str],
    model: str,
    usage: Any,
    cost: Optional[float],
    usage_source: str,
) -> Dict[str, Any]:
    prompt_tokens = _safe_usage_value(usage, "prompt_tokens")
    completion_tokens = _safe_usage_value(usage, "completion_tokens")
    total_tokens = _safe_usage_value(usage, "total_tokens")

    return {
        "request_id": request_id,
        "user_id": user_id,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost": cost,
        "usage_source": usage_source,
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }


def _persist_log(
    log_data: Dict[str, Any],
    logs_collection: Optional[Any] = None,
) -> None:
    if logs_collection is not None:
        try:
            logs_collection.insert_one(log_data)
            return
        except Exception as exc:
            logger.warning("Failed to persist OpenAI cost log to DB: %s", exc)

    logger.info("openai_cost_log=%s", json.dumps(log_data, default=str, sort_keys=True))


def call_llm_with_tracking(
    model: str,
    messages: List[Dict[str, Any]],
    user_id: Optional[str] = None,
    logs_collection: Optional[Any] = None,
) -> Tuple[Any, Optional[float], Dict[str, Any]]:
    """
    Execute OpenAI chat completion and return response + real usage-based cost.

    Actual cost is computed only from response.usage. No manual token estimation.
    """
    client = _get_client()
    response = client.chat.completions.create(model=model, messages=messages)

    usage = getattr(response, "usage", None)
    cost = calculate_cost(model, usage)
    usage_source = "actual" if usage else "missing"
    log_data = _build_log_data(
        request_id=str(uuid.uuid4()),
        user_id=user_id,
        model=model,
        usage=usage,
        cost=cost,
        usage_source=usage_source,
    )
    _persist_log(log_data=log_data, logs_collection=logs_collection)
    return response, cost, log_data


def get_cost_summary(
    logs_collection: Any,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Aggregate tracked request costs. Returns totals and request count.
    """
    if logs_collection is None:
        return {"request_count": 0, "total_cost": 0.0, "user_id": user_id}

    query: Dict[str, Any] = {}
    if user_id:
        query["user_id"] = user_id

    pipeline = [
        {"$match": query},
        {
            "$group": {
                "_id": None,
                "request_count": {"$sum": 1},
                "total_cost": {"$sum": {"$ifNull": ["$cost", 0]}},
            }
        },
    ]
    rows = list(logs_collection.aggregate(pipeline))
    if not rows:
        return {"request_count": 0, "total_cost": 0.0, "user_id": user_id}

    row = rows[0]
    return {
        "request_count": int(row.get("request_count", 0) or 0),
        "total_cost": float(row.get("total_cost", 0.0) or 0.0),
        "user_id": user_id,
    }
