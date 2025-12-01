from flask import Blueprint, request, jsonify
from middleware.auth_middleware import token_required
import os
import json
import base64
from google.cloud import texttospeech
from google.oauth2 import service_account

tts_bp = Blueprint('tts', __name__)

# Initialize Google TTS client with service account
def get_tts_client():
    """Initialize and return Google TTS client using service account credentials"""
    try:
        # Get service account key from environment variable (JSON string or file path)
        # Check both possible variable names
        service_account_info = os.getenv('GOOGLE_TTS_SERVICE_ACCOUNT_KEY') or os.getenv('GOOGLE_TTS_SERVICE_ACCOUNT_JSON')
        
        if not service_account_info:
            raise ValueError("GOOGLE_TTS_SERVICE_ACCOUNT_KEY or GOOGLE_TTS_SERVICE_ACCOUNT_JSON not found in environment variables")
        
        # Try to parse as JSON string first
        try:
            credentials_dict = json.loads(service_account_info)
            credentials = service_account.Credentials.from_service_account_info(credentials_dict)
        except (json.JSONDecodeError, TypeError):
            # If not JSON, treat as file path
            credentials = service_account.Credentials.from_service_account_file(service_account_info)
        
        return texttospeech.TextToSpeechClient(credentials=credentials)
    except Exception as e:
        print(f"Error initializing TTS client: {e}")
        raise

