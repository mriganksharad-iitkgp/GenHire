"""Shared interview runtime state.

Single home for the process-wide interview objects that app.py used to define
inline: the live proctoring session store, the interview session manager
singleton, the gaze recorder service, and the upload folder layout. Socket
handlers, interview routes, and background sweepers must all import these from
here so exactly one instance of each exists per process.
"""

import os

from config.env_loader import load_environment

load_environment()

from interview.config.settings import InterviewConfig, LLMConfig
from interview.core.session_manager import InterviewSessionManager
from utils.gaze_recorder_service import GazeRecorderService

# In-memory store: session_id -> { registered_face_bytes, proctoring_score, infractions }
live_sessions = {}

# Directories for storing interview artifacts
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
PROCTORING_FOLDER = os.path.join(UPLOAD_FOLDER, "proctoring")
RECORDING_FOLDER = os.path.join(UPLOAD_FOLDER, "recordings")
M_RECORDING_FOLDER = os.path.join(UPLOAD_FOLDER, "mobile_recordings")
TMP_FOLDER = os.path.join(UPLOAD_FOLDER, "tmp")
GAZE_RECORDER_FOLDER = os.path.join(PROCTORING_FOLDER, "gaze_recorder")

for _folder in (PROCTORING_FOLDER, RECORDING_FOLDER, M_RECORDING_FOLDER, TMP_FOLDER, GAZE_RECORDER_FOLDER):
    os.makedirs(_folder, exist_ok=True)

# Interview session manager singleton (default configs, GROQ-backed LLM)
interview_config = InterviewConfig()
llm_config = LLMConfig()
interview_manager = InterviewSessionManager(config=interview_config, llm_config=llm_config)

gaze_recorder_service = GazeRecorderService(output_dir=GAZE_RECORDER_FOLDER)
