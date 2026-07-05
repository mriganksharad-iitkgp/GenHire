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

- **Groq** (`GROQ_API_KEY`) — required, or interviews can't generate questions.
- **Google Cloud** — OAuth client id (login) + a service account with
  Speech-to-Text/Text-to-Speech (speech + kiosk) and optionally Cloud Storage.
- **Mailgun** — only if you need real emails; otherwise set
  `REQUIRE_EMAIL_VERIFICATION=false` and skip it.
- **Razorpay** test keys (`rzp_test_...`) — only for payment work.

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
REQUIRE_EMAIL_VERIFICATION=false     # skip Mailgun in dev
FLASK_ENV=development
GROQ_API_KEY=<key>                   # needed for interviews
GOOGLE_CLIENT_ID=<id>.apps.googleusercontent.com   # needed for Google login
```

Run it:

```bash
python app.py        # http://localhost:5000 (Flask + Socket.IO, auto-reload)
```

Sanity check: `GET http://localhost:5000/health` should return
`{"status": "healthy", "database": "connected"}`.

Notes:
- Indexes and the signup-bonus wallet bootstrap run automatically at startup.
- To create the first admin: `python create_super_admin.py`.
- Heavy proctoring deps (TensorFlow/MediaPipe/DeepFace) are imported lazily —
  if `security_check` can't import, live frame proctoring is silently
  disabled but everything else works.
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
npm start            # http://localhost:3000
```

Port 3000 matters: the backend's default `CORS_ORIGINS` allows
`localhost:3000`. If you serve the frontend elsewhere, set `CORS_ORIGINS`
in the backend `.env` to match.

## 3. Secure Browser (`secure-browser-kiosk/`) — only for interview work

```bash
cd secure-browser-kiosk
npm install
# place credentials.json (Google service account with Speech APIs) next to main.js
npm start
```

To test the full website→kiosk handoff you need the protocol registered,
which happens when you install a built package (`npm run dist` → installer
in `dist/`). During development you can launch `npm start` and trigger deep
links manually.

## Try the full loop (15 minutes)

1. Register a **candidate** at `/register` and a **recruiter** at
   `/recruiter-signup` (with `REQUIRE_EMAIL_VERIFICATION=false` both can log
   in immediately).
2. Create an admin (`python create_super_admin.py`), log in, go to
   `/admin/verification`, approve the recruiter.
3. As the recruiter: post a job (try the AI-generate button — costs 10
   credits from the 100-credit signup bonus).
4. As the candidate: upload a CV on `/profile`, apply to the job from
   `/dashboard`. Watch the background worker score the CV
   (application flips to shortlisted/rejected) and the recruiter dashboard
   update in real time.
5. Start the interview (needs the kiosk installed, plus Groq + Google keys).
   The first interview enrolls the candidate's face as their permanent
   identity; later interviews verify against it.
6. As the recruiter: open the interview report on the application (including
   the Candidate Identity section) and mark the candidate
   **Screening Cleared** or **Screening Not Cleared**.

## Where things live (quick reference)

| I want to change... | Look in |
|---|---|
| An API endpoint | `python-backend/routes/` → its controller in `controllers/` |
| Interview questions/evaluation | `python-backend/interview/`, `evaluation_model/rubrics_eval/` |
| Proctoring | `python-backend/security_check.py`, `utils/gaze_recorder_service.py`, Socket.IO handlers in `app.py` |
| Face identity verification | `python-backend/services/face_verification_service.py` (+ `register_face` in `app.py`) |
| Interview credit refunds / abandon sweeper | `python-backend/services/interview_credit_service.py` |
| Credits/payments | `python-backend/payment_module/` |
| Emails | `python-backend/services/email_service.py`, `invite_email_templates.py` |
| A screen in the website | `react-frontend/src/pages/` (+ `components/`) |
| A frontend API call | `react-frontend/src/services/` |
| Kiosk behavior | `secure-browser-kiosk/main.js` (system) / `renderer.js` (interview UI) |

## Gotchas

- **Two interview UIs exist**: `react-frontend/src/pages/Chat.jsx` (browser)
  and `secure-browser-kiosk/renderer.js` (kiosk). Interview-flow changes
  usually need to be mirrored in both.
- **Real interviews charge the recruiter's wallet** at `/api/interviews/start`.
  If interviews won't start with a credits error, top up / check the
  *recruiter's* balance, not the candidate's. Interviews that end with zero
  answers are refunded automatically (`interview_credit_service.py`).
- **Face verification needs the DeepFace/OpenCV stack** (in
  `requirements.txt`). Without it, identity checks degrade to photo capture
  only — useful in dev, but don't mistake it for the production behavior
  (`FACE_VERIFICATION_MODE=enforce`).
- **Status rename migration**: the terminal positive status is
  `screening_cleared` (formerly `selected`). Databases created before the
  rename should run `python scripts/migrate_screening_cleared.py migrate`
  once (the code reads legacy values fine in the meantime).
- The backend keeps interview sessions and live proctoring state
  **in memory** — restarting the server mid-interview loses the session
  (the refund sweeper cleans up and refunds/finalizes such sessions).
- **Production (Cloud Run) scales to zero when idle**, causing cold starts.
  `.github/workflows/keep-backend-warm.yml` pings `/health` every 5 minutes
  as a free, best-effort mitigation — see
  [backend-detailed.md](backend/backend-detailed.md#deployment-cloud-run-and-keeping-it-warm)
  for how it works and the guaranteed (paid) alternative.
- `locustfile.py` (backend root) has load tests; `test_*.py` files are
  ad-hoc integration scripts, not a pytest suite.
