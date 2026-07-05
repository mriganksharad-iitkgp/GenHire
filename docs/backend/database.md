# Database — MongoDB Collections & Indexes

The backend uses **MongoDB via PyMongo directly** (no ORM). Connection is
managed by `config/database.py` (`DatabaseConfig`), reading `MONGODB_URI` and
`DATABASE_NAME` (default `hrtech`). Pooling: `maxPoolSize=50`, `minPoolSize=0`
(idle connections are not pre-opened because Atlas closes them and causes SSL
resets), 10 s connect/server-selection timeouts, 30 s socket timeout.

`db_config.get_collections()` returns the seven core collections; a few more
are accessed ad-hoc via `db.get_collection(...)`.

## Core collections

### `users`
One document per account — candidates, recruiters, and admins share the
collection, distinguished by `user_type`.

Key fields: `name`, `email`, `email_lower`, `password` (hashed), `user_type`
(`candidate` | `recruiter` | `admin`), `is_verified` (recruiter admin-approval
and/or email verification), `is_active`, `permissions` (admin permission list,
`*` = super admin), `cv_details` (structured CV on the profile),
`is_invite_only` + `invite_id_lower` (burner accounts created by recruiter
invites — these log in with an Invite ID, not an email), and `face_profile`
(`{image_file_id (GridFS), registered_at, source_session_id,
source_application_id}` — the permanent face identity enrolled at the
candidate's **first** real interview; every later real interview is verified
against it).

### `jobs`
Recruiter job postings. Key fields: `title`, `company`, `department`,
`location`, `type`, `experience`, `salary`, `description`, `skills`,
`responsibilities`, `requirements`, `benefits`, `created_by` (recruiter id),
`minimum_cv_score` (auto-shortlist/reject threshold, default 50),
`proctoring_config` (per-job toggles: `voice_detection`, `object_detection`,
`eyeball_tracking`, `gaze_heatmap`), and denormalized status counters
(`pending`, `interviewed`, `screening_cleared`, `rejected`) that are
`$inc`-synced whenever an application changes status. (`selected` is the
legacy name for the `screening_cleared` counter — folded in by
`scripts/migrate_screening_cleared.py`.)

