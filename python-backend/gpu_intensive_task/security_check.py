import cv2
import mediapipe as mp
import numpy as np
from deepface import DeepFace

# --- Constants for Analysis ---
# These can be tuned for sensitivity
HEAD_POSE_THRESHOLD_YAW = 30 # Increased threshold to be more lenient
IDENTITY_VERIFY_THRESHOLD = 0.60 # Lower is stricter

# --- Penalties (applied per infraction event, not per frame) ---
PENALTY_NO_FACE = 0.5
PENALTY_MULTIPLE_FACES = 2.0 # Increased penalty for this clear violation
PENALTY_HEAD_TURN = 0.5 # Increased penalty for a confirmed turn
PENALTY_IDENTITY_MISMATCH = 5.0
# *** NEW ***: A much smaller penalty for technical errors
PENALTY_UNREADABLE_POSE = 0.05 

# --- Initialize MediaPipe ---
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=2,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

def analyze_frame_for_proctoring(current_frame, registered_face_img, current_score, infractions):
    """
    Analyzes a single frame for proctoring violations with improved robustness.
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

    else: # A single face was detected
        face_landmarks = results.multi_face_landmarks[0]

        # --- MODIFIED: More Robust Head Pose Check ---
        # Using 6 key landmarks for a more stable 3D model
        face_3d = np.array([
            [0.0, 0.0, 0.0],            # Nose tip
            [0.0, -330.0, -65.0],       # Chin
            [-225.0, 170.0, -135.0],    # Left eye left corner
            [225.0, 170.0, -135.0],     # Right eye right corner
            [-150.0, -150.0, -125.0],   # Left Mouth corner
            [150.0, -150.0, -125.0]      # Right mouth corner
        ], dtype=np.float64)

        face_2d = np.array([
            (face_landmarks.landmark[1].x * w, face_landmarks.landmark[1].y * h),      # Nose tip
            (face_landmarks.landmark[152].x * w, face_landmarks.landmark[152].y * h),  # Chin
            (face_landmarks.landmark[263].x * w, face_landmarks.landmark[263].y * h),  # Left eye corner
            (face_landmarks.landmark[33].x * w, face_landmarks.landmark[33].y * h),    # Right eye corner
            (face_landmarks.landmark[287].x * w, face_landmarks.landmark[287].y * h),  # Left mouth corner
            (face_landmarks.landmark[57].x * w, face_landmarks.landmark[57].y * h),    # Right mouth corner
        ], dtype=np.float64)
        
        cam_matrix = np.array([[w, 0, w/2], [0, w, h/2], [0, 0, 1]])
        
        try:
            success, rot_vec, trans_vec = cv2.solvePnP(face_3d, face_2d, cam_matrix, np.zeros((4,1)))
            rot_matrix, _ = cv2.Rodrigues(rot_vec)
            angles, _, _, _, _, _ = cv2.RQDecomp3x3(rot_matrix)
            yaw = angles[1]

            if abs(yaw) > HEAD_POSE_THRESHOLD_YAW:
                direction = "Right" if yaw > 0 else "Left"
                status_text = f"ALERT: Head Turned {direction}"
                score_deduction = PENALTY_HEAD_TURN
                infractions['head_turn'] = infractions.get('head_turn', 0) + 1

        except Exception:
            # *** MODIFIED ***: Penalize less for a technical error
            status_text = "ALERT: Head Pose Unreadable"
            score_deduction = PENALTY_UNREADABLE_POSE
            infractions['unreadable_pose'] = infractions.get('unreadable_pose', 0) + 1

        # Identity Verification Check (only if no other alert has been triggered)
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

# (The generate_final_proctoring_report function remains the same)
def generate_final_proctoring_report(infractions):
    if not infractions:
        return { "final_score": 100, "summary": "Excellent. No proctoring issues detected.", "infraction_counts": {} }

    total_deductions = (
        infractions.get('no_face', 0) * PENALTY_NO_FACE +
        infractions.get('multiple_faces', 0) * PENALTY_MULTIPLE_FACES +
        infractions.get('head_turn', 0) * PENALTY_HEAD_TURN +
        infractions.get('identity_mismatch', 0) * PENALTY_IDENTITY_MISMATCH +
        infractions.get('unverified_face', 0) * PENALTY_NO_FACE +
        infractions.get('unreadable_pose', 0) * PENALTY_UNREADABLE_POSE
    )
    final_score = max(0, 100 - total_deductions)

    summary_parts = []
    if infractions.get('identity_mismatch', 0) > 0:
        summary_parts.append("CRITICAL: A potential identity mismatch was detected.")
    if infractions.get('multiple_faces', 0) > 0:
        summary_parts.append("SEVERE: Multiple faces were detected.")
    if infractions.get('no_face', 0) > 5:
        summary_parts.append("WARNING: The candidate was not visible for a significant time.")
    if infractions.get('head_turn', 0) > 10:
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
