# Frontend — Detailed Wiring

Folder: `react-frontend/`. A single-page application built with **React 19 on
Create React App** (`react-scripts`), plain CSS Modules for styling (no UI
framework), `react-router-dom` v7 for routing, and `socket.io-client` for
real-time updates.

## Environment variables

| Variable | Purpose |
|---|---|
| `REACT_APP_API_URL` | Backend origin, e.g. `http://localhost:5000`. Used for Socket.IO and direct fetches. |
| `REACT_APP_API_BASE` | Optional full API base; defaults to `${REACT_APP_API_URL}/api`. |
| `REACT_APP_GOOGLE_CLIENT_ID` | Google OAuth client id for `@react-oauth/google`. |

Run with `npm run dev` / `npm start` (CRA dev server, port 3000 — matching the
backend's default `CORS_ORIGINS`). Build with `npm run build` (CI warnings
non-fatal via `cross-env CI=false`). `vercel.json` at the repo root configures
SPA hosting on Vercel.

## Application shell (`src/App.jsx`)

Provider nesting: `GoogleOAuthProvider` → `CandidateDataProvider` →
`ErrorBoundary` → `Router`. All pages are **lazy-loaded** (`React.lazy` +
`Suspense`) so each route is its own chunk.

`SessionExpiredHandler` listens for the global `auth:session-expired`
window event (fired by the API layer on any 401) and redirects to
`/login?expired=1`.

### Route map

| Path | Page | Who |
|---|---|---|
| `/` | `LandingPage` | public |
| `/login`, `/register`, `/recruiter-signup` | `Login`, `Register`, `RecruiterOnboarding` | public |
| `/verify-email`, `/forgot-password`, `/reset-password` | email/password flows | public |
| `/invite/redeem` | `InviteRedeem` — redeem a recruiter invite token | public |
| `/dashboard` | `Dashboard` (candidate job board + applications) | candidate — inside shared `Layout` |
| `/profile`, `/practice`, `/job/:jobId`, `/application/:applicationId`, `/team` | candidate pages inside `Layout` | candidate |
| `/interview/:interviewId` | `Interview` (wrapper around `Chat`) | candidate |
| `/mobile-cam/:sessionId` | `MobileRecorder` — phone second-camera page (paired via QR code) | candidate's phone |
| `/recruiter-dashboard` | `RecruiterDashboard` | recruiter |
| `/recruiter/cost-statistics`, `/recruiter/team` | recruiter pages | recruiter |
| `/subscription`, `/candidate/subscription` | recharge-pack purchase pages | recruiter / candidate |
| `/payment/success`, `/payment/cancel` | post-Razorpay redirect pages | any |
| `/candidate/cost-statistics` | candidate usage dashboard | candidate |
| `/admin`, `/admin/overview`, `/admin/candidates(/:id)`, `/admin/recruiters(/:id)`, `/admin/admins`, `/admin/verification`, `/admin/cost-statistics` | admin portal (`pages/admin/*` with `AdminLayout`) | admin |
| `/admin/old` | legacy `AdminDashboard` | admin |
| `/404`, `*` | `NotFound` | — |

## API layer (`src/services/`)

All backend communication is centralized here — components never build URLs
themselves.

| File | Covers |
|---|---|
| `api.js` | Core `request()`/`requestBlob()` helpers + profile, CV details, uploads, jobs (CRUD + `generateJobWithAI`), applications (list, status, interview report, CV view), `startInterview`. The helpers attach the JWT, set JSON headers only for non-FormData bodies, and turn 401s into the global session-expired event. |
| `adminApi.js` | Every `/api/admin/*` endpoint (users, verification, jobs, applications, CVs, system stats, cost statistics + credit summaries). |
| `inviteApi.js` | `previewInvites` (multipart: file/text/single), `sendInvites`, `getInviteBatchStatus`, `lookupInvite`, `redeemInvite`. |
| `cvService.js` | Multi-CV management calls (`/api/cv/*`). |
| `payment/paymentApi.js` | All `/api/payment/*` calls. |
| `socket.js` | Singleton Socket.IO connection: `getAppSocket()` / `connectAppSocket()` (auth callback supplies the current JWT) / `disconnectAppSocket()` (on logout). |

## Session & auth (`src/utils/sessionManager.js`, `hooks/useAuth.js`)

The JWT and user object live in tab-scoped storage managed by
`sessionManager` (`getToken`, `clearSession`, …). `useAuth` exposes login
state to components. Login options: email+password, Google OAuth (custom
button using the `useGoogleLogin` popup flow — chosen over the iframe
`GoogleLogin` button to bypass cross-origin popup blocking), or Invite ID
(invite-only accounts). New recruiters land in a "pending verification" state
until an admin approves them (`verified_required` on the backend).

## Real-time updates

- `hooks/useRealtimeApplications.js` — subscribes to the shared socket's
  `application_update` event and invokes `onUpdate(type, application)` where
  type ∈ `created | status_changed | score_updated`. Dashboards patch their
  lists in place instead of refetching.
- The backend puts every authenticated socket in a room named by user id, so
  each user only receives events about their own applications/jobs.
- Per-page sockets in `Chat.jsx` / `MobileRecorder.jsx` are separate — they
  stream proctoring frames and mobile-camera control, not app updates.

