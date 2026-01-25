# GPU Usage in Backend

This backend does **not** perform real-time inference or machine learning (ML) model training. Instead, it utilizes pre-trained ML models (such as YOLO, pyannote, and MediaPipe) for backend processing tasks, including:

- **Speaker analysis** in recordings
- **Object detection** in videos
- **Gaze/proctoring analysis**
- **CV scoring**

These tasks are typically executed as batch or background jobs, triggered by user uploads or API requests. Results are returned asynchronously (not in real-time).

## Summary

- **No real-time inference:** No live video stream analysis with instant response.
- **No model training:** No code for fitting or updating ML models.
- **Backend ML compute only:** Uses pre-trained models to process uploaded files.

This architecture is well-suited for queue-based, asynchronous ML processing with Dockerized ML workers.