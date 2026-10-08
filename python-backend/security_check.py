"""Bounded lazy CPU camera analysis; missing checks are coverage gaps.

OpenCV detects faces without loading TensorFlow. Provisioned YOLOv8 ONNX,
MediaPipe, and DeepFace add objects, pose, and identity continuity. Candidate
requests never download weights and technical failures never deduct scores.
"""
import base64
import logging
import os
import threading
from pathlib import Path

logger = logging.getLogger(__name__)
MAX_FRAME_BYTES = 2 * 1024 * 1024
# Bound compressed-image expansion before OpenCV is first imported.
os.environ.setdefault("OPENCV_IO_MAX_IMAGE_PIXELS", "16777216")
_detector_lock = threading.Lock()
_face_detector = None
_pose_detector = None
_pose_checked = False
_object_net = None
_object_path = None
_object_failed = None
DEFAULT_OBJECT_MODEL_PATH = Path(__file__).resolve().parent / "models" / "proctoring" / "yolov8n.onnx"


def decode_frame(image_data):
    if not isinstance(image_data, str) or len(image_data) > MAX_FRAME_BYTES * 2:
        raise ValueError("Camera frame is missing or too large")
    import cv2
    import numpy as np
    raw = base64.b64decode(image_data.split(",", 1)[-1], validate=True)
    if len(raw) > MAX_FRAME_BYTES:
        raise ValueError("Camera frame is too large")
    frame = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None or max(frame.shape[:2]) > 4096:
        raise ValueError("Invalid camera frame")
    height, width = frame.shape[:2]
    if max(height, width) > 640:
        ratio = 640 / max(height, width)
        frame = cv2.resize(frame, (round(width * ratio), round(height * ratio)))
    return frame


def detect_faces(frame):
    global _face_detector
    import cv2
    with _detector_lock:
        if _face_detector is None:
            _face_detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            if _face_detector.empty():
                _face_detector = None
                raise RuntimeError("Face detector could not be loaded")
        gray = cv2.equalizeHist(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        return list(_face_detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40)))


def _head_pose(frame):
    global _pose_detector, _pose_checked
    import cv2
    import numpy as np
    with _detector_lock:
        if not _pose_checked:
            _pose_checked = True
            try:
                import mediapipe as mp
                _pose_detector = mp.solutions.face_mesh.FaceMesh(max_num_faces=2, refine_landmarks=False)
            except Exception:
                logger.info("MediaPipe pose check unavailable")
        if _pose_detector is None:
            return False, None
        result = _pose_detector.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    faces = result.multi_face_landmarks or []
    if len(faces) != 1:
        return True, None
    height, width = frame.shape[:2]
    landmarks = faces[0].landmark
    model = np.array([[0, 0, 0], [0, -330, -65], [-225, 170, -135], [225, 170, -135], [-150, -150, -125], [150, -150, -125]], dtype=np.float64)
    points = np.array([(landmarks[i].x * width, landmarks[i].y * height) for i in (1, 152, 263, 33, 287, 57)], dtype=np.float64)
    camera = np.array([[width, 0, width / 2], [0, width, height / 2], [0, 0, 1]], dtype=np.float64)
    success, rotation, _ = cv2.solvePnP(model, points, camera, np.zeros((4, 1)))
    if not success:
        return True, None
    matrix, _ = cv2.Rodrigues(rotation)
    return True, float(cv2.RQDecomp3x3(matrix)[0][1])


def _objects(frame):
    """YOLOv8 raw [1,84,N] COCO ONNX, 640px input, no embedded NMS."""
    global _object_net, _object_path, _object_failed
    path = os.getenv("PROCTORING_OBJECT_MODEL_PATH", "").strip() or str(DEFAULT_OBJECT_MODEL_PATH)
    if not path or not os.path.isfile(path) or path == _object_failed:
        return False, []
    import cv2
    import numpy as np
    with _detector_lock:
        try:
            if _object_net is None or _object_path != path:
                _object_net = cv2.dnn.readNetFromONNX(path)
                _object_path = path
            height, width = frame.shape[:2]
            scale = 640 / max(width, height)
            resized = cv2.resize(frame, (round(width * scale), round(height * scale)))
            canvas = np.full((640, 640, 3), 114, dtype=np.uint8)
            left, top = (640 - resized.shape[1]) // 2, (640 - resized.shape[0]) // 2
            canvas[top:top + resized.shape[0], left:left + resized.shape[1]] = resized
            _object_net.setInput(cv2.dnn.blobFromImage(canvas, 1 / 255.0, (640, 640), swapRB=True, crop=False))
            predictions = np.asarray(_object_net.forward()).squeeze()
            if predictions.ndim != 2:
                raise ValueError("Expected raw YOLOv8 ONNX predictions")
            if predictions.shape[0] == 84:
                predictions = predictions.T
            if predictions.shape[1] != 84:
                raise ValueError("Model must use 80 COCO classes without embedded NMS")
            names = {0: "person", 67: "cell phone", 73: "book"}
            prohibited = {item.strip() for item in os.getenv("PROCTORING_PROHIBITED_OBJECTS", "cell phone,book").split(",")}
            wanted = {key: name for key, name in names.items() if name == "person" or name in prohibited}
            detections = []
            for class_id, name in wanted.items():
                candidates = predictions[predictions[:, 4 + class_id] >= 0.6]
                boxes, scores = [], []
                for row in candidates:
                    cx, cy, bw, bh = row[:4]
                    boxes.append([float(cx - bw / 2), float(cy - bh / 2), float(bw), float(bh)])
                    scores.append(float(row[4 + class_id]))
                indices = cv2.dnn.NMSBoxes(boxes, scores, 0.6, 0.45)
                for index in np.asarray(indices).reshape(-1):
                    detections.append({"class": name, "confidence": scores[int(index)]})
            return True, detections
        except Exception as exc:
            _object_failed = path
            logger.warning("Object detector unavailable (%s): %s", path, exc)
            return False, []


