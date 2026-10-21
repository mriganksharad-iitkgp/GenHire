# Recruiter job drafts and OA question authoring

Updated 21 October 2026.

## Publishing and recruiter-only previews

Choose Active to publish an OA job on its first save. An existing draft can also
be published directly; there is no extra OA review gate on the job listing.
Assessment delivery keeps its independent execution/readiness checks. Existing
candidate workflows are not silently replaced by editing the plan.

Job details show a collapsible preview of the selected questions, answers and
testcases. This preview is for the owning recruiting account; candidate job APIs
return public metadata only. Full question-bank/delivery tools are optional and
collapsed by default. Edit job remains the main place to change question content.

Interview qualification defaults to 60%; the proctoring minimum defaults to 70%
and is used when required proctoring is enabled. Blank thresholds restore the
defaults; explicit custom values and zero are preserved. Choosing section timers
shows prefilled minutes and score weights alongside a live totals summary. Score
weights must total 100%, and section minutes must equal the total OA duration.

Validation: 56 backend tests cover publication, privacy, authoring and progression;
rendered job setup checks verify defaults, section weights and private preview
behavior. Focused frontend lint and the production web build pass.

## AI question generation failures

Local JSON/truncation errors no longer mark a provider as quota-exhausted. The
previous message matcher misread "exceeded its output budget" as a quota error,
which caused the following OA request to fail against a five-minute cooldown.
HTTP status codes now take precedence, and a definite schema rejection is reported
as an output problem rather than funding guidance.

Coding generation uses smaller stages: statement, 15-20 tests and one language
first, then starter/reference sources for each other requested language. Core and
translation stages use 4096-token allowances. Accepted language stages survive
rate-limit waits privately. MCQs use batches of up to three, with 2048/4096-token
allowances; JD output uses 2048. Provider size refusals can reduce the allowance
without truncating the brief. `GROQ_JSON_MAX_OUTPUT_TOKENS` remains a generic JSON
default; staged authoring requests supply their own smaller task-specific budgets.

Supported GPT-OSS models use strict response schemas. A definite Groq JSON/schema
rejection can recover through plain JSON transport, still parsed and checked by
the same application validators. One bounded content-repair cycle follows invalid
output. Final merged questions must match every configured slot, language, mark
and testcase requirement; the whole selection is checked before settlement.
Generated code is never executed on the application server by this process.

JD and OA question authoring can use the same-account Groq backup configured by
`GENHIRE_ASSESSMENT_GROQ_FALLBACK_MODEL=openai/gpt-oss-120b`. It has a separate
cooldown entry from the primary model; clear this setting to disable it. Other
app-wide interview model settings are unchanged. Account model access, quotas
and provider pricing still apply. DeepSeek billing and Google quota failures were
observed, so these credentials alone do not establish a usable fallback.

Temporary refusals preserve the private JD, accepted question slots and partial
coding-language work. Reopening/resuming uses the same request and single 10-credit
reservation. Unknown interrupted calls refund without blind replay; cancellation
and permanent failures refund without replacing the existing form. Questions are
attached only after the complete validated draft is ready. Older checkpoints can
resume correctly even when MCQ batch sizes change.

Verification: 49 targeted backend tests, eight rendered compact-form checks,
focused frontend lint and the web build passed. A full synthetic JD + 20 MCQs +
four medium coding problems passed in about 443 seconds, including genuine rate
limits and JSON recovery, with one 10-credit isolated test-wallet charge. The final
larger translation allowance also passed a live coding-only assessment through
the backup while the primary was daily-capped. Full backup workload verification
is recorded in the integration progress log. These checks verify authoring and
storage, not managed code/SQL execution or semantic/performance acceptance.

## If OA template or AI loading returns "URL not found"

The frontend and backend must run the same revision. A stale local backend can
serve older job routes yet return 404 for the newer authoring POSTs. Restart it
from `python-backend` with `venv/Scripts/python.exe app.py`. On Windows native-thread Socket.IO, local development uses `GENHIRE_DEV_RELOAD=0`
and requires a fresh backend restart after changes; the automatic reloader was
observed to stop with WinError 10038. Production also keeps reload off. Deploy the updated backend
as well as frontend in production. The API catalog exposes `authoring_api.version`.

