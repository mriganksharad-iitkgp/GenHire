# S2 Low migration and deployment

The implemented stack follows the explicit S2 Low request (the message also
mentioned S1, but specified S2 providers and prices).

| Work | Provider / model |
| --- | --- |
| Primary LLM | DeepSeek V4.1 Flash, API model **`deepseek-flash`** |
| First fallback | Gemini **`gemini-3.1-flash-lite`** |
| Second fallback | Groq **`openai/gpt-oss-20b`** |
| Speech to text | Groq **`whisper-large-v3-turbo`** |
| Text to speech | Google Cloud **Standard** voice, default `en-US-Standard-C` |

`openai/gpt-oss-20b` is hosted and billed by Groq. It does not require an
OpenAI API key. The OpenAI-compatible SDK is retained to call DeepSeek.

## Changes made

- Both LLM paths use this order: the shared scoring/evaluation/JD service and
  the real/practice interview engine. An explicit provider list is authoritative;
  a leftover OpenAI key does not add OpenAI to the chain.
- Interview clients use the same chat adapters as the rest of the app.
  Evaluation initialization no longer requires an OpenAI key. The practice
  controller no longer requires Groq merely to initialize its interview LLM.
- DeepSeek uses its own API base and key, with thinking disabled by default
  for interview latency and cost. Provider failures fall through to Gemini,
  then Groq; exhausted providers receive a cooldown.
- STT uses Groq's file transcription API with returned audio duration and a
  minimum of 10 billed seconds per request. Google credentials are still
  required for Standard TTS and existing mandatory Cloud Storage.
- The kiosk sends one complete recording per answer to the backend. Local
  audio-level detection handles silence pacing. Text appears after submission;
  Whisper is not a live interim-transcript service. The Google streaming token
  route returns 410 while S2 STT is active, so old kiosk installers must be updated.
- Kiosk TTS uses Standard voices only. Non-Standard voices are rejected by
  the backend so they cannot silently incur Journey/Neural2 rates.
- Kiosk version is 1.2.0; its unused Google SDK dependencies were removed.
- Admin Cost Statistics displays the configured chain, speech pricing,
  DeepSeek selected-timeline estimated cost in USD/INR, request/token/cache counts,
  unpriced request count, and live account balance in its returned currency.
- Successful provider requests write to MongoDB `ai_provider_requests`, including
  token counts, cache hits, timestamp, and snapshotted prices. These records
  contain no prompts, responses, API keys or uploaded documents. A timeline
  index is created at startup. Action summaries use the recorded JD model.
- Selected calendar days are interpreted in IST and converted to UTC for DB
  queries. Per-session speech costs retain each request's minimum billing.

## Environment files

`python-backend/.env` was updated while preserving existing secrets. There was
no local `.env.production`, so a **placeholder production reference** was created.
Do not deploy it without filling its placeholders or configuring the platform env.

Tracked references:

- `python-backend/.env.example`
- `python-backend/.env.production.example`
- `react-frontend/.env.example`
- `react-frontend/.env.production.example`

The corresponding real `.env` and `.env.production` files are gitignored.
GCP/Vercel environment variables override dotenv values. Committing an example
file does not update either deployment. The backend loads `.env.production`
when `FLASK_ENV=production` and still respects existing platform variables.

The frontend gets **no provider keys**: every `REACT_APP_*` value is embedded
in the browser bundle by the Vite configuration.

## What you need to do on GCP (Cloud Run)

1. Create/fund a DeepSeek API key. Open **Cloud Run → your backend service →
   Edit & deploy new revision → Variables & Secrets**. Add the provider keys
   through Secret Manager secret references exposed under `DEEPSEEK_API_KEY`,
   `GOOGLE_API_KEY` and `GROQ_API_KEY`. Grant the runtime service account
   Secret Manager Secret Accessor on these secrets. Keep or update `GOOGLE_API_KEY`
   (Gemini) and `GROQ_API_KEY` (STT and tertiary LLM). Confirm those accounts have
   model access and sufficient quota/billing.
