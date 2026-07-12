# GenHire => AI Powered Interview Platform

**AI-powered screening platform** — recruiters post jobs and get automatically
CV-scored applicants; candidates take adaptive, voice-based AI interviews
inside a locked-down secure browser with live proctoring and face identity
verification; recruiters receive full interview reports with transcripts,
scores, and integrity signals, then mark candidates **Screening Cleared** for
their own further hiring rounds.

## What's in this repository

| Folder | What it is | Stack |
|---|---|---|
| [`python-backend/`](python-backend/) | The API and all business logic: auth, jobs, applications, the AI interview engine, proctoring, payments, emails | Python 3.11, Flask (app factory), Flask-SocketIO, MongoDB (PyMongo), LLM chain (OpenAI→Gemini→Groq, env-ordered), Google Cloud Speech, Google Cloud Storage (mandatory — all artifacts), Razorpay, ZeptoMail/Mailgun |
| [`react-frontend/`](react-frontend/) | The website used by candidates, recruiters, and admins | React 19 (CRA), feature-folder layout (`app/ features/ shared/`), react-router v7, socket.io-client, CSS Modules |
| [`secure-browser-kiosk/`](secure-browser-kiosk/) | The **Genhire** desktop app that runs interviews in fullscreen kiosk lockdown | Electron, backend-proxied speech (no bundled credentials), electron-builder |
| [`docs/`](docs/) | **Full documentation** — architecture, per-component overviews and deep dives, API reference, data flows, onboarding | Markdown |

## How it fits together (30 seconds)

```
React website ──REST + Socket.IO──►  Flask backend (port 5000) ──► MongoDB
      │                                   ▲            └─► LLM chain, Google Speech,
      │ secure-interview:// deep link     │                Razorpay, ZeptoMail, GCS
      ▼                                   │
Electron secure browser ──REST + Socket.IO┘   (runs the actual interview)
```

1. A recruiter posts a job; candidates apply and their CVs are AI-scored
   automatically against the job description.
2. Shortlisted candidates click "Start Interview" — the website deep-links
   into the installed secure browser. Recruiters can also **bulk-invite
   candidates by email** (1 credit per candidate, auto-refunded if the email
   fails): each invitee gets a magic link that logs them straight in on a
   scoped burner account. The kiosk captures the candidate's face and scores
   it against the **identity card uploaded once on their profile** in the
   background (a vision LLM similarity score shown to the recruiter — it
   never blocks the interview), locks the screen, and runs a spoken AI
   interview while streaming proctoring signals (head pose, gaze tracking,
   tab-switch detection, optional phone camera). Interviews pace themselves:
   30 seconds of silence after a question auto-advances; a 10-second pause
   after the candidate stops speaking submits the answer.
3. The recruiter reviews the interview report — transcript, answer/language
   scores, per-answer AI-generation probability, proctoring score, captured
   identity photo — and marks the candidate **Screening Cleared** or
   **Screening Not Cleared**, with the candidate notified by email and live
   dashboard updates throughout.
4. Everything billable runs on a credit wallet, topped up via Razorpay.
   Interviews are charged when they start and automatically **refunded** if
   they end with zero answers (crash or abandonment). All recordings, gaze
   artifacts, CVs, and JDs live in Google Cloud Storage only (separate
   dev/prod buckets — nothing is stored on local disk), and an admin cost
   dashboard tracks actual spend per provider (GCP billing export, OpenAI
   Costs API, per-send email log).

## Quick start

Full instructions live in **[docs/onboarding.md](docs/onboarding.md)**. The
short version:

```bash
# Backend (Python 3.11, needs MongoDB + a .env — see python-backend/.env.example)
cd python-backend
pip install -r requirements.txt
python app.py                         # http://localhost:5000

# Frontend (needs REACT_APP_API_URL + REACT_APP_GOOGLE_CLIENT_ID in .env)
cd react-frontend
npm install && npm start              # http://localhost:3000

# Secure browser (only needed for interview flows)
cd secure-browser-kiosk
npm install && npm start              # npm run dist → Windows installer
```

## Documentation

| Question | Answer lives in |
|---|---|
| How does the whole system connect? | [docs/architecture.md](docs/architecture.md) |
| How do I set up my machine? | [docs/onboarding.md](docs/onboarding.md) |
| What API endpoints exist? | [docs/backend/api-reference.md](docs/backend/api-reference.md) |
| How does the AI interview + proctoring work? | [docs/backend/interview-engine.md](docs/backend/interview-engine.md) |
| How do credits and payments work? | [docs/backend/payment-module.md](docs/backend/payment-module.md) |
| What's in the database? | [docs/backend/database.md](docs/backend/database.md) |
| How is the frontend organized? | [docs/frontend/frontend-detailed.md](docs/frontend/frontend-detailed.md) |
| How does the kiosk lockdown work? | [docs/secure-browser/secure-browser-detailed.md](docs/secure-browser/secure-browser-detailed.md) |
| What happens end-to-end when a candidate applies/interviews? | [docs/data-flows.md](docs/data-flows.md) |
| What does running this cost at 100/1k/10k users? | [cost.md](cost.md) |
| How production-ready are we, honestly? | [docs/production-readiness.md](docs/production-readiness.md) |

Start with the [docs index](docs/README.md).
