# Environment configuration

Use the backend file for Cloud Run and the frontend file for Vercel. They contain
separate settings; frontend values are public in the built website.

For detailed Redis setup and the owner action checklist, start with
[Required setup and rate limiting](required-setup-and-rate-limits.md).

The [environment cleanup report](environment-cleanup.md) explains the current
grouping, removed settings, blank-value requirements and private removal record.
All four backend files have **178 settings in the same order**. The two Google
ADC overrides retain local values but stay empty in production, as documented
below. All four frontend files have the same **8 public settings in the same order**.
DeepSeek, Groq and Gemini keys are grouped with the other external API secrets;
model names and pricing estimates are separate. OpenAI and inactive Mailgun
credentials, plus redundant provider/model aliases, have been removed.

## Files and current endpoints

Each application has four files, with matching sections and per-setting comments:

| File | Purpose |
| --- | --- |
| `.env` | Private local development settings; existing values preserved. |
| `.env.example` | Local setup reference without working credentials. |
| `.env.production` | Private deployment settings with production URLs. |
| `.env.production.example` | Production reference without working credentials. |

The real files are gitignored. Examples intentionally have empty secrets or
replacement values and cannot be deployed as credentials.

| Service | Current value |
| --- | --- |
| Frontend | `https://genhire.in` |
| Additional allowed frontend origin | `https://gen-hire-gamma.vercel.app` |
| Backend origin | `https://hrtech-628047232128.europe-west1.run.app` |
| Frontend API base | Backend origin followed by `/api` |
| Local frontend/backend | `http://localhost:3000` / `http://localhost:5000` |

`CORS_ORIGINS` also retains `https://www.genhire.in`. An origin has a scheme and
host, with no path or trailing slash. Temporary Vercel deployment URLs are not
added automatically; explicitly allow an additional trusted preview origin if
needed. Google OAuth's authorized JavaScript origins must include the frontend
origins you actually use. Both apps use the same public OAuth client ID.

## Values still needed before production deployment

The audit of the existing private files found these missing values. No credentials
were invented, and validation prints setting names rather than secret values.

| Setting | Requirement |
| --- | --- |
| `REDIS_URL` | **Required for production startup.** Supply a reachable `redis://` or `rediss://` connection from your Redis service. Keep `RATE_LIMIT_REQUIRE_REDIS=true`. Private networking/TLS/authentication must match that service. |
| `DEEPSEEK_API_KEY` | Needed to use the configured primary provider. Without it, the DeepSeek route is unavailable; the configured Gemini/Groq fallbacks remain. |
| `RAZORPAY_WEBHOOK_SECRET` | Needed for verified webhook processing. Use the signing secret configured for this webhook, not the Razorpay API key secret. The old placeholder was not copied into production. |
| Object-detection artifact | The default local `models/proctoring/yolov8n.onnx` already exists. Include it in the deployed image; it is gitignored and a fresh clone does not contain it. An explicit model-path setting is optional when using the default location. |

Existing backend credentials were preserved or used to replace production
placeholders. Check that each account/key and the selected database/bucket is the
one you intend to use in production. The templates group authentication, email,
AI providers/models, speech, storage, identity/proctoring, payments, wallet rules,
rate limits/capacity, reporting and observability separately.

## Local backend startup

From Git Bash:

```bash
cd /d/Projects/GenHire/python-backend
python dev.py --check
python app.py
```

The launcher selects the complete Python 3.11/3.12 backend environment and waits
in the foreground on Windows. The current local `.env` sets
`GENHIRE_DEV_RELOAD=0`, so one backend process starts. Set it to `1` if you
explicitly want the development watcher. Stop the command with Ctrl+C before
starting another server on the same port. A port conflict now reports an
actionable error before database initialization.

