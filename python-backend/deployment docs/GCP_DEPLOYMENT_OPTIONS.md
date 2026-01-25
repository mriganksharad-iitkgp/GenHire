# GCP Deployment Options: API + ML Containers

## Deployment Strategies Comparison

| Strategy | API | ML Worker | Best For |
|----------|-----|-----------|----------|
| **Option A** | GKE (together) | GKE with GPU nodes | Full control, high traffic |
| **Option B** | Cloud Run (serverless) | GCE GPU VM / Vertex AI | Cost optimization |
| **Option C** | Cloud Run | Cloud Run Jobs + GPU | Simplest, moderate workloads |

---

## Option A: Deploy Together on GKE

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
                    [Cloudflare CDN/WAF]
```

### Pros
- Single cluster management
- Easy inter-service communication (Kubernetes DNS)
- Unified logging/monitoring
- GPU nodes scale with demand

### Cons
- GKE management overhead
- GPU nodes expensive when idle (min 1 node)
- Overkill for small-medium traffic

### Cost Estimate (Monthly)
| Resource | Spec | Cost |
|----------|------|------|
| GKE Cluster | Autopilot | ~$74 |
| CPU Nodes | 3x e2-standard-2 | ~$150 |
| GPU Nodes | 2x n1-standard-4 + T4 | ~$600 |
| **Total** | | **~$824/month** |

---

## Option B: Split Deployment (Recommended)

```
┌─────────────────────────────────────────────────────────────────┐
│                    SERVERLESS (CLOUD RUN)                       │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │   API Service                                            │   │
│  │   - Scales 0 to N automatically                         │   │
│  │   - Pay per request                                      │   │
│  │   - No GPU needed                                        │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Redis Queue (Cloud Memorystore)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    GPU COMPUTE                                  │
│                                                                 │
│  Option B1: GCE GPU VM (always-on)                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │   ML Worker (Celery)                                     │   │
│  │   - n1-standard-4 + NVIDIA T4                           │   │
│  │   - Processes queue continuously                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Option B2: Vertex AI Custom Jobs (on-demand)                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │   ML Job triggered per request                           │   │
│  │   - Pay only when processing                             │   │
│  │   - Auto-provisions GPU                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Architecture Flow

```python
# API (Cloud Run) - queues task
@app.route('/api/analyze', methods=['POST'])
def analyze():
    # 1. Upload file to GCS/R2
    # 2. Push job to Redis queue
    # 3. Return job_id immediately
    return {'job_id': job_id, 'status': 'queued'}

# ML Worker (GPU VM) - processes queue
@celery.task
def process_recording(job_id):
    # 1. Download file from GCS/R2
    # 2. Run YOLO/pyannote analysis
    # 3. Save results to MongoDB
    # 4. Update job status
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

### Cost Estimate (Monthly)

| Resource | Spec | Cost |
|----------|------|------|
| Cloud Run (API) | 2 vCPU, 4GB, ~500K requests | ~$50-100 |
| Cloud Memorystore | 1GB Redis | ~$35 |
| GCE GPU VM | n1-standard-4 + T4 (preemptible) | ~$150-300 |
| Cloud Storage | 100GB | ~$2 |
| **Total** | | **~$240-440/month** |

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

| Factor | Option A (GKE) | Option B (Split) | Option C (Serverless) |
|--------|---------------|------------------|----------------------|
| **Complexity** | High | Medium | Low |
| **Cost (idle)** | High (~$400+) | Low (~$35) | Zero |
| **Cost (active)** | Predictable | Variable | Variable |
| **Scaling** | Manual/HPA | Auto (API) + Manual (GPU) | Full Auto |
| **Cold Start** | None | None (API), possible (GPU) | Yes |
| **GPU Options** | All NVIDIA | All NVIDIA | Limited (L4 only) |
| **Best For** | High traffic, predictable | Variable traffic | Low-medium traffic |

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
       └────────▶│   GCS/R2    │◀────────────────┘
                 │  (Files)    │
                 └─────────────┘
```

### Data Flow

1. **User uploads file** → API saves to GCS/R2
2. **API queues job** → Redis (job_id, file_path)
3. **GPU worker picks job** → Downloads file, processes
4. **Worker saves results** → MongoDB + GCS
5. **User polls status** → API reads from MongoDB

---

## Will It Work as a Whole?

**Yes**, with proper setup:

| Concern | Solution |
|---------|----------|
| **Service discovery** | Redis URL shared via secrets |
| **File sharing** | GCS/R2 bucket accessible by both |
| **Database** | MongoDB Atlas (external, both can access) |
| **Authentication** | JWT tokens validated by API only |
| **Latency** | Async processing, user polls for results |

### Potential Issues

| Issue | Mitigation |
|-------|------------|
| **GPU VM goes down** | Use managed instance group with auto-restart |
| **Redis connection from Cloud Run** | Use Serverless VPC Connector |
| **Cold starts** | Keep min instances = 1 for API |
| **File size limits** | Cloud Run: 32MB request, use signed URLs for large files |

---

## Quick Decision Guide

```
┌─────────────────────────────────────────────────────────────┐
│                   How much traffic?                         │
└─────────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
    < 10K users     10K-100K users    > 100K users
          │               │               │
          ▼               ▼               ▼
    ┌─────────┐     ┌─────────┐     ┌─────────┐
    │Option C │     │Option B │     │Option A │
    │Serverless│    │ Split   │     │  GKE    │
    └─────────┘     └─────────┘     └─────────┘
       ~$50           ~$300           ~$800+
```

---

## Summary

| Question | Answer |
|----------|--------|
| Deploy together? | ✅ Possible on GKE, but expensive |
| Deploy separately? | ✅ Recommended for cost/flexibility |
| Will it work? | ✅ Yes, with Redis queue + shared storage |
| Best option? | **Option B** for most cases |
| Trade-off? | Complexity vs Cost |

**Recommendation**: Start with **Option B** (Cloud Run + GPU VM). Migrate to GKE only if you need tighter integration or very high traffic.