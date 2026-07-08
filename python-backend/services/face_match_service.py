"""LLM-based face matching between the candidate's identity card and the
webcam capture taken at interview start.

Both images go to a vision-capable LLM which returns a 0-100 similarity score
for the person on the ID versus the person in the capture; the interview may
only start when the score clears FACE_MATCH_THRESHOLD (default 75).

Providers: Groq (default — llama-4-scout, same key that runs the interview
engine) with OpenAI as fallback, both speaking the OpenAI chat-completions
image_url shape. Order configurable via FACE_MATCH_PROVIDER.

Contract mirrors the previous DeepFace verifier: when every provider fails the
result is {"available": False} and the caller fails OPEN (records the gap for
the recruiter instead of locking candidates out over an outage).
"""

import base64
import json
import logging
import os

logger = logging.getLogger(__name__)

_clients = {}


def _get_client(provider):
    if provider not in _clients:
        if provider == "groq":
            from groq import Groq

            _clients[provider] = Groq()
        else:
            from openai import OpenAI

            _clients[provider] = OpenAI()
    return _clients[provider]


def get_provider_chain():
    preferred = (os.getenv("FACE_MATCH_PROVIDER", "groq") or "groq").strip().lower()
    if preferred not in ("groq", "openai"):
        preferred = "groq"
    return [preferred] + [p for p in ("groq", "openai") if p != preferred]


def get_model(provider):
    if provider == "groq":
        return os.getenv("FACE_MATCH_GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
    return os.getenv("FACE_MATCH_OPENAI_MODEL", os.getenv("FACE_MATCH_MODEL", "gpt-4o-mini"))


def get_threshold() -> int:
    try:
        value = int(os.getenv("FACE_MATCH_THRESHOLD", "75"))
    except ValueError:
        value = 75
    return min(max(value, 1), 100)


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


def _data_url(image_bytes, content_type):
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{content_type or 'image/jpeg'};base64,{encoded}"


def _extract_json(text):
    """Parse the model's JSON, tolerating code fences / surrounding prose."""
    text = (text or "").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"no JSON object in response: {text[:120]!r}")
    return json.loads(text[start : end + 1])


def _ask_provider(provider, id_card_bytes, id_card_content_type, capture_bytes):
    client = _get_client(provider)
    model = get_model(provider)
    kwargs = {}
    if provider == "openai":
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        max_tokens=200,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": _data_url(id_card_bytes, id_card_content_type)},
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": _data_url(capture_bytes, "image/jpeg")},
                    },
                ],
            }
        ],
        **kwargs,
    )
    payload = _extract_json(response.choices[0].message.content)
    score = min(max(int(payload.get("similarity_score")), 0), 100)
    return score, payload


def compare_faces(id_card_bytes, id_card_content_type, capture_bytes):
    """Compare the ID-card face with the live capture via the vision LLM.

    Returns {"available": bool, "matched": bool|None, "score": int|None,
             "threshold": int, "model": str, "reason": str|None}.
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

    for provider in get_provider_chain():
        try:
            score, payload = _ask_provider(
                provider, id_card_bytes, id_card_content_type, capture_bytes
            )
            result.update(
                {
                    "available": True,
                    "score": score,
                    # Both signals must agree: the numeric score clears the
                    # bar AND the model judged them the same person.
                    "matched": bool(score >= threshold and payload.get("same_person", True)),
                    "reason": str(payload.get("reason") or "")[:300] or None,
                    "model": f"{provider}:{get_model(provider)}",
                }
            )
            return result
        except Exception as exc:
            logger.error("LLM face match via %s failed: %s", provider, exc)

    return result
