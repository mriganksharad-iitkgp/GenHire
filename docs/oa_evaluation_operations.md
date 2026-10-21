# OA evaluation operations — Step 6

This runbook describes delivered source, not a production deployment. The active backend `.env` is unchanged. Do not enable live cohorts until actual execution/isolation, evaluator and secure-browser acceptance pass. Fake local transports are not execution attestations.

## Configuration and workers

The backend `.env.example` adds default-off `GENHIRE_OA_EVALUATION_ENABLED=false`. Candidate starts still require the existing workflow/scheduling flags and all three runtime/evaluation/security acceptance approvals. Keep those approvals false while their prerequisites are incomplete. Evaluation can be tested on an explicitly isolated staging database without enabling candidate starts. `.env` changes require restarting the corresponding web/worker processes.

Pilot controls, configurable downward within the documented ranges:

| Setting | Default / range | Meaning |
|---|---|---|
| `GENHIRE_OA_EXECUTION_CONCURRENCY` | 2 / 1–4 | Distributed active execution slots shared by public Run and hidden grading. Unknown POSTs retain slots. |
| `GENHIRE_OA_EXECUTION_QUEUE_LIMIT` | 1000 / 1–5000 | Queued-task admission limit. Returning in-flight capacity/quota retries can temporarily add at most the active concurrency limit; all admission remains bounded. |
| `GENHIRE_OA_GRADING_CASE_LIMIT` | 200 / 1–400 | Maximum grading fixtures per assessment, checked before accepted-start reservation. Selected coding language only; hidden coding tests and all weighted SQL datasets. |
| `GENHIRE_SPHERE_MONTHLY_SUBMISSION_LIMIT` | 500 / 1–500 | Existing shared monthly dispatch-intent budget, including reference validation and unknown executions. |
| `GENHIRE_SQL_MONTHLY_EXECUTION_LIMIT` | 200 / 1–200 | Existing SQL dispatch budget; SQL concurrency remains globally one. |

These limits do not guarantee the requested $10 monthly cloud target. Actual provider pricing, Cloud Run/storage/logging usage, alerts and deployment quotas still need live verification. No resources or billing settings were provisioned by this milestone.

Run the following only after verifying the intended environment/database, under the deployment supervisor, from `python-backend`:

```
venv/Scripts/python.exe scripts/workers/assessment_runtime_worker.py
venv/Scripts/python.exe scripts/workers/assessment_evaluation_worker.py
```

Each supports `--once` for a bounded pass. Do not run either against the application database merely to test imports. The runtime worker maintains accepted deadlines/public Run mapping; the evaluator reconciles up to 50 new submissions, processes one leased evaluation and drives the shared case executor. Both processes may drive case execution: Mongo admission/fencing enforces the global limit across processes. Web handlers never execute code or SQL. A process/database outage requires supervisor restart; work and provider IDs remain durable.

## Required executor upgrade

The current executor profile includes contract `oa_cases_v2`. Existing profile attestations no longer match. Rebuild/review the SQL images, deploy pinned digests to the existing project's `europe-west1` jobs, and rerun the existing operator executor preflight and isolation review before approval. **Do not insert a fake attestation or enable acceptance flags to bypass this requirement.** No image was built or deployed here.

SQL results must include `execution_evidence_version: 2`. The runner distinguishes pre-query bootstrap/fixture failures (`infrastructure_error`) from candidate query runtime/time failures. The parent gives the query its actual configured execution budget after bootstrap. Both reference publication validation and private grading reject older SQL evidence. Sphere private grading additionally checks actual returned compiler/version IDs and finite time/memory evidence against the configured pins.

