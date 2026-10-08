"""Export/validate the object model before building the API deployment.

Requires an isolated exporter environment with ultralytics + onnx installed.
The production API needs only OpenCV and the resulting ONNX artifact.
"""
import argparse
import hashlib
import shutil
from pathlib import Path


def validate(path):
    import cv2
    import numpy as np
    network = cv2.dnn.readNetFromONNX(str(path))
    network.setInput(np.zeros((1, 3, 640, 640), dtype=np.float32))
    output = np.asarray(network.forward())
    if output.ndim != 3 or output.shape[0] != 1 or 84 not in output.shape[1:]:
        raise ValueError(f"Unsupported output {output.shape}; require raw COCO YOLOv8 [1,84,N]")
    return output.shape


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", default="yolov8n.pt", help="Local official YOLOv8 COCO checkpoint")
    parser.add_argument("--download", action="store_true", help="Allow Ultralytics to fetch the official checkpoint during provisioning")
    parser.add_argument("--output", type=Path, default=Path("models/proctoring/yolov8n.onnx"))
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if not args.validate_only:
        weights = Path(args.weights)
        if not weights.is_file() and not args.download:
            parser.error("Weights do not exist. Supply a local --weights file or explicitly --download during provisioning.")
        from ultralytics import YOLO
        model = YOLO(str(weights))
        exported = Path(model.export(format="onnx", imgsz=640, batch=1, dynamic=False, half=False, simplify=False, opset=12, nms=False, device="cpu"))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if exported.resolve() != args.output.resolve():
            shutil.copyfile(exported, args.output)
    shape = validate(args.output)
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    args.output.with_suffix(".onnx.sha256").write_text(f"{digest}  {args.output.name}\n", encoding="utf-8")
    print(f"Validated {args.output}: output={shape}, SHA256={digest}")


if __name__ == "__main__":
    main()
