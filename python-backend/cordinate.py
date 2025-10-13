import os
from flask import Flask, request, jsonify
from flask_socketio import SocketIO
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import datetime
import uuid
import base64
from bson import ObjectId
import cv2
import numpy as np
from transformers import AutoTokenizer, AutoModel
import torch

# Import configuration
from config.database import db_config
from middleware.cors_middleware import setup_cors

# Import route blueprints
from routes.auth_routes import auth_bp
from routes.profile_routes import profile_bp
from routes.job_routes import job_bp
from routes.application_routes import application_bp
from routes.file_routes import file_bp
from utils.cheating_detection import ProctoringGazeDetector
from utils.interview_system import InterviewSessionManager
# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your-flask-secret-key')

# Initialize extensions
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
cors = setup_cors(app)

# Initialize database
db = db_config.connect()
collections = db_config.get_collections()

# Get collections for interview system
users_collection = collections['users']
interviews_collection = collections['interviews']
applications_collection = collections['applications']

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(job_bp)
app.register_blueprint(application_bp)
app.register_blueprint(file_bp)

# Define a dictionary to hold a detector instance for each session
proctoring_detectors = {}

# --- OPTIMIZATION: Load Similarity Model Once at Startup ---
print("Loading similarity model...")
similarity_model_name = "bert-base-uncased"
similarity_tokenizer = AutoTokenizer.from_pretrained(similarity_model_name)
similarity_model = AutoModel.from_pretrained(similarity_model_name)
print("✅ Similarity model loaded.")

# Initialize interview system with API key and the pre-loaded model
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
interview_manager = InterviewSessionManager(
    groq_api_key=GROQ_API_KEY,
    similarity_model=similarity_model,
    similarity_tokenizer=similarity_tokenizer
)

# === INTERVIEW SYSTEM (REMAINS IN APP.PY) ===
# All interview-related routes and Socket.IO handlers remain here

# Add this dictionary for live sessions
live_sessions = {}

# Define directories for storing files
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
PROCTORING_FOLDER = os.path.join(UPLOAD_FOLDER, "proctoring")

# Ensure folders exist
os.makedirs(PROCTORING_FOLDER, exist_ok=True)
RECORDING_FOLDER = os.path.join(UPLOAD_FOLDER, "recordings")
os.makedirs(RECORDING_FOLDER, exist_ok=True)

app.config["PROCTORING_FOLDER"] = PROCTORING_FOLDER
app.config["RECORDING_FOLDER"] = RECORDING_FOLDER

# Import middleware for interview routes
from middleware.auth_middleware import token_required

# Interview System API Routes
@app.route('/api/interviews/start', methods=['POST'])
@token_required
def start_interview(current_user):
    data = request.json or {}
    
    # Get file paths from the request
    cv_path = data.get('cv_path')
    jd_path = data.get('jd_path')
    application_id = data.get('application_id')

    # Handle single or multiple reference paths from the request
    reference_paths = data.get('reference_paths')
    if not reference_paths:
        reference_path = data.get('reference_path')
        if reference_path:
            reference_paths = [reference_path]

    if not all([cv_path, jd_path, reference_paths]):
        return jsonify({'error': 'cv_path, jd_path, and reference_paths are required'}), 400

    # Create interview session with the provided paths
    session_details = interview_manager.create_session(
        cv_path=cv_path,
        jd_path=jd_path,
        reference_paths=reference_paths  # Corrected keyword argument
    )
    
    # Store session info in database
    interview_id = interviews_collection.insert_one({
        'user_id': str(current_user['_id']),
        'session_id': session_details['session_id'],
        'cv_path': cv_path,
        'jd_path': jd_path,
        'reference_paths': reference_paths,
        'application_id': application_id,
        'status': 'active',
        'created_at': datetime.datetime.utcnow(),
        'updated_at': datetime.datetime.utcnow(),
        'similarity_score': session_details['similarity_score']
    }).inserted_id
    
    return jsonify({
        'interview_id': str(interview_id),
        'session_id': session_details['session_id'],
        'initial_questions': session_details['initial_questions'],
        'similarity_score': session_details['similarity_score']
    })

@app.route('/api/interviews/<session_id>/question', methods=['GET'])
def get_interview_question(session_id):
    return jsonify({
        'current_questions': ['What are your strengths?', 'Describe a challenging project you worked on.']
    })

