# Backend — Detailed Wiring

The backend is a single Flask application defined in `python-backend/app.py`.
It serves a JSON REST API under `/api/*`, a Socket.IO WebSocket server on the
same port, and runs two background worker threads. It is started with
`socketio.run(app, host="0.0.0.0", port=5000)` in development (or Gunicorn via
`gunicorn.conf.py` / `start_server.sh` / `Dockerfile` in deployment).

## Startup sequence (what `app.py` does, in order)

1. **Environment & logging** — forces UTF-8 stdout, silences TensorFlow/MediaPipe
   logs, loads `.env` via `config/env_loader.load_environment()`.
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
7. **Socket.IO + CORS** — the shared `socketio` instance from `extensions.py` is
   bound to the app. Allowed origins come from the `CORS_ORIGINS` env var
   (default `http://127.0.0.1:3000,http://localhost:3000`) and apply to both
   REST CORS and the WebSocket handshake.
8. **Error handling & request IDs** — a global exception handler returns JSON
   500s; every request gets an `X-Request-ID` (reused from the header if a
   proxy already set one).
9. **Database** — `config/database.py` connects to MongoDB (`MONGODB_URI`,
   database `DATABASE_NAME`, default `hrtech`) and ensures indexes
   (see [database.md](database.md)).
10. **Wallet bootstrap** — grants the signup bonus to any existing users who
    don't have a wallet yet (idempotent, runs every boot).
11. **Background workers** — starts the `BackgroundProcessor` (async CV scoring
    queue), the `InviteCleanupScheduler` (purges dormant invite-only
    accounts), and the `InterviewRefundSweeper` (refunds or auto-finalizes
    interviews abandoned mid-session — see
    [interview-engine.md](interview-engine.md)).
12. **Blueprint registration** — see the table below.
13. **Interview system init** — creates the global `InterviewSessionManager`
    with `InterviewConfig` + `LLMConfig` (Groq via `GROQ_API_KEY`).
14. **Payment module init** — `init_payment_routes(db)` and registers
    `payment_bp`. Wrapped in try/except so the app still boots if the payment
    module can't load.

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
| `payment_bp` | `payment_module/routes/payment_routes.py` | `/api/payment` | Plans, Razorpay checkout, wallet, transactions, webhook |

Routes are thin: each one validates the HTTP layer and delegates to a
controller class in `controllers/` (e.g. `ApplicationController`,
`JobController`, `AdminController`) which holds the business logic and talks
to MongoDB.

**Interview and proctoring routes are NOT in a blueprint** — they live
directly in `app.py` (`/api/interviews/*` plus all Socket.IO handlers).
See [interview-engine.md](interview-engine.md).

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
| `gcs_service.py` | Google Cloud Storage upload/download for CV files. |
| `email_service.py` + `email_providers/` | Transactional email (Mailgun-backed): verification, password reset, invite emails, application status changes, interview-complete notifications (recruiter + candidate). Sends run on fire-and-forget daemon threads. |
| `invite_service.py` | The invite system: parses emails from text/CSV/XLSX, classifies them, creates invite tokens (SHA-hashed, TTL-limited) and "burner" invite-only accounts with generated Invite IDs, tracks batches, and consumes tokens at redemption. |
| `invite_email_templates.py` | HTML templates for invite emails. |
| `invite_cleanup_scheduler.py` | Recurring scheduler that purges dormant burner accounts. |
| `face_verification_service.py` | Candidate face identity: image quality gate, DeepFace (VGG-Face) enroll/verify against the account's registered face, GridFS storage of identity photos. Modes via `FACE_VERIFICATION_MODE` (`enforce`/`monitor`/`off`); degrades to photo-capture-only if the DeepFace stack isn't installed. |
| `interview_credit_service.py` | The interview credit-refund lifecycle: idempotent refunds (`refund:<debit-key>`) when a session ends with zero answers, refund-count-aware debit keys (`real-interview:<app_id>:r<n>`), and the `InterviewRefundSweeper` daemon that refunds unanswered stale sessions and auto-finalizes answered ones into scored reports. |
| `credit_service.py`, `interview_quota_service.py`, `candidate_practice_quota_service.py` | Credit/quota checks around interviews and practice sessions. |
| `usage_telemetry_service.py` | `record_usage_event()` — writes usage/cost events (LLM, STT seconds, TTS characters) that power the admin/recruiter/candidate cost-statistics screens. |
| `google_speech_service.py` | Google Cloud STT/TTS used by `/api/speech/*`. |
| `llm_fallback_service.py` | Fallback chain when the primary LLM provider fails. |
| `recording_analysis_service.py` | Post-interview recording analysis (heavy dependencies; the `RecordingAnalyzer` integration is currently **disabled** in `app.py` — `RECORDING_ANALYZER_AVAILABLE = False`). |

## Utils (`utils/`)

