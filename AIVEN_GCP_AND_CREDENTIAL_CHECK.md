# Saved credential checks and GCP certificate setup

Verified on 22 October 2026, from this development machine. No secret values were displayed. Both `.env` and `.env.production` were tested as saved files; this does not test a deployed Cloud Run revision.

| Check | `.env` | `.env.production` |
|---|---|---|
| OnlineCompiler API authentication and Python execution | Passed | Passed |
| Native hidden-test verdict without output | Passed | Passed |
| SQLite execution and numeric aggregation | Passed | Passed |
| DuckDB execution and typed numeric aggregation | Passed | Passed |
| Certificate exists and parses as PEM | Passed | Passed |
| Aiven CA/hostname verification and TLS | Passed, TLS 1.3 | Passed, TLS 1.3 |
| Actual PostgreSQL version | 18.6 | 18.6 |
| Trusted reference validation against two independent datasets | Passed; rolled back | Passed; rolled back |

These checks used eight compiler runs in total. No application MongoDB connection, acceptance record, cloud deployment or cloud secret change was performed. The certificate paths were normalized to forward slashes in both files to satisfy the strict environment audit; they still resolve to the same files. Schema audit now passes. The only remaining required-field error is `GENHIRE_EXECUTOR_ISOLATION_POLICY_ID`. The local payment webhook secret also remains an unrelated notice.

## Where the isolation policy ID comes from

`GENHIRE_EXECUTOR_ISOLATION_POLICY_ID` is an internal GenHire field introduced with execution acceptance. It is not a vendor credential or a value to find in any provider console. You choose a stable identifier for the isolation policy you reviewed, for example:

```dotenv
GENHIRE_EXECUTOR_ISOLATION_POLICY_ID="genhire-onlinecompiler-isolation-v1"
```

Use that exact string as `policy_id` in the private security-review JSON described in [OA_FINAL_SETUP.md](OA_FINAL_SETUP.md#4-complete-live-codingsql-acceptance-before-candidate-release). Do not mark unverified review checks true. The identifier is not secret and can be a normal backend environment variable.

Once the review is complete, set the identifier in the intended environment and run:

```powershell
python-backend/venv/Scripts/python.exe python-backend/scripts/admin/validate_assessment_executors.py --execute-live --security-review C:/private/genhire/executor-review.json
```

This command uses the configured application database and consumes real compiler runs. Select the correct `ENV_FILE` for the intended environment before running it. The identifier alone does not enable candidate execution: the application also needs a successful, current profile-bound acceptance record. Records expire after 24 hours; credential/profile changes invalidate the previous record. The saved identifier was left blank because connectivity checks do not establish the completed isolation review.

## Store the Aiven CA in GCP

The CA **file contents** belong in Secret Manager. `AIVEN_POSTGRES_SSL_ROOT_CERT` remains a file path pointing to the mounted file. Your Windows path works locally; a Linux container needs its own path.

In your existing GCP project, enable Secret Manager if needed. Create `genhire-aiven-postgres-ca` and upload the existing `ca.pem` file as its value. Grant the intended Cloud Run runtime service account `roles/secretmanager.secretAccessor` on this secret. [Official secret creation instructions](https://docs.cloud.google.com/secret-manager/docs/creating-and-accessing-secrets).

On the Cloud Run workload that performs trusted validation:

1. Edit its configuration; choose **Mount volume → Secret**.
2. Select `genhire-aiven-postgres-ca`, version `1`, mount directory `/etc/secrets/aiven`, filename `ca.pem`.
3. Set the ordinary environment variable `AIVEN_POSTGRES_SSL_ROOT_CERT=/etc/secrets/aiven/ca.pem`.
4. Review the configuration diff and deploy when ready. Test TLS from that revision. Grant and mount Aiven credentials only where trusted validation runs. [Official Cloud Run instructions](https://docs.cloud.google.com/run/docs/configuring/services/secrets).

Equivalent update, after substituting your existing service/project/region, for later execution:

```powershell
gcloud run services update YOUR_VALIDATION_SERVICE --project YOUR_GCP_PROJECT --region YOUR_REGION --update-secrets "/etc/secrets/aiven/ca.pem=genhire-aiven-postgres-ca:1" --update-env-vars "AIVEN_POSTGRES_SSL_ROOT_CERT=/etc/secrets/aiven/ca.pem"
```

Keep `AIVEN_POSTGRES_URL` as a separate environment secret containing your database URI. Keep `AIVEN_POSTGRES_SSL_REQUIRED=true`, `AIVEN_POSTGRES_PURPOSE=question_validation` and `OA_POSTGRES_CANDIDATE_EXECUTION_ENABLED=false`.

The current Aiven integration is an explicit trusted validation CLI, not a candidate SQL endpoint. If validation runs only on your development machine, GCP does not need this CA mount yet. If you later use a Cloud Run Job for that CLI, configure the file secret on that Job instead; a service's mount is not shared automatically with jobs or workers. [Cloud Run Job secret configuration](https://docs.cloud.google.com/run/docs/configuring/jobs/secrets).

## Current functionality and next action

Direct compiler execution and trusted Aiven PostgreSQL validation work with your saved credentials. Candidate OA code/SQL execution remains gated by the blank policy ID and successful live acceptance. PostgreSQL candidate execution stays disabled; candidate SQL uses SQLite/DuckDB. Existing auth, MongoDB and payment configuration was not changed.

Complete the operator review, set its policy ID, run the acceptance command against the intended staging database, then verify the complete recruiter/candidate workflow. Cloud Run certificate mounting and runtime connectivity still need verification after your approved deployment. The GCP CLI is unavailable in this session, so no deployed configuration has been inspected or changed.
