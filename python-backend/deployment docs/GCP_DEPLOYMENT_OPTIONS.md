# GCP Deployment Options: API + ML Containers

## Deployment Strategies Comparison

| Strategy     | API                    | GPU Services         | Best For                               |
| ------------ | ---------------------- | -------------------- | -------------------------------------- |
| **Option A** | GKE (together)         | Separated GPU pods   | High traffic + predictable load        |
| **Option B** | Cloud Run (serverless) | Shared GPU VM        | Cost optimization + variable load      |
| **Option C** | Cloud Run              | Cloud Run Jobs + GPU | Low traffic, <20 concurrent interviews |

---

## Traffic Analysis: 100+ Daily Users, 50+ Concurrent Pattern

### Peak Usage Patterns & GPU Scheduling

```
Time Period    │ Concurrent │ Background │ GPU Memory Strategy
               │ Interviews │ ML Jobs    │
───────────────┼────────────┼────────────┼─────────────────────────────
09:00-17:00    │ 50-60+     │ Minimal    │ ████████░░ (80% real-time)
18:00-23:00    │ 20-30      │ Moderate   │ ██████░░░░ (60% mixed)
00:00-08:00    │ 2-5        │ Heavy      │ ███░░░░░░░ (30% batch focus)
```

### GPU Memory Allocation Strategy (16GB Total)

```
┌─────────────────────────────────────────────────────────────┐
│                    16GB GPU MEMORY POOL                    │
├─────────────────────┬─────────────────────┬─────────────────┤
│   REAL-TIME ZONE    │   BACKGROUND ZONE   │  SYSTEM BUFFER  │
│    4-6GB (Priority) │   8-10GB (Batch)    │   2GB (Reserve) │
│                     │                     │                 │
│ • MediaPipe         │ • YOLO Processing   │ • GPU Overhead  │
│ • Gaze Tracking     │ • pyannote Audio    │ • Memory Mgmt   │
│ • WebSocket I/O     │ • CV Analysis       │ • Error Recovery│
│ • <50ms Response    │ • Can queue/defer   │                 │
└─────────────────────┴─────────────────────┴─────────────────┘
```

### Cost Analysis: Shared vs Separated GPU

| Metric              | Shared GPU (Option B) | Separated GPU (Option A) | Savings         |
| ------------------- | --------------------- | ------------------------ | --------------- |
| **Monthly Cost**    | ~$400                 | ~$800                    | **50%**         |
| **GPU Utilization** | 80-95%                | 40-60%                   | **2.4x better** |
| **Idle Cost**       | $35 (Redis only)      | $400+ (GPU nodes)        | **91%**         |
| **Peak Efficiency** | Dynamic allocation    | Fixed allocation         | **Flexible**    |

### Smart Scheduling Implementation

```python
# Priority-based GPU task scheduling
class TrafficAwareScheduler:
    def __init__(self):
        self.time_based_priority = {
            "peak_hours": (9, 17),      # 9AM-5PM: Interviews priority
            "evening": (18, 23),        # 6PM-11PM: Mixed workload
            "batch_window": (0, 8)      # 12AM-8AM: Background ML
        }

    def get_current_priority_mode(self):
        hour = datetime.now().hour
        if 9 <= hour <= 17:
            return "interview_priority"  # Real-time gets 80% GPU
        elif 18 <= hour <= 23:
            return "mixed_mode"          # 60/40 split
        else:
            return "batch_mode"          # Background gets 70% GPU

    def schedule_gpu_task(self, task_type, memory_req):
        mode = self.get_current_priority_mode()

        if task_type == "real_time_proctoring":
            return self.allocate_priority_slot(memory_req)
        elif mode == "batch_mode":
            return self.allocate_batch_slot(memory_req)
        else:
            return self.queue_for_next_slot(task_type, memory_req)
```

```
┌─────────────────────────────────────────────────────────────────┐
│                    GKE CLUSTER                                  │
│                                                                 │
│  ┌─────────────────────────┐  ┌─────────────────────────────┐  │
│  │   CPU NODE POOL         │  │   GPU NODE POOL             │  │
│  │                         │  │   (n1-standard-4 + T4)      │  │
│  │  ┌─────────┐ ┌───────┐  │  │  ┌─────────────────────┐    │  │
│  │  │ API Pod │ │ Redis │  │  │  │ ML Worker Pod       │    │  │
│  │  │ (x3)    │ │       │  │  │  │ (x2)                │    │  │
│  │  └─────────┘ └───────┘  │  │  └─────────────────────┘    │  │
│  └─────────────────────────┘  └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    [Cloud Load Balancer]
                              │
                              ▼
                    [Cloud CDN/Cloud Armor]
```

