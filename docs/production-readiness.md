# Production-Readiness Review — what's done, what's left

Honest scorecard as of **2026-07-20**, after the reorganization, billing/costing,
go-live hardening, the **CRA → Vite** migration, and the **payment
credit-reconciliation** hardening.

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
  silently loses files on container restarts. Dev and prod use separate
  buckets.
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
- **Dev/prod isolation** (since 2026-07-12): separate Atlas clusters, separate
  GCS buckets (`genhireuploads` vs `genhire-uploads-prod`), a prod-only
  invite-token secret, and a deliberate boot failure if production is deployed
  without its own database URI.
- **Change safety**: route-manifest diffing, smoke checklist, lint ratchet
  (`npm run lint:ci`), per-step commits with verified gates.

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
- **Docs**: refreshed for the Vite move and payment hardening, but the ~70 KB
  handbook needs a full pass whenever flows change again.

## Gaps that matter ❌ (ranked)

1. **No automated test suite.** The manifest/smoke harness protects structure,
   not behavior. *Add pytest (auth, credits, invite, export, **payment
   verify/webhook** routes with a test DB) and React Testing Library smoke
   tests; run both in GitHub Actions on every PR.*
2. **Single-process scalability ceiling** — one eventlet worker, in-memory
   `live_sessions`, thread-based background jobs, in-memory rate limits.
   Fine to ~1k DAU; beyond that: *move rate limits + Socket.IO sessions to
   Redis (`REDIS_URL` already supported), background jobs to Cloud Tasks, and
   `live_sessions` to Redis so multiple Cloud Run instances can serve.*
3. **JWT in URL query params** (CV/report/image links `?token=`). URLs leak
   into logs/history. *Replace with short-lived signed download URLs.*
4. **UI/UX consistency**: ~400 inline `style={{}}` blocks remain (Chat, admin
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
2. **Secrets & isolation**: confirm prod `MONGODB_URI`, prod GCS bucket, prod
   invite-token secret, and live Razorpay keys are set **only** in the prod
   environment; rotate anything ever committed or shared.
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
