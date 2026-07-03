# Backend — Simple Overview

**What it is:** a Python **Flask** server (folder `python-backend/`) that is
the brain of GenHire. Everything the website and the secure browser do goes
through this one API.

**In one sentence:** it stores users/jobs/applications in MongoDB, runs
AI-powered interviews with live proctoring, scores CVs automatically, sends
emails, and manages the credit/payment system.

## What it does

- **Accounts & login** — email+password, Google sign-in, email verification,
  password reset. Everyone gets a JWT token the frontend sends with every
  request. Three roles: candidate, recruiter, admin.
- **Jobs & applications** — recruiters post jobs (optionally AI-generated
  from a prompt), candidates apply with a CV. A background worker
  automatically scores every CV against the job and shortlists or rejects
  the application, emailing the candidate.
- **AI interviews** — an LLM interviewer ("Alex", powered by Groq) asks
  adaptive questions based on the candidate's CV and the job description,
  evaluates every answer, and produces a final report with an interview
  score (70% answer quality + 30% communication quality).
- **Proctoring** — while the interview runs, the backend analyzes webcam
  frames (face identity + head pose), gaze-tracking data, tab switches, and
  an optional phone camera, producing a proctoring score for the recruiter.
- **Payments & credits** — every costly action (interviews, AI job
  descriptions) spends credits from a wallet; credits are bought through
  Razorpay. Real interviews are paid by the **recruiter**, practice
  interviews by the candidate.
- **Invites** — recruiters can bulk-invite candidates by email (CSV/Excel
  upload); invitees get temporary "Invite ID" accounts that skip signup.
- **Real-time updates** — a Socket.IO channel pushes application changes to
  dashboards instantly, and streams proctoring data during interviews.
- **Emails** — verification, invites, application status changes, interview
  results (via Mailgun).

## Shape of the code

```
python-backend/
├── app.py            # entry point — Flask app + interview & proctoring routes
├── routes/           # URL definitions (thin), one file per feature
├── controllers/      # the actual business logic behind each route
├── services/         # shared workers: CV scoring, emails, invites, storage...
├── middleware/       # JWT auth decorators, validation, rate limiting
├── models/           # MongoDB document helpers (no ORM — plain PyMongo)
├── config/           # database connection + .env loading
├── interview/        # the AI interview engine
├── evaluation_model/ # answer & communication evaluators (rubrics)
├── payment_module/   # self-contained Razorpay + wallet package
└── uploads/          # recordings, proctoring artifacts, temp files
```

## How to run it

```bash
cd python-backend
pip install -r requirements.txt      # Python 3.11
cp env.example .env                  # fill in MongoDB, JWT secret, API keys
python app.py                        # dev server on http://localhost:5000
```

Production runs on Gunicorn with the eventlet worker
(`./start_server.sh`, one worker — required for Socket.IO without Redis) or
the included `Dockerfile` (Cloud Run, port 8080).

**Want the details?** → [backend-detailed.md](backend-detailed.md) ·
[api-reference.md](api-reference.md) · [database.md](database.md) ·
[interview-engine.md](interview-engine.md) · [payment-module.md](payment-module.md)
