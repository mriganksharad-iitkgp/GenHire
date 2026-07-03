# System Architecture — How Everything Connects

GenHire is an AI-powered hiring platform made of **three applications** that talk to each other:

| Application | Technology | Folder | Role |
|---|---|---|---|
| Backend API | Python / Flask + Flask-SocketIO | `python-backend/` | All business logic, database, AI interview engine, payments, proctoring |
| Web Frontend | React 19 (Create React App) | `react-frontend/` | The website candidates, recruiters, and admins use |
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
  ┌─────────────────────►│      Flask Backend        │◄──► Groq (LLM interviews)
  │                      │      (port 5000)          │◄──► Google Cloud Speech (STT/TTS)
  │  WebSocket           │                           │◄──► Razorpay (payments)
  │  (Socket.IO)         │  - 10 route blueprints    │◄──► Mailgun (emails)
  │ ┌───────────────────►│  - payment_module         │◄──► Google Cloud Storage (CV files)
  │ │                    │  - interview engine       │◄──► GazeRecorder (eye tracking)
  │ │                    │  - proctoring (MediaPipe/ │
  │ │                    │    DeepFace)              │
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
through a small set of centralized service files
(`react-frontend/src/services/`) that:
- prefix requests with `REACT_APP_API_BASE` (or `REACT_APP_API_URL` + `/api`),
- attach the JWT as `Authorization: Bearer <token>`,
- on a `401` response, clear the session and fire a global
  `auth:session-expired` event that redirects the user to `/login?expired=1`.

### 2. Frontend ↔ Backend (Socket.IO, real-time)
A single shared Socket.IO connection (`services/socket.js`) authenticates
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

(see `pages/Profile.jsx` and `pages/Practice.jsx`). The OS launches the
installed Electron app, which is registered as the handler for the
`secure-interview://` scheme. The payload carries everything the kiosk needs
(auth token, API URL, application/practice context).

### 4. Secure Browser → Backend (REST + Socket.IO)
The kiosk does **not** proxy through the website. Its renderer calls the same
Flask API directly:
- `POST /api/interviews/start`, `/answer`, `/end` (or `/api/practice/...` in practice mode)
- Socket.IO events `start_proctoring`, `proctoring_frame`, `proctoring_violation`, and mobile-camera relay events.

### 5. Backend → External services
- **Groq** — LLM that generates interview questions and evaluates answers.
- **Google Cloud Speech** — speech-to-text and text-to-speech (backend `/api/speech/*`; the kiosk also has its own direct Google Cloud clients).
- **Razorpay** — payment gateway for credit recharge packs (checkout + webhook).
- **Mailgun** — transactional email (verification, invites, status updates, interview results).
- **Google Cloud Storage / GridFS** — CV file storage.
- **GazeRecorder (app.gazerecorder.com)** — third-party browser eye-tracking used for the gaze heatmap proctoring signal.

## User roles

| Role | Entry point | What they can do |
|---|---|---|
| Candidate | `/dashboard`, `/practice`, `/profile` | Browse jobs, upload CVs, apply, take practice + real AI interviews, buy candidate credit packs |
| Recruiter | `/recruiter-dashboard` | Post jobs (with AI JD generation), review applications and interview reports, invite candidates in bulk, buy recruiter credit packs |
| Admin | `/admin/*` | Verify recruiters, manage users/jobs/applications, view platform cost statistics |
| Invite-only candidate | `/invite/redeem` | A "burner" account created by a recruiter invite; logs in with an Invite ID instead of email |

## The credit economy (summary)

Everything costly runs on **credits** held in per-user wallets
(`payment_module`). Defaults (all configurable via env vars):

- Signup bonus: **100 credits**
- Candidate practice interview: **30** (or **50** with proctoring)
- Recruiter AI job-description generation: **10**
- Real interview (charged to the **recruiter** who owns the job): **30** (or **50** with proctoring)

Credits are bought via Razorpay recharge packs. See
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