The local backend starts its OA authoring queue runner when the local workflow and
generation flags are enabled. It honors `GENHIRE_DISABLE_JOBS=1` and optional
`GENHIRE_LOCAL_OA_WORKER=false`. Production still needs the standalone authoring
worker below; enabling a frontend control does not start a Cloud Run worker.

Device autosave and the saved server revision now appear as one resume choice.
Keeping/resuming the device copy does not create a second server draft. Another
browser with a stale revision must reload before overwriting the working draft.
Existing attached hiring versions are retained as history.

## Current layout: one page with expandable sections

Job creation and editing now use one scrollable form; there is no Next/Back wizard.
Opening a section preserves scroll. A missing required field opens its enclosing
sections so browser validation can reach it.

1. Choose a role starter or enter job fields. Templates minimize after selection.
   Description, responsibilities/benefits and interview monitoring are expandable.
2. Open screening criteria and company rounds if you want to customize them.
3. Open application dates, schedule and credit review to change the defaults.
4. Near the end, open **Want to add an online assessment? Click to add** and select
   **Include an online assessment**. OA stays off and collapsed until requested.
   With a matching prebuilt job role and no selected questions, this loads its full
   authored OA. Existing questions and unfinished editors are preserved. Replacing
   a selected set requires the visible replacement confirmation.
5. Review questions by opening MCQ, CODING or SQL. Each group starts collapsed;
   opening one question closes its sibling. **Expand all / Collapse all** is available
   per group. Coding testcase and SQL dataset editors follow the same pattern.
6. For a generated draft, choose **Fill with AI** in the header or open that section
   at the end. It starts collapsed and retains the complete 10-credit JD + selected
   OA generation flow described below. Manual starters and editing are free.
7. Save private question versions, then save the job to attach them. Device recovery
   continues to include your unsaved editor and saved question selection.

Help buttons support hover, keyboard focus and touch. Their explanations and
notifications render above dialogs instead of being clipped by modal containers.
Close buttons have red hover/press feedback; motion respects reduced-motion settings.

### Complete role starters

The 19 job templates map to 15 role-specific OA presets (with developer/ML/SRE
variants sharing the corresponding preset). Server-authored MCQs include five
role-fundamental questions plus workplace, numerical and evidence-reasoning items;
20/25-question presets include all answers, explanations, marks and difficulty slots.
These are editable starter assessments rather than calibrated skill tests.

SDE includes three coding tasks; web roles include two; DevOps/QA include one.
Data Analyst includes two SQL tasks; Data Science/ML includes coding and SQL.
Each coding task includes statement, constraints, stdin/stdout contract, all four
approved language starters/references, pinned runtime labels and 16 weighted cases
(two examples plus 14 hidden cases). SQL includes schema, private reference query
and six separate sample/hidden datasets covering NULLs, duplicates, empty tables
and unmatched data. Noncoding roles use MCQs.

Questions are created through a verified-recruiter, owner-scoped transactional
endpoint, never shipped with answer keys in the public frontend bundle. Replaying
an operation does not duplicate bank entries. Applying templates consumes no wallet
credits and neither approves content nor activates the job.

New coding drafts saved from either editor require 15-20 cases. AI output with
fewer/more cases is rejected and its generation reservation follows the failure
release path. Old immutable v1 content remains readable; editing it requires bringing
its suite to the new count before saving. Counts alone do not establish correctness.
See [template verification evidence](oa_template_validation.md) for the measured
slow-baseline results and remaining managed-runtime checks.

## Current flow: manual or one complete AI draft

This section supersedes the earlier JD-only / plan-default AI choices described
in the historical notes below.

- **Fill manually (free):** fill the JD and use the MCQ, coding and SQL editors
  in Online assessment. Enter the statement, correct answers, marks, explanations,
  reference solutions and sample/hidden cases/datasets yourself. No AI is called.
  Saving questions keeps section counts, difficulty slots and marks aligned with
  the actual saved set. Existing section timer choices are preserved.
