# GenHire — Complete Developer Handbook

*Written as a knowledge-transfer document for an engineer joining the team
tomorrow. Read this end to end and you should be able to run GenHire locally,
find any feature in the code, understand why it's built the way it is, and start
shipping without needing to ask anyone.*

Everything here is derived from the actual repository. Where I teach a concept
from scratch, I then show exactly how GenHire uses it and which files implement
it.

---

## Table of contents

1. [What GenHire is](#1-what-genhire-is)
2. [The three applications and how they talk](#2-the-three-applications-and-how-they-talk)
3. [Repository layout — folder by folder, and why each exists](#3-repository-layout)
4. [The request lifecycle, end to end](#4-the-request-lifecycle-end-to-end)
5. [Backend architecture (Flask)](#5-backend-architecture-flask)
6. [Authentication, authorization, and sessions](#6-authentication-authorization-and-sessions)
7. [Middleware](#7-middleware)
8. [Controllers, services, and utilities](#8-controllers-services-and-utilities)
9. [The database (MongoDB)](#9-the-database-mongodb)
10. [The AI interview engine](#10-the-ai-interview-engine)
11. [Resume (CV) parsing and scoring](#11-resume-cv-parsing-and-scoring)
12. [Face verification and proctoring](#12-face-verification-and-proctoring)
13. [The payment module (credits, wallets, Razorpay)](#13-the-payment-module)
14. [Email and notifications](#14-email-and-notifications)
15. [The invite system](#15-the-invite-system)
16. [Real-time updates (Socket.IO)](#16-real-time-updates-socketio)
17. [File uploads and storage](#17-file-uploads-and-storage)
18. [The frontend (React)](#18-the-frontend-react)
19. [The Secure Browser (Electron kiosk)](#19-the-secure-browser-electron-kiosk)
20. [Admin, recruiter, and candidate workflows](#20-workflows)
21. [Error handling, validation, and logging](#21-error-handling-validation-and-logging)
22. [Security](#22-security)
23. [Configuration and environment variables](#23-configuration-and-environment-variables)
24. [Third-party integrations and libraries](#24-third-party-integrations-and-libraries)
25. [Build, run, and deployment](#25-build-run-and-deployment)
26. [Local setup — step by step](#26-local-setup)
27. [Senior architect's review](#27-senior-architects-review)

---

## 1. What GenHire is

GenHire is an **AI-powered candidate screening platform**. The one-sentence
version, straight from the README:

> Recruiters post jobs and get automatically CV-scored applicants; candidates
> take adaptive, voice-based AI interviews inside a locked-down secure browser
> with live proctoring and face identity verification; recruiters receive full
> interview reports and mark candidates **Screening Cleared** for their own
> further hiring rounds.

Two design truths shape everything:

- **It screens, it does not hire.** The final decision is always a human
  recruiter's. GenHire filters the funnel (CV score → AI interview → integrity
  report) and hands a "Screening Cleared" candidate back to the recruiter's own
  hiring process.
- **Everything costly runs on credits.** A per-user credit wallet backs every
  billable action (interviews, AI job-description generation). This is the
  business model and it's woven through the backend.

---

## 2. The three applications and how they talk

GenHire is **three separate applications** in one repository:

| App | Tech | Folder | Role |
|---|---|---|---|
| **Backend API** | Python 3.11, Flask + Flask-SocketIO | `python-backend/` | All business logic, database, AI engine, proctoring, payments, email |
| **Web frontend** | React 19 (Create React App) | `react-frontend/` | The website candidates, recruiters, and admins use |
| **Secure Browser** | Electron desktop app | `secure-browser-kiosk/` | Locked-down kiosk that runs the actual AI interview |

```
                        ┌─────────────────────────────┐
                        │          MongoDB            │
                        │  users, jobs, applications, │
                        │  interviews, invites,       │
                        │  wallets, payments, ...     │
                        └────────────▲────────────────┘
                                     │ PyMongo
   HTTPS (REST /api/*)   ┌───────────┴───────────────┐    External services
  ┌─────────────────────►│      Flask Backend        │◄──► Groq (LLM)
  │                      │      (port 5000/8080)     │◄──► Google Cloud Speech (STT/TTS)
  │  WebSocket           │  - 10+ route blueprints   │◄──► Razorpay (payments)
  │  (Socket.IO)         │  - payment_module         │◄──► Mailgun / ZeptoMail (email)
  │ ┌───────────────────►│  - interview engine       │◄──► Google Cloud Storage + GridFS
  │ │                    │  - proctoring (MediaPipe/ │◄──► GazeRecorder CDN (eye tracking)
  │ │                    │    DeepFace)              │
  │ │                    └───────────▲───────────────┘
  │ │                                │ REST + Socket.IO
┌─┴─┴──────────────┐   deep link     │ (kiosk calls the SAME API directly)
│  React Frontend  │  secure-        │
│  (browser SPA)   ├─interview://───►┌──────────────────────┐
│ candidate /      │  start?         │  Secure Browser      │
│ recruiter /      │  initData=...   │  (Electron kiosk)    │
│ admin UIs        │                 │  runs the interview  │
└──────────────────┘                 └──────────────────────┘
```

**How they communicate:**

1. **Frontend → Backend (REST).** Every page calls the Flask API over HTTP
   through a small set of service files in `react-frontend/src/services/`. They
   prefix the API base, attach the JWT, and convert any `401` into a global
   session-expired event.
2. **Frontend ↔ Backend (Socket.IO).** A single shared socket, authenticated
   with the JWT in the handshake. Each user sits in a room named by their user
   ID and receives `application_update` events (live dashboards).
3. **Frontend → Secure Browser (deep link).** Starting an interview navigates the
   browser to `secure-interview://start?initData=<encoded payload>`. The OS
   launches the installed Electron app, which registered itself as the handler
   for that custom URL scheme.
4. **Secure Browser → Backend (REST + Socket.IO).** The kiosk does **not** proxy
   through the website. Its renderer calls the same Flask endpoints directly and
   opens its own socket for proctoring frames.
5. **Backend → External services.** Groq (LLM), Google Cloud Speech, Razorpay,
   Mailgun/ZeptoMail, Google Cloud Storage/GridFS, GazeRecorder.

**Why this shape?** The interview must be trustworthy (no alt-tabbing to Google
answers) and needs OS-level lockdown a browser tab can't provide — hence the
separate Electron app. But we don't want to reimplement the API twice, so the
kiosk reuses the exact same backend endpoints. The website and the kiosk are two
clients of one API.

---

## 3. Repository layout

### Top level

```
GenHire-final/
├── python-backend/       # Flask API + all business logic
├── react-frontend/       # React SPA
├── secure-browser-kiosk/ # Electron kiosk
├── docs/                 # Existing hand-written docs (architecture, api, flows)
├── vercel.json           # SPA hosting config for the frontend on Vercel
├── .github/workflows/keep-backend-warm.yml  # cron ping to fight Cloud Run cold starts
└── README.md
```

### `python-backend/` — why each folder exists

```
python-backend/
├── app.py                # THE entry point: Flask app, all wiring, interview routes, socket handlers
├── extensions.py         # Shared SocketIO instance (avoids circular imports)
├── config/               # env loading + Mongo connection/index management
│   ├── env_loader.py
│   └── database.py       # DatabaseConfig — connect(), get_collections(), _ensure_indexes()
├── routes/               # Flask blueprints — thin HTTP layer, one file per feature
├── controllers/          # Business logic classes (called by routes)
├── services/             # Cross-cutting services (email, CV scoring, credits, GCS, invites, ...)
│   └── email_providers/  # Pluggable email backends (mailgun / zeptomail / noop)
├── middleware/           # Auth decorators, CORS, input validation, rate limiting
├── models/               # Plain-Python document helpers (no ORM): user, job, application
├── interview/            # The AI interview engine (see §10)
│   ├── config/           # InterviewConfig, LLMConfig, LLMProvider
│   ├── core/             # session_manager, question generator, cost trackers, llm_wrapper
│   ├── llm/              # LLM provider clients + factory + fallback (Groq, Gemini, OpenAI, Groq)
│   ├── document/         # DocumentLoader/processor for CV/JD text
│   └── prompts/          # Prompt templates (greeting, technical, HR, closing, ...)
├── evaluation_model/     # Rubric-based answer & communication evaluators
│   └── rubrics_eval/
├── payment_module/       # Self-contained credits/wallet/Razorpay package (see §13)
├── question_bank/        # CSV/JSON question banks by role & seniority
├── gpu_intensive_task/   # Heavy proctoring microservice pieces (mostly disabled in app.py)
├── utils/                # ai_detection, cheating_detection, gaze recorder, validators, helpers
├── scripts/              # One-off ops: migrations, smoke tests, account cleanup, grant credits
├── migrate_*.py          # Schema/data migrations run manually
├── security_check.py     # Per-frame MediaPipe + DeepFace proctoring analysis
├── face_verify.py        # Face verification helpers
├── requirements.txt
├── Dockerfile            # Cloud Run image (Gunicorn + eventlet)
├── gunicorn.conf.py      # Production server config
└── .env.example          # Every backend env var, documented
```

**The single most important thing to understand:** `app.py` is not just a bootstrap.
It *is* the interview server. All `/api/interviews/*` routes and every Socket.IO
handler live directly in `app.py` (~2,285 lines). Everything else (auth, jobs,
applications, profile, CV, admin, invites, speech, payments) is factored into
blueprints and controllers. If you're looking for interview or proctoring logic,
look in `app.py`; for anything else, look in `routes/` → `controllers/` →
`services/`.

### `react-frontend/src/` — why each folder exists

```
src/
├── App.jsx               # Router + provider tree; all pages lazy-loaded
├── index.js              # React root
├── pages/                # One component per route (Dashboard, Interview, Chat, admin/*, ...)
├── components/           # Reusable UI, grouped by area (candidate/, recruiter/, admin/, interview/, payment/, common/)
├── services/             # ALL backend calls live here (api.js, adminApi.js, inviteApi.js, cvService.js, payment/, socket.js)
├── hooks/                # Data hooks (useJobs, useApplications, useAuth, useRazorpay, useRealtimeApplications, ...)
├── contexts/             # CandidateDataContext — app-wide candidate data cache
├── utils/                # sessionManager (JWT storage), applicationStatus (label logic), authedFetch, cvDetails
├── constants/            # jobTaxonomy
├── config/               # proctoring.js (client proctoring config)
└── styles/               # global CSS (responsive, dark-mode overrides)
```

Styling is **CSS Modules** (`*.module.css`), one per component — no Tailwind, no
MUI. Keep new components consistent with that.

### `secure-browser-kiosk/` — why each file exists

```
secure-browser-kiosk/
├── main.js       # Electron main process: window, kiosk lockdown, deep links, Google TTS/STT, local HTTP server
├── preload.js    # contextBridge — the ONLY channel between renderer and main
├── renderer.js   # Interview UI logic (~1,900 lines) — talks to the backend directly
├── index.html    # UI markup
├── credentials.json  # Google Cloud service-account key (bundled as extraResource)
└── package.json  # electron-builder config: NSIS installer, dmg, protocol registration
```

---

## 4. The request lifecycle, end to end

Take a concrete request: a candidate applying to a job.

```
1. React component calls services/api.js → request('/jobs/<id>/apply', {method, body})
2. api.js prefixes REACT_APP_API_BASE, attaches `Authorization: Bearer <jwt>`,
   sets JSON headers only if the body is NOT FormData, sends fetch()
        │
        ▼  (network)
3. Flask receives it. before_request hooks run:
     - assign_request_id()  → g.request_id (reused from X-Request-ID header or minted)
     - handle_preflight()   → answers OPTIONS directly for CORS
4. Blueprint route matches: application_bp → POST /api/jobs/<id>/apply
5. @token_required decorator (middleware/auth_middleware.py):
     - reads the Bearer token (or ?token= for file views)
     - decodes it with JWT_SECRET_KEY (HS256), loads the user from Mongo
     - passes `current_user` into the view function (or 401)
6. The route validates the HTTP layer and calls ApplicationController.apply_for_job(...)
7. Controller does the business logic:
     - freezes a cv_snapshot, inserts the application (status: processing)
     - socketio.emit('application_update', {type:'created'}) to candidate + recruiter rooms
     - queues a background CV-scoring task
8. Route returns JSON. after_request hooks run:
     - add_request_id_header() → echoes X-Request-ID
     - after_request() → CORS headers for the response
9. Custom JSON provider serializes any bson.ObjectId / datetime automatically.
        │
        ▼  (network)
10. api.js reads the response; a 401 anywhere fires window 'auth:session-expired'
    → SessionExpiredHandler navigates to /login?expired=1
11. Meanwhile the BackgroundProcessor thread parses + AI-scores the CV, updates
    the application, emails the candidate, and emits another application_update.
    The candidate's dashboard (subscribed via useRealtimeApplications) patches
    the card in place — no refetch.
```

Every backend request flows through this same skeleton. The only routes that skip
`@token_required` are the public ones (register, login, verify-email, forgot/reset
password, google-oauth, invite lookup/redeem, the gaze-recorder page, health).

---

## 5. Backend architecture (Flask)

### Concept: Flask + blueprints

Flask is a minimal Python web framework. A **blueprint** is a group of related
routes you can register onto the app as a unit — GenHire uses one blueprint per
feature so the routing stays organized.

### Startup sequence (`app.py`, in order)

1. **Environment & logging** — force UTF-8 stdout (Windows emoji crash fix),
   silence TensorFlow/MediaPipe/glog noise, load `.env` via
   `config/env_loader.load_environment()`.
2. **Sentry** — `sentry_sdk.init()` called unconditionally; no-ops unless
   `SENTRY_DSN` is set.
3. **Flask config** — `SECRET_KEY` from `FLASK_SECRET_KEY` (refuses to boot in
   production without it; dev falls back to an insecure default with a warning);
   `MAX_CONTENT_LENGTH = 16 MB` rejects oversized bodies before reading them.
4. **Security headers** — `Flask-Talisman` (optional) with a CSP scoped to the
   API plus the GazeRecorder page. HTTPS redirect only when `FORCE_HTTPS=true`.
5. **Rate limiting** — `Flask-Limiter` (optional). Dev: effectively unlimited.
   Prod default: `200/day, 50/hour` per IP. Uses `REDIS_URL` if set, else
   in-process memory.
6. **JSON provider** — `_ObjectIdSafeJSONProvider` auto-serializes `ObjectId` and
   `datetime`, so routes can return raw Mongo docs without 500-ing. (Important:
   a 500 here would short-circuit `after_request` and *also* surface to the
   browser as a misleading CORS error — this provider prevents that class of bug.)
7. **Socket.IO + CORS** — bind the shared `socketio` from `extensions.py`;
   allowed origins come from `CORS_ORIGINS` (default localhost:3000). Note both a
   `flask_cors.CORS(...)` config *and* manual `after_request` CORS headers exist —
   belt and suspenders.
8. **Error handling & request IDs** — global exception handler returns JSON 500s
   with the request ID; `X-Request-ID` on every request/response.
9. **Database** — `db_config.connect()` + ensure indexes.
10. **Wallet bootstrap** — grant the signup bonus to any user missing a wallet
    (idempotent, every boot).
11. **Background workers** — start `BackgroundProcessor` (CV scoring queue),
    `InviteCleanupScheduler` (purge dormant burner accounts), and
    `InterviewRefundSweeper` (refund/auto-finalize abandoned interviews).
12. **Blueprint registration** — see table below.
13. **Interview system init** — build the global `InterviewSessionManager` with
    `InterviewConfig` + `LLMConfig` (Groq).
14. **Payment module init** — `init_payment_routes(db)` + register `payment_bp`,
    wrapped in try/except so the app still boots if payments fail to import.

### Route blueprints

| Blueprint | File | Prefix | Purpose |
|---|---|---|---|
| `auth_bp` | `routes/auth_routes.py` | `/api` | Register, login, email verify, password reset, Google OAuth, delete account |
| `profile_bp` | `routes/profile_routes.py` | `/api` | Profile & company profile, CV details, recruiter/candidate cost statistics |
| `job_bp` | `routes/job_routes.py` | `/api` | Job CRUD, AI JD generation, per-job applications |
| `application_bp` | `routes/application_routes.py` | `/api` | Apply/withdraw, status, CV view, interview report, score recalculation |
| `file_bp` | `routes/file_routes.py` | `/api` | Legacy uploads (photo, CV), admin file access |
| `cv_bp` | `routes/cv_routes.py` (factory) | `/api/cv` | Multi-CV management |
| `practice_bp` | `routes/practice_routes.py` | `/api/practice` | Practice interviews |
| `admin_bp` | `routes/admin_routes.py` | `/api/admin` | Full admin portal API |
| `speech_bp` | `routes/speech_routes.py` | `/api/speech` | Google STT/TTS proxy |
| `invite_bp` | `routes/invite_routes.py` | `/api` | Bulk invites + redemption |
| `payment_bp` | `payment_module/routes/payment_routes.py` | `/api/payment` | Plans, Razorpay, wallet, webhook |
| *(none)* | **`app.py` directly** | `/api/interviews` | Real interviews + all Socket.IO handlers |

**Routes are thin.** They validate the HTTP layer and delegate to a controller
class. The pattern to follow when adding a feature: add a route → call a controller
method → controller calls services / talks to Mongo → return JSON.

---

## 6. Authentication, authorization, and sessions

### Concept: JWT

A JSON Web Token is a signed string containing claims (here, the user ID). The
server signs it with a secret; anyone can read it but only the server can forge a
valid one. Being stateless, the server doesn't store sessions — it just verifies
the signature on each request.

### How GenHire does auth

- **Token creation:** on login/register/OAuth, the backend signs an HS256 JWT with
  `JWT_SECRET_KEY`, expiry `JWT_EXPIRATION_DAYS` (default 7).
- **Single decode path:** `middleware/auth_middleware.py` →
  `decode_user_from_token()` is used by **both** REST and Socket.IO, so auth logic
  never diverges between the two.
- **Where the token lives on the client:** `react-frontend/src/utils/sessionManager.js`
  keeps the JWT and user object in **tab-scoped** storage. `useAuth` exposes login
  state to components.
- **Attaching it:** `services/api.js` adds `Authorization: Bearer <jwt>` to every
  request. File-view endpoints also accept `?token=<jwt>` so a CV/photo can be
  opened in a new browser tab (where you can't set a header).
- **Expiry handling:** any `401` clears the session and dispatches a window
  `auth:session-expired` event; `SessionExpiredHandler` in `App.jsx` redirects to
  `/login?expired=1`.
- **Socket auth:** the JWT is passed in the Socket.IO handshake; invalid tokens are
  disconnected immediately. Tokenless connects are *allowed but get no user room* —
  needed for the mobile-camera QR page, which only joins session rooms.

### Authorization — role-based access

Users share one `users` collection, distinguished by `user_type`
(`candidate` | `recruiter` | `admin`). Decorators in `auth_middleware.py` enforce
access:

| Decorator | Meaning |
|---|---|
| `@token_required` | Any logged-in user (Bearer header or `?token=`) |
| `@candidate_required` | Must be a candidate |
| `@recruiter_required` | Must be a recruiter |
| `@verified_required` | Recruiter must be **admin-approved** (`is_verified`) — this is what blocks unapproved recruiters from posting jobs |
| `@admin_required` | Must be an admin |
| `@permission_required('x.y')` | Fine-grained admin permission; `*` = super admin |

**Three-stage recruiter trust model:** register → email verification (optional,
`REQUIRE_EMAIL_VERIFICATION`) → **admin approval** (`/admin/verification` →
`PUT /api/admin/users/<id>/verify`). Only after approval does `@verified_required`
let them post.

**Invite-only accounts** are a special candidate created by recruiter bulk invites:
`is_invite_only: true`, no email, login via a generated **Invite ID**
(`invite_id_lower`).

---

## 7. Middleware

`middleware/`:

- **`auth_middleware.py`** — all the JWT decorators above, plus the shared
  `decode_user_from_token()`.
- **`cors_middleware.py`** — `setup_cors()` helper (the app also applies CORS
  directly in `app.py`).
- **`input_validator.py`** — request payload validation helpers.
- **`rate_limiter.py`** — rate-limiting helpers for specific routes (in addition to
  the global Flask-Limiter defaults).

Cross-cutting request behavior (request IDs, preflight, CORS response headers, the
global exception handler) is wired as Flask `before_request`/`after_request`/
`errorhandler` hooks in `app.py` — see §5 and §21.

---

## 8. Controllers, services, and utilities

### Controllers (`controllers/`)

Business-logic classes called by routes. Key ones:

- `auth_controller.py`, `profile_controller.py`
- `job_controller.py` — job CRUD, `generate_jd_with_ai` (prompt and/or JD file)
- `application_controller.py` — apply/withdraw, status transitions, socket emits,
  interview report assembly
- `cv_controller.py`, `file_controller.py`
- `practice_controller.py` — practice sessions (reuses the interview engine)
- `admin_controller.py` — the whole admin portal
- `invite_controller.py`, `speech_controller.py`

### Services (`services/`)

| Service | Role |
|---|---|
| `background_processor.py` | One daemon thread + `queue.Queue` (no Celery/Redis). CV scoring runs here off the request path. |
| `cv_scoring_service.py` | AI CV-vs-JD scoring; also formats CV/JD text for the interview engine. |
| `cv_structured_parser_service.py` | Extracts structured fields (education, experience, skills) from raw CV text. |
| `pdf_parser_service.py` | PDF → text. |
| `gcs_service.py` | Google Cloud Storage upload/download (CV + JD files). |
| `email_service.py` + `email_providers/` | Transactional email (see §14). |
| `invite_service.py` | The invite system (see §15). |
| `invite_email_templates.py` | HTML invite emails. |
| `invite_cleanup_scheduler.py` | Purges dormant burner accounts. |
| `face_verification_service.py` | Face enroll/verify, quality gate, GridFS storage (see §12). |
| `interview_credit_service.py` | Interview credit refund lifecycle + `InterviewRefundSweeper` (see §10/§13). |
| `credit_service.py`, `interview_quota_service.py`, `candidate_practice_quota_service.py` | Credit/quota checks. |
| `usage_telemetry_service.py` | `record_usage_event()` — powers cost-statistics dashboards. |
| `google_speech_service.py` | Google STT/TTS behind `/api/speech/*`. |
| `llm_fallback_service.py` | Fallback chain when the primary LLM fails. |
| `recording_analysis_service.py` | Post-interview recording analysis — **currently disabled** (`RECORDING_ANALYZER_AVAILABLE = False`) due to heavy deps. |

### Utils (`utils/`)

- `ai_detection.py` — per-answer AI-generated probability.
- `cheating_detection.py`, `gaze_recorder_service.py` — proctoring analysis; the
  gaze service builds the GazeRecorder HTML page and turns gaze points into a
  cheating score + heatmap files.
- `helpers.py`, `validators.py`, `job_standards.py`, `interview_system.py`,
  `cv_score_migration.py` — shared helpers and one-off migration logic.

### Models (`models/`)

`user.py`, `job.py`, `application.py` are **plain-Python document helpers** — the
app uses PyMongo directly, there is no ORM. These files define document
construction/validation helpers, not schema-enforcing classes.

---

## 9. The database (MongoDB)

### Concept

MongoDB stores JSON-like documents in collections (no fixed schema, no joins).
GenHire uses **PyMongo directly** — no ODM/ORM. `config/database.py`
(`DatabaseConfig`) manages the connection: `MONGODB_URI`, `DATABASE_NAME` (default
`hrtech`), pooling `maxPoolSize=50`, `minPoolSize=0` (Atlas closes idle
connections, so we don't pre-open them), 10 s connect/selection timeouts, 30 s
socket timeout.

`db_config.get_collections()` returns the seven core collections; a few others are
accessed ad-hoc via `db.get_collection(...)`.

### Core collections

**`users`** — one doc per account (all roles). Key fields: `name`, `email`,
`email_lower`, `password` (hashed), `user_type`, `is_verified`, `is_active`,
`permissions` (`*` = super admin), `cv_details` (structured CV on the profile),
`is_invite_only` + `invite_id_lower` (burner accounts), `face_profile`
(`{image_file_id (GridFS), registered_at, source_session_id, source_application_id}`
— the permanent identity enrolled at the first real interview).

**`jobs`** — recruiter postings. Key fields: `title`, `company`, `department`,
`location`, `type`, `experience`, `salary`, `description`, `skills`,
`responsibilities`, `requirements`, `benefits`, `created_by` (recruiter id),
`minimum_cv_score` (auto-shortlist threshold, default 50), `proctoring_config`
(per-job toggles), denormalized status counters (`pending`, `interviewed`,
`screening_cleared`, `rejected`; `selected` is the legacy counter name), and JD file
fields (`jd_pdf_path` = `gs://` URI, `jd_gcs_path`, `jd_original_filename`,
`jd_extracted_text`, `jd_upload_date` — all `None` if no JD file was uploaded).

**`applications`** — one per candidate-job pair. Key fields: `job_id`,
`student_id`, `student_name`, `student_email`, `job_title`, `status`, `cv_snapshot`
(frozen CV: `text` + `details` + metadata), `cv_score` (0–100),
`minimum_cv_score_required` (snapshot of the threshold at scoring time — so later
edits don't retroactively change past decisions), `processing_status`
(`processing` / `awaiting_candidate`), `interview_score`, `proctoring_score`,
`proctoring_status`, `is_visible`, `identity_verification` (copied from the
interview), and `interview_refund_count` (drives refund-aware idempotency).

**`interviews`** — one per real AI interview. Key fields: `user_id`, `session_id`
(UUID), `application_id`, `recruiter_id`, `status`
(`active` → `completed` | `abandoned` | `identity_blocked`), `cv_path`/`jd_path`
(temp .txt files), `similarity_score`, `proctoring_config`, `proctoring_score`,
`proctoring_status`, `evaluation` (full AI object), `final_score`, `transcript`
(`[{role, text, ai_probability}]`), `manual_infractions`, `gaze_*`,
`recording_path`, `mobile_recording_path`, `usage_summary`, `usage_deduction`,
`start_time`, `identity_verification` (`{status, verified, distance, threshold,
attempts, checked_at, captured_image_file_id, reference_image_file_id}`),
`debit_idempotency_key`, `questions_answered_count`, and (auto-finalized docs)
`auto_finalized` / `abandoned_reason` / `credits_refund`.

**`practice_sessions`** — candidate practice interviews; analogous to `interviews`
but candidate-paid and not linked to an application.

**`invite_tokens`** — `token_hash` (SHA — raw tokens never stored), `user_id`,
`expires_at` (Mongo TTL auto-deletes).

**`invite_batches`** — one per bulk invite: counts of sent/valid/invalid/redeemed.

### Ad-hoc collections

`openai_cost_logs`, `speech_cost_logs` (cost tracking), plus usage-telemetry
events from `record_usage_event()`. Payment collections (`payment_module/models/`):
`plans`, `payments`, `subscriptions`, credit wallets, credit transactions.

### The status lifecycle (a subtle, important detail)

```
pending  ──►  shortlisted  ──►  interviewed  ──►  screening_cleared
   │             │                                     
   └──►  rejected (CV stage)         └──►  rejected (post-interview "not cleared")
```

`rejected` is **reused at two different points**. Both persist as
`status: "rejected"`. The frontend disambiguates using
`react-frontend/src/utils/applicationStatus.js`:
- no `interview_score` on the application → "**Not Shortlisted**" (CV rejection)
- an `interview_score` present → "**Screening Not Cleared**" (post-interview)

`normalizeStatus()` also folds the legacy `"selected"` into `"screening_cleared"`.
Any code that displays a status **must** go through this helper.

### Indexes (`_ensure_indexes()` on every boot)

| Collection | Index | Why |
|---|---|---|
| `users` | `uq_users_email_lower_real` — **unique + sparse** on `email_lower` | One real account per email, while invite burners (`email_lower: null`) can share. Legacy non-sparse email indexes are detected and dropped on boot. |
| `users` | `idx_users_email`, `uq_users_username_lower`, `uq_users_invite_id_lower`, `idx_users_is_invite_only` | Lookups + invite login + cleanup. |
| `invite_tokens` | `uq_invite_tokens_hash`, `idx_invite_tokens_user`, `ttl_invite_tokens_expires_at` (TTL) | Token lookup + auto-expiry. |
| `invite_batches` | recruiter / job / created_at | Batch status. |
| `applications` | `(job_id, is_visible)`, `(job_id, student_id)` | Recruiter dashboard query + "already applied?" check. |

All index creation is wrapped in try/except so legacy duplicate data never blocks
startup.

---

## 10. The AI interview engine

The heart of the product. Lives in `interview/` plus the routes and
Socket.IO handlers in `app.py`.

### Components

```
interview/
├── config/settings.py       # InterviewConfig, LLMConfig, LLMProvider
├── core/
│   ├── session_manager.py   # InterviewSessionManager — the engine
│   ├── prompt_based_question_generator.py
│   ├── llm_wrapper.py       # call_llm_with_tracking (cost-logged calls)
│   ├── cost_tracker.py      # per-session token/STT/TTS usage
│   ├── speech_cost_tracker.py
│   └── pricing.py           # model price tables
├── document/                # DocumentLoader — reads CV/JD text
├── llm/                     # provider clients + factory + fallback (Groq primary)
└── prompts/                 # greeting / experiential / technical / HR / closing prompts
evaluation_model/rubrics_eval/
├── answer_evaluator.py      # scores answer content vs rubrics
├── communication_evaluator.py  # scores language/communication
├── answer_classifier.py
└── rubric_generator.py, evaluation_system.py
utils/ai_detection.py        # per-answer "AI-generated?" probability
security_check.py            # per-frame MediaPipe + DeepFace analysis
```

The LLM is **Groq** (`GROQ_API_KEY`) with a fallback chain
(`llm/factory.py`, `llm/fallback_llm.py`, `services/llm_fallback_service.py`). The
model recorded for usage fallback is `llama-3.3-70b-versatile`.

### Session lifecycle (`InterviewSessionManager`)

**1. `create_session(cv_path, jd_path, ...)`**
- Generates a UUID `session_id`, starts a `CostTracker` session.
- Loads CV/JD text via `DocumentLoader`. Files were written to `uploads/tmp/` by
  the start route from trusted DB data, so validation is skipped
  (`pre_validated=True`).
- **Returns instantly** with a hardcoded first question — *"Hello, I'm Alex… give
  me a brief introduction about yourself"* — for zero-lag startup.
- A **background thread** then builds real conversation context from CV sections +
  JD (`initialize_conversation`), marks the greeting done, and advances the phase
  to `EXPERIENTIAL_QUESTIONS`. The session holds an `init_event` the answer path
  can wait on.
- Returns `question_timeout_seconds`, `question_deadline`, and `max_questions` for
  progress + pacing.

**2. `submit_answer(session_id, question, answer)`**
- Evaluates the answer and generates the next question, adapting difficulty/topic
  to the demonstrated `candidate_skill_level`, `current_topic`, `interview_phase`.
- Evaluation runs through `rubrics_eval` (answer quality + communication quality) +
  `ai_detection` (`ai_probability` per answer). Slow work runs on background
  threads (`bg_evaluate_and_update`) so the next question isn't blocked.
- Empty answers are legal — a client-side timeout submits `""` to advance.
- Every **non-empty** answer `$inc`s `questions_answered_count` on the interview
  doc — this drives the zero-answer refund decision and survives restarts.
- `_should_continue_interview` decides completion.

**3. Ending — `POST /api/interviews/<session_id>/end` (in `app.py`)**
- **Zero-answer discard:** no substantive answer → not scored; the recruiter's
  start-time debit is refunded idempotently, the interview becomes `abandoned`, the
  application keeps its prior status (candidate can retake), response
  `{status: "interview_discarded", refund: {...}}`.
- Otherwise `_generate_final_evaluation(session)` produces the evaluation object.
- **Interview score** = `round((answer_score*0.7 + language_score*0.3) * 100)` with
  fallbacks to `final_score` or conversation-summary averages.
- Transcript stored; media usage derived (TTS characters from assistant turns, STT
  seconds from duration) and logged via `CostTracker` + `record_usage_event`.
- Application updated (`status: "interviewed"`, scores), job counters `$inc`-synced,
  real-time `application_update` emitted to both rooms, and both parties emailed
  (fire-and-forget threads).

### Interview pacing (client-side, identical for real & practice)

- **Candidate never speaks** → 30 s countdown (`NO_ANSWER_TIMEOUT_SECONDS`) →
  auto-advance with *"No problem, let's move on."*
- **Candidate speaks, then silent** → 10 s (`POST_SPEECH_SILENCE_SECONDS`) →
  auto-submit.
- Substantive answers get a short spoken acknowledgement before the next question.

### Credit lifecycle & the refund sweeper (`interview_credit_service.py`)

Interviews are **charged at start** and refunded — always idempotently, key
`refund:<original-debit-key>` — whenever a session produces **zero substantive
answers**: start failed after the debit, identity block, abandonment, or `/end`
with nothing answered.

Once one real answer exists, the charge stands. Each real-interview refund `$inc`s
`interview_refund_count`, and the next `/start` derives a fresh debit key
(`real-interview:<app_id>:r<n>`) — replaying the original key after a refund would
return the old transaction and never re-charge.

The **`InterviewRefundSweeper`** daemon runs every
`INTERVIEW_REFUND_SWEEP_INTERVAL_MINUTES` (15) for sessions stuck in
`active`/`identity_blocked` past `INTERVIEW_ABANDON_TTL_MINUTES` (120):

| Stale session | Outcome |
|---|---|
| Real, has answers | **Auto-finalized** into a scored report (`auto_finalized: true`). No refund. |
| Real, no answers | Refunded + `abandoned`. |
| Practice, has answers | Closed `abandoned`, no refund. |
| Practice, no answers | Refunded + `abandoned`. |

### Practice interviews

`practice_routes.py` + `practice_controller.py` reuse the same engine for
candidate-paid mocks (`/api/practice/*`): same start/answer/end flow and pacing,
results in `practice_sessions`, charged to the **candidate's** wallet (30/50), face
check is soft (never blocks), same refund rules.

---

## 11. Resume (CV) parsing and scoring

### What it is

The automatic filter that turns "someone applied" into "shortlisted / rejected /
held for review", without a human reading every resume.

### How it works internally

When a candidate applies (`ApplicationController.apply_for_job`):
1. A **frozen `cv_snapshot`** (raw `text` + structured `details` + metadata) is
   attached to the application. Later profile edits never mutate a past application.
2. The application is saved `processing_status: "processing"` and a task is put on
   the `BackgroundProcessor` queue.
3. The worker thread (`services/background_processor.py`):
   - Parses the CV (`pdf_parser_service.py` for PDFs; `cv_structured_parser_service.py`
     for structure).
   - AI-scores CV vs JD (`cv_scoring_service.py`) → `cv_score` (0–100).
   - Decides: `shortlisted` if `cv_score >= job.minimum_cv_score`; `rejected` if
     clearly below; **`pending`** (held for manual review) if the score is below the
     threshold *but* CV-parsing confidence wasn't "high" — so a mis-parsed PDF isn't
     auto-rejected.
   - Emails the candidate the outcome and emits an `application_update`.

**Check score before applying:** `POST /api/jobs/<id>/check-cv-score {cv_id,
use_manual_cv}` runs the *same* scoring engine with no application created — an
honest preview, not a client-side random number.

### Files / APIs / data

- Files: `services/cv_scoring_service.py`, `cv_structured_parser_service.py`,
  `pdf_parser_service.py`, `background_processor.py`,
  `controllers/application_controller.py`.
- APIs: `POST /api/jobs/<id>/apply`, `POST /api/jobs/<id>/check-cv-score`,
  `POST /api/applications/<id>/recalculate-score`.
- Data: `applications.cv_snapshot`, `cv_score`, `minimum_cv_score_required`,
  `processing_status`, `status`.

### Edge cases & improvements

- **Edge case handled:** low score + low parse confidence → manual review, not
  auto-reject.
- **Improvement:** the background processor is a single in-process thread + queue —
  it doesn't survive a crash mid-task and doesn't scale horizontally. A production
  redesign would move to Celery/RQ + Redis or a Cloud Tasks queue.

---

## 12. Face verification and proctoring

### Face identity gate (`services/face_verification_service.py`)

`POST /api/interviews/<session_id>/register-face` acts as an identity gate before
any real interview:

1. **First real interview ever** → the captured selfie is enrolled as the account's
   permanent identity (GridFS + `users.face_profile`). Status `registered_new`.
2. **Every later real interview** (any company) → compared against the registered
   face with **DeepFace (VGG-Face)**: match → `verified`; mismatch → up to
   `FACE_VERIFY_MAX_ATTEMPTS` (3) retries, then **blocked** (interview status
   `identity_blocked`, HTTP 403 `face_mismatch_blocked`); blocked sessions are
   refunded by the sweeper.
3. A quality gate rejects no-face / multiple-face images before comparison.

Modes (`FACE_VERIFICATION_MODE`): `enforce` (default) / `monitor` (log, never
block) / `off`. If the DeepFace/OpenCV stack isn't installed, verification degrades
to photo capture (`unverified_system_unavailable`) — a missing dependency never
locks a candidate out. **Practice soft-verifies** (photo taken, mismatch never
blocks).

Captured (and reference) photos are served to the interview owner, the job's
recruiter, and admins via `GET /api/interviews/<sid>/face-image/{captured|reference}`.

### Proctoring — four independent signals

Per-job `proctoring_config`: `voice_detection`, `object_detection`,
`eyeball_tracking`, `gaze_heatmap`. If **any** are on, the interview costs 50
credits instead of 30.

1. **Live frame analysis (Socket.IO).** The kiosk emits `start_proctoring` then one
   `proctoring_frame` (base64 JPEG) per second. `security_check.analyze_frame_for_proctoring()`
   runs **MediaPipe head-pose** + **DeepFace identity** against the *registered*
   face (not just the session selfie — you can't enroll a stand-in for one session).
   Infractions lower a running score in the in-memory `live_sessions` dict;
   violations trigger a `proctoring_alert` back to the kiosk.
2. **GazeRecorder eye tracking (third-party CDN).** The backend serves
   `/api/interviews/<sid>/gaze-recorder-page` loading GazeCloud scripts from
   `app.gazerecorder.com`. Points are POSTed to `/gaze-recorder-results`;
   `gaze_recorder_service.analyze_gaze_patterns()` computes `cheatingScore`;
   `proctoring_score = 100 - cheatingScore`.
3. **Manual violations.** Tab switches / window blur / app switches detected
   client-side (in the kiosk, on window blur) are emitted as `proctoring_violation`
   and counted as `manual_<type>`.
4. **Mobile second camera.** A QR pairs the phone (`/mobile-cam/:sessionId`) to the
   session room; the desktop relays start/stop via `control_mobile_recording`; the
   phone uploads to `/api/interviews/<sid>/upload-mobile-recording`.

**Final proctoring score:** the **minimum** of the GazeRecorder-based score and the
live frame score (either catching a problem counts). If **neither** signal exists →
`null` + `proctoring_status: "incomplete"` — never a fabricated pass.

---

## 13. The payment module

Folder: `payment_module/`. Self-contained, registered at `/api/payment`. If it
fails to import, the rest of the app still boots (`PAYMENT_MODULE_AVAILABLE = False`).

```
payment_module/
├── config/settings.py         # PaymentConfig — env vars, prices, DEFAULT_PLANS
├── routes/payment_routes.py   # payment_bp
├── controllers/               # payment, plan, subscription, webhook
├── services/
│   ├── razorpay_service.py     # Razorpay SDK wrapper
│   ├── payment_service.py      # payment records + verification
│   ├── plan_service.py         # seeds DEFAULT_PLANS
│   ├── subscription_service.py # purchased packs
│   └── wallet_service.py       # THE credit ledger — every balance change goes here
├── models/                    # plan, payment, subscription, credit_wallet, credit_transaction
└── utils.py
```

### The credit model

Users hold **credits** in a wallet; actions debit it. Two audiences: `candidate`
and `recruiter`.

| Action | Credits | Paid by | Env var (default) |
|---|---|---|---|
| Signing up | +100 | — | `SIGNUP_BONUS_CREDITS=100` |
| Practice interview | −30 | Candidate | `CANDIDATE_PRACTICE_CREDITS=30` |
| Practice, proctored | −50 | Candidate | `CANDIDATE_PRACTICE_PROCTORED_CREDITS=50` |
| AI JD generation | −10 | Recruiter | `RECRUITER_AI_JD_CREDITS=10` |
| Real interview | −30 | **Recruiter** | `RECRUITER_REAL_INTERVIEW_CREDITS=30` |
| Real interview, proctored | −50 | **Recruiter** | `RECRUITER_REAL_INTERVIEW_PROCTORED_CREDITS=50` |

**Key decision: candidates never pay for real interviews** — the recruiter who
posted the job does. On start, the backend debits the *recruiter's* wallet and
writes a zero-credit audit transaction on the candidate side for traceability.

### Recharge packs (`DEFAULT_PLANS`, seeded on first run)

| Pack | Price | Credits | Audience |
|---|---|---|---|
| Candidate Pro | ₹499 | 500 | candidate |
| Candidate Max | ₹999 | 1,000 | candidate |
| Recruiter Pro | ₹4,999 | 5,000 | recruiter |
| Recruiter Max | ₹9,999 | 10,000 | recruiter |

Prices stored in **paise**; credits non-expiring (`validity_days: 36500`); currency
`PAYMENT_CURRENCY` (default INR).

### Purchase flow (Razorpay)

```
Frontend → POST /api/payment/recharge/initiate {plan_id}  → backend creates order
        ← order_id, key_id
useRazorpay opens Razorpay Checkout → user pays
Frontend → POST /api/payment/recharge/verify {order_id, payment_id, signature}
        → backend verifies HMAC signature, marks payment success, credits wallet
        → navigate to /payment/success
Independently: Razorpay → POST /api/payment/webhooks/razorpay (RAZORPAY_WEBHOOK_SECRET)
```

Both a browser-side verify **and** a server-to-server webhook confirm the payment,
so a closed browser doesn't lose a purchase. Test mode auto-detected from the
`rzp_test_` key prefix.

### `WalletService` — single source of truth

- `check_credit_availability(owner_id, audience, min_required_credits)` — pre-flight
  check; returns `can_start_interview`, `credits_remaining`, and a friendly
  `error_code`.
- `debit_wallet(...)` — atomic debit writing a `credit_transactions` ledger row with
  `transaction_type`, `reference_type`/`reference_id`, `metadata`, and — critically —
  an **`idempotency_key`** so retries never double-charge. Returns `balance_after`.
- `add_audit_transaction(...)` — zero-credit ledger entries (candidate-side record).
- `bootstrap_signup_bonus_for_all_users(...)` — idempotent, every boot.

The ledger (`credit_transactions`) is **append-only**; refunds use
`refund:<debit-key>` with types `real_interview_refund` / `practice_interview_refund`.

---

## 14. Email and notifications

### Email (`services/email_service.py` + `services/email_providers/`)

**Pluggable provider pattern:** `email_providers/base.py` defines the interface;
`mailgun.py`, `zeptomail.py`, and `noop.py` implement it. The active provider is
chosen by config. Mailgun is the primary transactional backend.

Emails sent: verification, password reset, invite emails
(`invite_email_templates.py`), application status changes, and interview-complete
notifications (**separate** emails to recruiter and candidate). All sends run on
**fire-and-forget daemon threads** so the request path never blocks on the mail
server — see the `threading.Thread(...).start()` calls in `app.py`'s `/end` route.

### In-app notifications = real-time socket events

There is no separate notification store — "notifications" are delivered as live
`application_update` socket events to the user's room (dashboards patch in place)
plus the transactional emails above. See §16.

---

## 15. The invite system

Lets a recruiter pull a known shortlist into a job instead of waiting for
applicants. Files: `services/invite_service.py`, `controllers/invite_controller.py`,
`routes/invite_routes.py`, `services/invite_cleanup_scheduler.py`,
`services/invite_email_templates.py`; frontend `components/recruiter/InviteCandidatesModal.jsx`,
`services/inviteApi.js`, `pages/InviteRedeem.jsx`.

```
1. Recruiter opens InviteCandidatesModal on a job
   → POST /api/recruiter/jobs/<job_id>/invites/preview  (paste text OR upload CSV/XLSX
      → emails parsed, classified valid/invalid)
2. POST /api/recruiter/jobs/<job_id>/invites  → for each email, InviteService:
   • creates/refreshes an invite token (SHA-hashed, TTL — Mongo expires it)
   • creates a "burner" invite-only user (Invite ID login; sparse unique index
     lets many share a null email)
   • creates a pre-shortlisted application skeleton (processing_status: "awaiting_candidate")
   • sends the invite email
   • all grouped under an invite_batches record
3. Recruiter polls GET .../invites/batches/<batch_id> for send/redeem status.
4. Candidate clicks the email link → /invite/redeem
   → GET  /api/invite/redeem?token=...   (lookup)
   → POST /api/invite/redeem             (consume: activates burner, hands over Invite ID)
5. Candidate logs in with the Invite ID, uploads a CV to complete the application,
   then interviews. Interview start is BLOCKED until the CV exists.
6. InviteCleanupScheduler periodically purges burner accounts that never activated.
```

Security detail: raw tokens are never stored — only `token_hash`. Mongo's TTL index
on `invite_tokens.expires_at` auto-deletes expired tokens.

---

## 16. Real-time updates (Socket.IO)

### Concept

Socket.IO is a WebSocket abstraction giving bidirectional events and "rooms"
(broadcast groups). It reconnects automatically and falls back to long-polling.

### How GenHire uses it

- The shared instance lives in `extensions.py` (`socketio = SocketIO(...)`) so
  controllers can `socketio.emit(...)` without importing `app.py` (no circular
  import). Handlers are registered in `app.py`.
- **`connect`** — JWT handshake; the user joins a room named by their user ID.
  Invalid tokens rejected; tokenless connects allowed but get no user room (needed
  for the mobile QR page).
- **`application_update`** (server → client) — pushed to candidate + recruiter rooms
  on apply / status change / score update. Payload `{type, application}` with type
  ∈ `created | status_changed | score_updated`.
- **Proctoring channel:** `start_proctoring`, `proctoring_frame`, `proctoring_alert`,
  `proctoring_violation` (see §12).
- **Mobile channel:** `join_mobile_session`, `control_mobile_recording`,
  `mobile_recording_action`, `mobile_status_update`, `mobile_status_dashboard`,
  `mobile_connected`.

**Frontend:** `services/socket.js` is a singleton
(`getAppSocket`/`connectAppSocket`/`disconnectAppSocket`).
`hooks/useRealtimeApplications.js` subscribes to `application_update` and calls
`onUpdate(type, application)`; dashboards patch their lists in place instead of
refetching. Per-page sockets in `Chat.jsx`/`MobileRecorder.jsx` are separate.

---

## 17. File uploads and storage

Two storage backends, by file type:

- **GridFS** (MongoDB's large-file store) — CV PDFs and face-identity photos.
  Served via `GET /api/files/<gridfs_id>` (defined in `app.py`).
- **Google Cloud Storage** (`services/gcs_service.py`) — CV files and uploaded JD
  files; served back through signed, time-limited URLs (`/api/jobs/<id>/jd-download`,
  `/api/cv/<id>/download-url`). GCS failure is **non-fatal** for job creation.

Local disk under `UPLOAD_FOLDER` (default `uploads/`):

- `uploads/proctoring/` — gaze plots + GazeRecorder payloads (`gaze_recorder/`)
- `uploads/recordings/` — webcam recordings (`<session>-<user>.webm`)
- `uploads/mobile_recordings/` — phone-camera recordings
- `uploads/tmp/` — temporary CV/JD `.txt` files fed to the interview pipeline

`MAX_CONTENT_LENGTH = 16 MB` rejects oversized bodies before they're read.

**Improvement:** local-disk artifacts under `uploads/` don't survive a Cloud Run
instance recycle (ephemeral filesystem). Recordings/plots that must persist should
move to GCS.

---

## 18. The frontend (React)

### Stack

React 19 on **Vite** (`vite`, `@vitejs/plugin-react`), `react-router-dom` v7, plain CSS
Modules (no UI framework), `socket.io-client`, `@react-oauth/google`, `chart.js` +
`react-chartjs-2` (cost dashboards), `lucide-react` (icons), `react-qr-code`,
`@ffmpeg/ffmpeg` (WASM, client media processing). Env vars keep the `REACT_APP_`
prefix — `vite.config.mjs` shims `process.env.REACT_APP_*` so the CRA → Vite move
touched no source files.

### App shell (`App.jsx`)

Provider nesting: `GoogleOAuthProvider` → `CandidateDataProvider` → `ErrorBoundary`
→ `Router`. All pages are **lazy-loaded** (`React.lazy` + `Suspense`) so each route
is its own chunk. `SessionExpiredHandler` listens for `auth:session-expired` and
redirects to `/login?expired=1`.

### Route map (abridged — full list in `App.jsx`)

| Path | Page | Who |
|---|---|---|
| `/` | LandingPage | public |
| `/login`, `/register`, `/recruiter-signup` | auth | public |
| `/verify-email`, `/forgot-password`, `/reset-password`, `/invite/redeem` | flows | public |
| `/dashboard`, `/profile`, `/practice`, `/job/:jobId`, `/application/:applicationId`, `/team` | candidate (inside `Layout`) | candidate |
| `/interview/:interviewId` | Interview (wraps `Chat`) | candidate |
| `/mobile-cam/:sessionId` | MobileRecorder (phone second cam) | candidate's phone |
| `/recruiter-dashboard`, `/recruiter/cost-statistics`, `/recruiter/team` | recruiter | recruiter |
| `/subscription`, `/candidate/subscription`, `/candidate/cost-statistics` | billing/usage | recruiter/candidate |
| `/payment/success`, `/payment/cancel` | post-Razorpay | any |
| `/admin`, `/admin/overview`, `/admin/candidates(/:id)`, `/admin/recruiters(/:id)`, `/admin/admins`, `/admin/verification`, `/admin/cost-statistics` | admin portal | admin |
| `/404`, `*` | NotFound | — |

### API layer (`src/services/`)

All backend communication is centralized — components never build URLs. `api.js`
holds `request()`/`requestBlob()` helpers that attach the JWT, set JSON headers only
for non-FormData bodies, and turn 401s into the session-expired event. Other files:
`adminApi.js`, `inviteApi.js`, `cvService.js`, `payment/paymentApi.js`, `socket.js`.

### The interview UI (`pages/Chat.jsx`, ~2,400 lines)

The in-browser interview experience, largely mirrored inside the kiosk's
`renderer.js`. It: starts the session (real or `/api/practice/*`), runs the identity
gate (selfie → `register-face`, handling `face_mismatch`/`face_mismatch_blocked`),
opens a socket and streams `proctoring_frame` 1/sec, plays questions via
`POST /api/speech/synthesize` (Google TTS), enforces the 30 s/10 s silence rules,
submits answers, records the webcam and uploads to `/upload-recording`, pairs a
phone via QR, runs GazeRecorder, and on finish `POST .../end` with three outcome
screens (normal result / retryable "Couldn't Finalize" / "Interview Not Recorded"
when `interview_discarded`).

### Status labels

Everything status-related goes through `utils/applicationStatus.js`
(`normalizeStatus()` + label maps). This is the one place that knows "rejected +
no interview score = Not Shortlisted" vs "rejected + interview score = Screening Not
Cleared", and folds legacy `"selected"` → `"screening_cleared"`.

---

## 19. The Secure Browser (Electron kiosk)

### Concept

Electron packages a Chromium renderer + a Node.js "main" process into a desktop app.
The **main** process has OS powers (windows, global shortcuts, kiosk mode); the
**renderer** is the web UI. They communicate over IPC, bridged safely by a
**preload** script.

### Launch flow

1. **Install** registers the app as the OS handler for `secure-interview://`
   (`package.json` → `build.protocols`).
2. **Deep link:** website navigates to `secure-interview://start?initData=<payload>`;
   OS launches (or focuses — single-instance lock) the kiosk.
3. **Payload handoff:** `main.js` parses `initData` and sends it to the renderer via
   `init-from-deeplink` IPC (handled on cold start via `process.argv` and while
   running via `second-instance`/`open-url`).
4. **Local HTTP server:** the main process serves `index.html` over
   `http://localhost:<random-port>` instead of `file://` — Google Speech APIs reject
   `file://` origins. (`webSecurity: false` also lets the renderer call the backend
   cross-origin.)
5. **Interview:** the renderer drives the whole thing against the backend directly;
   kiosk mode toggles on at start and off at end.

### Kiosk lockdown (`enable-kiosk`/`disable-kiosk`)

Fullscreen + always-on-top, non-closable/minimizable, force-focus. Blocks in-window
shortcuts (F12, Ctrl+Shift+I, F5, Ctrl+R, Ctrl+W, Ctrl+F4, Alt+F4) via
`before-input-event`; global shortcuts swallow Alt+Tab, Ctrl+Tab, Escape, Super+D,
Super+Tab, and virtual-desktop switches. **Emergency exit `Ctrl+Q`** always works
(with a confirmation dialog). On window **blur** it re-focuses and sends
`app-switched` → the renderer logs a proctoring violation. `get-display-info`
reports monitor count so the renderer can **flag** (not block) multi-monitor setups.

### Speech — local to the kiosk

Unlike the website (which uses `/api/speech/*`), the kiosk has its own Google Cloud
clients from `credentials.json` (bundled as an extraResource):
- **TTS** (`synthesize-speech`): tries voices `en-US-Journey-F` → `en-US-Neural2-C`
  → `en-US-Standard-C`, returns base64 MP3.
- **Streaming STT** (`start-stt-stream`/`audio-chunk`/`stop-stt-stream`): live
  `streamingRecognize` (WEBM_OPUS, 48 kHz, `latest_long`, punctuation, interim
  results); transcripts over `stt-on-transcript (text, isFinal)`.

### Preload bridge (`preload.js`)

`contextIsolation: true` + `nodeIntegration: false`. The renderer only gets
`window.electronAPI` with: `quitApp`, `enableKiosk`/`disableKiosk`,
`onInitDeepLink`, `synthesizeSpeech`, `startSTTStream`/`sendAudioChunk`/
`stopSTTStream`, `onTranscript`/`onSTTError`, `openExternal`, `onAppSwitched`,
`getDisplayInfo`. The renderer's `proctoring_violation` emits use **acknowledgements
+ a retry queue** so violations lost mid-reconnect are re-sent on the next connect.

### Building

```bash
cd secure-browser-kiosk
npm install
npm start          # dev
npm run dist       # Windows NSIS installer (Genhire.exe)
npm run dist:mac   # macOS universal dmg/zip
```

`credentials.json` (Google service account with Speech APIs) must be present at
build time.

---

## 20. Workflows

### Candidate workflow

Register/verify → build profile + CVs → (optional) check CV match score → apply →
async CV scoring auto-shortlists/rejects/holds → practice → real interview in the
secure browser (identity gate + proctoring) → results → buy credits as needed.

### Recruiter workflow

Sign up (3-step wizard) → **wait for admin approval** → set company profile →
post a job (manual, AI-from-prompt, or AI-from-JD-file) with `minimum_cv_score` +
`proctoring_config` → applicants auto-scored → (optional) bulk-invite a shortlist →
review candidate cards + interview reports (transcript, scores, AI-probability,
identity photos, gaze heatmap) → mark **Screening Cleared / Not Cleared** →
monitor spend on cost-statistics → recharge credits.

### Admin workflow

Approve/reject recruiters (`/admin/verification`) → manage users/jobs/applications →
manage other admins + permissions → view platform-wide cost statistics. Backed by
`admin_bp` (`/api/admin/*`, all `@admin_required`) and `AdminController`.

---

## 21. Error handling, validation, and logging

- **Global exception handler** (`app.py` `@app.errorhandler(Exception)`) — passes
  through `HTTPException`s, otherwise logs with the request ID + traceback and
  returns a clean JSON 500. Prevents a raw stack trace from leaking and prevents the
  "500 breaks CORS" trap.
- **Request correlation** — every request gets an `X-Request-ID` (reused from the
  header if a proxy set one), attached to logs/Sentry/response.
- **Refund-on-failure pattern** — the interview `/start` route wraps everything after
  the wallet debit so any failure calls `_refund_start_debit(...)`; no credits ever
  vanish on a failed start. Study this pattern before touching billable flows.
- **Validation** — `middleware/input_validator.py` + `utils/validators.py`; routes
  validate the HTTP layer and return 400s with clear messages.
- **Frontend** — `ErrorBoundary` around the app; per-page `Toast` for user-facing
  errors; `common/Loading`, `SkeletonCard`, `EmptyState` for states.
- **Logging** — Python `logging` to stdout (Cloud Run captures it); optional Sentry
  via `SENTRY_DSN`. TensorFlow/MediaPipe noise is deliberately silenced at startup.

---

## 22. Security

Implemented protections:

- **Password hashing** — never stored in plain text.
- **JWT** — HS256 signed with `JWT_SECRET_KEY`, 7-day expiry; single decode path for
  REST + sockets; 401 → forced re-login.
- **Production secret enforcement** — refuses to boot in `production` without
  `FLASK_SECRET_KEY`.
- **CORS restricted** — origins from `CORS_ORIGINS`; a wildcard + credentials
  combination (invalid per spec) was deliberately removed.
- **CSP / security headers** — Flask-Talisman with a scoped CSP; HSTS/HTTPS redirect
  when `FORCE_HTTPS=true`.
- **Rate limiting** — Flask-Limiter (per-IP; production 200/day, 50/hour).
- **Idempotent billing** — every debit/refund carries an idempotency key; refunds are
  append-only ledger entries.
- **Invite tokens** — SHA-hashed at rest, TTL-expired.
- **Sparse-unique email index** — one real account per email; invite burners exempt.
- **Face identity gate** — blocks impersonators from taking someone else's interview.
- **Kiosk lockdown** — OS-level anti-cheating during interviews.
- **Signed URLs** — CV/JD downloads via time-limited GCS signed URLs.
- **Speech endpoints authenticated** — they proxy paid Google APIs.
- **Payment double-confirmation** — signature-checked browser verify + signed webhook.

Weaknesses to be aware of (see §27): `webSecurity: false` in the kiosk, secrets in a
bundled `credentials.json`, no CSRF tokens (mitigated by Bearer-header auth), and
shared dev/prod infrastructure (per the project memory — treat both `.env` files as
touching live infra).

---

## 23. Configuration and environment variables

Backend (`python-backend/.env.example`) — the important ones:

| Variable | Used for |
|---|---|
| `MONGODB_URI`, `DATABASE_NAME` | Mongo connection (default DB `hrtech`) |
| `JWT_SECRET_KEY`, `JWT_EXPIRATION_DAYS` | Auth tokens |
| `FLASK_SECRET_KEY`, `FLASK_ENV` | Flask sessions; `production` enforces real secrets |
| `CORS_ORIGINS` | Allowed frontend origins (REST + WebSocket) |
| `REQUIRE_EMAIL_VERIFICATION` | Gate login behind email verification |
| `MAILGUN_API_KEY`, `MAILGUN_DOMAIN`, `MAILGUN_FROM_EMAIL` | Email |
| `FRONTEND_URL` | Links inside emails |
| `GOOGLE_CLIENT_ID` | Google OAuth verification |
| `GROQ_API_KEY` | LLM interview engine |
| `RAZORPAY_KEY_ID`/`_KEY_SECRET`/`_WEBHOOK_SECRET` | Payments |
| `SIGNUP_BONUS_CREDITS`, `CANDIDATE_PRACTICE_CREDITS`, `CANDIDATE_PRACTICE_PROCTORED_CREDITS`, `RECRUITER_AI_JD_CREDITS`, `RECRUITER_REAL_INTERVIEW_CREDITS`, `RECRUITER_REAL_INTERVIEW_PROCTORED_CREDITS` | Credit pricing (100/30/50/10/30/50) |
| `FACE_VERIFICATION_MODE`, `FACE_VERIFY_MAX_ATTEMPTS` | Face gate (`enforce`/`monitor`/`off`; default 3 attempts) |
| `INTERVIEW_ABANDON_TTL_MINUTES`, `INTERVIEW_REFUND_SWEEP_INTERVAL_MINUTES` | Refund sweeper (120 / 15) |
| `UPLOAD_FOLDER` | Local artifact root (default `uploads/`) |
| `REDIS_URL` | Optional shared rate-limit storage |
| `SENTRY_DSN` | Optional error tracking |
| `FORCE_HTTPS` | HTTPS redirect + HSTS via Talisman |

Frontend (`react-frontend/.env.example`):

| Variable | Purpose |
|---|---|
| `REACT_APP_API_URL` | Backend origin (Socket.IO + fetches) |
| `REACT_APP_API_BASE` | Optional full API base; defaults to `${REACT_APP_API_URL}/api` |
| `REACT_APP_GOOGLE_CLIENT_ID` | Google OAuth client id |

> **Project note (from team memory):** dev and prod share the same Mongo/GCP/API
> keys — there is **no dev/prod isolation**. Treat both `.env` files as touching
> live infrastructure.

---

## 24. Third-party integrations and libraries

| Integration | Why | Where |
|---|---|---|
| **Groq** | Fast LLM for question generation + evaluation | `interview/llm/`, `GROQ_API_KEY` |
| **Google Cloud Speech** | STT (spoken answers) + TTS (spoken questions) | `services/google_speech_service.py`, kiosk `main.js` |
| **Razorpay** | Payment gateway for credit packs | `payment_module/services/razorpay_service.py` |
| **Mailgun / ZeptoMail** | Transactional email (pluggable) | `services/email_providers/` |
| **Google Cloud Storage** | CV + JD file storage, signed URLs | `services/gcs_service.py` |
| **GridFS** | Large-file store in Mongo (CV PDFs, identity photos) | `app.py` `/api/files/<id>` |
| **GazeRecorder** | Third-party browser eye-tracking | `utils/gaze_recorder_service.py`, CDN `app.gazerecorder.com` |
| **MediaPipe + DeepFace (VGG-Face)** | Head-pose + face identity per frame | `security_check.py`, `face_verification_service.py` |
| **Sentry** | Optional error tracking | `app.py` (`SENTRY_DSN`) |
| **Flask-Talisman / Flask-Limiter** | Security headers + rate limiting | `app.py` |

Frontend libs: React 19, react-router v7, socket.io-client, @react-oauth/google,
chart.js + react-chartjs-2, lucide-react, react-qr-code, @ffmpeg/ffmpeg.

---

## 25. Build, run, and deployment

- **Backend dev:** `python app.py` → `socketio.run(app, host="0.0.0.0", port=5000)`.
- **Backend prod:** Cloud Run from `python-backend/Dockerfile` (Gunicorn + eventlet
  worker, `$PORT` default 8080), config in `gunicorn.conf.py` / `start_server.sh`.
- **Frontend:** `npm run dev` (Vite dev, port 3000; `npm start` aliases it);
  `npm run build` (output in `build/`); hosted on Vercel (`vercel.json` SPA rewrites).
- **Kiosk:** `npm start` (dev), `npm run dist` / `dist:mac` (installers).

**Cold-start mitigation:** Cloud Run scales to zero when idle; the next request pays
a cold-start penalty. `.github/workflows/keep-backend-warm.yml` pings `GET /health`
every 5 minutes (unauthenticated, no GCP creds). It's **best-effort** — the
guaranteed fix is `gcloud run services update <svc> --min-instances=1` (continuous
compute cost; not automated in this repo). Note GitHub disables scheduled workflows
after 60 days with no default-branch commits.

**No IaC / deploy automation is checked in** — deployment is manual `gcloud`/Cloud
Console.

---

## 26. Local setup

```bash
# 1. Backend (Python 3.11, needs MongoDB running + a .env)
cd python-backend
cp .env.example .env            # fill MONGODB_URI, JWT_SECRET_KEY, GROQ_API_KEY, etc.
pip install -r requirements.txt
python app.py                   # http://localhost:5000

# 2. Frontend
cd react-frontend
cp .env.example .env            # set REACT_APP_API_URL=http://localhost:5000
                                #     REACT_APP_GOOGLE_CLIENT_ID=...
npm install && npm run dev      # http://localhost:3000

# 3. Secure browser (only for interview flows)
cd secure-browser-kiosk
# place credentials.json (Google service account w/ Speech APIs)
npm install && npm start        # or: npm run dist → installer
```

Minimum to boot the API: a reachable `MONGODB_URI` and `JWT_SECRET_KEY`. Groq,
Razorpay, Mailgun, GCS, and Google Speech each degrade gracefully if unset — the app
still starts, those features just don't work. Create a super admin with
`python create_super_admin.py`. Useful one-off scripts live in `scripts/` (billing
smoke test, email smoke test, migrations, test-account cleanup, grant recruiter
credits).

---

## 27. Senior architect's review

An honest assessment of GenHire as it stands.

### Strengths

- **Clear separation of concerns.** Routes (thin) → controllers (logic) → services
  (integrations). Easy to find things and to test in isolation.
- **Robust billing.** Idempotency keys, append-only ledger, refund-on-failure,
  refund-count-aware debit keys, and a background sweeper for abandonment. This is
  the most carefully engineered part of the system, and rightly so — it's money.
- **Honest scoring.** Proctoring is `null`/"incomplete" when signals are missing
  rather than faked; CV rejections aren't mislabeled as interview outcomes;
  low-score-but-low-confidence CVs are held for review, not auto-rejected.
- **Real anti-cheating.** Face identity enrollment + per-frame verification + OS-level
  kiosk lockdown is a genuinely strong integrity story most "AI interview" products
  don't have.
- **Graceful degradation everywhere.** Payment module, DeepFace stack, GCS, Talisman,
  Limiter — each is optional and the app still boots without it.
- **Good operational hygiene.** Request IDs, a real DB-pinging health check, Sentry
  hook, and a keep-warm workflow.

### Weaknesses & scalability limits

- **Single-process background work.** `BackgroundProcessor`, `InviteCleanupScheduler`,
  and `InterviewRefundSweeper` are in-process daemon threads with an in-memory
  `queue.Queue`. They don't survive a crash, don't scale beyond one instance, and
  interact badly with Cloud Run scale-to-zero (a scaled-down instance stops
  sweeping). **Redesign:** external queue (Celery/RQ + Redis, or Cloud Tasks) and a
  separate always-on worker service.
- **In-memory interview + proctoring state.** `interview_manager.sessions` and
  `live_sessions` live in process memory. With more than one backend instance behind
  a load balancer, a candidate's frames could hit a different instance than their
  session. **Redesign:** sticky sessions, or externalize session state to Redis.
- **Ephemeral local storage.** `uploads/` recordings/plots vanish on instance
  recycle. **Redesign:** write all durable artifacts to GCS.
- **`app.py` is a 2,285-line god file.** Interview routes + all socket handlers +
  wiring live here. **Redesign:** extract an `interview_bp` blueprint and a
  `socket_handlers` module.
- **No automated tests.** The `test_*.py` files are manual scripts, not a CI suite.
  This is the biggest risk for a payments-and-scoring product. **Redesign:** pytest
  around the wallet/refund logic, the status lifecycle, and CV-scoring decisions;
  React Testing Library around `applicationStatus.js` and the interview UI states.
- **No dev/prod isolation** (per project memory) — dev and prod share Mongo/GCP/API
  keys. A dev mistake can hit live data. **Redesign:** separate projects/databases
  and per-environment secrets.
- **Kiosk security trade-offs.** `webSecurity: false` and a bundled
  `credentials.json` (a Google service-account key shipped inside the installer, and
  therefore extractable). **Redesign:** proxy all speech through the authenticated
  backend so no cloud key ships to the client, and tighten webSecurity.
- **Third-party proctoring dependency.** The GazeRecorder signal depends on a CDN
  script loading in the candidate's browser — brittle and privacy-sensitive.
- **Manual deployment.** No IaC. **Redesign:** Terraform + a CI/CD pipeline; set
  `--min-instances=1` declaratively.

### Security improvements

Ship speech through the backend (remove the client cloud key), add CSRF defenses if
any cookie auth is ever introduced, rotate `JWT_SECRET_KEY` with a revocation
strategy, add per-user (not just per-IP) rate limits on billable endpoints, and move
secrets to a secret manager with real environment separation.

### Performance optimizations

Externalize session/proctoring state to Redis; batch or downsample proctoring frames
adaptively; cache the plan catalog and job lists; add Mongo indexes for the
cost-statistics aggregation queries; consider a CDN in front of served files.

### Developer experience

Split `app.py`; add type hints + mypy on the backend and (ideally) migrate the
frontend to TypeScript; add a docker-compose for one-command local bring-up
(Mongo + backend + frontend); add pre-commit hooks and a real test suite in CI.

### Testing gaps (priority order)

1. Wallet debit/refund idempotency and the refund sweeper.
2. Application status lifecycle + label disambiguation.
3. CV-scoring shortlist/reject/hold decisions.
4. Face-verification enforce/monitor/off modes.
5. Interview end-state handling (normal / zero-answer discard / finalize failure).

### Recommended future enhancements

- Move background work to a proper queue + worker.
- Externalize interview/proctoring state → true horizontal scale.
- Full automated test suite in CI + real environment isolation.
- Extract interview logic out of `app.py` into a blueprint.
- Backend speech proxy to remove the shipped Google key.
- Analytics/reporting depth for recruiters (funnel conversion, time-to-clear,
  cost-per-hire).

---

*End of handbook. Pair this with the existing `docs/` folder — this handbook is the
narrative overview and design rationale; `docs/backend/api-reference.md` is the
exhaustive endpoint list, and `docs/data-flows.md` traces each journey step by step.*
