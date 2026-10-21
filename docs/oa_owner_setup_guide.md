# OA integration: owner setup guide for local development and production

> Current AI authoring update (21 October): output truncation no longer triggers
> a false quota cooldown. Coding uses resumable language stages, and MCQs use
> smaller batches. The same-account authoring backup is configured with
> `GENHIRE_ASSESSMENT_GROQ_FALLBACK_MODEL=openai/gpt-oss-120b`; clear it to disable.
> The primary Groq daily cap was reached during verification, while DeepSeek
> returned billing errors and Google had exhausted quota. The backup passed live
> generation without new credentials. Each model's account limits/pricing still
> apply. Deploy/restart backend and authoring workers to use the new chain;
> interview model settings are unchanged. The entire JD + OA still costs one
> 10-credit wallet reservation, not an additional charge per language or retry.

> Job publishing update (21 October): OA jobs can now be published on their
> first save without a separate question-review gate on the job listing. Private
> OA delivery still has its own readiness checks. Job-detail question previews
> are recruiter-only. Interview/proctoring defaults are 60%/70%; section timers
> show role-default section weights and durations for adjustment.

> Full-assessment fix (21 October): input plus reserved output can exceed the
> provider account's request ceiling even when JD-only generation succeeds. Groq
> size refusals now adjust the output allowance; temporary rate limits checkpoint
> private progress and resume the same 10-credit operation automatically. MCQs are
> batched, and supported GPT-OSS requests use strict schemas for MCQ/SQL/stdin-stdout
> questions. Keep `GROQ_JSON_MAX_OUTPUT_TOKENS=8192` as the initial coding budget;
> increasing it alone does not resolve an account request ceiling. A full live
> synthetic JD + 23-question draft passed with exactly one test-wallet charge.
> Deploy/restart both backend and authoring worker with this source, and deploy
> the frontend to display automatic waiting/resumption. The local backend has been
> restarted. Refresh an open form; an already failed/refunded request needs a new
> deliberate generation. No extra credentials or feature-flag changes are needed
> for this fix. Real judge/SQL execution acceptance remains a separate requirement.

> OA loading fix (21 October): the old local backend returned 404 for new authoring
> routes. The backend was restarted from current source. Windows automatic reload is disabled after a socket failure; restart explicitly
> after backend source changes. The backend starts the accepted-draft authoring queue locally
> when workflow/generation are enabled. Production still needs its explicit worker
> and an updated backend deployment. Recovery now offers one working draft choice.

> Authoring UI update (21 October): creation/editing is one expandable page. OA is
> offered near the end; choosing it after a role template loads actual private
> question drafts. Restart the backend and authoring worker, then rebuild/redeploy
> the frontend. No new environment fields or secret changes are required for the
> manual starters. AI remains 10 credits per complete draft; OA setup remains 0.
> See [current authoring flow](oa_authoring_ux.md) and
> [template validation evidence](oa_template_validation.md).

Latest authoring change (21 October 2026): Create/Edit job now has **Fill manually**
or **Create with AI**. The complete JD and all selected OA questions cost 10
credits per generation, including JD-only requests. The separate OA setup price
is now 0; screening, candidate attempts and monitoring remain separately priced.
Set both API and worker deployments to `RECRUITER_AI_JD_CREDITS=10` and
`GENHIRE_OA_JOB_SETUP_CREDITS=0`, redeploy the updated authoring worker, and restart
the local backend/worker. The existing authoring worker now handles the combined
queue; without it requests remain queued. See [current authoring flow](oa_authoring_ux.md).
Earlier setup-price instructions below are historical where they differ.

Updated: 21 October 2026. Follow the numbered steps in order. Check boxes record
**your future actions**; none of the external setup below was performed by
creating this guide. On the owner's subsequent request, all eight local,
production and example profiles were synchronized and annotated. Existing filled
values were preserved; this guide contains no private credentials. Search
`# OWNER ACTION:` in your `.env` for remaining account-specific entries.

Latest owner override: all 17 OA `_ENABLED` / `_ACCEPTED` switches are now true
in both private backend profiles for development exploration. Example profiles
remain off. These settings do not attest completed tests, provision services or
update deployed GCP variables. Real executor acceptance remains independently
checked in Mongo. The active local API was still reporting an old disabled flag
after the file edits: stop the backend completely and restart it, then reopen the
job form. Reloading only the frontend is insufficient.

Create and edit now expose an OA card on the first step, 19 searchable job
templates and 16 server OA presets. Enabling OA fills role defaults, while
customized/resumed assessments remain intact. Settings outages have explicit
retry controls; do not overwrite an existing plan when its load failed.

The implementation and local tests exist. Working production OA additionally
needs funded/approved providers, deployed SQL jobs, continuous workers, current
executor acceptance, a tested secure-browser release, and staging acceptance.
**There is no single “turn everything on” switch.**

Related records: [implementation and evidence](oa_integration.md),
[release/rollback runbook](oa_release_runbook.md),
[SQL infrastructure](../infra/oa_sql/README.md),
[baseline backend/Redis setup](required-setup-and-rate-limits.md),
[environment configuration](environment-configuration.md).
Older deployment documents describe historical revisions, not a fresh inspection
of your GCP/Vercel accounts. Confirm current project/service/secret names yourself.

## 1. Understand what runs where

| Component | Local setup | Deployed setup | Your action |
|---|---|---|---|
| React recruiter/candidate/admin pages | Node 22, `react-frontend`, port 3000 | Vercel | Set public frontend variables and rebuild. |
| Flask API | Python environment, port 5000 | Existing GCP Cloud Run backend | Deploy reviewed backend image and inject server configuration/secrets. |
| Workflow, questions, attempts, ledger, queues | Separate local replica-set Mongo database | Your transaction-capable Mongo deployment | Verify replica-set/sharded transactions, indexes, network access and backup. |
| Request protection | Existing local Redis, or development-only fallback if allowed by current config | Reachable shared Redis | Preserve working production secret/network setup. |
| AI questions/critique/advice | Existing funded backend AI provider | Same supported provider stack, production credentials | Verify JSON generation, quality, latency and actual cost. |
| C++/Python/Java/JavaScript execution | Remote Sphere Engine, even when UI/API are local | Sphere Engine Problems v4 + Compilers v4 | Obtain account endpoints, tokens, runtime catalogs and sandbox evidence. |
| PostgreSQL/MySQL execution | Remote GCP jobs, even when UI/API are local | Two isolated Cloud Run Jobs, europe-west1 | Build/scan images, deploy Terraform, configure IAM and test isolation. |
| OA durable workers | Seven separate Python processes | Supervised continuous workers | API deployment alone does not run these workers. |
| Secure Browser | Installed/built Electron 1.3.0 release under test | Tested/signed installer distributed to candidates | Publish compatible installer and public download URL. |
| Camera evidence | Private GCS + functioning detector, if selected | Private application GCS bucket | Test upload, signed review URL, consent, cleanup and detector coverage. |
| Hiring email | Real provider only for deliberately approved test recipients | Verified email provider | Test delivery/unknown reconciliation before dispatch flag. |

**Not required:** a persistent Cloud SQL instance or a shared candidate database.
The approved SQL design creates disposable PostgreSQL 17/MySQL 8.4 processes per
job execution. Do not connect candidates' SQL to your application Mongo data or
any production relational database.

## 2. Prepare an environment inventory before changing anything

- [ ] Record existing GCP **project ID** (not display name/project number), billing
  account ID, backend service name, current image/revision and runtime service-account email.
