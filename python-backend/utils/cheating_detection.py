import cv2
import mediapipe as mp
import numpy as np
import time

class SimpleCheatingDetector:
    # Paste your SimpleCheatingDetector class here without any changes.
    def __init__(self, duration_threshold=3.5, normal_range=(-0.35, 0.35)):
        self.duration_threshold = duration_threshold
        self.normal_min, self.normal_max = normal_range
        self.suspicious_start_time = None
        self.is_suspicious = False
        self.alert_triggered = False
        self.total_suspicious_time = 0

    def check_gaze(self, gaze_ratio):
        if gaze_ratio is None:
            if self.is_suspicious:
                self.total_suspicious_time += time.time() - self.suspicious_start_time
                self.is_suspicious = False
                self.suspicious_start_time = None
                self.alert_triggered = False
            return False
        if not (self.normal_min < gaze_ratio < self.normal_max):
            if not self.is_suspicious:
                self.is_suspicious = True
                self.suspicious_start_time = time.time()
            else:
                elapsed_time = time.time() - self.suspicious_start_time
                if elapsed_time > self.duration_threshold:
                    if not self.alert_triggered:
                        print(f"ALERT: Suspicious gaze held for {elapsed_time:.2f} seconds!")
                        self.alert_triggered = True
                    return True
        else:
            if self.is_suspicious:
                self.total_suspicious_time += time.time() - self.suspicious_start_time
                print("Gaze returned to normal.")
                self.is_suspicious = False
                self.suspicious_start_time = None
                self.alert_triggered = False
        return False

class GazeTracker:
    # Paste your GazeTracker class here without any changes.
    def __init__(self):
        self.time_left = 0
        self.time_center = 0
        self.time_right = 0
        self.last_frame_time = time.time()

    def update(self, current_gaze):
        current_time = time.time()
        delta_time = current_time - self.last_frame_time
        self.last_frame_time = current_time
        if current_gaze == "Left":
            self.time_left += delta_time
        elif current_gaze == "Center":
            self.time_center += delta_time
        elif current_gaze == "Right":
            self.time_right += delta_time

    def get_times(self):
        return {
            "Left": self.time_left,
            "Center": self.time_center,
            "Right": self.time_right
        }

def get_gaze_direction(gaze_ratio):
    # Paste your get_gaze_direction function here without any changes.
    if gaze_ratio is None:
        return "Unknown"
    if gaze_ratio < -0.35:
        return "Right"
    elif gaze_ratio > 0.35:
        return "Left"
    else:
        return "Center"

# New class to integrate all the logic
class ProctoringGazeDetector:
    def __init__(self):
        # Initialize MediaPipe and your classes once per session
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.detector = SimpleCheatingDetector(duration_threshold=3.5, normal_range=(-0.35, 0.35))
        self.gaze_tracker = GazeTracker()
        
        # Landmark Indices for eye corners and iris
        self.P_LEFT_IRIS = 473
        self.P_RIGHT_IRIS = 468
        self.P_LEFT_EYE_OUTER = 33
        self.P_LEFT_EYE_INNER = 133
        self.P_RIGHT_EYE_OUTER = 263
        self.P_RIGHT_EYE_INNER = 362

    def process_frame(self, frame_np):
        """Processes a single NumPy frame and returns detection results."""
        image = cv2.cvtColor(frame_np, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False
        results = self.face_mesh.process(image)
        image.flags.writeable = True
        
        gaze_ratio = None
        is_cheating_alert = False
        gaze_direction_text = "Unknown"

        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                landmarks = np.array([(lm.x, lm.y) for lm in face_landmarks.landmark])
                
                left_iris = landmarks[self.P_LEFT_IRIS]
                left_eye_inner = landmarks[self.P_LEFT_EYE_INNER]
                left_eye_outer = landmarks[self.P_LEFT_EYE_OUTER]
                left_eye_center = (left_eye_inner + left_eye_outer) * 0.5
                left_eye_span = abs(left_eye_inner[0] - left_eye_outer[0])
                left_gaze_ratio = (left_eye_center[0] - left_iris[0]) / (left_eye_span / 2) if left_eye_span != 0 else None

                right_iris = landmarks[self.P_RIGHT_IRIS]
                right_eye_inner = landmarks[self.P_RIGHT_EYE_INNER]
                right_eye_outer = landmarks[self.P_RIGHT_EYE_OUTER]
                right_eye_center = (right_eye_inner + right_eye_outer) * 0.5
                right_eye_span = abs(right_eye_inner[0] - right_eye_outer[0])
                right_gaze_ratio = (right_eye_center[0] - right_iris[0]) / (right_eye_span / 2) if right_eye_span != 0 else None
                
                if left_gaze_ratio is not None and right_gaze_ratio is not None:
                    gaze_ratio = (left_gaze_ratio + right_gaze_ratio) / 2.0
            
            gaze_direction_text = get_gaze_direction(gaze_ratio)
            self.gaze_tracker.update(gaze_direction_text)
            is_cheating_alert = self.detector.check_gaze(gaze_ratio)
        
        return {
            "is_cheating_alert": is_cheating_alert,
            "gaze_direction": gaze_direction_text,
            "gaze_times": self.gaze_tracker.get_times()
        }