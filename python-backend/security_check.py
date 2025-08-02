import cv2
import mediapipe as mp
import math
import datetime

def analyze_gaze(face_landmarks, frame_shape):
    h, w, _ = frame_shape
    LEFT_EYE_INDICES = [33, 133]
    RIGHT_EYE_INDICES = [362, 263]
    LEFT_IRIS_INDEX = 473
    RIGHT_IRIS_INDEX = 468

    right_eye_left_corner = face_landmarks.landmark[RIGHT_EYE_INDICES[0]]
    right_eye_right_corner = face_landmarks.landmark[RIGHT_EYE_INDICES[1]]
    right_iris_center = face_landmarks.landmark[RIGHT_IRIS_INDEX]

    eye_width_right = math.hypot(
        (right_eye_left_corner.x - right_eye_right_corner.x) * w,
        (right_eye_left_corner.y - right_eye_right_corner.y) * h
    )
    if eye_width_right == 0:
        return "Forward"

    iris_pos_right = math.hypot(
        (right_iris_center.x - right_eye_right_corner.x) * w,
        (right_iris_center.y - right_eye_right_corner.y) * h
    )
    gaze_ratio = iris_pos_right / eye_width_right

    if gaze_ratio > 0.65:
        return "Right"
    elif gaze_ratio < 0.45:
        return "Left"
    else:
        return "Forward"

def run_security_check(video_path, session_id, interviews_collection):
    print(f"✅ [Analysis Started] for session: {session_id} on video: {video_path}")

    multiple_faces_frames = 0
    looking_away_frames = 0
    no_face_frames = 0
    total_processed_frames = 0

    mp_face_mesh = mp.solutions.face_mesh
    face_mesh = mp_face_mesh.FaceMesh(
        static_image_mode=False,
        max_num_faces=2,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ Error: Could not open video file {video_path}")
        return

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break

        total_processed_frames += 1
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(frame_rgb)

        if results.multi_face_landmarks:
            if len(results.multi_face_landmarks) > 1:
                multiple_faces_frames += 1
            
            face_landmarks = results.multi_face_landmarks[0]
            gaze = analyze_gaze(face_landmarks, frame.shape)
            if gaze != "Forward":
                looking_away_frames += 1
        else:
            no_face_frames += 1

    cap.release()
    face_mesh.close()

    if total_processed_frames > 0:
        score = 100
        score -= (multiple_faces_frames / total_processed_frames) * 50
        score -= (looking_away_frames / total_processed_frames) * 25
        score -= (no_face_frames / total_processed_frames) * 40
        final_score = max(0, round(score))
    else:
        final_score = 0

    print(f"🏁 [Analysis Finished] for session: {session_id}")
    print(f"    - Final Proctoring Score: {final_score}/100")

    interviews_collection.update_one(
        {'session_id': session_id},
        {'$set': {
            'proctoring_score': final_score,
            'proctoring_analysis': {
                'status': 'Completed',
                'multiple_faces_frames': multiple_faces_frames,
                'looking_away_frames': looking_away_frames,
                'no_face_frames': no_face_frames,
                'total_processed_frames': total_processed_frames,
                'analyzed_at': datetime.datetime.utcnow()
            }
        }}
    )