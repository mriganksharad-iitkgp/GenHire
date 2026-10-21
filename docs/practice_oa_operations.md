# Practice OA and pricing operations — Step 9

Implementation is disabled by default. Real `.env` is unchanged. No paid AI generation, actual Sphere/SQL execution, GCS/device capture, application database migration, cloud provisioning, email, native installer publication or deployment occurred during implementation. Local tests use isolated loopback Mongo, fake AI/judge/media transports and rendered React; they are not production acceptance.

## Candidate journey and purchase units

Practice offers separate Mock interview and Mock online assessment choices. Existing screening practice remains on its own engine/billing path. Mock OAs reuse the secure assessment workspace, server timer, revisioned autosave, public Run, immutable submissions and private objective grader.

All nine approved presets are available: SDE; frontend/backend/full-stack; data analyst; data science/ML; DevOps/SRE; product; QA/automation; business analyst; custom. Candidates can customize topics/instructions, specialization, easy/medium/hard counts, per-question marks, section weights, total/section minutes, single/multiple/mixed MCQs, four approved languages, stdin/stdout or typed-function coding and PostgreSQL 17/MySQL 8.4 SQL. Section weights total 100; separate section minutes total the assessment duration. Existing limits remain 120 questions (100 MCQ, 10 coding, 10 SQL), 300 minutes and the configured grading-case budget. C and descriptive/AI response grading remain deferred.

`GENHIRE_MOCK_OA_CREDITS` defaults to **30** per newly generated validated OA and one attempt, including deterministic grading, question explanations and best-effort basic AI educational advice. Camera/dual are optional separately quoted implemented extras, initially 10 credits each through existing environment keys; unavailable media choices are hidden and rejected by the server. Basic secure-browser controls are included. Practice similarity, enriched analytics, AI authorship detection and unimplemented extras cannot be purchased. Recruitment setup, recruitment accepted attempts, paid regeneration, reviewed variant batches and post-evaluation similarity retain their distinct units; a mock purchase does not debit any of them.

The candidate first receives a binding 15-minute quote containing normalized configuration/hash, price version, line items, total, included features, AI-processing policy and capture/start policy. Explicit approval is required. Configuration changes remove the displayed quote/approval; server price changes/expiry reject an unused quote. Purchase reserves the candidate wallet atomically with a durable generation job. Quote consumption plus candidate/request-key indexes prevent duplicate purchases, including retries under another key for the same quote. Only one generation can be pending per candidate. A new quote and explicit purchase for another mock is a new paid generation; start/resume never charges again.

Funds capture **only when the entire validated, playable practice publication and invitation commit**. Incomplete/invalid/quality-rejected/disabled/unknown-outcome generation returns the hold through a durable transaction; partial batches never become a shorter paid assessment. A failed purchase returns the same failed record on replay rather than regenerating or charging again. The candidate can approve a fresh purchase after the returned hold. Already purchased content retains its quoted price if env prices later change.

Ready purchases disclose a **30-day start window**. Valid accepted starts receive full duration even past that entry cutoff. Readiness/preflight is not a start. The practice worker marks unstarted ready purchases expired after the window; this is not an automatic technical refund because validated generation was delivered. Reconnect/closing the window does not restart a timer, create another attempt or refund a deliberate blank submission. Scope-specific support can approve browser/camera accommodations and extra time through the shared reason/revision controls. Functional reasons do not require medical details.

## Pool and runtime isolation

Practice questions, publications, invitations, attempts and reports explicitly use `pool=practice` and candidate ownership. Purchases/jobs live in practice-specific collections, without fake hiring jobs/applications or company decisions. Recruitment question reading/publishing/activation and similarity reject practice material. Hiring scheduling/overview queries exclude practice records. Practice content uses namespaced blueprint/stage identities to coexist with existing compound unique indexes, without dropping production indexes or inventing application IDs.

AI generation receives only the selected practice requirements and slots; it never reads live bank questions into a prompt. Literal complete-content hash collisions with protected recruitment material or already selected practice content reject the batch. This is an additional guard, not a promise that independently generated classic problems are semantically unique.

Default entry uses the existing opaque capability and scoped `aud=genhire-oa` session: no account JWT in the OA deep link. Consent, recent preflight, camera/phone requirements, internal editor clipboard policy, randomization, autosave revisions and retention reuse Step 7. Browser exceptions require administrator approval before starting. Runtime version/kiosk metadata remains client-reported, not cryptographic device attestation. Monitoring is sampled images/events, not continuous audio/screenshots or an automated misconduct verdict. Candidate questions exclude answers/reference solutions/hidden fixtures before completion. Public Run selects sample/custom inputs through the shared isolated dispatcher; no code or SQL runs on the web host.

Practice finalization, deadline submission and evaluation update practice purchase state, never application stages, job funnels, hiring notices or company outcomes. Objective MCQ exact-match/weighted code/SQL grading is unchanged. Recruitment results still need recruiter release; own practice scores become available after usable evaluation without that company release workflow.

