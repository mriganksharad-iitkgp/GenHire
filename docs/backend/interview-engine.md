# AI Interview Engine & Proctoring

This document explains how an AI interview actually runs: question
generation, answer evaluation, scoring, and all four proctoring signals.

## Components

```
python-backend/
├── interview/
│   ├── config/settings.py        # InterviewConfig, LLMConfig, LLMProvider
│   ├── core/
│   │   ├── session_manager.py    # InterviewSessionManager — the heart of it
│   │   ├── prompt_based_question_generator.py  # LLM question generation
│   │   ├── llm_wrapper.py        # call_llm_with_tracking (cost-logged LLM calls)
│   │   ├── cost_tracker.py       # per-session token/STT/TTS usage tracking
│   │   ├── speech_cost_tracker.py# STT/TTS cost events
│   │   └── pricing.py            # model price tables
│   ├── document/                 # DocumentLoader — reads CV/JD text files
│   ├── llm/                      # LLM provider clients (Groq)
│   └── prompts/                  # prompt templates
├── evaluation_model/rubrics_eval/
│   ├── answer_evaluator.py       # scores answer content against rubrics
│   ├── communication_evaluator.py# scores language/communication quality
│   ├── answer_classifier.py      # classifies answer types
│   └── rubric_generator.py, evaluation_system.py, ...
├── utils/
│   ├── ai_detection.py           # "was this answer AI-generated?" probability
│   ├── cheating_detection.py     # proctoring analysis helpers
│   └── gaze_recorder_service.py  # GazeRecorder page builder + gaze analysis
└── security_check.py             # per-frame MediaPipe + DeepFace analysis
```

The LLM is **Groq** (`GROQ_API_KEY`), with a fallback chain
(`_create_fallback_llm` / `llm_fallback_service.py`) if the primary model
fails. The model recorded for usage fallback is `llama-3.3-70b-versatile`.

## Session lifecycle (`InterviewSessionManager`)

### 1. `create_session(cv_path, jd_path, ...)`
- Generates a UUID `session_id`, starts a `CostTracker` session.
- Loads the CV and JD text via `DocumentLoader` (files were written to
  `uploads/tmp/` by the start route from trusted DB data, so validation is
  skipped with `pre_validated=True`).
- Returns **instantly** with a hardcoded first question — *"Hello, I'm Alex.
  Great to meet you! Could you please give me a brief introduction about
  yourself and your background?"* — for zero-lag startup.
- Meanwhile a **background thread** builds the real conversation context from
  the CV sections + JD (`initialize_conversation`), marks the greeting done,
  and jumps the phase to `EXPERIENTIAL_QUESTIONS`. The session holds an
  `init_event` the answer path can wait on.
- Also returns `question_timeout_seconds`, a `question_deadline`, and
  `max_questions` so the client can show progress ("Question 3 of 8") and
  enforce pacing.

### Interview pacing (client-side, identical for real and practice)

The question text appears on screen as the AI speaks it. After the AI
finishes speaking:

- **Candidate never speaks** → a 30-second countdown runs
  (`NO_ANSWER_TIMEOUT_SECONDS`); on expiry the interview auto-advances with
  an empty answer and the AI says *"No problem, let's move on."*
- **Candidate speaks, then goes silent** → after 10 seconds of silence
  (`POST_SPEECH_SILENCE_SECONDS`) the answer auto-submits.
- Substantive answers get a short spoken acknowledgement ("Alright, thank
  you." / "Got it." …) before the next question, so the flow feels
  conversational rather than form-like.

### 2. `submit_answer(session_id, question, answer)`
- Evaluates the answer and generates the next question, adapting difficulty
  and topic to the candidate's demonstrated skill level (the conversation
  context tracks `candidate_skill_level`, `current_topic`,
  `interview_phase`).
- Evaluation runs through the `rubrics_eval` evaluators
  (answer quality + communication quality) plus `ai_detection`
  (an `ai_probability` per answer, stored into the transcript).
  Slow evaluation work runs on background threads
  (`bg_evaluate_and_update`) so the next question isn't blocked.
