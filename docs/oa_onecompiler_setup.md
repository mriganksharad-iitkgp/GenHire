> ARCHIVED: OneCompiler was superseded by OnlineCompiler.io. Historical findings only; use [the final setup guide](../OA_FINAL_SETUP.md).

# OneCompiler OA execution

Updated 21 October 2026. Coding and SQL now use `OneCompilerExecutionProvider`.
The existing Vercel frontend, GCP API/workers, MongoDB, Redis, AI services,
authentication and private evidence storage remain in place.

## Backend configuration

All four backend dotenv profiles include:

```dotenv
OA_EXECUTION_PROVIDER="onecompiler"
OA_SQL_PROVIDER="onecompiler"
ONECOMPILER_API_URL="https://api.onecompiler.com/v1"
ONECOMPILER_API_KEY=""
OA_EXECUTION_TIMEOUT_MS="30000"
OA_MAX_CONCURRENT_EXECUTIONS="20"
OA_MAX_PRACTICE_RUNS_PER_QUESTION="10"
```

Fill the private key manually in the selected backend profile, or inject it as
a backend secret. Examples remain blank. Restart the API and execution,
validation, generation and evaluation workers after deployment. Never place the
key in a frontend variable. Existing workflow, generation, evaluation, integrity
and rollout flags retain their existing values and prerequisites.

Removed: all `SPHERE_*` fields, `GENHIRE_SPHERE_MONTHLY_SUBMISSION_LIMIT`,
all `GENHIRE_SQL_*` judge fields, and `GENHIRE_OA_EXECUTION_CONCURRENCY`.
The latter is replaced by `OA_MAX_CONCURRENT_EXECUTIONS`. Environment preparation
will also remove these keys from older profiles. General GCP/database settings
and shared grading queues remain required.

## Execution and grading

The backend calls `POST /v1/run` using `X-API-Key`. Supported provider language
IDs are `cpp`, `python`, `java`, `nodejs`, `c`, `mysql`, `postgresql`. Existing
`javascript` questions map to `nodejs`; both names work. C currently uses the
stdin/stdout question contract; existing typed function harnesses work for
Python, JavaScript/Node.js, Java and C++.

Run Code executes the public sample or custom coding input. Each question has
its own practice-run limit. Final grading retains deterministic output
comparison, hidden-case weights, partial scores and existing billing/report
settlement. Reference validation batches stdin tests sharing the same source;
typed function cases keep separate generated harnesses.

The documented API has no runtime-version selector, so new questions use
`provider-default`. Live acceptance probes actual language and database versions
and records them with a 24-hour account/profile-bound attestation. This is an
observed managed runtime, not a pinned version. Existing questions claiming old
versions must be deliberately revised, validated and reviewed before reuse.
Existing published attempts retain their data; no database migration or content
rewrite is performed automatically.

Every paid dispatch gets a durable `onecompiler_execution_requests` journal
entry first. Duplicate identities collect the original result. Ambiguous POSTs
retain their identity and slot, require operator review, and never retry
automatically. There is no documented asynchronous result lookup to recover a
lost synchronous response. A completed journal can recover a crashed worker;
an unknown response cannot be guessed or bound to another provider's ID.
Retired-provider public jobs are marked for reconciliation rather than
resubmitted to OneCompiler. Do not switch providers while old attempts are
actively executing; drain/reconcile them before deploying this migration.

## SQL acceptance is mandatory

Each SQL request contains schema creation, one selected dataset's seed data and
the candidate query. Candidate queries are restricted to one SELECT/WITH query.
SQL results are serialized by the engine as JSON inside hexadecimal frames,
including actual column aliases and types. The backend compares actual result
sets with null/type/numeric tolerance/duplicate/row-order handling. It never
grades a rendered ASCII table or substitutes expected rows for actual results.
Hidden schema setup/seed/query diagnostics and hidden outputs are not returned
to candidates. Candidate queries never run against the application database.

**SQL publication, mock purchase, new starts and execution require a separate
`sql_verified` live acceptance record.** A coding pass alone does not enable SQL.
The checks reuse the same schema/table name across requests with different
randomized seed values, check duplicate rows, SQL null versus the string `NULL`,
and discover database versions. An independent current provider isolation review
is also required. These checks are evidence of tested behavior, not proof of all
possible sandbox properties.

The provider documentation does not establish dataset isolation, read-only roles,
network/file restrictions or hard limits for the account. SQL JSON serialization,
client metacommands, metadata permissions and reproducible fresh state must be
verified by real calls. MySQL/PostgreSQL setup overhead is part of the reported
provider execution time; limits are conservative. Unsupported serialization,
missing required execution metrics or inadequate isolation keeps publication
blocked. No alternate SQL provider or GCP execution fallback is installed.

## Run live acceptance

The API key is intentionally left for the owner to fill. No live acceptance is
claimed by this source change or by synthetic test results.

Use an isolated staging database and current provider review. Set
`GENHIRE_EXECUTOR_ISOLATION_POLICY_ID` to the reviewed policy identifier and
explicitly enable `GENHIRE_ASSESSMENT_EXECUTION_ENABLED` for the check; keep
candidate rollout flags off. Create a private JSON review outside Git:

```json
{
  "policy_id": "YOUR_REVIEWED_POLICY_ID",
  "reviewed_by": "YOUR_OPERATOR_IDENTIFIER",
  "evidence_reference": "YOUR_PRIVATE_REVIEW_REFERENCE",
  "reviewed_at": "ACTUAL_RECENT_ISO_TIMESTAMP_WITH_TIMEZONE",
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

Set each assertion true only after its real review/test passes. From the backend:

```powershell
python scripts/admin/validate_assessment_executors.py --execute-live --security-review C:/PRIVATE_PATH/onecompiler-review.json
```

Require `state: passed` for coding and `sql_verified: true` for SQL. Inspect the
stable `sql_error` code if SQL fails; SQL stays disabled while coding may remain
available. Recheck each environment/account after changes and before expiry.
This command spends real provider credits without changing recruiter wallets.

## Usage and credit accounting

Each journal records purpose (public practice, grading, reference or acceptance),
language, hidden/public status, batch size, estimated credits, state and account
balance snapshots when returned. The administrator-only evaluation operations
endpoint aggregates requests/executions and estimates by purpose/language/state.

The documented response reports remaining balances, not a per-request actual
credit debit. `actual_credits` therefore stays null, and the operations response
explicitly counts unknown actuals. Concurrent account calls make subtraction of
balance snapshots unreliable; no such subtraction is presented as actual usage.
Verify estimates against the provider console/invoice, including large stdin
and batches. The advertised purchase tiers are purchase-dependent; no fixed USD
rate is hardcoded into assessment grading or wallet charges.

Official contract: [Code execution API](https://onecompiler.com/apis/code-execution)
and [live language catalog](https://onecompiler.com/api/v1/languages).

## Retired GCP resources: separate approval required

Repository-only SQL worker images, Terraform and provisioning instructions have
been removed. No deployed resource was deleted or modified. Inventory the
following before proposing decommissioning:

- Jobs named `genhire-oa-sql-postgresql` and `genhire-oa-sql-mysql`, including any
  customized names formerly configured in the backend profiles.
- Their private SQL artifact bucket and retained SQL execution artifacts.
- SQL-only images in Artifact Registry and dedicated job service accounts/IAM.
- SQL-specific budget alerts, schedules or other resources from the former
  `infra/oa_sql` Terraform state.

Check ownership and other consumers first. Obtain explicit approval for a
concrete deletion plan. Preserve the main backend, application database,
evidence bucket, shared queues, Google service identity and all unrelated IAM.
