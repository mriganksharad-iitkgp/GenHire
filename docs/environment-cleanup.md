# Environment cleanup and import checklist

Updated 10 October 2026 (IST). Configuration files were reorganized locally;
no Cloud Run or Vercel deployment was changed.

## Files to use

| Application | Local / local example | Production / production example |
| --- | --- | --- |
| Backend | 178 settings each | 178 settings each |
| Frontend | 8 public settings each | 8 public settings each |

All four files for each application have exactly the same keys and order.
Backend production includes `GOOGLE_APPLICATION_CREDENTIALS` and
`GOOGLE_APPLICATION_CREDENTIALS_JSON` as active, empty assignments: keep these
local Google authentication overrides empty on Cloud Run. The current Google
clients ignore empty overrides and use the attached service account for speech/billing,
and explicit `GCS_SERVICE_ACCOUNT_JSON` or a mounted signing file for signed URLs.
`PORT` is omitted because Cloud Run supplies it. Do not import a Windows file path.

The backend groups runtime URLs, MongoDB, authentication, external API keys,
Google storage credentials, email settings, AI models, speech, monitoring,
payments, wallet rules, Redis budgets, worker capacity, pricing and reporting.
Existing active private values were retained. Redis prefixes were separated into
`genhire-local` and `genhire-production`; neither profile had a Redis URL yet.
Example files contain no working secrets and disable tracing until configured.
The evaluation configuration now honors the tracing switch instead of forcing it on.

## Removed settings

The following 17 settings were removed from all four backend environment files.
Legacy implementation support remains in code; the selected chain is explicitly
DeepSeek, Gemini and Groq. Removing the credential prevents OpenAI live billing
requests; historical OpenAI reporting defaults to no live data/zero manual estimates.

| Settings | Reason |
| --- | --- |
| `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_CV_MODEL`, `LLM_OPENAI_MODEL`, `FACE_MATCH_OPENAI_MODEL` | OpenAI generation is not selected; `OPENAI_MODEL` has no source consumer. |
| `OPENAI_ADMIN_API_KEY`, `OPENAI_CREDIT_BALANCE_USD`, `INFRA_MONTHLY_OPENAI_INR` | Retired OpenAI billing credentials and manual estimates. |
| `MAILGUN_API_KEY`, `MAILGUN_DOMAIN`, `MAILGUN_FROM_EMAIL`, `MAILGUN_FROM_NAME` | All profiles select ZeptoMail; Mailgun is inactive. |
| `LLM_PRIMARY_PROVIDER`, `LLM_SECONDARY_PROVIDER`, `LLM_TERTIARY_PROVIDER` | `LLM_PROVIDER_PRIORITY` already overrides these aliases. |
| `CV_SCORING_MODEL`, `GROQ_CV_MODEL` | Canonical `LLM_GEMINI_MODEL`/`LLM_GROQ_MODEL` take precedence and had identical values. |

**Exact removed values, per file, are in the private local record:**
`python-backend/.private/environment-cleanup-2026-10-09.md`.
It is gitignored and excluded from Docker. Open it locally to review the values;
do not upload it or use it as deployment configuration.

The obsolete `payment_module/env.example` contained populated credentials and
duplicate settings. It now points to the canonical backend templates; its exact
previous contents are in that private record too. If the previously committed
payment credentials remain valid, rotate that key pair in Razorpay and update
the active private files and deployed secret references.

`LLM_GROQ_MODEL="openai/gpt-oss-20b"` is retained: this is hosted by Groq and uses
`GROQ_API_KEY`. It does not require an OpenAI credential. LangSmith credentials
are retained because tracing is enabled in the private configurations. Dynamic
`RATE_LIMIT_*` settings are active and retained even without literal source matches.

## Empty values and setup

| Setting | Action / intended behavior |
| --- | --- |
| `REDIS_URL` | Required for production boot. Create/connect managed Redis; follow sections 3–6 of [the service checklist](required-setup-and-rate-limits.md). Local blank uses bounded memory counters. |
| `DEEPSEEK_API_KEY` | Create/fund the key in the DeepSeek platform. Until then the primary route is unavailable; configured Gemini/Groq routes can fall back. |
| `RAZORPAY_WEBHOOK_SECRET` | Configure a Razorpay webhook targeting backend `/api/payment/webhooks/razorpay`; set its exact signing secret. Local placeholder values also need replacement. |
| `GCS_SERVICE_ACCOUNT_JSON` locally | Blank is intentional when the configured local ADC file supplies storage signing. Production already has signing JSON; examples deliberately do not. |
| `GCS_SERVICE_ACCOUNT_KEY` | Optional mounted-file alternative to signing JSON; blank is correct when another signing source is configured. |
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` locally | Optional inline alternative; blank uses the configured local Google credentials file. |
| `FACE_MATCH_GROQ_MODEL` | Optional separate image-capable Groq model; blank skips that vision route. GPT-OSS is text-only. |
| `PROCTORING_OBJECT_MODEL_PATH` | Blank uses the default local ONNX path. Include the gitignored model in the deployment image. |
| `GCP_BILLING_EXPORT_BQ_LOCATION` | Optional; blank permits dataset-location inference. |
| `SENTRY_DSN` | Optional; create a Sentry project and copy its DSN if external monitoring is wanted. |
| `REACT_APP_KIOSK_MAC_DOWNLOAD_URL` | Optional; build/publish a compatible Mac installer, then set its HTTPS URL. Blank hides the download. |

Comments next to every setting explain its purpose, units and requirements. Blank
example secrets must be filled with your own credentials; they are not evidence
that the corresponding private credentials are missing. Other outstanding owner
actions, including mobile recording and optional identity runtimes, remain in
[the main service checklist](required-setup-and-rate-limits.md).

## Import and verify

1. Run the configuration checks from the repository root:

   ```powershell
   python scripts/check_environment.py --schema-only
   python scripts/check_environment.py --profile local
   python scripts/check_environment.py --profile production
   ```

   Schema and local validation pass. Production still reports missing Redis;
   notices flag DeepSeek, webhook setup, mobile recording and model deployment.
   Validation does not confirm provider permissions, quota or network reachability.

2. **Cloud Run:** use the entire `python-backend/.env.production` after filling
   required values. In Containers → Variables & Secrets → Add Variable, paste
   the dotenv contents into the Name field and inspect the parsed variables.
   Preserve existing Secret Manager references when they supply the correct values;
   remove retired keys and conflicting plain entries explicitly. Keep the signing
   JSON as one escaped assignment; individual manual values use decoded JSON.
   [Cloud Run import documentation](https://docs.cloud.google.com/run/docs/configuring/services/environment-variables).

3. **Vercel:** import only `react-frontend/.env.production` into the frontend
   project's Production environment and rebuild. Its eight values are public;
   never upload the backend file to Vercel. Environment changes require redeployment.
   [Vercel configuration documentation](https://vercel.com/docs/environment-variables/managing-environment-variables).

4. Check deployed health, Redis enforcement, Google login, email delivery, a
   test payment/webhook and the interview flow using the main checklist and
   [smoke checklist](SMOKE_CHECKLIST.md).