Backend platform/shell variables take precedence over dotenv values. Production
loads `.env.production` when `FLASK_ENV=production`; `ENV_FILE`/`DOTENV_PATH` can
select a specific file. Cloud Run uses injected runtime settings because the
private dotenv files are excluded from the image. Frontend development reads
`.env`; production builds additionally use `.env.production` and platform build
variables. Avoid leaving production variables exported in a local shell.

## Validate before importing

From the repository root, with Python 3.11 or newer:

```bash
python scripts/check_environment.py --schema-only
python scripts/check_environment.py --profile local
python scripts/check_environment.py --profile production
```

The checker covers all eight files, duplicate assignments, key parity, production
URLs, OAuth agreement, required configuration, public frontend secret exclusion
and numeric rate/capacity settings. A production check currently fails until
`REDIS_URL` is supplied. Passing validation does not prove network access, account
permissions, available model quota, successful payments or physical device checks.

## Cloud Run import

Use **python-backend/.env.production** after resolving the required settings.
For your existing service, open its edit/redeploy configuration, then the container
**Variables & Secrets** section. Add a variable and paste the file into its
**Name** field; Cloud Run parses multiple assignments. Inspect the resulting
variables and revision diff before deploying. Keep existing secret references
when they already provide the matching value. The CLI also accepts an `.env` file
with `--env-vars-file`. These workflows are documented in
[Cloud Run environment variables](https://docs.cloud.google.com/run/docs/configuring/services/environment-variables).

Do not add `PORT`: Cloud Run supplies it. The two local Google ADC overrides,
`GOOGLE_APPLICATION_CREDENTIALS` and `GOOGLE_APPLICATION_CREDENTIALS_JSON`, are
present but intentionally empty in both backend production files. Empty values
allow the configured Google clients to use the Cloud Run runtime
service account for Google Standard TTS and enable its API/access. See
[Cloud Run service identity](https://docs.cloud.google.com/run/docs/configuring/services/service-identity).

Cloud Storage currently needs explicit signing credentials. The private production
file contains `GCS_SERVICE_ACCOUNT_JSON` from the existing local signing file;
its example contains no key. Prefer a Secret Manager reference for that variable
or a mounted key file under `GCS_SERVICE_ACCOUNT_KEY`. Do not deploy a local Windows
path. The decoded JSON must retain its private-key newlines; copying the entire
dotenv assignment through the import parser preserves escaping. If entering a
single value manually, use the decoded JSON, without dotenv's outer quote layer.
Never paste private credentials into chat or version control.

Retain one Gunicorn worker and at most one Cloud Run instance while interview
session state is process-local. Keep the existing deployment/build workflow; this
configuration work does not deploy a revision or provision a Redis service.
Also remove retired settings from the deployed service's existing variables and
secret references: pasting updated assignments may leave old keys in place.
Use the removal list in [environment cleanup](environment-cleanup.md).

## Vercel import

Use **react-frontend/.env.production** in the GenHire project's **Settings >
Environment Variables**, selecting **Production**. Import/paste the dotenv
assignments, check the API URLs and public OAuth client ID, then redeploy. Backend
provider keys, database URLs and signing secrets belong only on Cloud Run. Env
changes apply to subsequent deployments, as described by
[Vercel's configuration guide](https://vercel.com/docs/environment-variables/managing-environment-variables).

Build command: `npm run build`; output: `build/`; project root: `react-frontend`.
Changing token/user storage-key names signs existing users out; production keeps
its existing names. The installer download URL remains the configured public URL.
Publish the rebuilt `secure-browser-kiosk/dist/Genhire.exe` through the existing
release workflow before expecting candidates to download this build. The installer
was rebuilt locally and was not uploaded. A Mac installer URL remains optional;
it needs a separately built and published compatible Mac release.

The supplied production backend returned HTTP 503 from `/health` during this
audit; its URL is configured, but the remote service is not confirmed healthy.
No Cloud Run revision was changed and its runtime logs were not available.

After deployment, check backend `/health`, login, applications, job details,
first-time and returning secure-browser launch, a short practice interview, and
wallet/webhook processing in the appropriate environment.
