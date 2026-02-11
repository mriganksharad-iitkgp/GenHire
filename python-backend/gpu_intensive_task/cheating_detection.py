import cv2
import mediapipe as mp
import numpy as np
import time
import matplotlib.pyplot as plt
import os

class SimpleCheatingDetector:
    def __init__(self, duration_threshold=3.5, normal_range=(-0.35, 0.35)):
        self.duration_threshold = duration_threshold
        self.normal_min, self.normal_max = normal_range
        self.suspicious_start_time = None
        self.is_suspicious = False
        self.alert_triggered = False
        self.total_suspicious_time = 0

    # MODIFICATION: Added current_time parameter to support offline video analysis
    def check_gaze(self, gaze_ratio, current_time=None):
        if current_time is None:
            current_time = time.time()

        if gaze_ratio is None:
            if self.is_suspicious:
                self.total_suspicious_time += current_time - self.suspicious_start_time
                self.is_suspicious = False
                self.suspicious_start_time = None
                self.alert_triggered = False
            return False
        
        if not (self.normal_min < gaze_ratio < self.normal_max):
            if not self.is_suspicious:
                self.is_suspicious = True
                self.suspicious_start_time = current_time
            else:
                elapsed_time = current_time - self.suspicious_start_time
                if elapsed_time > self.duration_threshold:
                    if not self.alert_triggered:
                        print(f"ALERT: Suspicious gaze held for {elapsed_time:.2f} seconds!")
                        self.alert_triggered = True
                    return True
        else:
            if self.is_suspicious:
                self.total_suspicious_time += current_time - self.suspicious_start_time
                print("Gaze returned to normal.")
                self.is_suspicious = False
                self.suspicious_start_time = None
                self.alert_triggered = False
        return False

class GazeTracker:
    def __init__(self):
        self.time_left = 0
        self.time_center = 0
        self.time_right = 0
        # MODIFICATION: Initialize to None to handle first frame logic correctly
        self.last_frame_time = None 

    # MODIFICATION: Added current_time parameter
    def update(self, current_gaze, current_time=None):
        if current_time is None:
            current_time = time.time()
            
        # Handle the very first frame
        if self.last_frame_time is None:
            self.last_frame_time = current_time
            return

        delta_time = current_time - self.last_frame_time
        # Prevent negative time if timestamps are not perfectly sequential
        if delta_time < 0: 
            delta_time = 0
            
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
        
        # Data for plotting
        self.gaze_data = []
        # MODIFICATION: Initialize to None to capture start time from first processed frame
        self.session_start_time = None
        
        # Landmark Indices for eye corners and iris
        self.P_LEFT_IRIS = 473
        self.P_RIGHT_IRIS = 468
        self.P_LEFT_EYE_OUTER = 33
        self.P_LEFT_EYE_INNER = 133
        self.P_RIGHT_EYE_OUTER = 263
        self.P_RIGHT_EYE_INNER = 362

    # MODIFICATION: Added timestamp parameter for offline processing
    def process_frame(self, frame_np, timestamp=None):
        """
        Processes a single NumPy frame and returns detection results.
        If timestamp is provided (e.g. from video file), it uses that instead of system time.
        """
        if timestamp is None:
            timestamp = time.time()
            
        if self.session_start_time is None:
            self.session_start_time = timestamp

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
            
            # MODIFICATION: Pass the explicit timestamp
            self.gaze_tracker.update(gaze_direction_text, current_time=timestamp)
            is_cheating_alert = self.detector.check_gaze(gaze_ratio, current_time=timestamp)
        else:
            # Ensure time is tracked even if no face is found in this frame
            self.gaze_tracker.update("Unknown", current_time=timestamp)
        
        # Record data for plotting
        # MODIFICATION: Use relative time based on the explicit timestamp
        relative_time = timestamp - self.session_start_time
        # Use np.nan when gaze is not detected to create gaps in the plot
        self.gaze_data.append((relative_time, gaze_ratio if gaze_ratio is not None else np.nan))
        
        return {
            "is_cheating_alert": is_cheating_alert,
            "gaze_direction": gaze_direction_text,
            "gaze_times": self.gaze_tracker.get_times()
        }

    def generate_gaze_plot(self, output_dir=".", filename="gaze_movement_plot.png"):
        """
        Generates and saves a plot of gaze ratio over time.
        Call this method after the video processing is complete.
        """
        if not self.gaze_data:
            print("No gaze data to plot.")
            return

        timestamps, gaze_ratios = zip(*self.gaze_data)

        plt.figure(figsize=(15, 6))
        plt.plot(timestamps, gaze_ratios, label='Gaze Ratio', color='royalblue', linewidth=1)
        
        # Highlight suspicious regions (outside normal range)
        normal_min, normal_max = self.detector.normal_min, self.detector.normal_max
        plt.axhspan(normal_min, normal_max, color='green', alpha=0.2, label='Normal Gaze Zone')
        
        plt.title('Eyeball Movement Over Time')
        plt.xlabel('Time (seconds)')
        plt.ylabel('Gaze Ratio (Left < 0 > Right)')
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.legend()
        plt.ylim(-1.5, 1.5) # Set a fixed y-axis range for consistency
        
        # Ensure the output directory exists
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        filepath = os.path.join(output_dir, filename)
        plt.savefig(filepath)
        plt.close()
        print(f"Gaze plot saved to {filepath}")