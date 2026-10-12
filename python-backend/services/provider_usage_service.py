"""One persistent event per successful provider request, across all AI paths.

No prompts, responses, credentials or candidate documents are stored here.
The ledger is separate from action/session summaries to avoid duplicate counts.
"""
import logging
import queue
import threading
from datetime import datetime

from services.ai_pricing_service import model_rates, token_cost_usd

logger = logging.getLogger(__name__)

_events = queue.Queue(maxsize=1024)
_worker_lock = threading.Lock()
_worker = None


def enqueue_provider_request(*args, **kwargs):
    """Keep ledger DB latency off live speech/question delivery (bounded queue)."""
    global _worker
    with _worker_lock:
        if _worker is None or not _worker.is_alive():
            def drain():
                while True:
                    event_args, event_kwargs = _events.get()
                    try:
                        record_provider_request(*event_args, **event_kwargs)
                    finally:
                        _events.task_done()
            _worker = threading.Thread(target=drain, daemon=True, name="provider-usage-ledger")
            _worker.start()
    kwargs.setdefault("occurred_at", datetime.utcnow())
    try:
        _events.put_nowait((args, kwargs))
    except queue.Full:
        # Preserve the billing event instead of silently dropping usage.
        record_provider_request(*args, **kwargs)


def record_provider_request(provider, model, usage, *, service="llm", cost_usd=None,
                            metadata=None, occurred_at=None):
    occurred_at = occurred_at or datetime.utcnow()
    usage = usage or {}
    try:
        from config.database import db_config
        db = db_config.db
        if db is None:
            logger.warning("Provider usage ledger unavailable: database is not connected")
            return
        db["ai_provider_requests"].insert_one({
            "provider": provider, "model": model, "service": service,
            "occurred_at": occurred_at,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "prompt_cache_hit_tokens": usage.get("prompt_cache_hit_tokens"),
            "usage_source": usage.get("usage_source", "missing"),
            "estimated_cost_usd": (cost_usd if service != "llm" else
                                   token_cost_usd(model, usage, occurred_at)),
            "rates": model_rates(model, occurred_at) if service == "llm" else {},
            "metadata": metadata or {},
        })
    except Exception:
        logger.warning("Could not persist provider usage request", exc_info=True)


def provider_costs_for_range(db, start, end):
    if db is None:
        return {}
    rows = db["ai_provider_requests"].aggregate([
        {"$match": {"occurred_at": {"$gte": start, "$lte": end}}},
        {"$group": {
            "_id": "$provider", "request_count": {"$sum": 1},
            "cost_usd": {"$sum": {"$ifNull": ["$estimated_cost_usd", 0]}},
            "prompt_tokens": {"$sum": {"$ifNull": ["$prompt_tokens", 0]}},
            "completion_tokens": {"$sum": {"$ifNull": ["$completion_tokens", 0]}},
            "cached_tokens": {"$sum": {"$ifNull": ["$prompt_cache_hit_tokens", 0]}},
            "unpriced_requests": {"$sum": {"$cond": [
                {"$eq": [{"$ifNull": ["$estimated_cost_usd", None]}, None]}, 1, 0]}},
        }},
    ])
    return {row.pop("_id"): row for row in rows}
