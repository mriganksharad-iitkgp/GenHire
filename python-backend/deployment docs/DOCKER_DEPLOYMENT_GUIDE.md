# Docker Deployment Guide

## Current Project Structure Issues

| Issue                  | Problem                              | Solution                    |
| ---------------------- | ------------------------------------ | --------------------------- |
| **Monolithic app.py**  | Heavy ML imports block startup       | Separate API and ML workers |
| **Local file storage** | `uploads/` not portable              | Use R2/S3 object storage    |
| **Mixed dependencies** | GPU libs (torch, YOLO) with API libs | Multi-container setup       |
| **No health checks**   | Hard to monitor                      | Add `/health` endpoint      |
| **Secrets in code**    | `.env` not production-ready          | Use Docker secrets/env      |

---

## Recommended Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                    DOCKER COMPOSE / KUBERNETES                    │
│                                                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────────┐ │
│  │   API SERVICE   │  │   ML WORKER     │  │     REDIS         │ │
│  │   (Flask)       │  │   (GPU)         │  │   (Session Cache) │ │
│  │                 │  │                 │  │                   │ │
│  │ - auth routes   │  │ - YOLO          │  │ - session cache   │ │
│  │ - job routes    │  │ - pyannote      │  │                   │ │
│  │ - profile       │  │ - mediapipe     │  │                   │ │
│  │ - SocketIO      │  │ - CV scoring    │  │                   │ │
│  └────────┬────────┘  └────────┬────────┘  └────────────────────┘ │
│           │                    │                                   │
│           └────────────────────┘                                   │
│                       │                                            │
│                       ▼                                            │
│           ┌────────────────────────────┐                           │
│           │   MESSAGE QUEUE            │                           │
│           │   (RabbitMQ + Celery)      │                           │
│           └────────────────────────────┘                           │
└────────────────────────────────────────────────────────────────────┘
                                  │
                  ┌───────────────┼───────────────┐
                  ▼               ▼               ▼
          ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
          │ MongoDB Atlas│ │ Cloudflare R2│ │ External APIs│
          │              │ │ (uploads)    │ │ (Groq, etc.) │
          └──────────────┘ └──────────────┘ └──────────────┘
```

---

## Proposed Folder Restructure

```
python-backend/
├── docker/
│   ├── Dockerfile.api          # Lightweight API container
│   ├── Dockerfile.worker       # GPU-enabled ML worker
│   ├── docker-compose.yml      # Local development
│   └── docker-compose.prod.yml # Production setup
│
├── api/                        # API-only code (no ML)
│   ├── app.py                  # Slim Flask app
│   ├── routes/
│   ├── controllers/
│   ├── middleware/
│   └── models/
│
├── workers/                    # ML processing workers
│   ├── recording_worker.py     # YOLO, pyannote tasks
│   ├── proctoring_worker.py    # MediaPipe tasks
│   └── cv_scoring_worker.py    # CV analysis tasks
│
├── shared/                     # Shared utilities
│   ├── config/
│   ├── utils/
│   └── queue/                  # Redis/Celery setup
│
├── requirements/
│   ├── base.txt                # Common dependencies
│   ├── api.txt                 # API-only deps
│   └── ml.txt                  # ML/GPU deps
│
└── scripts/
    ├── start-api.sh
    ├── start-worker.sh
    └── healthcheck.sh
```

---

## Dockerfile Examples

### API Container (Lightweight)

```dockerfile
# filepath: python-backend/docker/Dockerfile.api
FROM python:3.11-slim

WORKDIR /app

# Install only API dependencies
COPY requirements/base.txt requirements/api.txt ./
RUN pip install --no-cache-dir -r api.txt

# Copy API code only
COPY api/ ./api/
COPY shared/ ./shared/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "api.app:app"]
```

### ML Worker Container (GPU)

```dockerfile
# filepath: python-backend/docker/Dockerfile.worker
FROM nvidia/cuda:12.1-runtime-ubuntu22.04

WORKDIR /app

# Install Python and dependencies
RUN apt-get update && apt-get install -y python3.11 python3-pip ffmpeg libsm6 libxext6