## Generation, validation and educational advice

Generation uses batches of at most five requested slots and strict bounded question JSON. A separate AI invocation checks correctness/ambiguity; only a strict approved response with no issues proceeds. This is a second invocation, not guaranteed independent reasoning or human review. MCQ structure plus AI critique does not prove factual correctness; the separate practice content acceptance gate needs actual quality sampling before rollout. Recruitment human review requirements remain unchanged.

Code/SQL additionally require actual managed reference execution across the selected contracts/runtimes/datasets and verification of per-case evidence. Publication rechecks earlier batch hashes, quality evidence, configured profile and total case budget. Acceptance fencing serializes publication/start with revocation of the current executor attestation. Mocked outputs, a boolean passed flag or an enablement flag never establish real executor acceptance. Changed/expired executor profiles block new starts; revalidate acceptance or use support disposition for verified permanently unusable purchases. Do not fabricate attestation rows.

Generation has a durable global single-worker admission lease, ten minutes with progress renewal. Claims are transactional/atomic; a process that loses its lease cannot publish. Expired generating/validating calls have unknown outcomes and are compensated rather than silently invoked again. Fully stored batches resume with the next batch. The existing AI fallback service still governs its own underlying provider retries; no exactly-once external AI HTTP or monthly-cost guarantee is made. Provider latency, production worker sizing and generation capacity require Step 10 measurement; the conservative pilot admission is not a high-throughput claim.

Completed practice reports include objective total/section/question marks, public question text/options and practice explanations/correct MCQ choices. They do not return hidden input/output fixtures, reference source or recruitment content. Explanation hashes remain bound to the graded questions. AI advice is generated separately from bounded performance topics/difficulty/marks, not raw source, personal profile, hidden fixtures or employer material. It is clearly labeled educational, cannot change marks and makes no authorship/hiring/misconduct verdict. Advice errors/unknown leases remain `unavailable`; objective marks and local explanations remain usable. There is no extra debit for advice and no automatic repeated paid advice call.

## Refund and support operations

Own candidates can inspect practice history and actual OA billing operations/reservations/captures/returned funds. Recruiters cannot read candidate practice reports/media merely because they share a company name. Authorized admins require application read/write permissions for support inspection/mutations; reads are audited.

Admin Candidate detail includes mock OA inspection, prestart accommodations, evidence/retention review, extra time and verified platform-failure disposition. Support must document actual operational evidence (20–1000 characters). A confirmed unusable generation returns its reservation; a confirmed unusable ready/active/submitted/evaluating purchase refunds the captured amount once. Active answers are immutably submitted before ending participation; evaluation/queued tasks are cancelled/fenced, session access is revoked and source/grade/billing history is retained. Completed usable evaluations cannot be refunded through this technical-failure endpoint. Already unknown judge dispatches keep their reconciliation/capacity journals; a credit refund does not authorize another external POST.

Normal wrong/blank answers, disconnection, monitoring observations and an AI-advice outage do not constitute permanently unusable objective evaluation. Feedback failure does not invent a final grade or repeat a purchase. Existing administrator evaluation failure handling also returns a practice purchase once when permanently unusable grading is confirmed. No candidate can invoke support refund/accommodation writes on themselves.

## Server pricing and operation history

The public `/api/pricing/catalog` exposes only prices/units/feature availability and active recharge-pack display fields, with no user ledger, credentials or service endpoints. Legacy interview/JD/invite prices come from the actual payment configuration; OA prices use validated server env settings. Active packs come from existing plan records. Missing prices/packs show unavailable/see-wallet states rather than hardcoded amounts. Restart services after editing environment prices so existing payment configuration and workers agree.

Landing activity/recharge/signup prices, candidate interview practice and recruiter invite cost copy now use server data. OA draft/generation/activation quotes remain authoritative for their operations. Unimplemented JD enriched-report/similarity toggles are removed; existing drafts can explicitly remove deferred flags. Recruitment similarity remains its separately approved after-evaluation report. Candidate/recruiter wallet pages expose paged reservation/capture/refund history; no activity-derived estimate becomes a bill. An operation's immutable amount/snapshot governs past work; a new catalog does not reprice it.

## Worker, flags and API map

New flags in `.env.example`, both false:

```
GENHIRE_MOCK_OA_ENABLED=false
GENHIRE_MOCK_OA_CONTENT_ACCEPTED=false
```

Purchases/publication also require existing workflow/generation enablement and the shared runtime/evaluation/security/integrity approvals. Code/SQL need genuine current executor acceptance; selected media needs media acceptance. These are rollout controls, not proof of successful live validation. Real `.env` was not edited.

From `python-backend`, supervise the new explicit worker:

```
venv/Scripts/python.exe scripts/workers/practice_assessment_worker.py
```