- **Create with AI (10 credits total):** describe the job and OA topics in one
  brief. In the same panel select whether OA is included, each question type's
  count, OA duration, difficulty mix, SQL engine, MCQ mode and coding settings.
  One user action prepares the JD plus all requested questions, answers,
  explanations, reference code and sample/hidden cases. The displayed amount is
  for the complete request, not per question or internal model call. JD-only has
  the same price. A deliberate new generation is another paid request.

Completed questions appear grouped into MCQ/CODING/SQL sections. Expand a question
for its preview and choose **Edit prefilled question** for the complete editable
form, including private answers and testcases. Saving an edit creates an immutable
version and replaces that selected draft slot. Save the job to attach the working
set; AI regeneration replaces the selected draft set rather than appending it.
Removing the final selected question clears the working selection on job save.
Creation and editing offer the same builder. Editing loads existing selected
question content and retains it during unrelated JD changes; a question-load
failure blocks submission until retried.

The extra OA setup fee now defaults to **0**; there is no second 30-credit
creation/activation setup charge for a new draft under this configuration.
Candidate assessment attempts, screening and optional monitoring retain their
own runtime prices. Existing paid reservations retain their approved amounts
until explicitly released/settled. Advanced single-question tools in the review
workspace remain a separate, collapsed operation and quote their own AI fee;
using them is unnecessary to attach the questions already included in a complete
JD + OA draft.

### Background processing and recovery

`POST /api/job-draft-generations` reserves the displayed whole-request price and
returns promptly. `GET /api/job-draft-generations/<operation_key>` returns scoped
progress/results. Duplicate keys replay one operation; different input under the
same key is rejected. Only one combined request per recruiter runs at a time.
A lookup can recover the recruiter's active request when another browser starts
one while it is still pending. Unknown transport outcomes retain the operation
key and retry that same request, including its original configuration snapshot.

The existing `scripts/workers/assessment_authoring_worker.py` now drains this
queue as well as question generation and validation queues. The worker may use
several internal AI calls to keep full coding/SQL questions within response
limits; these do not cause additional wallet debits. Completion atomically stores
all private questions and captures the single reservation. Failure releases the
entire amount and writes no partial bank set. Expired unknown provider-call
leases fail/release instead of silently repeating paid provider work.

Cancel generation releases a pending reservation. An uncertain request can also be
cancelled safely: its operation key is blocked from a delayed enqueue. A provider
call already in flight can finish, but its question outputs are not attached or
published after cancellation.

Close and choose **Resume device draft** later to restore the pending request or
its completed fields. Device snapshots include request key/configuration and
question editors, and remain subject to the existing seven-day/local-storage
limits. Uploaded files need reattaching after reopening if an unconfirmed upload
must be retried. JD documents are not stored in device snapshots.

Generation supplies draft content, not execution acceptance or independently
verified answers. Code and SQL generation no longer requires live judge
credentials just to draft content; actual execution validation, review and
publication still require the configured services. No code or SQL runs in Flask.
If reference validation later fails, correct the draft manually for free or
explicitly request another generation; there is no automatic paid retry.

### Run the changed flow

Restart the backend and run the authoring worker continuously from python-backend:

```powershell
.\venv\Scripts\python.exe scripts/workers/assessment_authoring_worker.py
```

Local and production dotenv profiles, plus both examples, now set
`RECRUITER_AI_JD_CREDITS=10` and `GENHIRE_OA_JOB_SETUP_CREDITS=0`. Production must
also use those injected environment values and deploy the updated API and worker
image; editing a local dotenv does not update Cloud Run. The regeneration-specific
legacy variable is retained for compatibility but no longer sets a second AI
price. Frontend price labels come from the backend catalog.

Validation for the current flow: 144 automated backend/UI/unit checks passed,
plus zero-warning frontend lint and a production build. APIs/providers are mocked
or isolated locally for those checks; live model quality, judge execution and
pixel-level browser acceptance are not established by them.

## Historical implementation notes

