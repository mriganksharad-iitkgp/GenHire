# GPU Usage in Backend

This backend performs **lightweight real-time inference** for live proctoring and utilizes heavier pre-trained ML models (such as YOLO, pyannote, and MediaPipe) for backend processing tasks, including:

**Real-time processing:**

- **Gaze/proctoring analysis** - Live gaze tracking using MediaPipe during interviews (WebSocket-based)
  - **Scaling note:** While MediaPipe is CPU-efficient per user, 100+ concurrent video streams may require GPU acceleration or horizontal scaling with load balancing

**Batch/background processing:**

- **Speaker analysis** in recordings
- **Object detection** in videos
- **CV scoring**

The heavy ML tasks are executed as batch or background jobs, triggered by user uploads or API requests. Results are returned asynchronously.

## Summary

- **Real-time inference (scale-dependent):** Live gaze tracking using MediaPipe - CPU-based for low concurrency, may need GPU or horizontal scaling for 50+ concurrent users.
- **Heavy batch inference:** YOLO, pyannote, and other models for post-processing uploaded files.
- **No model training:** No code for fitting or updating ML models.
- **Mixed architecture:** Real-time proctoring + asynchronous background ML processing.

## Scaling Considerations

- **Low concurrency (1-20 users):** CPU-only MediaPipe is sufficient
- **Medium concurrency (20-50 users):** Monitor CPU usage, consider GPU acceleration
- **High concurrency (50+ users):** Likely requires GPU acceleration or multi-instance deployment with load balancing

This architecture supports both live interview monitoring and queue-based, asynchronous ML processing with Dockerized ML workers.
