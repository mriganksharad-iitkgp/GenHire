from flask import Blueprint
from controllers.speech_controller import SpeechController

speech_bp = Blueprint("speech", __name__)
speech_controller = SpeechController()

@speech_bp.route("/transcribe", methods=["POST"])
def transcribe():
    """Endpoint for Speech-to-Text transcription."""
    return speech_controller.transcribe_audio()

@speech_bp.route("/synthesize", methods=["POST"])
def synthesize():
    """Endpoint for Text-to-Speech synthesis."""
    return speech_controller.synthesize_text()
