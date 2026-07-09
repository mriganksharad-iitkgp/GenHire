"""LLM-based face matching between the candidate's identity card and the
webcam capture taken at interview start.

Both images go through the app-wide LLM provider chain
(services/llm_fallback_service.py — order set by LLM_PROVIDER_PRIORITY,
default groq -> gemini -> openai) using vision-capable models per provider:

    FACE_MATCH_GROQ_MODEL    (default meta-llama/llama-4-scout-17b-16e-instruct)
    FACE_MATCH_GEMINI_MODEL  (default gemini-flash-lite-latest)
    FACE_MATCH_OPENAI_MODEL  (default gpt-4o-mini)

The model returns a 0-100 similarity score; the interview may only start when
the score clears FACE_MATCH_THRESHOLD (default 75) AND the model judges them
the same person.

Contract mirrors the previous DeepFace verifier: when every provider fails the
result is {"available": False} and the caller fails OPEN (records the gap for
the recruiter instead of locking candidates out over an outage).
"""

import json
import logging
import os

from services.llm_fallback_service import get_llm_fallback_service

logger = logging.getLogger(__name__)


def get_threshold() -> int:
    try:
        value = int(os.getenv("FACE_MATCH_THRESHOLD", "75"))
    except ValueError:
        value = 75
    return min(max(value, 1), 100)


def get_vision_models() -> dict:
    """Vision-capable model per provider for the face-match task."""
    return {
        "groq": os.getenv("FACE_MATCH_GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"),
        "google": os.getenv("FACE_MATCH_GEMINI_MODEL", "gemini-flash-lite-latest"),
        "openai": os.getenv("FACE_MATCH_OPENAI_MODEL", "gpt-4o-mini"),
    }


_PROMPT = (
    "You are an identity-verification assistant. Image 1 is a photo of an "
    "identity card; image 2 is a live webcam capture. Compare the FACE on the "
    "identity card with the face in the webcam capture and rate how likely "
    "they belong to the same person.\n\n"
    "Account for normal differences (ID photos are older, lower quality, "
    "different lighting/angle). Score 0-100 where 100 means certainly the "
    "same person and 0 means certainly different people. If image 1 does not "
    "contain a readable ID-card face or image 2 does not contain a clear "
    "face, score 0 and explain why in the reason.\n\n"
    'Respond with JSON only: {"similarity_score": <0-100 integer>, '
    '"same_person": <true|false>, "reason": "<one short sentence>"}'
)


def _extract_json(text):
    """Parse the model's JSON, tolerating code fences / surrounding prose."""
    text = (text or "").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"no JSON object in response: {text[:120]!r}")
    return json.loads(text[start : end + 1])


def compare_faces(id_card_bytes, id_card_content_type, capture_bytes):
    """Compare the ID-card face with the live capture via the LLM chain.

    Returns {"available": bool, "matched": bool|None, "score": int|None,
             "threshold": int, "model": str|None, "reason": str|None}.
    """
    threshold = get_threshold()
    result = {
        "available": False,
        "matched": None,
        "score": None,
        "threshold": threshold,
        "model": None,
        "reason": None,
    }

    try:
        chain_result = get_llm_fallback_service().invoke(
            _PROMPT,
            json_mode=True,
            images=[
                (id_card_bytes, id_card_content_type or "image/jpeg"),
                (capture_bytes, "image/jpeg"),
            ],
            model_overrides=get_vision_models(),
        )
        payload = _extract_json(chain_result["content"])
        score = min(max(int(payload.get("similarity_score")), 0), 100)
        result.update(
            {
                "available": True,
                "score": score,
                # Both signals must agree: the numeric score clears the bar
                # AND the model itself judged them the same person.
                "matched": bool(score >= threshold and payload.get("same_person", True)),
                "reason": str(payload.get("reason") or "")[:300] or None,
                "model": f"{chain_result['provider_used']}:{chain_result['model_used']}",
            }
        )
    except Exception as exc:
        logger.error("LLM face match failed across the provider chain: %s", exc)

    return result
