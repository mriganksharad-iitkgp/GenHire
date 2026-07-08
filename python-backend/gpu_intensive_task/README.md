# gpu_intensive_task — standalone proctoring server

Separately deployed Flask + Socket.IO server for GPU-heavy proctoring
analysis (face verification, cheating detection, recording analysis). **Not
imported by the main Flask app** — the main app's frame-level proctoring uses
the root-level `security_check.py`. Excluded from the main backend's Docker
image via `.dockerignore`.
