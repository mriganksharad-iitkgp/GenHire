import os
import warnings
# Suppress pydantic warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Optional: add console handler if missing
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(ch)
# Suppress TensorFlow and mediapipe warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # 0=all, 1=info, 2=warn, 3=error
warnings.filterwarnings("ignore", category=UserWarning)

from flask import Flask, request, jsonify
from flask_socketio import SocketIO
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import datetime
import uuid
import base64
from bson import ObjectId

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
from routes.practice_routes import practice_bp
from routes.cv_routes import create_cv_routes
from routes.admin_routes import admin_bp, init_admin_routes

from services.cv_scoring_service import CVScoringService
from services.interview_quota_service import (
    get_recruiter_interview_quota,
    consume_interview_credit,
)
from controllers.admin_controller import AdminController

# Optional import - RecordingAnalyzer has heavy dependencies that may conflict
# try:
#     from gpu_intensive_task.recording_analysis_service import RecordingAnalyzer
#     RECORDING_ANALYZER_AVAILABLE = True
#     print("✓ RecordingAnalyzer loaded successfully")
# except Exception as e:
#     print(f"⚠ Warning: RecordingAnalyzer not available: {str(e)[:100]}")
#     RecordingAnalyzer = None
#     RECORDING_ANALYZER_AVAILABLE = False
RECORDING_ANALYZER_AVAILABLE = False


# Import payment module
try:
    from payment_module.routes import payment_bp, init_payment_routes
    PAYMENT_MODULE_AVAILABLE = True
    print("[OK] Payment module loaded successfully")
except ImportError as e:
    print(f"[WARN] Payment module not available: {e}")
    PAYMENT_MODULE_AVAILABLE = False

# Load environment variables
load_dotenv()



# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "your-flask-secret-key")

# Initialize extensions
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# Configure CORS to allow all origins
CORS(app, 
     resources={r"/*": {
         "origins": "*",
         "allow_headers": ["Content-Type", "Authorization", "Access-Control-Allow-Credentials"],
         "supports_credentials": True,
         "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
         "expose_headers": ["Content-Type", "Authorization"]
     }})

# Handle preflight OPTIONS requests
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = app.make_default_options_response()
        headers = response.headers
        headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS, PATCH'
        headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Access-Control-Allow-Credentials'
        headers['Access-Control-Allow-Credentials'] = 'true'
        return response

# Add CORS headers to all responses
@app.after_request
def after_request(response):
    origin = request.headers.get('Origin')
    if origin:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS, PATCH'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response

# Initialize database
db = db_config.connect()
collections = db_config.get_collections()

# Get collections for interview system
users_collection = collections["users"]
interviews_collection = collections["interviews"]
applications_collection = collections["applications"]
jobs_collection = collections["jobs"]

# Initialize and start background processor for CV scoring
from services.background_processor import get_background_processor
background_processor = get_background_processor()
background_processor.start()
logger.info("[OK] Background processor started for async CV scoring")

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(job_bp)
app.register_blueprint(application_bp)
app.register_blueprint(file_bp)
app.register_blueprint(practice_bp)

# Register CV routes (requires collections, so created after database initialization)
cv_bp = create_cv_routes(collections)
app.register_blueprint(cv_bp, url_prefix='/api/cv')

# Initialize and register admin routes
admin_controller = AdminController(collections)
init_admin_routes(admin_controller)
app.register_blueprint(admin_bp, url_prefix='/api/admin')
logger.info("[OK] Admin routes registered at /api/admin")

# Define a dictionary to hold a detector instance for each session
# Define a dictionary to hold a detector instance for each session
# proctoring_detectors = {}  # Moved to separate service

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
# Add this dictionary for live sessions
# live_sessions = {} # Moved to proctoring_server

# Define directories for storing files
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
PROCTORING_FOLDER = os.path.join(UPLOAD_FOLDER, "proctoring")

# Ensure folders exist
os.makedirs(PROCTORING_FOLDER, exist_ok=True)
RECORDING_FOLDER = os.path.join(UPLOAD_FOLDER, "recordings")
M_RECORDING_FOLDER = os.path.join(UPLOAD_FOLDER, "mobile_recordings")
os.makedirs(RECORDING_FOLDER, exist_ok=True)
os.makedirs(M_RECORDING_FOLDER, exist_ok=True)  
TMP_FOLDER = os.path.join(UPLOAD_FOLDER, "tmp")
os.makedirs(TMP_FOLDER, exist_ok=True)

