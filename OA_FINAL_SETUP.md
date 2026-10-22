# GenHire: final OA setup actions

Migration date: 21 October 2026. Current provider: **OnlineCompiler.io** (not OneCompiler). Implementation and live provider smoke checks are complete; production release is pending the steps below. See [the migration record](docs/oa_integration.md) for architecture, testing, costs and limitations.

Update, 22 October: your saved OnlineCompiler key, Aiven URI and CA file passed live checks in both profiles, including PostgreSQL 18.6 over verified TLS 1.3 and rolled-back reference validation. The policy ID is still blank. See [current results, policy ID explanation and GCP certificate steps](AIVEN_GCP_AND_CREDENTIAL_CHECK.md).

Developer testing: [OA_LOCAL_DEVELOPER_TESTING.md](OA_LOCAL_DEVELOPER_TESTING.md) provides an isolated local candidate-page preview with prefilled answers and one-click real coding/SQL submission checks. It uses a disposable MongoDB and does not create production acceptance. The owner has subsequently added a policy identifier; its reviewed acceptance command is still a separate step.

## 1. Fill these backend fields yourself

Edit `python-backend/.env` for local work and `python-backend/.env.production` for the production profile. The loader selects one profile; it does not merge them. Platform environment variables take precedence. Restart the backend and supervised OA workers after changing settings.

| Field | What you must supply |
|---|---|
| `ONLINECOMPILER_API_KEY` | Your current **OnlineCompiler.io REST API key**. Keep it on the backend. The old OneCompiler key cannot authenticate here. |
| `AIVEN_POSTGRES_URL` | The PostgreSQL connection URI from your Aiven project `genhire`, dedicated **PostgreSQL 18 development service**, including database, username, password, hostname and port. URL-encode password characters. This is separate from the application MongoDB URI. |
| `AIVEN_POSTGRES_SSL_ROOT_CERT` | Absolute path to that service's downloaded CA certificate. The file must exist for the process running the trusted validator. On Windows use a quoted forward-slash path, e.g. `C:/private/genhire/ca.pem`; in a container use its mounted file path. Never commit credentials or the private environment file. |
| `GENHIRE_EXECUTOR_ISOLATION_POLICY_ID` | Your reviewed isolation policy identifier. It must match `policy_id` in the private security review used by the live acceptance command. An arbitrary string does not establish acceptance. |

The initial migration left the new API key, Aiven URI and CA path blank for manual entry; you have now filled and verified them. Existing unrelated authentication, MongoDB, storage, Google, AI, email and payment assignments were preserved. If you use payments, the existing empty local `RAZORPAY_WEBHOOK_SECRET` also needs your real webhook signing secret; it is unrelated to execution.

## 2. Keep these supplied defaults

```dotenv
OA_EXECUTION_PROVIDER="onlinecompiler"
OA_GENERIC_SQL_PROVIDER="onlinecompiler"
ONLINECOMPILER_API_BASE_URL="https://api.onlinecompiler.io"
ONLINECOMPILER_TEST_BATCH_SIZE="4"
ONLINECOMPILER_RUNS_PER_MINUTE="30"
ONLINECOMPILER_MONTHLY_PLAN_USD="0"
OA_MAX_CONCURRENT_EXECUTIONS="2"
OA_EXECUTION_TIMEOUT_MS="30000"
OA_MAX_PRACTICE_RUNS_PER_QUESTION="10"
OA_ENABLE_SQLITE="true"
OA_ENABLE_DUCKDB="true"
OA_POSTGRES_QUESTION_AUTHORING_ENABLED="true"
OA_POSTGRES_CANDIDATE_EXECUTION_ENABLED="false"
AIVEN_POSTGRES_SSL_REQUIRED="true"
AIVEN_POSTGRES_PURPOSE="question_validation"
```

Use the actual subscription price in `ONLINECOMPILER_MONTHLY_PLAN_USD` if you purchase a plan. Increase rate/concurrency/batch limits only to values confirmed for that account. No plan was purchased. PostgreSQL candidate execution must remain false; SQLite and DuckDB are different dialects and do not substitute for PostgreSQL-specific features.

## 3. Verify configuration and providers

From the repository root in PowerShell, using your backend virtual environment:

