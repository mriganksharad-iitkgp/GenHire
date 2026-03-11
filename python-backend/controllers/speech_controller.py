from flask import request, jsonify
from services.google_speech_service import GoogleSpeechService
import logging

logger = logging.getLogger(__name__)

class SpeechController:
    def __init__(self):
        self.speech_service = GoogleSpeechService()

    def transcribe_audio(self):
        """
        API endpoint to transcribe audio from base64 string.
        """
        data = request.json
        if not data:
            logger.error("No JSON data in transcribe request")
            return jsonify({"error": "No data provided"}), 400

        audio_base64 = data.get("audio_base64")
        if not audio_base64:
            logger.error("No audio_base64 in transcribe request")
            return jsonify({"error": "No audio content provided"}), 400

        try:
            # Optionally handle parameters from the request
            sample_rate_hertz = int(data.get("sample_rate_hertz", 16000))
            language_code = data.get("language_code", "en-US")
            encoding = data.get("encoding", "WEBM_OPUS")

            logger.info(f"Received transcription request: {len(audio_base64)} chars base64, encoding: {encoding}")
            transcript = self.speech_service.speech_to_text(
                audio_base64, sample_rate_hertz, language_code, encoding
            )

            if transcript is not None:
                return jsonify({"transcript": transcript})
            else:
                logger.error("Speech service returned None for transcript")
                return jsonify({"error": "Failed to transcribe audio"}), 500
        except Exception as e:
            logger.error(f"Error in transcribe_audio endpoint: {e}")
            return jsonify({"error": str(e)}), 500

    def synthesize_text(self):
        """
        API endpoint to synthesize text to speech as base64 audio.
        """
        data = request.json
        if not data:
            logger.error("No JSON data in synthesize request")
            return jsonify({"error": "No data provided"}), 400

        text = data.get("text")
        if not text:
            logger.error("No text in synthesize request")
            return jsonify({"error": "No text provided"}), 400

        try:
            # Optionally handle parameters from the request
            language_code = data.get("language_code", "en-US")
            voice_name = data.get("voice_name", "en-US-Standard-C")

            logger.info(f"Received synthesis request for text: '{text[:50]}...'")
            audio_base64 = self.speech_service.text_to_speech(
                text, language_code, voice_name
            )

            if audio_base64:
                return jsonify({"audio_base64": audio_base64})
            else:
                logger.error("Speech service returned None for audio_base64")
                return jsonify({"error": "Failed to synthesize speech"}), 500
        except Exception as e:
            logger.error(f"Error in synthesize_text endpoint: {e}")
            return jsonify({"error": str(e)}), 500
