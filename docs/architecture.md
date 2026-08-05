# System Architecture — How Everything Connects

GenHire is an AI-powered hiring platform made of **three applications** that talk to each other:

| Application | Technology | Folder | Role |
|---|---|---|---|
| Backend API | Python / Flask + Flask-SocketIO | `python-backend/` | All business logic, database, AI interview engine, payments, proctoring |
| Web Frontend | React 19 (Vite) | `react-frontend/` | The website candidates, recruiters, and admins use |
| Secure Browser | Electron (desktop app) | `secure-browser-kiosk/` | Locked-down kiosk that runs the actual AI interview |

## The Big Picture

```
                        ┌─────────────────────────────┐
                        │        MongoDB              │
                        │  users, jobs, applications, │
                        │  interviews, invites,       │
                        │  wallets, payments, ...     │
                        └────────────▲────────────────┘
                                     │ PyMongo
                                     │
   HTTPS (REST /api/*)   ┌───────────┴───────────────┐    External services
  ┌─────────────────────►│      Flask Backend        │◄──► LLM chain: OpenAI → Gemini → Groq
  │                      │      (port 5000)          │◄──► Google Cloud Speech (STT/TTS)
  │  WebSocket           │                           │◄──► Razorpay (payments)
  │  (Socket.IO)         │  - 15 route blueprints    │◄──► ZeptoMail (emails)
  │ ┌───────────────────►│  - payment_module         │◄──► Google Cloud Storage (all artifacts)
  │ │                    │  - interview engine       │◄──► GazeRecorder (eye tracking)
  │ │                    │  - proctoring + identity  │
  │ │                    │    scoring                │
  │ │                    └───────────▲───────────────┘
  │ │                                │ REST + Socket.IO
┌─┴─┴──────────────┐                 │ (same API, called directly)
│  React Frontend  │    deep link    │
│  (browser SPA)   ├────────────────►┌──────────────────────┐
│                  │ secure-         │  Secure Browser      │
│  candidate /     │ interview://    │  (Electron kiosk)    │
│  recruiter /     │ start?initData= │                      │
│  admin UIs       │                 │  runs the interview  │
└──────────────────┘                 └──────────────────────┘
```

## How the three apps communicate

### 1. Frontend → Backend (REST)
Every page in the React app calls the Flask API over HTTP. All calls go
through one HTTP core (`react-frontend/src/shared/api/client.js`) used by
each feature's `api/` module; the client:
- prefix requests with `REACT_APP_API_BASE` (or `REACT_APP_API_URL` + `/api`),
- attach the JWT as `Authorization: Bearer <token>`,
- on a `401` response, clear the session and fire a global
  `auth:session-expired` event that redirects the user to `/login?expired=1`.

### 2. Frontend ↔ Backend (Socket.IO, real-time)
A single shared Socket.IO connection (`react-frontend/src/shared/api/socket.js`) authenticates
with the JWT during the handshake. The backend puts each connected user in a
room named after their own user id, then pushes `application_update` events
(`created` / `status_changed` / `score_updated`) so recruiter and candidate
dashboards update live without refreshing.

### 3. Frontend → Secure Browser (deep link)
When a candidate starts an interview (real or practice), the React app builds
a custom-protocol URL:

```
secure-interview://start?initData=<encoded payload>
```

(see `features/candidate/pages/Profile.jsx` and
`features/candidate/pages/Practice.jsx`). The OS launches the
installed Electron app, which is registered as the handler for the
`secure-interview://` scheme. The payload carries everything the kiosk needs
(auth token, API URL, application/practice context).

### 4. Secure Browser → Backend (REST + Socket.IO)
The kiosk does **not** proxy through the website. Its renderer calls the same
Flask API directly:
- `POST /api/interviews/start`, `/answer`, `/end` (or `/api/practice/...` in practice mode)
- Socket.IO events `start_proctoring`, `proctoring_frame`, `proctoring_violation`, and mobile-camera relay events.