### Pros

- Single cluster management
- Easy inter-service communication (Kubernetes DNS)
- Unified logging/monitoring
- GPU nodes scale with demand
- **Dedicated proctoring service with GPU can handle 100+ concurrent interviews**
- **API stays lightweight (CPU-only) and scales independently**

### Cons

- GKE management overhead
- GPU nodes expensive when idle (min 1 node)
- **Need separate GPU node pool for proctoring service**
- Overkill for small-medium traffic

### Cost Estimate (Monthly)

| Resource               | Spec                  | Cost              |
| ---------------------- | --------------------- | ----------------- |
| GKE Cluster            | Autopilot             | ~$74              |
| CPU Nodes              | 3x e2-standard-2      | ~$150             |
| GPU Nodes (ML)         | 2x n1-standard-4 + T4 | ~$600             |
| GPU Nodes (Proctoring) | 2x n1-standard-4 + T4 | ~$600             |
| **Total (High Scale)** |                       | **~$1,424/month** |

---

## Option B: Split Deployment with Shared GPU 🏆 **RECOMMENDED**

### Architecture: Smart GPU Resource Sharing

```
┌─────────────────────────────────────────────────────────────────┐
│                    SERVERLESS (CLOUD RUN)                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │   API Service (CPU-only)                                │   │
│  │   - Scales 0 to N automatically                         │   │
│  │   - Pay per request                                      │   │
│  │   - Auth, jobs, file uploads                            │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Redis Queue + Priority Routing
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│            SHARED GPU COMPUTE (Cost-Efficient)                 │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           SMART GPU SCHEDULER (16GB T4/L4)              │   │
│  │                                                         │   │
│  │  ┌─────────────────┐    ┌─────────────────────────┐    │   │
│  │  │ REAL-TIME ZONE  │    │   BACKGROUND ZONE       │    │   │
│  │  │ 4-6GB Priority  │    │   8-10GB Batch          │    │   │
│  │  │                 │    │                         │    │   │
│  │  │ • WebSocket     │    │ • YOLO Analysis         │    │   │
│  │  │ • MediaPipe     │    │ • pyannote Audio        │    │   │
│  │  │ • Gaze Track    │    │ • CV Processing         │    │   │
│  │  │ • <50ms SLA     │    │ • Queue when busy       │    │   │
│  │  └─────────────────┘    └─────────────────────────┘    │   │
│  │                                                         │   │
│  │  Memory Manager: Dynamic allocation based on time       │   │
│  │  • 9AM-5PM: 80% real-time, 20% batch                  │   │
│  │  • 6PM-11PM: 60% real-time, 40% batch                 │   │
│  │  • 12AM-8AM: 30% real-time, 70% batch                 │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Architecture Flow (Shared GPU)

```python
# API (Cloud Run) - queues both real-time and batch tasks
@app.route('/api/start-interview', methods=['POST'])
def start_interview():
    # Queue proctoring session (high priority)
    gpu_service.start_proctoring_session(interview_id, priority="realtime")
    return {'status': 'started'}

@app.route('/api/analyze-cv', methods=['POST'])
def analyze_cv():
    # Queue CV analysis (low priority, deferrable)
    gpu_service.queue_cv_analysis(file_path, priority="batch")
    return {'job_id': job_id, 'status': 'queued'}

# Shared GPU Service - smart scheduling
class SharedGPUService:
    def __init__(self):
        self.realtime_slots = 30  # Max concurrent interviews
        self.gpu_memory_pool = 16384  # 16GB total

    def can_start_interview(self):
        active_interviews = self.get_active_interviews()
        return len(active_interviews) < self.realtime_slots

    def schedule_batch_job(self, job):
        # Run batch jobs when GPU memory is available
        if self.get_gpu_memory_usage() < 60%:  # Leave headroom for real-time
            self.execute_batch_job(job)
        else:
            self.queue_for_later(job)
