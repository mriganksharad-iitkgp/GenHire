> ARCHIVED: OneCompiler was superseded by OnlineCompiler.io. Historical findings only; use [the final setup guide](OA_FINAL_SETUP.md).

# GenHire: what you need to do now

Checked 21 October 2026. This is the current activation checklist for coding,
MySQL, PostgreSQL and the rest of the OA workflow.

## Current status

| Item | Saved local profile | Saved production profile |
| --- | --- | --- |
| All OA feature switches | Enabled | Enabled |
| Generation, scheduling, evaluation and runtime | Enabled | Enabled |
| Hiring emails, company hiring and mock OA | Enabled | Enabled |
| Integrity, media, variants and similarity switches | Enabled | Enabled |
| Coding provider | `onecompiler` | `onecompiler` |
| SQL provider | `onecompiler` | `onecompiler` |
| OneCompiler API key | Saved; API access blocked by Cloudflare 403 | Saved; API access blocked by Cloudflare 403 |
| Reviewed executor isolation-policy ID | **Missing** | **Missing** |
| Live coding/SQL acceptance | Pending API access and reviewed isolation policy | Pending API access and reviewed isolation policy |

There is no additional `SQL_ENABLED` switch to turn on. SQL becomes available
after real acceptance records `sql_verified: true` for the selected account,
configuration and application database. The feature/acceptance env switches are
already `true`; these values alone do not establish functioning services or
replace the separate live executor record. Cloud Run's deployed variables and
running workers were not inspected or changed by this file audit.

## 1. API keys saved; resolve the API access block

The owner has now saved keys in both private profiles. Live requests from this
test environment receive an interactive Cloudflare HTTP 403 challenge at the
documented API endpoint. See [the live check report](ONECOMPILER_CHECK_AND_COST.md)
for the confirmed response and a support message. Key validity remains
unconfirmed until a real API execution succeeds.

Fill `ONECOMPILER_API_KEY` in:

- `python-backend/.env` for local development.
- `python-backend/.env.production` for production configuration.

Use the appropriate key for each environment and save the editor buffer. Keep
the key in the backend only. Leave both example files without real keys.

The other execution settings are already configured:

```dotenv
OA_EXECUTION_PROVIDER="onecompiler"
OA_SQL_PROVIDER="onecompiler"
ONECOMPILER_API_URL="https://api.onecompiler.com/v1"
OA_EXECUTION_TIMEOUT_MS="30000"
OA_MAX_CONCURRENT_EXECUTIONS="20"
OA_MAX_PRACTICE_RUNS_PER_QUESTION="10"
```

Confirm the provider account has credits for real execution/acceptance calls.

## 2. Complete the provider isolation review

Obtain the actual OneCompiler account's isolation/limit documentation or support
confirmation and have the execution review completed. It must cover code
network/filesystem isolation and hard resource limits; SQL network/file/role
restrictions; bounded output; recovery; and fresh, separate datasets for each
request. The live correctness tests below do not independently prove all these
properties.

Set `GENHIRE_EXECUTOR_ISOLATION_POLICY_ID` to the identifier of that completed
review in the selected backend profile. It must match `policy_id` in the private
review JSON. Do not use a guessed approval ID.

Create `python-backend/.private/onecompiler-security-review.json` locally. That
directory is excluded from Git and Docker images. Start with this template,
replace the identifying fields, and set each assertion true only after its
actual review/test has passed:

```json
{
  "policy_id": "YOUR_ACTUAL_REVIEW_POLICY_ID",
  "reviewed_by": "YOUR_REVIEWER_IDENTIFIER",
  "evidence_reference": "YOUR_PRIVATE_REVIEW_REFERENCE",
  "reviewed_at": "ACTUAL_ISO_TIMESTAMP_WITH_TIMEZONE",
  "code_network_denied": false,
  "code_filesystem_isolated": false,
  "code_hard_resource_limits": false,
  "sql_network_denied": false,
  "sql_file_access_denied": false,
  "sql_role_escape_denied": false,
  "sql_output_limit_verified": false,
  "sql_crash_recovery_verified": false,
  "provider_isolation_evidence_reviewed": false
}
```

All review assertions must be true to run acceptance. The timestamp must include
its timezone and be within the previous seven days. If the provider cannot
establish these requirements, SQL cannot yet be activated under the agreed
assessment requirements; retain the exact limitation for engineering review.

## 3. Verify local configuration, then run live acceptance

First verify that `.env` selects the intended development/staging database. OA
requires MongoDB transactions on a replica set or sharded deployment. Use a
separate development/staging database for the initial acceptance run.

From PowerShell at the repository root:

```powershell
Set-Location D:\Projects\GenHire
$env:ENV_FILE = (Resolve-Path .\python-backend\.env).Path

python scripts/check_environment.py --profile local

& .\python-backend\venv\Scripts\python.exe .\python-backend\scripts\admin\discover_onecompiler_account.py

& .\python-backend\venv\Scripts\python.exe .\python-backend\scripts\admin\validate_assessment_executors.py --execute-live --security-review .\python-backend\.private\onecompiler-security-review.json
```

Platform/shell variables override dotenv: an old key or policy ID already set in
the terminal must also be updated. Discovery only reads the language catalog;
the final command makes paid OneCompiler calls and writes acceptance evidence
to the selected application database. It does not charge recruiter wallets.