@app.route('/api/interviews/<session_id>/answer', methods=['POST'])
@token_required
def submit_answer(current_user, session_id):
    data = request.json
    question = data.get('question')
    answer = data.get('answer')
    
    if not question or not answer:
        return jsonify({'error': 'Question and answer are required'}), 400
    
    # Submit answer using new system
    result = interview_manager.submit_answer(session_id, question, answer)
    
    if 'error' in result:
        return jsonify(result), 400
    
    # The new system handles completion and evaluation differently.
    # We don't update the DB here, but in the /end route.
    
    return jsonify(result)

@app.route('/api/interviews/<session_id>/end', methods=['POST'])
@token_required
def end_interview(current_user, session_id):
    # Get the final evaluation from the session manager if it exists
    session = interview_manager.sessions.get(session_id)
    if session and session.get('is_complete'):
        final_evaluation = session.get('evaluation')
    elif session:
        # If ended prematurely, generate evaluation now
        final_evaluation = interview_manager._generate_final_evaluation(session)
    else:
        final_evaluation = {'summary': 'Evaluation could not be computed as session was not found.'}

    # Get final proctoring data from the live session
    session_data = live_sessions.get(session_id, {})
    final_score = session_data.get('proctoring_score', 'N/A')
    manual_infractions = session_data.get('manual_infractions', [])

    # Get the final gaze data from the in-memory detector
    detector = proctoring_detectors.get(session_id)
    gaze_times = detector.gaze_tracker.get_times() if detector else None

    # Update the database record with final data
    interviews_collection.update_one(
        {'session_id': session_id, 'user_id': str(current_user['_id'])},
        {'$set': {
            'status': 'completed',
            'evaluation': final_evaluation,
            'proctoring_score': final_score,
            'manual_infractions': manual_infractions,
            'gaze_metrics': gaze_times,
            'updated_at': datetime.datetime.utcnow()
        }}
    )
    
    # Also update the related application with interview_score if linked
    session_doc = interviews_collection.find_one({'session_id': session_id, 'user_id': str(current_user['_id'])})
    if session_doc and session_doc.get('application_id'):
        try:
            # Use the quantitative score for the application
            numeric_score = final_evaluation.get('quantitative', {}).get('average_relevance_score', 0) * 100
            applications_collection.update_one(
                {'_id': ObjectId(session_doc['application_id'])},
                {'$set': {
                    'interview_score': numeric_score,
                    'status': 'interviewed',
                    'updated_at': datetime.datetime.utcnow()
                }}
            )
        except Exception:
            pass
    
    return jsonify({
        'status': 'interview_ended',
        'evaluation': final_evaluation
    })

# Add this new route
@app.route('/api/interviews/<session_id>/upload-recording', methods=['POST'])
@token_required
def upload_recording(current_user, session_id):
    if 'recording' not in request.files:
        return jsonify({'error': 'No recording file part'}), 400
    
    file = request.files['recording']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        filename = secure_filename(f"{session_id}-{current_user['_id']}.webm")
        filepath = os.path.join(app.config['RECORDING_FOLDER'], filename)
        file.save(filepath)

        # Update the interview record with the path to the recording
        interviews_collection.update_one(
            {'session_id': session_id, 'user_id': str(current_user['_id'])},
            {'$set': {'recording_path': filepath}}
        )
        
        return jsonify({'message': 'Recording uploaded successfully', 'path': filepath}), 200

    return jsonify({'error': 'File upload failed'}), 500


@app.route('/api/interviews', methods=['GET'])
@token_required
def get_user_interviews(current_user):
    user_type = current_user.get('user_type', 'candidate')
    
    if user_type == 'recruiter':
        # Recruiters can see all interviews
        user_interviews = list(interviews_collection.find({}))
    else:
        # Candidates can only see their own interviews
        user_interviews = list(interviews_collection.find({'user_id': str(current_user['_id'])}))
    
    # Format the interviews for JSON response
    formatted_interviews = []
    for interview in user_interviews:
        formatted_interview = {
            'id': str(interview['_id']),
            'session_id': interview['session_id'],
            'status': interview['status'],
            'created_at': interview['created_at'].isoformat(),
            'updated_at': interview['updated_at'].isoformat(),
            'cv_path': interview.get('cv_path'),
            'jd_path': interview.get('jd_path')
        }
        
        # Include user info for recruiters
        if user_type == 'recruiter':
            user_info = users_collection.find_one({'_id': ObjectId(interview['user_id'])})
            if user_info:
                formatted_interview['candidate'] = {
                    'name': user_info['name'],
                    'email': user_info['email']
                }
        
        formatted_interviews.append(formatted_interview)
    
    return jsonify(formatted_interviews)

