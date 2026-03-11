import os
import base64
from google.cloud import speech
from google.cloud import texttospeech
import logging

logger = logging.getLogger(__name__)

class GoogleSpeechService:
    def __init__(self):
        # The environment variable GOOGLE_APPLICATION_CREDENTIALS should be set
        try:
            creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            logger.info(f"Initializing Google Speech Service. Credentials path: {creds_path}")
            
            if creds_path and not os.path.exists(creds_path):
                logger.error(f"Credentials file NOT FOUND at: {creds_path}")
            
            self.speech_client = speech.SpeechClient()
            self.tts_client = texttospeech.TextToSpeechClient()
            logger.info("✅ Google Speech Service clients initialized successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Google Speech Service: {e}")
            self.speech_client = None
            self.tts_client = None

    def speech_to_text(self, audio_content, sample_rate_hertz=16000, language_code="en-US", encoding="WEBM_OPUS"):
        """
        Converts audio content to text using Google Cloud Speech-to-Text.
        """
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

        # Determine encoding based on parameter
        encoding_map = {
            "WEBM_OPUS": speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
            "OGG_OPUS": speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
            "LINEAR16": speech.RecognitionConfig.AudioEncoding.LINEAR16,
            "MP3": speech.RecognitionConfig.AudioEncoding.MP3,
        }
        
        selected_encoding = encoding_map.get(encoding.upper(), speech.RecognitionConfig.AudioEncoding.WEBM_OPUS)
        
        logger.info(f"Sending STT request: {len(audio_content)} bytes, {sample_rate_hertz}Hz, {language_code}, encoding: {encoding}")
        
        audio = speech.RecognitionAudio(content=audio_content)
        config = speech.RecognitionConfig(
            encoding=selected_encoding,
            sample_rate_hertz=sample_rate_hertz,
            language_code=language_code,
            enable_automatic_punctuation=True,
            model="latest_long"
        )

        try:
            response = self.speech_client.recognize(config=config, audio=audio)
            transcript = ""
            for result in response.results:
                transcript += result.alternatives[0].transcript
            
            logger.info(f"STT Result: '{transcript}'")
            return transcript.strip()
        except Exception as e:
            logger.error(f"Speech to text transcription failed: {e}")
            return None

    def text_to_speech(self, text, language_code="en-US", voice_name="en-US-Standard-C"):
        """
        Converts text to speech using Google Cloud Text-to-Speech.
        """
        if not self.tts_client:
            logger.error("TTS client not initialized. Check credentials.")
            return None

        logger.info(f"Sending TTS request: '{text[:50]}...', voice: {voice_name}")

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
            logger.info(f"TTS Success: {len(response.audio_content)} bytes of audio generated.")
            # Return base64 encoded audio
            return base64.b64encode(response.audio_content).decode("utf-8")
        except Exception as e:
            logger.error(f"Text to speech synthesis failed: {e}")
            return None
