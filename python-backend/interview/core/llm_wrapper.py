import datetime
import json
import logging
import threading
import uuid
from typing import Any, Dict, List, Optional, Tuple

from interview.core.cost_tracker import calculate_cost
from services.llm_fallback_service import get_llm_fallback_service

logger = logging.getLogger(__name__)


def _to_langchain_messages(messages: List[Dict[str, Any]]):
    """OpenAI-style role dicts -> LangChain messages (chain input)."""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    converted = []
    for message in messages or []:
        role = (message.get("role") or "user").lower()
        content = message.get("content") or ""
        if role == "system":
            converted.append(SystemMessage(content=content))
        elif role == "assistant":
            converted.append(AIMessage(content=content))
        else:
            converted.append(HumanMessage(content=content))
    return converted


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
    """Fire-and-forget cost log persistence so LLM calls don't block on DB I/O."""
    if logs_collection is not None:
        def _insert():
            try:
                logs_collection.insert_one(log_data)
            except Exception as exc:
                logger.warning("Failed to persist OpenAI cost log to DB: %s", exc)
        threading.Thread(target=_insert, daemon=True).start()
        return

    logger.info("openai_cost_log=%s", json.dumps(log_data, default=str, sort_keys=True))


def call_llm_with_tracking(
    model: str,
    messages: List[Dict[str, Any]],
    user_id: Optional[str] = None,
    logs_collection: Optional[Any] = None,
) -> Tuple[Any, Optional[float], Dict[str, Any]]:
    """
    Execute configured provider chat completion and return response + real usage-based cost.

    Actual cost is computed only from response.usage. No manual token estimation.
    """
    # `model` is honored as the OpenAI-leg model; the actual provider follows
    # LLM_PROVIDER_PRIORITY. The cost log records whichever model answered.
    result = get_llm_fallback_service().invoke(
        _to_langchain_messages(messages),
        model_overrides={"deepseek": model} if model and model.startswith("deepseek-") else None,
    )
    response = result["raw_response"]
    model_used = f"{result['provider_used']}:{result['model_used']}"

    usage = result.get("usage")
    cost = calculate_cost(result["model_used"], usage)
    usage_source = (usage or {}).get("usage_source") or ("actual" if usage else "missing")
    log_data = _build_log_data(
        request_id=str(uuid.uuid4()),
        user_id=user_id,
        model=model_used,
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