- Empty answers are legal — a client-side timeout submits `""` to advance
  the interview instead of leaving it stuck.
- Every **non-empty** answer `$inc`s `questions_answered_count` on the
  interview document — this drives the zero-answer refund decision (below)
  and survives server restarts.
- `_should_continue_interview` decides when the interview is complete.

### 3. Ending — `POST /api/interviews/<session_id>/end` (in `app.py`)
- **Zero-answer discard**: if not a single substantive answer was recorded,
  the interview is not scored at all — the recruiter's start-time debit is
  refunded (idempotently), the interview doc becomes `abandoned`, the
  application keeps its prior status so the candidate can simply retake,
  and the response is `{status: "interview_discarded", refund: {...}}`.
- Otherwise, `_generate_final_evaluation(session)` produces the evaluation object
  (quantitative scores, summary, per-question breakdown).
- **Interview score** = `round((answer_score * 0.7 + language_score * 0.3) * 100)`
  — 70% answer quality, 30% language quality. Falls back to `final_score` or
  the conversation-summary averages if the quantitative scores are missing.
- The transcript (`[{role: assistant|user, text, ai_probability}]`) is stored
  on the interview document.
- Actual media usage is derived (TTS characters from assistant turns, STT
  seconds from the interview duration) and logged via `CostTracker` +
  `record_usage_event` for the cost dashboards.
- The linked application is updated (`status: "interviewed"`,
  `interview_score`, `proctoring_score`), job counters are `$inc`-synced,
  a real-time `application_update` is emitted to the candidate's and
  recruiter's socket rooms, and both parties get notification emails
  (fire-and-forget threads).

## Face identity verification (`services/face_verification_service.py`)

Before any real interview runs, `POST .../register-face` acts as an
**identity gate**:

1. **First real interview ever** → the captured selfie is enrolled as the
   account's permanent identity: stored in GridFS and referenced from
   `users.face_profile`. Status: `registered_new`.
2. **Every later real interview** (any company's job) → the new selfie is
   compared against the registered face with **DeepFace (VGG-Face)**:
   - match → `verified`, interview proceeds;
   - mismatch → the candidate may retry up to `FACE_VERIFY_MAX_ATTEMPTS`
     (default 3); after that the interview is **blocked**
     (interview status `identity_blocked`, HTTP 403
     `error_code: face_mismatch_blocked`) and the attempt is recorded.
     Blocked sessions are refunded by the sweeper.
3. A quality gate rejects images with no face / multiple faces before any
   comparison (`error_code`s the UI turns into "retake photo" hints).

The captured photo (and the reference, on later interviews) is stored per
interview and served to the interview owner, the job's recruiter, and admins
via `GET .../face-image/{captured|reference}` — the recruiter sees a
"Candidate Identity" section in the report and an identity chip on the
candidate card (`identity_verification` on the application).

Modes (`FACE_VERIFICATION_MODE`): `enforce` (default, blocks impersonators),
`monitor` (records mismatches, never blocks), `off`. If the DeepFace/OpenCV
stack isn't installed, verification degrades to photo capture with status
`unverified_system_unavailable` — a missing server dependency never locks a
candidate out. **Practice sessions soft-verify**: the photo is taken, but a
mismatch never blocks.

## Proctoring — four independent signals

Per-job `proctoring_config` toggles: `voice_detection`, `object_detection`,
`eyeball_tracking`, `gaze_heatmap`. If **any** are enabled, the interview
costs the recruiter 50 credits instead of 30.

### Signal 1 — Live frame analysis (Socket.IO)
1. The identity-gate selfie from `register-face` initializes the in-memory
   `live_sessions` dict with `proctoring_score: 100`. When the account has a
   registered face profile, **that** image (not just the session selfie) is
   the comparison reference — someone can't enroll a stand-in's face for a
   single session.
2. The kiosk emits `start_proctoring` (joins the session room) and then one
   `proctoring_frame` per second (base64 JPEG).
3. `security_check.analyze_frame_for_proctoring()` runs **MediaPipe head-pose**
   and **DeepFace identity** checks against the registered face; infractions
   reduce the running score.
4. Violations trigger a `proctoring_alert` back to the kiosk in real time.

### Signal 2 — GazeRecorder eye tracking (third-party CDN)
The backend serves an HTML page at
`/api/interviews/<session_id>/gaze-recorder-page` that loads GazeCloudAPI /
GazeRecorderAPI scripts from `app.gazerecorder.com`. Gaze points are POSTed to
`/gaze-recorder-results`, where `gaze_recorder_service.analyze_gaze_patterns()`
computes a `cheatingScore`; `proctoring_score = 100 - cheatingScore`. Heatmap
and raw-point files are saved under `uploads/proctoring/gaze_recorder/`.
This signal depends on the CDN script loading in the candidate's browser.

### Signal 3 — Manual violations
Tab switches / window blur / app switches detected client-side are emitted as
`proctoring_violation` events and counted as `manual_<type>` infractions.
In the kiosk these fire when Electron detects window blur during kiosk mode.

### Signal 4 — Mobile second camera
A QR code pairs the candidate's phone (`/mobile-cam/:sessionId` page in the
React app) to the session room. The desktop relays start/stop via
`control_mobile_recording`; the phone records the environment and uploads to
`/api/interviews/<session_id>/upload-mobile-recording`.

