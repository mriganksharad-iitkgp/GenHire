# OA controlled-release runbook — Step 10

Status: implementation and local checks only. **Public rollout is not approved.**
For the owner's ordered local/GCP/Vercel configuration actions and current
engineering blockers, follow [the owner setup guide](oa_owner_setup_guide.md).
This document supplements [the integration record](oa_integration.md),
[evaluation operations](oa_evaluation_operations.md), [integrity operations](oa_integrity_operations.md),
[company hiring](company_hiring_operations.md), [practice operations](practice_oa_operations.md)
and [OnlineCompiler.io acceptance](../OA_FINAL_SETUP.md).

## Evidence and release decision

Passing tests does not approve production migration, cloud provisioning, vendor
purchases, email dispatch, feature activation or a public candidate cohort.
All OA rollout/acceptance examples remain false. An acceptance flag is an
operator assertion supported by evidence, never a substitute for that evidence.
Real coding/SQL publication still requires current profile-bound executor
attestation. Missing credentials fail closed without breaking screening-only jobs.

The seven requested journeys have automated **component/service integration**
coverage below. The real mixed SDE assessment, real AI quality, native/device and
provider journeys remain open; no end-to-end production pass is claimed.

| Journey | Local evidence to run | Remaining acceptance |
|---|---|---|
| 1. SDE: 3 coding + 20 MCQ, configured dates/thresholds, invite, grade, company round | `test_job_setup.py`, `test_assessment_authoring.py`, `test_hiring_progression.py`, `test_assessment_runtime.py`, `test_assessment_evaluation.py`, `test_company_hiring.py`; rendered setup/authoring/runtime/company suites | Assemble this exact 23-question cohort in staging; execute actual languages/providers and desktop-to-company flow. Separate tests do not establish the full journey. |
| 2. Nontechnical role, role OA or no OA | Every preset/timer/dialect/contract config matrix in `test_job_setup.py`; screening-only company round in `test_company_hiring.py` | Recruiter/candidate device walkthrough of a product/business MCQ-only job and a screening-only job. |
| 3. Manual screening shortlisting | `test_hiring_progression.py` manual-default eligibility, replay, review and scheduling; rendered progression and portals | Confirm both dashboards and actual invitation delivery with a consented staging cohort. |
| 4. Entirely manual authoring | Authoring contracts, independent review/publication, runtime and grading suites | Validate reference solutions, hidden cases and wrong solutions on actual judge and both SQL engines; inspect editor on device. |
| 5. Mock OA | `test_practice_assessment.py`: reserve/generate/validate/capture/start/report/advice/replay; rendered practice/ledger | Real AI quality and provider isolation, native launch, educational accuracy and exactly one purchase debit. |
| 6. Infrastructure failures | Billing atomicity, unknown POST/lease/restart/compensation tests in evaluation, practice, company and integrity suites | Kill staging worker during provider dispatch, cut network, restore, verify immutable submission, retained unknown identity and ledger reconciliation. No ambiguous POST auto-retry. |
| 7. Existing users | Legacy model/migration, interview regression, portal/status tests; disposable migration/restore rehearsal | Reviewed read-only production legacy audit, compatibility walkthrough on anonymized staging data, tested production backup/PITR procedure. |

Additional required cases: start one second before OA entry close and retain the
full duration; reject first start exactly at close; deadline submit after reconnect;
four languages × function/stdin contracts; PostgreSQL 17 and MySQL 8.4; wrong,
timeout, OOM and oversized outputs; dual camera, browser/camera waiver and extra
time; cross-owner/candidate/admin/scoped-session denial; withheld/revoked result;
formula-safe exports; repeated purchase/start/submit/evaluation/refund.

## Repeatable local checks and CI

From the repository root, using an **official local mongod executable**, without
loading application dotenv or calling providers:

```powershell
python-backend/venv/Scripts/python.exe python-backend/scripts/dev/run_workflow_integration.py --mongod .tmp/oa-step1-mongo/mongod.exe --combined --pattern 'test_*.py'
$env:GENHIRE_RUN_OA_LOAD='true'
python-backend/venv/Scripts/python.exe python-backend/scripts/dev/run_workflow_integration.py --mongod .tmp/oa-step1-mongo/mongod.exe --combined --pattern test_oa_pilot_load.py
Remove-Item Env:GENHIRE_RUN_OA_LOAD
```