```

### Pros

- API scales to zero (no cost when idle)
- GPU used only when needed
- Independent scaling
- Lower baseline cost

### Cons

- More complex setup
- Network latency between services
- Need managed Redis (Cloud Memorystore)

### Cost Breakdown: Shared GPU Strategy

| Resource              | Spec                       | Low Traffic (<50 users) | High Traffic (100+ users) |
| --------------------- | -------------------------- | ----------------------- | ------------------------- |
| **Cloud Run API**     | 2 vCPU, 4GB, ~500K req     | ~$50-100                | ~$150-250                 |
| **Cloud Memorystore** | 2GB Redis + priority queue | ~$70                    | ~$140 (4GB)               |
| **Shared GPU VM**     | n1-standard-8 + T4/L4 16GB | ~$300-400               | ~$450-600                 |
| **Cloud Storage**     | 500GB for ML assets        | ~$10                    | ~$20                      |
| **Total (Shared)**    |                            | **~$430-580/month**     | **~$760-1,010/month**     |

### ROI Analysis: Shared vs Separated Architecture

```
Monthly Cost Comparison (100+ Users, 50+ Concurrent):

┌─ SHARED GPU APPROACH ($400/month) ──────────────────────┐
│                                                         │
│ API Service:     $200  ██████████                      │
│ Redis Cache:     $100  █████                           │
│ Shared GPU VM:   $500  ████████████████████████        │
│ Storage:         $20   █                               │
│                                                         │
│ Total: $820/month    Efficiency: 85% GPU utilization   │
└─────────────────────────────────────────────────────────┘

┌─ SEPARATED GPU APPROACH ($800/month) ───────────────────┐
│                                                         │
│ API Service:     $200  ██████████                      │
│ Redis Cache:     $100  █████                           │
│ Proctoring GPU:  $500  ████████████████████████        │
│ ML Worker GPU:   $500  ████████████████████████        │
│ Storage:         $20   █                               │
│                                                         │
│ Total: $1,320/month  Efficiency: 45% GPU utilization   │
└─────────────────────────────────────────────────────────┘

SAVINGS: $500/month (38%) + 90% better resource utilization
```

---

## Option C: Full Serverless (Cloud Run + GPU Jobs)

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLOUD RUN                                    │
│                                                                 │
│  ┌───────────────┐     ┌───────────────────────────────────┐   │
│  │   API Service │────▶│   Cloud Run Jobs (GPU)            │   │
│  │               │     │   - Triggered per request         │   │
│  │               │     │   - L4 GPU support (preview)      │   │
│  └───────────────┘     └───────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Pros

- Simplest architecture
- True pay-per-use
- No infrastructure management

### Cons

- Cloud Run GPU still in preview
- Cold start latency for GPU jobs
- Limited GPU options

---

## Trade-offs Summary

| Factor                    | Option A (GKE)            | Option B (Split)           | Option C (Serverless) |
| ------------------------- | ------------------------- | -------------------------- | --------------------- |
| **Complexity**            | High                      | Medium                     | Low                   |
| **Cost (idle)**           | High (~$400+)             | Low (~$35)                 | Zero                  |
| **Cost (active)**         | Predictable               | Variable                   | Variable              |
| **Scaling**               | Manual/HPA                | Auto (API) + Manual (GPU)  | Full Auto             |
| **Cold Start**            | None                      | None (API), possible (GPU) | Yes                   |
| **GPU Options**           | All NVIDIA                | All NVIDIA                 | Limited (L4 only)     |
| **Concurrent Interviews** | 100+ (with GPU API pods)  | 50+ (may need API GPU)     | <20 (CPU only)        |
| **Best For**              | High traffic, predictable | Variable traffic           | Low-medium traffic    |

---

## Recommended: Option B (Split Deployment)

### Why?

1. **Cost Efficiency**: API scales to zero, GPU runs only when needed
2. **Flexibility**: Can swap GPU provider (GCE, Vertex AI, Modal)
3. **Reliability**: API stays up even if ML worker fails
4. **Scalability**: Scale API and ML independently

### Implementation

#### 1. Cloud Run API Setup

```yaml
# filepath: python-backend/cloudrun.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: interview-api
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "0"
        autoscaling.knative.dev/maxScale: "10"
    spec:
      containerConcurrency: 80
      containers:
        - image: gcr.io/PROJECT_ID/interview-api:latest
          ports:
            - containerPort: 5000
          resources:
            limits:
              cpu: "2"
              memory: "4Gi"
          env:
            - name: REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: redis-url
                  key: latest
```

#### 2. GPU Worker on GCE

```bash
# Create GPU VM
gcloud compute instances create ml-worker \
  --machine-type=n1-standard-4 \
  --accelerator=type=nvidia-tesla-t4,count=1 \
  --image-family=pytorch-latest-gpu \
  --image-project=deeplearning-platform-release \
  --boot-disk-size=100GB \
  --preemptible  # 70% cheaper, may be terminated