### Final proctoring score
At `/end`, the backend takes the **minimum** of the GazeRecorder-based DB
score and the live frame-analysis score (either method catching a problem
counts — they're independent signals). If **neither** signal is available
(camera denied, CDN blocked), the score is stored as `null` with
`proctoring_status: "incomplete"` — the system never fabricates a passing
score. A matplotlib gaze-ratio plot is also generated from client tracking
data and saved to `uploads/proctoring/`.

## Credit lifecycle & refunds (`services/interview_credit_service.py`)

Interviews are **charged at start** (recruiter wallet for real, candidate
wallet for practice) and refunded — always idempotently, key
`refund:<original-debit-key>` — whenever the session produced **zero
substantive answers**:

- start failed right after the debit,
- identity verification blocked the candidate,
- the candidate abandoned the tab / crashed before answering,
- `/end` was called with nothing answered (→ `interview_discarded`).

Once one real answer exists, the charge stands. Each real-interview refund
`$inc`s `interview_refund_count` on the application, and the next `/start`
derives a fresh debit key (`real-interview:<app_id>:r<n>`) — replaying the
original key after a refund would return the old transaction and never
actually re-charge.

The **`InterviewRefundSweeper`** daemon (started in `app.py`, same pattern
as the invite cleanup scheduler) runs every
`INTERVIEW_REFUND_SWEEP_INTERVAL_MINUTES` (15) and looks for sessions stuck
in `active` / `identity_blocked` past `INTERVIEW_ABANDON_TTL_MINUTES` (120):

| Stale session | Outcome |
|---|---|
| Real, has answers, in-memory state alive | **Auto-finalized** into a normal scored report (`auto_finalized: true`) — the recruiter paid for a screening signal and gets one. No refund. |
| Real, no answers | Refunded + marked `abandoned`. |
| Practice, has answers | Closed as `abandoned`, no refund (per-answer feedback already stored). |
| Practice, no answers | Refunded + marked `abandoned`. |

## Practice interviews

`practice_routes.py` + `practice_controller.py` reuse the same engine for
candidate-paid mock sessions (`/api/practice/*`): same
start/answer/end flow and the same client pacing rules, results stored in
`practice_sessions`, charged to the **candidate's** wallet (30/50 credits)
rather than the recruiter's, with history and per-session reports available
to the candidate (and admins). Same refund rules: failed starts and
zero-answer endings give the credits back.

## Cost tracking

Every LLM call goes through `call_llm_with_tracking()` which logs
tokens + computed cost to `openai_cost_logs`. STT/TTS usage is logged to
`speech_cost_logs` (`process_stt` / `process_tts`). `CostTracker` aggregates
per-session usage into `usage_summary` on the interview document, and
`record_usage_event()` writes telemetry rows powering the cost-statistics
dashboards (admin sees everything; recruiters and candidates see their own).