app.config["PROCTORING_FOLDER"] = PROCTORING_FOLDER
app.config["RECORDING_FOLDER"] = RECORDING_FOLDER
app.config["TMP_FOLDER"] = TMP_FOLDER

# Import middleware for interview routes
from middleware.auth_middleware import token_required

# Optional CV formatter (does not run AI scoring here)
try:
    cv_service = CVScoringService()
except Exception as e:
    print(f"Warning initializing CVScoringService for formatting: {e}")
    cv_service = None

# Initialize RecordingAnalyzer if available
if RECORDING_ANALYZER_AVAILABLE and RecordingAnalyzer is not None:
    try:
        recording_analyzer = RecordingAnalyzer()
        print("[OK] RecordingAnalyzer initialized successfully")
    except Exception as e:
        print(f"[WARN] Warning initializing RecordingAnalyzer: {e}")
        recording_analyzer = None
else:
    recording_analyzer = None
    print("ℹ RecordingAnalyzer not available - recording analysis features disabled")


def _format_cv_from_details(cv_details: dict) -> str:
    parts = []
    if not isinstance(cv_details, dict):
        return ""
    pi = cv_details.get("personalInfo", {})
    if pi:
        parts.append("PERSONAL INFORMATION")
        for k in ["fullName","email","phone","location","linkedin","github"]:
            v = pi.get(k)
            if v: parts.append(str(v))
    if cv_details.get("professionalSummary"):
        parts.append(cv_details.get("professionalSummary"))
    for edu in cv_details.get("education", []) or []:
        line = " ".join(filter(None, [edu.get("degree"), edu.get("institution"), str(edu.get("year") or "")]))
        if line.strip(): parts.append(line)
        if edu.get("description"): parts.append(edu["description"])
    for exp in cv_details.get("workExperience", []) or []:
        line = " ".join(filter(None, [exp.get("jobTitle"), exp.get("company"), str(exp.get("duration") or "")]))
        if line.strip(): parts.append(line)
        if exp.get("description"): parts.append(exp["description"])
    skills = cv_details.get("skills", {})
    for key in ["technical", "soft", "languages"]:
        arr = skills.get(key)
        if arr: parts.append(", ".join(arr))
    for proj in cv_details.get("projects", []) or []:
        if proj.get("title"): parts.append(proj["title"])
        if proj.get("description"): parts.append(proj["description"])
    return "\n".join(parts)

def _format_job_from_doc(job: dict) -> str:
    if not isinstance(job, dict):
        return ""
    parts = []
    for k in ["title","company","department","location","type","experience","salary"]:
        v = job.get(k)
        if v: parts.append(str(v))
    if job.get("description"): parts.append(job["description"])
    for sec in ["skills","responsibilities","requirements","benefits"]:
        vals = job.get(sec) or []
        if isinstance(vals, list) and vals:
            parts.append("\n".join([str(x) for x in vals]))
    return "\n".join(parts)


# Initialize payment module
if PAYMENT_MODULE_AVAILABLE:
    try:
        init_payment_routes(db)
        app.register_blueprint(payment_bp)
        print("[OK] Payment routes registered at /api/payment")
    except Exception as e:
        print(f"[WARN] Failed to initialize payment module: {e}")

# health check route
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

# basic index route
@app.route("/")
def index():
    return "Welcome to the Interview System API. Please use the /api endpoints to interact with the system."


