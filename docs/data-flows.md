# End-to-End Data Flows

The complete journeys through the system, showing exactly which API calls,
socket events, and background jobs fire at each step.

## 1. Candidate applies for a job

Before applying, a candidate can check a **real** match score for any CV
against the job without creating an application: `POST
/api/jobs/<id>/check-cv-score {cv_id, use_manual_cv}` opens the same CV
picker used for applying (`CVSelectionModal`, `mode="check_score"`) and runs
the identical scoring engine used below — no more client-side random number.

```
Candidate (browser)                Backend                          Background worker
────────────────────               ────────                         ─────────────────
Dashboard: GET /api/jobs
Job page:  POST /api/jobs/<id>/apply
  (CV file, saved CV id, or          │
   manual cv_details)                ▼
                            ApplicationController.apply_for_job
                              • stores application with a frozen
                                cv_snapshot (text + details)
                              • processing_status: "processing"
                              • socket emit application_update
                                {type:"created"} → candidate +      queue.put(score_cv_task)
                                recruiter rooms                          │
                                                                         ▼
                                                              BackgroundProcessor (1 worker thread)
                                                              • parse CV (pdf_parser / structured parser)
                                                              • AI score CV vs JD (cv_scoring_service)
                                                              • status → shortlisted (cv_score >=
                                                                job.minimum_cv_score) / rejected (below
                                                                threshold) / pending (score below
                                                                threshold but CV-parsing confidence
                                                                wasn't "high" — held for manual review
                                                                instead of auto-rejecting a possibly
                                                                mis-parsed CV)
                                                              • email the candidate the outcome
                                                              • socket emit application_update
Recruiter dashboard updates live via useRealtimeApplications (no refresh needed)
```

Full status lifecycle: `pending` (scoring in progress, or held for manual
review) → `shortlisted` / `rejected` (CV-score threshold) → `interviewed`
(after the AI interview) → `screening_cleared` / `rejected` (the recruiter's
own post-interview call). **`rejected` is reused at two different points** —
a CV-score rejection (never interviewed) and a post-interview "not cleared"
call both persist as `status: "rejected"`. The frontend disambiguates the two
for display using `applicationStatusLabel()`
(`react-frontend/src/shared/utils/applicationStatus.js`): no `interview_score` on
the application → "Not Shortlisted"; an `interview_score` present → "Screening
Not Cleared". Both recruiter and candidate views use this helper so a
CV-stage rejection is never mislabeled as a screening outcome that never
happened.

## 2. Real AI interview (the core product flow)

