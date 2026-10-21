# Company hiring operations — Step 8

Implementation is disabled by default. No production database migration, real `.env` edit, live mail, cloud provisioning, native installer publication or deployment occurred. Steps 3/6/7 live judge, SQL, device, storage and production acceptance gates remain open.

## Recruiter workflow

Select a job in Candidate Management, then load Company rounds and shortlist. This separate server-paged view shows canonical stage/lifecycle counts, screening scores, objective OA scores/recommendations, unresolved integrity reviews, private recruiter OA decisions and result-release status. Zero marks remain zero; missing evaluation remains unavailable. The original candidate cards retain detailed reports/evidence and add Company hiring decisions with an actual recorded event timeline. Main filters distinguish active OA/company stages and hired/withdrawn/closed lifecycles; overview screening counts use recorded managed stages rather than treating all rejected applicants as interviewed.

For a completed OA, record a reasoned qualification, nonqualification or review hold. Qualification requires a usable immutable objective report and, for integrity-enabled attempts, a current explicit `reviewed_clear` integrity review. Unknown/expired/missing integrity coverage cannot silently qualify. Reviewers can override an objective threshold recommendation with their documented decision; grades, recommendation, source, test verdicts and billing remain unchanged. These private decisions live outside candidate workflow payloads.

An approved decision binds the evaluation input hash and integrity review revision. Later review changes make advancement/release stale until a fresh decision is recorded. A write fence serializes approval/release/advancement against concurrent integrity review. An already released snapshot is historical recruiter publication; it does not auto-update when evidence is reviewed again. Reviewers should withdraw release where appropriate. Advancement always rechecks current evidence.

Configure company rounds during setup or append named rounds to an individual application's remaining company process with a reason. Per-application additions are audited snapshot revisions; they do not change the job's immutable version or other candidates. At most 12 total stages remain allowed. Explicit shortlist/advance moves a cleared screening-only application or approved OA candidate into the next company-managed round. Your company schedules/conducts those interviews. Record company round cleared/not cleared/review, advance to another configured round, or record hired/final rejection/closure manually. Hiring requires a cleared company stage. Adding/advancing a round does not send an email or auto-release scores.

Result release is a separate action. The candidate endpoint exposes only a recruiter-published overall score, section earned/possible/weight, decision outcome and release time. No question grades, solutions, hidden tests, private reviewer notes, integrity evidence or peer data are included. Own candidates can check released results in their application timeline. Changing an OA decision withdraws its old publication atomically. An explicit withdrawal of release restores the withheld state for subsequent reads; it cannot recall already downloaded/viewed information. Company advancement may be visible before numerical OA result release because it is an explicit recruiter action.

Bulk selections are limited to 100 explicit application/revision pairs. Each candidate commits separately; the response reports saved/conflict/access errors individually. A durable manifest binds actor/key to the exact request, while each item has its own replay-safe transaction receipt. Reusing a key with changed content is a conflict. A partial batch is not advertised as all-or-nothing. Refresh after a conflict and create a new approved request; never change revisions silently.

## Exports and access

CSV/XLSX exports use the same current-stage, lifecycle and objective-recommendation filters as comparison. They include only explicit contact/status/score/decision fields; no private notes, source code, question materials, media or similarity evidence. Strings that could execute as spreadsheet formulas are escaped. Export is audited, limited to 5000 rows and refuses truncation; narrow filters for larger jobs. Live pagination/export reads are not a transactionally frozen whole-cohort snapshot; active edits can change later pages/counts. REST refresh is authoritative and socket updates are hints.

The owning recruiter can inspect their job; writes require verified recruiter status. Company-name equality grants no access. Admin reads require `applications.read` or `*`; writes/reconciliation require `applications.write` or `*`. Candidate account and OA/mobile capabilities cannot access company reports/actions, bulk operations, contacts or exports. Admin application detail displays canonical workflow/report/review controls and disables incompatible legacy edit/delete actions. Admin job detail includes the same pipeline plus delivery inspection; read-only admins are still denied write operations by the API.

## Previewed communications

Select 1–100 candidates on the current job page, compose a plain-text subject/message and preview. No email is sent by preview or queueing. Preview uses current candidate account email, excludes inactive/withdrawn/unavailable accounts and deduplicates normalized addresses within the batch; skipped entries are disclosed. The recruiter approves the exact recipient/content snapshot, expiring after ten minutes. Queueing rechecks candidate email and application revision atomically; changed recipients/stages require a new preview. A preview queues once; identical queue replay returns the original batch. A separately approved new preview is a new intentional message campaign.

Each recipient gets an individual durable `company_messages` item. No recipient list is exposed to another candidate. Supplied plain text is escaped for HTML. Subject newlines are rejected. No internal report/notes are automatically merged into content; the recruiter must review what they compose. No new credit debit or hidden fee is introduced for company decisions, reports, export or these queue operations; normal configured mail-provider costs still apply.

New company-action, bulk and communication writes require the workflow and company flags. Existing manual `/stage-actions` decisions retain their original workflow rollout gate and authorization; OA advancement cannot bypass the new company decision checks. Dispatch requires all three:

- `GENHIRE_WORKFLOW_ENABLED=true`
- `GENHIRE_COMPANY_HIRING_ENABLED=true` (new, default false)
- `GENHIRE_HIRING_EMAILS_ENABLED=true` (existing, default false)

An actual configured non-noop mail provider is required. A development noop success never becomes a company `sent` status. Start the supervised worker from `python-backend` only in the intended deployment:

```
venv/Scripts/python.exe scripts/workers/company_communications_worker.py
```

`--once` runs one claim. This loads the backend `.env` and real database, so do not invoke it just to check imports. No worker was started against the application database during implementation. Claims are atomic; each worker dispatches one message at a time with a two-minute preparation lease and two-second polling. Batch size is bounded; provider throughput, additional worker counts and production campaign capacity still require Step 10 measurement/configuration.

Before dispatch, recheck initiator authorization/verification/activity, candidate activity/email and application revision/withdrawal. Changed work becomes `cancelled`; it is not silently rewritten to new content/recipients. As with any external send, a final state change can occur after the last authorization check and during the provider call; already accepted mail cannot be recalled.

States: `queued → preparing → dispatching → sent | delivery_unknown`, or `cancelled` before dispatch. Expired preparation can be reclaimed; `dispatching` and `delivery_unknown` are never automatically retried. `sent` means the provider accepted the send, not confirmed inbox delivery. Provider false/exception/crash can be ambiguous. The UI displays the batch ID and per-recipient state; queued never means delivered. Keep batch IDs for later admin inspection.

Authorized admins inspect a batch in job detail. For unknown/stale dispatch, record provider-side evidence (20–1000 characters) and explicitly confirm accepted send or confirmed non-send. A live preparation/dispatch lease cannot be reconciled early. Confirmed sent becomes `sent`; confirmed non-send becomes `cancelled`. A later resend requires a fresh recipient preview/approval; reconciliation itself never sends mail. These actions are idempotent and audited. There is no exactly-once external delivery claim, automated ambiguity retry, provider bounce/webhook integration or automatic failover.

## APIs and storage

| API | Purpose |
|---|---|
| `GET /api/jobs/:id/company-candidates` | Reviewer comparison/funnel; `stage`, `lifecycle`, `qualification`, `_id` cursor `after`, `limit` 1–200. |
| `GET /api/applications/:id/company-review` | Private recommendation, decision, current integrity hold and release status. |
| `POST /api/applications/:id/company-actions` | Reason/revision/key actions: qualify, not_qualify, hold, release, revoke_release, add_company_stage, advance. |
| `POST /api/applications/:id/stage-actions` | Existing reasoned company round decisions and terminal outcomes; OA advance requires the company endpoint. |
| `POST /api/jobs/:id/bulk-stage-actions` | Explicit per-item revisioned decisions with independent outcomes. |
| `GET /api/jobs/:id/exports?format=csv|xlsx` | Scoped filtered export, bounded/audited. |
| `POST /api/jobs/:id/communications/preview` | Exact recipients plus plain-text subject/message preview. |
| `POST /api/jobs/:id/communications` | Explicit accepted preview/key → durable batch. |
| `GET /api/jobs/:id/communications/:batchId` | Authorized per-recipient delivery state. |
| `POST /api/company-communications/:messageId/reconcile` | Admin provider-evidence disposition; never a resend. |
| `GET /api/assessment-attempts/:id/evaluation` | Existing owner-safe candidate result endpoint now returns only explicitly released summary. |

All new route responses use private/no-store and nosniff. Review/delivery/export access and mutation receipts are durable. New collections: `company_actions`, `company_bulk_operations`, `company_decisions`, `company_previews`, `company_messages`, `company_access`. Critical unique indexes bind actor/key, application decision and batch/email. Preview TTL is expiry plus one day; messages/decisions/audits are retained as application history under a separate future records-retention policy, not deleted by raw-media cleanup. Consent/media retention from Step 7 is unchanged.

## Acceptance and rollback

Local verification uses isolated loopback Mongo transactions, fake mail senders and offline rendered React. No candidate/recruiter was contacted. Full logs/counts are recorded in integration-plan section 22. Validate deployed mail configuration, sender identity, provider request timeouts, queue recovery/alerts, operator reconciliation, accessibility/responsive geometry and realistic export/worker load before enabling. Existing Sphere/SQL/native/GCS acceptance is not replaced by this step.

Monitor queue ages, preparation lease age, stale dispatch/unknown delivery, cancellation reasons, per-item stale/access conflicts and export limits. Alert for unknown dispatch rather than automatically retrying it. Disable new company endpoints/new dispatch with `GENHIRE_COMPANY_HIRING_ENABLED=false`; existing authorized reads, publications, history and delivery journals remain. Existing manual workflow actions retain their separate workflow gate; use that gate when pausing those writes too. Do not delete receipts, reset grades/deadlines, reverse settled billing, erase company stages or resend ambiguous mail during rollback. Step 9 is separate mock OA/practice pricing work; Step 10 completes wider rollout/load/hardening.
