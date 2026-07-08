# cv_jd_processing — standalone FastAPI microservice

Separately deployed CV/JD text-scoring service. **Not imported by the main
Flask app** (`app.py` / `core/factory.py`); it has its own `requirements.txt`
and runs under uvicorn on its own. Excluded from the main backend's Docker
image via `.dockerignore`.
