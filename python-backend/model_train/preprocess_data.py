
import os
import cv2
import mediapipe as mp
import numpy as np
import pandas as pd
import time

# UPDATE THIS PATH to the root directory of your OEP dataset
DATASET_ROOT = "C:/Users/aditya/Documents/GitHub/product-prototyping-lab/python-backend/model_train/OEP database" 
OUTPUT_DIR = "processed_data"
EYE_IMAGE_SIZE = (128, 64)  # Width, Height for the cropped eye images

# --- Initialization ---
mp_face_mesh = mp.solutions.face_mesh.FaceMesh(
    static_image_mode=True, max_num_faces=1, refine_landmarks=True)

# Landmark indices for the bounding box of the eyes
# These can be adjusted for a tighter or looser crop
LEFT_EYE_BOUNDS = [33, 133, 160, 144, 158, 153]
RIGHT_EYE_BOUNDS = [362, 263, 387, 373, 385, 380]

def get_seconds_from_timestamp(ts_str):
    """Converts MMSS timestamp string to total seconds."""
    # Ensure the string is the correct length for MMSS format
    if len(ts_str) != 4:
        print(f"Warning: Unexpected timestamp format encountered: '{ts_str}'. Skipping.")
        return None # Return None to indicate an error
    try:
        minutes = int(ts_str[0:2])
        seconds = int(ts_str[2:4])
        return minutes * 60 + seconds
    except (ValueError, TypeError):
        print(f"Warning: Could not parse timestamp: '{ts_str}'. Skipping.")
        return None # Return None to indicate an error

def get_eye_bounding_box(landmarks, eye_indices, img_shape):
    """Calculates the bounding box for an eye region from landmarks."""
    # Use a list comprehension to correctly select the landmarks
    points = [landmarks[i] for i in eye_indices]
    x_coords = [p.x * img_shape[1] for p in points]
    y_coords = [p.y * img_shape[0] for p in points]
    
    x_min, x_max = int(min(x_coords)), int(max(x_coords))
    y_min, y_max = int(min(y_coords)), int(max(y_coords))
    
    # Add some padding
    padding_x = int((x_max - x_min) * 0.15)
    padding_y = int((y_max - y_min) * 0.25)
    
    return (x_min - padding_x, y_min - padding_y, 
            x_max + padding_x, y_max + padding_y)

def process_dataset():
    """Main function to process all subjects in the dataset."""
    # Create output directories
    cheating_dir = os.path.join(OUTPUT_DIR, "cheating")
    not_cheating_dir = os.path.join(OUTPUT_DIR, "not_cheating")
    os.makedirs(cheating_dir, exist_ok=True)
    os.makedirs(not_cheating_dir, exist_ok=True)

    subject_folders = [f for f in os.listdir(DATASET_ROOT) if f.startswith("subject")]
    
    for subject in subject_folders:
        print(f"--- Processing {subject} ---")
        subject_path = os.path.join(DATASET_ROOT, subject)
        
        # 1. Parse Ground Truth
        gt_path = os.path.join(subject_path, "gt.txt")
        cheating_intervals = []
        try:
            with open(gt_path, 'r') as f:
                for line in f:
                    # Split by any whitespace instead of just comma
                    parts = line.strip().split()
                    # Add a check to skip blank or malformed lines
                    if len(parts) < 2:
                        continue
                    start_time = get_seconds_from_timestamp(parts[0])
                    end_time = get_seconds_from_timestamp(parts[1])
                    
                    # Check if timestamp conversion was successful
                    if start_time is None or end_time is None:
                        continue
                        
                    cheating_intervals.append((start_time, end_time))
        except FileNotFoundError:
            print(f"Warning: gt.txt not found for {subject}. Skipping.")
            continue
            
        # 2. Find and Open Webcam Video
        video_file = next((f for f in os.listdir(subject_path) if f.endswith("1.avi")), None)
        if not video_file:
            print(f"Warning: Webcam video not found for {subject}. Skipping.")
            continue
        
        cap = cv2.VideoCapture(os.path.join(subject_path, video_file))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = 0
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            frame_count += 1
            # Process every Nth frame to speed up and reduce data redundancy
            if frame_count % 5 != 0: 
                continue

            current_time_sec = frame_count / fps
            
            # 3. Label the frame
            is_cheating = any(start <= current_time_sec <= end for start, end in cheating_intervals)
            label_folder = cheating_dir if is_cheating else not_cheating_dir

            # 4. Detect landmarks and crop eyes
            img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = mp_face_mesh.process(img_rgb)
            
            if results.multi_face_landmarks:
                face_landmarks = results.multi_face_landmarks[0].landmark
                
                # Crop and save left eye
                l_x1, l_y1, l_x2, l_y2 = get_eye_bounding_box(face_landmarks, LEFT_EYE_BOUNDS, frame.shape)
                left_eye_crop = frame[l_y1:l_y2, l_x1:l_x2]
                if left_eye_crop.size > 0:
                    left_eye_resized = cv2.resize(left_eye_crop, EYE_IMAGE_SIZE)
                    filename = f"{subject}_frame{frame_count}_left.png"
                    cv2.imwrite(os.path.join(label_folder, filename), left_eye_resized)
                
                # Crop and save right eye
                r_x1, r_y1, r_x2, r_y2 = get_eye_bounding_box(face_landmarks, RIGHT_EYE_BOUNDS, frame.shape)
                right_eye_crop = frame[r_y1:r_y2, r_x1:l_x2]
                if right_eye_crop.size > 0:
                    right_eye_resized = cv2.resize(right_eye_crop, EYE_IMAGE_SIZE)
                    filename = f"{subject}_frame{frame_count}_right.png"
                    cv2.imwrite(os.path.join(label_folder, filename), right_eye_resized)

        print(f"Finished processing {subject}. Total frames processed: {frame_count // 5}")
        cap.release()

if __name__ == "__main__":
    start_time = time.time()
    process_dataset()
    end_time = time.time()
    print(f"\nData preprocessing finished in {end_time - start_time:.2f} seconds.")

