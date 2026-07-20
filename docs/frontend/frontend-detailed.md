# Frontend — Detailed Wiring

Folder: `react-frontend/`. A single-page application built with **React 19 on
Vite** (`vite`, `@vitejs/plugin-react`), plain CSS Modules for styling (no UI
framework), `react-router-dom` v7 for routing, and `socket.io-client` for
real-time updates.

## Environment variables

Variables keep the `REACT_APP_` prefix inherited from the original Create React
App setup. `vite.config.mjs` loads every `REACT_APP_*` var for the active mode
and statically shims `process.env` with them, so all call sites read
`process.env.REACT_APP_*` unchanged (unset vars read back as `undefined`, as
they did under CRA).

| Variable | Purpose |
|---|---|
| `REACT_APP_API_URL` | Backend origin, e.g. `http://localhost:5000`. Used for Socket.IO and direct fetches. |
| `REACT_APP_API_BASE` | Optional full API base; defaults to `${REACT_APP_API_URL}/api`. |
| `REACT_APP_GOOGLE_CLIENT_ID` | Google OAuth client id for `@react-oauth/google`. |
| `REACT_APP_TOKEN_KEY` / `REACT_APP_USER_KEY` | localStorage keys for the JWT and user record. |
| `REACT_APP_KIOSK_DOWNLOAD_URL` | Installer link offered when the desktop kiosk app isn't installed. |

Run with `npm run dev` (Vite dev server, port 3000 — matching the backend's
default `CORS_ORIGINS`; `npm start` is an alias). Build with `npm run build`
(output in `build/`, `.env.production` values baked in); `npm run preview`
serves that build locally. `vercel.json` at the repo root configures SPA
hosting on Vercel.

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
| `/dashboard` | `Dashboard` (candidate job board + applications) | authenticated — inside shared `Layout` (`ProtectedRoute allow="any"`) |
| `/profile`, `/practice`, `/jobs/:jobId`, `/applications/:applicationId`, `/team` | candidate pages inside `Layout` | authenticated |
| `/interviews/:interviewId` | `Interview` (identity-card gate + wrapper around `Chat`) | candidate |
| `/mobile-camera/:sessionId` | `MobileRecorder` — phone second-camera page (paired via QR code; hidden when `MOBILE_RECORDING_ENABLED=false`) | candidate's phone |
| `/recruiter/dashboard` | `RecruiterDashboard` | recruiter (`ProtectedRoute allow="recruiter"`) |
| `/recruiter/cost-statistics`, `/recruiter/team` | recruiter pages | recruiter |
| `/recruiter/subscription`, `/candidate/subscription` | recharge-pack purchase pages | recruiter / candidate |
| `/payment/success`, `/payment/cancel` | post-Razorpay redirect pages | any |
| `/candidate/cost-statistics` | candidate usage dashboard | candidate |
| `/admin`, `/admin/overview`, `/admin/candidates(/:id)`, `/admin/recruiters(/:id)`, `/admin/admins`, `/admin/verification`, `/admin/cost-statistics` | admin portal (`features/admin/pages/*` with `AdminLayout`) | admin (`ProtectedRoute allow="admin"`) |
| `/404`, `*` | `NotFound` | — |

Legacy paths (`/recruiter-dashboard`, `/subscription`, `/job/:id`,
`/application/:id`, `/interview/:id`, `/mobile-cam/:id`) permanently redirect
to their renamed successors with params and query preserved.

## API layer (`shared/api/` + per-feature `api/` folders)

All backend communication runs through one HTTP core — components never build
URLs themselves.

| File | Covers |
|---|---|
| `shared/api/client.js` | THE `request()`/`requestBlob()`/`authedFetch()` core: base URL resolution, JWT header, JSON headers only for non-FormData bodies, 401 → global session-expired event (opt-out for payment/invite flows). |
| `shared/api/endpoints.js` | Cross-role endpoints: profile, CV details, uploads, jobs (CRUD + `generateJobWithAI`), applications (list, status, interview report, CV view), `startInterview`. |
| `shared/api/socket.js` | Singleton Socket.IO connection: `getAppSocket()` / `connectAppSocket()` (auth callback supplies the current JWT) / `disconnectAppSocket()` (on logout). |
| `features/admin/api/adminApi.js` | Every `/api/admin/*` endpoint incl. identity-card review and cost statistics. |
| `features/recruiter/api/inviteApi.js` | `previewInvites` (multipart: file/text/single), `sendInvites`, `getInviteBatchStatus`, `lookupInvite`, `redeemInvite`. |
| `features/recruiter/api/jobExportApi.js` | One-click screening-cleared XLSX/CSV export per job. |
| `features/candidate/api/cvService.js` | Multi-CV management calls (`/api/cv/*`). |
| `features/candidate/api/identityCardApi.js` | One-time identity-card upload/status/preview. |
| `features/auth/api/authApi.js` | Login/register/OAuth/verify/reset (raw-Response contract — these flows branch on status codes). |
| `features/payment/api/paymentApi.js` | All `/api/payment/*` calls. |