The test helper accepts only loopback Mongo without an application database and
creates randomly named disposable databases. Never point it at production.
The benchmark writes `.tmp/oa-step10-load.json`, with latency percentiles,
errors, host/CPU/pool details, queue admissions and settlement counts. It creates
100 simultaneous active one-MCQ attempts for one payer and exercises 100-client
start/save/submit plus bounded execution admission. Its claim-only executor does
not dispatch code or fabricate validation evidence. The fixed clock exercises
business deadlines; durations use the real monotonic clock.

```powershell
Set-Location react-frontend
npm.cmd run check:oa
Set-Location ..
node --test secure-browser-kiosk/tests/runtime-security.test.js secure-browser-kiosk/tests/media-permissions.test.js secure-browser-kiosk/tests/built-assets.test.js
```

CI: [oa-readiness.yml](../.github/workflows/oa-readiness.yml). It uses a disposable
loopback Mongo replica set, Python 3.12, Node 22, the existing full backend tests,
opt-in local load, all frontend suites/lint/web+kiosk builds and native contracts.
It has read-only repository permissions and no deployment or application secrets.
The load artifact is synthetic and excludes identities/answers. The workflow
must pass on the actual hosted runner before merging; local checks cannot prove
the dependency installation and container image work there.

## Private pilot and measured capacity

The approved target is 100 simultaneous OA attempts, with queued execution and
separate durable workers. Local service/Mongo results do **not** measure HTTP,
TLS, shared Redis, deployed Mongo pool limits, cold starts, secure-browser/media,
provider latency, quotas or spend. There is no production capacity/SLO claim.

For staging, record deployment revision, API/worker instance counts, CPU/RAM,
Mongo tier/pool, Redis limits, region, observed active attempts, provider profile,
quota counters and background load. Begin with 5, then 25, then 100 consented
synthetic candidates; run starts, 15-second autosaves, public Run bursts,
submissions, coding/SQL grading, reconnects and worker restarts. Keep a stable
cohort and include the shared recruiter-wallet contention case. Compare p50/p95/
p99 and errors per route with agreed pilot SLOs before increasing admission.
Record admission-to-dispatch, submission-to-result, maximum queue depth/age,
429/503, Mongo pool waits, Redis failures, capture/refund reconciliation and
incremental provider/cloud cost. A slow successful burst is not a capacity pass.

Use `OA_MAX_CONCURRENT_EXECUTIONS` (1-100, default 20), queue limit
(1–5000, default 1000), SQL concurrency (default 1) and monthly quotas. Unknown
dispatches retain slots. Increasing API replicas cannot overcome judge quota or
the single-payer wallet transaction hotspot. Do not promise 100 simultaneous Run
executions: the pilot deliberately queues them.

The recorded Step 10 local run (see integration section 24) retained 100/100
attempts and reconciled all grades/history/billing. Start p95 was **18.5 seconds**
after bounded jitter on wallet-contended transaction retries (97.8 seconds in
the pre-backoff sample). Autosave p95 was 300 ms, submit 379 ms. The host had eight
logical CPUs, ~15.76 GiB physical RAM and Mongo max pool 100. This is a useful
integrity/load baseline with a remaining start-latency concern, **not permission
to admit 100 real candidates**. Agree and meet staging SLOs first.

## Topology and observability

Keep the existing API hosting in europe-west1. Existing live screening interview
engines remain process-local: retain the supported single-worker/sticky routing
and do not scale screening horizontally without a separate persistence/routing
change. Durable OA services can run independently against the same transactional
Mongo topology. Run explicit supervised workers from `scripts/workers/` for
hiring scheduling/deadlines, authoring, runtime public runs, evaluation/execution,
integrity retention, company email and practice generation/advice. Inspect each
worker's flag dependencies and launch entry point; imports never start workers.
Allocate continuously available worker CPU; web keep-warm pings are not a worker
supervisor. Avoid duplicate embedded/background scheduler deployments.

Read-only operator commands (these load server-side configuration):

```powershell
python scripts/admin/oa_operations_snapshot.py
python scripts/admin/audit_workflow_foundation.py --job-id JOB_ID --owner-id OWNER_ID --audience recruiter
```

Run from `python-backend`. Queue snapshot reports allowlisted aggregate counts,
oldest due/queued age, expired external-call leases, review/unknown states and
execution slot/counter differences. Exit 1 indicates alerts; it never repairs
records. Multi-collection observations can race, so repeat a mismatch after a
quiet interval before reconciling. Future scheduled reminders do not count as
overdue backlog. This is an operator tool, not a public endpoint.