`--once` performs one bounded generation/advice/ready-expiry pass. It loads backend `.env` and the intended database, so do not invoke it as an import test. No worker was run against the application database here. The existing assessment runtime worker still submits deadlines/public Runs and the evaluation worker still grades through the common execution queue. Retention stays on the Step 7 worker. Keep compensation/reconciliation workers supervised during rollback.

| API | Access / purpose |
|---|---|
| `GET /api/pricing/catalog` | Public nonbinding display data only. |
| `GET /api/billing-operations[/:id]` | Own payer/audience history, 20 records per page, `after` cursor. |
| `GET /api/practice/assessments/catalog` | Candidate templates/defaults/capabilities. |
| `POST /api/practice/assessments/quotes` or `/api/pricing/quote` | Candidate binding mock quote, `{configuration}`. |
| `POST /api/practice/assessments` | Approved quote/key → reservation and durable generation. |
| `GET /api/practice/assessments` | Own paged purchase/resume history, `after` cursor. |
| Shared `/assessment-invitations` and `/assessment-attempts` endpoints | Existing opaque launch, consent, start/resume, save/Run/Submit/evaluation/media/retention controls. |
| `GET /api/practice/assessments/:attemptId/report` | Own practice report or authorized admin; never recruitment. |
| `GET /api/admin/practice-assessments/:candidateId` | Authorized admin support history/access audit. |
| `POST /api/practice/assessments/:purchaseId/platform-failure` | Authorized admin, evidence and stable key; atomic return/retained submission. |

New collections: `practice_assessment_quotes`, `practice_assessment_purchases`, `practice_purchase_controls`, `practice_generation_jobs`, `practice_generation_capacity`, `practice_feedback_jobs`, `practice_assessment_actions`. Shared questions/versions/attempts/submissions/execution/evidence records retain explicit pool ownership. Quotes expire via TTL after expiry plus one day; purchase/submission/billing/teaching history has its separate records-retention policy and is not deleted by raw-media expiry. No production index deletion/backfill is introduced.

## Acceptance and rollback

Before enabling, sample actual role/MCQ/SQL/coding quality, reference runtime results, end-to-end secure-browser and phone capture, accommodations, graded explanations, real AI failure/latency/cost and purchase/refund crash recovery. Validate actual privacy/retention/storage behavior and responsive/assistive navigation. Step 3/6/7 provider/device/storage acceptance and Step 8 mail acceptance remain open. Local pass counts are in integration-plan section 23.

Monitor generation queue/lease age, held credits, failed/unknown calls, validation/profile errors, objective evaluation queue, unresolved execution dispatch, advice unavailable and technical refund actions. Disable new practice work with the mock flag; retain authorized history, accepted deadlines, common evaluation/settlement and retention. Let reserved generation compensate instead of deleting jobs/receipts. Do not reset accepted attempts, mix pools, fabricate scores/attestations or erase billing records. Step 10 retains broader production hardening and rollout authorization.


## 21 October 2026: background practice and compact launch flow

Local development now runs practice generation, educational advice and ready-entry
expiry through LocalPracticeWorker alongside the existing authoring queues.
Production continues to require the explicit supervised practice worker shown above;
there is no newly enabled production web-thread worker.

Practice uses the shared assessment authoring provider chain, small homogeneous
MCQ batches (3), single SQL questions, and staged coding sources. Each generated
coding problem still requires 15-20 cases and genuine reference execution before
publication. JSON-object critique/advice requests now explicitly ask for JSON,
fixing a confirmed provider HTTP 400 rejection. Definite temporary rate refusals
checkpoint private generated content/languages with a bounded retry window; unknown
interrupted calls retain the existing failure/compensation behavior.

The catalog now exposes effective purchase readiness and per-type availability.
Unconfigured execution does not prevent MCQ practice; presets select their
available MCQ portion, disclose unavailable coding/SQL, and disable those inputs.
Missing runtime profiles, SQL project/bucket and reviewed isolation configuration
were observed locally. They were not fabricated or marked accepted.

The page now uses selectable role cards, quick question counts, automatic default
weights/times, and collapsed advanced settings. Exact price and AI-processing
approval precede the durable purchase. History shows bounded generation counts
and polls while pending, refreshing again on returning to the page. When the
watched purchase becomes ready, the secure-browser guide opens; launch exchanges
an opaque code and never embeds the account token or starts the attempt timer.
Existing browser accommodations use the common assessment entry page. Purchases
and refunds are collapsed; ready purchases retain explicit start/resume actions.

Validation: 38 isolated backend tests (24 practice, 4 local worker, 10 generation),
11 practice UI checks, 4 integrity checks and 10 runtime checks, full frontend lint
and production build. Real configured providers generated and quality-checked six
synthetic MCQs in two batches in 12.052 seconds, reaching ready with exactly one
30-credit capture in a disposable test wallet; no real candidate account was
charged. This is not code/SQL execution or real-device kiosk acceptance.

The local backend was restarted after confirming no in-flight generation leases,
and its health/startup were checked. Production deployment remains separate.
