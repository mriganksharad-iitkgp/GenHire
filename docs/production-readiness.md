# Production-Readiness Review — are we doing what industry-standard products do?

Honest scorecard as of July 2026, after the reorganization and hardening work.
"✅" = matches common industry practice; "⚠️" = partially; "❌" = gap with a
concrete recommendation.

## What is now industry-standard ✅

- **Codebase layout**: feature-folder frontend (`app/ features/ shared/`),
  layered backend (routes → controllers → services → repositories, app
  factory, one composition root). New engineers can navigate by folder names.
- **Configuration**: secrets and business knobs live in env vars — LLM
  provider order, plan prices/credits, feature toggles (mobile recording),
  verification thresholds. `.env.example` documents everything.
- **Resilience for LLMs**: one provider chain (Groq→Gemini→OpenAI, env-driven)
  with quota detection and cooldowns used by every LLM feature. This is the
  pattern serious LLM products use.
- **Auth**: JWT + role decorators server-side, declarative route guards
  client-side, one signing-secret source, session-expiry broadcast.
- **Security wins**: no secrets in the repo; the desktop installer no longer
  ships a GCP private key (short-lived token broker instead); identity
  verification (one-time ID card + LLM face match) gates interviews; CORS is
  origin-listed; admin endpoints are role-gated.
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
2. **No dev/prod isolation** — local runs hit the live MongoDB/GCS with the
   same keys. This is the riskiest habit in the project. *Create a separate
   Atlas project + GCS bucket + API keys for dev/staging; parameterize by env.*
3. **Single-process scalability ceiling** — one eventlet worker, in-memory
   `live_sessions`, thread-based background jobs, in-memory rate limits.
   Fine to ~1k DAU; beyond that: *move rate limits + Socket.IO sessions to
   Redis (`REDIS_URL` already supported), background jobs to Cloud Tasks, and
   `live_sessions` to Redis so multiple Cloud Run instances can serve.*
4. **CRA is deprecated** (its own build output says unmaintained). *Migrate to
   Vite: faster builds, removes the CI=false hack, modern defaults. The
   feature-folder layout makes this a mostly mechanical move.*
5. **JWT in URL query params** (CV/report/image links `?token=`). URLs leak
   into logs/history. *Replace with short-lived signed download URLs.*
6. **UI/UX consistency**: ~400 inline `style={{}}` blocks remain (Chat, admin
   detail pages) alongside CSS Modules; no design tokens; a11y rule now warns.
   *Adopt a small token layer (colors/spacing/typography CSS variables),
   migrate inline styles opportunistically, fix a11y warnings, and keep using
   the shared Modal/ConfirmDialog primitives for anything new.*
7. **Data lifecycle**: recordings accumulate forever. *GCS lifecycle rules
   (delete after retention, Nearline after 30 days) — also a cost lever
   (see cost.md §6).*
8. **Keys**: the OpenAI key is invalid and the Gemini project has no paid
   quota — the chain hides this operationally, but the paid fallbacks should
   exist before a Groq outage. *Refresh both; a 5-minute task.*

## Recommended order of attack

1. Fix keys + set SENTRY_DSN + GCS lifecycle rules (hours).
2. GitHub Actions CI: lint ratchet + build + backend import/manifest (a day).
3. Dev/staging environment split (a day).
4. Pytest + RTL starter suites (ongoing).
5. Chat/RecruiterDashboard decomposition with interactive verification —
   clears the exhaustive-deps debt and unlocks strict CI.
6. Vite migration.
7. Redis-backed scale-out work when approaching ~1k DAU.