Proposed pilot alarms: any unknown dispatch or ledger mismatch pages an operator;
queue age over five minutes warns; stale leases/review states trigger investigation.
Establish staging SLOs before treating these provisional thresholds as production
guarantees. External monitoring must also collect worker heartbeat/restarts,
request error/latency, submission-result duration, media retention failures and
provider/cloud billing; the queue snapshot alone does not prove worker health.
Logs/tickets must exclude bearer tokens, question content, hidden fixtures,
reference solutions, SQL seeds, source code and raw camera frames.

## Migration and rollback rehearsal

`test_oa_release_readiness.py` uses a real isolated replica set. It snapshots
legacy documents/indexes, verifies repeatable read-only classification, applies
adoption only to eligible records, leaves ambiguous records untouched, verifies
replay adds no events, then restores the original documents/indexes into another
random disposable database and verifies equality and the original dry-run result.
This demonstrates application-level restore semantics. It is **not** a Mongo
dump/PITR, a production restore, or evidence that accepted later work can be lost.

Before a real migration: obtain explicit rollout/migration authorization, take a
verified backup/PITR checkpoint, restore it into staging, run identity/legacy
and workflow/ledger audits, review ambiguous rows, preview one owner-scoped job,
record checkpoint/versions/row counts, and apply bounded batches with the
existing migration CLI. Do not infer a legacy rejection, fabricate timestamps,
drop history or normalize ambiguous records automatically. Record database,
backup, app revision and compatible rollback revision in a private operator log.

Prefer a **forward-compatible drain** if the pilot needs rollback:

1. Stop new job/cohort activation at the operator/recruiter boundary and set
   `GENHIRE_OA_RUNTIME_ENABLED=false` to stop new recruitment starts. Stop new
   mock purchases/starts with `GENHIRE_MOCK_OA_ENABLED=false`. Keep workflow and
   integrity protections enabled for already accepted attempts.
2. Keep accepted attempts' save/submit, scoped refresh, deadline worker,
   evaluation/execution, storage retention and wallet reconciliation running on
   the compatible revision. Keep evaluation enabled while draining; disabling
   its flag stops the evaluator, including admitted work.
3. Pause new authoring separately if required; turning generation off can
   compensate pending holds. Do not delete pending jobs. Keep already ready
   purchases and their support/refund obligations in the reconciliation manifest.
4. Stop outbound company/scheduler email using its dispatch flag if necessary.
   Preserve previews, sent/unknown identities and delivery evidence. No blind
   resend. Existing manual workflow stage-actions retain their workflow gate;
   disabling the company feature is not a universal mutation lock.
5. Inventory active deadlines, immutable submissions, unknown external calls,
   held/captured operations, released results and unresolved messages. Drain or
   record verified platform-failure disposition; preserve operation/event IDs.
6. Only after drain and explicit approval consider disabling the broader workflow
   feature or rolling back code. Never deploy pre-OA writers over managed records.
   Do not restore a stale backup over post-checkpoint submissions or ledger events.
   If storage corruption requires restore, use the rehearsed PITR and controlled
   reconciliation with a documented recovery point and authorized outage.

## Cost and final activation gates

The SQL incremental target is **$10/month**, not an enforced dollar ceiling.
Existing environment quota and concurrency limits bound submissions, not all
cloud charges. Before provisioning, review the SQL infrastructure directory,
dedicated least-privilege service identities, private artifact buckets and
retention, disposable PostgreSQL/MySQL isolation, timeout/resource/egress controls
and Cloud Run Jobs quotas in the existing project/europe-west1. Configure actual
cloud billing budget notifications at 50%, 80% and 100% of the $10 target and
an operator response; no billing alert was provisioned by this implementation.
Track job CPU/RAM duration, storage/network/registry/logging and Sphere/AI
usage separately. Stop new paid admissions on budget risk and drain accepted
work; do not strand submissions or fake provider results to meet a budget.

Activation requires documented owner approval, passing hosted CI and staging
journeys/load, real account runtime IDs and current executor attestation, both SQL
versions/isolation tests, AI question quality approval, GCS/privacy/retention,
native signed installer/device acceptance and accessible accommodations, working
shared Redis/Mongo transactions, email delivery/unknown reconciliation, actual
budget alerts, monitoring ownership and a demonstrated production backup restore.
Set per-job qualification thresholds and approved recruiter attempt pricing;
do not invent a pass mark or copy test-only prices. Start with an explicitly
selected private cohort. No item in this document enables a flag automatically.
