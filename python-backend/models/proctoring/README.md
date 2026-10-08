# Object detector artifact

The API finds `yolov8n.onnx` here by default. Generate it before building the
backend image with `scripts/provision_proctoring_model.py`; binary weights are
excluded from Git. See `docs/proctoring-model-setup.md` at the repository root.

Locally provisioned 2026-10-08 with Python 3.12.10, Ultralytics 8.3.193,
PyTorch 2.6.0+cpu, ONNX 1.17.0, OpenCV 4.11.0 and NumPy 1.26.4. Official
checkpoint: https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt

Expected raw output: `[1, 84, 8400]`; static FP32 640px, opset 12, no NMS.
The accompanying `.sha256` records the locally exported artifact, not an
upstream guarantee of a reproducible binary. Preserve it with your deployment.
