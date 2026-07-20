# Frontend — Simple Overview

**What it is:** the GenHire website — a **React 19** single-page app (folder
`react-frontend/`, built with **Vite**) used by candidates,
recruiters, and admins in a normal browser.

**In one sentence:** it renders the dashboards and forms, calls the Flask
backend for everything, and receives live updates over a WebSocket so lists
refresh themselves.

## What each role sees

- **Candidates** — a landing page and job board (`/dashboard`), a profile
  with multi-CV management (`/profile`), job application pages, practice
  interviews (`/practice`), their application/interview reports, and a
  credit recharge page.
- **Recruiters** — `/recruiter/dashboard` for posting jobs (with an
  "AI generate" option), reviewing applicants with CV scores, opening
  interview reports (transcript, scores, gaze heatmap, candidate identity
  photo), marking candidates **Screening Cleared** / **Not Cleared** (and
  exporting the cleared list per job as XLSX/CSV in one click),
  bulk-inviting candidates, plus cost statistics and credit packs.
- **Admins** — an admin portal under `/admin/*` for verifying recruiters,
  managing users/jobs/applications, and platform-wide cost statistics.

## How it's wired (the short version)

- **One HTTP core** — `src/shared/api/client.js` owns `request()` (base URL,
  bearer token, 401 handling); each feature keeps its endpoint functions in
  its own `api/` folder (`features/admin/api/adminApi.js`,
  `features/payment/api/paymentApi.js`, `features/candidate/api/…`, etc.).
  The interview page `Chat.jsx` still calls its endpoints directly (through
  the shared base URL) pending its planned decomposition.
- **Auth** — the backend's JWT is stored per-tab and attached as a
  `Bearer` header to every call. Any 401 logs the user out globally and
  redirects to `/login?expired=1`. Login works with email+password, Google,
  or an Invite ID.
- **Real-time** — one shared Socket.IO connection receives
  `application_update` events so candidate and recruiter dashboards update
  live, without polling.
- **Payments** — the `useRazorpay` hook opens Razorpay Checkout; success
  verification goes back through the API.
- **Interviews** — clicking "Start Interview" doesn't run the interview in
  the browser tab; it deep-links into the installed **GenHire Secure
  Browser** desktop app via a `secure-interview://` URL.

## Shape of the code (feature-based since the 2026-07 reorganization)

```
react-frontend/src/
├── App.jsx            # providers + router only (~18 lines)
├── app/               # routes.jsx (all lazy routes + ProtectedRoute guards),
│                      # providers.jsx, NotFound
├── features/          # one folder per domain, each with pages/ components/
│   ├── auth/          #   hooks/ api/ as needed
│   ├── candidate/     # dashboard, profile (incl. identity-card upload), practice
│   ├── recruiter/     # recruiter dashboard, team, exports, invites
│   ├── admin/         # admin portal pages + panels
│   ├── interview/     # Chat (interview engine), lobby, mobile recorder
│   ├── payment/       # plans, checkout, subscription components
│   └── landing/
└── shared/            # cross-feature building blocks
    ├── api/           # client.js (the one request()), endpoints.js, socket.js
    ├── components/    # ui/ (Modal, ConfirmDialog, Toast…), layout/, lists/, account/
    ├── hooks/         # useAuth, useDebounce
    ├── utils/         # session.js (token storage), format.js, helpers
    └── constants/
```

## How to run it

```bash
cd react-frontend
npm install
# .env: REACT_APP_API_URL=http://localhost:5000
#       REACT_APP_GOOGLE_CLIENT_ID=<your client id>
npm run dev                  # Vite dev server on http://localhost:3000 (npm start is an alias)
npm run build                # production build to build/ (deployed via vercel.json)
npm run preview              # serve the production build locally
```

> Env vars keep the `REACT_APP_` prefix from the old Create React App setup:
> Vite's config (`vite.config.mjs`) shims `process.env.REACT_APP_*` so no call
> sites had to change during the CRA → Vite migration.

**Want the details?** → [frontend-detailed.md](frontend-detailed.md)