- [ ] Record Mongo cluster/replica set and separate database names for local,
  staging and production. Choose a separate database user for nonproduction.
- [ ] Record the existing Redis secret reference and how each deployment reaches Redis.
- [ ] Record production frontend/API origins, Vercel project/root directory and
  one stable staging frontend/API pair.
- [ ] Record a private SQL artifact bucket name, two SQL job names and application
  evidence bucket name. Use separate nonproduction SQL jobs/bucket where practical.
- [ ] Record installer release/version/download URL, provider account owners,
  an operator for unknown dispatches, and your approved **total** infrastructure budget.

Keep secrets in your password manager, local gitignored files or Secret Manager.
Do not put them in this guide, screenshots, tickets, Terraform state committed to
Git, Vercel frontend variables, or browser code. The $10/month target covers
incremental SQL infrastructure, not all API, AI, Sphere, Redis or worker spending.

Use placeholders below only after replacing them with your actual values:
`PROJECT_ID`, `BACKEND_SERVICE`, `BACKEND_SA_EMAIL`, `SQL_BUCKET`,
`FRONTEND_ORIGIN`, `API_ORIGIN`, `REPOSITORY` and immutable `IMAGE@sha256:DIGEST`.

## 3. Understand the configuration files and overrides

| Location | What belongs there | What does not |
|---|---|---|
| `python-backend/.env` | Local server config, local DB, server-only provider keys and OA block below | Production DB accidentally selected for experimentation |
| `python-backend/.env.production` | Optional private production reference; keep aligned with actual platform settings | A substitute for updating deployed services |
| GCP API **and each worker's** Variables & Secrets | Production server settings; Secret Manager references for sensitive values | Local Windows credential paths |
| `react-frontend/.env` | Local public API/OAuth/download URLs | Any Sphere/AI/Mongo/Redis/private credentials |
| `react-frontend/.env.production` | Public values used for local production/kiosk builds | Backend flags or secrets |
| Vercel environment variables | Public frontend values, scoped to Preview/Production | The backend `.env` contents |

Edit/add values in existing private files; **do not replace your working `.env`
with these partial snippets**. Preserve baseline auth, rate-limit, payment,
screening, email and model settings. The OA block now appears in all four backend
profiles with owner actions, safe defaults and optional/ADC comments. Add the
reviewed production values to GCP explicitly; files do not update deployments.

Backend process environment overrides dotenv. An explicit `ENV_FILE` /
`DOTENV_PATH` selects that file exclusively; a missing explicit file stops
startup. Otherwise production selects only `.env.production`, and development
selects `.env`. Workers, billing, interview and AI configuration share this
loader; production/explicit environments never fill gaps from local `.env`.
Workers/maintenance commands also refuse a missing Mongo URI or database name;
an explicitly selected file must be complete or complemented by injected values.
For deployed workers inject the complete intended environment and exclude local
dotenv from the image, as the backend `.dockerignore` does. Restart after edits.
Stale PowerShell environment variables can override the file you just edited.

The frontend uses **`REACT_APP_*`**, including on Vite. The Vite config explicitly
embeds only the eight approved public settings into the browser bundle and
rejects unknown `REACT_APP_*`/`VITE_*` entries at build time. Do not rename them
to `VITE_*`. Kiosk builds inject no provider configuration; their API origin
comes from the scoped launch. Build-time changes require rebuild/redeployment.

## 4. Make the local foundation work first

### 4.1 Tools and Python

- [ ] Install Python **3.12**, Node **22**, Git, Google Cloud CLI, Docker Desktop
  with Linux containers, and Terraform >=1.6 if you will provision SQL resources.
- [ ] In `D:\Projects\GenHire\python-backend`, use the existing `venv` if it is
  Python 3.12; otherwise create/select a new 3.12 environment. Activate it:

```powershell
Set-Location D:\Projects\GenHire\python-backend
.\venv\Scripts\Activate.ps1
python --version
python -m pip install -r requirements-dev.txt
```

For a new environment only: `py -3.12 -m venv venv` before activation. Do not
overwrite an environment currently running the API/workers. Production images
use `requirements.txt`; test dependencies belong in development/CI.

**Image alignment:** `python-backend/Dockerfile` now uses Python **3.12**, matching
milestone verification. The source fix does not rebuild or redeploy an existing
GCP image: build, scan and validate the actual new image before production.

### 4.2 Local Mongo must support transactions

