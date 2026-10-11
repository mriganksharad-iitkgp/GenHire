# Backend — Detailed Wiring

The backend is a single Flask application built by the app factory
`create_app()` in `python-backend/core/factory.py`. `python-backend/app.py` is
only a thin entrypoint: it calls `create_app()`, exposes `app` for
`gunicorn app:app`, and contains one piece of real logic — a guard that
suppresses the boot of Werkzeug's disposable reloader "watcher" process so
`python app.py` doesn't boot the app twice and run the background daemons
against the live DB twice.

The app serves a JSON REST API under `/api/*`, a Socket.IO WebSocket server on
the same port, and runs **three** background worker threads. It is started with
`socketio.run(app, host="0.0.0.0", port=$PORT|5000)` in development (or Gunicorn
via `gunicorn.conf.py` / `start_server.sh` / `Dockerfile` in deployment).

## Startup sequence (what `create_app()` does, in order)

1. **Environment & logging** — `core/bootstrap.py` (imported first) forces
   UTF-8 stdout and silences TensorFlow/MediaPipe logs; `.env` is loaded via
   `config/env_loader.load_environment()`.
2. **Sentry** — `sentry_sdk.init()` is called unconditionally; it no-ops unless
   `SENTRY_DSN` is set.
3. **Flask app config** — `SECRET_KEY` from `FLASK_SECRET_KEY` (refuses to boot in
   production without it), `MAX_CONTENT_LENGTH` = 16 MB.
4. **Security headers** — `Flask-Talisman` (if installed) with a CSP scoped to the
   API plus the GazeRecorder page; HTTPS redirect only when `FORCE_HTTPS=true`.
5. **Rate limiting** — `Flask-Limiter` (if installed). Development: effectively
   unlimited. Production defaults: `200/day, 50/hour` per IP. Uses `REDIS_URL`
   for shared storage if set, otherwise in-process memory.
6. **JSON provider** — a custom provider auto-serializes `bson.ObjectId` and
   `datetime` values in any response so routes can return raw Mongo documents.
7. **Socket.IO + CORS** — the shared `socketio` instance from
   `core/extensions.py` is bound to the app. Allowed origins come from the
   `CORS_ORIGINS` env var (default `http://127.0.0.1:3000,http://localhost:3000`)
   and apply to both REST CORS and the WebSocket handshake.
8. **Error handling & request IDs** — a global exception handler returns JSON
   500s; every request gets an `X-Request-ID` (reused from the header if a
   proxy already set one).
9. **Database** — `config/database.py` connects to MongoDB (`MONGODB_URI`,
   database `DATABASE_NAME`, default `hrtech`) and ensures indexes
   (see [database.md](database.md)).
10. **GCS hard requirement** — `gcs_service.is_gcs_configured()` is checked and
    the boot **raises** if Cloud Storage isn't configured. Deliberate: every
    persistent artifact lives in GCS with no local-disk fallback, so a
    misconfigured deployment must fail loudly rather than silently lose uploads.
11. **Wallet bootstrap** — grants the signup bonus to any existing users who
    don't have a wallet yet (idempotent, runs every boot).
12. **Interview runtime init** — importing `interview/runtime.py` creates the
    process-wide singletons: the `InterviewSessionManager` (built from
    `InterviewConfig` + `LLMConfig`, which defaults to OpenAI/`gpt-4o-mini`),
    the in-memory `live_sessions` proctoring store, the `GazeRecorderService`,
    and the transient staging folders under the OS temp dir.
13. **Background workers** — `jobs/runner.start_all()` starts the
    `BackgroundProcessor` (async CV scoring queue), the
    `InviteCleanupScheduler` (purges dormant invite-only accounts), and the
    `InterviewRefundSweeper` (refunds or auto-finalizes interviews abandoned
    mid-session — see [interview-engine.md](interview-engine.md)). Honors
    `GENHIRE_DISABLE_JOBS=1` so tooling can import the app without spawning
    threads.
