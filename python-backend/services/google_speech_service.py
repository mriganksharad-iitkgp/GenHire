import os
import base64
import wave
import io
from google.cloud import speech
from google.cloud import texttospeech
import logging
from interview.core.cost_tracker import CostTracker

logger = logging.getLogger(__name__)


class GoogleSpeechService:
    def __init__(self):
        self.cost_tracker = CostTracker()
        self.stt_provider = os.getenv("STT_PROVIDER", "groq").strip().lower()
        self.stt_model = os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo")
        self.groq_client = None
        if self.stt_provider == "groq" and os.getenv("GROQ_API_KEY"):
            from groq import Groq
            self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"), timeout=30, max_retries=0)
        import json
        from google.oauth2 import service_account
        try:
            creds_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
            creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            credentials = None
            
            if creds_json and creds_json.strip().startswith("{"):
                try:
                    creds_dict = json.loads(creds_json)
                    credentials = service_account.Credentials.from_service_account_info(creds_dict)
                    logger.info("Google Speech Service: Using JSON credentials from environment variable.")
                except Exception as e:
                    logger.error(f"Failed to parse GOOGLE_APPLICATION_CREDENTIALS_JSON: {e}")
            elif creds_path:
                if creds_path.strip().startswith("{"):
                    try:
                        creds_dict = json.loads(creds_path)
                        credentials = service_account.Credentials.from_service_account_info(creds_dict)
                        logger.info("Google Speech Service: Using JSON credentials from GOOGLE_APPLICATION_CREDENTIALS.")
                    except Exception as e:
                        logger.error(f"Failed to parse JSON from GOOGLE_APPLICATION_CREDENTIALS: {e}")
                elif os.path.exists(creds_path):
                    credentials = service_account.Credentials.from_service_account_file(creds_path)
                    logger.info(f"Google Speech Service: Using credentials from path: {creds_path}")
            
            if credentials is None and not creds_json and not creds_path:
                # Cloud Run/Compute Engine can authenticate using their attached
                # service account without a downloaded private key.
                import google.auth
                credentials, _ = google.auth.default(
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
                logger.info("Google Speech Service: Using Application Default Credentials.")

            if credentials is None:
                raise RuntimeError("Configured Google speech credentials could not be loaded")

            self._credentials = credentials
            self.speech_client = speech.SpeechClient(credentials=credentials) if self.stt_provider == "google" else None
            self.tts_client = texttospeech.TextToSpeechClient(credentials=credentials)
            self.cost_tracker = CostTracker()
            logger.info("✅ Google Speech Service clients initialized successfully.")
        except Exception as e:
            logger.warning(f"Failed to initialize Google Speech Service (features disabled): {e}")
            self.speech_client = None
            self.tts_client = None
            self._credentials = None


    def get_scoped_credentials(self, scopes):
        """Service-account credentials re-scoped for token minting (see the
        /api/speech/token broker); None when speech is unconfigured."""
        if getattr(self, "_credentials", None) is None:
            return None
        from google.auth.credentials import with_scopes_if_required
        return with_scopes_if_required(self._credentials, list(scopes))

    def _estimate_audio_duration(self, audio_content, encoding, sample_rate_hertz):
        """Estimate audio duration in seconds."""
        try:
            # For LINEAR16/WAV we can be precise if it's a valid WAV
            if encoding == "LINEAR16":
                try:
                    with wave.open(io.BytesIO(audio_content), "rb") as wav_file:
                        frames = wav_file.getnframes()
                        rate = wav_file.getframerate()
                        return frames / float(rate)
                except:
                    # Fallback to byte size estimation for raw PCM
                    # 16-bit = 2 bytes per sample
                    return len(audio_content) / (2.0 * sample_rate_hertz)

            # For compressed formats (WEBM/MP3/OGG), we use a rough heuristic
            # or a default minimum for short clips if we can't parse headers easily.
            # Most interview answers are 5-60 seconds.
            # Let's use a byte-to-duration approximation for WebM/Opus (roughly 32kbps)
            # 32000 bits/s = 4000 bytes/s
            return max(1.0, len(audio_content) / 4000.0)
        except Exception as e:
            logger.warning(f"Could not estimate audio duration: {e}")
            return 1.0

    def speech_to_text(
        self,
        audio_content,
        sample_rate_hertz=16000,
        language_code="en-US",
        encoding="WEBM_OPUS",
        session_id=None,
    ):
        """
        Transcribe with configured Groq STT, or explicitly selected legacy Google STT.
        """
        if self.stt_provider == "groq":
            return self._groq_transcribe(audio_content, language_code, encoding, session_id, sample_rate_hertz)
        if not self.speech_client:
            logger.error("Speech client not initialized. Check credentials.")
            return None

        # If audio_content is base64, decode it
        if isinstance(audio_content, str):
            try:
                logger.info(f"Decoding base64 audio (length: {len(audio_content)})")
                audio_content = base64.b64decode(audio_content)
            except Exception as e:
                logger.error(f"Failed to decode base64 audio: {e}")
                return None

        duration = self._estimate_audio_duration(
            audio_content, encoding, sample_rate_hertz
        )

        # Determine encoding based on parameter
        encoding_map = {
            "WEBM_OPUS": speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
            "OGG_OPUS": speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
            "LINEAR16": speech.RecognitionConfig.AudioEncoding.LINEAR16,
            "MP3": speech.RecognitionConfig.AudioEncoding.MP3,
        }

        selected_encoding = encoding_map.get(
            encoding.upper(), speech.RecognitionConfig.AudioEncoding.WEBM_OPUS
        )

        logger.info(
            f"Sending STT request: {len(audio_content)} bytes, {sample_rate_hertz}Hz, {language_code}, encoding: {encoding}, estimated duration: {duration:.2f}s"
        )

        audio = speech.RecognitionAudio(content=audio_content)
        config = speech.RecognitionConfig(
            encoding=selected_encoding,
            sample_rate_hertz=sample_rate_hertz,
            language_code=language_code,
            enable_automatic_punctuation=True,
            model="latest_long",
        )

        try:
            response = self.speech_client.recognize(config=config, audio=audio)
            transcript = ""
            for result in response.results:
                transcript += result.alternatives[0].transcript
            self.cost_tracker.add_stt_usage(
                "interview_stt", duration, model="google-stt", session_id=session_id
            )

            logger.info(f"STT Result: '{transcript}'")
            return transcript.strip()
        except Exception as e:
            logger.error(f"Speech to text transcription failed: {e}")
            return None

    def _groq_transcribe(self, audio_content, language_code, encoding, session_id, sample_rate_hertz=16000):
        if self.groq_client is None:
            raise RuntimeError("Groq STT is not configured; set GROQ_API_KEY")
        if isinstance(audio_content, str):
            audio_content = base64.b64decode(audio_content, validate=True)
        if not audio_content:
            return ""
        suffix = {"WEBM_OPUS": "webm", "OGG_OPUS": "ogg", "MP3": "mp3", "LINEAR16": "wav"}.get(encoding.upper())
        if suffix is None:
            raise ValueError("Unsupported audio encoding")
        # Kiosk sends complete WebM containers. Raw PCM callers need a WAV header.
        if suffix == "wav" and not audio_content.startswith(b"RIFF"):
            output = io.BytesIO()
            with wave.open(output, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(sample_rate_hertz)
                wav.writeframes(audio_content)
            audio_content = output.getvalue()
        response = self.groq_client.audio.transcriptions.create(
            file=("answer." + suffix, audio_content), model=self.stt_model,
            language=language_code.split("-")[0], response_format="verbose_json",
            temperature=0,
        )
        duration = getattr(response, "duration", None)
        duration_source = "actual" if duration is not None else "assumed"
        if duration is None:
            duration = self._estimate_audio_duration(audio_content, encoding, sample_rate_hertz)
        self.cost_tracker.add_stt_usage(
            "interview_stt", float(duration), model=self.stt_model, session_id=session_id
        )
        from services.provider_usage_service import record_provider_request
        from services.ai_pricing_service import groq_stt_cost
        record_provider_request("groq", self.stt_model, {"usage_source": duration_source},
                                service="stt", cost_usd=groq_stt_cost(duration),
                                metadata={"audio_seconds": duration, "session_id": session_id,
                                          "billed_seconds": max(10, duration)})
        return response.text.strip()

    def text_to_speech(
        self,
        text,
        language_code="en-US",
        voice_name="en-US-Standard-C",
        session_id=None,
    ):
        """
        Converts text to speech using Google Cloud Text-to-Speech.
        """
        if not self.tts_client:
            logger.error("TTS client not initialized. Check credentials.")
            return None

        logger.info(f"Sending TTS request: '{text[:50]}...', voice: {voice_name}")

        if "Standard" not in voice_name:
            raise ValueError("S2 Low uses a Google Standard voice")

        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code, name=voice_name
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        try:
            response = self.tts_client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )
            self.cost_tracker.add_tts_usage(
                "interview_tts", len(text), session_id=session_id
            )
            from services.provider_usage_service import record_provider_request
            from interview.core.speech_cost_tracker import calculate_tts_cost
            record_provider_request("gcp", voice_name, {"usage_source": "actual"},
                                    service="tts", cost_usd=calculate_tts_cost(text),
                                    metadata={"tts_characters": len(text), "session_id": session_id})
            logger.info(
                f"TTS Success: {len(response.audio_content)} bytes of audio generated."
            )
            # Return base64 encoded audio
            return base64.b64encode(response.audio_content).decode("utf-8")
        except Exception as e:
            logger.error(f"Text to speech synthesis failed: {e}")
            return None
