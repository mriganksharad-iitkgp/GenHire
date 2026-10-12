# Backend startup and login recovery

13 October update: the interview instance exceeded 512 MiB. Memory is now 2 GiB on ready revision `hrtech-00160-j8z`; health and login preflight passed. See [Interview turn recovery](interview-turn-recovery.md) for the provider fix and remaining code deployment.

Updated 12 October 2026. Follow this guide for production recovery and verification,
then use [Required setup and rate limits](required-setup-and-rate-limits.md)
for the remaining service setup.

## Verified recovery: revision hrtech-00149-5dg

The deployed configuration was repaired from this workspace: the empty ordinary
`GOOGLE_APPLICATION_CREDENTIALS` variable was removed, and the TCP startup probe
was replaced with an HTTP `/health` probe. Image `879f473…`, the attached runtime
identity, and the Redis Secret Manager reference were preserved.

Cloud Run revision **`hrtech-00149-5dg`** is ready and serves **100% of traffic**.
Fresh public checks returned:

- `GET /health`: **200**, `status=healthy`, `database=connected`,
  `request_protection=available`.
- `OPTIONS /api/google-oauth`: **200**, with
  `Access-Control-Allow-Origin: https://genhire.in`.
- `POST /api/google-oauth` with an empty JSON object: controlled **400**,
  `Google token is required`, with the same allowed-origin header. This checks
  the real handler without using an account or a Google credential.

The latest warm checks took 2.59 seconds for health, 0.89 seconds for preflight
and 1.55 seconds for the empty auth request; these are observations, not a
cold-start performance guarantee.

The supplied recovery logs confirm GCS initializes and the HTTP startup probe
passes. The GCS exceptions at 02:04–02:07 belong to the earlier revision, not
the recovered deployment. The gRPC finalization message follows a shutdown
signal and does not contradict the successful readiness check.

Actual password/Google login and signed object access still require a user check;
these probes do not submit real user credentials. No frontend URL change is needed.

## Remaining timeout risk: duplicate wallet backfills during cold startup

Recovery logs expose a second issue in the existing image: startup spends about
90 seconds scanning existing accounts for signup bonuses, then about 108 seconds
initializing payments, which performs the same scan again. One cold request took
230 seconds; frontend authentication aborts after 20 seconds.

The workspace removes both blocking all-account scans. Registration already
grants bonuses for new local and Google accounts. Existing wallet balances and
the email/per-wallet bonus checks remain unchanged. Legacy catch-up is now an
explicit maintenance command, not HTTP startup work:

```powershell
# From python-backend; default is a read-only account count.
.\venv\Scripts\python.exe scripts/migrations/backfill_signup_bonuses.py
# Only for a database that actually needs the historical bonus backfill:
.\venv\Scripts\python.exe scripts/migrations/backfill_signup_bonuses.py --apply
```

The supplied production scan reported `Granted=0, skipped=91`; it does not need
another backfill. The command uses the selected backend environment/database;
do not run `--apply` against another database by accident.

**Next deployment:** review, commit and push the workspace fixes, then run
`genhire-main-deploy` on that updated commit. Revision `hrtech-00149-5dg` still
uses the original `879f473…` image: the blank-override guard and startup scan
removal are tested locally but are not yet in production. Recheck health,
preflight and actual login after deploying. Measure the next cold startup;
remaining SDK imports and database initialization still take time.