def analyze_frame(current_frame, registered_face_img=None, config=None, source="desktop", check_identity=False):
    config = config or {}
    capabilities = {"face_detection": False, "object_detection": False, "head_pose": False, "identity_continuity": False}
    violations, errors, face_count = [], [], None
    try:
        face_count = len(detect_faces(current_frame))
        capabilities["face_detection"] = True
        # No frontal face in the side-view phone is expected.
        if source == "desktop" and face_count == 0:
            violations.append({"type": "no_face", "message": "No face detected. Please stay visible in the laptop camera."})
        elif face_count > 1:
            violations.append({"type": "multiple_faces", "message": "Multiple faces detected. Only the candidate should be visible."})
    except Exception as exc:
        errors.append(f"face_detection: {type(exc).__name__}")
    if source == "desktop" and face_count == 1 and config.get("eyeball_tracking", True):
        try:
            available, yaw = _head_pose(current_frame)
            capabilities["head_pose"] = available
            if yaw is not None and abs(yaw) > 35:
                violations.append({"type": "head_turn", "message": "Please keep your face directed toward the interview screen."})
        except Exception as exc:
            errors.append(f"head_pose: {type(exc).__name__}")
    if config.get("object_detection", True):
        available, objects = _objects(current_frame)
        capabilities["object_detection"] = available
        if sum(obj["class"] == "person" for obj in objects) > 1 and not any(v["type"] == "multiple_faces" for v in violations):
            violations.append({"type": "multiple_faces", "message": "Multiple people detected. The interview space must be private."})
        if any(obj["class"] == "cell phone" for obj in objects):
            violations.append({"type": "phone_detected", "message": "A phone is visible. Keep additional phones away from your interview workspace."})
        others = sorted({obj["class"] for obj in objects if obj["class"] not in {"person", "cell phone"}})
        if others:
            violations.append({"type": "prohibited_object", "message": f"Unapproved material detected: {', '.join(others)}. Clear your workspace."})
    if check_identity and source == "desktop" and face_count == 1 and registered_face_img is not None:
        try:
            from deepface import DeepFace
            import cv2
            import numpy as np
            reference = registered_face_img
            if isinstance(reference, bytes):
                reference = cv2.imdecode(np.frombuffer(reference, dtype=np.uint8), cv2.IMREAD_COLOR)
            result = DeepFace.verify(img1_path=reference, img2_path=current_frame, model_name="VGG-Face", enforce_detection=True)
            capabilities["identity_continuity"] = True
            if not result.get("verified"):
                violations.append({"type": "identity_mismatch", "message": "Your face could not be matched to the registered capture. Please face the camera."})
        except Exception as exc:
            errors.append(f"identity_continuity: {type(exc).__name__}")
    return {"available": capabilities["face_detection"] or capabilities["object_detection"], "face_count": face_count, "capabilities": capabilities, "violations": violations, "errors": errors}


def analyze_frame_for_proctoring(current_frame, registered_face_img, current_score, infractions):
    """Legacy wrapper; live sockets use per-session confirmation/cooldowns."""
    from services.proctoring_service import PENALTIES
    result = analyze_frame(current_frame, registered_face_img)
    deduction = 0
    for violation in result["violations"]:
        key = violation["type"]
        infractions[key] = infractions.get(key, 0) + 1
        deduction += PENALTIES[key]
    return {"status": result["violations"][0]["message"] if result["violations"] else "Status: OK", "score": max(0, current_score - deduction), "infractions": infractions, "available": result["available"]}


def generate_final_proctoring_report(infractions):
    from services.proctoring_service import score_from_infractions
    return {"final_score": score_from_infractions(infractions), "infraction_counts": infractions, "summary": "No warnings detected." if not infractions else "Review recorded warnings and camera coverage."}
