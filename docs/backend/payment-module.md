# Payment Module — Razorpay, Wallets & Credits

Folder: `python-backend/payment_module/`. A self-contained package registered
at `/api/payment`. If it fails to import, the rest of the app still boots
(`PAYMENT_MODULE_AVAILABLE = False`).

```
payment_module/
├── config/settings.py      # PaymentConfig — env vars, credit prices, default packs
├── routes/payment_routes.py# payment_bp (url_prefix="/api/payment")
├── controllers/            # payment, plan, subscription, webhook controllers
├── services/
│   ├── razorpay_service.py # Razorpay SDK wrapper (orders, signature verify, refunds)
│   ├── payment_service.py  # payment records + verification flow
│   ├── plan_service.py     # plan catalog (seeds DEFAULT_PLANS)
│   ├── subscription_service.py # purchased packs per user
│   └── wallet_service.py   # THE credit ledger — every balance change goes here
├── models/                 # plan, payment, subscription, credit_wallet, credit_transaction
└── utils.py
```

## The credit model (how money works in GenHire)

Users don't pay per action — they hold **credits** in a wallet and actions
debit it. Two wallet audiences exist: `candidate` and `recruiter`.

| Action | Credits | Paid by | Config (env var, default) |
|---|---|---|---|
| Signing up | +100 (bonus) | — | `SIGNUP_BONUS_CREDITS=100` |
| Practice interview | −30 | Candidate | `CANDIDATE_PRACTICE_CREDITS=30` |
| Practice interview, proctored | −50 | Candidate | `CANDIDATE_PRACTICE_PROCTORED_CREDITS=50` |
| AI job-description generation | −10 | Recruiter | `RECRUITER_AI_JD_CREDITS=10` |
| Real interview | −30 | **Recruiter** (job owner) | `RECRUITER_REAL_INTERVIEW_CREDITS=30` |
| Real interview, proctored | −50 | **Recruiter** | `RECRUITER_REAL_INTERVIEW_PROCTORED_CREDITS=50` |

Note the key design decision: **candidates never pay for real interviews** —
the recruiter who posted the job does. When a candidate starts an interview,
the backend checks and debits the *recruiter's* wallet, and writes a
zero-credit audit transaction on the candidate side for traceability.

## Interview refunds (charge at start, refund if nothing happened)

Interview credits are debited at `/start` and **reversed automatically**
when the session ends with zero substantive answers — start failure after
the debit, identity-verification block, abandonment, or an `/end` with
nothing answered (`services/interview_credit_service.py`; a background
sweeper handles abandoned sessions). Mechanics that matter for the ledger:

- Refunds are `credit_wallet` calls with idempotency key
  `refund:<original-debit-key>` and transaction types
  `real_interview_refund` / `practice_interview_refund` — a refund can only
  ever apply once no matter how often it's retried.
- Real-interview debit keys are refund-count-aware:
  `real-interview:<application_id>` initially, then `:r1`, `:r2`… after each
  refund (tracked by `interview_refund_count` on the application). Without
  this, retrying `/start` after a refund would idempotently replay the old
  debit and the recruiter would never actually be re-charged.
- Once the candidate gives **one** real answer, the charge stands; stale
  answered sessions are auto-finalized into scored reports instead of
  refunded. See
  [interview-engine.md](interview-engine.md#credit-lifecycle--refunds-servicesinterview_credit_servicepy).

## Recharge packs (`PaymentConfig.DEFAULT_PLANS`, seeded on first run)

| Pack | Price | Credits | Audience |
|---|---|---|---|
| Candidate Pro | ₹499 | 500 | candidate |
| Candidate Max | ₹999 | 1,000 | candidate |
| Recruiter Pro | ₹4,999 | 5,000 | recruiter |
| Recruiter Max | ₹9,999 | 10,000 | recruiter |

Prices are stored in **paise**; credits are non-expiring
(`validity_days: 36500`). Currency: `PAYMENT_CURRENCY` (default `INR`).

## Purchase flow (Razorpay)

```
Frontend                        Backend                         Razorpay
   │  POST /api/payment/recharge/initiate {plan_id}
   ├──────────────────────────────►│  create order ──────────────────►│
   │   ◄── order_id, key_id ───────┤◄──────────────────────────────── │
   │  open Razorpay Checkout (useRazorpay hook loads checkout.js)     │
   │◄═════════ user pays in the Razorpay modal ══════════════════════►│
   │  POST /api/payment/recharge/verify {order_id, payment_id, signature}
   ├──────────────────────────────►│  verify HMAC signature
   │                               │  mark payment success
   │                               │  credit wallet (+pack credits)
   │   ◄── success ────────────────┤
   │  navigate to /payment/success
```

Independently, Razorpay calls `POST /api/payment/webhooks/razorpay`
(verified with `RAZORPAY_WEBHOOK_SECRET`) so payments are also confirmed
server-to-server even if the browser never completes the verify call.
Test mode is auto-detected from a `rzp_test_` key prefix.

## WalletService — the single source of truth for balances

All balance changes go through `wallet_service.py`:

- `check_credit_availability(owner_id, audience, min_required_credits)` —
  pre-flight check before starting anything billable; returns
  `can_start_interview`, `credits_remaining`, and a friendly `error_code`
  (e.g. `RECRUITER_INTERVIEW_CREDITS_EXHAUSTED`).
- `debit_wallet(...)` — atomic debit that writes a ledger row
  (`credit_transactions`) with `transaction_type`
  (e.g. `real_interview_recruiter`), `reference_type`/`reference_id`
  (e.g. the application id), free-form `metadata`, and — critically — an
  **`idempotency_key`** such as `real-interview:<application_id>` so retrying
  a request can never double-charge. The returned transaction includes
  `balance_after`.
- `add_audit_transaction(...)` — zero-credit ledger entries (candidate-side
  record of a recruiter-paid interview).
- `bootstrap_signup_bonus_for_all_users(users_collection)` — run at every app
  boot; grants the signup bonus to any user without a wallet (idempotent).

## Frontend integration

- `react-frontend/src/features/payment/api/paymentApi.js` — all `/api/payment/*` calls
  (`getPlans`, `initiatePayment`, `verifyPayment`, `getCurrentSubscription`,
  `getCreditTransactions`, …).
- `features/payment/hooks/useRazorpay.js` — loads the Razorpay checkout script and opens the modal.

Plan prices and credit amounts are env-editable
(`PLAN_<NAME>_PRICE_PAISE` / `PLAN_<NAME>_CREDITS`) and sync into MongoDB on
every boot.
- Pages: `/subscription` (recruiter packs), `/candidate/subscription`
  (candidate packs), `/payment/success`, `/payment/cancel`.
- Credit balances/transactions also surface in the recruiter/candidate
  cost-statistics pages and the admin cost dashboards.

## Environment variables

```
RAZORPAY_KEY_ID=rzp_test_xxx        # rzp_test_ prefix ⇒ test mode
RAZORPAY_KEY_SECRET=xxx
RAZORPAY_WEBHOOK_SECRET=xxx
PAYMENT_CURRENCY=INR
FRONTEND_URL=...                    # payment success/cancel redirect base
PAYMENT_SUCCESS_URL / PAYMENT_CANCEL_URL   # optional explicit overrides
SIGNUP_BONUS_CREDITS / CANDIDATE_PRACTICE_CREDITS / ... (see table above)
```
