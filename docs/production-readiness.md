# Production-Readiness Review — are we doing what industry-standard products do?

Honest scorecard as of 2026-07-12, after the reorganization, billing/costing,
and go-live hardening work.
"✅" = matches common industry practice; "⚠️" = partially; "❌" = gap with a
concrete recommendation.

## What is now industry-standard ✅

- **Codebase layout**: feature-folder frontend (`app/ features/ shared/`),
  layered backend (routes → controllers → services → repositories, app
  factory, one composition root). New engineers can navigate by folder names.
- **Configuration**: secrets and business knobs live in env vars — LLM
  provider order, plan prices/credits, feature toggles (mobile recording),
  verification thresholds. `.env.example` documents everything.
- **Resilience for LLMs**: one provider chain (OpenAI→Gemini→Groq, env-driven)
  with quota detection and cooldowns used by every LLM feature. This is the
  pattern serious LLM products use.
- **Storage**: GCS-only for every persistent artifact (CVs, JDs, recordings,
  gaze data) with a boot-time hard requirement — no local-disk fallback that
  silently loses files on container restarts. Dev and prod use separate
  buckets.
- **Cost transparency**: admin cost page shows actual fetched spend (GCP
  BigQuery billing export, OpenAI Costs API, per-send email log) with a
  usage-source badge on every figure, plus real credit charging for bulk
  invites (1 credit/candidate, auto-refund on failed emails).
- **Auth**: JWT + role decorators server-side, declarative route guards
  client-side, one signing-secret source, session-expiry broadcast.
- **Security wins**: no secrets in the repo; the desktop installer no longer
  ships a GCP private key (short-lived token broker instead); identity
  verification (ID card + background LLM face-match scoring); CORS is
  origin-listed (trailing slashes normalized so `https://genhire.in/` can't
  silently break it); admin endpoints are role-gated; artifact serving
  (`/api/view-file`) requires auth and is scoped to the app's own bucket.
- **Dev/prod isolation** (since 2026-07-12): separate Atlas clusters
  (personal-account dev vs company-account prod), separate GCS buckets
  (`genhireuploads` vs `genhire-uploads-prod`), a prod-only invite-token
  secret (dev magic links can't redeem on prod), and a deliberate boot
  failure if production is deployed without its own database URI.
- **Change safety**: route-manifest diffing, smoke checklist, lint ratchet
  (`npm run lint:ci`), per-step commits with verified gates.

## Partial ⚠️

- **Linting/CI**: rules are on and warnings burned 89 → 15, but the remaining
  `exhaustive-deps` warnings sit in the interview/dashboard effect code, and
  CRA's all-warnings-fail-CI behavior forces `CI=false` to stay (the @ffmpeg
  webpack warning is third-party). *Path out: finish the Chat/RecruiterDashboard
  decomposition (needs interactive verification) and/or migrate CRA → Vite.*
- **Observability**: Sentry is wired but `SENTRY_DSN` is unset; logs are
  unstructured prints in places. *Set the DSN, adopt structured logging, add
  Cloud Run alerting on 5xx/latency.*
- **Docs**: refreshed for the new structure, but the 70 KB handbook needs a
  full pass whenever flows change again.

## Gaps that matter ❌ (ranked)

1. **No automated test suite.** The manifest/smoke harness protects structure,
   not behavior. *Add pytest (auth, credits, invite, export routes with a test
   DB) and React Testing Library smoke tests; run both in GitHub Actions on
   every PR along with `lint:ci` and the production build.*
2. **Single-process scalability ceiling** — one eventlet worker, in-memory
   `live_sessions`, thread-based background jobs, in-memory rate limits.
   Fine to ~1k DAU; beyond that: *move rate limits + Socket.IO sessions to
   Redis (`REDIS_URL` already supported), background jobs to Cloud Tasks, and
   `live_sessions` to Redis so multiple Cloud Run instances can serve.*
3. **CRA is deprecated** (its own build output says unmaintained). *Migrate to
   Vite: faster builds, removes the CI=false hack, modern defaults. The
   feature-folder layout makes this a mostly mechanical move.*
4. **JWT in URL query params** (CV/report/image links `?token=`). URLs leak
   into logs/history. *Replace with short-lived signed download URLs.*
5. **UI/UX consistency**: ~400 inline `style={{}}` blocks remain (Chat, admin
   detail pages) alongside CSS Modules; no design tokens; a11y rule now warns.
   *Adopt a small token layer (colors/spacing/typography CSS variables),
   migrate inline styles opportunistically, fix a11y warnings, and keep using
   the shared Modal/ConfirmDialog primitives for anything new.*
6. **Data lifecycle**: recordings accumulate forever. *GCS lifecycle rules
   (delete after retention, Nearline after 30 days) — also a cost lever
   (see cost.md §6).*
7. **Keys**: the OpenAI key has zero quota (needs billing credit) and the
   Gemini project is free-tier (flash-lite only) — the chain hides this
   operationally, but a paid leg should exist before a Groq outage.
8. **Dev Razorpay keys are LIVE keys** — swap the dev `.env` to test-mode
   keys (`rzp_test_...`) so local testing can't touch the live account.

## Recommended order of attack

1. Swap dev Razorpay to test keys + set SENTRY_DSN + GCS lifecycle rules (hours).
2. GitHub Actions CI: lint ratchet + build + backend import/manifest (a day).
3. Pytest + RTL starter suites (ongoing).
5. Chat/RecruiterDashboard decomposition with interactive verification —
   clears the exhaustive-deps debt and unlocks strict CI.
6. Vite migration.
7. Redis-backed scale-out work when approaching ~1k DAU.