# SSH and start worker
gcloud compute ssh ml-worker
docker run -d --gpus all \
  -e REDIS_URL=$REDIS_URL \
  gcr.io/PROJECT_ID/ml-worker:latest
```

#### 3. Cloud Memorystore (Redis)

```bash
# Create Redis instance
gcloud redis instances create interview-queue \
  --size=1 \
  --region=us-central1 \
  --redis-version=redis_7_0
```

---

## Communication Between Services

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  Cloud Run  │─────▶│   Redis     │◀─────│  GPU Worker │
│  (API)      │      │  (Queue)    │      │  (Celery)   │
└─────────────┘      └─────────────┘      └─────────────┘
       │                                         │
       │         ┌─────────────┐                 │
       └────────▶│   MongoDB   │◀────────────────┘
                 │   Atlas     │
                 └─────────────┘
       │                                         │
       │         ┌─────────────┐                 │
       └────────▶│   GCS       │◀────────────────┘
                 │  (Files)    │
                 └─────────────┘
```

### Data Flow

1. **User uploads file** → API saves to GCS
2. **API queues job** → Redis (job_id, file_path)
3. **GPU worker picks job** → Downloads file, processes
4. **Worker saves results** → MongoDB + GCS
5. **User polls status** → API reads from MongoDB

---

## Will It Work as a Whole?

**Yes**, with proper setup:

| Concern               | Solution                                  |
| --------------------- | ----------------------------------------- |
| **Service discovery** | Redis URL shared via secrets              |
| **File sharing**      | GCS bucket accessible by both             |
| **Database**          | MongoDB Atlas (external, both can access) |
| **Authentication**    | JWT tokens validated by API only          |
| **Latency**           | Async processing, user polls for results  |

### Potential Issues

| Issue                               | Mitigation                                               |
| ----------------------------------- | -------------------------------------------------------- |
| **GPU VM goes down**                | Use managed instance group with auto-restart             |
| **Redis connection from Cloud Run** | Use Serverless VPC Connector                             |
| **Cold starts**                     | Keep min instances = 1 for API                           |
| **File size limits**                | Cloud Run: 32MB request, use signed URLs for large files |

---

## Quick Decision Guide

```
┌─────────────────────────────────────────────────────────────┐
│          Cost vs Performance Trade-offs?                      │
└─────────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┖───────────────┐
          ▼               ▼               ▼
     Cost priority    Balanced         Performance
     (Startups)      (Growing)        (Enterprise)
          │               │               │
          ▼               ▼               ▼
    ┌─────────┐     ┌─────────┐     ┌─────────┐
    │Option B │     │Monitor  │     │Option A │
    │SharedGPU│     │& Switch │     │Separated│
    │~50% Cost│     │as needed│     │Max Perf │
    └─────────┘     └─────────┘     └─────────┘
      ~$400          Monitor at        ~$800+
                     100+ users
```

### Migration Path

┌────────────────────────────────────────────────────────┐
│ Start Here → Scale Later │
├────────────────────────────────────────────────────────┤
│ Shared GPU (Option B) │ Separated GPU (Option A) │
│ - Cost: ~$400/month │ - Cost: ~$800+/month │
│ - 50+ concurrent interviews │ - 100+ concurrent interviews │
│ - Smart scheduling required │ - Predictable performance │
│ - Risk: latency spikes │ - Better isolation │
└────────────────────────────────────────────────────────┘

---

## Summary

| Question                           | Answer                                                                  |
| ---------------------------------- | ----------------------------------------------------------------------- |
| Deploy together?                   | ✅ Possible on GKE, but expensive                                       |
| **Share GPU for proctoring + ML?** | **✅ Recommended for 100+ daily users (50% cost savings)**              |
| Deploy separately?                 | ✅ Safer but 2x cost, better for 200+ users                             |
| Will it work?                      | ✅ Yes, with smart GPU scheduling + priority queues                     |
| **Traffic pattern matters?**       | **✅ Yes - peaks need real-time priority, off-hours for batch**         |
| Best option?                       | **Option B** (shared) for most cases, **Option A** for high-reliability |
| Trade-off?                         | Cost vs Performance vs Complexity vs Real-time Guarantees               |

**Recommendation**: Start with **Option B** (Cloud Run + GPU VM). Migrate to GKE only if you need tighter integration or very high traffic.
