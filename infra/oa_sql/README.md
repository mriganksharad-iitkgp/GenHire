# Disposable SQL validation jobs

Target: existing GenHire project, `europe-west1`, PostgreSQL 17 and MySQL 8.4.
This directory prepares deployment; it does not imply images or cloud jobs have
been built, provisioned or isolation-tested.

Step 6 requires result `execution_evidence_version: 2` and executor contract
`oa_cases_v2`. Rebuild/review both pinned images and rerun live acceptance; old
attestations do not match. Bootstrap/fixture failures are infrastructure errors,
while candidate query errors/timeouts are graded separately. Query/source limits
accept the runtime's 64,000-byte candidate answer budget. See
[evaluation operations](../../docs/oa_evaluation_operations.md).

Each execution creates a fresh database. Untrusted fixture SQL uses a separate
non-superuser author login. The query login has SELECT only; file access,
plugins, local infile and TCP listeners are unavailable. Bootstrap credentials
are never provided to query execution. The parent enforces a query deadline
independently of SQL session settings, then kills the disposable process group.
No database is shared between executions. Actual escape/abuse/engine-version
tests must pass in the built images before any validation is trusted.

Build from this directory with Dockerfiles `Dockerfile.postgresql` and
`Dockerfile.mysql`. Scan/test both images and supply immutable image digests to
Terraform. The build requires network access to official image/package sources.
Runtime database binaries are dropped to their dedicated OS user. No production
database URI is accepted. Images contain no platform API tokens or account keys.

Terraform variables: `project_id`, `billing_account`, `backend_service_account`,
`artifact_bucket`, `postgresql_image`, `mysql_image`. Use existing project/account
values; do not create a second project. If the billing account currency differs
from USD, supply `budget_currency` and the current USD-10 equivalent in
`budget_units` before planning. Keep tfvars/state out of Git. Run `terraform init`,
`terraform validate`, then review `terraform plan` before applying. This creates
only new SQL resources/IAM bindings, preserves other project services, and never
grants access to unrelated application buckets. No Terraform apply was run.

Budget defaults: $10/month target, alerts at 50%, 80%, 100%, one task per
execution, one vCPU/1 GiB, 60-second task timeout, zero automatic task retries.
The application adds a **global one-execution slot across both dialects** and a
hard pilot maximum of **200 dispatches per UTC month**, including uncertain or
failed dispatches. Task parallelism alone does not limit concurrent executions.
Do not raise admission limits before measuring costs. The alerts-only budget
does not enforce a monetary spending cap; image builds, registry, logs and other
project usage need separate monitoring. Do not automatically disable billing on
the shared GenHire project, as that would interrupt existing screening.

Private request/result objects expire after one day. Runtime IAM is limited to
reading `sql-validation/requests/` and creating `sql-validation/results/`; bucket
public access is prohibited. Results are tied to request ID/content hash. Do not
expose GCS artifacts, vendor URLs or credentials to candidates.

Set backend placeholders in `.env.example` after provisioning. Keep
`GENHIRE_ASSESSMENT_EXECUTION_ENABLED=false` until real fixture correctness,
timeouts, DDL/file/network/role abuse, output caps and crash/dispatch recovery are
verified. An uncertain Cloud Run POST is held for reconciliation; it is not
blindly retried or billed as a new dispatch. Abandoned slots must be reconciled
against the actual execution before release.

## Live acceptance after provisioning

Run `python scripts/admin/validate_assessment_executors.py --execute-live
--security-review PATH` from `python-backend` only in an explicitly selected
environment. This command loads that backend's `.env`, uses its Mongo database,
consumes managed execution quota and creates a private Sphere Problems canary.
It does not deploy infrastructure, activate jobs or charge recruiter credits.
Keep the long-running authoring worker stopped during the initial acceptance.
Do not run this command merely to test the application locally.

