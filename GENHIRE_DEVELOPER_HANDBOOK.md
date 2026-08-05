# GenHire — Complete Developer Handbook

*Written as a knowledge-transfer document for an engineer joining the team
tomorrow. Read this end to end and you should be able to run GenHire locally,
find any feature in the code, understand why it's built the way it is, and start
shipping without needing to ask anyone.*

Everything here is derived from the actual repository. Where I teach a concept
from scratch, I then show exactly how GenHire uses it and which files implement
it.

*Verified against the codebase on **2026-08-06**. If this document and the code
ever disagree, the code is right — fix the document.*

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
| **Web frontend** | React 19 on Vite | `react-frontend/` | The website candidates, recruiters, and admins use |
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
  ┌─────────────────────►│      Flask Backend        │◄──► LLM chain: OpenAI→Gemini→Groq
  │                      │      (port 5000/8080)     │◄──► Google Cloud Speech (STT/TTS)
  │  WebSocket           │  - 15 route blueprints    │◄──► Razorpay (payments)
  │  (Socket.IO)         │  - payment_module         │◄──► ZeptoMail / Mailgun (email)
  │ ┌───────────────────►│  - interview engine       │◄──► Google Cloud Storage + GridFS
  │ │                    │  - proctoring + identity  │◄──► GazeRecorder CDN (eye tracking)
  │ │                    │    scoring                │
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
   through one HTTP core, `react-frontend/src/shared/api/client.js`, with each
   feature's endpoint functions living in its own `api/` folder. The core
   prefixes the API base, attaches the JWT, and converts any `401` into a
   global session-expired event.
2. **Frontend ↔ Backend (Socket.IO).** A single shared socket, authenticated
   with the JWT in the handshake. Each user sits in a room named by their user
   ID and receives `application_update` events (live dashboards).
3. **Frontend → Secure Browser (deep link).** Starting an interview navigates the
   browser to `secure-interview://start?initData=<encoded payload>`. The OS
   launches the installed Electron app, which registered itself as the handler
   for that custom URL scheme.
4. **Secure Browser → Backend (REST + Socket.IO).** The kiosk does **not** proxy
   through the website. Its renderer calls the same Flask endpoints directly and
   opens its own socket. Its Electron main process also talks to the backend —
   `/api/speech/synthesize` for TTS and `/api/speech/token` for a short-lived
   Google STT token — so **no Google service-account key ships in the installer**.
