import datetime
import json
import logging
import math
import uuid
from typing import Any, Dict, Optional

from .pricing import PRICING

logger = logging.getLogger(__name__)


def calculate_stt_cost(audio_seconds: Any) -> Optional[float]:
    if audio_seconds is None:
        return None
    try:
        seconds = float(audio_seconds)
    except (TypeError, ValueError):
        return None
    if seconds < 0:
        return None
    if seconds == 0:
        return 0.0

    price_per_15s = float(PRICING["gcp_stt"]["default"])
    billed_units = math.ceil(seconds / 15.0)
    return billed_units * price_per_15s


def calculate_tts_cost(text: Any, voice_type: str = "standard") -> Optional[float]:
    if text is None:
        return None
    if not isinstance(text, str):
        return None
    if text == "":
        return 0.0

    normalized_voice = str(voice_type or "standard").lower()
    price = PRICING["gcp_tts"].get(normalized_voice, PRICING["gcp_tts"]["standard"])
    return len(text) * float(price)


def calculate_tts_cost_from_characters(
    characters: Any, voice_type: str = "standard"
) -> Optional[float]:
    if characters is None:
        return None
    try:
        count = int(characters)
    except (TypeError, ValueError):
        return None
    if count < 0:
        return None
    if count == 0:
        return 0.0

    normalized_voice = str(voice_type or "standard").lower()
    price = PRICING["gcp_tts"].get(normalized_voice, PRICING["gcp_tts"]["standard"])
    return count * float(price)


def log_cost(
    service: str,
    cost: Optional[float],
    metadata: Optional[Dict[str, Any]] = None,
    logs_collection: Any = None,
) -> Dict[str, Any]:
    log_entry = {
        "request_id": str(uuid.uuid4()),
        "service": service,
        "cost": cost,
        "metadata": metadata or {},
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }

    if logs_collection is not None:
        try:
            logs_collection.insert_one(log_entry)
            return log_entry
        except Exception as exc:
            logger.warning("Failed to persist speech cost log to DB: %s", exc)

    logger.info("speech_cost_log=%s", json.dumps(log_entry, default=str, sort_keys=True))
    return log_entry


def process_stt(
    audio_seconds: Any,
    user_id: Optional[str] = None,
    logs_collection: Any = None,
) -> Optional[float]:
    cost = calculate_stt_cost(audio_seconds)
    billed_seconds = 0
    if cost is not None:
        try:
            seconds = float(audio_seconds)
            billed_seconds = math.ceil(seconds / 15.0) * 15 if seconds > 0 else 0
        except (TypeError, ValueError):
            billed_seconds = 0

    log_cost(
        "gcp_stt",
        cost,
        {
            "user_id": user_id,
            "audio_seconds": audio_seconds,
            "billed_seconds": billed_seconds,
        },
        logs_collection=logs_collection,
    )
    return cost


def process_tts(
    text: Any,
    voice_type: str = "standard",
    user_id: Optional[str] = None,
    logs_collection: Any = None,
) -> Optional[float]:
    cost = calculate_tts_cost(text, voice_type)
    characters = len(text) if isinstance(text, str) else None
    log_cost(
        "gcp_tts",
        cost,
        {
            "user_id": user_id,
            "characters": characters,
            "voice_type": voice_type,
        },
        logs_collection=logs_collection,
    )
    return cost