# ... other imports

@app.route('/api/interviews/<session_id>/register-face', methods=['POST'])
@token_required
def register_face(current_user, session_id):
    data = request.get_json()
    if 'image' not in data:
        return jsonify({'error': 'No image data provided'}), 400
    try:
        header, encoded = data['image'].split(",", 1)
        decoded_image = base64.b64decode(encoded)
        
        # Initialize the session in our live store, including the manual_infractions list
        live_sessions[session_id] = {
            'registered_face': decoded_image, # Corrected: Use decoded_image instead of frame
            'proctoring_score': 100,
            'infractions': {}, 
            'sid': None,
            'manual_infractions': []  # Initialize list for tab/window switch violations
        }
        
        # Update the interview status in the database
        interviews_collection.update_one(
            {'session_id': session_id, 'user_id': str(current_user['_id'])},
            {'$set': {'status': 'active'}}
        )
        
        print(f"✅ Face registered for session: {session_id}. Interview is now active.")
        return jsonify({'message': 'Face registered successfully'}), 200
    except Exception as e:
        print(f"Error during face registration: {e}")
        return jsonify({'error': 'Failed to process image'}), 500

# Add this entire block for WebSocket event handling
@socketio.on('connect')
def handle_connect():
    print(f"🔌 Client connected with sid: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"🔌 Client disconnected with sid: {request.sid}")
    for session_id, data in list(live_sessions.items()):
        if data.get('sid') == request.sid:
            # Clean up both the live session data and the detector instance
            del live_sessions[session_id]
            if session_id in proctoring_detectors:
                del proctoring_detectors[session_id]
            print(f"🧹 Cleaned up live session data and detector for {session_id}")
            break

@socketio.on('start_proctoring')
def handle_start_proctoring(data):
    session_id = data.get('session_id')
    if session_id and session_id in live_sessions:
        live_sessions[session_id]['sid'] = request.sid
        # Initialize the gaze detector for this session
        proctoring_detectors[session_id] = ProctoringGazeDetector()
        print(f"▶️ Live proctoring stream started for session: {session_id}")
    else:
        print(f"⚠️ Attempted to start proctoring for invalid/unregistered session: {session_id}")

@socketio.on('proctoring_frame')
def handle_proctoring_frame(data):
    session_id = data.get('session_id')
    session_data = live_sessions.get(session_id)
    detector = proctoring_detectors.get(session_id)

    if not session_data or not detector: return

    header, encoded = data['image'].split(",", 1)
    frame = cv2.imdecode(np.frombuffer(base64.b64decode(encoded), np.uint8), cv2.IMREAD_COLOR)

    # Pass the frame to your cheating detection logic
    analysis_result = detector.process_frame(frame)

    # Update the session data in memory with real metrics
    session_data['gaze_times'] = analysis_result['gaze_times']

    # Emit the results back to the frontend
    socketio.emit('gaze_data', {
        'session_id': session_id,
        'is_cheating_alert': analysis_result['is_cheating_alert'],
        'gaze_direction': analysis_result['gaze_direction'],
        'gaze_times': analysis_result['gaze_times']
    }, room=session_data['sid'])

# New handler for tab/window switching violations
@socketio.on('proctoring_violation')
def handle_proctoring_violation(data):
    session_id = data.get('session_id')
    violation_type = data.get('type')
    session_data = live_sessions.get(session_id)
    if not session_data:
        print(f"⚠️ Received proctoring violation for unknown session: {session_id}")
        return

    # Log the infraction
    timestamp = datetime.datetime.utcnow().isoformat()
    infraction = {'type': violation_type, 'timestamp': timestamp}
    
    if 'manual_infractions' not in session_data:
        session_data['manual_infractions'] = []
    
    session_data['manual_infractions'].append(infraction)
    
    # Optionally, deduct from the proctoring score for each violation
    session_data['proctoring_score'] = max(0, session_data.get('proctoring_score', 100) - 5) # Deduct 5 points
    
    # print(f"🔴 Tab/Window Switch Violation [Session: {session_id}]: Type: {violation_type} | New Score: {session_data['proctoring_score']:.1f}")

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)