2. Add/update these runtime environment variables in the same revision:

   ```dotenv
   FLASK_ENV=production
   DEEPSEEK_API_BASE=https://api.deepseek.com
   LLM_PROVIDER_PRIORITY=deepseek,gemini,groq
   LLM_PRIMARY_PROVIDER=deepseek
   LLM_SECONDARY_PROVIDER=gemini
   LLM_TERTIARY_PROVIDER=groq
   LLM_DEEPSEEK_MODEL=deepseek-flash
   INTERVIEW_LLM_MODEL=deepseek-flash
   DEEPSEEK_THINKING_MODE=disabled
   LLM_GEMINI_MODEL=gemini-3.1-flash-lite
   CV_SCORING_MODEL=gemini-3.1-flash-lite
   CV_PARSER_MODEL=gemini-3.1-flash-lite
   LLM_GROQ_MODEL=openai/gpt-oss-20b
   GROQ_CV_MODEL=openai/gpt-oss-20b
   FACE_MATCH_DEEPSEEK_MODEL=deepseek-flash
   FACE_MATCH_GEMINI_MODEL=gemini-3.1-flash-lite
   FACE_MATCH_GROQ_MODEL=
   STT_PROVIDER=groq
   GROQ_STT_MODEL=whisper-large-v3-turbo
   GOOGLE_TTS_VOICE=en-US-Standard-C
   DEEPSEEK_PRICING_MODE=peak
   DEEPSEEK_INPUT_USD_PER_1M=0.30
   DEEPSEEK_CACHED_INPUT_USD_PER_1M=0.006
   DEEPSEEK_OUTPUT_USD_PER_1M=1.20
   GEMINI_INPUT_USD_PER_1M=0.25
   GEMINI_OUTPUT_USD_PER_1M=1.50
   GROQ_INPUT_USD_PER_1M=0.075
   GROQ_OUTPUT_USD_PER_1M=0.30
   GROQ_STT_USD_PER_HOUR=0.04
   ```

   Remove the old `FACE_MATCH_GROQ_MODEL` value, or set it empty. GPT-OSS 20B
   cannot accept images, so identity images use DeepSeek then Gemini. A different
   Groq vision model is optional and would be a separate stack/cost choice.

3. Keep your existing MongoDB, JWT, payment, email, Cloud Storage and application
   secrets. Keep `INR_PER_USD` at your chosen reporting conversion rate.
   `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_CV_MODEL` and `LLM_OPENAI_MODEL`
   are not used by the S2 chain. You may keep OpenAI admin billing settings to
   report legacy spend, or unset them if you no longer want legacy billing queries.
4. Enable the Google Cloud **Text-to-Speech API**, with billing. The speech
   service now supports the runtime service account through Application Default
   Credentials, so TTS does not need a downloaded private key on Cloud Run.
   For this route, unset `GOOGLE_APPLICATION_CREDENTIALS` and
   `GOOGLE_APPLICATION_CREDENTIALS_JSON`, and select the intended service account
   in the revision's security settings. Confirm its Google API access.
   Existing explicit speech credentials remain supported if you retain them.

   **Retain your working Cloud Storage configuration.** The storage module still
   uses explicit signing credentials for signed URLs: keep `GCS_BUCKET_NAME`
   and `GCS_SERVICE_ACCOUNT_JSON` or `GCS_SERVICE_ACCOUNT_KEY`. If storage
   currently relies on `GOOGLE_APPLICATION_CREDENTIALS`, move that same secret
   file path to `GCS_SERVICE_ACCOUNT_KEY` before unsetting it for ADC. Store JSON
   keys in Secret Manager or mount a secret file; do not use a local Windows path.
5. Set `CORS_ORIGINS` and `FRONTEND_URL` to your actual Vercel/custom-domain
   frontend URL. Keep any other required origins. The production reference has
   `YOUR-FRONTEND` placeholders because no deployment URLs were supplied.
   Keep `PAYMENT_SUCCESS_URL` and `PAYMENT_CANCEL_URL` on your production
   frontend domain too.
6. Build/deploy the updated repository using your existing Cloud Build/Cloud Run
   pipeline, then deploy the revision with the updated runtime env/secrets.
   Set the new revision to receive traffic. Use the existing Python **3.11**
   Docker deployment. Provider adapters reuse dependencies already
   pinned in `python-backend/requirements.txt`; no DeepSeek-specific SDK is needed.
   The interview state is process-local: retain one Gunicorn worker and use
   a maximum of one Cloud Run instance until shared session state is implemented.
   `.env.production` is excluded from the Docker image by `.dockerignore`;
   configure runtime variables/secrets on Cloud Run rather than relying on it.

## What you need to do on Vercel

No AI provider keys or LLM model variables belong on Vercel.

Keep/update these public build values in the frontend project's Production env:

```dotenv
REACT_APP_API_URL=https://YOUR-BACKEND.run.app
REACT_APP_API_BASE=https://YOUR-BACKEND.run.app/api
REACT_APP_GOOGLE_CLIENT_ID=YOUR_EXISTING_OAUTH_CLIENT_ID
REACT_APP_KIOSK_DOWNLOAD_URL=YOUR_UPDATED_INSTALLER_URL
```

Use the same OAuth client ID as the backend. If the backend and installer URLs
did not change, keep the existing values. Redeploy the frontend to publish the
new admin UI and any changed public values. The existing build remains
`npm run build`, output directory `build/`.

## Kiosk release

Publish the newly built kiosk installer at your configured download URL, and
have candidates install/update it before their next interview. The previously
installed kiosk uses Google streaming STT and does not support this migration.

The Windows x64 version **1.2.0** installer was built successfully at
`secure-browser-kiosk/dist/Genhire.exe`, with its SHA256 checksum in
`Genhire.exe.sha256`. The packaged app was checked for the new transcription
handler and contains no `.env` or `credentials.json` files. The `dist/` folder
is gitignored: upload the installer itself through your release workflow.

To reproduce a Windows installer locally:

```powershell
cd secure-browser-kiosk
npm ci
npm run dist:win
```

Upload `secure-browser-kiosk/dist/Genhire.exe` through your existing download
hosting workflow. Then update `REACT_APP_KIOSK_DOWNLOAD_URL` if the URL changed.

