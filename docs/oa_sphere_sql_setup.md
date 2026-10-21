# Sphere Engine and SQL setup

Updated 20 October 2026. Official documentation was researched; no real provider
execution, deployment or security acceptance was performed in this session.

## Saved configuration and changes

Both private backend profiles now contain the public endpoints supplied by the
owner (existing nonempty values were preserved):

```dotenv
SPHERE_COMPILERS_ENDPOINT=https://114917b3.compilers.sphere-engine.com/api/v4
SPHERE_PROBLEMS_ENDPOINT=https://114917b3.problems.sphere-engine.com/api/v4
```

Both saved files still had empty `SPHERE_COMPILERS_TOKEN` and
`SPHERE_PROBLEMS_TOKEN` when checked. Save your editor changes in the backend
files; unsaved values are unavailable to Python. No token was copied from the
screenshot. Rotate the Containers token exposed there before using it.

Only local `.env` now enables `GENHIRE_WORKFLOW_ENABLED`,
`GENHIRE_ASSESSMENT_GENERATION_ENABLED` and `GENHIRE_COMPANY_HIRING_ENABLED`.
These enable development controls, not candidate acceptance. Local AI credentials
are configured; funding, generation quality and workers still need verification.
Database connectivity could not be confirmed. Production/example flags remain
disabled. Restart the backend after saving. Process variables override dotenv;
editing local files does not update GCP or Vercel.

## What each token permits

| Product | Capability | Additional setup | Current GenHire use |
|---|---|---|---|
| Compilers v4 | Compile/run source with stdin; retrieve output, diagnostics and status | Actual compiler/version pins, quota, expected outputs, scoring and sandbox review | Coding reference validation and candidate execution; GenHire calculates marks. |
| Problems v4 | Store problems/testcases, execute against judges, return verdicts | Authored problem, testcase/master judge IDs, fixtures and reference validation | Required by full executor acceptance canary. Candidate questions are currently graded through Compilers plus GenHire, not all uploaded to Problems. |
| Containers | Configured multi-file projects, database services and custom evaluation scenarios | Project IDs, versions, init/run/test scripts, isolated fixtures, adapter and acceptance | Not integrated. SQL currently uses GCP disposable jobs. |

