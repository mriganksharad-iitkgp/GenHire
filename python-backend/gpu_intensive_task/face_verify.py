# main.py
import cv2
import os
from deepface import DeepFace
import time

# --- Constants ---
REGISTERED_FACES_DIR = "registered_faces"
REGISTERED_IMAGE_PATH = os.path.join(REGISTERED_FACES_DIR, "registered_face.jpg")
FONT = cv2.FONT_HERSHEY_SIMPLEX
WINDOW_NAME = "Facial Registration and Verification"

def ensure_dir_exists(directory):
    """Creates the directory if it does not exist."""
    if not os.path.exists(directory):
        os.makedirs(directory)

def register_face():
    """
    Captures a face from the webcam and saves it for registration.
    """
    ensure_dir_exists(REGISTERED_FACES_DIR)
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to capture frame.")
            break

        # Display instructions
        cv2.putText(frame, "Press 's' to save the image for registration.", (10, 30), FONT, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, "Press 'q' to quit.", (10, 60), FONT, 0.7, (0, 0, 255), 2)
        
        cv2.imshow(WINDOW_NAME, frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('s'):
            # Save the captured frame
            cv2.imwrite(REGISTERED_IMAGE_PATH, frame)
            print(f"Image saved to {REGISTERED_IMAGE_PATH}")
            break
        elif key == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()
    # Add a small delay to ensure the window is properly closed
    cv2.waitKey(1)


def verify_face():
    """
    Verifies faces from the webcam feed against the registered face.
    """
    if not os.path.exists(REGISTERED_IMAGE_PATH):
        print("Error: No registered face found. Please register a face first.")
        return

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    verification_result = {"verified": False, "distance": float('inf')}
    last_check_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to capture frame.")
            break
            
        current_time = time.time()
        
        # Perform verification every 2 seconds to reduce processing load
        if current_time - last_check_time >= 2:
            try:
                # The core of the verification logic
                result = DeepFace.verify(
                    img1_path=REGISTERED_IMAGE_PATH,
                    img2_path=frame,
                    model_name='VGG-Face',
                    detector_backend='opencv',
                    enforce_detection=False # Allow processing even if face is not perfectly detected
                )
                verification_result = result
                print("Verification Result:", verification_result)

            except Exception as e:
                # This can happen if no face is detected in the frame
                print(f"Could not verify face: {e}")
                verification_result = {"verified": False, "distance": float('inf')}
            
            last_check_time = current_time


        # Display the verification status on the frame
        if verification_result.get("verified"):
            status_text = "VERIFIED"
            color = (0, 255, 0) # Green
        else:
            status_text = "NOT VERIFIED"
            color = (0, 0, 255) # Red

        try:
            # Find face coordinates to draw a rectangle
            face_objs = DeepFace.extract_faces(
                img_path=frame, 
                detector_backend='opencv', 
                enforce_detection=False
            )
            if face_objs:
                face_area = face_objs[0]['facial_area']
                x, y, w, h = face_area['x'], face_area['y'], face_area['w'], face_area['h']
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                
                # Place status text above the rectangle
                text_size = cv2.getTextSize(status_text, FONT, 1, 2)[0]
                text_x = x + (w - text_size[0]) // 2
                text_y = y - 10
                cv2.putText(frame, status_text, (text_x, text_y), FONT, 1, color, 2, cv2.LINE_AA)

        except Exception as e:
            print(f"Could not draw rectangle: {e}")

        # Display general instructions
        cv2.putText(frame, "Press 'q' to quit verification.", (10, 30), FONT, 0.7, (255, 255, 255), 2)
        cv2.imshow(WINDOW_NAME, frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    # Add a small delay
    cv2.waitKey(1)


def main():
    """
    Main function to run the application.
    """
    while True:
        print("\n--- Facial Recognition System ---")
        print("1. Register a new face")
        print("2. Verify face")
        print("3. Exit")
        choice = input("Enter your choice (1/2/3): ")

        if choice == '1':
            register_face()
        elif choice == '2':
            verify_face()
        elif choice == '3':
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")

if __name__ == "__main__":
    main()
