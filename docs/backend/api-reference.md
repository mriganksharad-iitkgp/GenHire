# API Reference

Every HTTP endpoint the backend exposes, grouped by feature. All endpoints
return JSON. Authenticated endpoints expect `Authorization: Bearer <jwt>`
(file-view endpoints also accept `?token=<jwt>` so they can be opened in a
new browser tab).

**Auth legend:** 🔓 public · 🔑 any logged-in user · 🧑‍💼 recruiter · 🎓 candidate · 🛡️ admin

## Auth — `routes/auth_routes.py` (prefix `/api`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/register` | 🔓 | Create account (candidate or recruiter). Sends verification email when `REQUIRE_EMAIL_VERIFICATION=true`. |
| POST | `/api/login` | 🔓 | Email+password (or Invite ID for invite-only accounts) → JWT. |
| POST | `/api/check-email-account-type` | 🔓 | Tells the login UI whether an email belongs to a password or Google account. |
| GET | `/api/me` | 🔑 | Current user from token. |
| DELETE | `/api/me` | 🔑 | Delete own account. |
| POST | `/api/verify-email` | 🔓 | Consume the emailed verification token. |
| POST | `/api/resend-verification` | 🔓 | Re-send verification email. |
| POST | `/api/forgot-password` | 🔓 | Send password-reset email. |
| POST | `/api/reset-password` | 🔓 | Consume reset token, set new password. |
| POST | `/api/google-oauth` | 🔓 | Google sign-in/sign-up (verifies the Google credential, issues our JWT). |

## Profile — `routes/profile_routes.py` (prefix `/api`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET / PUT | `/api/profile` | 🔑 | Read / update own profile. |
| PUT | `/api/company-profile` | 🧑‍💼 | Update recruiter company details. |
| GET / PUT | `/api/cv-details` | 🎓 | Structured CV fields stored on the user profile. |
| GET | `/api/recruiter/cost-statistics` | 🧑‍💼 | Recruiter's own usage/cost dashboard data. |
| GET | `/api/candidate/cost-statistics` | 🎓 | Candidate's own usage/cost dashboard data. |

## Jobs — `routes/job_routes.py` (prefix `/api`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/jobs` | 🔑 | List jobs (candidates see open jobs; recruiters see their own). |
| POST | `/api/jobs` | 🧑‍💼 (verified) | Create a job. Accepts JSON or `multipart/form-data` with an optional `jd_file` (PDF/TXT) — stored in Google Cloud Storage and served back to candidates via `/jd-download`; per-job `proctoring_config` included. |
| POST | `/api/jobs/generate-ai` | 🧑‍💼 | AI-generate a job description from a text prompt, an uploaded JD file (parsed and structured), or both (deducts recruiter credits). Accepts JSON `{"prompt"}` or multipart with `prompt` + `jd_file`. |
| GET | `/api/jobs/<job_id>/jd-download` | 🔑 | Signed, time-limited download URL for the job's uploaded JD file (404 if none was uploaded). |
| GET / PUT / DELETE | `/api/jobs/<job_id>` | 🔑 / 🧑‍💼 / 🧑‍💼 | Read / update / delete a job. |
| GET | `/api/jobs/<job_id>/applications` | 🧑‍💼 | Applications for one job. |
| DELETE | `/api/remove-sample-jobs` | — | Dev/maintenance helper. |
| GET | `/api/test-jobs` | — | Dev helper. |