# Interview System API Routes
@app.route("/api/interviews/start", methods=["POST"])
@token_required
def start_interview(current_user):
    data = request.json or {}
    application_id = data.get("application_id")
    if not application_id:
        return jsonify({"error": "application_id is required"}), 400

    try:
        app_doc = applications_collection.find_one({"_id": ObjectId(application_id)})
    except Exception:
        return jsonify({"error": "Invalid application_id"}), 400

    if not app_doc:
        return jsonify({"error": "Application not found"}), 404

    app_student_id = str(app_doc.get("student_id", ""))
    current_user_id = str(current_user.get("_id", ""))
    if app_student_id != current_user_id:
        return jsonify({"error": "Unauthorized"}), 403

    student = current_user
    job = jobs_collection.find_one({"_id": ObjectId(app_doc["job_id"])})

    # --- Interview quota enforcement ---
    if job:
        recruiter_id = job.get("created_by")
        if recruiter_id:
            db = db_config.get_db()
            quota = get_recruiter_interview_quota(db, recruiter_id)

            if not quota.get("can_start_interview", False):
                return jsonify(
                    {
                        "error": quota.get("error_message")
                        or "Interview is currently unavailable for this job.",
                        "error_code": quota.get("error_code")
                        or "RECRUITER_INTERVIEW_LIMIT_REACHED",
                        "plan_owner": quota.get("plan_owner", "recruiter"),
                    }
                ), 403

            # Consume credit idempotently for this application/month.
            if not consume_interview_credit(db, recruiter_id, application_id, quota_snapshot=quota):
                return jsonify(
                    {
                        "error": "Interview is currently unavailable for this job. The recruiter has exhausted interview credits on their plan.",
                        "error_code": "RECRUITER_INTERVIEW_CREDITS_EXHAUSTED",
                        "plan_owner": "recruiter",
                    }
                ), 403

    if not job:
        return jsonify({"error": "Job not found"}), 404

    cv_details = student.get("cv_details")
    if not cv_details:
        return jsonify({"error": "CV details not found for this candidate"}), 400

    # Build plain-text CV and JD from stored structured data
    cv_text = (
        cv_service.format_cv_details(cv_details) if cv_service else _format_cv_from_details(cv_details)
    )
    jd_text = (
        cv_service.format_job_description(job) if cv_service else _format_job_from_doc(job)
    )

    # Persist as temporary .txt files for the interview document pipeline
    import uuid as _uuid
    cv_txt_path = os.path.join(TMP_FOLDER, f"{_uuid.uuid4()}_cv.txt")
    jd_txt_path = os.path.join(TMP_FOLDER, f"{_uuid.uuid4()}_jd.txt")
    with open(cv_txt_path, "w", encoding="utf-8") as f:
        f.write(cv_text)
    with open(jd_txt_path, "w", encoding="utf-8") as f:
        f.write(jd_text)

    session_details = interview_manager.create_session(
        cv_path=cv_txt_path, jd_path=jd_txt_path, reference_paths=[]
    )

    if "error" in session_details:
        return jsonify(session_details), 400

    cv_score = app_doc.get("cv_score")
    sim_score = (float(cv_score) / 100.0) if isinstance(cv_score, (int, float)) else 0.75

    interview_doc = {
        "user_id": str(current_user["_id"]),
        "session_id": session_details["session_id"],
        "cv_path": cv_txt_path,
        "jd_path": jd_txt_path,
        "reference_paths": [],
        "application_id": application_id,
        "status": "active",
        "similarity_score": sim_score,
        "created_at": datetime.datetime.utcnow(),
        "updated_at": datetime.datetime.utcnow(),
        "start_time": time.time(),
    }

    interview_id = interviews_collection.insert_one(interview_doc).inserted_id

    return jsonify(
        {
            "interview_id": str(interview_id),
            "session_id": session_details["session_id"],
            "initial_questions": [session_details["first_question"]],
            "similarity_score": sim_score,
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
    data = request.json or {}
    question = data.get("question")
    answer = data.get("answer")

    if not question or not answer:
        return jsonify({"error": "Question and answer are required"}), 400

    try:
        # Submit answer using new system
        result = interview_manager.submit_answer(session_id, question, answer)

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
    final_evaluation = {}
    interview_transcript = []
    
    # HARDCODED SCORES - To be replaced with actual model calculations
    interview_score = 85  # Hardcoded interview score
    
    if session and session.is_complete:
        # Generate evaluation from the session manager instead of accessing session attribute
        final_evaluation = interview_manager._generate_final_evaluation(session)
        
        # Extract transcript from interview data
        if hasattr(session, 'interview_data') and session.interview_data:
            for qa in session.interview_data:
                interview_transcript.append({
                    'role': 'assistant',
                    'text': qa.get('question', '')
                })
                interview_transcript.append({
                    'role': 'user',
                    'text': qa.get('answer', '')
                })
            
    elif session:
        # If ended prematurely, generate evaluation now
        final_evaluation = interview_manager._generate_final_evaluation(session)
        
        # Extract transcript
        if hasattr(session, 'interview_data') and session.interview_data:
            for qa in session.interview_data:
                interview_transcript.append({
                    'role': 'assistant',
                    'text': qa.get('question', '')
                })
                interview_transcript.append({
                    'role': 'user',
                    'text': qa.get('answer', '')
                })
    else:
        final_evaluation = {
            "summary": "Evaluation not computed in this build.",
            "final_score": None
        }

    # Get proctoring data from external service
    proctoring_service_url = os.getenv("PROCTORING_SERVICE_URL", "http://localhost:5001")
    try:
        import requests
        resp = requests.get(f"{proctoring_service_url}/api/session/{session_id}/stats", timeout=2)
        if resp.status_code == 200:
            stats = resp.json()
            proctoring_score = stats.get("proctoring_score", 90)
            manual_infractions = stats.get("manual_infractions", [])
            gaze_times = stats.get("gaze_times")
            gaze_plot_filename = stats.get("gaze_plot_filename")
            
            if gaze_plot_filename:
                gaze_plot_path = os.path.join(app.config["PROCTORING_FOLDER"], gaze_plot_filename)
            else:
                gaze_plot_path = None
        else:
            print(f"⚠️ Proctoring service returned {resp.status_code}")
            # Fallback or keep defaults
            proctoring_score = 90
            manual_infractions = []
            gaze_times = None
            gaze_plot_path = None
    except Exception as e:
        print(f"⚠️ Could not contact proctoring service: {e}")
        proctoring_score = 90
        manual_infractions = []
        gaze_times = None
        gaze_plot_path = None
    
    suspicious_activity_time = 0 # Not tracking this explicitly anymore in app.py

    # Calculate total interview duration for logging
    interview_duration = 0
    session_doc = interviews_collection.find_one(
        {"session_id": session_id, "user_id": str(current_user["_id"])}
    )
    if session_doc and "created_at" in session_doc:
        start_time = session_doc["created_at"]
        end_time = datetime.datetime.utcnow()
        interview_duration = (end_time - start_time).total_seconds()
        
        # Note: Proctoring score is currently hardcoded at 90%
        # Future: Will be calculated based on gaze metrics and infractions

    # --- NEW: Generate and save the gaze plot ---
    gaze_plot_path = None
    # Gaze plot generation is now handled by the external service



    # Update the database record with final data
    interviews_collection.update_one(
        {'session_id': session_id, 'user_id': str(current_user['_id'])},
        {'$set': {
            'status': 'completed',
            'evaluation': final_evaluation,
            'final_score': interview_score,  # Store calculated interview score
            'proctoring_score': proctoring_score,  # Store calculated proctoring score
            'transcript': interview_transcript,  # Store conversation transcript
            'manual_infractions': manual_infractions,
            'gaze_metrics': gaze_times,
            'gaze_plot_path': gaze_plot_path,
            'updated_at': datetime.datetime.utcnow()
        }}
    )

    # Also update the related application with both scores if linked
    if session_doc and session_doc.get("application_id"):
        try:
            application_id = session_doc["application_id"]
            # First, check if the application exists
            existing_app = applications_collection.find_one({"_id": ObjectId(application_id)})
            if not existing_app:
                print(f"❌ ERROR: Application with ID {application_id} NOT FOUND in database!")
                return jsonify({
                    'status': 'interview_ended',
                    'evaluation': final_evaluation,
                    'interview_score': interview_score,
                    'proctoring_score': proctoring_score,
                    'transcript': interview_transcript,
                    'error': 'Application not found'
                })

            previous_status = str(existing_app.get("status", "pending")).lower()
            
            result = applications_collection.update_one(
                {"_id": ObjectId(application_id)},
                {
                    "$set": {
                        "interview_score": interview_score,  # Store interview performance score
                        "proctoring_score": proctoring_score,  # Store proctoring behavior score
                        "status": "interviewed",
                        "updated_at": datetime.datetime.utcnow(),
                    }
                },
            )

            # Keep recruiter job-card counters in sync with the application status transition
            status_counters = ["pending", "interviewed", "selected", "rejected"]
            job_counter_update = {}

            if previous_status in status_counters and previous_status != "interviewed":
                job_counter_update[previous_status] = -1
            if previous_status != "interviewed":
                job_counter_update["interviewed"] = job_counter_update.get("interviewed", 0) + 1

            if job_counter_update:
                jobs_collection.update_one(
                    {"_id": ObjectId(existing_app["job_id"])},
                    {"$inc": job_counter_update},
                )
            
            if result.modified_count == 0:
                print(f"❌ Warning: Application {application_id} was not updated (no documents modified)")
                
        except Exception as e:
            print(f"❌ Error updating application: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"⚠️ WARNING: No application_id found in session document!")
        print(f"⚠️ Session doc keys: {session_doc.keys() if session_doc else 'No session doc'}")
            
    return jsonify({
        'status': 'interview_ended',
        'evaluation': final_evaluation,
        'interview_score': interview_score,
        'proctoring_score': proctoring_score,
        'transcript': interview_transcript
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
        if recording_analyzer:
            # Note: This might take some time to process. 
            # For a production app, this should be a background task (Celery/Redis).
            try:
                recording_analyzer.run_full_analysis(filepath)
            except Exception as e:
                print(f"Error running post-interview analysis: {e}")
        return (
            jsonify({"message": "Recording uploaded successfully", "path": filepath}),
            200,
        )

    return jsonify({"error": "File upload failed"}), 500


# In app.py (add near your existing upload-recording route)

@app.route('/api/interviews/<session_id>/upload-mobile-recording', methods=['POST'])
# @token_required  <-- NOTE: You might need to relax auth or pass a temporary token via URL for the mobile device
def upload_mobile_recording(session_id):
    if 'recording' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['recording']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if file:
        # Save with a specific suffix to distinguish from webcam
        filename = secure_filename(f"{session_id}_mobile_env.webm")
        filepath = os.path.join(app.config["M_RECORDING_FOLDER"], filename)
        file.save(filepath)
        
        # Update database with mobile recording path
        interviews_collection.update_one(
            {"session_id": session_id},
            {"$set": {"mobile_recording_path": filepath}}
        )
        
        return jsonify({"message": "Mobile recording uploaded"}), 200



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
    # This might now be handled by the proctoring service directly, 
    # OR we just acknowledge it here if the frontend still calls this for status updates.
    # For now, we'll just update status and let the proctoring service handle the image if the frontend calls it there too.
    
    # If the frontend calls THIS endpoint with the image, we might need to forward it or just ignore it 
    # if the frontend calls the proctoring service separately.
    # Assuming frontend will be updated to call proctoring service for face reg, 
    # but we still need to set status to active.
    
    # Update the interview status in the database
    interviews_collection.update_one(
        {"session_id": session_id, "user_id": str(current_user["_id"])},
        {"$set": {"status": "active"}},
    )
    return jsonify({"message": "Interview activated"}), 200

# def register_face(current_user, session_id):_OLD
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
        return jsonify({"message": "Face registered successfully"}), 200
    except Exception as e:
        print(f"Error during face registration: {e}")
        return jsonify({"error": "Failed to process image"}), 500


# Add this entire block for WebSocket event handling
@socketio.on("connect")
def handle_connect():
    from flask import request
    pass

@socketio.on("disconnect")  
def handle_disconnect():
    from flask import request  
    # Clean up any sessions associated with this client
    # Note: In SocketIO, we don't have direct access to sid in these handlers
    # We'll need to handle cleanup differently
    pass

# Socket handlers for proctoring have been moved to proctoring_server.py

@socketio.on("join_mobile_session")
def handle_mobile_join(data):
    session_id = data.get("session_id")
    # Join the specific room for this interview session
    from flask_socketio import join_room
    join_room(session_id)
    # Notify the desktop client that mobile is connected
    socketio.emit("mobile_connected", {"status": "connected"}, room=session_id)

@socketio.on("control_mobile_recording")
def handle_mobile_control(data):
    session_id = data.get("session_id")
    action = data.get("action") # 'start' or 'stop'
    
    # Relay the command to the mobile device in the room
    socketio.emit("mobile_recording_action", {"action": action}, room=session_id)

@socketio.on("mobile_status_update")
def handle_mobile_status(data):
    session_id = data.get("session_id")
    status = data.get("status") # e.g., 'recording', 'uploading', 'completed'
    # Relay status back to desktop to show user
    socketio.emit("mobile_status_dashboard", {"status": status}, room=session_id)


if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=5000, debug=False)
        # Disable reloader to avoid torch deadlock issues on Windows
        socketio.run(app, debug=True, host="0.0.0.0", port=5000, use_reloader=False)
    finally:
        # Cleanup background processor on shutdown
        logger.info("Shutting down background processor...")
        background_processor.stop()
        logger.info("Background processor stopped")