## State & data hooks

| Hook / context | Role |
|---|---|
| `contexts/CandidateDataContext.jsx` | App-wide provider caching candidate data (profile, applications) across pages. |
| `hooks/useApplications.js` | Fetch + manage application lists. |
| `hooks/useJobs.js` | Job list fetching/filtering. |
| `hooks/useRazorpay.js` | Loads the Razorpay checkout script and opens the payment modal. |
| `hooks/useDebounce.js` | Debounced search inputs. |
| `hooks/candidate/` | Candidate-specific data hooks. |

## The interview UI (`pages/Chat.jsx`, ~2,400 lines)

The in-browser interview experience (also largely mirrored inside the
Electron kiosk's own `renderer.js`). Responsibilities:

1. Starts the session — `POST /api/interviews/start` (or is handed one), and
   for practice mode targets `/api/practice/*` instead. Reads
   `max_questions` / `question_deadline` for progress display and pacing.
2. Runs the **identity gate** — captures a selfie →
   `POST /api/interviews/<id>/register-face`, and handles the outcomes:
   quality problems become "retake photo" toasts, `face_mismatch` shows
   attempts remaining, `face_mismatch_blocked` parks the candidate on a
   dedicated "Identity Verification Failed" screen (interview over).
   A transparency note tells first-time candidates their photo becomes the
   account's registered identity.
3. Opens a Socket.IO connection and streams webcam frames
   (`proctoring_frame`) once per second; listens for `proctoring_alert`.
4. Plays questions aloud via `POST /api/speech/synthesize` (Google TTS,
   authenticated) and records the candidate's spoken answers, showing the
   question text as it's spoken.
5. Enforces the two-phase silence rules: no speech at all → 30 s visible
   countdown → auto-advance; spoke then went silent → 10 s → auto-submit.
   Substantive answers get a short spoken acknowledgement; the
   `InterviewHeader` shows a phase-aware indicator (listening / countdown /
   recording / auto-submit).
6. Submits answers to `/answer`, renders next questions ("Question x of y").
7. Records the webcam (MediaRecorder) and uploads to `/upload-recording`;
   pairs a phone via QR (`react-qr-code`) for the mobile environment camera.
8. Runs the inline GazeRecorder integration and posts results to
   `/gaze-recorder-results`.
9. On finish: `POST .../end`. Three outcomes: the normal result screen (plus
   `PUT /api/applications/<id>/update-score`); a retryable "Couldn't
   Finalize" screen if `/end` failed (answers are safe server-side); or an
   "Interview Not Recorded" screen when the backend returns
   `interview_discarded` — no answers were given, credits were refunded,
   and the interview can be retaken.

## Component organization (`src/components/`)

- **Root-level shared** — `Layout` (navbar + outlet shell), `Navbar`, `Avatar`,
  `Toast`, `Pagination`, `SkeletonCard`, `ErrorBoundary`, modals
  (`JobCreationModal` — AI generation from a prompt, an uploaded JD file, or
  both, with no separate manual-upload step; `JobEditModal`, `JobDetailsModal`,
  `JDDetailsModal`, `InterviewReportModal`, `ProctoringResultModal`,
  `PracticeDetailsModal`, `CVSelectionModal` — CV picker reused for applying,
  practice, and the "Check CV Match Score" flow via `mode`, `CVViewer`,
  `GazeHeatmapPanel`).
- **`candidate/`** — CV management (`CVManagement`, `CVList`, `CVSelector`,
  `CVDetailsForm/Modal`), `ApplicationsList`, `BioForm`, `SidebarProfile`,
  `subscription/`.
- **`recruiter/`** — `CandidateCard`, `CandidatesFilters`,
  `InviteCandidatesModal` (bulk invite: paste text / upload CSV/XLSX →
  preview → send → batch status).
- **`admin/`** — `AdminLayout`, `UserTable`, detail/confirm modals.
- **`common/`** — `ConfirmDialog`, `DeleteAccountModal`, `EmptyState`,
  `Loading`.
- **`interview/`** — interview sub-components (`InterviewHeader` with the
  phase-aware timing indicator, …).
- **`payment/`** — payment UI pieces.

Application statuses render through `src/utils/applicationStatus.js` —
`normalizeStatus()` folds the legacy `"selected"` value into
`"screening_cleared"`, and the label maps display it as **"Screening
Cleared"** (with `"rejected"` shown as **"Screening Not Cleared"** and, on
candidate screens, `"pending"` as **"Awaiting Recruiter Review"**).

Charts on the cost-statistics pages use `chart.js` + `react-chartjs-2`.
`@ffmpeg/ffmpeg` (WASM) is available for client-side media processing of
recordings. Icons are `lucide-react`.

## Launching the secure browser

`pages/Profile.jsx` (real interviews) and `pages/Practice.jsx` (practice)
build a deep link:

```js
const customUri = `secure-interview://start?initData=${encodeURIComponent(encodedPayload)}`;
```

and navigate to it, which launches the installed GenHire Secure Browser with
the session payload (token, API URL, session context). See
[../secure-browser/secure-browser-detailed.md](../secure-browser/secure-browser-detailed.md).
