# Proctoring & Facial Verification Features

## Overview

This backend implements **AI-powered proctoring** and **facial verification** for online interviews, ensuring candidate authenticity and monitoring suspicious behavior. The main entry point is [`app.py`](python-backend/app.py), which integrates all proctoring logic and exposes REST and WebSocket APIs.

---

## Main Components

### 1. **Proctoring (Live Cheating Detection)**
- **File:** [`utils/cheating_detection.py`](python-backend/utils/cheating_detection.py)
- **Usage:** Directly used in [`app.py`](python-backend/app.py)
- **Features:**
  - Real-time gaze tracking using MediaPipe
  - Suspicious gaze detection (e.g., looking away for too long)
  - Session-based tracking and plotting of gaze data
  - Generates gaze movement plots at interview end

### 2. **Facial Verification (Standalone Script)**
- **File:** [`face_verify.py`](python-backend/face_verify.py)
- **Usage:** Standalone script, **not directly used** by [`app.py`](python-backend/app.py)
- **Features:**
  - Register a face via webcam and save locally
  - Verify live webcam feed against registered face using DeepFace
  - Useful for local testing or future integration

### 3. **Security Checks (Frame-by-Frame Analysis)**
- **File:** [`security_check.py`](python-backend/security_check.py)
- **Usage:** Can be used for batch/offline analysis or as a utility
- **Features:**
  - Detects multiple faces, head turns, and identity mismatches
  - Assigns penalties for each infraction
  - Generates a final proctoring report

### 4. **Recording Analysis (Audio/Video Post-Processing)**
- **File:** [`services/recording_analysis_service.py`](python-backend/services/recording_analysis_service.py)
- **Usage:** Used in [`app.py`](python-backend/app.py) if dependencies are available
- **Features:**
  - Speaker diarization (number of speakers in audio)
  - Object detection in video (e.g., non-person objects)
  - Used for post-interview analysis of uploaded recordings

---

## How Everything Connects

- **Live Interview Proctoring:**  
  [`app.py`](python-backend/app.py) uses [`ProctoringGazeDetector`](python-backend/utils/cheating_detection.py) for real-time gaze tracking via WebSocket events. Results are stored in memory and saved to the database at interview end.

- **Face Registration & Verification:**  
  The logic for registering and verifying faces is implemented in [`face_verify.py`](python-backend/face_verify.py), but **is not currently invoked by [`app.py`](python-backend/app.py)**. It can be integrated for stricter identity checks if needed.

- **Security Checks:**  
  [`security_check.py`](python-backend/security_check.py) provides frame-level analysis and can be used for offline or batch proctoring, but is not directly called in the live interview flow.

- **Recording Analysis:**  
  If enabled, [`recording_analysis_service.py`](python-backend/services/recording_analysis_service.py) analyzes uploaded interview recordings for speaker count and suspicious objects. This is triggered by the `/api/interviews/<session_id>/upload-recording` endpoint in [`app.py`](python-backend/app.py).

---

## Integration Summary

| Feature                | Main App (`app.py`) | Standalone Script | Used in Production? |
|------------------------|---------------------|-------------------|---------------------|
| Gaze Proctoring        | ✅ Yes              | ❌                | ✅ Yes              |
| Face Verification      | ❌                  | ✅ Yes            | ❌ (demo only)      |
| Security Check Utility | ❌                  | ✅ Yes            | ❌ (utility only)   |
| Recording Analysis     | ✅ (if enabled)     | ❌                | ✅ (optional)       |

---

## Extending/Modifying

- To **enable facial verification** in live interviews, integrate logic from [`face_verify.py`](python-backend/face_verify.py) into the interview start or proctoring flow in [`app.py`](python-backend/app.py).
- To **run batch proctoring analysis**, use [`security_check.py`](python-backend/security_check.py) on saved video frames.
- To **analyze recordings**, ensure all dependencies for [`recording_analysis_service.py`](python-backend/services/recording_analysis_service.py) are installed.

---

## References

- [app.py](python-backend/app.py)
- [face_verify.py](python-backend/face_verify.py)
- [security_check.py](python-backend/security_check.py)
- [utils/cheating_detection.py](python-backend/utils/cheating_detection.py)
- [services/recording_analysis_service.py](python-backend/services/recording_analysis_service.py)
