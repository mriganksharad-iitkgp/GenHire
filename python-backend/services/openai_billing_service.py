"""Real OpenAI spend fetch via the official Organization Costs API.

GET https://api.openai.com/v1/organization/costs returns daily cost buckets
for the organization. It requires an ADMIN API key (created under
platform.openai.com → Settings → Organization → Admin keys, with the
`api.usage.read` scope) — the normal project inference key
(OPENAI_API_KEY) is NOT accepted. Set it as OPENAI_ADMIN_API_KEY.

Balance remaining: OpenAI does NOT expose a prepaid-credit balance through
any official API (the old dashboard/billing/credit_grants endpoint only
works with browser session cookies). The owner can mirror the dashboard
figure into OPENAI_CREDIT_BALANCE_USD manually; it is surfaced on the admin
page with a "manually entered" note.

Everything degrades gracefully: missing admin key / network error → None,
and the admin page falls back to the INFRA_MONTHLY_OPENAI_INR placeholder.
"""

import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

_COSTS_URL = "https://api.openai.com/v1/organization/costs"

# Short in-process cache so timeline tweaks on the admin page don't hit the
# OpenAI API repeatedly; cost buckets are daily anyway.
_CACHE_TTL_SECONDS = 600
_cache = {}


def fetch_openai_costs_usd(start_dt, end_dt):
    """Total organization spend in USD for [start_dt, end_dt), summed over
    daily buckets from the official Costs API. Returns float USD or None
    when OPENAI_ADMIN_API_KEY is unset or the request fails."""
    admin_key = (os.getenv("OPENAI_ADMIN_API_KEY") or "").strip()
    if not admin_key:
        return None

    cache_key = (start_dt.isoformat(), end_dt.isoformat())
    hit = _cache.get(cache_key)
    if hit and (time.time() - hit[0]) < _CACHE_TTL_SECONDS:
        return hit[1]

    headers = {"Authorization": f"Bearer {admin_key}"}
    params = {
        "start_time": int(start_dt.timestamp()),
        "end_time": int(end_dt.timestamp()),
        "bucket_width": "1d",
        "limit": 180,
    }

    total_usd = 0.0
    page_guard = 0
    try:
        while True:
            response = requests.get(_COSTS_URL, headers=headers, params=params, timeout=20)
            if response.status_code != 200:
                logger.error(
                    "openai_billing: costs API %s: %s",
                    response.status_code,
                    response.text[:300],
                )
                return None
            payload = response.json()
            for bucket in payload.get("data", []):
                for item in bucket.get("results", []):
                    amount = (item.get("amount") or {}).get("value")
                    if amount is not None:
                        total_usd += float(amount)
            if not payload.get("has_more"):
                break
            params["page"] = payload.get("next_page")
            page_guard += 1
            if page_guard > 20 or not params["page"]:
                break
    except Exception as e:
        logger.error("openai_billing: costs fetch failed: %s", e)
        return None

    _cache[cache_key] = (time.time(), total_usd)
    return total_usd


def get_openai_credit_balance_usd():
    """Manually mirrored prepaid balance (OPENAI_CREDIT_BALANCE_USD) — no
    official API exposes it. Returns float USD or None when unset."""
    raw = (os.getenv("OPENAI_CREDIT_BALANCE_USD") or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        logger.error("openai_billing: OPENAI_CREDIT_BALANCE_USD is not a number: %r", raw)
        return None