## Job creation and editing

Selecting a role starter now collapses the template list, returns keyboard focus
to its summary and announces which template was applied. The first-step OA card
shows the role's suggested assessment. Include OA to use it; changing the role
does not silently replace customized assessment questions/settings.

Progress autosaves after 600 ms and is also flushed on close, page hide and
navigation/unmount. This device draft contains job fields, OA configuration, the
wizard step and the JD generation prompt. It is scoped to the signed-in account
and to either a new job or the specific edited job. Reopen the form and choose
**Resume device draft**. It expires after seven days; successful job saving clears
it. A failed save retains it. **Discard device draft** removes that backup.

Device drafts are browser storage, not a cloud backup or an update to the live
job. Uploaded file contents are not stored: reattach the JD file if needed.
Storage restrictions/quota failure show an autosave warning. The existing
**Save hiring draft** action stores valid configuration on the server and can
be resumed separately; incomplete local work is not automatically submitted to
the server or published. Avoid shared browser profiles for confidential job work.

Hover over a question-mark help control, or focus it from the keyboard, for
plain-language explanations of cohort/rolling applications, screening windows,
manual activation, shared/section timers, coding formats, SQL dialects and
monitoring. The selected value remains editable beside its explanation.

## Where actual questions are entered

1. In **Online assessment**, choose recruiter-authored, AI-generated or hybrid.
   Set topics and requirements in **Instructions for assessment generation**.
2. Save the job as a draft. Open the job's **Job details**, then choose
   **Manage assessment questions**. The question workspace requires the saved
   assessment ID; selecting a source in the wizard does not itself generate or
   charge for questions.
3. Manual: choose **Add MCQ question**, **Add CODING question** or **Add SQL
   question**. Forms include answer options, correct answers, statements,
   reference solutions/queries, sample and hidden cases/datasets, marks and limits.
4. AI/hybrid: use **Additional generation instructions**, choose type/difficulty,
   count and marks, and preview the credit quote. Generation starts only after
   approval. Manual-only plans must be saved as hybrid/AI before using generation.
5. Save, validate and review each question version; save the assessment selection
   and publish reviewed content. Activation/invitations are separate actions.

## Pasted problems and testcases

In the question workspace enable **Use a pasted problem or a reference link**.
Paste the task, input/output format, constraints and examples. For SQL, include
the schema and sample data; for MCQs, include the options and answer requirements.
An optional HTTPS link is attribution only. The application does not fetch arbitrary
URLs or obtain another platform's hidden tests. A URL alone is rejected.

You can copy the statement into the manual form without AI or request a quoted
AI conversion. One problem is converted per request. It remains editable content
requiring validation/review; it is never automatically published.

| Option | Use when | What must still be checked |
|---|---|---|
| Trusted reference solution + proposed cases (recommended when available) | You have independently verified solution code. Include its language and the full statement. | Check generated solutions/cases against the trusted algorithm, constraints, edge cases and required runtime. The reference is guidance; the importer does not certify it. |
| Your testcase guidance + AI expansion | You already have examples or an existing test suite. | Verify that the generated inputs/outputs preserve those requirements, then inspect new boundary/performance cases. Guidance is free text, not a guaranteed lossless test-suite import. |
| AI proposes sample + hidden edge cases | You have a clear statement but no tests. | Independently verify expected answers. AI-generated code agreeing with AI-generated answers does not prove correctness. |
| Entirely manual authoring | You need exact control or cannot use AI. | Enter all cases/reference solutions yourself, run execution validation and approve only after review. |

Generated candidates should cover minimum/maximum sizes, empty inputs when
allowed, duplicates, ties, negative/large values and performance bounds. SQL
datasets should exercise NULLs, duplicates, empty tables and ordering. MCQ review
should check ambiguity and exact correct-option sets. Multiple valid outputs
need an explicitly supported deterministic comparison contract; do not assume
arbitrary custom judges are supported by this importer.

