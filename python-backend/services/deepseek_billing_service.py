"""Live account balance using the normal DeepSeek key; no admin key required.

The documented API has no date-ranged costs endpoint. Timeline spend comes
from our recorded request usage, never from subtracting account balances.
"""
import logging
import os
from datetime import datetime
from services.shared_cache import cache

import requests

logger = logging.getLogger(__name__)


def fetch_deepseek_balance():
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not key:
        return {"status": "not_configured", "balances": []}
    base = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return cache.remember('deepseek-balance', [key, base], lambda: _fetch_balance(key, base), 60) or {"status": "unavailable", "balances": []}


def _fetch_balance(key, base):
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
    return value
