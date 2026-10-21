# Production-Readiness Review — what's done, what's left

## OA update — 20 October 2026

The OA integration now has durable workflow/attempt/evaluation services,
owner-scoped company rounds and mock OA purchases. Release controls, the seven
journey evidence matrix, isolated migration/restore rehearsal, local 100-client
benchmark and CI are documented in [the OA release runbook](oa_release_runbook.md)
and [Step 10's implementation record](oa_integration.md#24-step-10--release-hardening-and-controlled-release).
This is local readiness work, not public rollout approval. Real provider/device,
security, staging load/cost and backup recovery gates remain. Existing live
screening still needs its supported single-worker/sticky topology.


## Request robustness update ? 8 October 2026

All HTTP routes now use mandatory environment-driven request protection with
named critical-action policies and read/write fallbacks. Redis quotas are atomic
and shared; production requires a reachable REDIS_URL. Local development has a
bounded memory store. Invalid forwarded identities cannot bypass IP quotas,
verified accounts get separate action budgets, and 429/503 includes retry hints.
Request/body parsing, heavy HTTP work, socket analysis/traffic, bulk invite
dispatch, notification workers and Mongo pool waits have bounds.

Application submission no longer performs synchronous CV scoring. A unique
candidate/job index and conditional invite conversion prevent duplicate records.
Persisted snapshots/leases/retries recover scoring after restart; unavailable or
invalid scores never invent eligibility. Recruiter decisions survive concurrent
publication. Login now has an animated responsive split layout and protected
auth/retry workflows; candidate polling/live scoring progress are repaired.

**Local verification:** 109 backend tests and 14 frontend/kiosk contract tests
pass, lint is clean, web/kiosk bundles build, and integration modules compile.
This does not establish a production concurrency or latency target. No browser
surface was available for visual acceptance.

**Rollout prerequisites:** actual shared Redis credentials/network validation;
read-only legacy application audit and any reviewed normalization/duplicate
resolution before startup index enforcement; representative staging load tests;
and continuously allocated CPU or a dedicated deployment for background workers.
Live engines still require the existing sticky/single-worker topology. No live
database migration or deployment was performed during this work.

Plan: [robustness-plan.md](robustness-plan.md).
Evidence: [robustness-audit.md](robustness-audit.md).
Flow/settings/learning guide: [request-protection-flow.md](request-protection-flow.md).

## Interview update — 8 October 2026

The interview implementation now includes recruiter-selected laptop/mobile
proctoring, signed phone pairing with fresh camera/heartbeat checks, laptop
camera/microphone/speaker checks, face capture, and explicit activation after
setup. Web and kiosk share the same React interview runtime. Installation
guidance appears before session creation; real interviews create the session
inside the kiosk. Optional model downloads, eye calibration, recording
conversion and practice CV scoring no longer block startup.

Repeated start/answer/end requests preserve the session and stored results.
Ownership gates cover REST and desktop sockets; a phone receives only a signed
session capability. Scores use actual evaluation/detection evidence with
pending, unavailable, disabled and partial coverage states. The completion
screen and saved report expose interview/CV/proctoring scores, transcript,
identity evidence and monitoring events. Missing voice/eyeball/gaze pipelines
are reported as missing checks rather than silently counted as working.

**Local validation:** 74 backend behavioral tests pass on Python 3.12, ten
frontend contract tests and two kiosk security tests pass, lint has zero
warnings/errors, both web/kiosk production bundles build, and a local Windows
NSIS installer packages successfully. A local official
YOLOv8n export validates in OpenCV and runs at 91 ms warm mean on blank frames
on the development laptop. This does not establish footage accuracy or the
production 5–10 second startup target.

**Before enabling this in production:** provision the Git-ignored object
artifact into the API image; build/test and publish updated kiosk installers;
configure reachable HTTPS frontend/API origins and secrets; and run the
two-device acceptance matrix in [interview-flow-audit.md](interview-flow-audit.md).
Browser visual automation was unavailable in this session. Keep the current
single-worker/sticky session topology: engines and live monitoring remain
process-local. Restart recovery retains submitted answers and can finalize a
report; it does not recreate a lost live interviewer.

Implementation checklist: [interview-flow-plan.md](interview-flow-plan.md).
Model setup: [proctoring-model-setup.md](proctoring-model-setup.md).
The broader scorecard below is the August baseline and has not been fully
re-audited for unrelated payment, infrastructure or account configuration.

Honest scorecard as of **2026-08-06**, after the reorganization,
billing/costing, go-live hardening, the **CRA → Vite** migration, and the
**payment credit-reconciliation** hardening.

"✅" = matches common industry practice · "⚠️" = partial · "❌" = gap with a
concrete recommendation. This is the single source of truth for "how
production-ready are we" — keep it current when flows change.

## What is now industry-standard ✅

- **Codebase layout**: feature-folder frontend (`app/ features/ shared/`),
  layered backend (routes → controllers → services → repositories, app
  factory, one composition root). New engineers can navigate by folder names.
- **Build tooling**: frontend runs on **Vite** (`vite.config.mjs`), migrated
  off the now-unmaintained Create React App. `npm run dev` (port 3000),
  `npm run build` (→ `build/`), `npm run preview`. Env vars kept their
  `REACT_APP_` prefix via a `process.env` shim, so the move touched no source
  files. Production build verified end-to-end.
- **Configuration**: secrets and business knobs live in env vars — LLM
  provider order, plan prices/credits, feature toggles, verification
  thresholds. `.env.example` (frontend + backend) documents everything.
- **Resilience for LLMs**: one provider chain (`LLM_PROVIDER_PRIORITY`,
  default **openai → gemini → groq**, env-driven) with quota detection and
  per-provider cooldowns used by every LLM feature.
- **Storage**: GCS-only for every persistent artifact (CVs, JDs, recordings,
  gaze data) with a boot-time hard requirement — no local-disk fallback that
  silently loses files on container restarts. (Identity cards and face
  captures are the deliberate exception: they live in GridFS.)
- **Payments — no lost credits**: recharge crediting is idempotent
  (`recharge:<order_id>`) and **self-healing**. If a payment succeeds at
  Razorpay but the wallet credit fails, the order is flagged
  (`credit_status:"failed"`, `needs_reconciliation:true`), logged at ERROR,
  and enqueued in the durable **`payment_reconciliations`** collection; the
  webhook replays the idempotent credit automatically. See
  [backend/payment-module.md](backend/payment-module.md).
- **Cost transparency**: admin cost page shows actual fetched spend (GCP
  BigQuery billing export, OpenAI Costs API via an admin key, per-send email
  log) with a usage-source badge on every figure, plus real credit charging
  for bulk invites (1 credit/candidate, auto-refund on failed emails).
- **Auth**: JWT + role decorators server-side, declarative route guards
  client-side, one signing-secret source, session-expiry broadcast.
- **Security wins**: no secrets in the repo; the desktop installer no longer
  ships a GCP private key (short-lived token broker instead); identity
  verification (ID card + background LLM face-match scoring); CORS is
  origin-listed (trailing slashes normalized); admin endpoints are role-gated;
  artifact serving (`/api/view-file`) requires auth and is bucket-scoped.
- **Change safety**: route-manifest diffing (`scripts/route_manifest.py` vs
  its committed baseline), smoke checklist, lint ratchet (`npm run lint:ci`),
  per-step commits with verified gates.

## Partial ⚠️

- **Observability**: Sentry is wired but `SENTRY_DSN` is unset; some logs are
  unstructured prints. *Set the DSN, adopt structured logging, add Cloud Run
  alerting on 5xx/latency, and alert on unresolved `payment_reconciliations`
  rows.*
- **Linting/CI**: ESLint runs clean today (`react-app` config on standalone
  eslint 8 — 0 errors, 0 warnings across `src`), but no CI actually runs
  lint/build/tests on a PR yet (the only workflow is the backend keep-warm
  ping). *Add a GitHub Actions job: `lint:ci` + Vite build + backend
  import/manifest check on every PR.*
- **Payments — reconciliation has no UI**: the `payment_reconciliations` queue
  is written and self-heals via webhook, but there's no admin view or alert to
  catch a row that stays `resolved:false`. *Add an admin panel + alert.*
- **Dev/prod isolation — designed, not yet in effect.** The two-env-file
  split exists (`python-backend/.env` and `.env.production`), but **both
  currently point at the same Atlas cluster (`hrtech.kdo8zml.mongodb.net`) and
  the same GCS bucket (`genhireuploads`)**. The intended end state is a
  company-account prod cluster, a `genhire-uploads-prod` bucket, and a
  prod-only invite-token secret. Until then a production incident can touch
  development data and vice versa. *Stand up the prod cluster + bucket and
  repoint `.env.production`.*
- **Docs**: refreshed 2026-08-06 against the current code (identity flow, LLM
  chain order, kiosk speech brokering, blueprint list, route inventory).
  Re-verify the ~70 KB handbook whenever flows change again.

## Gaps that matter ❌ (ranked)

1. **Integration coverage and CI remain incomplete.** The backend now has 74
   passing behavioral tests, plus frontend/kiosk contract regressions. Live
   Mongo/GCS, hardware/media and payment verify/webhook integration still need
   isolated test environments and CI execution on every PR.
2. **Single-process scalability ceiling** — one eventlet worker, in-memory
   `live_sessions`, thread-based background jobs, in-memory rate limits.
   Fine to ~1k DAU; beyond that: *move rate limits + Socket.IO sessions to
   Redis (`REDIS_URL` already supported), background jobs to Cloud Tasks, and
   `live_sessions` to Redis so multiple Cloud Run instances can serve.*
3. **JWT in URL query params** (CV/report/image links `?token=`). URLs leak
   into logs/history. *Replace with short-lived signed download URLs.*
4. **UI/UX consistency**: ~500 inline `style={{}}` blocks remain (Chat, admin
   detail pages) alongside CSS Modules; no design tokens. *Adopt a small token
   layer (CSS variables for colors/spacing/typography), migrate inline styles
   opportunistically, fix a11y warnings.*
5. **Data lifecycle**: recordings accumulate forever. *GCS lifecycle rules
   (delete after retention, Nearline after 30 days) — also a cost lever
   (see [cost.md](../cost.md) §6).*
6. **Paid LLM leg missing**: the OpenAI key is valid but has **zero inference
   quota** and the Gemini project is free-tier (flash-lite only) — the chain
   hides this, but a funded leg should exist before a Groq outage.
7. **Dev Razorpay keys are LIVE keys** — the dev `.env` currently holds
   `rzp_live_...`. *Swap to test-mode keys (`rzp_test_...`) so local testing
   can't touch the live account.*

## Pre-launch checklist (before going public)

Concrete, ordered — the things to clear before real users and real money.

1. **Payments**: switch dev `.env` to `rzp_test_` keys; run one real
   test-mode purchase end-to-end (initiate → checkout → verify → wallet
   credited); register the production webhook URL
   (`/api/payment/webhooks/razorpay`) in the Razorpay dashboard and confirm a
   `payment.captured` event credits/self-heals; confirm `payment_reconciliations`
   stays empty on the happy path.
2. **Secrets & isolation**: create the production Atlas cluster and the
   `genhire-uploads-prod` bucket, then point `.env.production` at them so it
   stops sharing the dev cluster/bucket. Confirm the prod invite-token secret
   and live Razorpay keys are set **only** in the prod environment; rotate
   anything ever committed or shared.
3. **Observability**: set `SENTRY_DSN`; add Cloud Run alerts on 5xx rate and
   latency; add an alert on unresolved `payment_reconciliations`.
4. **CI gate**: GitHub Actions running `lint:ci`, the Vite build, and the
   backend import/manifest check on every PR.
5. **Data lifecycle**: apply GCS lifecycle rules so recordings don't grow
   (and bill) unbounded.
6. **Scale headroom**: if launch could exceed ~1k DAU, move rate limits +
   `live_sessions` to Redis and background jobs to Cloud Tasks first.
7. **Smoke pass**: run [SMOKE_CHECKLIST.md](SMOKE_CHECKLIST.md) against a
   prod-like deploy (signup → apply → interview → recruiter review → recharge).

## Recommended order of attack

1. Pre-launch checklist items 1–3 (payments test keys + webhook, secrets,
   Sentry/alerts) — hours to a day.
2. GitHub Actions CI: lint ratchet + Vite build + backend import/manifest.
3. GCS lifecycle rules.
4. Pytest + RTL starter suites (ongoing), payment verify/webhook covered first.
5. Reconciliation admin view + alert.
6. Chat/RecruiterDashboard decomposition (clears exhaustive-deps, unlocks
   stricter CI).
7. Redis-backed scale-out work when approaching ~1k DAU.
