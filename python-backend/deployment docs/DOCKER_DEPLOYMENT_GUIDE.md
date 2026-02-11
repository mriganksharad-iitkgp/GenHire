# Docker Deployment Guide

## Current Project Structure Issues

| Issue                  | Problem                               | Solution                           |
| ---------------------- | ------------------------------------- | ---------------------------------- |
| **Monolithic app.py**  | Heavy ML imports block startup        | Separate API and ML workers        |
| **Real-time scaling**  | MediaPipe CPU bottleneck at 50+ users | GPU acceleration or load balancing |
| **GPU resource waste** | Separate GPUs for real-time + batch   | Shared GPU with smart scheduling   |
| **Local file storage** | `uploads/` not portable               | Use R2/S3 object storage           |
| **Mixed dependencies** | GPU libs (torch, YOLO) with API libs  | Multi-container setup              |
| **No health checks**   | Hard to monitor                       | Add `/health` endpoint             |
| **Secrets in code**    | `.env` not production-ready           | Use Docker secrets/env             |

---

## Traffic Analysis: 100+ Daily Users, 50+ Concurrent Pattern

### Peak Usage Patterns & Resource Allocation

```
Time Period    │ Concurrent │ Background │ GPU Memory Strategy (16GB)
               │ Interviews │ ML Jobs    │
───────────────┼────────────┼────────────┼────────────────────────────────────────
09:00-17:00    │ 50-60+     │ Queued     │ Real-time: 6GB, Batch: 8GB, Buffer: 2GB
18:00-23:00    │ 20-30      │ Moderate   │ Real-time: 5GB, Batch: 9GB, Buffer: 2GB
00:00-08:00    │ 2-5        │ Heavy      │ Real-time: 4GB, Batch: 10GB, Buffer: 2GB
```

### GPU Memory Allocation Strategy

```
┌────────────────────────────────────────────────────────────────────────┐
│                      16GB SHARED GPU CONTAINER                        │
├───────────────────────┬────────────────────────┬────────────────────────┤
│   PRIORITY ZONE       │    BACKGROUND ZONE    │    SYSTEM ZONE      │
│   (Real-time)         │    (Batch ML)         │    (Buffer)         │
│   4-6GB               │    8-10GB             │    2GB              │
│                       │                       │                     │
│ • MediaPipe           │ • YOLO Object Detect  │ • CUDA Overhead    │
│ • Gaze Tracking       │ • pyannote Diarization│ • Memory Fragmentation│
│ • WebSocket Streams   │ • CV Analysis         │ • Error Recovery   │
│ • <50ms Response      │ • Can be deferred     │ • Process Switching│
└───────────────────────┴────────────────────────┴────────────────────────┘
```

### Cost Analysis: Shared vs Separated GPU Containers

| Architecture      | Monthly Cost | GPU Utilization | Memory Efficiency | Best For               |
| ----------------- | ------------ | --------------- | ----------------- | ---------------------- |
| **Shared GPU**    | ~$300-400    | 80-95%          | 85%               | 100+ daily users       |
| **Separated GPU** | ~$600-800    | 40-60%          | 45%               | 200+ users, enterprise |
| **Savings**       | **50%**      | **2.1x better** | **1.9x better**   | **Startups to growth** |

### Docker Compose Strategy for Traffic Patterns

```yaml
# Shared GPU approach - recommended for 100+ daily users
version: "3.8"
services:
  # Lightweight API - handles auth, routing, file uploads
  api:
    image: interview-api:cpu-only
    replicas: 3 # Horizontal scaling
    resources:
      limits:
        cpu: 2
        memory: 4G

  # Smart GPU scheduler - handles both real-time and batch
  gpu-shared:
    image: interview-gpu:shared
    environment:
      - GPU_MEMORY_LIMIT=16384 # 16GB
      - REALTIME_RESERVED=6144 # 6GB priority zone
      - BATCH_LIMIT=8192 # 8GB background zone
      - BUFFER_RESERVED=2048 # 2GB system buffer
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    volumes:
      - ./monitoring:/app/metrics # GPU utilization tracking
```

```
┌────────────────────────────────────────────────────────────────────┐
│                    DOCKER COMPOSE / KUBERNETES                    │
│                                                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────────┐ │
│  │   API SERVICE   │  │   ML WORKER     │  │     REDIS         │ │
│  │   (Flask)       │  │   (GPU)         │  │   (Session Cache) │ │
│  │                 │  │                 │  │                   │ │
│  │ - auth routes   │  │ - YOLO          │  │ - session cache   │ │
│  │ - job routes    │  │ - pyannote      │  │ - job queue       │ │
│  │ - profile       │  │ - mediapipe     │  │                   │ │
│  │ - SocketIO      │  │ - CV scoring    │  │                   │ │
│  │ - LIVE PROCTORING│ │                 │  │                   │ │
│  │   (1-20 users)  │  │                 │  │                   │ │
│  └────────┬────────┘  └────────┬────────┘  └────────────────────┘ │
│           │                    │                                   │
│           └────────────────────┘                                   │
│                       │                                            │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │   SCALING NOTE: 50+ concurrent interviews                   │  │
│  │   → API service may need GPU or horizontal scaling          │  │
│  └─────────────────────────────────────────────────────────────┘  │
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
```