COPY requirements/base.txt requirements/ml.txt ./
RUN pip install --no-cache-dir -r ml.txt

# Copy worker code
COPY workers/ ./workers/
COPY shared/ ./shared/

# Use Celery to run the worker (recommended for production)
CMD ["celery", "-A", "workers.recording_worker", "worker", "--loglevel=info"]
```

---

## Docker Compose

```yaml
# filepath: python-backend/docker/docker-compose.yml
version: "3.8"

services:
  api:
    build:
      context: ..
      dockerfile: docker/Dockerfile.api
    ports:
      - "5000:5000"
    environment:
      - MONGODB_URI=${MONGODB_URI}
      - JWT_SECRET=${JWT_SECRET}
      - REDIS_URL=redis://redis:6379
      - R2_ENDPOINT=${R2_ENDPOINT}
      - R2_ACCESS_KEY=${R2_ACCESS_KEY}
      - R2_SECRET_KEY=${R2_SECRET_KEY}
    depends_on:
      - redis
    restart: unless-stopped

  ml-worker:
    build:
      context: ..
      dockerfile: docker/Dockerfile.worker
    environment:
      - REDIS_URL=redis://redis:6379
      - HF_TOKEN=${HF_TOKEN}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    depends_on:
      - redis
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  redis_data:
```

---

## Requirements Split

### base.txt (Shared)

```txt
# filepath: python-backend/requirements/base.txt
python-dotenv==1.0.0
pymongo==4.6.0
redis==5.0.0
celery==5.3.0
boto3==1.34.0          # For R2/S3
```

### api.txt (API Only)

```txt
# filepath: python-backend/requirements/api.txt
-r base.txt
flask==3.0.0
flask-cors==4.0.0
flask-socketio==5.3.0
gunicorn==21.2.0
eventlet==0.33.0
python-jose==3.3.0
bcrypt==4.1.0
Werkzeug==3.0.0
```

### ml.txt (ML Workers)

```txt
# filepath: python-backend/requirements/ml.txt
-r base.txt
torch==2.1.0
torchvision==0.16.0
ultralytics==8.0.0      # YOLO
pyannote.audio==3.1.0
mediapipe==0.10.0
opencv-python==4.8.0
librosa==0.10.0
```

---

## Code Changes Required

### 1. Add Health Check Endpoint

```python
# filepath: python-backend/api/app.py
@app.route('/health', methods=['GET'])
def health_check():
    """Health check for load balancers and container orchestration."""
    try:
        # Check MongoDB connection
        db.command('ping')
        # Check Redis connection
        redis_client.ping()
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'services': {
                'mongodb': 'connected',
                'redis': 'connected'
            }
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503
```

### 2. Queue-Based ML Processing

```python
# filepath: python-backend/workers/recording_worker.py
from celery import Celery
from services.recording_analysis_service import RecordingAnalyzer

app = Celery('ml_worker', broker='redis://redis:6379/0')

analyzer = RecordingAnalyzer()

@app.task(bind=True, max_retries=3)
def analyze_recording(self, file_path: str, job_id: str):
    """Process recording in background."""
    try:
        result = analyzer.run_full_analysis(file_path)
        # Store result in MongoDB
        db.recordings.update_one(
            {'_id': ObjectId(job_id)},
            {'$set': {'analysis': result, 'status': 'completed'}}
        )
        return result
    except Exception as e:
        self.retry(exc=e, countdown=60)
```

### 3. Replace Local Storage with R2

```python
# filepath: python-backend/shared/storage.py
import boto3
from botocore.config import Config

