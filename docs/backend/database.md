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
invites — these log in with an Invite ID, not an email).

### `jobs`
Recruiter job postings. Key fields: `title`, `company`, `department`,
`location`, `type`, `experience`, `salary`, `description`, `skills`,
`responsibilities`, `requirements`, `benefits`, `created_by` (recruiter id),
`proctoring_config` (per-job toggles: `voice_detection`, `object_detection`,
`eyeball_tracking`, `gaze_heatmap`), and denormalized status counters
(`pending`, `interviewed`, `selected`, `rejected`) that are `$inc`-synced
whenever an application changes status.

### `applications`
One per candidate-job application. Key fields: `job_id`, `student_id`,
`student_name`, `student_email`, `job_title`, `status`
(`pending` → `shortlisted`/`rejected` → `interviewed` → `selected`/`rejected`),
`cv_snapshot` (frozen copy of the CV used to apply: `text`, `details`,
metadata), `cv_score` (AI CV-vs-JD match, 0–100),
`processing_status` (`processing` while the background CV scorer runs;
`awaiting_candidate` for invite skeletons that still need a CV),
`interview_score`, `proctoring_score`, `proctoring_status`
(`complete` | `incomplete`), `is_visible`, `stt_seconds`, `tts_characters`,
`usage_source`.

### `interviews`
One per real AI interview session. Key fields: `user_id`, `session_id` (UUID
from the interview engine), `application_id`, `recruiter_id`, `status`
(`active` → `completed`), `cv_path`/`jd_path` (temp .txt files),
`similarity_score`, `proctoring_config`, `proctoring_score`,
`proctoring_status`, `evaluation` (full AI evaluation object), `final_score`,
`transcript` (`[{role, text, ai_probability}]`), `manual_infractions`,
`gaze_metrics`, `gaze_plot_path`, `gaze_recorder_*` (recording/analysis/points
paths + analysis + score), `recording_path`, `mobile_recording_path`,
`usage_summary`, `usage_deduction`, `start_time`.

### `practice_sessions`
Candidate practice interviews — analogous to `interviews` but candidate-paid
and not linked to an application.

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
- **credit transactions** — append-only ledger; every debit/credit has a `transaction_type`, `reference_type`/`reference_id`, optional `idempotency_key` (prevents double-charging, e.g. `real-interview:<application_id>`), and `balance_after`.

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
