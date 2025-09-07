import cv2
import mediapipe as mp
import numpy as np
import time

# --- Timer Variables ---
print_interval = 2  # Time in seconds between prints
last_print_time = 0 # Timestamp of the last print

# Initialize MediaPipe solutions
mp_face_mesh = mp.solutions.face_mesh
mp_drawing = mp.solutions.drawing_utils

# --- Define Drawing Specs ---
drawing_spec_face = mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=1, circle_radius=1) # Green
drawing_spec_eyes = mp_drawing.DrawingSpec(color=(255, 255, 0), thickness=1, circle_radius=1) # Yellow
drawing_spec_iris = mp_drawing.DrawingSpec(color=(0, 255, 255), thickness=1, circle_radius=1) # Cyan

# Initialize Face Mesh model
face_mesh = mp_face_mesh.FaceMesh(static_image_mode=False,
                                  max_num_faces=1,
                                  refine_landmarks=True,
                                  min_detection_confidence=0.5,
                                  min_tracking_confidence=0.5)

# Start video capture
cap = cv2.VideoCapture(0)

# --- Landmark Indices ---
# Iris centers
P_LEFT_IRIS = 473
P_RIGHT_IRIS = 468
# Face origin
P_NOSE_TIP = 1
# Eye corners
P_LEFT_EYE_OUTER = 33
P_LEFT_EYE_INNER = 133
P_RIGHT_EYE_OUTER = 263
P_RIGHT_EYE_INNER = 362


while cap.isOpened():
    success, image = cap.read()
    if not success:
        print("Ignoring empty camera frame.")
        continue

    # Flip the image horizontally and convert BGR to RGB
    image = cv2.cvtColor(cv2.flip(image, 1), cv2.COLOR_BGR2RGB)
    
    # Process the image to find face landmarks
    image.flags.writeable = False
    results = face_mesh.process(image)

    # Prepare image for drawing by converting back to BGR
    image.flags.writeable = True
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    
    if results.multi_face_landmarks:
        for face_landmarks in results.multi_face_landmarks:
            
            # --- 1. DRAW THE SHAPES ---
            mp_drawing.draw_landmarks(image=image, landmark_list=face_landmarks, connections=mp_face_mesh.FACEMESH_CONTOURS,
                                      landmark_drawing_spec=None, connection_drawing_spec=drawing_spec_face)
            mp_drawing.draw_landmarks(image=image, landmark_list=face_landmarks, connections=mp_face_mesh.FACEMESH_LEFT_EYE,
                                      landmark_drawing_spec=None, connection_drawing_spec=drawing_spec_eyes)
            mp_drawing.draw_landmarks(image=image, landmark_list=face_landmarks, connections=mp_face_mesh.FACEMESH_RIGHT_EYE,
                                      landmark_drawing_spec=None, connection_drawing_spec=drawing_spec_eyes)
            mp_drawing.draw_landmarks(image=image, landmark_list=face_landmarks, connections=mp_face_mesh.FACEMESH_IRISES,
                                      landmark_drawing_spec=None, connection_drawing_spec=drawing_spec_iris)

            # --- 2. GET AND PRINT THE COORDINATES (with a delay) ---
            
            current_time = time.time()
            if (current_time - last_print_time) > print_interval:
                last_print_time = current_time # Reset the timer

                landmarks = np.array([(lm.x, lm.y, lm.z) for lm in face_landmarks.landmark])

                # Get coordinates for all relevant points
                left_iris = landmarks[P_LEFT_IRIS]
                right_iris = landmarks[P_RIGHT_IRIS]
                nose_tip = landmarks[P_NOSE_TIP]
                
                left_eye_inner = landmarks[P_LEFT_EYE_INNER]
                left_eye_outer = landmarks[P_LEFT_EYE_OUTER]
                right_eye_inner = landmarks[P_RIGHT_EYE_INNER]
                right_eye_outer = landmarks[P_RIGHT_EYE_OUTER]

                # --- Calculate Relative Positions ---
                # A) Position of iris between the eye corners (normalized 0.0 to 1.0)
                left_eye_span = left_eye_inner[0] - left_eye_outer[0]
                left_eye_pos = (left_eye_inner[0] - left_iris[0]) / left_eye_span

                right_eye_span = right_eye_outer[0] - right_eye_inner[0]
                right_eye_pos = (right_iris[0] - right_eye_inner[0]) / right_eye_span

                # B) Position of iris relative to the face (nose tip)
                rel_iris_to_face_left = left_iris - nose_tip
                rel_iris_to_face_right = right_iris - nose_tip
                
                # Print the coordinates
                print("--- Eye Position ---")
                print(f"  Left Eye Pos (0=inner, 1=outer): {left_eye_pos:.3f}")
                print(f"  Right Eye Pos (0=inner, 1=outer): {right_eye_pos:.3f}")
                print("\n--- Iris Position on Face (from Nose) ---")
                print(f"  Left: x={rel_iris_to_face_left[0]:.3f}, y={rel_iris_to_face_left[1]:.3f}")
                print(f"  Right: x={rel_iris_to_face_right[0]:.3f}, y={rel_iris_to_face_right[1]:.3f}")
                print("="*40)


    # Display the resulting frame
    cv2.imshow('Face and Eye Tracking', image)

    # Exit on 'ESC' key
    if cv2.waitKey(5) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()