- `ai_detection.py` — estimates the probability an answer was AI-generated (stored per answer as `ai_probability`).
- `cheating_detection.py`, `gaze_recorder_service.py` — proctoring analysis; the gaze service builds the GazeRecorder HTML page and analyzes gaze-point payloads into a cheating score + heatmap files.
- `helpers.py`, `validators.py`, `job_standards.py`, `interview_system.py`, `cv_score_migration.py` — misc shared helpers and one-off migration logic.

## Models (`models/`)

Plain-Python model helpers for `user.py`, `job.py`, `application.py`
(the app uses PyMongo directly — there is no ORM; these files define
document construction/validation helpers).

## Socket.IO (`extensions.py`)

`extensions.py` holds the shared `socketio = SocketIO(...)` instance so
controllers can `socketio.emit(...)` without importing `app.py` (avoids
circular imports). Handlers registered in `app.py`:

| Event | Direction | Purpose |
|---|---|---|
| `connect` | client → server | JWT-authenticated handshake; joins a room named after the user's id. Invalid tokens are rejected; *tokenless* connects are allowed but get no user room — needed for the mobile-camera QR companion page, which only joins session rooms. |
| `application_update` | server → client | Pushed to the candidate's and recruiter's rooms on apply / status change / score update. Payload: `{type, application}`. |
| `start_proctoring` | kiosk → server | Kiosk announces it will stream frames; joins a room keyed by interview `session_id`. |
| `proctoring_frame` | kiosk → server | One base64 JPEG per second → MediaPipe head-pose + DeepFace identity check → score/infractions updated in the in-memory `live_sessions` store. |
| `proctoring_alert` | server → kiosk | Emitted when a frame analysis flags a violation. |
| `proctoring_violation` | kiosk → server | Manual violations (tab switch / window blur / app switch) recorded against the session. |
| `join_mobile_session`, `control_mobile_recording`, `mobile_recording_action`, `mobile_status_update`, `mobile_status_dashboard`, `mobile_connected` | both | Relay channel pairing a phone camera (`/mobile-cam/:sessionId` page, opened via QR code) with the desktop interview for a second-angle environment recording. |

## Environment variables

Defined in `python-backend/.env.example`. The important ones:

| Variable | Used for |
|---|---|
| `MONGODB_URI`, `DATABASE_NAME` | MongoDB connection (default DB name `hrtech`) |
| `JWT_SECRET_KEY`, `JWT_EXPIRATION_DAYS` | Auth tokens |
| `FLASK_SECRET_KEY`, `FLASK_ENV` | Flask sessions; `production` enforces real secrets |
| `CORS_ORIGINS` | Allowed frontend origins (REST + WebSocket) |
| `REQUIRE_EMAIL_VERIFICATION` | Gate login behind email verification |
| `MAILGUN_API_KEY`, `MAILGUN_DOMAIN`, `MAILGUN_FROM_EMAIL` | Email sending |
| `FRONTEND_URL` | Links inside emails (verification, reset, invites) |
| `GOOGLE_CLIENT_ID` | Google OAuth token verification |
| `GROQ_API_KEY` | LLM interview engine |
| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` | Payments |
| `SIGNUP_BONUS_CREDITS`, `CANDIDATE_PRACTICE_CREDITS`, `CANDIDATE_PRACTICE_PROCTORED_CREDITS`, `RECRUITER_AI_JD_CREDITS`, `RECRUITER_REAL_INTERVIEW_CREDITS`, `RECRUITER_REAL_INTERVIEW_PROCTORED_CREDITS` | Credit pricing (defaults 100 / 30 / 50 / 10 / 30 / 50) |
| `FACE_VERIFICATION_MODE`, `FACE_VERIFY_MAX_ATTEMPTS` | Face identity gate: `enforce` (default) / `monitor` / `off`; mismatch attempts before blocking (default 3) |
| `INTERVIEW_ABANDON_TTL_MINUTES`, `INTERVIEW_REFUND_SWEEP_INTERVAL_MINUTES` | Refund sweeper: how long an "active" session may idle before it's treated as abandoned (default 120), and sweep frequency (default 15) |
| `UPLOAD_FOLDER` | Local storage root for recordings/proctoring artifacts (default `uploads/`) |
| `REDIS_URL` | Optional shared rate-limit storage |
| `SENTRY_DSN` | Optional error tracking |
| `FORCE_HTTPS` | Enable HTTPS redirect + HSTS via Talisman in production |

## File storage layout

- `uploads/proctoring/` — gaze plots and GazeRecorder payloads (`gaze_recorder/` subfolder)
- `uploads/recordings/` — webcam interview recordings (`<session>-<user>.webm`)
- `uploads/mobile_recordings/` — phone-camera environment recordings
- `uploads/tmp/` — temporary CV/JD `.txt` files fed to the interview document pipeline
- CV PDFs — GridFS (`GET /api/files/<gridfs_id>`) and/or Google Cloud Storage via `gcs_service.py`

## Deployment: Cloud Run and keeping it warm

Production is deployed to **Google Cloud Run** from `python-backend/Dockerfile`
(Gunicorn + eventlet worker, listens on `$PORT`, default `8080`). Cloud Run's
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
