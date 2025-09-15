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
import time

# Import configuration
from config.database import db_config
from middleware.cors_middleware import setup_cors
from flask_cors import CORS

# Import route blueprints
from routes.auth_routes import auth_bp
from routes.profile_routes import profile_bp
from routes.job_routes import job_bp
from routes.application_routes import application_bp
from routes.file_routes import file_bp
from utils.cheating_detection import ProctoringGazeDetector

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "your-flask-secret-key")

# Initialize extensions
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")
CORS(app, origins=["http://localhost:3000"])  # Allow your React app

# Initialize database
db = db_config.connect()
collections = db_config.get_collections()

# Get collections for interview system
users_collection = collections["users"]
interviews_collection = collections["interviews"]
applications_collection = collections["applications"]

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(job_bp)
app.register_blueprint(application_bp)
app.register_blueprint(file_bp)

# Define a dictionary to hold a detector instance for each session
proctoring_detectors = {}

# Initialize interview system with proper configuration
from interview.config.settings import InterviewConfig, LLMConfig, LLMProvider
from interview.core.session_manager import InterviewSessionManager

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Use default configurations but override for GROQ
interview_config = InterviewConfig()
llm_config = LLMConfig()

# Initialize interview session manager with proper config
interview_manager = InterviewSessionManager(
    config=interview_config, llm_config=llm_config
)

# === INTERVIEW SYSTEM (REMAINS IN APP.PY) ===
# All interview-related routes and Socket.IO handlers remain here

# Add this dictionary for live sessions
live_sessions = {}

# Define directories for storing files
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
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
@app.route("/api/interviews/start", methods=["POST"])
@token_required
def start_interview(current_user):
    data = request.json or {}

    # Get file paths from the request
    cv_path = data.get("cv_path")
    jd_path = data.get("jd_path")
    reference_paths = data.get("reference_paths")  # <-- FIX IS HERE
    application_id = data.get("application_id")

    if not all([cv_path, jd_path, reference_paths]):
        return (
            jsonify({"error": "cv_path, jd_path, and reference_paths are required"}),
            400,
        )

    # Create interview session using the correct keyword
    session_details = interview_manager.create_session(
        cv_path=cv_path, jd_path=jd_path, reference_paths=reference_paths
    )

    if "error" in session_details:
        return jsonify(session_details), 400

    # Store session info in database
    interview_id = interviews_collection.insert_one(
        {
            "user_id": str(current_user["_id"]),
            "session_id": session_details["session_id"],
            "cv_path": cv_path,
            "jd_path": jd_path,
            "reference_paths": reference_paths,
            "application_id": application_id,
            "status": "active",
            "similarity_score": 0.8,  # hardcoded for now
            "created_at": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow(),
            "start_time": time.time(),  # Add start time
        }
    ).inserted_id

    return jsonify(
        {
            "interview_id": str(interview_id),
            "session_id": session_details["session_id"],
            "initial_questions": session_details["first_question"],
            "similarity_score": 0.8,  # hardcoded for now
            "conversation_context": session_details.get("conversation_context", {}),
        }
    )


@app.route("/api/interviews/<session_id>/question", methods=["GET"])
def get_interview_question(session_id):
    question_result = interview_manager.get_next_question(session_id)

    if "error" in question_result:
        return jsonify(question_result), 400

    return jsonify(question_result)


