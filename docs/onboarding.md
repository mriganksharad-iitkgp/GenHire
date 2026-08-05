# Onboarding — New Teammate Setup Guide

Welcome to GenHire! This gets you from a fresh clone to a fully running
platform on your machine. Read [architecture.md](architecture.md) first for
the 5-minute mental model.

## Prerequisites

| Tool | Version | Needed for |
|---|---|---|
| Python | 3.11 | backend |
| Node.js + npm | any recent LTS | frontend + secure browser |
| MongoDB | local instance **or** an Atlas connection string | backend |
| Git | — | obviously |

Third-party accounts you'll need keys for (ask a teammate for the shared
dev credentials rather than creating your own where possible):

- **At least one LLM key** — the chain is `LLM_PROVIDER_PRIORITY`, default
  `openai,gemini,groq`, reading `OPENAI_API_KEY` / `GOOGLE_API_KEY` (Gemini) /
  `GROQ_API_KEY`. Any one working key is enough to boot and run interviews;
  with none of them, question generation fails. `GROQ_API_KEY` is the usual
  dev choice because the free tier works.
- **Google Cloud** — OAuth client id (login) + a service account with
  Speech-to-Text/Text-to-Speech AND **Cloud Storage (now mandatory — the
  backend refuses to boot without a bucket; every persistent artifact lives
  in GCS, there is no local-disk storage)**.
- **ZeptoMail / Mailgun** — only if you need real emails; otherwise set
  `EMAIL_PROVIDER=noop` and `REQUIRE_EMAIL_VERIFICATION=false` and skip it.
- **Razorpay** test keys (`rzp_test_...`) — only for payment work.

**Dev vs production data is NOT yet isolated.** Two env files exist
(`python-backend/.env` and `.env.production`), but as of 2026-08-06 both point
at the **same** Atlas cluster (`hrtech.kdo8zml.mongodb.net`) and the **same**
GCS bucket (`genhireuploads`). The intended end state is a company-account
prod cluster plus a `genhire-uploads-prod` bucket. Until that lands, treat
every local run as touching production data: prefer reads, reuse existing test
accounts, and don't bulk-delete anything.

## 1. Backend (`python-backend/`)

```bash
cd python-backend
python -m venv venv
venv\Scripts\activate          # Windows   (source venv/bin/activate on mac/linux)
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` — the minimum to boot:

```
MONGODB_URI=mongodb://localhost:27017/
DATABASE_NAME=hrtech
JWT_SECRET_KEY=<random string>       # python -c "import secrets; print(secrets.token_hex(32))"
FLASK_SECRET_KEY=<random string>
REQUIRE_EMAIL_VERIFICATION=false     # skip real email in dev
EMAIL_PROVIDER=noop                  # no real sends in dev unless you need them
FLASK_ENV=development
GROQ_API_KEY=<key>                   # at least one LLM key; see the chain above
GOOGLE_CLIENT_ID=<id>.apps.googleusercontent.com   # needed for Google login
GCS_BUCKET_NAME=<dev bucket>         # MANDATORY — boot fails without GCS
GOOGLE_APPLICATION_CREDENTIALS=gcs-service-account.json
```

Run it:

```bash
python app.py        # http://localhost:5000 (Flask + Socket.IO, auto-reload)
```

Sanity check: `GET http://localhost:5000/health` should return
`{"status": "healthy", "database": "connected"}`.

Notes:
- Always run the backend through its own venv
  (`python-backend/venv/Scripts/python.exe` on Windows) — a global Python
  won't have the `google-cloud-*` packages and the boot-time GCS check fails.
