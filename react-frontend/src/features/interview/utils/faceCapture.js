// Client guidance only. The server still requires a valid, single-face image.
export const FACE_HOLD_MS = 1200;

export function facePosition(detections, width, height) {
  if (!detections?.length) return { ready: false, message: "Center your face in the guide." };
  if (detections.length !== 1) return { ready: false, message: "Only you should be visible in the camera." };
  const box = detections[0].boundingBox;
  if (!box || !width || !height) return { ready: false, message: "Waiting for your camera preview…" };
  const x = (box.originX + box.width / 2) / width;
  const y = (box.originY + box.height / 2) / height;
  const size = box.height / height;
  if (size < 0.26) return { ready: false, message: "Move a little closer to your camera." };
  if (size > 0.86 || box.width / width > 0.72) return { ready: false, message: "Move a little farther from your camera." };
  if (x < 0.34 || x > 0.66 || y < 0.24 || y > 0.72) return { ready: false, message: "Center your face in the guide." };
  return { ready: true, x, y, message: "Hold still. Capturing automatically…" };
}

export function captureProgress(previous, position, now) {
  if (!position.ready) return { since: null, progress: 0, captured: false };
  const moved = previous?.x != null && (Math.abs(previous.x - position.x) > 0.045 || Math.abs(previous.y - position.y) > 0.045);
  const since = previous?.since == null || moved ? now : previous.since;
  const progress = Math.min(1, Math.max(0, (now - since) / FACE_HOLD_MS));
  return { since, x: position.x, y: position.y, progress, captured: progress === 1 };
}

export function faceSnapshot(video) {
  if (!video?.videoWidth || !video.videoHeight || video.readyState < 2) throw new Error("Your camera preview is still loading. Please retry in a moment.");
  const canvas = document.createElement("canvas");
  // A 640px image is sufficient for the existing quality gate and ID comparison.
  const ratio = Math.min(1, 640 / video.videoWidth, 480 / video.videoHeight);
  canvas.width = Math.round(video.videoWidth * ratio); canvas.height = Math.round(video.videoHeight * ratio);
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.8);
}

export async function createFaceDetector() {
  const { FaceDetector, FilesetResolver } = await import("@mediapipe/tasks-vision");
  const assets = new URL("/assets/", window.location.origin).href;
  const runtime = await FilesetResolver.forVisionTasks(assets.slice(0, -1));
  return FaceDetector.createFromOptions(runtime, {
    baseOptions: { modelAssetPath: assets + "blaze_face_short_range.tflite", delegate: "CPU" },
    runningMode: "VIDEO", minDetectionConfidence: 0.65,
  });
}