Require **both** of these fields in the final JSON result:

```json
{"state": "passed", "sql_verified": true}
```

The result also includes observed runtime versions. `state: passed` with
`sql_verified: false` enables coding acceptance only; inspect `sql_error` and
resolve that failure before treating SQL as available. The SQL checks exercise
both engines with repeated schema names, different datasets, actual column
metadata, duplicate rows, nulls, decimals, Unicode, row order and empty results.

If a paid POST has an uncertain outcome, do not repeatedly rerun it to force a
pass. Retain the request journal and resolve the uncertainty first. Attestations
expire after 24 hours: plan genuine renewal for each environment. Changes to the
key/account, endpoint, timeout or review-policy ID require fresh acceptance.

## 4. Keep the API and all seven workers running

Run the API through your existing startup/deployment method. For local OA,
run each worker below in its own terminal, from `D:\Projects\GenHire`, with
the same explicit `ENV_FILE` selection as step 3:

```powershell
& .\python-backend\venv\Scripts\python.exe .\python-backend\scripts\workers\assessment_authoring_worker.py
& .\python-backend\venv\Scripts\python.exe .\python-backend\scripts\workers\assessment_runtime_worker.py
& .\python-backend\venv\Scripts\python.exe .\python-backend\scripts\workers\assessment_evaluation_worker.py
& .\python-backend\venv\Scripts\python.exe .\python-backend\scripts\workers\practice_assessment_worker.py
& .\python-backend\venv\Scripts\python.exe .\python-backend\scripts\workers\hiring_scheduler_worker.py
& .\python-backend\venv\Scripts\python.exe .\python-backend\scripts\workers\company_communications_worker.py
& .\python-backend\venv\Scripts\python.exe .\python-backend\scripts\workers\assessment_retention_worker.py
```

These are separate long-running commands; pasting all seven into one terminal
runs only the first until it exits. Authoring also processes reference-validation
jobs. Runtime/evaluation drive public runs, deadlines and private grading.
Scheduling/communications workers can dispatch queued emails to actual
recipients because their switches are already on; confirm the intended queues
and recipients before starting them. Production needs supervised, continuously
running worker processes; deploying the web API alone does not start them.

## 5. Deploy the backend settings and repeat acceptance in production

1. Deploy the migrated backend code and worker code to your existing GCP setup.
2. Inject `ONECOMPILER_API_KEY` as a backend secret and set the reviewed policy ID
   and execution settings on the API and relevant workers. Local file changes do
   not update a deployed service. Docker excludes the backend dotenv files.
3. Preserve existing database, Google identity, AI, storage, Redis and email
   configuration. Production `REDIS_URL` is expected from the existing
   `genhire-redis-url` Secret Manager reference. Do not replace it with an ordinary
   blank variable. Omit `GOOGLE_APPLICATION_CREDENTIALS`, including blank values,
   from Cloud Run variables so the attached service identity supplies ADC.
4. Run the same acceptance script as a deliberate administrative task inside the
   deployed backend environment, using its actual account/settings/database.
   Supply the private review file through an appropriate private mount or
   administrative execution environment; `.private` is excluded from images.
   Local acceptance does not create the production database's attestation.
5. Require `state: passed` and `sql_verified: true` there as well. Restart/redeploy
   all affected API/worker processes to pick up the configuration.
6. Deploy the migrated frontend to the existing Vercel project. Its environment
   contains only public application configuration, never the OneCompiler key.

Optional file audit from the repository root:

```powershell
python scripts/check_environment.py --profile production --allow-runtime-secrets
```

This checks the saved production file, not deployed secrets, IAM, workers or live
SQL acceptance. The earlier file audit found a missing policy ID in both
profiles; the owner has since supplied the API keys. It also reported a missing
local `RAZORPAY_WEBHOOK_SECRET`: fill the
matching signing secret if you want local verified payment webhooks. For
production media, include the configured ONNX model in the deployment image
and verify private GCS upload/signing permissions and real camera devices.

## 6. Check the complete user journeys

- Revise old questions that claim the retired runtime versions to the managed
  `provider-default` profile, then validate and review their references again.
  Do this deliberately; old published questions/attempts were not rewritten.
- Publish a small reviewed coding + SQL + MCQ assessment. Test both MySQL and
  PostgreSQL, public Run, hidden-test grading, errors and partial scores.
- Confirm candidate invitation, scheduling, secure-browser launch, autosave,
  timers, submission, recruiter report/release and application progression.
- Test mock OA purchase, generation, grading, feedback and wallet settlement.
- Verify email delivery, camera/dual-device evidence, retention and the optional
  variants/similarity workflows you intend to offer. Enabled flags are not
  evidence that those services or content pools are ready.
- Check administrator evaluation operations and OneCompiler console usage.
  Actual per-request debits remain unknown where the provider returns only
  balance snapshots; estimates are labeled separately.

No deployed GCP resources were removed. Retired SQL jobs, their bucket, images
and dedicated IAM need a separate inspected and approved deletion plan. They are
not needed to run the new OneCompiler integration.

For adapter details and failure behavior, see
[the OneCompiler setup guide](docs/oa_onecompiler_setup.md).
