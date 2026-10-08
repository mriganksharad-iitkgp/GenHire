# Camera proctoring deployment

The primary Flask API handles laptop analysis and the signed mobile companion.
Send both clients to its Socket.IO endpoint. The optional GPU gaze service is
not a mobile pairing endpoint and cannot replace primary API coverage.

`requirements.txt` now installs OpenCV headless. Face enrollment uses its
local Haar classifier, so it does not initialize TensorFlow or download face
weights. Exactly one frontal face is required. A missing detector returns
`face_detection_unavailable` rather than claiming enrollment succeeded.

## Provision phone, material, and multiple-person detection

Live object inference requires an official YOLOv8 COCO ONNX artifact. The API
never downloads a model while a candidate waits. Export it in an isolated
Python 3.11 or 3.12 environment before building the deployment:

```powershell
python -m venv .model-export
.model-export/Scripts/python.exe -m pip install ultralytics==8.3.193 onnx==1.17.0 opencv-python-headless==4.11.0.86 numpy==1.26.4
.model-export/Scripts/python.exe python-backend/scripts/provision_proctoring_model.py --download --output python-backend/models/proctoring/yolov8n.onnx
.model-export/Scripts/python.exe -m pip freeze > model-export-requirements.txt
```

The provisioner exports a static FP32 640px model with raw COCO class scores,
ONNX opset 12, and no embedded NMS; then loads it through the API's OpenCV DNN
runtime and verifies its output. Preserve the model, generated checksum, and
exporter dependency list together. Include the ONNX file in the backend image
or mount it at a readable location. Set:

```dotenv
PROCTORING_OBJECT_MODEL_PATH=/app/models/proctoring/yolov8n.onnx
PROCTORING_PROHIBITED_OBJECTS=cell phone,book
```

These export options follow the official
[Ultralytics export documentation](https://docs.ultralytics.com/modes/export/)
and [ONNX integration documentation](https://docs.ultralytics.com/integrations/onnx/).
The parser supports raw YOLOv8 COCO predictions, not arbitrary ONNX models.
It warns for additional phones, configured materials, and multiple people;
normal furniture and the companion's laptop are permitted. Detections need
two successive observations and are scored at most once per 15 seconds.

## Optional checks and coverage

MediaPipe can add head-pose observations. DeepFace identity continuity is
opt-in with `PROCTORING_IDENTITY_ENABLED=true`; provision its weights before
enabling this in production. Head pose is not a completed eyeball-tracking
check. Voice detection and gaze heatmaps also require their own working
pipelines. The final report lists missing configured checks as `partial`;
zero analyzed laptop frames produce an unavailable score, never a default
100. A side-view phone without a frontal face is normal and does not reduce
the score. Camera failures/disconnections are coverage gaps rather than
cheating findings.

Mobile pairing credentials are signed, owner/session bound, and valid for
three hours. Readiness requires camera and microphone permission, a heartbeat
within 15 seconds, and a decoded preview frame within 15 seconds. Phone frames
run during setup to prove capture works, with scoring only after activation.
Reconnecting a phone revokes the previous socket. Uploads validate the signed
capability even after the desktop has ended the interview.

Run the local regressions with:

```powershell
python -m unittest discover -s python-backend/tests -p test_proctoring_flow.py -v
```

Before deployment, validate the provisioned artifact on representative camera
samples and measure CPU frame latency. The automated tests cover decoding,
authorization, pairing freshness, and scoring policy; they do not establish
object-model accuracy on real interview footage.

Local provision/check on 2026-10-08 succeeded with Python 3.12.10 and CPU
PyTorch 2.6.0. The checksum is retained in
`python-backend/models/proctoring/yolov8n.onnx.sha256`. Binary model weights
are Git-ignored: provision them again in a fresh checkout before building the
backend image. Do not assume a clone includes the working local model.

Warm blank-frame inference averaged 91 ms over five frames on the development
Intel i5-1155G7 laptop (cold first call 178 ms). Representative footage and
deployment concurrency still require a measured acceptance pass.