python-backend/
├── docker/
│ ├── Dockerfile.api # Lightweight API container (CPU-only)
│ ├── Dockerfile.gpu-shared # Shared GPU service (proctoring + ML)
│ ├── Dockerfile.proctoring # Dedicated proctoring service
│ ├── Dockerfile.worker # Dedicated ML worker
│ ├── docker-compose.shared.yml # Shared GPU setup (cost-efficient)
│ ├── docker-compose.separated.yml # Separated GPU setup (safer)
│ └── docker-compose.yml # Local development
│
├── api/ # API-only code (no ML, no WebSocket)
│ ├── app.py # Slim Flask app
│ ├── routes/
│ ├── controllers/
│ ├── middleware/
│ └── models/
│
├── shared-gpu/ # Combined proctoring + ML service
│ ├── app.py # GPU scheduler + WebSocket + Celery
│ ├── gpu_scheduler.py # Smart memory & priority management
│ ├── proctoring_handler.py # Real-time MediaPipe processing
│ ├── ml_worker.py # Background YOLO/pyannote processing
│ └── memory_manager.py # GPU memory allocation
│
├── proctoring/ # Dedicated proctoring service (Option A)
│ ├── app.py # WebSocket server with MediaPipe
│ ├── gaze_detector.py # GPU-accelerated gaze tracking
│ └── session_manager.py # Interview session handling
│
├── shared/ # Shared utilities
│ ├── config/
│ ├── utils/
│ └── queue/ # Redis/Celery setup
│
├── requirements/
│ ├── base.txt # Common dependencies
│ ├── api.txt # API-only deps
│ └── ml.txt # ML/GPU deps
│
└── scripts/
├── start-api.sh
├── start-worker.sh
└── healthcheck.sh

````

---

## Dockerfile Examples

### Shared GPU Service (Cost-Efficient Option)

```dockerfile
# filepath: python-backend/docker/Dockerfile.gpu-shared
FROM nvidia/cuda:12.1-runtime-ubuntu22.04

WORKDIR /app

# Install Python and dependencies
RUN apt-get update && apt-get install -y python3.11 python3-pip

# Install all GPU dependencies
COPY requirements/base.txt requirements/gpu-shared.txt ./
RUN pip install --no-cache-dir -r gpu-shared.txt

# Copy shared GPU service code
COPY shared-gpu/ ./shared-gpu/
COPY shared/ ./shared/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Start GPU scheduler with both services
CMD ["python", "shared-gpu/app.py"]
````

### GPU Scheduler Implementation

```python
# filepath: python-backend/shared-gpu/gpu_scheduler.py
import asyncio
import psutil
import pynvml
from queue import PriorityQueue
from enum import Enum

class TaskPriority(Enum):
    REALTIME = 1    # MediaPipe proctoring
    URGENT = 2      # CV analysis
    BATCH = 3       # YOLO, pyannote

class GPUScheduler:
    def __init__(self, max_gpu_memory_gb=16):
        self.max_memory = max_gpu_memory_gb * 1024  # MB
        self.current_memory = 0
        self.task_queue = PriorityQueue()
        self.running_tasks = {}

    def can_schedule(self, task_memory_mb, priority):
        """Check if task can be scheduled based on memory and priority."""
        if priority == TaskPriority.REALTIME:
            return True  # Always prioritize real-time
        return (self.current_memory + task_memory_mb) <= self.max_memory

    def schedule_task(self, task_id, task_fn, memory_mb, priority):
        """Schedule GPU task with priority and memory management."""
        if self.can_schedule(memory_mb, priority):
            self.running_tasks[task_id] = {
                'memory': memory_mb,
                'priority': priority,
                'task': task_fn
            }
            self.current_memory += memory_mb
            return True
        else:
            # Queue for later
            self.task_queue.put((priority.value, task_id, task_fn, memory_mb))
            return False
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

## Docker Compose: Shared GPU Setup (Recommended)