### 5. Backend → External services
- **LLM chain (OpenAI → Gemini → Groq)** — one env-ordered failover chain
  (`LLM_PROVIDER_PRIORITY`, default `openai,gemini,groq`) behind *every* LLM
  task: interview questions, answer evaluation, CV parse/score, JD generation,
  and the ID-card face match. Quota errors fail over with a per-provider
  cooldown.
- **Google Cloud Speech** — speech-to-text and text-to-speech, always via the backend (`/api/speech/*`). The kiosk proxies TTS through the same endpoint and gets a short-lived Google access token from `/api/speech/token` for its streaming STT — it ships no service-account key.
- **Razorpay** — payment gateway for credit recharge packs (checkout + webhook).
- **ZeptoMail** (Mailgun sandbox fallback) — transactional email (verification, invites, status updates, interview results); every send is logged for usage-based cost tracking.
- **Google Cloud Storage** — mandatory, and the only store for persistent artifacts (CVs, JDs, recordings, gaze data). Identity-card images and interview face captures are the exception: they live in MongoDB GridFS.
- **GazeRecorder (app.gazerecorder.com)** — third-party browser eye-tracking used for the gaze heatmap proctoring signal on the web interview UI (the kiosk runs WebGazer locally instead).

## User roles

| Role | Entry point | What they can do |
|---|---|---|
| Candidate | `/dashboard`, `/practice`, `/profile` | Browse jobs, save jobs, upload CVs, upload a one-time identity card (required before any real interview), apply, take practice + real AI interviews, buy candidate credit packs |
| Recruiter | `/recruiter/dashboard` | Post jobs (with AI JD generation), review applications and interview reports, mark candidates **Screening Cleared** / **Not Cleared** (one-click XLSX/CSV export of the cleared list per job), invite candidates in bulk, buy recruiter credit packs |
| Admin | `/admin/*` | Verify recruiters, manage users/jobs/applications, view platform cost statistics |
| Invite-only candidate | `/invite/redeem` | A "burner" account created by a recruiter invite; logs in with an Invite ID instead of email |

## The credit economy (summary)

Everything costly runs on **credits** held in per-user wallets
(`payment_module`). Defaults (all configurable via env vars):

- Signup bonus: **100 credits**
- Candidate practice interview: **30** (or **50** with proctoring)
- Recruiter AI job-description generation: **10**
- Real interview (charged to the **recruiter** who owns the job): **30** (or **50** with proctoring)

Bulk-inviting a candidate costs the recruiter **1 credit** per invitee
(auto-refunded if the email fails to send).

Interviews are charged when they **start** and refunded automatically —
always idempotently — if the session ends with **zero answers** (candidate
never spoke, browser crashed, the start failed after the debit). A
background sweeper also refunds or auto-finalizes sessions abandoned
mid-interview. Credits are bought via Razorpay recharge packs. See
[backend/payment-module.md](backend/payment-module.md).

## Where to go next

- [backend/overview.md](backend/overview.md) — backend in simple terms
- [backend/backend-detailed.md](backend/backend-detailed.md) — every blueprint, service, and middleware
- [backend/api-reference.md](backend/api-reference.md) — every endpoint
- [backend/database.md](backend/database.md) — MongoDB collections and indexes
- [backend/interview-engine.md](backend/interview-engine.md) — how the AI interview + proctoring works
- [backend/payment-module.md](backend/payment-module.md) — Razorpay, wallets, credits
- [frontend/overview.md](frontend/overview.md) / [frontend/frontend-detailed.md](frontend/frontend-detailed.md)
- [secure-browser/overview.md](secure-browser/overview.md) / [secure-browser/secure-browser-detailed.md](secure-browser/secure-browser-detailed.md)
- [data-flows.md](data-flows.md) — end-to-end journeys (apply → interview → report)
- [onboarding.md](onboarding.md) — set up and run everything locally
