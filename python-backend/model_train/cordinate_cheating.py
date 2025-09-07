import cv2
import mediapipe as mp
import numpy as np
import time

class SimpleCheatingDetector:
    """
    A rule-based detector that flags suspicious gaze behavior based on duration.
    """
    def __init__(self, duration_threshold=3.5, normal_range=(-0.35, 0.35)):
        """
        Initializes the detector.
        :param duration_threshold: How many continuous seconds of suspicious gaze to trigger an alert.
        :param normal_range: The (min, max) gaze ratio considered "normal" (looking at the screen).
        """
        self.duration_threshold = duration_threshold
        self.normal_min, self.normal_max = normal_range
        
        self.suspicious_start_time = None
        self.is_suspicious = False
        self.alert_triggered = False # New state to prevent console spam

    def check_gaze(self, gaze_ratio):
        """
        Checks the current gaze ratio and returns True if cheating is detected.
        """
        if gaze_ratio is None:
            if self.is_suspicious: # Reset if face is lost
                self.is_suspicious = False
                self.suspicious_start_time = None
                self.alert_triggered = False
            return False

        # Check if the gaze is outside the normal, screen-facing range
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
                print("Gaze returned to normal.")
                self.is_suspicious = False
                self.suspicious_start_time = None
                self.alert_triggered = False
                
        return False

class GazeTracker:
    """
    Tracks and accumulates the time spent in each gaze direction.
    """
    def __init__(self):
        self.time_left = 0
        self.time_center = 0
        self.time_right = 0
        self.last_frame_time = time.time()

    def update(self, current_gaze):
        """Updates the timers based on the current gaze direction."""
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
        """Returns the accumulated times."""
        return {
            "Left": self.time_left,
            "Center": self.time_center,
            "Right": self.time_right
        }

def get_gaze_direction(gaze_ratio):
    """Converts the gaze ratio to a descriptive string."""
    if gaze_ratio is None:
        return "Unknown"
    if gaze_ratio < -0.35:
        return "Right"
    elif gaze_ratio > 0.35:
        return "Left"
    else:
        return "Center"

# --- Main Application ---

# Initialize MediaPipe
mp_face_mesh = mp.solutions.face_mesh
mp_drawing = mp.solutions.drawing_utils
face_mesh = mp_face_mesh.FaceMesh(
    static_image_mode=False,
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5)

# Landmark Indices for eye corners and iris
P_LEFT_IRIS = 473
P_RIGHT_IRIS = 468
P_LEFT_EYE_OUTER = 33
P_LEFT_EYE_INNER = 133
P_RIGHT_EYE_OUTER = 263
P_RIGHT_EYE_INNER = 362

# Initialize the detectors and trackers
detector = SimpleCheatingDetector(duration_threshold=3.5, normal_range=(-0.35, 0.35))
gaze_tracker = GazeTracker()

# Start video capture
cap = cv2.VideoCapture(0)

while cap.isOpened():
    success, image = cap.read()
    if not success:
        print("Ignoring empty camera frame.")
        continue

    # Flip and convert the image
    image = cv2.cvtColor(cv2.flip(image, 1), cv2.COLOR_BGR2RGB)
    image.flags.writeable = False
    results = face_mesh.process(image)
    image.flags.writeable = True
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    
    is_cheating_alert = False
    gaze_direction_text = "Face Not Found"

    if results.multi_face_landmarks:
        for face_landmarks in results.multi_face_landmarks:
            landmarks = np.array([(lm.x, lm.y) for lm in face_landmarks.landmark])

            # Get coordinates for all relevant points
            left_iris = landmarks[P_LEFT_IRIS]
            right_iris = landmarks[P_RIGHT_IRIS]
            left_eye_inner = landmarks[P_LEFT_EYE_INNER]
            left_eye_outer = landmarks[P_LEFT_EYE_OUTER]
            right_eye_inner = landmarks[P_RIGHT_EYE_INNER]
            right_eye_outer = landmarks[P_RIGHT_EYE_OUTER]

            # --- NEW: Improved Gaze Ratio Calculation (-1.0 Right to 1.0 Left) ---
            left_eye_center = (left_eye_inner + left_eye_outer) * 0.5
            left_eye_span = abs(left_eye_inner[0] - left_eye_outer[0])
            left_gaze_ratio = (left_eye_center[0] - left_iris[0]) / (left_eye_span / 2) if left_eye_span != 0 else None

            right_eye_center = (right_eye_inner + right_eye_outer) * 0.5
            right_eye_span = abs(right_eye_inner[0] - right_eye_outer[0])
            right_gaze_ratio = (right_eye_center[0] - right_iris[0]) / (right_eye_span / 2) if right_eye_span != 0 else None
            
            gaze_ratio = None
            if left_gaze_ratio is not None and right_gaze_ratio is not None:
                gaze_ratio = (left_gaze_ratio + right_gaze_ratio) / 2.0
            
            # --- Get direction and update trackers ---
            gaze_direction = get_gaze_direction(gaze_ratio)
            gaze_tracker.update(gaze_direction)
            is_cheating_alert = detector.check_gaze(gaze_ratio)
            gaze_direction_text = f"Gaze: {gaze_direction}"
            
            # Draw face mesh for visualization
            mp_drawing.draw_landmarks(
                image=image, landmark_list=face_landmarks,
                connections=mp_face_mesh.FACEMESH_TESSELATION,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp_drawing.DrawingSpec(thickness=1, circle_radius=1, color=(0,255,0)))

    # --- Display Status and Timers on Screen ---
    h, w, _ = image.shape
    # Gaze status
    cv2.putText(image, gaze_direction_text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
    # Alert
    if is_cheating_alert:
        cv2.putText(image, "ALERT!", (w // 4, h // 2), 
                    cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 255), 10)
    # Time trackers
    times = gaze_tracker.get_times()
    cv2.putText(image, f"Time Left: {times['Left']:.1f}s", (50, h - 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    cv2.putText(image, f"Time Center: {times['Center']:.1f}s", (50, h - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    cv2.putText(image, f"Time Right: {times['Right']:.1f}s", (50, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

    # Display the resulting frame
    cv2.imshow('Live Cheating Detector', image)

    # Exit on 'ESC' key
    if cv2.waitKey(5) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()