```yaml
# filepath: python-backend/docker/docker-compose.shared.yml
version: "3.8"

services:
  # Lightweight API service - handles routing, auth, file uploads
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
      - GPU_SERVICE_URL=http://gpu-shared:8000
      - R2_ENDPOINT=${R2_ENDPOINT}
    depends_on:
      - redis
    restart: unless-stopped

  # Smart GPU scheduler - handles both real-time and batch ML
  gpu-shared:
    build:
      context: ..
      dockerfile: docker/Dockerfile.gpu-shared
    ports:
      - "8000:8000" # WebSocket endpoint
      - "8001:8001" # Health/metrics endpoint
    environment:
      - REDIS_URL=redis://redis:6379
      - MONGODB_URI=${MONGODB_URI}
      # GPU Memory Management
      - GPU_TOTAL_MEMORY=16384 # 16GB
      - REALTIME_RESERVED=6144 # 6GB for interviews
      - BATCH_LIMIT=8192 # 8GB for background
      - SYSTEM_BUFFER=2048 # 2GB safety buffer
      # Time-based Allocation
      - PEAK_HOURS="9-17" # 9AM-5PM priority mode
      - EVENING_HOURS="18-23" # 6PM-11PM mixed mode
      - BATCH_HOURS="0-8" # 12AM-8AM batch focus
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
        limits:
          memory: 12G # System RAM limit
    depends_on:
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/gpu-health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Redis with priority queues for task scheduling
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
      - ./redis.conf:/usr/local/etc/redis/redis.conf
    restart: unless-stopped

  # GPU monitoring dashboard
  gpu-monitor:
    image: nvidia/gpu-monitoring:latest
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    ports:
      - "3000:3000" # Grafana dashboard
    environment:
      - MONITOR_CONTAINER=gpu-shared
    restart: unless-stopped

volumes:
  redis_data:
    driver: local
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

### gpu-shared.txt (Combined Proctoring + ML)

```txt
# filepath: python-backend/requirements/gpu-shared.txt
-r base.txt
# WebSocket & real-time
flask-socketio==5.3.0
eventlet==0.33.0
# GPU-accelerated MediaPipe
mediapipe-gpu==0.10.0
opencv-python==4.8.0
# ML processing
torch==2.1.0
torchvision==0.16.0
ultralytics==8.0.0      # YOLO
pyannote.audio==3.1.0
librosa==0.10.0
# GPU management
pynvml==11.5.0          # NVIDIA GPU monitoring
psutil==5.9.0           # System resource monitoring
# Task scheduling
celery==5.3.0
aiofiles==23.2.1        # Async file operations
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

## Architecture Comparison

## Architecture Decision Matrix: 100+ Daily Users

| Factor                            | Shared GPU (Option B)  | Separated GPU (Option A) | Winner for 100+ Users     |
| --------------------------------- | ---------------------- | ------------------------ | ------------------------- |
| **Monthly Cost**                  | ~$300-400              | ~$600-800                | 🏆 Shared (50% savings)   |
| **GPU Utilization**               | 80-95%                 | 40-60%                   | 🏆 Shared (2x efficiency) |
| **Real-time Latency**             | <50ms (priority queue) | <30ms (dedicated)        | Separated (slight edge)   |
| **Complexity**                    | Medium (scheduler)     | Low (isolated)           | Separated                 |
| **Failure Resilience**            | Single point failure   | Isolated failures        | Separated                 |
| **Memory Efficiency**             | Dynamic allocation     | Fixed allocation         | 🏆 Shared                 |
| **Peak Traffic (50+ concurrent)** | Smart scheduling       | Predictable performance  | Tied                      |
| **Off-peak Optimization**         | Batch processing       | Idle resources           | 🏆 Shared                 |
| **Startup Suitability**           | Perfect for growth     | Over-provisioned         | 🏆 Shared                 |

### Traffic-Based Recommendations

```
Concurrent Interviews │ Architecture Choice    │ Monthly Cost │ GPU Setup
──────────────────────┼──────────────────────┼──────────────┼───────────────
1-20 users           │ Shared GPU (Single)   │ ~$300        │ CPU-priority
20-50 users          │ 🏆 Shared GPU (Smart) │ ~$400        │ Mixed allocation
50-80 users          │ 🏆 Shared GPU (Tuned) │ ~$500        │ Peak optimization
80+ users            │ Monitor & decide      │ ~$500-800    │ Consider separation
```

### Implementation Timeline for 100+ Daily Users

**Phase 1 (Months 1-3): Foundation**

- Deploy shared GPU container with basic scheduling
- Monitor: GPU utilization, interview latency, user satisfaction
- Baseline: 4GB real-time + 8GB batch + 2GB buffer

**Phase 2 (Months 4-6): Optimization**

- Implement time-based priority scheduling
- Add memory pressure monitoring and auto-scaling
- Fine-tune allocation based on traffic patterns

**Phase 3 (Months 6+): Scale Decision**

- If >90% GPU utilization consistently: Add second shared GPU
- If >100ms latency spikes: Consider separated architecture
- If >200 daily users: Migration to Option A justified

### Cost Savings Analysis

```
Yearly Savings with Shared GPU Approach:

┌─ SHARED GPU (Option B) ───────────────────────────────────┐
│ Month 1-12: $400 x 12 = $4,800/year                    │
│ Resource Efficiency: 85%                               │
│ Scales with growth, optimizes automatically            │
└──────────────────────────────────────────────────────┘

┌─ SEPARATED GPU (Option A) ──────────────────────────────────┐
│ Month 1-12: $800 x 12 = $9,600/year                   │
│ Resource Efficiency: 45%                              │
│ Fixed costs regardless of usage                       │
└──────────────────────────────────────────────────────┘

💰 ANNUAL SAVINGS: $4,800 (50% reduction)
🚀 ROI: Shared GPU setup pays for itself in 2-3 months
```

**Key Takeaway:** For 100+ daily users with 50+ concurrent interviews, the shared GPU approach provides optimal cost-efficiency while maintaining performance through smart scheduling. Scale to separated architecture only when reliability requirements exceed cost optimization priorities.
