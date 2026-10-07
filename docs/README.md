For the current provider migration, see **[S2 Low deployment, interview workflow and costs](S2_LOW_DEPLOYMENT.md)**.

# GenHire Documentation

Everything in these docs is written directly from the current code — file
names, endpoints, credit amounts, and flows match what is actually
implemented today.

## Start here

| You are... | Read |
|---|---|
| **New to the team** | [architecture.md](architecture.md) → [onboarding.md](onboarding.md) |
| Wondering what a component does | the `overview.md` in its folder below |
| Changing or debugging code | the `-detailed.md` for that component |
| Tracing a feature end-to-end | [data-flows.md](data-flows.md) |

## All documents

### System level
- **[architecture.md](architecture.md)** — the three applications (Flask
  backend, React frontend, Electron secure browser), how they communicate,
  user roles, and the credit economy. *The 5-minute mental model.*
- **[data-flows.md](data-flows.md)** — step-by-step journeys: applying,
  the full AI interview, recruiter review, bulk invites, buying credits,
  practice sessions, auth.
- **[onboarding.md](onboarding.md)** — set up and run everything locally,
  try the full loop, where to change what, gotchas.
- **[production-readiness.md](production-readiness.md)** — honest scorecard of
  what is industry-standard, what is partial, and the ranked gaps.
- **[SMOKE_CHECKLIST.md](SMOKE_CHECKLIST.md)** — the manual click-through pass
  to run before merging or deploying.
- **[costfetch.md](costfetch.md)** — how the admin cost page gets *real*
  provider spend (GCP billing export, OpenAI Costs API) and what is still a
  hand-entered env estimate.
- **[../cost.md](../cost.md)** — what running the platform costs at
  100 / 1k / 10k DAU, and the cost levers.

### Backend (`python-backend/`)
- **[backend/overview.md](backend/overview.md)** — what it does, in simple terms.
- **[backend/backend-detailed.md](backend/backend-detailed.md)** — startup
  sequence, every blueprint/service/middleware, Socket.IO events, env vars,
  file storage, Cloud Run deployment and the keep-warm workflow.
- **[backend/api-reference.md](backend/api-reference.md)** — every HTTP
  endpoint with method, auth requirement, and purpose.
- **[backend/database.md](backend/database.md)** — MongoDB collections,
  document fields, and indexes.
- **[backend/interview-engine.md](backend/interview-engine.md)** — the AI
  interviewer: session lifecycle, interview pacing (30 s / 10 s silence
  rules), question generation, scoring formula, **face identity
  verification**, all four proctoring signals, the **credit refund
  lifecycle + abandon sweeper**, cost tracking.
- **[backend/payment-module.md](backend/payment-module.md)** — credits,
  wallets, recharge packs, interview refunds, the Razorpay flow, and the
  webhook.

### Frontend (`react-frontend/`)
- **[frontend/overview.md](frontend/overview.md)** — what each role sees and
  how the app is organized.
- **[frontend/frontend-detailed.md](frontend/frontend-detailed.md)** — route
  map, API service layer, auth/session handling, real-time sockets, hooks,
  the interview UI, component tree.

### Secure Browser (`secure-browser-kiosk/`)
- **[secure-browser/overview.md](secure-browser/overview.md)** — why it
  exists and what it does.
- **[secure-browser/secure-browser-detailed.md](secure-browser/secure-browser-detailed.md)**
  — deep-link launch, kiosk lockdown mechanics, Google TTS/STT, the preload
  IPC bridge, backend integration, build instructions.

## Keeping these docs honest

When you change behavior the docs describe (an endpoint, a credit price, a
flow), update the matching doc in the same pull request. If a doc and the
code ever disagree, **the code is right** — fix the doc.
