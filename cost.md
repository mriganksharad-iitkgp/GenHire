# GenHire — Cost Model & Projections

> **Every number below is an assumption-based estimate.** Provider prices are
> as known in **January 2026** and change often — re-verify each one before
> budgeting. Currency: **USD**, with INR at an assumed **₹84 / USD**.

---

## 1. Architecture being priced (current repo)

| Component | What runs there | Provider |
|---|---|---|
| `react-frontend/` | CRA SPA | Vercel |
| `python-backend/` | Flask + Socket.IO (gunicorn, 1 eventlet worker) | Google Cloud Run (europe-west1) |
| Database | MongoDB (users, jobs, applications, interviews, GridFS files) | MongoDB Atlas |
| Object storage | CVs, JDs, interview + mobile recordings, gaze artifacts | Google Cloud Storage |
| Speech | STT (interview answers), TTS (interviewer voice) | Google Cloud Speech / TTS |
| LLM chain | Interview Q-gen + evaluation, CV parse/score, face match, JD gen | **Groq (primary) → Gemini → OpenAI** (`LLM_PROVIDER_PRIORITY`) |
| Email | Verification, invites, notifications | ZeptoMail (primary; Mailgun sandbox fallback) |
| Payments | Recharge packs | Razorpay (2% of transaction value — a revenue cost, excluded from infra totals) |
| Kiosk | Electron desktop app | one-time build, no runtime cost |

---

## 2. Usage assumptions

**User mix per daily-active-user (DAU):** 80 % candidates, 20 % recruiters.

**Daily activity (per 100 DAU):**

| Event | Count/day | Basis |
|---|---|---|
| Real interviews | 20 | 25 % of candidates interview on an active day |
| Practice interviews | 12 | 15 % of candidates |
| Applications (CV parse + score) | 40 | 0.5 per active candidate |
| AI JD generations | 4 | 1 per 5 active recruiters |
| Transactional emails | 60 | verification + invites + notifications |

**Per-interview profile (real):** ~20 min total; 8 questions; candidate speaks
~10 min (STT); interviewer TTS ~2,000 characters; LLM ≈ 50k input + 10k output
tokens across question generation + per-answer evaluation + final report;
1 face-match call (2 images); ~60 MB of recordings (webcam + mobile) kept 90
days. Practice ≈ half of the above and no recordings.

**Per-application:** CV parse + JD match ≈ 8k in / 1.5k out tokens.

---

## 3. Unit prices assumed (Jan 2026 — re-verify)

| Item | Price (USD) |
|---|---|
| Groq llama-3.3-70b-versatile | $0.59 / 1M in, $0.79 / 1M out |
| Groq llama-4-scout (vision, face match) | $0.11 / 1M in, $0.34 / 1M out |
| OpenAI gpt-4o-mini | $0.15 / 1M in, $0.60 / 1M out |
| Gemini flash-lite | $0.075 / 1M in, $0.30 / 1M out (free tier: heavily limited) |
| Google STT (standard, streaming) | **$0.016 / minute** |
| Google TTS Neural2 | $16 / 1M characters |
| GCS standard storage | $0.020 / GB-month |
| Cloud Run | $0.000024 / vCPU-s + $0.0000025 / GiB-s (1 vCPU / 1 GiB config) |
| MongoDB Atlas | M0 free → M10 $57/mo → M30 ~$390/mo → M50 ~$1,550/mo |
| ZeptoMail | 1 credit = ₹150 = 10,000 emails (valid 6 mo); assumed 30k emails/mo = ₹450/mo |
| Mailgun (fallback) | Foundation $35/mo (50k emails) → Growth $90/mo (100k) |
| Vercel | Hobby $0 → Pro $20/user/mo |
| Razorpay | ~2 % of payment value (excluded from totals) |

**Per-event unit costs derived from the above:**

| Event | LLM (Groq) | Speech | Total ≈ |
|---|---|---|---|
| Real interview | $0.037 | $0.16 STT + $0.032 TTS | **$0.23** |
| Practice interview | $0.019 | $0.096 | **$0.12** |
| Application processed | $0.006 | — | **$0.006** |
| Face match | <$0.001 | — | ~$0.001 |
| AI JD generation | $0.01 | — | $0.01 |

> **The single biggest cost driver is Google STT** (≈ 70 % of per-interview
> cost). See §6 for the Groq-Whisper lever that cuts it ~8×.

---

## 4. Monthly cost by scale (30 active days)

### 100 DAU  (≈ 600 real + 360 practice interviews, 1,200 applications / month)