14. **Blueprint registration** — see the table below.
15. **Payment module init** — `init_payment_routes(db)` and registers
    `payment_bp`. Wrapped in try/except so the app still boots if the payment
    module can't load.
16. **Socket.IO handlers** — `sockets.register_all()` registers the proctoring
    stream and mobile-companion handlers.

## Route blueprints

| Blueprint | File | URL prefix | Purpose |
|---|---|---|---|
| `auth_bp` | `routes/auth_routes.py` | `/api` | Register, login, email verification, password reset, Google OAuth, account deletion |
| `profile_bp` | `routes/profile_routes.py` | `/api` | Profile CRUD, company profile, CV details, recruiter/candidate cost statistics |
| `job_bp` | `routes/job_routes.py` | `/api` | Job CRUD, AI JD generation, per-job applications list |
| `application_bp` | `routes/application_routes.py` | `/api` | Apply/withdraw, application status, CV view, interview reports, score recalculation |
| `file_bp` | `routes/file_routes.py` | `/api` | Legacy file upload/view (CV, photo), admin file access |
| `cv_bp` | `routes/cv_routes.py` (factory `create_cv_routes(collections)`) | `/api/cv` | Multi-CV management: upload, list, preview, set primary, delete, text extraction |
| `practice_bp` | `routes/practice_routes.py` | `/api/practice` | Practice interview sessions (start/answer/end/history/report) |
| `admin_bp` | `routes/admin_routes.py` | `/api/admin` | Full admin portal API (users, jobs, applications, verification, cost stats) |
| `speech_bp` | `routes/speech_routes.py` | `/api/speech` | Speech-to-text (`/transcribe`) and text-to-speech (`/synthesize`) via Google Cloud |
| `invite_bp` | `routes/invite_routes.py` | `/api` | Recruiter bulk invites + invite redemption |
| `identity_bp` | `routes/identity_routes.py` | `/api` | One-time candidate identity-card upload, status, and image |
| `interview_bp` | `routes/interview_routes.py` (factory `init_interview_routes(db, collections)`) | `/api` | The real interview engine's HTTP surface (`/api/interviews/*`) |
| `system_bp` | `routes/system_routes.py` (factory `create_system_routes(db)`) | — | `/`, `/health` (pings Mongo), `/api/files/<gridfs_id>` |
| `cost_bp` | `routes/cost_routes.py` (factory `create_cost_routes(db)`) | — | Direct LLM chat + STT/TTS cost logging endpoints |
| `payment_bp` | `payment_module/routes/payment_routes.py` | `/api/payment` | Plans, Razorpay checkout, wallet, transactions, webhook |

Routes are thin: each one validates the HTTP layer and delegates to a
controller class in `controllers/` (e.g. `ApplicationController`,
`JobController`, `AdminController`) which holds the business logic and talks
to MongoDB.

Socket.IO handlers are **not** blueprints — they live in `sockets/`
(`proctoring_sockets.py`, `mobile_sockets.py`) and are registered by
`sockets.register_all()`. See [interview-engine.md](interview-engine.md).

## Middleware (`middleware/`)

| File | What it provides |
|---|---|
| `auth_middleware.py` | JWT auth. `decode_user_from_token()` is the single decode path shared by REST and Socket.IO. Decorators: `@token_required` (accepts `Authorization: Bearer <jwt>` header **or** `?token=` query param for new-tab file views), `@admin_required`, `@recruiter_required`, `@candidate_required`, `@verified_required` (recruiter must be admin-approved), `@permission_required('x.y')` (admin permission system, `*` = super admin). Tokens are HS256, signed with `JWT_SECRET_KEY`, expiry `JWT_EXPIRATION_DAYS` (default 7 days). |
| `cors_middleware.py` | CORS setup helper. |
| `input_validator.py` | Request payload validation helpers. |
| `rate_limiter.py` | Per-route `@rate_limit(max_calls, window_seconds, key_func=None)` decorator (separate from the global Flask-Limiter above) — e.g. register (5/60s), login (10/60s), forgot-password (3/300s). Sliding window, shared via Redis when `REDIS_URL` is set, otherwise in-process only. Keys by client IP (`X-Forwarded-For`, falling back to `remote_addr`) unless `key_func` is given; forgot-password keys by the **target email** instead, since IP-keying can misfire behind a reverse proxy/CDN that doesn't cleanly forward each visitor's distinct IP (collapses many different real users into one shared bucket) — email-keying is also the more correct defense for that endpoint's actual abuse vector (spamming one inbox), and sidesteps proxy quirks entirely. |

