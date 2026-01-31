# GCP Interview Platform Cost Estimation Document (Option B: Cloud Run + Shared GPU)

**Valid for January 2026 pricing (us-central1 region).** Option B uses Cloud Run for API (scales to zero) + shared GPU VM for real-time proctoring (MediaPipe/gaze) and batch ML (YOLO/pyannote), optimized for 20-30 min interviews and your traffic patterns (100+ daily users, 50+ concurrent peaks). Costs assume 80-95% GPU utilization via smart scheduling from docs.

## Executive Summary

| Scenario   | Daily Users | Monthly Interviews | Total Cost     | Cost/Interview | GPU Count |
| ---------- | ----------- | ------------------ | -------------- | -------------- | --------- |
| **Low**    | 20          | ~750               | **$330-400**   | $0.44-0.53     | 1x T4     |
| **Medium** | 100         | ~2,500             | **$500-600**   | $0.20-0.24     | 1x T4/L4  |
| **High**   | 200         | ~5,000             | **$900-1,100** | $0.18-0.22     | 2x T4/L4  |

**Key Savings**: 50% vs GKE (Option A) via shared GPU + autoscaling. Preemptible GPUs cut 70% ($80-170/month savings).

## Traffic Scenarios & Assumptions

- **Interview**: 25 min avg, 100MB video (~200MB GPU memory peak).
- **Patterns**: 09-17 peak (50-60 concurrent, 80% real-time); 18-23 mixed (20-30); 00-08 batch (2-5).
- **GPU**: n1-standard-8 + T4 (16GB, $0.35/hr on-demand = $255/mo always-on).
- **730 hrs/mo max**. Uptime: 75-100% via `TrafficAwareScheduler`.

| Scenario   | Concurrent Peak | Interviews/Day | GPU Load     |
| ---------- | --------------- | -------------- | ------------ |
| **Low**    | 10              | 25             | 75% uptime   |
| **Medium** | 30-40           | 85             | 96% uptime   |
| **High**   | 50-60           | 170            | 100% + scale |

## Detailed Monthly Cost Breakdown

### 1. GPU Costs (Dominant: 60-75% of total)

**Single GPU Pricing**: $0.35/hr on-demand ($255/mo full), $0.105/hr preemptible ($77/mo). [fluence](https://www.fluence.network/blog/nvidia-t4/)

| Scenario   | Active Hours/Mo | Uptime % | 1x GPU Cost | Multi-GPU | Total GPU |
| ---------- | --------------- | -------- | ----------- | --------- | --------- |
| **Low**    | 550             | 75%      | **$193**    | 1x        | **$193**  |
| **Medium** | 700             | 96%      | **$245**    | 1x        | **$245**  |
| **High**   | 730             | 100%     | **$255**    | 2x        | **$510**  |

**Autoscaling Logic**:

```
09-17 (Peak): 100% active (240 hrs/mo)
18-23 (Mixed): 80% (150 hrs)
00-08 (Batch): 50% or preemptible (120 hrs)
Trigger: Redis queue >100 OR >40 concurrent → +GPU
Downscale: <10 concurrent ×30min → sleep
```

### 2. Cloud Run API (Pay-per-use, scales 0→N)

2 vCPU/4GB instances, ~500K free req/mo.

| Scenario   | Requests/Mo | vCPU-Hrs | Cost         |
| ---------- | ----------- | -------- | ------------ |
| **Low**    | 50K         | 200      | **$30-50**   |
| **Medium** | 300K        | 900      | **$100-150** |
| **High**   | 600K        | 1,800    | **$200-250** |

### 3. Supporting Services (Fixed + Linear)

| Service                 | Low         | Medium     | High       | Notes           |
| ----------------------- | ----------- | ---------- | ---------- | --------------- |
| **Redis (Memorystore)** | $70 (2GB)   | $100 (3GB) | $140 (4GB) | Priority queues |
| **GCS Storage**         | $10 (500GB) | $15 (1TB)  | $20 (2TB)  | Video uploads   |
| **MongoDB Atlas**       | $20 (M10)   | $30 (M20)  | $50 (M30)  | Sessions        |
| **Networking/LB/Misc**  | $20         | $30        | $40        | Egress, CDN     |

## Per-Interview & Per-User Costs

| Metric           | Low          | Medium    | High         |
| ---------------- | ------------ | --------- | ------------ |
| **$/Interview**  | **$0.44**    | **$0.20** | **$0.19**    |
| **$/Daily User** | **$16.50**   | **$5**    | **$4.50**    |
| **$/Concurrent** | **$1.65/hr** | **$1/hr** | **$0.90/hr** |

## Complete Monthly Totals

| Component       | Low      | Medium   | High     |
| --------------- | -------- | -------- | -------- |
| GPU             | $193     | $245     | $510     |
| Cloud Run       | $40      | $125     | $225     |
| Redis           | $70      | $100     | $140     |
| Storage/DB      | $30      | $45      | $70      |
| Networking      | $20      | $30      | $40      |
| **TOTAL**       | **$353** | **$545** | **$985** |
| **Preemptible** | **$275** | **$410** | **$740** |

## GPU Scaling Roadmap

| Concurrent | GPU Setup    | Memory Split                  | Cost Adder | Action           |
| ---------- | ------------ | ----------------------------- | ---------- | ---------------- |
| **1-25**   | 1x T4 (16GB) | 6GB real/8GB batch/2GB buffer | Base       | HPA >70% util    |
| **25-40**  | 1x L4 (24GB) | 8GB real/12GB batch           | +$50/mo    | Peak priority    |
| **40-60**  | 2x T4        | 12GB real/16GB batch          | +$255/mo   | Redis >100 jobs  |
| **60+**    | 3x L4 or GKE | Dynamic scheduler             | +$500/mo   | Migrate Option A |

**Monitoring**: pynvml + Grafana dashboard; auto-restart via instance groups.

## Cost Optimization Strategies (20-50% Savings)

1. **Preemptible GPUs**: 70% off ($77 vs $255/GPU). Safe for batch, risky for live interviews.
2. **Committed Use**: 37-55% off for 1-3yr ($160/GPU/mo).
3. **Spot VMs**: Up to 90% off, auto-failover.
4. **MinScale=1 API**: $20-50/mo cold-start prevention.
5. **Free Tiers**: 500K Cloud Run req, 5GB GCS.

**ROI**: Shared GPU saves $300-500/mo vs separated (Option A: $1,424/mo high-scale). Break-even at 50 daily users.

## Risks & Mitigations

| Risk         | Impact | Mitigation                  |
| ------------ | ------ | --------------------------- |
| GPU OOM      | High   | 2GB buffer + memory manager |
| Cold Starts  | Medium | minScale=1 + Redis caching  |
| Preemptions  | Medium | Multi-VM + queue retry (3x) |
| Cost Overrun | Low    | Budget alerts + rightsizing |

## Decision Framework

```
Daily Users | Architecture | Monthly | When to Upgrade
<50     | 1x GPU       | $350    | → 2x at 40 concurrent
50-150  | 1-2x GPU     | $550    | → GKE at 60+ concurrent
150+    | Monitor      | $1K+    | Option A for isolation
```

**Start Here**: Deploy 1x preemptible T4 GPU + Cloud Run. Monitor 30 days via Cloud Billing. Expected Year 1: $5K-7K total (medium growth).
