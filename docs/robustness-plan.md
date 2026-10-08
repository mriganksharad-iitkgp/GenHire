# Request robustness and login improvement plan

Started 8 October 2026. Continue the existing interview improvements without
claiming production capacity from local tests. No secrets belong in this document.

## Steps and audit checkpoints

- [x] 1. Audit middleware, authentication, application submission, database
  indexes, background processing, API clients and login flows.
- [x] 2. Replace competing request limiters with one mandatory protection layer:
  atomic Redis counters, bounded local development storage, trusted proxy
  configuration, meaningful per-user/action budgets and consistent retry hints.
- [x] 3. Cover critical public/authenticated actions and bound expensive work.
  Keep interview monitoring and normal polling usable. Check coverage again
  against the route inventory after integration.
- [x] 4. Make concurrent application submission idempotent; protect invite
  conversion, persist scoring work and bound worker/database resources.
- [x] 5. Improve API error handling and login workflow. Build an accessible,
  responsive split login page with animation and reduced-motion support.
- [x] 6. Verify abuse, concurrent requests, duplicate submissions, outages,
  retries and recovery with behavioral tests; run existing tests/lint/builds.
- [x] 7. Re-audit results, document settings and explain the request/application
  flow. Record infrastructure and real-load acceptance checks still needed.

## Findings driving this work

The custom Redis limiter catches exceptions from the route itself and can run
that route again. It trusts arbitrary forwarded IPs, never removes expired
identity keys locally, and silently falls back independently in every worker.
A second optional limiter imposes very small production quotas. Most expensive
actions have no explicit policy. Application submission uses a read then insert
without a unique constraint; invite conversion has no conditional update.

Checkpoint updates and evidence: [robustness-audit.md](robustness-audit.md).

## Implementation checkpoint

Steps 2-5 implemented and re-audited. Central policies cover the 162 static
HTTP route declarations; socket events have independent quotas/caps. Application
scoring is asynchronous and persistent. The login/polling changes pass lint and
web/kiosk builds. Behavioral validation is passing; final evidence and rollout
limits are being consolidated in the audit and flow guide.


## Final checkpoint

Implementation and local verification complete: 109 backend tests, 14
frontend/kiosk contract tests, frontend lint and both production bundles pass.
The static coverage audit counted 162 HTTP route declarations. No real Redis
credentials were configured or invented, no production database was migrated,
and no production capacity claim is made. Deployment acceptance remains listed
in the audit/flow guide.

Learning guide and environment settings: [request-protection-flow.md](request-protection-flow.md).