An ordinary standalone `mongodb://localhost:27017` is insufficient for OA's
multi-document transactions. Use an Atlas nonproduction database or a local
replica set. MongoDB documents replica-set transaction support in its
[replication guide](https://www.mongodb.com/docs/manual/replication/).

Example **new local-only** Docker setup, from PowerShell, using port 37017 to
avoid your existing application's usual 27017 listener. If port 37017 or the
container name is already in use, inspect your existing installation and choose
another port consistently in mongod, Docker mapping, mongosh, replica-set member
and the URI below; do not delete an existing database.

```powershell
docker run --detach --name genhire-oa-local-mongo --publish 127.0.0.1:37017:37017 --mount source=genhire-oa-local-data,target=/data/db mongo:8.0 --port 37017 --replSet genhireLocal --bind_ip_all
@'
rs.initiate({_id:"genhireLocal",members:[{_id:0,host:"127.0.0.1:37017"}]})
'@ | docker exec -i genhire-oa-local-mongo mongosh --port 37017 --quiet
docker exec genhire-oa-local-mongo mongosh --port 37017 --quiet --eval 'db.hello().isWritablePrimary'
```

Wait for the container before initialization; the last command must return
`true`. Run `rs.initiate` only on a new uninitialized replica set. Later starts
use `docker start genhire-oa-local-mongo`; keep its volume. This unauthenticated
loopback example is for development only, never a public/production database.

Local backend foundation, merged into your file:

```dotenv
FLASK_ENV=development
FORCE_HTTPS=false
FRONTEND_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
MONGODB_URI=mongodb://127.0.0.1:37017/?replicaSet=genhireLocal
DATABASE_NAME=genhire_oa_local
MONGO_MAX_POOL_SIZE=50
MONGO_WAIT_QUEUE_TIMEOUT_MS=2000
MONGO_SERVER_SELECTION_TIMEOUT_MS=5000
```

Keep real stable development values for `FLASK_SECRET_KEY`, `JWT_SECRET_KEY`,
`INVITE_TOKEN_SECRET` and your existing OAuth settings. Do not rotate production
signing secrets as a routine OA setup step.

### 4.3 Redis and baseline health

Use your existing working local Redis. If you need a separate new local instance:

```powershell
docker run --detach --name genhire-oa-local-redis --publish 127.0.0.1:6379:6379 redis:7
```

Set `REDIS_URL=redis://127.0.0.1:6379/0` locally, and preserve the complete existing
request-protection settings from the baseline guide. Production requires shared
Redis and its configured network/TLS/authentication. Do not replace a working
Secret Manager-backed production URL with a blank local template value.

Start the API from an activated backend terminal with `python app.py`. Confirm
`http://localhost:5000/health`, login and existing screening still work before
turning on any OA flag. A healthy API alone does not establish OA readiness.

## 5. Configure Sphere Engine in its dashboard

See [Sphere and SQL setup](oa_sphere_sql_setup.md) for account endpoint updates,
the read-only judge/runtime discovery command, current SQL Run limitations and
the latest local flag changes. The implemented SQL path uses GCP jobs; it does
not require or consume a Sphere Containers token.

- [ ] Sign in/create the intended Sphere Engine account and arrange access to
  **both Compilers API v4 and Problems API v4**, sufficient quota and billing.
- [ ] Obtain each product's account-specific endpoint and token. These can be
  separate credentials. Ask support if the account catalog/products are incomplete.
- [ ] Obtain approved **master judge** and **testcase judge** IDs for the Problems
  canary. Do not guess IDs from examples or use an arbitrary “default judge.”
- [ ] Retrieve `GET /compilers` through each product using your account credentials.
  Match real compiler IDs, version IDs and version names in **both catalogs**.
- [ ] Confirm Python 3.12, Node.js 22, Java 21 and a compiler configuration that
  actually enables C++20. Merely relabeling a compiler does not change its runtime.
- [ ] Obtain evidence of network denial, filesystem isolation and hard execution
  limits for your account's sandbox. Resolve unsupported requirements before accepting it.

The adapter requires endpoints shaped as:

```dotenv
SPHERE_COMPILERS_ENDPOINT=https://YOUR_ACCOUNT.compilers.sphere-engine.com/api/v4
SPHERE_COMPILERS_TOKEN=YOUR_PRIVATE_COMPILERS_TOKEN
SPHERE_PROBLEMS_ENDPOINT=https://YOUR_ACCOUNT.problems.sphere-engine.com/api/v4
SPHERE_PROBLEMS_TOKEN=YOUR_PRIVATE_PROBLEMS_TOKEN
SPHERE_MASTER_JUDGE_ID=YOUR_APPROVED_POSITIVE_INTEGER
SPHERE_TESTCASE_JUDGE_ID=YOUR_APPROVED_POSITIVE_INTEGER
```

The exact suffix, HTTPS and `/api/v4` matter; no query-string token belongs in
the endpoint variable. Keep tokens backend-only. Avoid token-bearing URLs in
browser history, shared terminals or screenshots. Official contracts:
[Compilers v4](https://docs.sphere-engine.com/compilers/api/overview-version-4),
[Problems v4](https://docs.sphere-engine.com/problems/api/overview-version-4).

Set `SPHERE_RUNTIME_PROFILES_JSON` as a **single-line JSON object**. Shape example
only: replace every numeric `0` and version-name placeholder with the actual
positive IDs/names from your account. The zero IDs deliberately cannot pass validation.

```dotenv
SPHERE_RUNTIME_PROFILES_JSON='{"python":{"compiler_id":0,"version_id":0,"version_name":"ACCOUNT_VERSION_NAME","runtime_label":"3.12"},"javascript":{"compiler_id":0,"version_id":0,"version_name":"ACCOUNT_VERSION_NAME","runtime_label":"22"},"java":{"compiler_id":0,"version_id":0,"version_name":"ACCOUNT_VERSION_NAME","runtime_label":"21"},"cpp":{"compiler_id":0,"version_id":0,"version_name":"ACCOUNT_VERSION_NAME","runtime_label":"C++20"}}'
```

In a GCP environment-variable field, paste the raw JSON object **without the
outer dotenv single quotes**. Do not add C/C17: this milestone supports the four
approved languages. If a required runtime is absent, keep publication blocked
and resolve the provider/runtime mismatch with engineering.

## 6. Configure Google Cloud identity, SQL images and jobs

### 6.1 Select the existing project and enable required APIs

Use the actual existing GenHire project and `europe-west1`. Do not infer project
ID from the backend URL's project number. You need access to billing, API
enablement, Artifact Registry, Cloud Run, IAM, Storage and the relevant secrets.

```powershell
gcloud auth login
gcloud config set project PROJECT_ID
gcloud services enable run.googleapis.com artifactregistry.googleapis.com storage.googleapis.com secretmanager.googleapis.com iamcredentials.googleapis.com billingbudgets.googleapis.com --project PROJECT_ID
```

For local builds below, Docker performs the builds. If your team chooses Cloud
Build instead, enable/configure it separately. Do not grant project Owner to
runtime accounts to work around a permission error.

### 6.2 Build the two SQL images

Create a Docker Artifact Registry repository in europe-west1, or select an
existing suitable repository. The following creates one **only if needed**:

```powershell
gcloud artifacts repositories create REPOSITORY --repository-format=docker --location=europe-west1 --project=PROJECT_ID
gcloud auth configure-docker europe-west1-docker.pkg.dev
Set-Location D:\Projects\GenHire
docker build --platform linux/amd64 -f infra/oa_sql/Dockerfile.postgresql -t europe-west1-docker.pkg.dev/PROJECT_ID/REPOSITORY/oa-postgresql:review1 infra/oa_sql
docker build --platform linux/amd64 -f infra/oa_sql/Dockerfile.mysql -t europe-west1-docker.pkg.dev/PROJECT_ID/REPOSITORY/oa-mysql:review1 infra/oa_sql
docker push europe-west1-docker.pkg.dev/PROJECT_ID/REPOSITORY/oa-postgresql:review1
docker push europe-west1-docker.pkg.dev/PROJECT_ID/REPOSITORY/oa-mysql:review1
```

Inspect Artifact Registry for the pushed image **digests**, scan/review the
images and record each full `.../IMAGE@sha256:...` reference. Terraform rejects
tag-only image references. Read the existing Dockerfiles/runner before approving
them; build success alone does not prove SQL isolation. Official image-push
reference: [Artifact Registry](https://cloud.google.com/artifact-registry/docs/docker/pushing-and-pulling).

### 6.3 Plan and provision the repository's SQL Terraform

In a private tfvars file outside Git, supply:

```hcl
project_id              = "PROJECT_ID"
billing_account         = "YOUR_BILLING_ACCOUNT_ID"
backend_service_account = "BACKEND_SA_EMAIL"
artifact_bucket         = "YOUR_GLOBALLY_UNIQUE_PRIVATE_SQL_BUCKET"
postgresql_image        = "europe-west1-docker.pkg.dev/PROJECT_ID/REPOSITORY/oa-postgresql@sha256:ACTUAL_DIGEST"
mysql_image             = "europe-west1-docker.pkg.dev/PROJECT_ID/REPOSITORY/oa-mysql@sha256:ACTUAL_DIGEST"
budget_currency         = "USD"
budget_units            = "10"
```

The digest placeholders are intentionally invalid. If your billing currency is
INR, use its actual currency code and an approved current USD-10 equivalent;
do not configure a budget of INR 10 by copying the dollar value. Review the
actual billing-account currency and target before applying.

```powershell
terraform -chdir=infra/oa_sql init
terraform -chdir=infra/oa_sql validate
terraform -chdir=infra/oa_sql plan -var-file=C:/PRIVATE_PATH/oa-sql.tfvars -out=C:/PRIVATE_PATH/oa-sql.tfplan
```

Review the plan with your GCP/IaC operator. Check IAM scope, private bucket,
one-day SQL object lifecycle, image digests, job identities/resources, budget
filter/recipients and that no existing unrelated resource will be replaced.
Resolve any provider/schema/validation error in engineering; do not bypass it.
Only after approving the concrete plan:

```powershell
terraform -chdir=infra/oa_sql apply C:/PRIVATE_PATH/oa-sql.tfplan
terraform -chdir=infra/oa_sql output
```

Secure Terraform state/plans/tfvars; do not commit them. This template creates
`genhire-oa-sql-postgresql`, `genhire-oa-sql-mysql`, a SQL runner service account,
private artifact bucket, scoped IAM and an alerts-only budget. It does **not**
deploy your Flask API, durable OA workers, Redis, Vercel, detector models or installer.
The SQL runner account is different from the API/worker account.

### 6.4 IAM and backend values

The template's configured backend identity gets access to the two SQL jobs and
artifact bucket. If workers use another identity, grant that identity the same
necessary job-specific execution/override and artifact permissions explicitly.
The local impersonated identity needs them too. Do not grant those rights to
the browser or candidate accounts. Confirm same-project images can be pulled by
Cloud Run; cross-project registries need additional deliberate IAM.

```dotenv
GENHIRE_SQL_PROJECT=PROJECT_ID
GENHIRE_SQL_REGION=europe-west1
GENHIRE_SQL_ARTIFACT_BUCKET=YOUR_PRIVATE_SQL_BUCKET
GENHIRE_SQL_POSTGRESQL_JOB=genhire-oa-sql-postgresql
GENHIRE_SQL_MYSQL_JOB=genhire-oa-sql-mysql
GENHIRE_SQL_MONTHLY_EXECUTION_LIMIT=200
GENHIRE_SQL_MAX_CONCURRENT_EXECUTIONS=1
GENHIRE_SQL_TASK_TIMEOUT_SECONDS=60
GENHIRE_SQL_MONTHLY_BUDGET_USD=10
GENHIRE_SPHERE_MONTHLY_SUBMISSION_LIMIT=500
```

The application currently caps SQL at 200 dispatches/month, globally one active
SQL execution, and a 60-second task timeout; Sphere is capped at 500 submissions/
month. Some are hard pilot constraints, not values you can raise arbitrarily by
editing `.env`. See step 16 before planning continuous production traffic.

### 6.5 Local Application Default Credentials versus Cloud Run

`gcloud auth login` configures CLI access, **not automatically Python SDK ADC**.
For local SDK access, arrange a dedicated approved service-account identity and
the necessary impersonation permission, then:

```powershell
gcloud auth application-default login --impersonate-service-account=YOUR_LOCAL_TEST_SA_EMAIL
gcloud auth application-default set-quota-project PROJECT_ID
```

Use an identity with only the nonproduction resources it needs. Follow
[Google's impersonation/ADC guide](https://cloud.google.com/docs/authentication/use-service-account-impersonation).
Remove stale nonempty credential-file overrides from your local configuration
when using ADC. Existing dummy paths take precedence and break authentication.
If using a local key file instead, keep it private, uncommitted and never package
it in an installer/image; use the existing supported credential fields.

On Cloud Run, attach the correct runtime service account and use its ADC.
**Omit** `GOOGLE_APPLICATION_CREDENTIALS`,
`GOOGLE_APPLICATION_CREDENTIALS_JSON`, `GCS_SERVICE_ACCOUNT_KEY` and
`GCS_SERVICE_ACCOUNT_JSON` overrides there when using attached identity. Never
paste `C:\Users\...` or the template's `path/to/service-account.json` into GCP.

## 7. Configure AI, private evidence storage, email and payments

### AI generation and advice

- [ ] Confirm at least one supported provider in the existing fallback service
  has funded credentials and an available structured-output text model.
- [ ] Keep the current `LLM_PROVIDER_PRIORITY`, `LLM_DEEPSEEK_MODEL`,
  `LLM_GEMINI_MODEL`, `LLM_GROQ_MODEL` aligned with actual provider access.
  Model names in old examples are not proof of current account availability.
- [ ] Configure the corresponding `DEEPSEEK_API_KEY`, `GOOGLE_API_KEY` and/or
  `GROQ_API_KEY` on the backend and authoring/practice workers, never Vercel.
- [ ] Review generated role questions, answers, hidden cases, difficulty and
  educational explanations. An AI critic agreeing with a generator is not proof
  of factual correctness. Recruitment publication still needs human review.

OA uses the existing LLM fallback service; you do not need to introduce a new
OpenAI account or standalone “OA AI key.” Manual recruitment authoring can avoid
AI calls, but coding/SQL reference validation still needs the judge infrastructure.
Mock OA generation needs AI; it is not a static question bank fallback.

### Evidence GCS and signing

- [ ] Configure `GCS_BUCKET_NAME` to the private application artifact/evidence
  bucket. OA camera objects use `oa-evidence/`. This is **separate** from
  `GENHIRE_SQL_ARTIFACT_BUCKET`, whose one-day lifecycle is for SQL artifacts.
- [ ] Give the API/media/retention identities object upload/read/delete rights
  on the intended bucket/prefixes. Keep public access blocked.
- [ ] Configure signed-URL capability (`iam.serviceAccounts.signBlob`) on the
  signing service-account resource with your IAM operator; the ADC identity
  must support service-account signing. A plain local user ADC identity may
  upload successfully yet fail the signed review-link flow.
- [ ] Verify upload, authorized five-minute reviewer URL, denied anonymous raw
  read, retention deletion, retry after failed deletion and preservation holds.
- [ ] Provision/test the actual detector artifact from the existing proctoring
  model setup, including gitignored `models/proctoring/yolov8n.onnx` or the
  configured `PROCTORING_OBJECT_MODEL_PATH`. Missing analysis stays unknown.

Do not apply a one-day bucket-wide lifecycle to application evidence. OA's
reasoned holds and separate raw/summary retention require the retention worker;
a storage rule must not silently defeat a preservation hold. Camera tiers are
sampled images, not continuous video/audio/screen recording.

### Email and wallet/payment readiness

Preserve your existing verified mail provider; for current ZeptoMail settings,
confirm `EMAIL_PROVIDER`, `ZEPTOMAIL_API_KEY`, `ZEPTOMAIL_FROM_EMAIL` and
`ZEPTOMAIL_FROM_NAME`. Verify domain/sender and delivery using approved test
recipients. Start with `GENHIRE_HIRING_EMAILS_ENABLED=false`. Email-provider
failure must not be recorded as successful delivery; unknown sends require
operator evidence, not blind retries.

Use local/staging test wallet funding and the existing payment test-mode flow
for billing rehearsal. Keep Razorpay key pairs/webhook/return URLs in the correct
environment. No new payment gateway is required for OA. Never use test data to
credit real production wallets or mix test/live gateway credentials. Verify
exactly one hold/capture/refund in the OA ledger before selling assessments.

## 8. Add the complete OA settings block — start disabled

Merge the following additional settings with the provider/SQL values above.
Use the same names in local backend config, production reference and GCP
API/worker environments. These are server variables; **none goes into Vercel**.

```dotenv
GENHIRE_WORKFLOW_ENABLED=false
GENHIRE_ASSESSMENT_EXECUTION_ENABLED=false
GENHIRE_ASSESSMENT_GENERATION_ENABLED=false
GENHIRE_SCHEDULING_ENABLED=false
GENHIRE_HIRING_EMAILS_ENABLED=false
GENHIRE_OA_RUNTIME_ENABLED=false
GENHIRE_OA_EVALUATION_ENABLED=false
GENHIRE_OA_EVALUATION_ACCEPTED=false
GENHIRE_OA_SECURITY_ACCEPTED=false
GENHIRE_OA_INTEGRITY_ENABLED=false
GENHIRE_COMPANY_HIRING_ENABLED=false
GENHIRE_MOCK_OA_ENABLED=false
GENHIRE_MOCK_OA_CONTENT_ACCEPTED=false
GENHIRE_OA_MEDIA_ENABLED=false
GENHIRE_OA_MEDIA_ACCEPTED=false
GENHIRE_OA_VARIANTS_ENABLED=false
GENHIRE_OA_SIMILARITY_ENABLED=false
GENHIRE_EXECUTOR_ISOLATION_POLICY_ID=
GENHIRE_OA_KIOSK_RELEASE_ID=1.3.0
GENHIRE_OA_EXECUTION_CONCURRENCY=2
GENHIRE_OA_EXECUTION_QUEUE_LIMIT=1000
GENHIRE_OA_GRADING_CASE_LIMIT=200
GENHIRE_OA_RAW_RETENTION_DAYS=30
GENHIRE_OA_SUMMARY_RETENTION_DAYS=180
GENHIRE_OA_JOB_SETUP_CREDITS=30
GENHIRE_OA_ATTEMPT_CREDITS=30
GENHIRE_MOCK_OA_CREDITS=30
GENHIRE_OA_REGENERATION_CREDITS=10
GENHIRE_CAMERA_PROCTORING_CREDITS=10
GENHIRE_DUAL_PROCTORING_CREDITS=10
GENHIRE_ADVANCED_OA_ANALYTICS_CREDITS=10
GENHIRE_EXTRA_VARIANTS_CREDITS=10
GENHIRE_PLAGIARISM_CHECK_CREDITS=10
```

**Your price decision:** the owner's request to fill defaults set a provisional
`GENHIRE_OA_ATTEMPT_CREDITS=30`. Review/change this nonnegative integer price
before activating recruitment OA. Blank still means
unknown and blocks dependent paid recruitment activation. Do not copy the
5-credit fixture price from tests. Set zero only if you deliberately approve
free attempts. All prices are wallet credits, not INR/USD vendor prices.

Setup, accepted recruitment attempt, mock purchase, regeneration, extra variant
batch and post-evaluation similarity are different billing units. Basic mock
advice is included; no separate charge is introduced here. Configuring an
analytics price does not make deferred advanced analytics available. Do not
turn on or sell unimplemented analytics, descriptive answer grading, C17,
AI authorship detection or practice similarity.

Treat price changes as prospective: restart affected processes, obtain a fresh
quote and use the supported versioned configuration flow. Existing accepted
attempts, invoices/ledger entries and pinned invitation prices must not be
rewritten to match a newly edited `.env` value. Qualification minimums belong
in each job's reviewed policy, not in a newly invented global env threshold.

## 9. Bring up frontend and continuous workers locally

Local frontend config, merged into `react-frontend/.env`:

```dotenv
REACT_APP_API_URL=http://localhost:5000
REACT_APP_API_BASE=http://localhost:5000/api
REACT_APP_FRONTEND_URL=http://localhost:3000
REACT_APP_GOOGLE_CLIENT_ID=YOUR_MATCHING_PUBLIC_GOOGLE_WEB_CLIENT_ID
REACT_APP_TOKEN_KEY=genhire-token
REACT_APP_USER_KEY=genhire-user
REACT_APP_KIOSK_DOWNLOAD_URL=YOUR_TESTED_WINDOWS_INSTALLER_HTTPS_URL
REACT_APP_KIOSK_MAC_DOWNLOAD_URL=
```

`REACT_APP_API_BASE` takes precedence over `REACT_APP_API_URL`; keep them aligned
and avoid `/api/api`. Use the backend's same public OAuth client ID and allow
the local frontend origin in the OAuth console. Keep session-storage key names
aligned with existing users unless deliberately invalidating local login state.

```powershell
Set-Location D:\Projects\GenHire\react-frontend
npm.cmd ci
npm.cmd run dev
```

For each worker below, open an additional terminal in `python-backend`, activate
the same environment and run the listed command. Workers use the **same local
DB/settings as your local API**. Start them after baseline/provider configuration;
keep the authoring worker stopped during initial live executor acceptance.

| Worker | Command from `python-backend` | What stops working if absent |
|---|---|---|
| Scheduling/notifications | `python scripts/workers/hiring_scheduler_worker.py` | Automatic cohort progression, due schedules and notification delivery processing |
| Authoring/validation | `python scripts/workers/assessment_authoring_worker.py` | AI content jobs, validation jobs and compensation drain |
| Runtime | `python scripts/workers/assessment_runtime_worker.py` | Deadline sweep/public Run processing; server still refuses late edits |
| Evaluation/execution | `python scripts/workers/assessment_evaluation_worker.py` | Objective final grading and shared execution dispatcher |
| Retention | `python scripts/workers/assessment_retention_worker.py` | Raw/summary evidence cleanup |
| Company communications | `python scripts/workers/company_communications_worker.py` | Approved company email batches |
| Mock generation/advice | `python scripts/workers/practice_assessment_worker.py` | Purchased practice generation, advice and ready-entry expiry processing |

These processes can stay idle behind disabled flags. Each supports `--once` for
one operator tick; **one tick is not a continuously running service**. Depending
on settings/data, ticks can dispatch paid AI/judge/mail or mutate records. Do not
use production `--once` commands as harmless diagnostic probes.

## 10. Build and test the Secure Browser before accepting candidates

- [ ] On a suitable Windows build machine, install kiosk dependencies and build:

```powershell
Set-Location D:\Projects\GenHire\secure-browser-kiosk
npm.cmd ci
npm.cmd run dist:win
```

The build script rebuilds the kiosk UI. The web production build reads its
public frontend environment; the kiosk config does not inject those variables
and receives its API origin through a scoped launch. Test both production
launch/return URLs and installer links; do not distribute a localhost launch.

- [ ] Test the generated installer in `secure-browser-kiosk/dist`, custom
  `secure-interview` protocol launch, OA scoped session, save/resume/submit, Monaco
  worker, internal clipboard rules, emergency exit and permitted accessibility.
- [ ] Confirm runtime release actually reports **1.3.0**, matching
  `GENHIRE_OA_KIOSK_RELEASE_ID`; if you deliberately release another version,
  update package/runtime/release configuration consistently and retest.
- [ ] Arrange production code signing; on macOS, build/sign/notarize on a
  suitable Mac. Keep the Mac download variable empty until a working Mac
  installer is available. A Windows executable is not a Mac release.
- [ ] Upload the reviewed installer to a public **download** location and set
  `REACT_APP_KIOSK_DOWNLOAD_URL` to its actual HTTPS URL, preferably a versioned
  path. The existing fallback `Genhire.exe` URL does not prove that its bytes are
  the new OA build. Do not make the private evidence/SQL bucket public.

For dual-camera testing, a phone's `localhost` is the phone, not your PC. Use a
reachable trusted HTTPS staging frontend/API. Plain LAN HTTP is insufficient
for the required secure-context/device/native URL policy. Test real permission
denial, disconnection, pairing expiry and browser/camera waivers. Client-reported
release/kiosk activity is not cryptographic native attestation.

## 11. Run real executor acceptance in a deliberately selected test environment

This step consumes paid provider quota and writes acceptance records to the
selected Mongo database. Do not run against production accidentally. Stop the
authoring worker during initial acceptance; do not have another operator start
a competing preflight on the same environment/profile.

1. Complete actual sandbox/image/isolation security tests with a qualified
   engineer, including file/network/role escape, output bounds and crash recovery.
   Terraform source and an image scan alone do not establish these properties.
2. Choose `GENHIRE_EXECUTOR_ISOLATION_POLICY_ID`, e.g. your internally approved
   versioned review identifier. Record image digests, account sandbox policy,
   runtime pins and private evidence references.
3. Create a private JSON file outside Git with the shape below. Initially keep
   the booleans false; set each true **only after its actual review/test passes**.

```json
{
  "policy_id": "YOUR_REVIEWED_POLICY_ID",
  "reviewed_by": "YOUR_OPERATOR_IDENTIFIER",
  "evidence_reference": "YOUR_PRIVATE_REVIEW_REPORT_ID",
  "reviewed_at": "ACTUAL_RECENT_ISO_TIMESTAMP_WITH_TIMEZONE",
  "code_network_denied": false,
  "code_filesystem_isolated": false,
  "code_hard_resource_limits": false,
  "sql_network_denied": false,
  "sql_file_access_denied": false,
  "sql_role_escape_denied": false,
  "sql_output_limit_verified": false,
  "sql_crash_recovery_verified": false,
  "images_scanned_and_digest_pinned": false
}
```

4. Confirm the correct database/providers/SQL jobs, then temporarily set
   `GENHIRE_ASSESSMENT_EXECUTION_ENABLED=true` **in that environment**. Keep
   candidate runtime and acceptance flags false. The review policy ID must match;
   its timestamp must be timezone-aware and no older than seven days.
5. From an activated `python-backend` terminal:

```powershell
python scripts/admin/validate_assessment_executors.py --execute-live --security-review C:/PRIVATE_PATH/oa-security-review.json
```

6. Require a real `state: passed` result. It checks both catalogs, four languages,
   stdin/function contracts, wrong/timeout results, SQL fixtures/DDL denial/timeouts
   and the Problems reference-versus-wrong-answer path. It creates a private
   Sphere Problems canary; record IDs for later reviewed cleanup.
   A preliminary read-only quota check refuses an already impossible run with
   `preflight_budget_insufficient` before dispatch or attestation changes. Other
   traffic can still consume quota after that snapshot; it is not a reservation.
7. A pass writes a profile-bound Mongo attestation valid for **24 hours**. It is
   **not** a recruiter-credit charge. A failed recheck revokes the old acceptance.
   Unknown POSTs retain identity/capacity; reconcile provider/cloud records before
   retrying. Never manually insert a fake passed attestation to unblock publication.
8. Repeat genuine acceptance for each environment/database. Local Mongo evidence
   does not automatically populate staging/production. Changing image policy,
   endpoints, runtime pins or SQL configuration requires fresh acceptance.

Resolve step 16's renewal/quota conflict before treating this as a sustainable
always-on production approval. Do not enable an unattended daily cron yet.

## 12. Enable features in stages, with evidence

Apply changes to the API **and relevant workers**, then restart/redeploy those
processes. Environment flags do not synchronize between deployments. Start in
local/staging synthetic accounts, not the shared public production backend.

| Stage | Values to enable only when ready | Evidence before proceeding |
|---|---|---|
| Draft workflow/configuration | `GENHIRE_WORKFLOW_ENABLED=true` | Transactional DB, working auth, job-owner boundaries, pricing decisions; no legacy bulk migration |
| AI/manual authoring | `GENHIRE_ASSESSMENT_GENERATION_ENABLED=true` for AI; execution flag for real coding/SQL validation | AI credentials/quality, authoring worker, live executor acceptance for non-MCQ content, human review |
| Scheduling and grading preparation | `GENHIRE_SCHEDULING_ENABLED=true`, `GENHIRE_OA_EVALUATION_ENABLED=true` | Scheduler/runtime/evaluation workers healthy; dates/thresholds and failure/billing tests pass |
| Secure launch foundation | `GENHIRE_OA_INTEGRITY_ENABLED=true` | Tested scoped launch, consent, kiosk/accommodations and evidence policy |
| Candidate start | `GENHIRE_OA_EVALUATION_ACCEPTED=true`, `GENHIRE_OA_SECURITY_ACCEPTED=true`, then `GENHIRE_OA_RUNTIME_ENABLED=true` | Actual grading/security/device acceptance; accepted-start full duration and save/deadline behavior verified |
| Company results/rounds | `GENHIRE_COMPANY_HIRING_ENABLED=true` | Owner/admin scopes, integrity review, withheld/released reports, export and manual company stages verified |
| Mock purchases | `GENHIRE_MOCK_OA_CONTENT_ACCEPTED=true`, `GENHIRE_MOCK_OA_ENABLED=true` | Shared runtime ready, actual generated-content review, generation worker, ledger/compensation and teaching reports verified |
| Optional camera/dual | `GENHIRE_OA_MEDIA_ENABLED=true`, `GENHIRE_OA_MEDIA_ACCEPTED=true` | Private GCS/signing, detector coverage, actual desktop/phone tests and retention; choose monitoring in each OA |
| Optional extra variants | `GENHIRE_OA_VARIANTS_ENABLED=true` | Real reviewed published pool and allocation verified; pay/review extra generation explicitly |
| Optional recruitment similarity | `GENHIRE_OA_SIMILARITY_ENABLED=true` | Human-reviewed feature and quote tested; no automatic cheating verdict or grade change |
| Actual hiring/company email | `GENHIRE_HIRING_EMAILS_ENABLED=true` last | Verified sender, recipient/content previews, replay and unknown-delivery handling; communication workers running |

The accepted/security/content flags assert evidence, not technical capability.
Do not set them just to remove an unavailable message. Leave optional flags off
until you need and validate those features. MCQ-only work does not prove coding
or SQL is ready. Global flags are not a per-recruiter pilot allowlist: an engineer
must enforce private-cohort admission if enabling a shared public backend would
otherwise expose features beyond your chosen test accounts.

## 13. Run the local/staging owner acceptance checklist

- [ ] Create a verified recruiter and candidate test account through the existing
  account flow; fund only their intended test wallets.
- [ ] Create a **new test job** through the wizard. Choose template, manual/AI/hybrid
  content, separate interview/proctoring minimums, OA threshold and approved price.
- [ ] Review application/screening/OA dates and timezone. For a quick test, choose
  valid short windows in the UI; do not alter server clocks or database deadlines
  to bypass validation. Default OA entry is 24 hours; timely entry gets full duration.
- [ ] For the SDE journey, review/publish exactly 3 coding + 20 MCQ and inspect
  quote/capture. Then test SQL separately in **both** engines.
- [ ] Finish screening, verify manual-default “screening cleared,” approve one
  invitation, and separately verify explicit automatic invitation opt-in.
- [ ] Start in the installed Secure Browser; answer MCQ, run public/custom code,
  save, refresh/reconnect, submit, wait for actual worker grading and inspect ledger.
- [ ] Test one-second-before entry close/full duration, exact-close rejection,
  unanswered/incorrect answers and deadline submission.
- [ ] Review integrity, qualify/hold, release/revoke results, add a company technical/
  HR stage, export and record hired manually. Company interviews are conducted by
  the company; the platform does not invent a completed company interview.
- [ ] Buy one mock OA for the quoted price, complete it, verify exactly one capture,
  explanations and separately labeled AI advice. A feedback outage must not change marks.
- [ ] Test missing providers, stopped/restarted worker, unknown dispatch,
  cross-owner denial, verified platform failure and a single correct refund/release.
- [ ] Test product/business MCQ-only and screening-only jobs; old interview and
  candidate/recruiter/admin pages must still work.

Use [all seven representative journeys](oa_release_runbook.md) before release.
Automated test command, from repository root, using your existing official
`mongod` executable; replace the path if it differs:

```powershell
python-backend/venv/Scripts/python.exe python-backend/scripts/dev/run_workflow_integration.py --mongod .tmp/oa-step1-mongo/mongod.exe --combined --pattern 'test_*.py'
Set-Location react-frontend
npm.cmd run check:oa
Set-Location ..
node --test secure-browser-kiosk/tests/runtime-security.test.js secure-browser-kiosk/tests/media-permissions.test.js secure-browser-kiosk/tests/built-assets.test.js
```

Those automated suites use isolated/fake transports and do not replace the
actual provider/device checklist. Phone/kiosk accessibility requires real devices.

## 14. Deploy the backend and continuous workers on GCP

### API deployment

- [ ] Merge/review the OA code and obtain a passing hosted
  [OA CI workflow](../.github/workflows/oa-readiness.yml). Uncommitted local files
  will not arrive through a Git-based deployment.
- [ ] Complete the Python image-alignment decision in step 4. Build/deploy the
  reviewed backend revision using your existing deployment process.
- [ ] In Secret Manager, create/update private secrets for Mongo URI, Redis URL,
  signing keys and required AI/Sphere/mail/payment credentials. Preserve working
  secret references rather than importing blank examples.
- [ ] Give each runtime identity Secret Accessor on its required secrets. In
  **Cloud Run → backend service → Edit/deploy revision → Variables & Secrets**,
  map each secret to the exact environment variable name. Pin reviewed secret
  versions for reproducible releases. See
  [Cloud Run secret configuration](https://cloud.google.com/run/docs/configuring/services/secrets).
- [ ] Add all nonsecret OA config/provider endpoints/runtime JSON/SQL names/prices
  and retain flags off for initial deployment. Configure `FLASK_ENV=production`,
  `FORCE_HTTPS=true`, `FRONTEND_URL=FRONTEND_ORIGIN` and exact trusted
  `CORS_ORIGINS`. Use the intended production `DATABASE_NAME`.
- [ ] Keep credential-file overrides absent when using attached ADC. Check
  service identity, Mongo/Redis egress, startup health and baseline login first.
- [ ] Preserve the supported **one Gunicorn worker** and current screening routing
  constraints. Cloud Run adding replicas does not make process-local screening
  engines durable. Get an explicit session-routing design before horizontal scaling.

### Continuous workers — a separate deployment task

The seven scripts in step 9 have long-running loops and do not serve `$PORT`.
Do **not** deploy one as an ordinary HTTP Cloud Run service and expect it to
become healthy, or assume a one-off Cloud Run Job runs forever. An HTTP
keep-warm ping is not worker supervision.

Use a supervised existing always-on host, or configure Cloud Run **worker pools**
after reviewing availability and cost in europe-west1. Worker pools support
continuous background containers and use manually configured instance counts;
they are different from the two disposable SQL Jobs. Official references:
[worker pools](https://docs.cloud.google.com/run/docs/deploy-worker-pools),
[deployment CLI](https://docs.cloud.google.com/sdk/gcloud/reference/run/worker-pools/deploy).

For a worker-pool deployment, repeat for every required script:

1. Select the same reviewed backend image digest and working directory `/app`.
2. Override container command to `python`, and argument to its exact
   `scripts/workers/NAME_worker.py` path from step 9; omit `--once`.
3. Attach the intended service account, complete server config and Secret Manager
   references, with access to the same intended Mongo/Redis and relevant GCP resources.
4. Configure a nonzero supervised instance count, measured CPU/RAM and restart/
   alert handling. Seven separately allocated workers cost more than the SQL-only
   $10 target; consolidate on a supervised host only through an explicit process plan.
5. Verify queue progress and recovery after restart. Keep initial authoring stopped
   until executor acceptance is ready; keep email dispatch off during setup.

The repository currently has no complete deployment manifest/supervisor for
these seven continuous workers. You/your engineer must configure it; API and SQL
Terraform deployment alone do not finish this step. Ensure the chosen identities
get all necessary IAM; Terraform binds only its configured backend identity.

Reapply staged flags in step 12 only after staging evidence. API and workers
must use compatible code/config and current acceptance in the same database.

## 15. Deploy the frontend on Vercel

1. Open the intended Vercel project. Set **Root Directory = `react-frontend`** and
   framework Vite. The authoritative config is `react-frontend/vercel.json`:
   build `npm run build`, output **`build`**, SPA rewrites retained. Do not change
   output to `dist` just because this is Vite. Root-repository fallback config
   exists, but choose one consistent project-root strategy.
2. In project environment settings, set the public variables below. Use a
   staging API for Preview and production API for Production; do not expose a
   preview app to production wallets/DB unintentionally.

```dotenv
REACT_APP_API_URL=https://YOUR_BACKEND_ORIGIN
REACT_APP_API_BASE=https://YOUR_BACKEND_ORIGIN/api
REACT_APP_FRONTEND_URL=https://YOUR_FRONTEND_DOMAIN
REACT_APP_GOOGLE_CLIENT_ID=YOUR_MATCHING_PUBLIC_GOOGLE_WEB_CLIENT_ID
REACT_APP_TOKEN_KEY=genhire-token
REACT_APP_USER_KEY=genhire-user
REACT_APP_KIOSK_DOWNLOAD_URL=https://YOUR_PUBLIC_DOWNLOAD_HOST/YOUR_TESTED_INSTALLER.exe
REACT_APP_KIOSK_MAC_DOWNLOAD_URL=
```

3. Match backend `CORS_ORIGINS` and Google OAuth authorized JavaScript origins to
   each actual frontend domain. Origins have no `/api`, path or trailing slash.
   A changing Vercel preview URL is not automatically allowed by your backend.
4. Redeploy/rebuild after changing variables. Verify direct refresh of
   `/assessments/INVITATION_ID`, practice, login and recruiter pages hits the SPA
   correctly. Check browser network requests use the intended API with `/api` once.
5. Test the installer link returns the tested release and that native launch
   returns to the correct web origin. Check phone companion on real HTTPS devices.

Vercel hosts the frontend here; it does not run your Flask workers or SQL
containers. Backend OA flags belong in GCP. Every `REACT_APP_*` value is public.
Official references: [Vite deployment](https://vercel.com/docs/frameworks/frontend/vite),
[environment scopes/redeployment](https://vercel.com/docs/environment-variables).

## 16. Resolve the remaining production blockers with engineering

These require evidence or code/infrastructure work; they cannot all be solved
by you pasting credentials into `.env`.

| Pending item | What you explicitly need to arrange |
|---|---|
| **24-hour attestation versus monthly quotas** | Approve an operating design for renewal, security evidence freshness, quotas and cost. Do not bypass expiry or edit Mongo attestation dates. |
| **Continuous worker deployment** | A reviewed worker-pool/supervisor configuration, capacity, identities, secrets, restarts and monitoring; not supplied by the SQL Terraform. |
| **100-candidate start latency** | Actual staging HTTP/Redis/Mongo/provider load and tuning. Local p95 start was 18.5 seconds; this is not an acceptable-capacity certification. Agree a user-facing latency target before a real cohort. |
| **Real execution isolation** | Provider sandbox guarantees, image scans and actual escape/resource/recovery tests. Terraform alone does not establish egress isolation; add controls if the review finds a gap. |
| **Backend image validation** | Source now uses tested Python 3.12; build/scan/test and deploy the new image rather than assuming the running 3.11 image changed. |
| **Device/accessibility/storage** | Installed signed release, real desktop/phone/Monaco/permission tests, keyboard/screen-reader/zoom, accommodations, GCS signing/detector and cleanup. |
| **Private rollout admission** | Separate staging or an enforced production cohort boundary; global flags alone are not per-tenant access controls. |
| **Backup and restoration** | Real production backup/PITR restored into staging and a reconciliation/drain plan before any legacy adoption. |

### Why daily acceptance renewal is not currently a complete production plan

From the current canary definitions, a fully successful fresh preflight is
expected to dispatch **28 Sphere submissions and 12 SQL executions**, excluding
additional failures/retries and unrelated traffic. This is a source-derived
estimate, not a live bill: 16 correct coding contract/case/language executions,
8 wrong-output checks, 2 Python timeouts and 2 Problems submissions; both SQL
engines each run two datasets for correct, denied-DDL and timeout checks.

Daily runs for 30 days would consume roughly **840 Sphere + 360 SQL** calls,
already above the enforced **500 + 200 monthly caps**, before reference validation,
candidate grading or public Run. The security review timestamp also expires
after seven days; rerunning with a stale review is rejected. There is no completed
automatic renewal/reconciliation service supplied here.

For a short controlled test, perform genuine acceptance shortly before its
24-hour window and budget the canaries. For continuous production, have
engineering resolve/review the quota/renewal policy and cost envelope first.
Raising env values above the hard pilot caps will fail validation; weakening
acceptance without an approved redesign is not a setup instruction.

Judge quotas count **executions/cases**, not candidates. A 100-candidate SQL OA
with two datasets can consume 200 SQL dispatches from grading alone, leaving no
room under the present cap for reference validation/preflight/Run. Estimate:
reference validation sums languages × cases; final grading uses submitted
language × grading cases; public Run and renewed preflights add more. Get actual
account prices and measure before deciding wallet prices or promising volume.

Local/staging calls still use real paid external accounts. Test wallet credits
do not pay Sphere/GCP invoices. Separate Mongo databases have separate local
usage counters, so they do not jointly enforce a shared provider account's total
usage; track combined development/staging/production consumption or use explicitly
separated provider accounts and budgets.

## 17. Production acceptance, monitoring and rollback

- [ ] Verify hosted CI, the final deployed image and all seven staging journeys.
- [ ] Run 5, then 25, then the approved larger staging cohort with actual providers,
  recording resources, quota/cost, start/save/submit/result latency and failures.
- [ ] Check Cloud Billing budget exists, label filter is appropriate and alert
  recipients receive notifications at 50%, 80%, 100%. Check unlabelled registry/
  builds/logging/worker costs separately. Alerts are **not** a hard dollar cap.
- [ ] Add monitored worker liveness/restarts, request failure/latency, oldest queue,
  unknown execution/delivery, wallet drift and retention errors. The following
  read-only commands, from the intended backend environment, help inspect state:

```powershell
python scripts/admin/oa_operations_snapshot.py
python scripts/admin/audit_workflow_foundation.py --job-id YOUR_TEST_JOB_ID --owner-id YOUR_RECRUITER_ID --audience recruiter
```

The snapshot reports aggregates, not full health/SLO proof. An alert exit is a
request to inspect/recheck, not authorization to delete queue records or release
unknown slots. Do not log tokens, hidden fixtures, candidate code or camera frames.

### Existing jobs and migration

New test jobs are the safest first cohort. Existing legacy records do not all
need automatic conversion. Back up first; run the read-only legacy duplicate
audit with the intended environment explicitly selected, then preview one job:

```powershell
python scripts/migrations/migrate_hiring_workflows.py --job-id YOUR_JOB_ID
```

Review ambiguity/checkpoints and verify backup recovery. Only after explicitly
approving adoption of those particular records, use the existing CLI's
`--apply --actor-id VERIFIED_OWNER_OR_AUTHORIZED_ADMIN_ID`, optional `--after-id`
and bounded `--limit`. Do not apply to all production jobs as a generic install
step. Never infer missing historical outcomes or drop ledger/event history.

### Go-live and recovery

- [ ] Complete step 16 blockers and record an explicit release decision, named
  operator, cohort, flag changes, price/threshold policy, backup and code revision.
- [ ] Deploy backend/workers/frontend/installer in a compatible staged order;
  activate only the reviewed features/cohort. Test a real invitation/purchase
  immediately and reconcile its ledger/result before expanding.
- [ ] If stopping admission, disable new starts/purchases while retaining accepted
  saves, scoped refresh, deadlines, evaluation/polling/settlement and retention.
  Do not switch the whole workflow off or roll back to legacy writers over active
  managed records. Follow the full [drain/rollback runbook](oa_release_runbook.md).
- [ ] Keep unknown provider/email records for operator reconciliation. A stale
  backup must not overwrite newer submissions or wallet events.

## 18. Quick diagnosis when a feature is still unavailable

| Symptom | Check first |
|---|---|
| Draft OA missing/404 | `GENHIRE_WORKFLOW_ENABLED`, deployed source revision and verified recruiter ownership |
| Blank/unknown attempt price | Set the approved `GENHIRE_OA_ATTEMPT_CREDITS`, restart and obtain a fresh quote |
| `execution_not_configured` / runtime mismatch | Both account endpoints/tokens, raw JSON pins in both catalogs, exact runtime labels, SQL names/project/bucket |
| Live validation required after yesterday's success | Actual 24-hour attestation expiry/profile changes; genuine review and renewal/quota plan, not a bypass flag |
| Quota/monthly-limit error | All preflight/reference/public/final cases count; check actual monthly counters before retrying |
| `sql_capacity` / `dispatch_unknown` | A held active/unknown execution; reconcile actual terminal cloud/provider state before release |
| Generated OA stays queued | Authoring/practice worker deployment, matching DB/config, AI flags/keys/quota and unknown lease handling |
| Submitted forever/no usable grade | Evaluation and execution workers, current capabilities/acceptance, queue review/unknown state; do not invent score zero |
| Secure launch rejects old browser | Installed/runtime release, configured release ID, fresh grant and scoped preflight; do not forge readiness |
| Phone cannot join | Public trusted HTTPS frontend/API, real phone URL, fresh pairing and permissions; never the PC's localhost |
| Camera upload or reviewer URL fails | Application GCS bucket, attached/impersonated identity, object permissions, signing permission and detector availability |
| Browser CORS or HTML instead of JSON | Actual trusted origin, frontend API_BASE, `/api` exactly once, production build values and SPA rewrite |
| GCP SDK searches a Windows key path | Remove stale credential overrides from Cloud Run and use attached ADC; configure local ADC separately |
| GCP API healthy but nothing advances | Continuous workers absent/stopped, wrong database, flags inconsistent, or configured dates not yet due |
| No hiring email | Dispatch flag intentionally off, provider readiness, recipient-preview approval, company/scheduler worker and unknown-delivery state |
| Pricing changed in file but UI unchanged | Restart backend/workers, reload catalog/new quote; Vercel frontend variable changes require a build |

### Your completion log

Keep a private checklist with date/operator and nonsecret evidence references:

- [ ] Local baseline, separate transactional DB and all local processes verified.
- [ ] Sphere products/catalogs/judges/account isolation approved.
- [ ] SQL images/digests/jobs/IAM/budget tested in the selected environment.
- [ ] Actual executor acceptance passed; sustainable renewal/quota plan approved.
- [ ] AI quality, pricing/wallet/refund, private storage and signed installer verified.
- [ ] API, continuous workers, Vercel and public URLs deployed consistently.
- [ ] Staging journeys/accessibility/security/load/backup restore accepted.
- [ ] Explicit private-cohort production activation recorded; monitoring/drain owner assigned.

Completing configuration is progress; a box is complete only when its observable
check succeeds. Keep unresolved engineering/provider limitations visible instead
of marking flags accepted to make the UI appear available.
