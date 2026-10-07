"""Shared, configurable provider prices; USD per million tokens unless stated.

DeepSeek defaults are the documented Flash peak rates as of 2026-10-05.
The request ledger snapshots rates so later configuration changes do not
reprice past requests. Estimates are not provider invoices.
"""
import math
import os
from datetime import datetime, timezone


def _rate(name, default):
    try:
        value = float(os.getenv(name, default))
        return value if math.isfinite(value) and value >= 0 else default
    except (TypeError, ValueError):
        return default


def deepseek_rates(occurred_at=None):
    when = occurred_at or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    when = when.astimezone(timezone.utc)
    mode = os.getenv("DEEPSEEK_PRICING_MODE", "peak").lower()
    # Auto follows UTC weekday peak windows. Chinese public holidays are not
    # available locally; peak (default) is a conservative estimate on them.
    peak = when.weekday() < 5 and (1 <= when.hour < 4 or 6 <= when.hour < 10)
    multiplier = 0.5 if mode == "off_peak" or (mode == "auto" and not peak) else 1.0
    return {
        "input": _rate("DEEPSEEK_INPUT_USD_PER_1M", 0.30) * multiplier,
        "cached_input": _rate("DEEPSEEK_CACHED_INPUT_USD_PER_1M", 0.006) * multiplier,
        "output": _rate("DEEPSEEK_OUTPUT_USD_PER_1M", 1.20) * multiplier,
        "pricing_mode": mode,
    }


def model_rates(model, occurred_at=None):
    name = str(model or "").split(":")[-1]
    if name in ("deepseek-flash", "deepseek-v4-flash", "deepseek-v4.1-flash"):
        return deepseek_rates(occurred_at)
    if name == "gemini-3.1-flash-lite":
        return {"input": _rate("GEMINI_INPUT_USD_PER_1M", 0.25),
                "output": _rate("GEMINI_OUTPUT_USD_PER_1M", 1.50)}
    if name == "openai/gpt-oss-20b":
        return {"input": _rate("GROQ_INPUT_USD_PER_1M", 0.075),
                "output": _rate("GROQ_OUTPUT_USD_PER_1M", 0.30)}
    # Preserve historical pricing for previously recorded models.
    from interview.core.pricing import PRICING
    rates = PRICING.get(name)
    if rates and "input" in rates:
        return {k: rates[k] * 1_000_000 for k in ("input", "output")}
    historical = {
        "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
        "gemini-flash-lite-latest": {"input": 0.075, "output": 0.30},
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    }
    if name in historical:
        return historical[name]
    return None


def token_cost_usd(model, usage, occurred_at=None):
    rates = model_rates(model, occurred_at)
    if not rates or not usage:
        return None
    prompt = usage.get("prompt_tokens")
    output = usage.get("completion_tokens")
    if prompt is None or output is None:
        return None
    prompt, output = max(0, int(prompt)), max(0, int(output))
    cached = min(prompt, max(0, int(usage.get("prompt_cache_hit_tokens") or 0)))
    return ((prompt - cached) * rates["input"] +
            cached * rates.get("cached_input", rates["input"]) +
            output * rates["output"]) / 1_000_000


def groq_stt_hourly_rate():
    return _rate("GROQ_STT_USD_PER_HOUR", 0.04)


def groq_stt_cost(seconds):
    # Groq bills each transcription request for at least 10 seconds.
    return max(10.0, float(seconds)) / 3600 * groq_stt_hourly_rate()
