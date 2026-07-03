# Frontend — Simple Overview

**What it is:** the GenHire website — a **React 19** single-page app (folder
`react-frontend/`, built with Create React App) used by candidates,
recruiters, and admins in a normal browser.

**In one sentence:** it renders the dashboards and forms, calls the Flask
backend for everything, and receives live updates over a WebSocket so lists
refresh themselves.

## What each role sees

- **Candidates** — a landing page and job board (`/dashboard`), a profile
  with multi-CV management (`/profile`), job application pages, practice
  interviews (`/practice`), their application/interview reports, and a
  credit recharge page.
- **Recruiters** — `/recruiter-dashboard` for posting jobs (with an
  "AI generate" option), reviewing applicants with CV scores, opening
  interview reports (transcript, scores, gaze heatmap), bulk-inviting
  candidates, plus cost statistics and credit packs.
- **Admins** — an admin portal under `/admin/*` for verifying recruiters,
  managing users/jobs/applications, and platform-wide cost statistics.

## How it's wired (the short version)

- **One API layer** — all HTTP calls live in `src/services/` (`api.js`,
  `adminApi.js`, `inviteApi.js`, `cvService.js`, `payment/paymentApi.js`).
  Components never call `fetch` with hand-built URLs (the interview page
  `Chat.jsx` is the one big exception — it talks to the interview endpoints
  directly).
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

## Shape of the code

```
react-frontend/src/
├── App.jsx        # all routes (lazy-loaded pages)
├── pages/         # one file per screen (+ admin/, candidate/, recruiter/)
├── components/    # shared UI + candidate/, recruiter/, admin/, common/...
├── services/      # the API layer + Socket.IO singleton
├── hooks/         # useAuth, useJobs, useApplications, useRazorpay, ...
├── contexts/      # CandidateDataContext (app-wide cached data)
└── utils/         # sessionManager (token storage), helpers
```

## How to run it

```bash
cd react-frontend
npm install
# .env: REACT_APP_API_URL=http://localhost:5000
#       REACT_APP_GOOGLE_CLIENT_ID=<your client id>
npm start                    # dev server on http://localhost:3000
npm run build                # production build (deployed via vercel.json)
```

**Want the details?** → [frontend-detailed.md](frontend-detailed.md)
