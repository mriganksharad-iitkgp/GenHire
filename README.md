# GenHire

**AI-powered hiring platform** — recruiters post jobs and get automatically
CV-scored applicants; candidates take adaptive, voice-based AI interviews
inside a locked-down secure browser with live proctoring; recruiters receive
full interview reports with transcripts, scores, and integrity signals.

## What's in this repository

| Folder | What it is | Stack |
|---|---|---|
| [`python-backend/`](python-backend/) | The API and all business logic: auth, jobs, applications, the AI interview engine, proctoring, payments, emails | Python 3.11, Flask, Flask-SocketIO, MongoDB (PyMongo), Groq LLM, Google Cloud Speech, Razorpay, Mailgun |
| [`react-frontend/`](react-frontend/) | The website used by candidates, recruiters, and admins | React 19 (CRA), react-router v7, socket.io-client, CSS Modules |
| [`secure-browser-kiosk/`](secure-browser-kiosk/) | The **Genhire** desktop app that runs interviews in fullscreen kiosk lockdown | Electron, Google Cloud TTS/STT, electron-builder |
| [`docs/`](docs/) | **Full documentation** — architecture, per-component overviews and deep dives, API reference, data flows, onboarding | Markdown |

## How it fits together (30 seconds)

```
React website ──REST + Socket.IO──►  Flask backend (port 5000) ──► MongoDB
      │                                   ▲            └─► Groq LLM, Google Speech,
      │ secure-interview:// deep link     │                Razorpay, Mailgun, GCS
      ▼                                   │
Electron secure browser ──REST + Socket.IO┘   (runs the actual interview)
```

1. A recruiter posts a job; candidates apply and their CVs are AI-scored
   automatically against the job description.
2. Shortlisted candidates click "Start Interview" — the website deep-links
   into the installed secure browser, which locks the screen and runs a
   spoken AI interview while streaming proctoring signals (face identity,
   head pose, gaze tracking, tab-switch detection, optional phone camera).
3. The recruiter reviews the interview report — transcript, answer/language
   scores, per-answer AI-generation probability, proctoring score — and
   selects or rejects, with the candidate notified by email and live
   dashboard updates throughout.
4. Everything billable runs on a credit wallet, topped up via Razorpay.

## Quick start

Full instructions live in **[docs/onboarding.md](docs/onboarding.md)**. The
short version:

```bash
# Backend (Python 3.11, needs MongoDB + a .env — see python-backend/env.example)
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

Start with the [docs index](docs/README.md).
