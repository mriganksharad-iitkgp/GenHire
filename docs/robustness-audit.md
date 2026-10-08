# Robustness audit — 8 October 2026

## Checkpoint 1: code inspection

| Area | Finding | Required change |
| --- | --- | --- |
| Request limits | Competing optional/custom middleware, handler replay after exceptions | One installed layer; limiter exceptions never encompass business code |
| Identity | Untrusted X-Forwarded-For, shared office IP budgets | Explicit proxy trust; verified user buckets plus broad network protection |
| Distributed limits | Non-atomic increment/expiry; silent per-process fallback | Atomic Redis operation; production fail-closed when store unavailable |
| Critical routes | Incomplete auth/upload/AI/interview/invite/payment coverage | Route inventory and named environment-driven policies |
| Applications | Read/insert race; unrestricted invite skeleton update | Unique candidate/job constraint, conditional conversion and replay response |
| Capacity | Database pool wait unbounded; background work needs recovery audit | Bounded admission/pool/workers and persisted work |
| Login | Concurrent auth attempts; role selection can influence redirects | One pending attempt, server-role navigation, explicit retry feedback |
| Login presentation | Centered form; no requested split animated experience | Responsive animated left panel and accessible right form |

## Deployment verification still required

Local behavioral tests cannot establish how many simultaneous real users the
deployment supports. Verify shared Redis against the deployed network, audit
existing application duplicates before index rollout, load-test representative
application/CV/interview mixes, and measure latency/queue age/429/503 rates.
The live interview engine still requires the documented single-worker/sticky
topology. Shared request counters do not make live engines distributed.


## Checkpoint 2: implementation and second audit

- One mandatory protection installation replaces the optional Flask-Limiter.
  Named policies and general read/write fallbacks cover all 162 static HTTP
  route declarations. Health/OPTIONS and signed webhook behavior are documented.
- Redis counters/expiry are atomic. The local store is bounded; configured
  outages return 503. Business failures cannot replay handlers.
- Per-account quotas, target auth quotas, explicit proxy trust and environment
  configuration are integrated. Global admission starts before body parsing;
  heavy-action admission, Mongo waits and camera analysis are bounded.
- Concurrent inserts/invite conversion are idempotent. Critical indexes and
  canonical identities must pass startup checks; the duplicate audit is read-only.
- CV scoring now uses persisted snapshots, bounded workers, renewable leases and
  due retries. Failed/invalid scores stay unavailable. Recruiter decisions survive.
- Bulk invite background capacity remains reserved until email dispatch ends and
  is acquired before charging credits. Application notifications are bounded.
- Re-audit found and fixed stopped scoring polling, missing live result pushes,
  legacy photo redirect credential loss, malformed input responses, auth overload
  logging users out, and readiness ping amplification.
- Payment auth handler mismatch and exposed legacy cost/development/GridFS
  endpoints were corrected. This is not a new full payment/account-data migration.
- Login has a responsive animated split layout, motion preferences, accessible
  controls, one pending auth attempt, server-role redirects and retry countdowns.

The local environment has **no REDIS_URL configured** and uses development
mode. Shared atomic counter behavior is tested with the Redis Lua emulator;
real Redis service/network/failover validation remains a production prerequisite.


## Checkpoint 3: final local evidence

- **109 backend behavioral tests pass**, including 35 new robustness tests.
  A 40-request simultaneous account burst admits exactly 5; a 16-request
  application race creates one row, increments the counter once and wakes work
  once. Two emulated Redis clients share 100 atomic Lua increments without loss.
- **14 JavaScript contract tests pass**: 10 existing interview checks, 2 retry
  checks and 2 kiosk security checks.
- **Frontend lint passes** with no code warnings/errors. Web and kiosk production
  bundles build. Edited backend integration modules compile; diff whitespace
  checks pass.
- New tests cover capacity release on failure, malformed/forged identity
  protection, native socket acknowledgements, Redis outages, short cached
  readiness, actual slow-worker execution, persistent provider retries, invalid
  score rejection, lease fencing, concurrent recruiter updates and frozen inputs.
- Critical index rollout tests reject duplicate/noncanonical legacy identities
  while preserving every record. The actual database audit/migration was not run.
- The available browser inventory had no enabled surfaces, so no screenshot or
  interactive desktop/mobile visual acceptance was possible.

## Remaining acceptance work

Configure real shared Redis credentials/TLS/network access and verify outages
across API instances. Run the read-only application audit and review legacy
records before rollout. Use the corrected staging load profile with separate
candidate accounts; measure latency, queue age, provider quotas and 429/503/5xx.
Provide continuously allocated CPU for in-process workers or run a dedicated
worker deployment. Retain sticky/single-worker live interview routing. Verify the
new login on desktop/mobile and real laptop/phone camera coverage. Best-effort
notifications and existing bulk invite dispatch are not a new durable mail queue.

Implementation/learning guide: [request-protection-flow.md](request-protection-flow.md).