@app.route("/api/interviews/<session_id>/answer", methods=["POST"])
@token_required
def submit_answer(current_user, session_id):
    data = request.json
    question = data.get("question")
    answer = data.get("answer")

    if not question or not answer:
        return jsonify({"error": "Question and answer are required"}), 400

    try:
        # Submit answer using new system
        result = interview_manager.submit_answer(session_id, question, answer)
        print(f"response after submitting the answer: {result}")

        if "error" in result:
            return jsonify(result), 400

        # Deep JSON serialization function to handle all types
        def make_json_serializable(obj):
            """Recursively convert an object to be JSON serializable."""
            from enum import Enum
            import datetime

            if isinstance(obj, dict):
                return {
                    key: make_json_serializable(value) for key, value in obj.items()
                }
            elif isinstance(obj, list):
                return [make_json_serializable(item) for item in obj]
            elif isinstance(obj, Enum):
                return obj.value
            elif hasattr(obj, "isoformat"):  # datetime objects
                return obj.isoformat()
            elif hasattr(obj, "__dict__"):  # custom objects with __dict__
                return make_json_serializable(obj.__dict__)
            elif isinstance(obj, (str, int, float, bool, type(None))):
                return obj
            else:
                # Convert other types to string as fallback
                return str(obj)

        # Apply deep serialization to the result
        serializable_result = make_json_serializable(result)

        return jsonify(serializable_result)

    except Exception as e:
        print(f"Error in submit_answer: {str(e)}")
        import traceback

        print(f"Full traceback: {traceback.format_exc()}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


@app.route("/api/interviews/<session_id>/end", methods=["POST"])
@token_required
def end_interview(current_user, session_id):
    # Get the final evaluation from the session manager if it exists
    session = interview_manager.sessions.get(session_id)
    if session and session.is_complete:
        final_evaluation = (
            session.evaluation if hasattr(session, "evaluation") else None
        )
    elif session:
        # If ended prematurely, generate evaluation now
        final_evaluation = interview_manager._generate_final_evaluation(session)
    else:
        final_evaluation = {
            "summary": "Evaluation could not be computed as session was not found."
        }

    # Get final proctoring data from the live session
    session_data = live_sessions.get(session_id, {})
    final_score = session_data.get("proctoring_score", "N/A")
    manual_infractions = session_data.get("manual_infractions", [])

    # Get the final gaze data from the in-memory detector
    detector = proctoring_detectors.get(session_id)
    gaze_times = detector.gaze_tracker.get_times() if detector else None
    suspicious_activity_time = (
        detector.detector.total_suspicious_time if detector else 0
    )

    # Calculate total interview duration
    interview_duration = 0
    session_doc = interviews_collection.find_one(
        {"session_id": session_id, "user_id": str(current_user["_id"])}
    )
    if session_doc and "created_at" in session_doc:
        start_time = session_doc["created_at"]
        end_time = datetime.datetime.utcnow()
        interview_duration = (end_time - start_time).total_seconds()

    # --- NEW: Generate and save the gaze plot ---
    gaze_plot_path = None
    if detector:
        try:
            # Define a unique filename for the plot
            plot_filename = f"{session_id}_gaze_plot.png"
            
            # Call the method from your detector to generate the plot
            detector.generate_gaze_plot(
                output_dir=app.config["PROCTORING_FOLDER"], 
                filename=plot_filename
            )
            
            # Create the full path to be saved in the database
            gaze_plot_path = os.path.join(app.config["PROCTORING_FOLDER"], plot_filename)
            print(f"📈 Gaze plot generated for session {session_id} at {gaze_plot_path}")
        except Exception as e:
            print(f"Error generating gaze plot for session {session_id}: {e}")

    # --- Log the final times to the backend console ---
    print(f"--- Interview {session_id} Ended ---")
    print(f"Total Interview Duration: {round(interview_duration, 2)} seconds")
    print(f"Total Suspicious Gaze Time: {round(suspicious_activity_time, 2)} seconds")
    print(f"------------------------------------")

    # Update the database record with final data
    interviews_collection.update_one(
        {'session_id': session_id, 'user_id': str(current_user['_id'])},
        {'$set': {
            'status': 'completed',
            'evaluation': final_evaluation,
            'proctoring_score': final_score,
            'manual_infractions': manual_infractions,
            'gaze_metrics': gaze_times,
            'gaze_plot_path': gaze_plot_path, # <-- ADDED: Save the plot path
            'updated_at': datetime.datetime.utcnow()
        }}
    )

    # Also update the related application with interview_score if linked
    if session_doc and session_doc.get("application_id"):
        try:
            # Use the quantitative score for the application
            numeric_score = (
                final_evaluation.get("quantitative", {}).get(
                    "average_relevance_score", 0
                )
                * 100
            )
            applications_collection.update_one(
                {"_id": ObjectId(session_doc["application_id"])},
                {
                    "$set": {
                        "interview_score": numeric_score,
                        "status": "interviewed",
                        "updated_at": datetime.datetime.utcnow(),
                    }
                },
            )
        except Exception:
            pass
            
    return jsonify({
        'status': 'interview_ended',
        'evaluation': final_evaluation
    })

# ... (rest of app.py remains the same)


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
        filepath = os.path.join(app.config["RECORDING_FOLDER"], filename)
        file.save(filepath)
        # Update the interview record with the path to the recording
        interviews_collection.update_one(
            {"session_id": session_id, "user_id": str(current_user["_id"])},
            {"$set": {"recording_path": filepath}},
        )

        return (
            jsonify({"message": "Recording uploaded successfully", "path": filepath}),
            200,
        )

    return jsonify({"error": "File upload failed"}), 500


@app.route("/api/interviews", methods=["GET"])
@token_required
def get_user_interviews(current_user):
    user_type = current_user.get("user_type", "candidate")

    if user_type == "recruiter":
        # Recruiters can see all interviews
        user_interviews = list(interviews_collection.find({}))
    else:
        # Candidates can only see their own interviews
        user_interviews = list(
            interviews_collection.find({"user_id": str(current_user["_id"])})
        )

    # Format the interviews for JSON response
    formatted_interviews = []
    for interview in user_interviews:
        formatted_interview = {
            "id": str(interview["_id"]),
            "session_id": interview["session_id"],
            "status": interview["status"],
            "created_at": interview["created_at"].isoformat(),
            "updated_at": interview["updated_at"].isoformat(),
            "cv_path": interview.get("cv_path"),
            "jd_path": interview.get("jd_path"),
        }

        # Include user info for recruiters
        if user_type == "recruiter":
            user_info = users_collection.find_one(
                {"_id": ObjectId(interview["user_id"])}
            )
            if user_info:
                formatted_interview["candidate"] = {
                    "name": user_info["name"],
                    "email": user_info["email"],
                }

        formatted_interviews.append(formatted_interview)

    return jsonify(formatted_interviews)


# ... other imports


@app.route("/api/interviews/<session_id>/register-face", methods=["POST"])
@token_required
def register_face(current_user, session_id):
    data = request.get_json()
    if "image" not in data:
        return jsonify({"error": "No image data provided"}), 400
    try:
        header, encoded = data["image"].split(",", 1)
        decoded_image = base64.b64decode(encoded)

        # Initialize the session in our live store, including the manual_infractions list
        live_sessions[session_id] = {
            "registered_face": decoded_image,  # Corrected: Use decoded_image instead of frame
            "proctoring_score": 100,
            "infractions": {},
            "sid": None,
            "manual_infractions": [],  # Initialize list for tab/window switch violations
        }

        # Update the interview status in the database
        interviews_collection.update_one(
            {"session_id": session_id, "user_id": str(current_user["_id"])},
            {"$set": {"status": "active"}},
        )

        print(f"✅ Face registered for session: {session_id}. Interview is now active.")
        return jsonify({"message": "Face registered successfully"}), 200
    except Exception as e:
        print(f"Error during face registration: {e}")
        return jsonify({"error": "Failed to process image"}), 500


# Add this entire block for WebSocket event handling
@socketio.on("connect")
def handle_connect():
    print(f"🔌 Client connected with sid: {request.sid}")


@socketio.on("disconnect")
def handle_disconnect():
    print(f"🔌 Client disconnected with sid: {request.sid}")
    for session_id, data in list(live_sessions.items()):
        if data.get("sid") == request.sid:
            # Clean up both the live session data and the detector instance
            del live_sessions[session_id]
            if session_id in proctoring_detectors:
                del proctoring_detectors[session_id]
            print(f"🧹 Cleaned up live session data and detector for {session_id}")
            break


@socketio.on("start_proctoring")
def handle_start_proctoring(data):
    session_id = data.get("session_id")
    if session_id and session_id in live_sessions:
        live_sessions[session_id]["sid"] = request.sid
        # Initialize the gaze detector for this session
        proctoring_detectors[session_id] = ProctoringGazeDetector()
        print(f"▶️ Live proctoring stream started for session: {session_id}")
    else:
        print(
            f"⚠️ Attempted to start proctoring for invalid/unregistered session: {session_id}"
        )


@socketio.on("proctoring_frame")
def handle_proctoring_frame(data):
    session_id = data.get("session_id")
    session_data = live_sessions.get(session_id)
    detector = proctoring_detectors.get(session_id)

    if not session_data or not detector:
        return

    header, encoded = data["image"].split(",", 1)
    frame = cv2.imdecode(
        np.frombuffer(base64.b64decode(encoded), np.uint8), cv2.IMREAD_COLOR
    )

    # Pass the frame to your cheating detection logic
    analysis_result = detector.process_frame(frame)

    # Update the session data in memory with real metrics
    session_data["gaze_times"] = analysis_result["gaze_times"]

    # Emit the results back to the frontend
    socketio.emit(
        "gaze_data",
        {
            "session_id": session_id,
            "is_cheating_alert": analysis_result["is_cheating_alert"],
            "gaze_direction": analysis_result["gaze_direction"],
            "gaze_times": analysis_result["gaze_times"],
        },
        room=session_data["sid"],
    )


# New handler for tab/window switching violations
@socketio.on("proctoring_violation")
def handle_proctoring_violation(data):
    session_id = data.get("session_id")
    violation_type = data.get("type")
    session_data = live_sessions.get(session_id)
    if not session_data:
        print(f"⚠️ Received proctoring violation for unknown session: {session_id}")
        return

    # Log the infraction
    timestamp = datetime.datetime.utcnow().isoformat()
    infraction = {"type": violation_type, "timestamp": timestamp}

    if "manual_infractions" not in session_data:
        session_data["manual_infractions"] = []

    session_data["manual_infractions"].append(infraction)

    # Optionally, deduct from the proctoring score for each violation
    session_data["proctoring_score"] = max(
        0, session_data.get("proctoring_score", 100) - 5
    )  # Deduct 5 points

    # print(f"🔴 Tab/Window Switch Violation [Session: {session_id}]: Type: {violation_type} | New Score: {session_data['proctoring_score']:.1f}")


if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