## Services (`services/`)

| Service | Role |
|---|---|
| `background_processor.py` | A single daemon worker thread + `queue.Queue` (no Redis/Celery). Applications are inserted with `processing_status: "processing"`, then a queued task parses + AI-scores the CV, updates the application, and emails the candidate if the automatic result is `shortlisted` or `rejected`. |
| `cv_scoring_service.py` | AI CV-vs-JD scoring; also formats CV/JD text for the interview engine. |
| `cv_structured_parser_service.py` | Extracts structured fields (education, experience, skills…) from raw CV text. |
| `pdf_parser_service.py` | PDF text extraction. |
| `gcs_service.py` | Google Cloud Storage upload/download/signed URLs — the only persistent artifact store, checked at boot. |
| `email_service.py` + `email_providers/` | Transactional email: verification, password reset, invite emails, application status changes, interview-complete notifications (recruiter + candidate). Provider chosen by `EMAIL_PROVIDER` — `zeptomail` (primary), `mailgun` (fallback), `noop` (dev). Every send is written to the `email_log` collection for usage-based cost tracking. Sends run on fire-and-forget daemon threads. |
| `invite_service.py` | The invite system: parses emails from text/CSV/XLSX, classifies them, creates invite tokens (SHA-hashed, TTL-limited) and "burner" invite-only accounts with generated Invite IDs, tracks batches, and consumes tokens at redemption. |
| `invite_email_templates.py` | HTML templates for invite emails. |
| `invite_cleanup_scheduler.py` | Recurring scheduler that purges dormant burner accounts. |
| `identity_card_service.py` | The one-time candidate identity card: upload validation (JPEG/PNG/WebP, ≤5 MB), GridFS storage, and the `users.identity_card` pointer. Candidates cannot replace their own card — only admins can. |
| `face_match_service.py` | The interview identity check: sends the ID card + the live webcam capture through the LLM chain on vision-capable models (`FACE_MATCH_*_MODEL`) and returns a 0–100 similarity score against `FACE_MATCH_THRESHOLD` (default 75). Advisory only — see [interview-engine.md](interview-engine.md). |
| `face_verification_service.py` | Image-quality gate for captures (no face / multiple faces), GridFS storage of face images, and the DeepFace helpers still used by live frame proctoring. `FACE_VERIFICATION_MODE` (`enforce`/`monitor`/`off`) only gates whether the check runs at all; the DeepFace/OpenCV stack is **not** in `requirements.txt`, and every path degrades to storage-only without it. |
| `interview_credit_service.py` | The interview credit-refund lifecycle: idempotent refunds (`refund:<debit-key>`) when a session ends with zero answers, refund-count-aware debit keys (`real-interview:<app_id>:r<n>`), and the `InterviewRefundSweeper` daemon that refunds unanswered stale sessions and auto-finalizes answered ones into scored reports. |
| `credit_service.py`, `interview_quota_service.py`, `candidate_practice_quota_service.py` | Credit/quota checks around interviews and practice sessions. |
| `usage_telemetry_service.py` | `record_usage_event()` — writes usage/cost events (LLM, STT seconds, TTS characters) that power the admin/recruiter/candidate cost-statistics screens. |
| `google_speech_service.py` | Google Cloud STT/TTS used by `/api/speech/*`, plus the short-lived access token the kiosk uses for its own streaming STT. |
| `llm_fallback_service.py` | **THE** LLM chain. Provider order from `LLM_PROVIDER_PRIORITY` (default `openai,gemini,groq`; `LLM_PRIMARY/SECONDARY/TERTIARY_PROVIDER` also accepted), per-provider models from `LLM_<P>_MODEL`, quota/rate-limit detection with per-provider cooldowns, and per-call `model_overrides` for task-specific models. |
| `gcp_billing_service.py`, `openai_billing_service.py` | Real provider spend for the admin cost page — GCP via the BigQuery billing export, OpenAI via the Costs API. Both fall back to the `INFRA_MONTHLY_*` env estimates when unconfigured. See [costfetch.md](../costfetch.md). |
| `screening_export_service.py` | Builds the per-job screening-cleared XLSX/CSV export. |