class R2Storage:
    def __init__(self):
        self.client = boto3.client(
            's3',
            endpoint_url=os.getenv('R2_ENDPOINT'),
            aws_access_key_id=os.getenv('R2_ACCESS_KEY'),
            aws_secret_access_key=os.getenv('R2_SECRET_KEY'),
            config=Config(signature_version='s3v4')
        )
        self.bucket = os.getenv('R2_BUCKET', 'uploads')

    def upload_file(self, file_path: str, key: str) -> str:
        """Upload file to R2 and return URL."""
        self.client.upload_file(file_path, self.bucket, key)
        return f"{os.getenv('R2_PUBLIC_URL')}/{key}"

    def download_file(self, key: str, local_path: str):
        """Download file from R2."""
        self.client.download_file(self.bucket, key, local_path)

    def delete_file(self, key: str):
        """Delete file from R2."""
        self.client.delete_object(Bucket=self.bucket, Key=key)
```

### 4. Update app.py to Queue ML Tasks

```python
# filepath: python-backend/api/app.py (modified)
from workers.recording_worker import analyze_recording

@app.route('/api/recordings/analyze', methods=['POST'])
@token_required
def start_recording_analysis(current_user):
    """Queue recording for analysis."""
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'No file provided'}), 400

    # Upload to R2
    key = f"recordings/{current_user['_id']}/{secure_filename(file.filename)}"
    storage.upload_file(file, key)

    # Create job record
    job = db.recordings.insert_one({
        'user_id': current_user['_id'],
        'file_key': key,
        'status': 'queued',
        'created_at': datetime.utcnow()
    })

    # Queue ML task
    analyze_recording.delay(key, str(job.inserted_id))

    return jsonify({
        'job_id': str(job.inserted_id),
        'status': 'queued'
    }), 202
```

---

## Best Practices Checklist

### Container Best Practices

- [ ] Use multi-stage builds to reduce image size
- [ ] Run as non-root user
- [ ] Use `.dockerignore` to exclude unnecessary files
- [ ] Pin dependency versions
- [ ] Add health checks
- [ ] Use slim/alpine base images for API

### Security

- [ ] Never commit secrets (use Docker secrets or env vars)
- [ ] Scan images for vulnerabilities (`docker scan`)
- [ ] Use read-only file systems where possible
- [ ] Limit container resources (CPU/memory)

### Performance

- [ ] Separate CPU and GPU workloads
- [ ] Use Redis for caching and queues
- [ ] Enable gunicorn workers based on CPU cores
- [ ] Use connection pooling for MongoDB

### Monitoring

- [ ] Add structured logging (JSON format)
- [ ] Export metrics (Prometheus format)
- [ ] Set up alerts for container health
- [ ] Log to external service (CloudWatch, Datadog)

---

## .dockerignore

```
# filepath: python-backend/.dockerignore
.git
.gitignore
.env
.env.*
__pycache__
*.pyc
*.pyo
.pytest_cache
.vscode
uploads/
*.md
tests/
docker-compose*.yml
Dockerfile*
```

---

## Migration Steps

1. **Phase 1: Add Docker support (no code changes)**
   - Create `Dockerfile.api` for current monolithic app
   - Test locally with `docker-compose`

2. **Phase 2: Extract ML workers**
   - Set up Redis queue
   - Move ML code to background workers
   - Update API to queue tasks

3. **Phase 3: External storage**
   - Configure R2/S3
   - Migrate file uploads
   - Update file handling code

4. **Phase 4: Production deployment**
   - Set up container registry (ECR, GCR)
   - Deploy to ECS/GKE/Kubernetes
   - Configure Cloudflare Tunnel

---

## Quick Start (Development)

```bash
# Build and run
cd python-backend
docker-compose -f docker/docker-compose.yml up --build

# Check logs
docker-compose logs -f api
docker-compose logs -f ml-worker

# Scale workers
docker-compose up --scale ml-worker=3
```

---

## Summary

| Component     | Container           | Resources            |
| ------------- | ------------------- | -------------------- |
| **Flask API** | `Dockerfile.api`    | 2 vCPU, 4GB RAM      |
| **ML Worker** | `Dockerfile.worker` | 4 vCPU, 8GB RAM, GPU |
| **Redis**     | Official image      | 1 vCPU, 2GB RAM      |
| **Storage**   | Cloudflare R2       | External             |
| **Database**  | MongoDB Atlas       | External             |

**Key takeaway:** Separate API and ML workloads into different containers for independent scaling and resource allocation.