```
1. Candidate clicks "Start Interview" on a shortlisted application (website).
2. Frontend builds secure-interview://start?initData=<token, apiUrl, application context>
   → OS launches the GenHire Secure Browser (Electron kiosk).
3. Kiosk renderer: POST /api/interviews/start {application_id}
   Backend:
   • verifies the application belongs to this candidate and has a CV
     (invite skeletons that never uploaded a CV are bounced back to apply)
   • reads the job's proctoring_config → cost = 30 or 50 (proctored) credits
   • checks + debits the RECRUITER's wallet
     (idempotency_key "real-interview:<application_id>", or ":r<n>" after a
     refund — retries never double-charge, and refunded attempts re-charge)
   • writes CV + JD text to transient staging .txt files (OS temp dir)
   • InterviewSessionManager.create_session() → session_id +
     hardcoded first question (context builds in a background thread)
   • inserts the `interviews` document (status: active,
     questions_answered_count: 0, debit_idempotency_key persisted)
   • if anything fails AFTER the debit, the charge is refunded immediately
4. IDENTITY CAPTURE — the candidate takes a selfie
   (POST .../register-face):
   • NO identity card on the account → 403 identity_card_required. This is
     the only identity condition that stops an interview; the candidate
     uploads their card once on /profile and it is locked afterwards
     (admins alone can replace it).
   • otherwise → the capture is stored (GridFS), identity_verification.status
     becomes "score_pending", the interview flips to "active", and the
     endpoint RETURNS IMMEDIATELY
   • a background daemon thread then sends the ID card + the capture through
     the LLM chain on a vision model (face_match_service) and writes back
     status "scored" with a 0-100 similarity vs FACE_MATCH_THRESHOLD (75),
     or "score_unavailable" if every provider failed. The summary is copied
     onto the application so the recruiter's candidate card can badge it.
   • the score NEVER blocks, delays, or fails the interview for any account
     type — the recruiter sees the number and both photos and decides
   • FACE_VERIFICATION_MODE=off skips capture and scoring entirely
     (status "skipped")
5. Kiosk/browser enables lockdown, connects Socket.IO, emits
   start_proctoring. Live frames are compared against this session's own
   capture, held in the in-memory live_sessions store.
6. Interview loop (repeats, up to max_questions):
   • the question appears on screen as the AI speaks it (TTS)
   • candidate answers by voice → streaming STT → text
   • pacing (same for real and practice):
       - candidate never spoke → 30 s countdown → auto-advance ("no answer")
       - candidate spoke, then 10 s of silence → answer auto-submits
       - substantive answers get a short spoken acknowledgement before the
         next question; empty ones get "No problem, let's move on."
   • POST .../answer {question, answer} → evaluation + next question
     (each non-empty answer $inc's questions_answered_count)
   • meanwhile: the WEB UI streams 1 frame/sec → proctoring_frame →
     server-side MediaPipe + DeepFace. The KIOSK analyzes frames locally
     (MediaPipe FaceLandmarker + coco-ssd phone detection) and relays only
     violations. Gaze points are collected either way; blur/app-switch →
     proctoring_violation
7. Wrap-up:
   • gaze results   → POST .../gaze-recorder-results
   • webcam video   → POST .../upload-recording
   • phone video    → POST .../upload-mobile-recording (if paired)
   • POST .../end →
       - ZERO answers recorded? → the interview is DISCARDED instead of
         scored: recruiter's credits refunded, interview → "abandoned",
         application left untouched (candidate can retake), response
         {status: "interview_discarded", refund: {...}}
       - otherwise:
       - final evaluation generated (rubrics + AI-detection per answer)
       - interview_score = 70% answer quality + 30% language quality (×100)
       - proctoring_score = min(gaze-based score, live-frame score);
         null + "incomplete" if neither signal exists
       - application updated → status "interviewed", scores stored
       - job counters synced, socket event pushed to both parties
       - emails sent to recruiter and candidate (fire-and-forget threads)
       - usage telemetry recorded (LLM tokens, STT seconds, TTS characters)
8. Kiosk exits lockdown and offers to return to the website
   (opens the default browser via open-external).

Abandoned sessions (tab closed, crash): the InterviewRefundSweeper checks
every INTERVIEW_REFUND_SWEEP_INTERVAL_MINUTES (15) for sessions stuck
"active" past INTERVIEW_ABANDON_TTL_MINUTES (120). Sessions WITH answers are
auto-finalized into a normal scored report (the recruiter paid for a
screening signal and gets one); sessions WITHOUT answers are refunded and
marked "abandoned".
```

## 3. Recruiter reviews results

```
RecruiterDashboard: GET /api/applications      (or per-job .../applications)
InterviewReportModal: GET /api/applications/<id>/interview-report
  → evaluation, transcript (with per-answer ai_probability),
    proctoring score/status, gaze heatmap data,
    identity_verification block + captured/reference face images
    (GET /api/interviews/<sid>/face-image/{captured|reference})
Decision: PUT /api/applications/<id>/status
          {status: "screening_cleared"|"rejected"}
  (legacy value "selected" still accepted and normalized; the platform only
   SCREENS — "screening_cleared" candidates go into the recruiter's own
   further hiring rounds; "rejected" displays as "Screening Not Cleared")
  → candidate emailed + socket event + job counters updated
```

## 4. Bulk invite flow (pre-shortlisted candidates)

```
1. Recruiter opens InviteCandidatesModal on a job
   → POST /api/recruiter/jobs/<job_id>/invites/preview
     (paste text, or upload CSV/XLSX — emails parsed and classified)
2. POST /api/recruiter/jobs/<job_id>/invites  → charges the recruiter
   RECRUITER_INVITE_CREDITS_PER_CANDIDATE (1) per invitee upfront, then for
   each email, InviteService:
   • creates or refreshes an invite token (SHA-hashed, TTL — Mongo expires it)
   • creates a "burner" invite-only user (no email uniqueness clash —
     the sparse unique index skips them) with a generated Invite ID
   • creates a pre-shortlisted application skeleton
     (processing_status: "awaiting_candidate")
   • sends the invite email (invite_email_templates) — a row whose email
     fails to send is auto-refunded (the invite/link still exists for manual
     sharing)
   • all grouped under an invite_batches record
3. Recruiter polls GET .../invites/batches/<batch_id> for send/redeem status.
4. Candidate clicks the email link → /invite/redeem (React page)
   → GET /api/invite/redeem?token=...  (lookup)
   → POST /api/invite/redeem           (consume: activates the burner account,
                                        hands over the Invite ID login)
5. Candidate logs in with the Invite ID, uploads a CV to complete the
   application and an identity card on their profile, then takes the
   interview (flow #2). Interview start is blocked until both exist.
6. InviteCleanupScheduler periodically purges burner accounts that never
   became active.
```