@tts_bp.route('/api/tts/synthesize', methods=['POST'])
@token_required
def synthesize_speech(current_user):
    """
    Synthesize speech from text using Google Cloud TTS
    Returns audio data in the format expected by TalkingHead library
    TalkingHead expects a Google TTS API proxy endpoint format
    """
    try:
        # Get Authorization header (TalkingHead sends JWT token here)
        auth_header = request.headers.get('Authorization', '')
        
        # TalkingHead sends data in Google TTS API format
        data = request.get_json()
        
        # Debug: Log the incoming request
        print(f"DEBUG TTS Request - Headers: {dict(request.headers)}")
        print(f"DEBUG TTS Request - Data: {json.dumps(data, indent=2) if data else 'None'}")
        
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        # Parse Google TTS API format
        # Format: { "input": { "text": "..." }, "voice": { ... }, "audioConfig": { ... } }
        input_data = data.get('input', {})
        if isinstance(input_data, str):
            # Sometimes input is just a string
            text = input_data
        else:
            # Standard format: input is an object with text or ssml
            text = input_data.get('text') or input_data.get('ssml', '')
        
        # Extract voice parameters from Google TTS API format
        voice_data = data.get('voice', {})
        language_code = voice_data.get('languageCode') or voice_data.get('language_code', 'en-GB')
        voice_name = voice_data.get('name', 'en-GB-Standard-A')
        gender = voice_data.get('ssmlGender') or voice_data.get('ssml_gender', 'NEUTRAL')
        
        # Extract audio config (TalkingHead sends OGG-OPUS)
        audio_config_data = data.get('audioConfig', {})
        requested_encoding = audio_config_data.get('audioEncoding', 'OGG_OPUS')
        
        # Check if time pointing is enabled (TalkingHead sends enableTimePointing: [1])
        enable_time_pointing = data.get('enableTimePointing', [])
        wants_time_points = len(enable_time_pointing) > 0 and enable_time_pointing[0] == 1
        
        # Fallback to direct format if nested format not found
        if not text:
            text = data.get('text', '')
        if not language_code or language_code == 'en-GB':
            language_code = data.get('language_code', 'en-GB') or 'en-GB'
        if not voice_name or voice_name == 'en-GB-Standard-A':
            voice_name = data.get('voice_name', 'en-GB-Standard-A') or 'en-GB-Standard-A'
        
        if not text:
            print(f"DEBUG: Received data: {json.dumps(data, indent=2)}")
            return jsonify({'error': 'Text is required. Received data: ' + str(data)}), 400
        
        # Initialize TTS client
        try:
            client = get_tts_client()
        except ValueError as e:
            # Service account not configured
            return jsonify({
                'error': 'Google TTS service account not configured. Please set GOOGLE_TTS_SERVICE_ACCOUNT_KEY in .env file.',
                'details': str(e)
            }), 503  # Service Unavailable
        except Exception as e:
            return jsonify({
                'error': 'Failed to initialize TTS client',
                'details': str(e)
            }), 500
        
        # Configure synthesis input
        # Handle SSML if provided (TalkingHead sends SSML with mark tags)
        if input_data.get('ssml'):
            synthesis_input = texttospeech.SynthesisInput(ssml=input_data.get('ssml'))
            # Extract plain text from SSML for lip-sync (remove SSML tags)
            import re
            plain_text = re.sub(r'<[^>]+>', '', input_data.get('ssml'))
            plain_text = plain_text.replace('&quot;', '"').replace('&apos;', "'")
            text = plain_text.strip()
        else:
            synthesis_input = texttospeech.SynthesisInput(text=text)
        
        # Configure voice parameters
        try:
            ssml_gender = getattr(texttospeech.SsmlVoiceGender, gender.upper(), texttospeech.SsmlVoiceGender.NEUTRAL)
        except:
            ssml_gender = texttospeech.SsmlVoiceGender.NEUTRAL
            
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name,
            ssml_gender=ssml_gender
        )
        
        # Configure audio output - TalkingHead requests OGG-OPUS
        # Map string encoding names to enum values
        encoding_map = {
            'OGG_OPUS': texttospeech.AudioEncoding.OGG_OPUS,
            'OGG-OPUS': texttospeech.AudioEncoding.OGG_OPUS,
            'MP3': texttospeech.AudioEncoding.MP3,
            'LINEAR16': texttospeech.AudioEncoding.LINEAR16
        }
        audio_encoding = encoding_map.get(requested_encoding.upper(), texttospeech.AudioEncoding.OGG_OPUS)
        
        # Get speaking rate and pitch from request
        speaking_rate = audio_config_data.get('speakingRate', 1.0)
        pitch = audio_config_data.get('pitch', 0.0)
        
        audio_config = texttospeech.AudioConfig(
            audio_encoding=audio_encoding,
            sample_rate_hertz=24000,
            speaking_rate=speaking_rate,
            pitch=pitch
        )
        
        # Perform synthesis with time pointing if requested
        # Google TTS API supports enable_time_pointing for SSML mark tags
        try:
            if wants_time_points:
                # Enable time pointing for SSML mark tags
                # The enable_time_pointing parameter should be a list of TimepointType enums
                try:
                    from google.cloud.texttospeech import SynthesizeSpeechRequest
                    timepoint_type = SynthesizeSpeechRequest.TimepointType.TIMEPOINT_TYPE_MARK
                    response = client.synthesize_speech(
                        input=synthesis_input,
                        voice=voice,
                        audio_config=audio_config,
                        enable_time_pointing=[timepoint_type]
                    )
                except (AttributeError, TypeError) as e:
                    # If the API structure is different, try alternative approach
                    print(f"DEBUG: Timepoint API structure issue: {e}")
                    # Try using the method with time_pointing_types parameter
                    try:
                        response = client.synthesize_speech(
                            input=synthesis_input,
                            voice=voice,
                            audio_config=audio_config,
                            time_pointing_types=[texttospeech.SynthesizeSpeechRequest.TimepointType.TIMEPOINT_TYPE_MARK]
                        )
                    except:
                        # Fallback - synthesize without time points
                        print("WARNING: Using fallback without time points")
                        response = client.synthesize_speech(
                            input=synthesis_input,
                            voice=voice,
                            audio_config=audio_config
                        )
            else:
                response = client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice,
                    audio_config=audio_config
                )
        except Exception as synth_error:
            print(f"DEBUG: Synthesis error: {synth_error}")
            # Fallback without time points
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
        
        # Get audio content
        audio_content = response.audio_content
        
        # Get time points if available (word timestamps from SSML marks)
        time_points = []
        if wants_time_points:
            try:
                # Check various possible response structures
                if hasattr(response, 'timepoints') and response.timepoints:
                    for tp in response.timepoints:
                        time_point_data = {}
                        # Try different attribute names
                        if hasattr(tp, 'mark_name'):
                            time_point_data['markName'] = tp.mark_name
                        elif hasattr(tp, 'markName'):
                            time_point_data['markName'] = tp.markName
                        
                        if hasattr(tp, 'time_seconds'):
                            time_point_data['timeSeconds'] = tp.time_seconds
                        elif hasattr(tp, 'timeSeconds'):
                            time_point_data['timeSeconds'] = tp.timeSeconds
                        
                        if time_point_data:
                            time_points.append(time_point_data)
                
                print(f"DEBUG: Extracted {len(time_points)} time points from response")
                
                # Debug: Check response structure
                if not time_points:
                    print(f"DEBUG: No timepoints found. Response has timepoints attr: {hasattr(response, 'timepoints')}")
                    if hasattr(response, 'timepoints'):
                        print(f"DEBUG: timepoints value: {response.timepoints}")
                    
            except Exception as tp_error:
                print(f"DEBUG: Error extracting time points: {tp_error}")
                import traceback
                traceback.print_exc()
        
        # TalkingHead expects the response in Google TTS API format
        audio_base64 = base64.b64encode(audio_content).decode('utf-8')
        
        # Build response matching Google TTS API format
        response_data = {
            'audioContent': audio_base64
        }
        
        # Always include timepoints array (even if empty) when requested
        # This prevents TalkingHead from crashing with "Cannot read properties of undefined"
        if wants_time_points:
            response_data['timepoints'] = time_points if time_points else []
        
        print(f"DEBUG: TTS Success - Text: '{text[:50]}...' (length: {len(text)})")
        print(f"DEBUG: Audio encoding: {audio_encoding}, Time points: {len(time_points)}")
        print(f"DEBUG: Returning audio response, audio length: {len(audio_base64)} chars")
        
        response = jsonify(response_data)
        response.headers['Content-Type'] = 'application/json'
        return response, 200
        
    except Exception as e:
        print(f"Error in TTS synthesis: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to synthesize speech: {str(e)}'}), 500

@tts_bp.route('/api/tts/voices', methods=['GET'])
@token_required
def list_voices(current_user):
    """List available voices from Google TTS"""
    try:
        client = get_tts_client()
        
        # List voices
        voices = client.list_voices()
        
        # Filter English voices
        english_voices = []
        for voice in voices.voices:
            if voice.language_codes:
                for lang_code in voice.language_codes:
                    if lang_code.startswith('en'):
                        english_voices.append({
                            'name': voice.name,
                            'language_code': lang_code,
                            'ssml_gender': voice.ssml_gender.name,
                            'natural_sample_rate_hertz': voice.natural_sample_rate_hertz
                        })
                        break
        
        return jsonify({
            'voices': english_voices
        }), 200
        
    except Exception as e:
        print(f"Error listing voices: {e}")
        return jsonify({'error': f'Failed to list voices: {str(e)}'}), 500