| Component | USD/mo | INR/mo |
|---|---|---|
| Speech (STT + TTS) | $150 | ₹12,600 |
| LLM (all tasks, Groq-first) | $40 | ₹3,360 |
| Cloud Run (mostly 1 warm instance) | $25 | ₹2,100 |
| MongoDB Atlas (M10) | $57 | ₹4,800 |
| GCS (~110 GB steady incl. recordings @ 90-day retention) | $5 | ₹420 |
| ZeptoMail (~1,800 emails/mo → 1 credit lasts months; ₹450/mo at the 30k assumption) | $5 | ₹450 |
| Vercel (Pro, 1 seat) | $20 | ₹1,680 |
| Sentry / misc | $0–10 | ₹0–840 |
| **Total** | **≈ $335 / mo** | **≈ ₹28,000 / mo** |

### 1,000 DAU  (≈ 6,000 real + 3,600 practice, 12,000 applications / month)

| Component | USD/mo | INR/mo |
|---|---|---|
| Speech (STT + TTS) | $1,500 | ₹1.26 L |
| LLM | $400 | ₹33,600 |
| Cloud Run (2–4 instances at peak) | $150 | ₹12,600 |
| MongoDB Atlas (M30) | $390 | ₹32,800 |
| GCS (~1.1 TB steady) | $40 | ₹3,400 |
| ZeptoMail (~18k emails/mo ≈ 2 credits) | $4 | ₹300 |
| Vercel Pro | $20 | ₹1,680 |
| **Total** | **≈ $2,600 / mo** | **≈ ₹2.2 L / mo** |

### 10,000 DAU  (≈ 60,000 real + 36,000 practice, 120,000 applications / month)

| Component | USD/mo | INR/mo |
|---|---|---|
| Speech (STT + TTS) | $15,000 | ₹12.6 L |
| LLM | $4,000 | ₹3.4 L |
| Cloud Run (10–20 instances; needs the multi-worker fix, §6) | $1,200 | ₹1.0 L |
| MongoDB Atlas (M50 + backups) | $1,800 | ₹1.5 L |
| GCS (~11 TB steady) | $400 | ₹33,600 |
| ZeptoMail (~180k emails/mo ≈ 18 credits) | $32 | ₹2,700 |
| Vercel Pro (team) | $60 | ₹5,000 |
| **Total** | **≈ $23,000 / mo** | **≈ ₹19.3 L / mo** |

> Per-real-interview all-in cost stays roughly **$0.30–0.40** across scales;
> the fixed floor (DB, email, hosting) dominates only at the 100-DAU tier.

---

## 5. What today's env defaults mean for cost

- `LLM_PROVIDER_PRIORITY=groq,gemini,openai` — Groq answers everything while
  its quota lasts. **Groq's free tier is rate-limited, not metered**: at 100
  DAU you may pay ~$0 for LLM; at 1,000+ DAU move to Groq's paid tier (priced
  above) or the chain will fall over to Gemini/OpenAI.
- The Gemini key is **free-tier with zero quota on 2.x-flash models** — as a
  fallback leg it only works on `gemini-flash-lite-latest` until billing is
  enabled on that Google project.
- The OpenAI key is currently **invalid** — the tertiary leg is dead until
  replaced (the chain's cooldown makes this cost latency only when both
  Groq and Gemini fail).
- Practice interviews are credit-gated (`CANDIDATE_PRACTICE_CREDITS=30` per
  session, signup bonus 100) — the credit economy already throttles abuse.

---

## 6. Cost levers, biggest first

1. **Move STT to Groq Whisper** (`whisper-large-v3`, ~$0.111/audio-hour ≈
   $0.00185/min vs Google's $0.016/min): real-interview cost drops from
   ~$0.23 to **~$0.09**; at 10k DAU that is ~**$13k/mo saved**. Requires
   switching the streaming recognizer to chunked transcription (the kiosk
   already records in chunks).
2. **GCS lifecycle rules** — auto-delete recordings after the retention window
   (90 days assumed above) and move >30-day objects to Nearline (½ price).
   Without lifecycle rules storage grows unbounded.
3. **TTS caching** — interview questions repeat across candidates for the same
   JD; caching synthesized audio by text-hash cuts TTS spend materially.
4. **Keep Groq primary** (already the default) — 10–20× cheaper than GPT-4-class
   for these tasks; the env chain makes experimentation free.
5. **Cloud Run min-instances=1** instead of the keep-warm cron once revenue
   supports it (~$15/mo) — removes cold starts without the 5-minute ping.
6. **Atlas right-sizing** — M10 is enough until ~1,000 DAU if GridFS recordings
   move fully to GCS (GridFS files count against the Atlas disk).

---

## 7. Revenue-side reference (not a cost)

Recharge packs (env-configurable, current defaults): Candidate ₹499/500cr and
₹999/1,000cr; Recruiter ₹4,999/5,000cr and ₹9,999/10,000cr. A real proctored
interview debits 50 recruiter credits (`RECRUITER_REAL_INTERVIEW_PROCTORED_CREDITS`),
i.e. recruiters pay ≈ ₹50/interview against a marginal cost of ≈ ₹19–34
(§4) — gross margin per interview stays positive at every tier priced above.
Razorpay keeps ~2% of each recharge.