```powershell
python-backend/venv/Scripts/python.exe scripts/check_environment.py --schema-only
python-backend/venv/Scripts/python.exe scripts/check_environment.py --profile local
python-backend/venv/Scripts/python.exe python-backend/scripts/admin/discover_oa_provider.py
```

The discovery command reads the compiler catalog and account limits without running candidate code. Its optional `--record-usage` stores an allowlisted usage snapshot in the explicitly configured application MongoDB for admin reporting. It is a database write; run it only against the intended environment. The default is read-only.

Prepare a private full question-contract JSON file for a trusted PostgreSQL 18 reference question. Its schema, seed and reference must be operator approved. Then:

```powershell
python-backend/venv/Scripts/python.exe python-backend/scripts/admin/validate_postgres_question.py --question-json C:/private/genhire/postgres-question.json --trusted-reference
```

This checks the real server version, uses verify-full TLS, creates a unique schema per dataset inside a transaction, bounds query time/results, compares typed results and rolls back. It does not publish the question or permit candidate access. This workflow passed a real two-dataset test with your saved credentials on 22 October; deployed GCP connectivity still needs its own check.

## 4. Complete live coding/SQL acceptance before candidate release

Review actual provider isolation evidence and the controlled staging checks. Do not mark unchecked evidence true. Save a private JSON review with `policy_id`, `reviewed_by`, `reviewed_at` (timezone-aware ISO timestamp within seven days), `evidence_reference`, and these independently verified boolean fields:

```text
code_network_denied
code_filesystem_isolated
code_hard_resource_limits
sql_network_denied
sql_file_access_denied
sql_role_escape_denied
sql_output_limit_verified
sql_crash_recovery_verified
provider_isolation_evidence_reviewed
```

Once reviewed, run against the intended staging MongoDB:

```powershell
python-backend/venv/Scripts/python.exe python-backend/scripts/admin/validate_assessment_executors.py --execute-live --security-review C:/private/genhire/executor-review.json
```

This consumes real execution runs and writes a profile-bound, 24-hour acceptance record. It checks current compiler IDs, stdin/stdout and function contracts, wrong answers, native judging and independent SQLite/DuckDB datasets including empty results. Only known rate/capacity rejections may retry. Ambiguous dispatches remain for operator reconciliation. Review and renew acceptance when it expires or the credential/profile changes. The earlier transport smoke checks did **not** create this acceptance record or certify isolation.

Older questions pinned to previous runtime labels need explicit revision, live reference validation and approval before reuse. Native hidden judging requires the provider limits of 512 MB memory and 64 KB output; existing questions with lower pinned limits are blocked for revision rather than silently changed.

Supervise existing workers from `python-backend`:

```powershell
python scripts/workers/assessment_runtime_worker.py
python scripts/workers/assessment_evaluation_worker.py
```

Keep the existing authoring, progression, integrity and email workers required by your selected features. Existing OA feature/acceptance settings in private files were preserved; their values are not evidence that review or release was completed. Examples retain false rollout gates. Confirm the full recruiter-to-candidate staging journey, wallet settlement, reports, proctoring/device checks and provider failures before enabling a real cohort.

## 5. Deployment actions you must perform later

No deployment, cloud provisioning, purchase, commit or push was performed. GCP/Vercel deployed environment inspection could not be completed: their CLIs and an authenticated browser connection were unavailable in this session.

In the backend deployment and each OA worker, add the OnlineCompiler settings above and inject the API key through your secret manager. Aiven credentials and CA are required only wherever you intentionally run trusted question validation; keep that workflow separate from candidate routes. Preserve all existing application service credentials. Do not upload `.env` files wholesale to Vercel. The frontend needs no execution key, Aiven URI or CA path.

Remove old OneCompiler/Sphere and custom GCP SQL judge keys from deployment configuration after inspecting the deployed workload. The exact retirement list is in [the migration record](docs/oa_integration.md#retired-environment-settings). Retain shared GCP storage/authentication/AI and application MongoDB settings. Drain/reconcile old queued or ambiguous executions before cutover; do not replay them on the new provider. Historical results and IDs remain unchanged.

After staging verification and approved deployment, revoke retired provider credentials in their consoles. No cloud resources have been destroyed. Recheck account limits and peak exam capacity before increasing candidates. Production mount/connectivity, isolation acceptance and release remain pending; stop here before the next OA development milestone.
