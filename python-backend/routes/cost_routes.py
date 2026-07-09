"""Cost-tracking routes: tracked chat, LLM cost summary, STT/TTS cost logging.

Moved verbatim from app.py. Each route is registered under both its legacy
bare path and the /api-prefixed path, exactly as before.
"""

import logging

from flask import Blueprint, jsonify, request

from interview.core.llm_wrapper import call_llm_with_tracking, get_cost_summary
from interview.core.speech_cost_tracker import process_stt, process_tts

logger = logging.getLogger(__name__)

cost_bp = Blueprint("cost", __name__)


def create_cost_routes(db):
    openai_cost_logs_collection = db.get_collection("openai_cost_logs")
    speech_cost_logs_collection = db.get_collection("speech_cost_logs")

    # Direct tracked chat endpoint (actual cost from response.usage only)
    @cost_bp.route("/chat", methods=["POST"])
    @cost_bp.route("/api/chat", methods=["POST"])
    def chat_with_cost_tracking():
        data = request.get_json() or {}
        messages = data.get("messages")
        model = data.get("model", "gpt-4o-mini")
        user_id = data.get("user_id")

        if not isinstance(messages, list) or not messages:
            return jsonify({"error": "messages (non-empty list) is required"}), 400

        try:
            response, cost, log_data = call_llm_with_tracking(
                model=model,
                messages=messages,
                user_id=user_id,
                logs_collection=openai_cost_logs_collection,
            )
        except Exception as exc:
            logger.exception("Tracked chat request failed")
            return jsonify({"error": "LLM request failed", "details": str(exc), "cost": None}), 500

        content = ""
        try:
            # Chain responses are LangChain messages (have .content directly);
            # keep the OpenAI .choices path for compatibility.
            content = getattr(response, "content", "") or ""
            if not content:
                choice = (getattr(response, "choices", None) or [None])[0]
                message = getattr(choice, "message", None) if choice is not None else None
                content = getattr(message, "content", "") if message is not None else ""
        except Exception:
            content = ""

        return jsonify(
            {
                "response": content,
                "cost": cost,
                "request_id": log_data.get("request_id"),
            }
        )

    @cost_bp.route("/cost-summary", methods=["GET"])
    @cost_bp.route("/api/cost-summary", methods=["GET"])
    def cost_summary():
        user_id = request.args.get("user_id")
        summary = get_cost_summary(
            logs_collection=openai_cost_logs_collection,
            user_id=user_id,
        )
        return jsonify(summary), 200

    @cost_bp.route("/stt-cost", methods=["POST"])
    @cost_bp.route("/api/stt-cost", methods=["POST"])
    def stt_cost():
        data = request.get_json() or {}
        cost = process_stt(
            data.get("audio_seconds"),
            user_id=data.get("user_id"),
            logs_collection=speech_cost_logs_collection,
        )
        return jsonify({"cost": cost}), 200

    @cost_bp.route("/tts-cost", methods=["POST"])
    @cost_bp.route("/api/tts-cost", methods=["POST"])
    def tts_cost():
        data = request.get_json() or {}
        cost = process_tts(
            data.get("text"),
            data.get("voice_type", "standard"),
            data.get("user_id"),
            logs_collection=speech_cost_logs_collection,
        )
        return jsonify({"cost": cost}), 200

    return cost_bp