JD file fields (populated when a recruiter uploads a JD file — either
directly on the create-job form, or via AI JD generation's "upload to parse"
option): `jd_pdf_path` (`gs://` URI, the file's location in Cloud Storage),
`jd_gcs_path` (bare bucket-relative object path, used to generate signed
download URLs and to delete), `jd_original_filename` (for the download's
filename), `jd_extracted_text` (parsed text, also fed to AI JD generation
when a file is uploaded there), `jd_upload_date`. All are `None` if the
recruiter never uploaded a JD file (prompt-only AI generation or a fully
manually-typed job) — the candidate-facing "Download JD" button falls back to
a generated plain-text summary in that case.

### `applications`
One per candidate-job application. Key fields: `job_id`, `student_id`,
`student_name`, `student_email`, `job_title`, `status`
(`pending` → `shortlisted`/`rejected` → `interviewed` →
`screening_cleared`/`rejected`; `selected` is the pre-migration legacy value
for `screening_cleared`, still accepted on read),
`cv_snapshot` (frozen copy of the CV used to apply: `text`, `details`,
metadata), `cv_score` (AI CV-vs-JD match, 0–100),
`minimum_cv_score_required` (the job's threshold at the time this
application was scored — a snapshot, so later job-threshold edits don't
retroactively change past decisions),
`processing_status` (`processing` while the background CV scorer runs;
`awaiting_candidate` for invite skeletons that still need a CV),
`interview_score`, `proctoring_score`, `proctoring_status`
(`complete` | `incomplete`), `is_visible`, `stt_seconds`, `tts_characters`,
`usage_source`, `identity_verification` (copied from the interview: status,
distance, attempts — surfaces on the recruiter's candidate card), and
`interview_refund_count` (how many times a start-of-interview debit was
refunded; each refund makes the next attempt use a fresh idempotency key).

### `interviews`
One per real AI interview session. Key fields: `user_id`, `session_id` (UUID
from the interview engine), `application_id`, `recruiter_id`, `status`
(`active` → `completed` | `abandoned` (discarded/refunded) |
`identity_blocked` (face verification failed repeatedly)),
`cv_path`/`jd_path` (temp .txt files),
`similarity_score`, `proctoring_config`, `proctoring_score`,
`proctoring_status`, `evaluation` (full AI evaluation object), `final_score`,
`transcript` (`[{role, text, ai_probability}]`), `manual_infractions`,
`gaze_metrics`, `gaze_plot_path`, `gaze_recorder_*` (recording/analysis/points
paths + analysis + score), `recording_path`, `mobile_recording_path`,
`usage_summary`, `usage_deduction`, `start_time`,
`identity_verification` (`{status, verified, distance, threshold, attempts,
checked_at, captured_image_file_id, reference_image_file_id}`),
`debit_idempotency_key` (the exact key used for the recruiter debit, so
refunds can reverse it precisely), `questions_answered_count` (incremented
per substantive answer — the zero-answer refund decision survives a server
restart), and on auto-finalized docs `auto_finalized` +
`auto_finalized_reason` / `abandoned_reason` + `credits_refund`.

### `practice_sessions`
Candidate practice interviews — analogous to `interviews` but candidate-paid
and not linked to an application. Status `active` → `completed` |
`abandoned` (with `abandoned_reason` and, when refunded, `credits_refund`).

### `invite_tokens`
One per invite email. Fields include `token_hash` (SHA hash — raw tokens are
never stored), `user_id` (the burner account), `expires_at`. Mongo TTL
auto-deletes expired tokens.

### `invite_batches`
One per bulk-invite action: `recruiter_id`, `job_id`, counts of
sent/valid/invalid/redeemed, `created_at`.

## Cost/telemetry collections (ad-hoc access)

- `openai_cost_logs` — every tracked LLM call (tokens, model, cost, request id).
- `speech_cost_logs` — STT seconds / TTS characters cost events.
- Usage-telemetry events written by `usage_telemetry_service.record_usage_event()` power the admin/recruiter/candidate cost-statistics endpoints.

## Payment collections (`payment_module/models/`)

- **plans** — recharge packs seeded from `PaymentConfig.DEFAULT_PLANS` (Candidate Pro ₹499/500cr, Candidate Max ₹999/1000cr, Recruiter Pro ₹4,999/5000cr, Recruiter Max ₹9,999/10000cr — prices stored in paise).
- **payments** — Razorpay order/payment records and their verification status.
- **subscriptions** — purchased packs per user.
- **credit wallets** — one wallet per (user, audience) with the current balance.
- **credit transactions** — append-only ledger; every debit/credit has a `transaction_type`, `reference_type`/`reference_id`, optional `idempotency_key` (prevents double-charging, e.g. `real-interview:<application_id>`, or `:r<n>`-suffixed after refunds; refunds use `refund:<debit-key>` with types `real_interview_refund` / `practice_interview_refund`), and `balance_after`.

## Indexes (ensured on every startup by `_ensure_indexes()`)

| Collection | Index | Why |
|---|---|---|
| `users` | `uq_users_email_lower_real` — **unique + sparse** on `email_lower` | Enforces one real account per email while letting invite-only burner docs (which have `email_lower: null`) share an email. Legacy non-sparse unique email indexes are detected and dropped on boot. |
| `users` | `idx_users_email` (sparse, non-unique) | Email lookups. |
| `users` | `uq_users_username_lower` (unique, sparse) | Legacy invite docs. |
| `users` | `uq_users_invite_id_lower` (unique, sparse) | Invite ID is the login identifier for burner accounts. |
| `users` | `idx_users_is_invite_only` (sparse) | Cleanup scheduler queries. |
| `invite_tokens` | `uq_invite_tokens_hash` (unique) · `idx_invite_tokens_user` · `ttl_invite_tokens_expires_at` (TTL) | Token lookup, per-user lookup, automatic expiry. |
| `invite_batches` | `idx_invite_batches_recruiter` · `idx_invite_batches_job` · `idx_invite_batches_created_at` | Batch status queries. |
| `applications` | `idx_applications_job_visible` on `(job_id, is_visible)` | Matches the recruiter dashboard query. |
| `applications` | `idx_applications_job_student` on `(job_id, student_id)` | "Has this candidate already applied to this job?" lookup. |

All index creation is wrapped in try/except so legacy duplicate data never
blocks startup.