## Session & auth (`shared/utils/session.js`, `shared/hooks/useAuth.js`, `app/ProtectedRoute.jsx`)

The JWT and user object live in tab-scoped storage managed by
`shared/utils/session` (`getToken`, `clearSession`, …). Routes are guarded
declaratively by `ProtectedRoute` (`allow="any" | "recruiter" | "admin"`);
`useAuth` exposes login
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
| `features/candidate/context/CandidateDataContext.jsx` | App-wide provider caching candidate data (profile, applications) across pages. |
| `features/candidate/hooks/useApplications.js` | Fetch + manage application lists. |
| `features/candidate/hooks/useJobs.js` | Job list fetching/filtering. |
| `features/payment/hooks/useRazorpay.js` | Loads the Razorpay checkout script and opens the payment modal. |
| `shared/hooks/useDebounce.js` | Debounced search inputs. |
| `features/candidate/hooks/` | Candidate-specific data hooks (profile, applications). |

## The interview UI (`pages/Chat.jsx`, ~2,400 lines)

The in-browser interview experience (also largely mirrored inside the
Electron kiosk's own `renderer.js`). Responsibilities:

1. Starts the session — `POST /api/interviews/start` (or is handed one), and
   for practice mode targets `/api/practice/*` instead. Reads
   `max_questions` / `question_deadline` for progress display and pacing.
2. Runs the **identity gate** — the lobby (`Interview.jsx`) first requires an
   identity card on the profile; then the capture goes to
   `POST /api/interviews/<id>/register-face`, where a vision LLM scores it
   against the ID-card photo. Outcomes: quality problems become "retake
   photo" toasts, `face_mismatch` shows attempts remaining,
   `face_mismatch_blocked` and `identity_card_required` park the candidate on
   a dedicated blocked screen (interview over / upload card first).
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

## Component organization (`shared/components/` + per-feature `components/`)

- **`shared/components/ui/`** — the primitives: `Modal` (the one modal shell
  every dialog builds on), `ConfirmDialog`, `Toast`, `Pagination`,
  `SkeletonCard`, `Loading`, `EmptyState`, `ErrorBoundary`.
- **`shared/components/layout/`** — `Layout` (navbar + outlet shell),
  `Navbar`, `Avatar`. **`shared/components/lists/`** — application/practice
  history lists shared by candidate and admin. **`shared/components/account/`**
  — `DeleteAccountModal`.
- **`features/recruiter/components/`** — `CandidateCard`, `CandidatesFilters`,
  `InviteCandidatesModal` (bulk invite: paste text / upload CSV/XLSX →
  preview → send → batch status), `JobCreationModal` (AI generation from a
  prompt, an uploaded JD file, or both), `JobEditModal`, `JobDetailsModal`,
  `JDDetailsModal`, jobs grid with the per-job **Export Cleared** button.
- **`features/candidate/components/`** — CV management (`CVManagement`,
  `CVList`, `CVSelector`, `CVDetailsForm/Modal`, `CVSelectionModal` — reused
  for applying, practice, and "Check CV Match Score" via `mode`, `CVViewer`),
  `ApplicationsList`, `BioForm`, `SidebarProfile`, `IdentityCardUpload`
  (one-time, locked after upload).
- **`features/admin/components/`** — `AdminLayout`, `UserTable`,
  `IdentityCardPanel` (view/replace/reset a candidate's card),
  detail/confirm modals.
- **`features/interview/components/`** — `InterviewHeader` (phase-aware
  timing indicator), `InterviewReportModal`, `ProctoringResultModal`,
  `PracticeDetailsModal`, `GazeHeatmapPanel`, checklist/loading screens.
- **`features/payment/components/`** — plan cards, payment history, both
  role subscription trees.

Application statuses render through `shared/utils/applicationStatus.js` —
`normalizeStatus()` folds the legacy `"selected"` value into
`"screening_cleared"`, and the label maps display it as **"Screening
Cleared"** (with `"rejected"` shown as **"Screening Not Cleared"** and, on
candidate screens, `"pending"` as **"Awaiting Recruiter Review"**).

Charts on the cost-statistics pages use `chart.js` + `react-chartjs-2`.
`@ffmpeg/ffmpeg` (WASM) is available for client-side media processing of
recordings. Icons are `lucide-react`.

## Launching the secure browser

`features/candidate/pages/Profile.jsx` (real interviews) and
`features/candidate/pages/Practice.jsx` (practice) build a deep link:

```js
const customUri = `secure-interview://start?initData=${encodeURIComponent(encodedPayload)}`;
```

and navigate to it, which launches the installed GenHire Secure Browser with
the session payload (token, API URL, session context). See
[../secure-browser/secure-browser-detailed.md](../secure-browser/secure-browser-detailed.md).
