"""Live account balance using the normal DeepSeek key; no admin key required.

The documented API has no date-ranged costs endpoint. Timeline spend comes
from our recorded request usage, never from subtracting account balances.
"""
import logging
import os
import time
from datetime import datetime
from threading import Lock

import requests

logger = logging.getLogger(__name__)
_lock = Lock()
_cache = {"key": None, "at": 0, "value": None}


def fetch_deepseek_balance():
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not key:
        return {"status": "not_configured", "balances": []}
    base = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    with _lock:
        if _cache["key"] == (key, base) and time.monotonic() - _cache["at"] < 60:
            return _cache["value"]
    try:
        response = requests.get(base + "/user/balance",
                                headers={"Authorization": "Bearer " + key}, timeout=10)
        response.raise_for_status()
        data = response.json()
        value = {"status": "available", "is_available": data.get("is_available"),
                 "balances": data.get("balance_infos", []),
                 "fetched_at": datetime.utcnow().isoformat() + "Z"}
    except Exception as exc:
        # Do not expose headers, response bodies, keys or account details in logs.
        logger.warning("DeepSeek balance fetch failed (%s)", type(exc).__name__)
        value = {"status": "unavailable", "balances": []}
    with _lock:
        _cache.update(key=(key, base), at=time.monotonic(), value=value)
    return value