## 5. Buying credits

```
SubscriptionPlans page: GET /api/payment/recharge/packs
  → POST /api/payment/recharge/initiate {plan_id}   (creates Razorpay order)
  → useRazorpay opens the Razorpay Checkout modal
  → POST /api/payment/recharge/verify {order/payment ids + signature}
  → wallet credited, ledger row written → /payment/success
(In parallel, Razorpay hits POST /api/payment/webhooks/razorpay server-side.)
```

## 6. Practice interview (candidate-paid)

```
Practice page → deep link into the kiosk (same as flow #2) but:
  • POST /api/practice/start          (debits the CANDIDATE's wallet 30/50;
                                       refunded if starting fails after the
                                       debit)
  • POST /api/practice/<sid>/answer   (same engine, evaluators, and 30s/10s
                                       pacing rules as real interviews)
  • POST /api/practice/<sid>/end      (zero answers → session discarded +
                                       candidate credits refunded)
  • identity is capture-only — the selfie is taken for live proctoring, is
    never scored against the ID card, and never blocks (no identity card is
    required to practice)
  • results in `practice_sessions`; history via GET /api/practice/history,
    reports via GET /api/practice/<sid>/report
  • abandoned practice sessions: sweeper refunds if unanswered, otherwise
    closes them without a refund
```

## 7. Auth flows

- **Register** → `POST /api/register` → verification email (when
  `REQUIRE_EMAIL_VERIFICATION=true`) → `/verify-email` page →
  `POST /api/verify-email` → login allowed.
- **Recruiter signup** additionally waits for **admin approval**
  (`/admin/verification` → `PUT /api/admin/users/<id>/verify`); unverified
  recruiters are blocked from posting jobs by `@verified_required`.
- **Google OAuth** → `POST /api/google-oauth` with the Google credential
  → backend verifies it against `GOOGLE_CLIENT_ID` → our JWT.
- **Session expiry** — any 401 anywhere clears the session and fires
  `auth:session-expired` → redirect to `/login?expired=1`.
- **Socket auth** — the JWT is passed in the Socket.IO handshake; invalid
  tokens are disconnected immediately and the UI falls back to REST polling.

## 8. Recruiter creates a job posting (AI generation + JD file, merged)

```
Recruiter (JobCreationModal)                          Backend
─────────────────────────────                         ────────
"Create with AI" section:
  type a prompt, and/or upload a JD file (PDF/TXT)
        │
        ▼
POST /api/jobs/generate-ai
  (JSON {prompt}, or multipart {prompt, jd_file})  →   job_controller.generate_jd_with_ai
                                                          • jd_file given → pdf_parser extracts text
                                                            (temp file, deleted after — NOT the final
                                                            upload; see below)
                                                          • LLM prompt = "extract & structure this
                                                            document" (+ prompt as extra instructions)
                                                            when a file was given, else the classic
                                                            free-text prompt
                                                          • deducts RECRUITER_AI_JD_CREDITS,
                                                            refunds on any failure
  ← job_data (title, department, skills, description,
     responsibilities, requirements, benefits, ...)
        │
        ▼
Form is auto-filled; recruiter reviews/edits, sets
minimum_cv_score + proctoring_config, clicks "Create Job"
        │
        ▼
POST /api/jobs
  multipart {..job fields.., jd_file}              →   job_controller.create_job
    (jd_file re-sent here — the SAME file the AI          • array fields (skills/responsibilities/
     parsed a moment ago; only sent once for real,          requirements/benefits) arrive as JSON-
     avoiding an orphaned GCS upload if the recruiter        stringified arrays, not comma-split, so
     abandons the form after generating but before           multi-line values survive intact
     creating)                                            • jd_file → uploaded to Cloud Storage at
                                                              jds/<recruiter_id>/jd_<uuid>.<ext>;
                                                              text re-extracted for jd_extracted_text
                                                            • GCS failure/not-configured is NON-FATAL —
                                                              the job is still created, just without a
                                                              downloadable JD file
  ← job created (201)
```

Candidates then see the job as usual (`GET /api/jobs`, `GET /api/jobs/<id>`)
— `jd_pdf_path`/`jd_gcs_path` ride along on the job document, and the job
details page's "Download JD" button calls `GET /api/jobs/<id>/jd-download`
for a signed URL when they're set, falling back to a generated plain-text
summary of the structured fields when no JD file was ever uploaded.