Future improvements worth considering: a structured JSON/CSV testcase importer
that preserves exact fixtures, independent brute-force/reference comparison for
small random inputs, property-based tests, mutation checks against known wrong
solutions, and a licensed curated question bank. These are options for further
work, not features claimed by this release. Direct website scraping would also
need separate permission/licensing, domain and network-security controls.

## Validation boundaries

This update passed 93 backend/UI checks, zero-warning frontend lint and the
production build. The checks use fixture APIs and isolated local Mongo storage;
they do not establish live provider or device acceptance.

Coding/SQL AI conversion still needs the configured execution validator. Without
it, manual statement drafting remains available; execution approval/publication
is blocked. MCQ AI generation can work separately when its generation worker is
enabled. No live provider execution, paid purchase, email or production deployment
was performed to implement this UX update.


## Historical: superseded wizard navigation and AI choices (21 October 2026)

Next, Back, step links and restored steps now reset the dialog scroll to the top
and focus the selected step. Create and edit share this behavior. Form widths,
fieldsets and footer controls are constrained; footer stats have a separate row.
Long guidance and future-charge details are expandable. Applying current role
defaults produces a visible status message, including repeated clicks.

The AI JD control now offers two explicit scopes:

| Choice | What it fills | Credit behavior |
| --- | --- | --- |
| Job details only (default) | Title, department, location, experience, compensation text, skills and JD content | The displayed server-configured AI JD price per request; later settings stay unchanged |
| Job details + matching OA plan defaults | JD fields plus role-based OA sections, counts, marks, duration and instructions | Same JD request and price; role defaults are local presets, with no second AI request |
| Manual role template | Editable JD starter; enable OA for matching plan defaults | No AI generation charge |
| Quoted OA question generation | Actual MCQ, coding or SQL questions after the job is saved | Separate quote and explicit approval in Job details / Manage assessment questions |

Neither JD scope generates actual OA questions, invents approval thresholds, nor
changes configured application/interview windows. The second choice explicitly
replaces OA plan defaults; use the first to preserve a customized plan. Credit
prices come from the backend catalog, not hardcoded marketing text. Saving
settings is distinct from future activation, candidate-attempt and AI charges.

### Manual questions inside creation and editing

In Online assessment, use Add MCQ/CODING/SQL question. The existing structured
editor supports answer options/keys, reference code, input/output formats,
constraints, sample/hidden cases, SQL schema and separate sample/hidden datasets.
An unfinished editor is included in device autosave. Save private question version
stores a schema-checked question in the private bank, without activation or an AI
charge. Save hiring draft stores settings only. Save the job to attach its saved
questions to the assessment working selection. Save/discard an open question
before submitting the job; turning OA off requires removing pending questions.

Job creation records the returned job ID before attaching question versions. If
attachment fails, the saved form is locked and Retry attaching questions completes
the remaining operation without creating another job. The job ID and pending
selection survive device draft recovery. Retries merge with the current workspace
and do not append duplicate version IDs; revision conflicts remain visible. All
questions still require validation, independent review and content publication.
Questions removed from the pending selection remain in the private question bank.
Device recovery is account-specific, browser-specific and expires after seven days;
reattach uploaded JD files after reopening. This is not cross-device draft sync.

### Options for a later AI expansion

1. **Recommended next: reviewable full-plan suggestions.** One recruiter brief could
   propose JD, interview focus, OA mix and schedule. Show a field-level preview,
   preserve locked fields, and apply only selected suggestions. Keep thresholds,
   dates and any paid generation subject to deliberate review.
2. **Section assistants.** Refine only the selected JD/pipeline/OA section with a
   visible server quote; preserve all other fields. This offers more control but
   can require more individual AI requests.
3. **One guided end-to-end draft.** Save a draft job, request approved OA generation
   and show its worker progress inside the wizard. This reduces navigation but
   needs resumable job/workspace IDs, combined cost disclosure and separate
   reference-execution/review stages before activation.

These three expansions are proposals, not claims of implemented AI behavior.
No paid provider requests, email dispatch or production deployment were performed
for this UI update. Automated interaction checks use fixture APIs; they establish
state transitions and persistence, not live Sphere/SQL execution or visual browser
acceptance.