## Applications — `routes/application_routes.py` (prefix `/api`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/jobs/<job_id>/apply` | 🎓 | Apply with a CV (uploaded file or saved CV / manual details). Kicks off async CV scoring; emits real-time `application_update`. |
| POST | `/api/jobs/<job_id>/check-cv-score` | 🎓 | Check a real CV-vs-JD match score **before** applying — no application is created. Body: `{cv_id, use_manual_cv}` (same CV picker as apply). Runs the same scoring engine as apply-time scoring. |
| DELETE | `/api/jobs/<job_id>/withdraw` | 🎓 | Withdraw own application. |
| GET | `/api/applications` | 🔑 | Own applications (candidate) or applications to own jobs (recruiter). |
| PUT | `/api/applications/<id>/status` | 🧑‍💼 | Change status (`pending`/`reviewed`/`shortlisted`/`interviewed`/`screening_cleared`/`rejected`; legacy `selected` is accepted and normalized to `screening_cleared`); emails candidate; updates job counters; emits socket event. |
| GET | `/api/applications/<id>` | 🔑 | One application (owner or job's recruiter). |
| GET | `/api/applications/<id>/cv` | 🔑 | The CV snapshot attached to the application. |
| GET | `/api/applications/<id>/interview-report` | 🔑 | Full AI interview report (evaluation, transcript, proctoring). |
| POST | `/api/applications/<id>/recalculate-score` | 🧑‍💼 | Re-run CV scoring. |
| PUT | `/api/applications/<id>/update-score` | 🔑 | Persist interview score onto the application (called by the interview UI). |
| GET | `/api/debug/applications` | — | Debug listing. |

## CV Management — `routes/cv_routes.py` (prefix `/api/cv`)

Candidates can store multiple CVs; one is "primary".

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/cv/upload` | Upload a CV file (`cv_file` form field, `is_primary` flag). |
| GET | `/api/cv/list` | List own CVs. |
| GET / DELETE | `/api/cv/<cv_id>` | Get metadata / delete. |
| PUT | `/api/cv/<cv_id>/set-primary` | Mark as the primary CV. |
| GET | `/api/cv/<cv_id>/preview` | Inline PDF preview. |
| GET | `/api/cv/<cv_id>/download-url` | Signed/download URL. |
| GET | `/api/cv/<cv_id>/text` | Extracted plain text. |

## Files (legacy + shared) — `routes/file_routes.py` (prefix `/api`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/upload`, `/api/upload-cv`, `/api/upload-photo` | Legacy single-file uploads (profile photo still uses `/upload-photo`). |
| GET | `/api/view-file`, `/api/view-cv`, `/api/download-cv`, `/api/view-photo` | Stream own files. |
| GET | `/api/admin/cv/<user_id>`, `/api/admin/photo/<user_id>` | 🛡️ view any user's files. |
| GET | `/api/files/<gridfs_id>` | Serve any GridFS-stored file inline (defined in `app.py`). |

## Practice Interviews — `routes/practice_routes.py` (prefix `/api/practice`)

Candidate-paid mock interviews (30 credits, 50 with proctoring). Same
credit-refund rules as real interviews: a start that fails after the debit
refunds it, and ending with zero answers discards the session and refunds
the candidate (`{status: "interview_discarded"}`).

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/practice/start` | Start a practice session (deducts candidate credits; returns pacing config: `question_timeout_seconds`, `question_deadline`, `max_questions`). |
| POST | `/api/practice/<session_id>/answer` | Submit an answer, get the next question. |
| POST | `/api/practice/<session_id>/end` | End + generate evaluation (or discard + refund when nothing was answered). |
| GET | `/api/practice/history` | Own past sessions. |
| GET | `/api/practice/<session_id>/report` | Full report for one session. |

## Real Interviews — defined in `app.py` (prefix `/api/interviews`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/interviews/start` | 🎓 | Start the real AI interview for an application. Verifies ownership + CV, checks & debits the **recruiter's** wallet (30/50 credits, refund-count-aware idempotency key), writes CV/JD temp files, creates the LLM session, returns `session_id` + first question + `max_questions` + `question_deadline`. Anything failing after the debit refunds it. |
| GET | `/api/interviews/<session_id>/question` | 🔑 | Next question for the session (owner-checked). |
| POST | `/api/interviews/<session_id>/answer` | 🎓 | Submit an answer (empty string allowed — auto-submitted on timeout). Returns evaluation + next question; non-empty answers increment `questions_answered_count`. |
| POST | `/api/interviews/<session_id>/end` | 🎓 | Finalize: builds evaluation + transcript, computes interview score (70% answers / 30% language), merges proctoring signals, updates interview + application docs, syncs job counters, emails recruiter & candidate, records usage telemetry. If **zero answers** were recorded, the session is discarded instead — recruiter credits refunded, response `{status: "interview_discarded", refund: {...}}`. |
| POST | `/api/interviews/<session_id>/register-face` | 🎓 | The face identity gate. First real interview: enrolls the face permanently on the account (`users.face_profile`). Later interviews: verifies the captured face against the registered one (DeepFace); mismatches return `error_code: face_mismatch` (attempts left) or `face_mismatch_blocked` (interview blocked, status `identity_blocked`). Also initializes the live proctoring session. Practice sessions soft-verify (never block). |
| GET | `/api/interviews/<session_id>/face-image/<kind>` | 🔑 | Serve the `captured` or `reference` identity photo (interview owner, the job's recruiter, or admin only). |
| GET | `/api/interviews/<session_id>/gaze-recorder-page` | 🔓 (token via query) | Server-rendered HTML page that loads the GazeRecorder eye-tracking scripts. |
| POST | `/api/interviews/<session_id>/gaze-recorder-results` | 🎓 | Receives gaze points; computes cheating score → `proctoring_score`. |
| POST | `/api/interviews/<session_id>/upload-recording` | 🎓 | Upload the webcam recording (`.webm`). |
| POST | `/api/interviews/<session_id>/upload-mobile-recording` | 🔓 | Upload the phone-camera environment recording. |
| GET | `/api/interviews` | 🔑 | List interviews (recruiters see all, candidates their own). |

## Invites — `routes/invite_routes.py` (prefix `/api`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/recruiter/jobs/<job_id>/invites/preview` | 🧑‍💼 | Parse & classify emails from text/CSV/XLSX before sending. |
| POST | `/api/recruiter/jobs/<job_id>/invites` | 🧑‍💼 | Send invites (creates tokens, burner accounts, pre-shortlisted applications, emails). |
| GET | `/api/recruiter/jobs/<job_id>/invites/batches/<batch_id>` | 🧑‍💼 | Batch send/redeem status. |
| GET | `/api/invite/redeem?token=` | 🔓 | Look up an invite token (used by the redeem page). |
| POST | `/api/invite/redeem` | 🔓 | Redeem: activates the burner account, returns Invite ID + temp credentials/JWT. |

## Admin — `routes/admin_routes.py` (prefix `/api/admin`, all 🛡️)

User & verification: `GET /stats`, `GET /users`, `GET /users/<id>`,
`DELETE /users/<id>`, `PUT /users/<id>/permissions`, `PUT /users/<id>/user-type`,
`GET /pending-recruiters`, `PUT /users/<id>/verify`, `PUT /users/<id>/reject`,
`GET /permissions`, `GET/PUT /candidates/<id>`, `GET/PUT /recruiters/<id>`,
`GET/DELETE /candidates/<id>/cv`.

Jobs & applications: `GET /jobs`, `GET/PUT/DELETE /jobs/<id>`,
`GET/PUT/DELETE /applications/<id>`, `PUT /applications/<id>/status`,
`GET /applications/<id>/report`, `GET /candidates/<id>/practice-history`,
`GET /practice/<session_id>/report`, `GET /system/stats`.

Cost statistics: `GET /cost-statistics`,
`GET /cost-statistics/candidates/usage`, `.../candidates/<id>/usage-lines`,
`.../recruiters/usage`, `.../recruiters/<id>/usage-lines`,
`.../candidates/credit-summary`, `.../candidates/<id>/credit-lines`,
`.../recruiters/credit-summary`, `.../recruiters/<id>/credit-lines`.

## Speech — `routes/speech_routes.py` (prefix `/api/speech`)

Both endpoints require authentication (🔑) — they proxy paid Google Cloud
APIs.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/speech/transcribe` | Google Cloud speech-to-text. |
| POST | `/api/speech/synthesize` | Google Cloud text-to-speech (used by the browser interview UI; the kiosk uses its own local Google clients instead). |

## Payments — `payment_module/routes/payment_routes.py` (prefix `/api/payment`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/plans` · `/recharge/packs` | Active recharge packs (filtered by audience). |
| GET | `/plans/<plan_id>` · `/plans/slug/<slug>` | One plan. |
| POST | `/payments/initiate` · `/recharge/initiate` | Create a Razorpay order for a pack. |
| POST | `/payments/verify` · `/recharge/verify` | Verify the Razorpay signature after checkout; credits the wallet. |
| GET | `/payments/<payment_id>` · `/payments/history` | Payment records. |
| POST | `/payments/<payment_id>/refund` | Refund flow. |
| GET | `/subscriptions/me` · `/wallet/summary` | Wallet balance + active pack summary. |
| GET | `/subscriptions/check` · `/wallet/check` | "Can I afford an interview?" check. |
| GET | `/subscriptions/history` | Past subscriptions/packs. |
| POST | `/subscriptions/cancel` | Cancel. |
| GET | `/credits/transactions` · `/wallet/transactions` | Credit ledger. |
| POST | `/interviews/use` | Debit credits for an interview usage. |
| POST | `/webhooks/razorpay` | Razorpay server-to-server webhook (signature-verified). |
| GET | `/health` | Payment module health. |

## Miscellaneous (in `app.py`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness/readiness — pings MongoDB, 503 if unreachable. |
| GET | `/` | Plain-text welcome. |
| POST | `/chat` · `/api/chat` | Direct LLM chat with cost tracking (logs to `openai_cost_logs`). |
| GET | `/cost-summary` · `/api/cost-summary` | Aggregated LLM cost summary. |
| POST | `/stt-cost` · `/api/stt-cost`, `/tts-cost` · `/api/tts-cost` | Record STT/TTS cost events. |