## Interview workflow

1. Recruiter creates a job/JD. Candidate applies with a CV or opens an invite.
   AI CV scoring and JD generation use DeepSeek, Gemini, then Groq.
2. Candidate launches the secure browser (or the existing supported browser
   interview view). Session initialization loads trusted CV/JD data, starts
   proctoring/identity checks, and immediately returns the introduction question.
3. Google Standard TTS reads the question. Candidate speech is recorded.
   No speech for 30 seconds skips the answer; 10 seconds of silence after
   speech auto-submits. Manual Send Answer still works. In the kiosk, an audio
   transcription failure preserves the recording so Send Answer can retry.
4. Backend transcribes the answer with Groq Whisper Turbo, then evaluates and
   generates the next question using the LLM fallback chain. The session manager
   keeps the CV/JD context, phase, difficulty and progress. Empty/junk answers
   retain the existing deterministic low-score path.
5. Completion saves transcript/evaluation/usage and existing integrity signals
   for the recruiter. Practice interviews use the same configured providers.
   Wallet charging/refund rules remain as configured; infrastructure price
   estimates do not change subscription credit prices.

## How DeepSeek spend is reported

The documented DeepSeek API provides **current account balance** via
`GET /user/balance` using the ordinary DeepSeek key. It does not document an
OpenAI-style organization Costs API for an arbitrary date range. No
`DEEPSEEK_ADMIN_API_KEY` is needed or invented.

The admin timeline therefore sums **recorded request usage × snapshotted
configured rates**. Input cache hits have their own rate. Output counts include
any provider-reported reasoning tokens. Balance is displayed separately in
USD or CNY as returned; CNY is not mislabeled as USD.

Limitations:

- Tracking starts when this code is deployed. It cannot backfill prior
  DeepSeek calls, other apps' calls, or requests whose telemetry write failed.
- A call missing usage/pricing increments the unpriced count. The figure is
  an estimate, not an invoice, and does not account for grants/tax/free quota.
- `DEEPSEEK_PRICING_MODE=peak` is a conservative default. `off_peak` halves
  the configured peak rates. `auto` uses weekday UTC windows (01:00–04:00 and
  06:00–10:00). Auto does not have a Chinese public-holiday calendar; compare
  against the provider dashboard for invoice reconciliation.
- Current balance cannot establish past date-ranged spend, especially when
  top-ups/grants or other applications use the same account. It is cached for
  60 seconds and is independent of the admin timeline.
- The DeepSeek card is a provider reference excluded from infrastructure totals
  to avoid adding the same AI usage twice. The existing action/session AI lines
  remain usage estimates; mixed-provider sessions can differ from the precise
  per-provider request ledger.

The quoted `$0.0179 + $0.020 + $0.016 = $0.0539` is a workload planning
estimate, not a guaranteed interview fee. Model tariffs, tokens, speech
duration and cache hits determine the result. Prices were verified on
2026-10-05 and can be changed through the pricing env variables.

Official references:

- [DeepSeek model names and pricing](https://api-docs.deepseek.com/quick_start/pricing/)
- [DeepSeek current balance API](https://api-docs.deepseek.com/api/get-user-balance/)
- [Gemini 3.1 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite)
- [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Groq supported models and pricing](https://console.groq.com/docs/models)
- [Groq speech transcription and minimum billing](https://console.groq.com/docs/speech-to-text)
- [Google Cloud TTS pricing](https://cloud.google.com/text-to-speech/pricing)
- [Cloud Run secrets](https://docs.cloud.google.com/run/docs/configuring/services/secrets)
- [Cloud Run service identity and ADC](https://docs.cloud.google.com/run/docs/securing/service-identity)
- [Vercel environment variables and redeployment](https://vercel.com/docs/environment-variables/managing-environment-variables)

## Checks after deployment

1. Start a short practice interview: hear a Standard voice, speak, submit, and
   confirm the returned transcript and next question.
2. In Admin → Cost Statistics, select Today. Confirm DeepSeek requests/tokens
   and a nonzero USD estimate after a primary call, and a live balance/status.
   Expand the configured-chain table to confirm all three model IDs.
3. In a staging environment, temporarily remove only the DeepSeek key and
   restart: a text request should use Gemini. Remove Gemini too: it should use
   Groq. Restore both keys and restart. STT still needs Groq throughout.
4. Confirm that the new `ai_provider_requests` collection has the timeline
   index. No manual database migration/backfill command is required.

Local regression command (mocked APIs/DB, no live usage):

```powershell
python -m unittest discover -s python-backend/tests -v
```

Local verification passed: 30 backend regression tests on Python 3.11,
frontend production build, backend source syntax, kiosk JavaScript syntax,
and the Windows kiosk installer build.
Provider calls and MongoDB are mocked in these tests; live interview validation
requires your configured accounts after deployment.

The standalone FastAPI sample in `python-backend/cv_jd_processing/` is not
imported by the deployed Flask app and retains its independent legacy setup.
The deployed CV scoring path is `services/cv_scoring_service.py` and uses S2.