5. **Backend → External services.** The LLM chain (OpenAI → Gemini → Groq,
   ordered by `LLM_PROVIDER_PRIORITY`), Google Cloud Speech, Razorpay,
   ZeptoMail/Mailgun, Google Cloud Storage (+ GridFS for identity images),
   GazeRecorder.

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
├── app.py                # Entrypoint only. Calls create_app(), exposes `app`
│                         #   for gunicorn, and guards the dev reloader's
│                         #   double-boot. No wiring lives here.
├── core/                 # THE composition root
│   ├── factory.py        #   create_app() — every blueprint, CORS, workers
│   ├── bootstrap.py      #   UTF-8 stdout + TF/glog silencing (imported first)
│   ├── extensions.py     #   Shared SocketIO instance (avoids circular imports)
│   ├── config.py         #   Typed accessors for env settings
│   ├── security.py       #   JWT secret resolution
│   └── json_provider.py  #   ObjectId/datetime-safe JSON responses
├── extensions.py         # Legacy re-export of core/extensions.py — kept so the
│                         #   many `from extensions import socketio` lines work
├── config/               # env loading + Mongo connection/index management
│   ├── env_loader.py
│   └── database.py       # DatabaseConfig — connect(), get_collections(), _ensure_indexes()
├── routes/               # Flask blueprints — thin HTTP layer, one file per feature
│                         #   (incl. interview_routes, identity_routes, system, cost)
├── sockets/              # Socket.IO handlers: proctoring stream + mobile camera
├── controllers/          # Business logic classes (called by routes)
│   └── admin/            #   the admin portal split into domain mixins
├── services/             # Cross-cutting services (email, CV scoring, credits, GCS,
│   │                     #   invites, LLM chain, identity/face match, billing, exports)
│   └── email_providers/  # Pluggable email backends (zeptomail / mailgun / noop)
├── repositories/         # MongoDB data access (user/job/application/interview)
├── schemas/              # Pydantic request schemas (auth is the exemplar)
├── jobs/                 # runner.py — background worker lifecycle (start_all/stop_all)
├── middleware/           # Auth decorators, CORS, input validation, rate limiting
├── models/               # Plain-Python document helpers (no ORM): user, job, application
├── interview/            # The AI interview engine (see §10)
│   ├── runtime.py        # Process-wide singletons + staging dirs
│   ├── config/           # InterviewConfig, LLMConfig, LLMProvider
│   ├── core/             # session_manager, question generator, cost trackers, llm_wrapper
│   ├── llm/              # Provider clients + factory + fallback (OpenAI, Gemini, Groq)
│   ├── document/         # DocumentLoader/processor for CV/JD text
│   └── prompts/          # Prompt templates (greeting, technical, HR, closing, ...)
├── evaluation_model/     # Rubric-based answer & communication evaluators (IMPORTED
│   └── rubrics_eval/     #   by the app — ships in the Docker image)
├── payment_module/       # Self-contained credits/wallet/Razorpay package (see §13)
├── question_bank/        # CSV/JSON question banks by role & seniority
├── cv_jd_processing/     # Standalone FastAPI CV/JD scorer — NOT imported by the
│                         #   app, own requirements, excluded via .dockerignore
├── gpu_intensive_task/   # Standalone GPU proctoring server (face_verify.py,
│                         #   cheating_detection.py, yolov8n.pt) — also NOT imported
├── utils/                # ai_detection, gaze_recorder_service, company_resolver,
│                         #   validators, helpers, job_standards
├── scripts/              # route_manifest.py + baseline; migrations/ admin/ dev/ smoke/
├── security_check.py     # Per-frame MediaPipe + DeepFace proctoring analysis
├── requirements.txt      # Production deps (dev tooling in requirements-dev.txt)
├── Dockerfile            # Cloud Run image (Gunicorn + eventlet)
├── gunicorn.conf.py      # Production server config
├── start_server.sh       # Gunicorn + eventlet, 1 worker
└── .env.example          # The backend env vars you need to boot
```

**The single most important thing to understand:** the app is assembled by
`create_app()` in `core/factory.py`, and everything is a blueprint —
including the interview engine (`routes/interview_routes.py`). `app.py` holds
no wiring. Socket.IO handlers are the one exception to the blueprint rule:
they live in `sockets/` and are registered by `sockets.register_all()`. So:
routes → `routes/`, business logic → `controllers/`, shared work →
`services/`, real-time → `sockets/`, and the assembly order → `core/factory.py`.

> If you find older notes claiming `/api/interviews/*` and the socket handlers
> live inside a ~2,300-line `app.py`, that was the pre-2026-07 layout. It is
> gone.

### `react-frontend/src/` — why each folder exists

The frontend is **feature-based** since the 2026-07 reorganization — there is
no top-level `pages/`, `components/`, or `services/` any more:

```
src/
├── App.jsx               # Providers + router only (~20 lines)
├── index.js              # React root
├── app/                  # routes.jsx (every lazy route + guards), providers.jsx,
│                         #   ProtectedRoute.jsx, NotFound
├── features/             # one folder per domain, each with pages/ components/
│   ├── auth/             #   hooks/ api/ as needed
│   ├── candidate/        #   dashboard, profile (CVs + identity card), practice
│   ├── recruiter/        #   dashboard, team, invites, exports
│   ├── admin/            #   admin portal pages + panels
│   ├── interview/        #   Chat (the interview UI), lobby, mobile recorder,
│   │                     #   config/proctoring.js
│   ├── payment/          #   plans, checkout, subscription components
│   └── landing/
├── shared/               # cross-feature building blocks
│   ├── api/              #   client.js (THE request()), endpoints.js, socket.js
│   ├── components/       #   ui/ layout/ lists/ account/
│   ├── hooks/            #   useAuth, useDebounce
│   ├── utils/            #   session.js (JWT storage), applicationStatus.js,
│   │                     #   format.js, cvDetails.js, monthRange.js
│   └── constants/        #   jobTaxonomy, company, appLinks
└── assets/
```

Styling is **CSS Modules** (`*.module.css`), one per component — no Tailwind, no
MUI. Keep new components consistent with that.

### `secure-browser-kiosk/` — why each file exists

```
secure-browser-kiosk/
├── main.js       # Electron main process: window, kiosk lockdown, deep links,
│                 #   speech token broker + TTS proxy, local HTTP server (~450 lines)
├── preload.js    # contextBridge — the ONLY channel between renderer and main
├── renderer.js   # Interview UI logic (~2,070 lines) — talks to the backend directly
├── index.html    # UI markup + CDN scripts (webgazer, coco-ssd, socket.io, vad-web)
└── package.json  # electron-builder config: NSIS installer, dmg, protocol registration
```

A `credentials.json` remains in the working tree but is **excluded from the
build** (`"!credentials.json"`) and no longer read — speech auth is brokered
by the backend at runtime.

---

## 4. The request lifecycle, end to end

Take a concrete request: a candidate applying to a job.

```
1. React component calls a feature api/ function, which calls
   shared/api/client.js → request('/jobs/<id>/apply', {method, body})
2. client.js prefixes REACT_APP_API_BASE, attaches `Authorization: Bearer <jwt>`,
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
10. client.js reads the response; a 401 anywhere fires window
    'auth:session-expired' → SessionExpiredHandler navigates to /login?expired=1
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

### Startup sequence (`create_app()` in `core/factory.py`, in order)

1. **Environment & logging** — `core/bootstrap.py` (imported before anything
   heavy) forces UTF-8 stdout (Windows emoji crash fix) and silences
   TensorFlow/MediaPipe/glog noise; `.env` loads via
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
6. **JSON provider** — `core/json_provider.ObjectIdSafeJSONProvider` auto-serializes `ObjectId` and
   `datetime`, so routes can return raw Mongo docs without 500-ing. (Important:
   a 500 here would short-circuit `after_request` and *also* surface to the
   browser as a misleading CORS error — this provider prevents that class of bug.)
7. **Socket.IO + CORS** — bind the shared `socketio` from `core/extensions.py`;
   allowed origins come from `CORS_ORIGINS` (default localhost:3000). Note both a
   `flask_cors.CORS(...)` config *and* manual `after_request` CORS headers exist —
   belt and suspenders.
8. **Error handling & request IDs** — global exception handler returns JSON 500s
   with the request ID; `X-Request-ID` on every request/response.
9. **Database** — `db_config.connect()` + ensure indexes.
10. **GCS hard requirement** — boot **raises** unless Cloud Storage is
    configured. Deliberate: there is no local-disk fallback, so a
    misconfigured deploy must not come up and silently lose uploads.
11. **Wallet bootstrap** — grant the signup bonus to any user missing a wallet
    (idempotent, every boot).
12. **Interview runtime init** — importing `interview/runtime.py` builds the
    process-wide singletons: `InterviewSessionManager` (from `InterviewConfig`
    + `LLMConfig`, which defaults to OpenAI/`gpt-4o-mini`), the in-memory
    `live_sessions` store, the gaze service, and the staging folders.
13. **Background workers** — `jobs/runner.start_all()` starts
    `BackgroundProcessor` (CV scoring queue), `InviteCleanupScheduler` (purge
    dormant burner accounts), and `InterviewRefundSweeper` (refund/auto-finalize
    abandoned interviews). Skipped when `GENHIRE_DISABLE_JOBS=1`.
14. **Blueprint registration** — see table below.
15. **Payment module init** — `init_payment_routes(db)` + register `payment_bp`,
    wrapped in try/except so the app still boots if payments fail to import.
16. **Socket.IO handlers** — `sockets.register_all()`.

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
| `identity_bp` | `routes/identity_routes.py` | `/api` | One-time identity-card upload/status/image |
| `interview_bp` | `routes/interview_routes.py` (factory) | `/api` | Real interviews — `/api/interviews/*` |
| `system_bp` | `routes/system_routes.py` (factory) | — | `/`, `/health`, `/api/files/<gridfs_id>` |
| `cost_bp` | `routes/cost_routes.py` (factory) | — | LLM chat + STT/TTS cost logging |
| `payment_bp` | `payment_module/routes/payment_routes.py` | `/api/payment` | Plans, Razorpay, wallet, webhook |

Socket.IO handlers are **not** a blueprint — they live in `sockets/` and are
registered by `sockets.register_all()`.

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
- **Where the token lives on the client:** `react-frontend/src/shared/utils/session.js`
  keeps the JWT and user object in **tab-scoped** storage (keys overridable via
  `REACT_APP_TOKEN_KEY` / `REACT_APP_USER_KEY`). `shared/hooks/useAuth.js`
  exposes login state to components.
- **Attaching it:** `shared/api/client.js` adds `Authorization: Bearer <jwt>` to every
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
- **`cors_middleware.py`** — `setup_cors()` helper (the factory also applies
  CORS directly).
- **`input_validator.py`** — request payload validation helpers.
- **`rate_limiter.py`** — per-route `@rate_limit(max_calls, window_seconds,
  key_func=None)` decorator, separate from the global Flask-Limiter defaults —
  e.g. register 5/60s, login 10/60s, forgot-password 3/300s. Sliding window,
  shared via Redis when `REDIS_URL` is set. Keys by client IP except
  forgot-password, which keys by the **target email** (IP-keying collapses many
  real users into one bucket behind a proxy/CDN, and the real abuse vector
  there is spamming one inbox).

Cross-cutting request behavior (request IDs, preflight, CORS response headers, the
global exception handler) is wired as Flask `before_request`/`after_request`/
`errorhandler` hooks in `core/factory.py` — see §5 and §21.

---

## 8. Controllers, services, and utilities

### Controllers (`controllers/`)

Business-logic classes called by routes. Key ones:

- `auth_controller.py`, `profile_controller.py`
- `job_controller.py` — job CRUD, `generate_jd_with_ai` (prompt and/or JD file)
- `application_controller.py` — apply/withdraw, status transitions, socket emits,
  interview report assembly
- `cv_controller.py`, `file_controller.py`
- `saved_job_controller.py` — candidate job bookmarks
- `practice_controller.py` — practice sessions (reuses the interview engine)
- `admin_controller.py` + the `admin/` package — the admin portal, split into
  domain mixins (`user_admin`, `recruiter_admin`, `job_admin`,
  `application_admin`, `credit_admin`, `cost_stats_admin`, `cost_helpers`)
- `invite_controller.py`, `speech_controller.py`

Data access for the bigger domains goes through `repositories/`
(`user_repository.py`, `job_repository.py`, `application_repository.py`,
`interview_repository.py`, `recruiter_repository.py`, all on
`base_repository.py`) rather than raw collection calls in the controller.

### Services (`services/`)

| Service | Role |
|---|---|
| `background_processor.py` | One daemon thread + `queue.Queue` (no Celery/Redis). CV scoring runs here off the request path. |
| `cv_scoring_service.py` | AI CV-vs-JD scoring; also formats CV/JD text for the interview engine. |
| `cv_structured_parser_service.py` | Extracts structured fields (education, experience, skills) from raw CV text. |
| `pdf_parser_service.py` | PDF → text. |
| `gcs_service.py` | Google Cloud Storage upload/download/signed URLs — the only persistent artifact store; checked at boot. |
| `screening_export_service.py` | The per-job screening-cleared XLSX/CSV export. |
| `email_service.py` + `email_providers/` | Transactional email (see §14). |
| `invite_service.py` | The invite system (see §15). |
| `invite_email_templates.py` | HTML invite emails. |
| `invite_cleanup_scheduler.py` | Purges dormant burner accounts. |
| `identity_card_service.py` | The one-time candidate identity card: validation, GridFS storage, `users.identity_card` pointer (see §12). |
| `face_match_service.py` | Vision-LLM similarity between the identity card and the interview capture (see §12). |
| `face_verification_service.py` | Image-quality gate, GridFS face-image storage, and the DeepFace helpers used by live frame proctoring (see §12). |
| `interview_credit_service.py` | Interview credit refund lifecycle + `InterviewRefundSweeper` (see §10/§13). |
| `credit_service.py`, `interview_quota_service.py`, `candidate_practice_quota_service.py` | Credit/quota checks. |
| `usage_telemetry_service.py` | `record_usage_event()` — powers cost-statistics dashboards. |
| `google_speech_service.py` | Google STT/TTS behind `/api/speech/*`, plus the short-lived access token the kiosk uses for its own streaming STT. |
| `llm_fallback_service.py` | **THE** app-wide LLM chain — order from `LLM_PROVIDER_PRIORITY` (default `openai,gemini,groq`), quota detection, per-provider cooldowns, per-call model overrides. |
| `gcp_billing_service.py`, `openai_billing_service.py` | Real provider spend for the admin cost page (BigQuery billing export / OpenAI Costs API), falling back to `INFRA_MONTHLY_*` env estimates. |

### Utils (`utils/`)

- `ai_detection.py` — per-answer AI-generated probability.
- `gaze_recorder_service.py` — builds the GazeRecorder HTML page and turns gaze
  points into a cheating score + heatmap files.
- `company_resolver.py` — resolves a job's display company from the recruiter's
  current company profile, so renames don't leave stale names on old jobs.
- `helpers.py`, `validators.py`, `job_standards.py`, `cv_score_migration.py` —
  shared helpers and one-off migration logic.

Per-frame proctoring analysis is **not** in `utils/` — it's the backend-root
`security_check.py`.

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

`db_config.get_collections()` returns the eight core collections (`users`,
`jobs`, `applications`, `interviews`, `practice_sessions`, `invite_tokens`,
`invite_batches`, `saved_jobs`); a few others are accessed ad-hoc via
`db.get_collection(...)`.

### Core collections

**`users`** — one doc per account (all roles). Key fields: `name`, `email`,
`email_lower`, `password` (hashed), `user_type`, `is_verified`, `is_active`,
`permissions` (`*` = super admin), `cv_details` (structured CV on the profile),
`is_invite_only` + `invite_id_lower` (burner accounts), and `identity_card`
(`{image_file_id (GridFS), content_type, original_filename, uploaded_at,
uploaded_by}` — the one-time ID every real interview capture is scored
against). `face_profile` is **legacy**: nothing writes it any more; it is only
read to serve the `reference` image on interviews predating the ID-card flow.

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
(`active` → `completed` | `abandoned`; `identity_blocked` is a legacy value
nothing sets any more), `cv_path`/`jd_path` (transient staging .txt files under
the OS temp dir), `similarity_score`, `proctoring_config`, `proctoring_score`,
`proctoring_status`, `evaluation` (full AI object), `final_score`, `transcript`
(`[{role, text, ai_probability}]`), `manual_infractions`, `gaze_*`,
`recording_path`, `mobile_recording_path`, `usage_summary`, `usage_deduction`,
`start_time`, `identity_verification` (`{status: score_pending → scored |
score_unavailable | skipped, method: "llm_id_card_match", verified, matched,
score, threshold, model, match_reason, checked_at, scored_at,
captured_image_file_id, reference_image_file_id}`),
`debit_idempotency_key`, `questions_answered_count`, and (auto-finalized docs)
`auto_finalized` / `abandoned_reason` / `credits_refund`.

**`practice_sessions`** — candidate practice interviews; analogous to `interviews`
but candidate-paid and not linked to an application.

**`invite_tokens`** — `token_hash` (SHA — raw tokens never stored), `user_id`,
`expires_at` (Mongo TTL auto-deletes).

**`invite_batches`** — one per bulk invite: counts of sent/valid/invalid/redeemed.

**`saved_jobs`** — one per (candidate, job) bookmark: `candidate_id`, `job_id`,
`saved_at`, with a unique compound index making the save endpoint idempotent.

### Ad-hoc collections

`openai_cost_logs`, `speech_cost_logs` (cost tracking), `email_log` (one row
per outbound send — the admin cost page prices successful sends at
`ZEPTOMAIL_PER_EMAIL_COST_INR`), `payment_reconciliations` (the durable
lost-credit queue, §13), plus usage-telemetry events from
`record_usage_event()`. Payment collections (`payment_module/models/`):
`plans`, `payments`, `subscriptions`, credit wallets, credit transactions.
**GridFS** (`fs.files`/`fs.chunks`) holds identity cards, interview face
captures, and legacy CVs.

### The status lifecycle (a subtle, important detail)

```
pending  ──►  shortlisted  ──►  interviewed  ──►  screening_cleared
   │             │                                     
   └──►  rejected (CV stage)         └──►  rejected (post-interview "not cleared")
```

`rejected` is **reused at two different points**. Both persist as
`status: "rejected"`. The frontend disambiguates using
`react-frontend/src/shared/utils/applicationStatus.js`:
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
| `saved_jobs` | `uq_saved_jobs_candidate_job` (unique), `(candidate_id, saved_at desc)` | Idempotent bookmarking + "my saved jobs, newest first". |
| `email_log` | `(sent_at, success)` | Per-window successful-send count for the cost page. |

All index creation is wrapped in try/except so legacy duplicate data never blocks
startup.

---

## 10. The AI interview engine

The heart of the product. Lives in `interview/`, with its HTTP surface in
`routes/interview_routes.py` and its real-time surface in
`sockets/proctoring_sockets.py`.

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
├── llm/                     # provider clients + factory + fallback
│                            #   (openai_llm, gemini_llm, groq_llm, fallback_llm)
├── prompts/                 # greeting / experiential / technical / HR / closing prompts
└── runtime.py               # session manager singleton, live_sessions, staging dirs
evaluation_model/rubrics_eval/
├── answer_evaluator.py      # scores answer content vs rubrics
├── communication_evaluator.py  # scores language/communication
├── answer_classifier.py
└── rubric_generator.py, evaluation_system.py
utils/ai_detection.py        # per-answer "AI-generated?" probability
security_check.py            # per-frame MediaPipe + DeepFace analysis
```

**Which LLM runs where.** The session manager is built from `LLMConfig` in
`interview/config/settings.py`, which defaults to **OpenAI / `gpt-4o-mini`**
(`INTERVIEW_LLM_MODEL` or `OPENAI_MODEL` overrides it), with
`llm/factory.py` + `llm/fallback_llm.py` able to wrap several configs into a
failover chain. Everything *outside* the session manager — CV scoring, JD
generation, the ID-card face match — goes through the app-wide chain in
`services/llm_fallback_service.py`, ordered by `LLM_PROVIDER_PRIORITY`
(default `openai,gemini,groq`, reading `OPENAI_API_KEY` / `GOOGLE_API_KEY` /
`GROQ_API_KEY`).

### Session lifecycle (`InterviewSessionManager`)

**1. `create_session(cv_path, jd_path, ...)`**
- Generates a UUID `session_id`, starts a `CostTracker` session.
- Loads CV/JD text via `DocumentLoader`. Files were written to the transient
  staging dir `<os-temp>/genhire_staging/tmp/` by the start route from trusted
  DB data, so validation is skipped (`pre_validated=True`).
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

**3. Ending — `POST /api/interviews/<session_id>/end` (in `routes/interview_routes.py`)**
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
answers**: start failed after the debit, abandonment, or `/end` with nothing
answered.

Once one real answer exists, the charge stands. Each real-interview refund `$inc`s
`interview_refund_count`, and the next `/start` derives a fresh debit key
(`real-interview:<app_id>:r<n>`) — replaying the original key after a refund would
return the old transaction and never re-charge.

The **`InterviewRefundSweeper`** daemon (started by `jobs/runner.start_all()`)
runs every `INTERVIEW_REFUND_SWEEP_INTERVAL_MINUTES` (15) for sessions stuck in
`active` — or the legacy `identity_blocked` — past
`INTERVIEW_ABANDON_TTL_MINUTES` (120):

| Stale session | Outcome |
|---|---|
| Real, has answers | **Auto-finalized** into a scored report (`auto_finalized: true`). No refund. |
| Real, no answers | Refunded + `abandoned`. |
| Practice, has answers | Closed `abandoned`, no refund. |
| Practice, no answers | Refunded + `abandoned`. |

### Practice interviews

`practice_routes.py` + `practice_controller.py` reuse the same engine for
candidate-paid mocks (`/api/practice/*`): same start/answer/end flow and pacing,
results in `practice_sessions`, charged to the **candidate's** wallet (30/50).
Identity is capture-only for practice — no ID card required, no scoring, never
blocks. Same refund rules.

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

Identity is **advisory, not a gate**. It runs in two stages.

#### Stage 1 — the one-time identity card (`services/identity_card_service.py`)

The candidate uploads a government/institutional ID **once** on their profile
(`POST /api/identity-card`, JPEG/PNG/WebP ≤ 5 MB). It's stored in GridFS and
pointed at by `users.identity_card`. Candidates cannot replace it themselves;
only an admin can, via `PUT/DELETE /api/admin/candidates/<id>/identity-card`.

#### Stage 2 — background scoring at interview start

`POST /api/interviews/<session_id>/register-face`:

1. A **quality gate** rejects no-face / multiple-face images first.
2. **No identity card on the account → HTTP 403 `identity_card_required`.**
   This is the only identity condition that stops an interview.
3. Otherwise the capture is stored, `identity_verification.status` becomes
   `score_pending`, the session flips to `active`, and the endpoint **returns
   immediately**. A daemon thread (`_score_identity_async`) then sends the ID
   card + capture through the LLM chain on a vision model
   (`services/face_match_service.py`) for a 0–100 similarity against
   `FACE_MATCH_THRESHOLD` (default 75), writing back `scored` or
   `score_unavailable` onto the interview *and* the application.

**The score never blocks, delays, or fails an interview** — for any account
type. The recruiter sees the number and both photos and decides.
`FACE_VERIFICATION_MODE=off` skips capture and scoring entirely; `enforce` and
`monitor` currently behave identically. **Practice sessions** only capture (for
live proctoring) — no ID card required, no scoring.

Captured and reference photos are served to the interview owner, the job's
recruiter, and admins via `GET /api/interviews/<sid>/face-image/{captured|reference}`.

> **Legacy note.** This used to be a blocking DeepFace gate: first interview
> enrolled a selfie into `users.face_profile`, later ones verified against it,
> and repeated mismatches produced `face_mismatch` / `face_mismatch_blocked`
> and an `identity_blocked` interview. That flow is gone — the backend no
> longer returns those codes (the kiosk's `renderer.js` still carries dead
> branches for them).

### Proctoring — four independent signals

Per-job `proctoring_config`: `voice_detection`, `object_detection`,
`eyeball_tracking`, `gaze_heatmap`. If **any** are on, the interview costs 50
credits instead of 30.

1. **Live frame analysis (Socket.IO) — the WEB UI only.** The browser emits
   `start_proctoring` then one `proctoring_frame` (base64 JPEG) per second.
   `security_check.analyze_frame_for_proctoring()` runs **MediaPipe head-pose**
   + **DeepFace identity** against this session's own capture, held in the
   in-memory `live_sessions` dict; infractions lower a running score and
   violations trigger a `proctoring_alert` back to the client. MediaPipe and
   DeepFace are deliberately **absent from `requirements.txt`** — in
   production this signal is simply unavailable and the score falls back to
   the gaze signal. **The kiosk does not use this path**: it runs MediaPipe
   FaceLandmarker + a coco-ssd phone detector locally in `renderer.js` and
   relays only the resulting violations.
2. **Gaze tracking.** The backend serves
   `/api/interviews/<sid>/gaze-recorder-page` loading GazeCloud scripts from
   `app.gazerecorder.com` (the kiosk runs `webgazer` locally instead). Points
   are POSTed to `/gaze-recorder-results`;
   `gaze_recorder_service.analyze_gaze_patterns()` computes `cheatingScore`;
   `proctoring_score = 100 - cheatingScore`.
3. **Manual violations.** Tab switches / window blur / app switches detected
   client-side (in the kiosk, on window blur) are emitted as `proctoring_violation`
   and counted as `manual_<type>`. The kiosk sends these with acknowledgements
   and a retry queue so none are lost across a reconnect.
4. **Mobile second camera.** A QR pairs the phone (`/mobile-camera/:sessionId`,
   hidden when `MOBILE_RECORDING_ENABLED=false`) to the session room; the
   desktop relays start/stop via `control_mobile_recording`; the phone uploads
   to `/api/interviews/<sid>/upload-mobile-recording`.

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
| Bulk invite, per candidate | −1 | Recruiter | `RECRUITER_INVITE_CREDITS_PER_CANDIDATE=1` (charged upfront; failed emails auto-refund) |

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
`zeptomail.py`, `mailgun.py`, and `noop.py` implement it. The active provider is
chosen by `EMAIL_PROVIDER`. **ZeptoMail is the primary backend**, Mailgun the
fallback, `noop` for local dev.

Emails sent: verification, password reset, invite emails
(`invite_email_templates.py`), application status changes, and interview-complete
notifications (**separate** emails to recruiter and candidate). All sends run on
**fire-and-forget daemon threads** so the request path never blocks on the mail
server — see the `threading.Thread(...).start()` calls in the `/end` route in
`routes/interview_routes.py`.

Every send is written to the **`email_log`** collection (`sent_at`, `success`)
by `EmailService._log_send`; the admin cost page counts successful sends per
window and prices them at `ZEPTOMAIL_PER_EMAIL_COST_INR` (default 0.015).

### In-app notifications = real-time socket events

There is no separate notification store — "notifications" are delivered as live
`application_update` socket events to the user's room (dashboards patch in place)
plus the transactional emails above. See §16.

---

## 15. The invite system

Lets a recruiter pull a known shortlist into a job instead of waiting for
applicants. Files: `services/invite_service.py`, `controllers/invite_controller.py`,
`routes/invite_routes.py`, `services/invite_cleanup_scheduler.py`,
`services/invite_email_templates.py`; frontend
`features/recruiter/components/InviteCandidatesModal.jsx`,
`features/recruiter/api/inviteApi.js`, `features/auth/pages/InviteRedeem.jsx`.

```
1. Recruiter opens InviteCandidatesModal on a job
   → POST /api/recruiter/jobs/<job_id>/invites/preview  (paste text OR upload CSV/XLSX
      → emails parsed, classified valid/invalid)
2. POST /api/recruiter/jobs/<job_id>/invites  → charges 1 credit per invitee
   (RECRUITER_INVITE_CREDITS_PER_CANDIDATE) upfront, then per email InviteService:
   • creates/refreshes an invite token (SHA-hashed, TTL — Mongo expires it)
   • creates a "burner" invite-only user (Invite ID login; sparse unique index
     lets many share a null email)
   • creates a pre-shortlisted application skeleton (processing_status: "awaiting_candidate")
   • sends the invite email (a row whose email fails is auto-refunded; the
     invite/link still exists for manual sharing)
   • all grouped under an invite_batches record
3. Recruiter polls GET .../invites/batches/<batch_id> for send/redeem status.
4. Candidate clicks the email link → /invite/redeem
   → GET  /api/invite/redeem?token=...   (lookup)
   → POST /api/invite/redeem             (consume: activates burner, hands over Invite ID)
5. Candidate logs in with the Invite ID, uploads a CV to complete the application
   and an identity card on their profile, then interviews. Interview start is
   BLOCKED until both exist.
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

- The shared instance lives in `core/extensions.py` (`socketio = SocketIO(...)`)
  so controllers can `socketio.emit(...)` without importing the app factory (no
  circular import). A root-level `extensions.py` re-exports it so the many
  existing `from extensions import socketio` lines keep working. Handlers live
  in `sockets/` and are registered by `sockets.register_all()`.
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

**Frontend:** `shared/api/socket.js` is a singleton
(`getAppSocket`/`connectAppSocket`/`disconnectAppSocket`).
`features/candidate/hooks/useRealtimeApplications.js` subscribes to `application_update` and calls
`onUpdate(type, application)`; dashboards patch their lists in place instead of
refetching. Per-page sockets in `Chat.jsx`/`MobileRecorder.jsx` are separate.

---

## 17. File uploads and storage

**There is no persistent local disk, and no `uploads/` directory.** This was a
deliberate change: an ephemeral Cloud Run filesystem silently lost artifacts on
every instance recycle.

- **Google Cloud Storage** (`services/gcs_service.py`) — the store for every
  persistent artifact: CVs, uploaded JD files, webcam recordings, phone-camera
  recordings, gaze plots and GazeRecorder payloads. It is **mandatory**:
  `create_app()` raises at boot if `GCS_BUCKET_NAME` +
  `GOOGLE_APPLICATION_CREDENTIALS`/`GCS_SERVICE_ACCOUNT_KEY` aren't set.
  Artifacts come back through `GET /api/view-file` (auth required,
  bucket-scoped) or signed, time-limited URLs
  (`/api/jobs/<id>/jd-download`, `/api/cv/<id>/download-url`). A GCS failure is
  still **non-fatal for job creation** — the job is created without a
  downloadable JD.
- **GridFS** (MongoDB's large-file store) — the one exception: identity-card
  images, interview face captures, and legacy CVs. Served via
  `GET /api/identity-card/image`,
  `GET /api/interviews/<sid>/face-image/<kind>`, and the legacy
  `GET /api/files/<gridfs_id>` (in `routes/system_routes.py`).

**Transient staging only**, rooted in the OS temp dir (not the app tree), set up
by `interview/runtime.py` and deleted right after upload:

```
<os-temp>/genhire_staging/
├── proctoring/          # gaze plots; gaze_recorder/ for raw payloads
├── recordings/          # webcam recordings before upload
├── mobile_recordings/   # phone-camera recordings before upload
└── tmp/                 # CV/JD .txt files fed to the interview pipeline
```

`MAX_CONTENT_LENGTH = 16 MB` rejects oversized bodies before they're read.

**Improvement:** GCS objects accumulate forever — there are no lifecycle rules
yet. See [cost.md](cost.md) §6.

---

## 18. The frontend (React)

### Stack

React 19 on **Vite** (`vite`, `@vitejs/plugin-react`), `react-router-dom` v7, plain CSS
Modules (no UI framework), `socket.io-client`, `@react-oauth/google`, `chart.js` +
`react-chartjs-2` (cost dashboards), `lucide-react` (icons), `react-qr-code`,
`@ffmpeg/ffmpeg` (WASM, client media processing). Env vars keep the `REACT_APP_`
prefix — `vite.config.mjs` shims `process.env.REACT_APP_*` so the CRA → Vite move
touched no source files.

### App shell (`App.jsx` + `src/app/`)

`App.jsx` is ~20 lines: providers + router. Provider nesting (`app/providers.jsx`):
`GoogleOAuthProvider` → `CandidateDataProvider` → `ErrorBoundary` → `Router`.
Every route is declared in `app/routes.jsx` and **lazy-loaded** (`React.lazy` +
`Suspense`) so each route is its own chunk. `SessionExpiredHandler` listens for
`auth:session-expired` and redirects to `/login?expired=1`.

### Route map (abridged — full list in `app/routes.jsx`)

| Path | Page | Who |
|---|---|---|
| `/` | LandingPage | public |
| `/login`, `/register`, `/recruiter-signup` | auth | public |
| `/verify-email`, `/forgot-password`, `/reset-password`, `/invite/redeem` | flows | public |
| `/dashboard`, `/profile`, `/practice`, `/jobs/:jobId`, `/applications/:applicationId`, `/team` | candidate (inside `Layout`) | authenticated |
| `/interviews/:interviewId` | Interview (identity-card lobby wrapping `Chat`) | candidate |
| `/mobile-camera/:sessionId` | MobileRecorder (phone second cam) | candidate's phone |
| `/recruiter/dashboard`, `/recruiter/cost-statistics`, `/recruiter/team` | recruiter | recruiter |
| `/recruiter/subscription`, `/candidate/subscription`, `/candidate/cost-statistics` | billing/usage | recruiter/candidate |
| `/payment/success`, `/payment/cancel` | post-Razorpay | any |
| `/admin`, `/admin/overview`, `/admin/candidates(/:id)`, `/admin/recruiters(/:id)`, `/admin/admins`, `/admin/verification`, `/admin/cost-statistics`, `/admin/credit-statistics` | admin portal (one persistent `AdminLayoutOutlet`) | admin |
| `/404`, `*` | NotFound | — |

Legacy paths renamed in the 2026-07 reorg — `/recruiter-dashboard`,
`/subscription`, `/job/:id`, `/application/:id`, `/interview/:id`,
`/mobile-cam/:id` — permanently redirect to their successors with params and
query preserved, so old emails and bookmarks keep working.

### API layer (`shared/api/` + per-feature `api/`)

All backend communication is centralized — components never build URLs.
`shared/api/client.js` holds the `request()`/`requestBlob()`/`authedFetch()`
core that attaches the JWT, sets JSON headers only for non-FormData bodies, and
turns 401s into the session-expired event. `shared/api/endpoints.js` covers
cross-role calls; each feature keeps the rest in its own `api/` folder
(`features/admin/api/adminApi.js`, `features/recruiter/api/inviteApi.js` and
`jobExportApi.js`, `features/candidate/api/cvService.js` and
`identityCardApi.js`, `features/auth/api/authApi.js`,
`features/payment/api/paymentApi.js`). `shared/api/socket.js` is the singleton
socket.

### The interview UI (`features/interview/pages/Chat.jsx`, ~2,900 lines)

The in-browser interview experience, largely mirrored inside the kiosk's
`renderer.js`. It: starts the session (real or `/api/practice/*`), does the
identity capture (selfie → `register-face`; only `identity_card_required` stops
the flow — the similarity score is computed in the background and never
blocks), opens a socket and streams `proctoring_frame` 1/sec, plays questions
via `POST /api/speech/synthesize` (Google TTS), enforces the 30 s/10 s silence
rules, submits answers, records the webcam and uploads to `/upload-recording`,
pairs a phone via QR, runs GazeRecorder, and on finish `POST .../end` with three
outcome screens (normal result / retryable "Couldn't Finalize" / "Interview Not
Recorded" when `interview_discarded`).

### Status labels

Everything status-related goes through `shared/utils/applicationStatus.js`
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

### Speech — brokered by the backend, no bundled key

The kiosk uses the **same** `/api/speech/*` endpoints as the website, authorized
by the interview JWT from the deep link (`main.js` keeps `{apiUrl, token}` via
`captureBackendSession`). Shipping a service-account key in a user-installed app
would have handed every candidate a usable GCP key.
- **TTS** (`synthesize-speech`): POSTs to `/api/speech/synthesize`, trying
  voices `en-US-Journey-F` → `en-US-Neural2-C` → `en-US-Standard-C`, returns
  base64 MP3.
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

No credentials setup is required at build time — the kiosk gets its backend URL
and JWT from the deep link at runtime, so a build is reproducible from a clean
checkout. `npm start` runs Electron directly; the full website→kiosk handoff
needs the `secure-interview://` protocol registered, which only happens when you
install a built package.

---

## 20. Workflows

### Candidate workflow

Register/verify → build profile + CVs + the one-time identity card → (optional)
check CV match score → apply → async CV scoring auto-shortlists/rejects/holds →
practice → real interview in the secure browser (identity capture + proctoring)
→ results → buy credits as needed.

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

- **Global exception handler** (`core/factory.py` `@app.errorhandler(Exception)`) — passes
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
  errors; `shared/components/ui/` `Loading`, `SkeletonCard`, `EmptyState` for states.
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
- **Identity evidence** — a locked, one-time ID card plus a per-interview
  similarity score gives the recruiter proof of who sat the interview. Note it
  **records**, it does not block; the deterrent is that the score reaches the
  recruiter, not that the system refuses to proceed.
- **Kiosk lockdown** — OS-level anti-cheating during interviews.
- **No GCP key in the desktop installer** — the kiosk gets a short-lived Google
  access token from `/api/speech/token`, so a user-installed app never carries a
  service-account key.
- **Signed URLs** — CV/JD downloads via time-limited GCS signed URLs.
- **Speech endpoints authenticated** — they proxy paid Google APIs.
- **Payment double-confirmation** — signature-checked browser verify + signed webhook.

Weaknesses to be aware of (see §27): `webSecurity: false` in the kiosk, JWTs
passed in URL query params for file/report links, no CSRF tokens (mitigated by
Bearer-header auth), and **dev/prod are not actually isolated** — both `.env`
files currently point at the same Atlas cluster and GCS bucket, so treat every
local run as touching live infrastructure.

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
| `EMAIL_PROVIDER` | `zeptomail` (primary) · `mailgun` (fallback) · `noop` (dev) |
| `ZEPTOMAIL_API_KEY`/`_FROM_EMAIL`/`_FROM_NAME`, `MAILGUN_API_KEY`/`_DOMAIN`/`_FROM_EMAIL` | Email credentials |
| `FRONTEND_URL` | Links inside emails |
| `GOOGLE_CLIENT_ID` | Google OAuth verification |
| `LLM_PROVIDER_PRIORITY` | Chain order, default `openai,gemini,groq` |
| `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `GROQ_API_KEY` | Provider keys (Gemini reads `GOOGLE_API_KEY`) |
| `LLM_OPENAI_MODEL`, `LLM_GEMINI_MODEL`, `LLM_GROQ_MODEL` | Per-provider default models |
| `FACE_MATCH_THRESHOLD`, `FACE_MATCH_{OPENAI,GEMINI,GROQ}_MODEL` | ID-card match threshold (75) + vision model per provider |
| `INVITE_TOKEN_SECRET`, `INVITE_DEFAULT_VALIDITY_DAYS`, `INVITE_SCOPED_JWT_TTL_HOURS`, `INVITE_CLEANUP_INTERVAL_HOURS` | Invite tokens + burner lifecycle |
| `MOBILE_RECORDING_ENABLED` | Phone second camera (default `true`) |
| `RAZORPAY_KEY_ID`/`_KEY_SECRET`/`_WEBHOOK_SECRET` | Payments |
| `SIGNUP_BONUS_CREDITS`, `CANDIDATE_PRACTICE_CREDITS`, `CANDIDATE_PRACTICE_PROCTORED_CREDITS`, `RECRUITER_AI_JD_CREDITS`, `RECRUITER_REAL_INTERVIEW_CREDITS`, `RECRUITER_REAL_INTERVIEW_PROCTORED_CREDITS`, `RECRUITER_INVITE_CREDITS_PER_CANDIDATE` | Credit pricing (100/30/50/10/30/50/1) |
| `PLAN_*_PRICE_PAISE`, `PLAN_*_CREDITS` | Recharge pack prices/credits, synced to Mongo every boot |
| `GCS_BUCKET_NAME`, `GOOGLE_APPLICATION_CREDENTIALS` | Cloud Storage — **mandatory**, boot fails without it |
| `ZEPTOMAIL_PER_EMAIL_COST_INR` | Per-email price on the admin cost page (0.015) |
| `FACE_VERIFICATION_MODE` | `enforce` (default) / `monitor` / `off` — `off` skips identity capture; none of them block |
| `INTERVIEW_ABANDON_TTL_MINUTES`, `INTERVIEW_REFUND_SWEEP_INTERVAL_MINUTES` | Refund sweeper (120 / 15) |
| `GCP_BILLING_EXPORT_BQ_TABLE`, `OPENAI_ADMIN_API_KEY`, `INFRA_MONTHLY_*` | Real/estimated spend on the admin cost page |
| `REDIS_URL` | Optional shared rate-limit storage |
| `SENTRY_DSN` | Optional error tracking |
| `FORCE_HTTPS` | HTTPS redirect + HSTS via Talisman |
| `GENHIRE_DISABLE_JOBS` | `1` skips the background daemons (tooling / dev-reloader watcher) |

There is no `UPLOAD_FOLDER` any more — see §17.
`FACE_VERIFICATION_MODE`, the sweeper knobs, `REDIS_URL`, `SENTRY_DSN`, the
billing vars and `INFRA_MONTHLY_*` are read by code but **not** listed in
`.env.example`; all have defaults or degrade gracefully.

Frontend (`react-frontend/.env`):

| Variable | Purpose |
|---|---|
| `REACT_APP_API_URL` | Backend origin (Socket.IO + fetches) |
| `REACT_APP_API_BASE` | Optional full API base; defaults to `${REACT_APP_API_URL}/api` |
| `REACT_APP_GOOGLE_CLIENT_ID` | Google OAuth client id |
| `REACT_APP_TOKEN_KEY`, `REACT_APP_USER_KEY` | Storage keys for the JWT / user record |
| `REACT_APP_KIOSK_DOWNLOAD_URL` | Installer link shown when the kiosk isn't installed |

> **Dev/prod isolation is not in place.** Two backend env files exist
> (`.env`, `.env.production`) but as of 2026-08-06 both point at the same Atlas
> cluster (`hrtech.kdo8zml.mongodb.net`) and the same GCS bucket
> (`genhireuploads`). Treat both as touching live infrastructure.

---

## 24. Third-party integrations and libraries

| Integration | Why | Where |
|---|---|---|
| **OpenAI / Gemini / Groq** | One env-ordered failover chain behind every LLM task | `services/llm_fallback_service.py`, `interview/llm/` |
| **Google Cloud Speech** | STT (spoken answers) + TTS (spoken questions); the kiosk proxies through the backend | `services/google_speech_service.py`, `/api/speech/*` |
| **Razorpay** | Payment gateway for credit packs | `payment_module/services/razorpay_service.py` |
| **ZeptoMail / Mailgun** | Transactional email (pluggable, ZeptoMail primary) | `services/email_providers/` |
| **Google Cloud Storage** | All persistent artifacts, signed URLs; mandatory at boot | `services/gcs_service.py` |
| **GridFS** | Identity cards, interview face captures, legacy CVs | `identity_card_service.py`, `routes/system_routes.py` |
| **GazeRecorder / WebGazer** | Browser eye-tracking (CDN for the web UI, local `webgazer` in the kiosk) | `utils/gaze_recorder_service.py`, `app.gazerecorder.com` |
| **MediaPipe + DeepFace** | Head-pose + per-frame identity. **Not in `requirements.txt`** — imported lazily, absent in production | `security_check.py`, `face_verification_service.py` |
| **BigQuery / OpenAI Costs API** | Real provider spend on the admin cost page | `gcp_billing_service.py`, `openai_billing_service.py` |
| **Sentry** | Optional error tracking | `core/factory.py` (`SENTRY_DSN`) |
| **Flask-Talisman / Flask-Limiter** | Security headers + rate limiting | `core/factory.py` |

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
python -m venv venv && venv\Scripts\activate   # ALWAYS use the venv
cp .env.example .env            # fill MONGODB_URI, JWT_SECRET_KEY, GCS_*, an LLM key
pip install -r requirements.txt
python app.py                   # http://localhost:5000

# 2. Frontend
cd react-frontend
# create .env with REACT_APP_API_URL=http://localhost:5000
#                  REACT_APP_GOOGLE_CLIENT_ID=...
npm install && npm run dev      # http://localhost:3000

# 3. Secure browser (only for interview flows) — no credentials file needed
cd secure-browser-kiosk
npm install && npm start        # or: npm run dist → installer
```

Minimum to boot the API: a reachable `MONGODB_URI`, `JWT_SECRET_KEY`, **and a
configured GCS bucket** — Cloud Storage is the one hard requirement, and
`create_app()` raises without it. The LLM keys, Razorpay, email, and Google
Speech each degrade gracefully if unset: the app still starts, those features
just don't work. Run everything through `python-backend/venv/Scripts/python.exe`
— a global Python lacks the `google-cloud-*` packages and the boot-time GCS
check will fail.

Create a super admin with `python scripts/admin/create_super_admin.py`. One-off
scripts live under `scripts/`: `migrations/` (schema/data migrations),
`admin/` (super admin, test-account cleanup, grant recruiter credits),
`smoke/` (billing + email smoke tests), `dev/` (locust load tests, ad-hoc
integration scripts), and `route_manifest.py` (dumps the live URL map and diffs
it against `route_manifest.baseline.json` — run it after touching routes).

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
- **Real anti-cheating.** A locked one-time ID card, a per-interview similarity
  score surfaced to the recruiter, and OS-level kiosk lockdown make a stronger
  integrity story than most "AI interview" products. Note the identity leg is
  now *evidence*, not enforcement.
- **Clean composition root.** `core/factory.py` assembles everything in one
  readable place; `app.py` is a thin entrypoint. The 2026-07 reorg also moved
  the interview engine and socket handlers out of the old god-file.
- **Graceful degradation everywhere.** Payment module, DeepFace stack, Talisman,
  Limiter — each is optional and the app still boots without it. GCS is the
  deliberate exception: it fails the boot rather than silently losing uploads.
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
- **Unbounded object storage.** Artifacts now correctly live in GCS rather than
  an ephemeral disk, but there are no lifecycle rules, so recordings accumulate
  (and bill) forever. **Redesign:** GCS lifecycle rules — delete after the
  retention window, Nearline after 30 days.
- **Chat.jsx is a ~2,900-line god component.** The interview UI carries session
  setup, identity capture, sockets, TTS/STT, pacing, recording, QR pairing, gaze
  and three end-states in one file. **Redesign:** decompose by responsibility;
  this also clears the remaining `exhaustive-deps` warnings and unlocks a
  stricter lint gate.
- **No automated tests.** The `scripts/dev/test_*.py` files are manual scripts,
  not a CI suite. This is the biggest risk for a payments-and-scoring product.
  **Redesign:** pytest around the wallet/refund logic, the status lifecycle, and
  CV-scoring decisions; React Testing Library around `applicationStatus.js` and
  the interview UI states.
- **No dev/prod isolation.** Both `.env` and `.env.production` currently point at
  the same Atlas cluster and the same GCS bucket, so a dev mistake hits live
  data. **Redesign:** stand up the prod cluster + `genhire-uploads-prod` bucket
  and repoint `.env.production`.
- **Kiosk security trade-off.** `webSecurity: false` is still on. (The bundled
  Google key is **fixed** — speech now goes through the authenticated backend
  and no cloud key ships in the installer.) **Redesign:** tighten webSecurity.
- **Third-party proctoring dependency.** The GazeRecorder signal depends on a CDN
  script loading in the candidate's browser — brittle and privacy-sensitive.
- **Manual deployment.** No IaC. **Redesign:** Terraform + a CI/CD pipeline; set
  `--min-instances=1` declaratively.

### Security improvements

Replace the `?token=` query-param auth on file/report links with short-lived
signed URLs (URLs leak into logs and history), add CSRF defenses if any cookie
auth is ever introduced, rotate `JWT_SECRET_KEY` with a revocation strategy, add
per-user (not just per-IP) rate limits on billable endpoints, and move secrets to
a secret manager with real environment separation. Also swap the dev
`rzp_live_...` Razorpay keys for test-mode keys so local testing can't touch the
live account.

### Performance optimizations

Externalize session/proctoring state to Redis; batch or downsample proctoring frames
adaptively; cache the plan catalog and job lists; add Mongo indexes for the
cost-statistics aggregation queries; consider a CDN in front of served files.

### Developer experience

Decompose `Chat.jsx` and `RecruiterDashboard.jsx`; add type hints + mypy on the
backend and (ideally) migrate the frontend to TypeScript; add a docker-compose
for one-command local bring-up (Mongo + backend + frontend); add pre-commit
hooks and a real CI job (`lint:ci` + Vite build + the backend
import/route-manifest check) — today the only workflow is the keep-warm ping.

### Testing gaps (priority order)

1. Wallet debit/refund idempotency and the refund sweeper.
2. Application status lifecycle + label disambiguation.
3. CV-scoring shortlist/reject/hold decisions.
4. Identity flow: `identity_card_required` gating, and that a low similarity
   score never blocks.
5. Interview end-state handling (normal / zero-answer discard / finalize failure).

### Recommended future enhancements

- Move background work to a proper queue + worker.
- Externalize interview/proctoring state → true horizontal scale.
- Full automated test suite in CI + real environment isolation.
- GCS lifecycle rules so recordings don't grow unbounded.
- An admin view + alert for unresolved `payment_reconciliations` rows.
- Decompose `Chat.jsx`.
- Analytics/reporting depth for recruiters (funnel conversion, time-to-clear,
  cost-per-hire).

*(Already done, listed here because older notes still call for them: extracting
the interview logic into `interview_bp`, and proxying speech through the backend
so no Google key ships in the kiosk.)*

---

*End of handbook. Pair this with the existing `docs/` folder — this handbook is the
narrative overview and design rationale; `docs/backend/api-reference.md` is the
exhaustive endpoint list, and `docs/data-flows.md` traces each journey step by step.*
