# Bundled face capture model

The local automatic-capture guide uses Google's MediaPipe BlazeFace short-range
float16 model (version 1), downloaded from:

https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite

SHA-256: `b4578f35940bf5a1a655214a1cce5cab13eba73c1297cd78e1a04c2380b0152f`.

The MediaPipe Tasks runtime is pinned to `@mediapipe/tasks-vision@0.10.32` under
Apache-2.0. Its WASM/loader files are copied from that dependency during npm
install/start/build. Detection runs locally; only the candidate-approved photo
is submitted to the existing server quality gate. This guide is not identity
verification or a liveness test.