An optional Cloud Run minimum of one instance reduces scale-to-zero cold starts
but can add ongoing charges; it was not enabled as part of this recovery.
[Cloud Run startup guidance](https://docs.cloud.google.com/run/docs/tips/general).

## Resolved runtime blocker: blank Google credential-file override

Build `b48bbbb7-d4ed-4f21-9f0e-954fcf74aefa` succeeded and deployed image
`879f4738389c6253af9e30bae66b3ca0ec266e7c` to revision `hrtech-00148-667`.
The earlier deployment IAM problem is resolved. The new worker logs identify a
different startup failure:

```text
Failed to initialize Google Speech Service (features disabled): File  was not found.
GCS credentials unavailable (DefaultCredentialsError)
RuntimeError: Google Cloud Storage is not configured
```

The failed revision's ordinary variable `GOOGLE_APPLICATION_CREDENTIALS` existed with an
empty string value. The real `google-auth` SDK treats that as a configured file
path and raises before checking Cloud Run's metadata service. An empty assignment
is therefore different from an absent variable. The attached runtime account and
`GCS_BUCKET_NAME=genhireuploads` are present; Redis still has its secret reference.
Its reproduced public health and auth preflight responses were platform **503**,
plain `Service Unavailable`, without application CORS headers.

**Correction to the earlier instructions:** keep blank placeholders in the dotenv
profiles for matching schemas, but omit `GOOGLE_APPLICATION_CREDENTIALS` from
Cloud Run's deployed variables. Google recommends using the attached identity
without setting this override.
[Cloud Run environment guidance](https://docs.cloud.google.com/run/docs/configuring/services/environment-variables).

### Recovery command for recurrence (already applied)

The following Cloud Shell command removes only the empty SDK file override and
changes the startup probe from TCP to HTTP so a bound Gunicorn socket cannot
mark an uninitialized/crashed Flask worker healthy. Other environment variables,
the Redis secret reference, runtime identity and image remain in place:

```bash
gcloud run services update hrtech \
  --project=hr-tech-2026 \
  --region=europe-west1 \
  --remove-env-vars=GOOGLE_APPLICATION_CREDENTIALS \
  --startup-probe='httpGet.path=/health,httpGet.port=8080,initialDelaySeconds=0,periodSeconds=10,timeoutSeconds=10,failureThreshold=24'
```

Console alternative: **Cloud Run → hrtech → Edit & deploy new revision →
Variables & Secrets**, delete the ordinary `GOOGLE_APPLICATION_CREDENTIALS`
row entirely; do not leave an empty row. Keep the Redis secret mapping and
runtime account. Set the HTTP startup probe using section 3, then deploy.

The workspace also normalizes blank/whitespace Google credential overrides after
dotenv loading and before storage/speech client initialization. Nonblank local
file/JSON overrides are preserved, and invalid explicit paths still fail instead
of silently switching identities. Commit and deploy this source change to
prevent a future full-profile import from recreating the same startup failure.
Regression tests exercise actual Google credential-discovery logic with a mocked
metadata transport, rather than replacing `google.auth.default` itself.

After any future recovery, run section 4's health/preflight checks and test deployed login.
If the new HTTP startup probe fails, use the first traceback from the new
revision; successful image build/push alone still does not prove readiness.

## Resolved deployment blocker: missing service-account attachment permission

Build `2065955a-a72d-4c2d-832c-e89a22909d55` (source commit `879f473`) built
and pushed the Docker image successfully, then failed in the **Deploy** step:

```text
PERMISSION_DENIED: Permission 'iam.serviceaccounts.actAs' denied on service account
genhire-backend@hr-tech-2026.iam.gserviceaccount.com
This command is authenticated as genhire-backend@hr-tech-2026.iam.gserviceaccount.com
```

Cloud Build is deploying as `genhire-backend@hr-tech-2026.iam.gserviceaccount.com`;
Cloud Run also uses that account as its runtime identity. Deploying requires
permission to attach the runtime account, even when the deploying account and
runtime account are the same. `roles/iam.serviceAccountUser` supplies that
permission. Storage permissions, Secret Manager access and Service Account Token
Creator address different operations and do not replace it.
[Google service-account attachment permissions](https://docs.cloud.google.com/iam/docs/service-account-permissions).

Read-only inspection before the successful retry on 12 October confirmed:

- The target account exists and is enabled; its permission test did not grant
  `iam.serviceAccounts.actAs` or `iam.serviceAccounts.setIamPolicy` to itself.
- Cloud Run's latest ready/created revision is `hrtech-00146-665`, still using
  image `c53d179e487e9dc333db433135239069f7ce3c13`, rather than the new build.
- `REDIS_URL` still references Secret Manager `genhire-redis-url:latest`; it has
  not been replaced with an empty ordinary variable.
- The startup probe is still TCP-only. A ready revision in the control plane
  does not prove that the Flask worker or `/health` is healthy.

This permission failure occurs before the new application starts. Changing
dotenv values or CORS cannot resolve it. Local login can work while production
keeps serving an older image because local execution does not deploy to Cloud Run.

### Apply the scoped grant using your administrator account

Open **GCP Cloud Shell** while signed in as your human project administrator,
not as the backend service account. Check the active account first:

```bash
gcloud auth list --filter=status:ACTIVE --format='value(account)'
```

The selected account needs permission to update IAM policy on the target
service account (`iam.serviceAccounts.setIamPolicy`). Then run:

```bash
gcloud iam service-accounts add-iam-policy-binding \
  genhire-backend@hr-tech-2026.iam.gserviceaccount.com \
  --project=hr-tech-2026 \
  --member='serviceAccount:genhire-backend@hr-tech-2026.iam.gserviceaccount.com' \
  --role='roles/iam.serviceAccountUser' \
  --condition=None
```

The target is the **service-account resource**, and the member is the **Cloud
Build deployer identity**. This adds one scoped binding and preserves other
bindings. Repeating it is safe. A project-wide Owner/Editor grant is unnecessary.
[Command reference](https://docs.cloud.google.com/sdk/gcloud/reference/iam/service-accounts/add-iam-policy-binding).

Console alternative: **IAM & Admin → Service Accounts → genhire-backend →
Permissions / Manage access → Grant access**. Principal:
`genhire-backend@hr-tech-2026.iam.gserviceaccount.com`; role: **Service Account
User**. Grant it on this service-account resource, rather than granting another
Storage or Secret Manager role in the project's IAM page.

1. Allow a few minutes for IAM propagation.
2. Open the failed Cloud Build and choose **Retry build**, or run
   `genhire-main-deploy` on the current `main` branch. No source or environment
   change is required for this attachment-permission fix.
3. Check that **Deploy** succeeds and Cloud Run's new revision uses the image
   from that successful build, rather than `c53d179…`.
4. Follow sections 2–4 below to check the preserved secret, configure HTTP
   readiness and verify health/preflight/login. A later worker-startup error
   must be diagnosed from the new revision's logs separately.

If the grant command itself is denied, have a project IAM administrator apply
this exact binding. The locally available diagnostic service account cannot
change its IAM policy; the owner completed the IAM repair before the successful
build. The later configuration recovery was performed from this workspace.

For future maintenance, use separate build/deploy and runtime accounts. The
build/deploy account needs Service Account User **on** the runtime account;
the runtime account needs application access to Storage, speech and the Redis
secret. This separation is a later infrastructure change, not required to
recover the current trigger. If the trigger's execution identity changes,
grant the attachment role to that new deployer on the runtime account.

## Earlier application startup failure: old image requiring a GCS key

Before the successful retry, Cloud Run `hrtech` in project `hr-tech-2026`, region
`europe-west1`, was running the old `c53d179…` image. The supplied
11 October runtime logs for the earlier revision `hrtech-00144-kz9` show its
Gunicorn worker failing in `core/factory.py`:

```text
RuntimeError: Google Cloud Storage is not configured
(GCS_BUCKET_NAME + GOOGLE_APPLICATION_CREDENTIALS/GCS_SERVICE_ACCOUNT_KEY)
Reason: Worker failed to boot.
```

That image expects an explicit credential file/JSON, but the production
configuration now uses the attached Cloud Run service identity. ADC support was
added in commit `a089776`, after the running image's source commit. The failed
deployment did not replace the running image with that fix. Build/push success
alone does not prove the application starts.

Cloud Run returns 500/503 before Flask can handle requests. Those platform error
responses lack Flask's CORS headers, so the browser reports a preflight/CORS
failure. The inspected deployed `CORS_ORIGINS` already includes `https://genhire.in`.
Do not switch CORS to `*` to address this crash. The Google popup COOP warnings
and the gRPC finalization message are not the worker's boot failure.

A separate local Redis defect was reproduced: a connection succeeded in about
2.1 seconds with a five-second budget but timed out with the hardcoded 500ms
budget. The current source uses configurable, bounded connection/read timeouts
and disables automatic retries. Production still requires working Redis.

## 1. Deploy the current source, not the old image

1. Review and commit the source/example/documentation changes, then push them
   to the branch used by `genhire-main-deploy` (currently `main`). Private `.env`
   files and service-account JSON must remain untracked.
2. In GCP **Cloud Build → Triggers → genhire-main-deploy**, run a build of the
   updated branch. Confirm its Docker context is `python-backend` and it uses
   `python-backend/Dockerfile`. This deployment already uses a Docker image;
   switching hosting platforms is unnecessary.
3. Confirm the deploy step targets **hrtech / europe-west1 / hr-tech-2026** and
   uses the newly built image. Do not select the old `c53d179…` image or merely
   edit its variables and redeploy it.
4. If the deploy step fails, open **that build's Deploy step logs**. Fix the first
   exception reported there; repeated keep-warm requests cannot repair startup.

The diagnostic service account could read Cloud Run configuration but received
HTTP 403 for Cloud Build and IAM policy inspection on 12 October; earlier Logging
inspection also returned 403. No connected browser was available for this
inspection. No production IAM change was performed from this workspace. The
available Cloud Run update permission allowed the narrow configuration repair
described above; it did not rebuild or publish the uncommitted source changes.

## 2. Check the runtime identity and environment

In **Cloud Run → hrtech → Edit & deploy new revision**:

- Keep `GCS_BUCKET_NAME` set to the existing artifact bucket.
- Under **Security / Service account**, select the runtime service identity
  intended to access the bucket. Google client libraries use this identity
  through [Application Default Credentials](https://docs.cloud.google.com/run/docs/securing/service-identity).
- On that bucket, the runtime identity needs object read/create/delete access;
  `roles/storage.objectUser` is a suitable bucket-scoped role for these operations.
  For signed CV/JD links, also enable the IAM Service Account Credentials API
  and grant the runtime identity `iam.serviceAccounts.signBlob` on the signing
  service account, typically through `roles/iam.serviceAccountTokenCreator`.
  See [Google's signed URL permissions](https://docs.cloud.google.com/storage/docs/access-control/signing-urls-with-helpers).
- Keep `GCS_SERVICE_ACCOUNT_KEY` and `GCS_SERVICE_ACCOUNT_JSON` unconfigured
  when using the attached identity. Omit `GOOGLE_APPLICATION_CREDENTIALS` and
  `GOOGLE_APPLICATION_CREDENTIALS_JSON` from Cloud Run's deployed variables;
  an empty SDK file override breaks discovery in the previously deployed image.
  The dotenv profiles retain blanks for parity, and the updated source removes
  these blanks before Google client initialization. Do not copy a Windows
  key-file path into the container. Local development retains its credential file.
- Keep the existing `REDIS_URL` Secret Manager reference and confirm the runtime
  identity can access its selected version. The reference is already present in
  the deployed service; an empty local production file was not proof it was absent
  remotely. Keep `REDIS_URL=""` in the production file: the owner reports
  `genhire-redis-url:latest` is mapped to `REDIS_URL` in Cloud Run. Remove a
  conflicting ordinary variable when importing the file.
- Keep these non-secret settings:

  ```dotenv
  FLASK_ENV=production
  FRONTEND_URL=https://genhire.in
  CORS_ORIGINS=https://genhire.in,https://www.genhire.in,https://gen-hire-gamma.vercel.app
  RATE_LIMIT_REQUIRE_REDIS=true
  RATE_LIMIT_NAMESPACE=genhire-production
  REDIS_CONNECT_TIMEOUT_MS=5000
  REDIS_SOCKET_TIMEOUT_MS=2000
  ```

Both new timeout settings exist in all four backend dotenv files, in the same
order. Defaults are also applied in code when an existing deployment omits them.
Changing only environment variables cannot change the old hardcoded timeout.

The Redis password was shared in chat. Rotate it in Upstash, update the private local
backend profile and the Cloud Run secret version, then deploy the matching
revision. Do not put Redis credentials into the frontend environment.

## 3. Make deployment health reflect Flask readiness

The logs show the default TCP startup check passing as soon as Gunicorn binds
port 8080, before the worker crashes. Configure an **HTTP startup probe** in
Cloud Run **Containers → Health checks**:

| Field | Value |
| --- | --- |
| Type | Startup |
| Probe | HTTP |
| Path | `/health` |
| Port | `8080` |
| Initial delay | `0` seconds |
| Period | `10` seconds |
| Timeout | `10` seconds |
| Failure threshold | `24` |

This allows up to four minutes of startup checks. The current code exempts only
`/health` from the HTTPS redirect so the internal HTTP probe receives the actual
200/503 dependency result. Other routes retain HTTPS enforcement. Do not use a
redirect as proof of readiness. Keep one Gunicorn worker and at most one Cloud
Run instance while interview state is process-local.
[Cloud Run probe configuration](https://docs.cloud.google.com/run/docs/configuring/healthchecks).

## 4. Verify the rebuilt deployment

From PowerShell, use `curl.exe` rather than the older PowerShell `curl` alias:

```powershell
curl.exe --fail --max-time 90 "https://hrtech-628047232128.europe-west1.run.app/health"
curl.exe -i --max-time 90 -X OPTIONS "https://hrtech-628047232128.europe-west1.run.app/api/google-oauth" -H "Origin: https://genhire.in" -H "Access-Control-Request-Method: POST" -H "Access-Control-Request-Headers: content-type,authorization"
```

Expected: health HTTP **200** with `status=healthy`, `database=connected`, and
`request_protection=available`. Preflight should return **200** with
`Access-Control-Allow-Origin: https://genhire.in` and allow the requested headers.
Then test password login, Google sign-in, CV upload, and opening its signed link.
Health proves Mongo/Redis readiness, not bucket permissions or OAuth success.

The frontend backend URL is already correct; this outage does not require a
Vercel URL change or a frontend rebuild.

## 5. Run locally

In PowerShell, from the repository root:

```powershell
.\python-backend\venv\Scripts\python.exe scripts/check_environment.py --profile local
cd python-backend
.\venv\Scripts\python.exe scripts/check_rate_limit_setup.py --profile local
.\venv\Scripts\python.exe app.py
```

In Git Bash, from `python-backend`, use `./venv/Scripts/python.exe app.py`.
The project's Python 3.12 virtualenv is the verified interpreter. This machine's
other Python installation encountered an application-control/DLL import error;
use the established virtualenv rather than changing Windows security settings.
Keep local API URLs on port 5000 and frontend on port 3000. Stop a server you
started before launching another on the same port.

Verification performed: live Redis PING, Lua quota counter, expiry and 429;
local backend health and auth/preflight handling; storage ADC and HTTP health
probe regressions; request-protection and environment validation tests. The
latest focused run passed 48 backend tests and 13 environment-checker tests;
all dotenv profiles retain matching key order/count. New startup tests verify
HTTP readiness without historical account scans and maintenance bonus
idempotency, email reuse protection and invite-account exclusions. Empty
auth payloads were used to verify controlled 400 responses, not real user login.
Production revision `hrtech-00149-5dg` is verified for health and Google-auth
preflight. Real user login, bucket object permissions and the cold-start timing
of the pending source changes remain to be checked after their deployment.