- Indexes and the signup-bonus wallet bootstrap run automatically at startup.
- To create the first admin: `python scripts/admin/create_super_admin.py`.
- Heavy proctoring deps (TensorFlow/MediaPipe/DeepFace) are **not** in
  `requirements.txt` and are imported lazily — if `security_check` can't
  import, server-side frame proctoring is silently disabled but everything
  else (including the gaze signal and the kiosk's local detection) works.
  Production runs this way deliberately.
- Production: `./start_server.sh` (Gunicorn + eventlet, **1 worker** — more
  workers break Socket.IO room delivery without a Redis message queue) or
  the `Dockerfile` (Cloud Run, port 8080).

## 2. Frontend (`react-frontend/`)

```bash
cd react-frontend
npm install
```

Create `react-frontend/.env`:

```
REACT_APP_API_URL=http://localhost:5000
REACT_APP_GOOGLE_CLIENT_ID=<same client id as backend>
```

Run it:

```bash
npm run dev          # Vite dev server, http://localhost:3000 (npm start is an alias)
```

Port 3000 matters: the backend's default `CORS_ORIGINS` allows
`localhost:3000`. If you serve the frontend elsewhere, set `CORS_ORIGINS`
in the backend `.env` to match.

## 3. Secure Browser (`secure-browser-kiosk/`) — only for interview work

```bash
cd secure-browser-kiosk
npm install
npm start
```

No credentials file is needed: the kiosk proxies TTS through the backend and
mints a short-lived STT token from it, using the JWT that arrives in the deep
link.

To test the full website→kiosk handoff you need the protocol registered,
which happens when you install a built package (`npm run dist` → installer
in `dist/`). During development you can launch `npm start` and trigger deep
links manually.

## Try the full loop (15 minutes)

1. Register a **candidate** at `/register` and a **recruiter** at
   `/recruiter-signup` (with `REQUIRE_EMAIL_VERIFICATION=false` both can log
   in immediately).
2. Create an admin (`python scripts/admin/create_super_admin.py`), log in, go
   to `/admin/verification`, approve the recruiter.
3. As the recruiter: post a job (try the AI-generate button — costs 10
   credits from the 100-credit signup bonus; if you upload a JD PDF while
   generating, candidates can download that exact file from the job page).
   Bulk-inviting candidates costs **1 credit per candidate** (charged
   upfront; failed emails are auto-refunded).
4. As the candidate: upload a CV **and an identity card** on `/profile`, then
   apply to the job from `/dashboard`. Watch the background worker score the
   CV (application flips to shortlisted/rejected) and the recruiter dashboard
   update in real time.
5. Start the interview (needs the kiosk installed, plus an LLM key + Google
   Speech). The webcam capture is scored against the identity card in the
   background — the interview never waits on it, and a low score never blocks;
   the number shows up on the recruiter's report. Without an identity card on
   the account the interview refuses to start.
6. As the recruiter: open the interview report on the application (including
   the Candidate Identity section) and mark the candidate
   **Screening Cleared** or **Screening Not Cleared**.

## Where things live (quick reference)

| I want to change... | Look in |
|---|---|
| An API endpoint | `python-backend/routes/` → its controller in `controllers/` |
| Interview questions/evaluation | `python-backend/interview/`, `evaluation_model/rubrics_eval/` |
| Proctoring | `python-backend/security_check.py`, `utils/gaze_recorder_service.py`, Socket.IO handlers in `sockets/` |
| The app's wiring (blueprints, CORS, workers) | `python-backend/core/factory.py` — `app.py` is just an entrypoint |
| Which LLM answers a call | `python-backend/services/llm_fallback_service.py` (+ `interview/config/settings.py` for the interview session manager) |
| Face identity verification | `python-backend/services/face_match_service.py` (LLM ID-card match) + `identity_card_service.py` (+ `register_face` in `routes/interview_routes.py`) |
| Interview credit refunds / abandon sweeper | `python-backend/services/interview_credit_service.py` |
| Credits/payments | `python-backend/payment_module/` |
| Emails | `python-backend/services/email_service.py`, `invite_email_templates.py` |
| A screen in the website | `react-frontend/src/features/<domain>/pages/` (+ that feature's `components/`) |
| A frontend API call | `react-frontend/src/shared/api/client.js` + the feature's `api/` folder |
| Kiosk behavior | `secure-browser-kiosk/main.js` (system) / `renderer.js` (interview UI) |

## Gotchas

- **Two interview UIs exist**: `react-frontend/src/features/interview/pages/Chat.jsx` (browser)
  and `secure-browser-kiosk/renderer.js` (kiosk). Interview-flow changes
  usually need to be mirrored in both.
- **Real interviews charge the recruiter's wallet** at `/api/interviews/start`.
  If interviews won't start with a credits error, top up / check the
  *recruiter's* balance, not the candidate's. Interviews that end with zero
  answers are refunded automatically (`interview_credit_service.py`).
- **Identity verification is advisory, not a gate.** A candidate must have an
  identity card on file to start a real interview, but the LLM similarity
  score runs in the background and never blocks anyone. If you read older
  notes about DeepFace enrollment, `face_mismatch_blocked`, or
  `identity_blocked`, that flow is gone.
- **Status rename migration**: the terminal positive status is
  `screening_cleared` (formerly `selected`). Databases created before the
  rename should run
  `python scripts/migrations/migrate_screening_cleared.py migrate` once (the
  code reads legacy values fine in the meantime). Other one-off migrations
  live alongside it in `scripts/migrations/`.
- The backend keeps interview sessions and live proctoring state
  **in memory** — restarting the server mid-interview loses the session
  (the refund sweeper cleans up and refunds/finalizes such sessions).
- **Production (Cloud Run) scales to zero when idle**, causing cold starts.
  `.github/workflows/keep-backend-warm.yml` pings `/health` every 5 minutes
  as a free, best-effort mitigation — see
  [backend-detailed.md](backend/backend-detailed.md#deployment-cloud-run-and-keeping-it-warm)
  for how it works and the guaranteed (paid) alternative.
- `scripts/dev/locustfile.py` has load tests; the `scripts/dev/test_*.py`
  files are ad-hoc integration scripts, not a pytest suite. Smoke scripts for
  email and billing live in `scripts/smoke/`.
- `python app.py` starts under the Werkzeug reloader, which leaves orphan
  processes holding port 5000 if a run is killed. If a restart says the port
  is in use, find the PID with `netstat -ano | findstr :5000` and kill it.