Sphere requests use the documented form parameters, bounded stream endpoints and account-pinned compiler/version IDs. Public compiler/runtime diagnostics are bounded and redact tokens, provider URLs and control characters; hidden execution diagnostics are never exposed. Contracts were checked against the official [Compilers API v4](https://docs.sphere-engine.com/compilers/api/overview-version-4) and [Problems API v4](https://docs.sphere-engine.com/problems/api/overview-version-4) documentation. The deterministic per-case evaluation path uses Compilers v4; the existing Problems adapter/canary remains required for account acceptance and is not silently substituted as an unverified custom judge.

## States, retries and reconciliation

- A submission remains immutable. Its answers/hash, question hashes, publication configuration and scoring policy bind one evaluation job. Content mismatches or malformed submissions enter review without a fabricated result.
- Evaluation jobs: `queued`, `waiting`, `blocked`, `needs_review`, `complete`, `unavailable`. Metadata work has a renewable 60-second lease and token fencing. Queue pressure waits rather than poisoning a candidate. Unexpected repeatable job errors stop after eight failures for review.
- Case tasks: `queued`, `dispatching`, `running`, `blocked`, `dispatch_unknown`, `complete`, `cancelled`. Dispatch intent precedes every paid POST. A five-minute abandoned dispatch is unknown, not a reason to resend.
- Read-only polling backs off from two seconds up to 300 seconds. Eight errors flag review while retaining the original provider identity and slot. Unknown or missing resource evidence is not a wrong answer. Late valid results may still recover through safe polling.
- Confirmed terminal infrastructure errors may retry twice with fresh per-retry dispatch identities and recorded provider history. Ambiguous POSTs never automatically retry. An unposted SQL artifact failure retries the **same** reserved request identity; it does not reserve another SQL slot or monthly execution.
- A private hash-bound SQL result artifact can resolve an unknown Cloud Run launch without another POST. Missing results retain the SQL/global slot; do not decrement counters manually to make room while an execution might still be active.

Authenticated APIs (normal platform token required; no unsigned callback endpoint exists):

| API | Access / behavior |
|---|---|
| `GET /api/assessment-evaluation-operations` | Admin with `applications.read`/`*`; aggregate job/task counts, capacity and oldest queued time. No sources/fixtures/credentials. |
| `POST /api/assessment-executions/:taskId/reconcile` | Admin with `applications.write`/`*`; `operation_key`, `reason` (10–1000 characters), `action`, optional positive `provider_id`. Audited and idempotent. |
| `GET /api/assessment-attempts/:id/evaluation` | Owner recruiter/authorized admin gets safe objective report/state. Own candidate gets status only; recruitment marks/recommendation remain withheld. |
| `POST /api/assessment-attempts/:id/platform-failure` | Admin write permission, stable operation key and documented verified platform failure; releases a held reservation, fences unfinished evaluation and cancels unposted grading tasks. It cannot reverse a usable/captured evaluation through this endpoint. |

Reconciliation actions:

1. `bind_provider`: for an unknown Sphere dispatch, verify the submission's source/input/account relationship in the provider console, then supply its real ID and document that evidence. The service verifies existence on the original profile, rotates the dispatch token and resumes GET polling. The service does not infer ownership merely because a provider ID exists; this is an authorized operator assertion with an audit trail.
2. `resume_poll`: for a known running provider ID after an account/read outage, reset polling backoff/review flags without any POST or deadline change.
3. `retry_confirmed`: only a known pre-dispatch block or confirmed completed infrastructure error, no held execution slot, maximum two retries, and no terminal settled grading job. It cannot retry an unknown POST or a candidate wrong answer. Normal terminal infrastructure retries already happen automatically within these bounds.

All vendor calls occur outside Mongo transactions. Operator actions do not accept scores, fixtures, deadlines or arbitrary endpoints. Never publish hidden actual/expected output, provider diagnostics from hidden runs, sources, private SQL seeds or tokens in tickets/logs. Authorized operators can inspect task IDs/states/provider identities through a deliberately projected database query; full private task documents must not be exported casually.

## Scoring, release and billing

MCQs use exact sets for multiple correct answers, no negative marks, and the saved question marks. Unanswered finalized questions are zero. Coding partial credit uses only hidden test weights for the selected language. SQL uses all explicitly weighted validated datasets, including samples. Section percentage is earned/possible; overall percentage uses the saved section weights. Decimal arithmetic avoids accumulating floating-point rounding errors; display values round to four decimal places. Infrastructure-ungraded questions keep the overall score unavailable.

A private report records the objective threshold recommendation. It does not establish proctoring clearance, publish candidate results, advance company stages or automatically reject a candidate. Canonical OA completion remains pending recruiter release; Step 7 supplies integrity evidence and Step 8 supplies release/advancement controls.

A usable finalized evaluation captures the original recruiter reservation in the same transaction as the report, attempt/submission state and canonical stage event. Unanswered/wrong/compile/time/memory/output-limit answers are usable grading outcomes and are not platform refunds. Exhausted confirmed infrastructure failure returns the reservation and records no final score. Ambiguous/pending execution keeps the hold until recovery or a reasoned administrator platform-failure action. Candidate withdrawal does not manufacture a technical refund. Existing general billing refund primitives remain available to financial operations; this milestone does not expose a new post-capture customer refund policy.

## Monitoring, rollout and rollback

Monitor oldest queued age, held global/SQL slots, unknown dispatches, polling review flags, job review counts, submission-to-result latency, monthly quota consumption, and reports versus capture/release ledger entries. Polling is authoritative; no browser or external callback is required. No production SLO/load claim is made from local fake-provider tests.

Before launch, verify the four actual account runtimes, both contract styles, both SQL engines, incorrect solutions, timeout/OOM/output bounds, egress/file/role escape denial, worker death/restart, concurrent publication/settlement, deployment resources and actual costs. Use the existing executor canary/security review plus a disposable staging cohort. Keep all candidate launch approvals false until those checks and Step 7 safeguards pass.

Rollback: stop new evaluation admission with its flag and stop new starts with the runtime flag. Preserve accepted deadlines and deadline worker, submissions, hashes, reports, reservations, case identities and unknown-provider slots. Continue approved polling/reconciliation/settlement for already admitted work rather than deleting journals. Do not restore old SQL evidence acceptance to unblock a cohort. Existing Step 5 running public jobs retain their original read-only result path; legacy unknown dispatches require operator review and must not be silently re-created.
