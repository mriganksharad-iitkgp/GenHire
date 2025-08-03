import cv2
import mediapipe as mp
import numpy as np
from deepface import DeepFace

# --- Constants for Analysis ---
# These can be tuned for sensitivity
HEAD_POSE_THRESHOLD_YAW = 25
IDENTITY_VERIFY_THRESHOLD = 0.60 # Lower is stricter, higher is more lenient

# --- Penalties (applied per infraction event, not per frame) ---
# These values represent how much the score is reduced for each confirmed infraction.
PENALTY_NO_FACE = 0.5
PENALTY_MULTIPLE_FACES = 1.0
PENALTY_HEAD_TURN = 0.25
PENALTY_IDENTITY_MISMATCH = 5.0

# --- Initialize MediaPipe ---
# This is a global instance to avoid re-initializing on every function call, which is slow.
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=2,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

def analyze_frame_for_proctoring(current_frame, registered_face_img, current_score, infractions):
    """
    Analyzes a single frame for proctoring violations. This is the core logic engine for live analysis.
    (This function remains unchanged)
    """
    h, w, _ = current_frame.shape
    status_text = "Status: OK"
    score_deduction = 0

    results = face_mesh.process(cv2.cvtColor(current_frame, cv2.COLOR_BGR2RGB))

    if not results.multi_face_landmarks:
        status_text = "ALERT: No Face Detected"
        score_deduction = PENALTY_NO_FACE
        infractions['no_face'] = infractions.get('no_face', 0) + 1
    elif len(results.multi_face_landmarks) > 1:
        status_text = "ALERT: Multiple Faces Detected"
        score_deduction = PENALTY_MULTIPLE_FACES
        infractions['multiple_faces'] = infractions.get('multiple_faces', 0) + 1
    else:
        face_landmarks = results.multi_face_landmarks[0]
        face_3d = np.array([[0.0, 0.0, 0.0], [-225.0, 170.0, -135.0], [225.0, 170.0, -135.0]], dtype=np.float64)
        face_2d = np.array([face_landmarks.landmark[1].x * w, face_landmarks.landmark[1].y * h, face_landmarks.landmark[263].x * w, face_landmarks.landmark[263].y * h, face_landmarks.landmark[33].x * w, face_landmarks.landmark[33].y * h], dtype=np.float64).reshape(3, 2)
        cam_matrix = np.array([[w, 0, w/2], [0, w, h/2], [0, 0, 1]])
        
        try:
            _, rot_vec, _ = cv2.solvePnP(face_3d, face_2d, cam_matrix, np.zeros((4,1)))
            rot_matrix, _ = cv2.Rodrigues(rot_vec)
            angles, _, _, _, _, _ = cv2.RQDecomp3x3(rot_matrix)
            yaw = angles[1]
            if abs(yaw) > HEAD_POSE_THRESHOLD_YAW:
                direction = "Right" if yaw > 0 else "Left"
                status_text = f"ALERT: Head Turned {direction}"
                score_deduction = PENALTY_HEAD_TURN
                infractions['head_turn'] = infractions.get('head_turn', 0) + 1
        except Exception:
            status_text = "ALERT: Head Pose Unreadable"
            score_deduction = PENALTY_HEAD_TURN
            infractions['head_turn'] = infractions.get('head_turn', 0) + 1

        if status_text == "Status: OK":
            try:
                result = DeepFace.verify(
                    img1_path=registered_face_img,
                    img2_path=current_frame,
                    model_name="VGG-Face",
                    enforce_detection=False
                )
                if not result["verified"] or result["distance"] > IDENTITY_VERIFY_THRESHOLD:
                    status_text = "CRITICAL: Identity Mismatch"
                    score_deduction = PENALTY_IDENTITY_MISMATCH
                    infractions['identity_mismatch'] = infractions.get('identity_mismatch', 0) + 1
            except Exception:
                status_text = "ALERT: Face Cannot Be Verified"
                score_deduction = PENALTY_NO_FACE
                infractions['unverified_face'] = infractions.get('unverified_face', 0) + 1

    updated_score = max(0, current_score - score_deduction)
    return {
        "status": status_text,
        "score": updated_score,
        "infractions": infractions
    }

# --- NEW FUNCTION FOR FINAL REPORT ---
def generate_final_proctoring_report(infractions):
    """
    Generates a final summary report based on the total infractions recorded during the session.

    Args:
        infractions (dict): The final dictionary containing the total count for each infraction type.

    Returns:
        dict: A dictionary containing the final score, total deductions, and a qualitative summary.
    """
    if not infractions:
        return {
            "final_score": 100,
            "summary": "Excellent. No proctoring issues were detected during the session.",
            "infraction_counts": {}
        }

    # Calculate total deductions
    total_deductions = (
        infractions.get('no_face', 0) * PENALTY_NO_FACE +
        infractions.get('multiple_faces', 0) * PENALTY_MULTIPLE_FACES +
        infractions.get('head_turn', 0) * PENALTY_HEAD_TURN +
        infractions.get('identity_mismatch', 0) * PENALTY_IDENTITY_MISMATCH +
        infractions.get('unverified_face', 0) * PENALTY_NO_FACE
    )

    final_score = max(0, 100 - total_deductions)

    # Generate a qualitative summary
    summary_parts = []
    if infractions.get('identity_mismatch', 0) > 0:
        summary_parts.append("CRITICAL: A potential identity mismatch was detected.")
    if infractions.get('multiple_faces', 0) > 0:
        summary_parts.append("SEVERE: Multiple faces were detected during the session, which is a major violation.")
    if infractions.get('no_face', 0) > 5: # More than 5 "no face" alerts is significant
        summary_parts.append("WARNING: The candidate was not visible for a significant portion of the interview.")
    if infractions.get('head_turn', 0) > 10: # More than 10 head turns could indicate looking away
        summary_parts.append("NOTE: The candidate frequently turned away from the screen.")
    
    if not summary_parts:
        summary = "Good. The candidate maintained focus with no significant proctoring issues."
    else:
        summary = " ".join(summary_parts)

    return {
        "final_score": round(final_score, 2),
        "summary": summary,
        "infraction_counts": infractions
    }
