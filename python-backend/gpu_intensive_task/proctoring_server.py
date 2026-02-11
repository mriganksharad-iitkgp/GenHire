import os
import logging
import warnings
import base64
import cv2
import numpy as np
import eventlet
from flask import Flask, jsonify, request
from flask_socketio import SocketIO
from dotenv import load_dotenv
from flask_cors import CORS
import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Filter warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

from cheating_detection import ProctoringGazeDetector

# Initialize Flask App
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "proctoring-secret-key")

# Setup CORS
CORS(app, resources={r"/*": {"origins": "*"}})

# Setup SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# State management
proctoring_detectors = {}
live_sessions = {}

# Ensure directories exist
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "../uploads") # Adjust path relative to where this script runs usually
PROCTORING_FOLDER = os.path.join(UPLOAD_FOLDER, "proctoring")
os.makedirs(PROCTORING_FOLDER, exist_ok=True)

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "Proctoring Server Running", "service": "gpu-intensive-task"}), 200

@socketio.on("connect")
def handle_connect():
    logger.info(f"Client connected: {request.sid}")

@socketio.on("disconnect")
def handle_disconnect():
    logger.info(f"Client disconnected: {request.sid}")
    # Cleanup logic if needed, but usually we keep session state for a bit?
    # For now, simplistic cleanup could happen here if we mapped sid to session_id effectively.
    pass

@socketio.on("start_proctoring")
def handle_start_proctoring(data):
    session_id = data.get("session_id")
    if not session_id:
        return
    
    logger.info(f"Starting proctoring for session: {session_id}")
    
    # Initialize session data if not exists (it might be initialized via API later/concurrently)
    if session_id not in live_sessions:
        live_sessions[session_id] = {
            "proctoring_score": 100,
            "manual_infractions": [],
            "gaze_times": {"Left": 0, "Center": 0, "Right": 0}
        }
    
    # Initialize detector
    if session_id not in proctoring_detectors:
        proctoring_detectors[session_id] = ProctoringGazeDetector()
    
    live_sessions[session_id]["connected"] = True

@socketio.on("proctoring_frame")
def handle_proctoring_frame(data):
    session_id = data.get("session_id")
    if not session_id or session_id not in proctoring_detectors:
        return

    detector = proctoring_detectors[session_id]
    session_data = live_sessions.get(session_id)
    
    try:
        header, encoded = data["image"].split(",", 1)
        frame = cv2.imdecode(
            np.frombuffer(base64.b64decode(encoded), np.uint8), cv2.IMREAD_COLOR
        )
        
        # Process frame
        analysis_result = detector.process_frame(frame)
        
        # Update session state
        if session_data:
            session_data["gaze_times"] = analysis_result["gaze_times"]

        # Emit back results
        socketio.emit(
            "gaze_data",
            {
                "session_id": session_id,
                "is_cheating_alert": analysis_result["is_cheating_alert"],
                "gaze_direction": analysis_result["gaze_direction"],
                "gaze_times": analysis_result["gaze_times"],
            }
        )
    except Exception as e:
        logger.error(f"Error processing frame for session {session_id}: {e}")

@socketio.on("proctoring_violation")
def handle_proctoring_violation(data):
    session_id = data.get("session_id")
    violation_type = data.get("type")
    
    if not session_id or session_id not in live_sessions:
        return
        
    session_data = live_sessions[session_id]
    
    # Log infraction
    timestamp = datetime.datetime.utcnow().isoformat()
    infraction = {"type": violation_type, "timestamp": timestamp}
    
    if "manual_infractions" not in session_data:
        session_data["manual_infractions"] = []
    
    session_data["manual_infractions"].append(infraction)
    
    # Deduct score
    session_data["proctoring_score"] = max(
        0, session_data.get("proctoring_score", 100) - 5
    )
    
    logger.info(f"Violation recorded for {session_id}: {violation_type}")

# Internal API for the main app to fetch stats when interview ends
@app.route("/api/session/<session_id>/stats", methods=["GET"])
def get_session_stats(session_id):
    session_data = live_sessions.get(session_id, {})
    detector = proctoring_detectors.get(session_id)
    
    # Prepare stats
    stats = {
        "manual_infractions": session_data.get("manual_infractions", []),
        "proctoring_score": session_data.get("proctoring_score", 100),
        "gaze_times": None
    }
    
    if detector:
        stats["gaze_times"] = detector.gaze_tracker.get_times()
        
        # Generate plot if needed
        try:
            plot_filename = f"{session_id}_gaze_plot.png"
            detector.generate_gaze_plot(
                output_dir=PROCTORING_FOLDER, 
                filename=plot_filename
            )
            # Return path relative to what the main app expects? 
            # Or just filename. Main app knows PROCTORING_FOLDER.
            stats["gaze_plot_filename"] = plot_filename
        except Exception as e:
            logger.error(f"Failed to generate plot: {e}")
            
    # Cleanup session (optional, or wait for explicit end command)
    # proctoring_detectors.pop(session_id, None)
    # live_sessions.pop(session_id, None)
    
    return jsonify(stats)

if __name__ == "__main__":
    logger.info("Starting Proctoring Server on port 5001...")
    socketio.run(app, debug=True, port=5001, allow_unsafe_werkzeug=True)
