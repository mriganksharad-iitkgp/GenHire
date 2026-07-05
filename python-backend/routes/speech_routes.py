from flask import Blueprint
from controllers.speech_controller import SpeechController
from middleware.auth_middleware import token_required

speech_bp = Blueprint("speech", __name__)
speech_controller = SpeechController()

# Both endpoints proxy paid Google Cloud Speech APIs, so they require a valid
# session token — they were previously open to anonymous use.


@speech_bp.route("/transcribe", methods=["POST"])
@token_required
def transcribe(current_user):
    """Endpoint for Speech-to-Text transcription."""
    return speech_controller.transcribe_audio()


@speech_bp.route("/synthesize", methods=["POST"])
@token_required
def synthesize(current_user):
    """Endpoint for Text-to-Speech synthesis."""
    return speech_controller.synthesize_text()
