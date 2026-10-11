# Backend startup and login recovery

Verified 11 October 2026. Follow this guide for the current production outage,
then use [Required setup and rate limits](required-setup-and-rate-limits.md)
for the remaining service setup.

## Confirmed cause

Cloud Run `hrtech` in project `hr-tech-2026`, region `europe-west1`, is running
revision `hrtech-00144-kz9`. The inspected container image is tagged `c53d179…`.
The supplied runtime logs show its Gunicorn worker failing in `core/factory.py`:

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
HTTP 403 for Cloud Build and Logging. Browser inspection also stopped because
the automation could not verify the browser URL. No production deployment was
performed from this workspace.

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
- Keep `GCS_SERVICE_ACCOUNT_KEY`, `GCS_SERVICE_ACCOUNT_JSON`,
  `GOOGLE_APPLICATION_CREDENTIALS`, and `GOOGLE_APPLICATION_CREDENTIALS_JSON`
  empty on Cloud Run when using this identity. Do not copy a Windows key-file
  path into the container. Local development retains its local credential file.
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
probe regressions; request-protection and environment validation tests. Empty
auth payloads were used to verify controlled 400 responses, not real user login.
The deployed service remains unverified until the updated image is deployed.