All three tokens authenticate services; they do not configure projects, grant
unlimited capacity or prove successful execution. Compilers status 15 indicates
successful execution, not automatically a correct answer against expected output.
Sources: [Compilers v4](https://docs.sphere-engine.com/compilers/api/overview-version-4),
[Problems v4](https://docs.sphere-engine.com/problems/api/overview-version-4),
[Containers projects](https://docs.sphere-engine.com/containers/handbook/projects),
[Containers submissions](https://docs.sphere-engine.com/containers/api/quickstart).

## Find judge IDs and runtime versions

1. Save the Compilers and Problems tokens in their matching backend fields.
   Never put tokens in the endpoint URL, frontend files or command arguments.
2. From your activated backend environment run:

   ```powershell
   Set-Location D:\Projects\GenHire\python-backend
   python scripts/admin/discover_sphere_account.py
   ```

   This new command only reads `/test`, `/compilers` and Problems `/judges`.
   It creates no submissions/problems, invokes no SQL job, connects to no Mongo
   database and writes no configuration. It strips provider URIs and redacts
   configured tokens. Authentication/catalog success is not live acceptance.
3. From `testcase_judges`, select the account's **Ignores extra white spaces**
   judge for the current echo canary. Set its positive `id` as
   `SPHERE_TESTCASE_JUDGE_ID`. An exact-byte judge may fail this canary because
   the Python solution prints a newline. Confirm semantics if names differ.
4. From `master_judges`, select the account's **Generic master judge** for the
   canary. Set its positive `id` as `SPHERE_MASTER_JUDGE_ID`. Do not copy judge
   type IDs, compiler IDs or example IDs. Ask Sphere support if judges are absent.
5. Fill `SPHERE_RUNTIME_PROFILES_JSON` with real compiler IDs, version IDs and
   exact version names available in **both** catalogs. Keep approved labels
   Python `3.12`, JavaScript `22`, Java `21`, C++ `C++20`. The
   [owner guide](oa_owner_setup_guide.md#5-configure-sphere-engine-in-its-dashboard)
   has the JSON shape. Labels alone do not select/verify runtimes; execution must
   prove versions and C++20 support. Do not invent IDs or silently downgrade.

Problems exposes `GET /judges?typeId=0` (testcase) and `typeId=1` (master), with
`limit`/`offset` pagination. The discovery command retrieves both types without
following token-bearing links. A testcase judge compares one result; a master
combines verdicts/scores. Compilers-only execution needs neither, but the current
integrated preflight requires both. See the
[judge API](https://docs.sphere-engine.com/problems/api/overview-version-4).

Sphere also offers a percentage-of-passed-tests master judge. GenHire computes
its own weighted marks, so its authoritative score does not come from that field.
Some testcase judges return zero score even on accepted solutions. See
[judge semantics](https://docs.sphere-engine.com/problems/handbook/judges).

## Current Run, Submit and scoring behavior

- Coding **Run** executes the first sample, or custom stdin/supported typed
  function input. It gives feedback, not marks; pilot limit is 30 runs/attempt.
- Coding **Submit** grades hidden cases. Marks = question maximum multiplied by
  passed hidden-case weight divided by total hidden-case weight. With equal
  weights, 3/5 passed earns 60% of that question's marks. Samples add no coding marks.
- SQL **Run** executes the candidate query on the first public sample dataset.
  Candidates can change the query. Arbitrary custom seed datasets/custom SQL input
  are currently rejected; supporting those requires an additional feature.
- SQL **Submit** grades all validated weighted datasets, including sample and
  hidden datasets. Comparison checks column names, typed rows, duplicates,
  configured ordering and numeric tolerance. Authors supply schema, private
  reference SELECT, dataset seed SQL, expected columns/rows and weights.
- Section weights determine the final score. Candidate errors/timeouts can lose
  marks; provider or fixture infrastructure failures leave evaluation unavailable
  rather than inventing zero. Hidden fixtures/reference solutions stay private.

## SQL: finish the implemented GCP setup

1. Follow [owner guide section 6](oa_owner_setup_guide.md#6-configure-google-cloud-identity-sql-images-and-jobs)
   and [infra instructions](../infra/oa_sql/README.md). Use the existing GenHire
   project in `europe-west1`; obtain its project ID and billing account.
2. Build, scan and isolation-test both SQL Dockerfiles in `infra/oa_sql`; push
   immutable image digests to Artifact Registry. Engines are PostgreSQL 17 and
   MySQL 8.4. Each execution creates a fresh database and restricted query role;
   no persistent Cloud SQL database or production database connection is needed.
3. Review/apply the existing Terraform with the project, backend identity, private
   bucket, digests and budget. It provisions SQL jobs/IAM, not application workers.
4. Set `GENHIRE_SQL_PROJECT`, `GENHIRE_SQL_ARTIFACT_BUCKET`, the two deployed job
   names and `GENHIRE_EXECUTOR_ISOLATION_POLICY_ID`. Job-name defaults do not mean
   resources exist. Configure local ADC; production API and workers use attached
   identities and server secrets with the required scoped permissions.
5. Create sample and hidden SQL fixtures covering NULLs, duplicates, ties and
   empty tables. Validate expected outputs with the private reference query.
6. Complete actual isolation review and explicit paid acceptance using
   [the preflight instructions](../infra/oa_sql/README.md#live-acceptance-after-provisioning).
   A full pass needs at least 28 Sphere submissions and 12 SQL executions.
   Temporarily enable execution only for this operator check after provisioning;
   never fabricate the security-review booleans or `_ACCEPTED` flags.
7. Start/deploy the seven continuous workers listed in the owner guide. Test the
   kiosk installer and full recruiter/candidate Run/Submit/grading/release journey
   in staging before enabling candidate runtime and production flags. Inject
   backend configuration into the API **and workers** on GCP. Vercel receives
   only public API/OAuth/download settings, never Sphere tokens.

Budget alerts target $10/month but do not enforce a spending cap. Pilot quotas
are 200 SQL dispatches/month, globally one active SQL execution and a 60-second
task timeout, plus a separate 500 Sphere submissions/month. Reference validations,
public runs and per-case grading consume quota. Full acceptance expires in 24h;
daily full rechecks would exceed these caps before candidate traffic. Resolve
the [renewal/capacity blocker](oa_owner_setup_guide.md#16-resolve-the-remaining-production-blockers-with-engineering)
before sustained production. Official references:
[Cloud Run jobs](https://docs.cloud.google.com/run/docs/create-jobs),
[budget alerts](https://docs.cloud.google.com/billing/docs/how-to/budgets).

## Alternative: SQL on Sphere Containers

Feasible in principle: create private PostgreSQL/MySQL projects in Sphere's
Projects UI, confirm exact supported versions/capacity, and define init/run/test
scenarios to seed a fresh database, execute a restricted candidate query and
return bounded results. Review network/file access and prove hidden fixtures are
inaccessible to candidate execution. A database service checkbox alone does not
establish isolation or compatibility with the approved versions.

Engineering must implement a Containers adapter with project pins, fixture
packaging, dispatch/poll/results, idempotency, unknown-outcome reconciliation,
quotas, scoring integration and acceptance tests. Containers uses a separate
versioned API contract; changing the v4 client's hostname is insufficient. No
`SPHERE_CONTAINERS_TOKEN` variable is currently consumed by GenHire. Keep the
rotated token private until that alternative is deliberately implemented; it
cannot satisfy the existing GCP SQL adapter's configuration requirements.