Before running, configure the four compiler/version pins from **both live account
catalogs**, both endpoints/tokens, approved master/testcase judges, SQL project,
jobs and private bucket. Temporarily enable server-side execution for this
operator check; publication still requires the resulting live attestation.
The supported labels are `3.12`, `22`, `21`, `C++20` for Python, JavaScript, Java,
C++ respectively. A compiler ID/version guessed from public examples is invalid.
If the account does not provide a target, keep publication blocked and resolve
the runtime choice rather than silently substituting it.

The private security-review JSON needs `policy_id` equal to
`GENHIRE_EXECUTOR_ISOLATION_POLICY_ID`, `reviewed_by`, `evidence_reference` (an
internal report identifier), and a timezone-aware ISO `reviewed_at` no older
than seven days. These boolean checks must each be `true` **only after actual
security tests/review**, not to bypass setup:

- `code_network_denied`, `code_filesystem_isolated`, `code_hard_resource_limits`
- `sql_network_denied`, `sql_file_access_denied`, `sql_role_escape_denied`
- `sql_output_limit_verified`, `sql_crash_recovery_verified`
- `images_scanned_and_digest_pinned`

Review Sphere account sandbox/resource policy and both actual image digests;
verify SQL file reads, role escalation, network functions, huge output and task
crashes against the built containers. The source implementation alone is not
evidence of those properties. Rotate the policy ID and rerun acceptance whenever
images or sandbox policy change. Keep the review file/evidence out of Git.

The command checks all four languages with stdin/stdout and typed integer
functions, exact runtime probes, wrong output rejection, Python timeout,
PostgreSQL/MySQL fixtures, reader DDL denial, SQL timeouts, and the Problems API
reference/wrong-answer path. This is bounded acceptance, not a load test or proof
of all type combinations. Full typed edge-case/live escape testing belongs in
the referenced operator review. Successful acceptance expires in **24 hours**;
rechecks put the existing profile on hold and failures do not restore acceptance.
Only a passing live run writes `assessment_executor_attestations.state=passed`.

Execution IDs, private evidence and created Problems resource IDs are retained
in `assessment_executor_preflights` / `assessment_executor_dispatches`. Interrupted
POSTs are never automatically repeated. Reconcile provider-side unknown outcomes
and clean up operator canary problems using recorded IDs; do not delete actual
assessment problems. Missing SQL result objects retain the global slot: verify
the corresponding Cloud Run execution is terminal before any administrative
slot release. Automated terminal-execution reconciliation is not implemented.

The Sphere pilot adds a separate hard maximum of **500 submissions per UTC
month**, configurable downward with `GENHIRE_SPHERE_MONTHLY_SUBMISSION_LIMIT`.
It counts reference validations and acceptance calls, including ambiguous POSTs;
it does not cover other applications using the same Sphere account. SQL monthly
quota is independently configurable downwards to 1–200. Concurrency is fixed at
one across both SQL engines and task timeout at 60 seconds for this pilot;
the corresponding `.env.example` fields document those fixed deployment values.
Changing them alone does not raise runtime limits. Budget alerts remain advisory.

Before invalidating an existing attestation or dispatching paid canaries, the
operator preflight now checks its minimum expected remaining workload: currently
28 Sphere submissions and 12 SQL executions. Insufficient quota returns
`preflight_budget_insufficient` without dispatch or acceptance mutation. This is
a read-only snapshot; concurrent traffic can still consume quota afterward, so
per-dispatch atomic admission remains authoritative. Catalog/runtime-pin failures
are now recorded as failed preflights and revoke acceptance rather than leaving
it silently stuck in `checking`.

The 24-hour expiry has not been weakened. Daily full preflights still exceed the
current monthly caps before candidate traffic. See the
[owner renewal/quota blocker](../../docs/oa_owner_setup_guide.md#16-resolve-the-remaining-production-blockers-with-engineering)
and approve an operating design before continuous production use.

Sources: [Cloud Run job overrides](https://docs.cloud.google.com/run/docs/reference/rest/v2/projects.locations.jobs/run),
[budget alerts](https://docs.cloud.google.com/billing/docs/how-to/budgets),
[job Terraform resource](https://registry.terraform.io/providers/hashicorp/google/7.10.0/docs/resources/cloud_run_v2_job),
[budget Terraform resource](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/billing_budget.html).