## Utils (`utils/`)

- `ai_detection.py` — estimates the probability an answer was AI-generated (stored per answer as `ai_probability`).
- `gaze_recorder_service.py` — builds the GazeRecorder HTML page and analyzes gaze-point payloads into a cheating score + heatmap files.
- `company_resolver.py` — resolves a job's display company name from the recruiter's current company profile (so renames don't leave stale names on old jobs).
- `helpers.py`, `validators.py`, `job_standards.py`, `cv_score_migration.py` — misc shared helpers and one-off migration logic.
- Frame-level proctoring analysis lives in the backend-root `security_check.py`, not in `utils/`.

## Models (`models/`)

Plain-Python model helpers for `user.py`, `job.py`, `application.py`
(the app uses PyMongo directly — there is no ORM; these files define
document construction/validation helpers).

## Socket.IO (`core/extensions.py` + `sockets/`)

`core/extensions.py` holds the shared `socketio = SocketIO(...)` instance so
controllers can `socketio.emit(...)` without importing the app factory (avoids
circular imports). Handlers live in `sockets/proctoring_sockets.py` and
`sockets/mobile_sockets.py`, registered by `sockets.register_all()`:

| Event | Direction | Purpose |
|---|---|---|
| `connect` | client → server | JWT-authenticated handshake; joins a room named after the user's id. Invalid tokens are rejected; *tokenless* connects are allowed but get no user room — needed for the mobile-camera QR companion page, which only joins session rooms. |
| `application_update` | server → client | Pushed to the candidate's and recruiter's rooms on apply / status change / score update. Payload: `{type, application}`. |
| `start_proctoring` | kiosk → server | Kiosk announces it will stream frames; joins a room keyed by interview `session_id`. |
| `proctoring_frame` | client → server | One base64 JPEG per second → `security_check.analyze_frame_for_proctoring()` (MediaPipe head-pose + DeepFace identity) → score/infractions updated in the in-memory `live_sessions` store. Streamed by the **web** interview UI; the kiosk analyzes frames locally and only sends violations. |
| `proctoring_alert` | server → client | Emitted when a frame analysis flags a violation. |
| `proctoring_violation` | client → server | Manual violations (tab switch / window blur / app switch) recorded against the session. The kiosk sends these with acknowledgements and a retry queue. |
| `join_mobile_session` (in), `mobile_connected` (out) · `control_mobile_recording` (in), `mobile_recording_action` (out) · `mobile_status_update` (in), `mobile_status_dashboard` (out) | both | Relay channel pairing a phone camera (`/mobile-camera/:sessionId` page, opened via QR code) with the desktop interview for a second-angle environment recording. |

Inbound events are exactly: `connect`, `disconnect`, `start_proctoring`,
`proctoring_frame`, `proctoring_violation`, `join_mobile_session`,
`control_mobile_recording`, `mobile_status_update` — the set
`scripts/route_manifest.py` diffs against its baseline.

## Environment variables

Defined in `python-backend/.env.example`. The important ones:

| Variable | Used for |
|---|---|
| `MONGODB_URI`, `DATABASE_NAME` | MongoDB connection (default DB name `hrtech`) |
| `JWT_SECRET_KEY`, `JWT_EXPIRATION_DAYS` | Auth tokens |
| `FLASK_SECRET_KEY`, `FLASK_ENV` | Flask sessions; `production` enforces real secrets |
| `CORS_ORIGINS` | Allowed frontend origins (REST + WebSocket) |
| `REQUIRE_EMAIL_VERIFICATION` | Gate login behind email verification |
| `EMAIL_PROVIDER` | `zeptomail` · `mailgun` · `noop` |
| `ZEPTOMAIL_API_KEY`, `ZEPTOMAIL_FROM_EMAIL`, `ZEPTOMAIL_FROM_NAME` | Primary email provider |
| `MAILGUN_API_KEY`, `MAILGUN_DOMAIN`, `MAILGUN_FROM_EMAIL` | Fallback email provider |
| `FRONTEND_URL` | Links inside emails (verification, reset, invites) |
| `GOOGLE_CLIENT_ID` | Google OAuth token verification |
| `LLM_PROVIDER_PRIORITY` | Chain order, default `openai,gemini,groq` |
| `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `GROQ_API_KEY` | Provider keys for the chain (Gemini reads `GOOGLE_API_KEY`) |
| `LLM_OPENAI_MODEL`, `LLM_GEMINI_MODEL`, `LLM_GROQ_MODEL` | Per-provider default models |
| `FACE_MATCH_THRESHOLD`, `FACE_MATCH_OPENAI_MODEL`, `FACE_MATCH_GEMINI_MODEL`, `FACE_MATCH_GROQ_MODEL` | ID-card face-match score threshold (default 75) and the vision model per provider |
| `INVITE_TOKEN_SECRET`, `INVITE_DEFAULT_VALIDITY_DAYS`, `INVITE_SCOPED_JWT_TTL_HOURS`, `INVITE_CLEANUP_INTERVAL_HOURS` | Invite tokens, burner-account validity, cleanup cadence |
| `MOBILE_RECORDING_ENABLED` | Phone second-camera pairing (default `true`) |
| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` | Payments |
| `SIGNUP_BONUS_CREDITS`, `CANDIDATE_PRACTICE_CREDITS`, `CANDIDATE_PRACTICE_PROCTORED_CREDITS`, `RECRUITER_AI_JD_CREDITS`, `RECRUITER_REAL_INTERVIEW_CREDITS`, `RECRUITER_REAL_INTERVIEW_PROCTORED_CREDITS` | Credit pricing (defaults 100 / 30 / 50 / 10 / 30 / 50) |
| `FACE_VERIFICATION_MODE` | `enforce` (default) / `monitor` / `off`. `off` skips identity capture+scoring entirely; identity never blocks an interview either way. Not in `.env.example` — set it explicitly if you need it. |
| `INTERVIEW_ABANDON_TTL_MINUTES`, `INTERVIEW_REFUND_SWEEP_INTERVAL_MINUTES` | Refund sweeper: how long an "active" session may idle before it's treated as abandoned (default 120, floor 15), and sweep frequency (default 15, floor 5) |
| `GCS_BUCKET_NAME`, Cloud Run service identity or local credentials | Cloud Storage — **mandatory**; omit `GOOGLE_APPLICATION_CREDENTIALS` on Cloud Run, since an empty SDK file override blocks ADC |
| `RECRUITER_INVITE_CREDITS_PER_CANDIDATE` | Bulk-invite price (default 1 credit/candidate; failed emails auto-refund) |
| `ZEPTOMAIL_PER_EMAIL_COST_INR` | Per-email price for the admin cost page's usage-based email line (default 0.015) |
| `GCP_BILLING_EXPORT_BQ_TABLE`, `OPENAI_ADMIN_API_KEY` | Real billing fetch for the admin cost page |
| `REDIS_URL` | Optional shared rate-limit storage |
| `SENTRY_DSN` | Optional error tracking |
| `FORCE_HTTPS` | Enable HTTPS redirect + HSTS via Talisman in production |
| `GENHIRE_DISABLE_JOBS` | `1` skips the background daemons (used by `scripts/route_manifest.py` and the dev reloader's watcher pass) |

`FACE_VERIFICATION_MODE`, `INTERVIEW_ABANDON_TTL_MINUTES`,
`INTERVIEW_REFUND_SWEEP_INTERVAL_MINUTES`, `REDIS_URL`, `SENTRY_DSN`,
`GCP_BILLING_EXPORT_BQ_TABLE`, `OPENAI_ADMIN_API_KEY` and the `INFRA_MONTHLY_*`
figures are read by the code but are **not** in `.env.example` — all have
working defaults or degrade gracefully when unset.

## File storage layout (GCS-only — no persistent local disk)

Every persistent artifact lives in the bucket named by `GCS_BUCKET_NAME`
(currently `genhireuploads` in **both** `.env` and `.env.production` — the
planned `genhire-uploads-prod` split has not happened yet, see
[production-readiness.md](../production-readiness.md)); local paths under the
OS temp dir (`genhire_staging/`) are transient staging only, deleted right
after upload:

- `cvs/<user>/`, `photos/<user>/`, `jds/<recruiter>/` — CVs, profile photos, recruiter-uploaded JD PDFs
- `recordings/` — webcam interview recordings (`<session>-<user>.webm`)
- `mobile_recordings/` — phone-camera environment recordings
- `proctoring/` — gaze plots; `proctoring/gaze_recorder/` — GazeRecorder JSON payloads
- Artifacts are served through `GET /api/view-file` (auth required; proxies
  bytes from GCS, scoped to the app's own bucket) or signed URLs (CVs/JDs)

**The one exception to GCS-only**: identity-card images and interview face
captures live in **MongoDB GridFS**, not GCS (`identity_card_service.py` /
`face_verification_service.store_face_image`), served via
`GET /api/identity-card/image` and
`GET /api/interviews/<sid>/face-image/<kind>`. Legacy GridFS CVs also remain
readable through `GET /api/files/<gridfs_id>`.

## Deployment: Cloud Run and keeping it warm

Production is deployed to **Google Cloud Run** from `python-backend/Dockerfile`
(pending source: Gunicorn gthread + simple-websocket, listens on `$PORT`,
Docker default `8080`; see [interview setup recovery](../interview-setup-recovery.md)). Cloud Run's
default billing model scales a service to **zero instances** after a period
of no traffic — the next request then pays a cold-start penalty (container
boot + Python imports + a fresh MongoDB connection).

**Mitigation in this repo**: `.github/workflows/keep-backend-warm.yml` is a
GitHub Actions scheduled workflow that pings `GET /health` on the production
URL every 5 minutes (plus a manual `workflow_dispatch` trigger for on-demand
testing). It needs no GCP credentials — it's a plain unauthenticated HTTP GET
from GitHub's runners. Two things worth knowing:

- **It's best-effort, not a guarantee.** Google does not promise that
  incoming traffic alone prevents scale-to-zero (Cloud Run can still recycle
  an idle instance), and GitHub's cron scheduler is not perfectly punctual
  under load. Occasional cold starts can still happen.
- **It works the same on a private or public repo** — scheduled workflows
  run regardless of visibility. The only difference is billing: a public
  repo's Actions minutes are unlimited/free, while a private repo draws down
  the account's monthly free quota (2,000 min/month on GitHub Free, 3,000 on
  Pro). At a 5-minute cadence this workflow uses roughly ~1,400 minutes/month
  on its own — fine in isolation, but worth checking against other CI usage
  on the same account. Widen the cron interval in the workflow file (e.g.
  `*/10 * * * *`) if quota becomes tight.
- GitHub also disables **any** scheduled workflow after 60 days with no
  commits pushed to the default branch — a routine push re-enables it.

**The guaranteed fix** (costs continuous compute instead of Actions minutes):
set a minimum instance count on the Cloud Run service so one instance never
scales down —

```bash
gcloud run services update <SERVICE_NAME> \
  --region=europe-west1 \
  --min-instances=1
```

This isn't run from this repo (no deploy automation/IaC is checked in here —
deployment is manual `gcloud`/Cloud Console) and requires GCP credentials, so
it's a manual, deliberate choice rather than something the keep-warm workflow
does automatically.
