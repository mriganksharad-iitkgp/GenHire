# Credit Deduction Specification

## 1) Purpose

This document defines how interview usage cost is calculated, converted into credits, and deducted.

It is written so another coding agent can implement or refine the feature end-to-end in both backend and frontend.

Scope:

- Practice interview session: credits are deducted from the candidate plan.
- Non-practice interview session: credits are deducted from the recruiter plan.

## 2) Current Architecture References

Backend files already involved:

- python-backend/interview/core/cost_tracker.py
- python-backend/payment_module/services/subscription_service.py
- python-backend/controllers/practice_controller.py
- python-backend/app.py
- python-backend/services/candidate_practice_quota_service.py
- python-backend/services/interview_quota_service.py (legacy/monthly quota style for recruiter stats)
- python-backend/payment_module/config/settings.py

Frontend files already involved:

- react-frontend/src/pages/Practice.jsx
- react-frontend/src/pages/Chat.jsx
- react-frontend/src/pages/candidate/CandidateCostStatistics.jsx
- react-frontend/src/pages/candidate/CandidateSubscriptionPlans.jsx
- react-frontend/src/pages/SubscriptionPlans.jsx

## 3) Single Interview Cost Model

Interview cost must be tracked from 3 sources:

- LLM token usage
- STT audio usage
- TTS character usage

### 3.1 LLM cost formula

For one model call:

LLM_cost_usd = (prompt_tokens / 1,000,000) _ input_rate_usd_per_1m + (completion_tokens / 1,000,000) _ output_rate_usd_per_1m

Session-level LLM cost is the sum across all LLM events in that session.

Rates are read from CostTracker.PRICING in python-backend/interview/core/cost_tracker.py.

### 3.2 STT cost formula

STT_cost_usd = (stt_seconds / 60) \* stt_rate_usd_per_min

Default rate currently in CostTracker:

- google-stt price_per_minute = 0.024

### 3.3 TTS cost formula

TTS_cost_usd = (tts_characters / 1,000,000) \* tts_rate_usd_per_1m_chars

Default rate currently in CostTracker:

- google-tts price_per_1m_chars = 4.00

### 3.4 Session total cost

Total_session_cost_usd = LLM_cost_usd + STT_cost_usd + TTS_cost_usd

This value is emitted as usage_summary.total_cost by:

- CostTracker().end_session(session_id, clear_events=True)

## 4) Convert Cost to Credits

Credits are integer billing units.

Config source:

- python-backend/payment_module/config/settings.py
  - CREDIT_PER_USD (default: 1000)
  - MIN_USAGE_CREDITS (default: 1)
  - START_INTERVIEW_MIN_CREDITS (default: 1)

### 4.1 Conversion formula

If total_session_cost_usd > 0:

credits_to_deduct = max(MIN_USAGE_CREDITS, ceil(total_session_cost_usd \* CREDIT_PER_USD))

If total_session_cost_usd <= 0:

credits_to_deduct = MIN_USAGE_CREDITS

This matches \_credits_from_usage_cost in SubscriptionService.

### 4.2 Worked example (single interview)

Assume session usage:

- prompt tokens: 14,000
- completion tokens: 7,000
- model: llama-3.3-70b-versatile (input 0.59, output 0.79 USD per 1M)
- STT: 720 sec
- TTS: 12,000 chars

Compute:

- LLM = (14000/1e6)*0.59 + (7000/1e6)*0.79
- LLM = 0.00826 + 0.00553 = 0.01379 USD
- STT = (720/60)\*0.024 = 0.288 USD
- TTS = (12000/1e6)\*4.00 = 0.048 USD
- Total = 0.01379 + 0.288 + 0.048 = 0.34979 USD

Credit conversion (CREDIT_PER_USD = 1000):

- ceil(0.34979\*1000) = ceil(349.79) = 350
- credits_to_deduct = max(1, 350) = 350 credits

## 5) Deduction Ownership Rules

## 5.1 Ownership matrix

1. Practice session (candidate path)

- Payer: candidate
- Deduct from: active candidate subscription credits
- Endpoint flow: /api/practice/start and /api/practice/{session_id}/end

2. Non-practice interview (application/job path)

- Payer: recruiter
- Deduct from: active recruiter subscription credits
- Endpoint flow: /api/interviews/start and /api/interviews/{session_id}/end

### 5.2 Important policy

Credit pre-check happens at start.

Credit deduction happens at end (when actual usage cost is known).

## 6) Backend Implementation Blueprint

## 6.1 Start interview checks

Before starting session:

- Call SubscriptionService.check_credit_availability(employer_id, audience)
- audience = candidate for practice
- audience = recruiter for non-practice
- Fail fast if can_start_interview is false

Current behavior:

- Practice start already checks candidate availability in PracticeController.start_practice.
- Non-practice start already checks recruiter availability in app.py start_interview.

### 6.2 End interview deduction

At session end:

1. usage_summary = CostTracker().end_session(session_id, clear_events=True)
2. Call consume_usage_credits with idempotency_key
3. Persist both usage_summary and usage_deduction in interview/practice session document

Idempotency keys in current code:

- Non-practice: interview-session:{session_id}
- Practice: practice-session:{session_id}

### 6.3 Candidate free fallback rule

Current code path in PracticeController.end_practice:

- If consume_usage_credits returns error_code=no_subscription
- Fallback to consume_candidate_practice_credit in candidate_practice_quota_service
- Deduct 1 session unit from candidate monthly free quota ledger

This keeps free candidate users supported even without a paid subscription doc.

### 6.4 Data persisted after deduction

On interview/practice documents:

- usage_summary
  - total_prompt_tokens
  - total_completion_tokens
  - total_stt_seconds
  - total_tts_characters
  - total_cost
- usage_deduction
  - success
  - credits_deducted
  - usage_cost_usd
  - credits_remaining
  - credits_used
  - credits_allocated
  - is_unlimited
  - interviews_used
  - source (for free candidate fallback)

On subscription documents:

- credits_remaining decremented
- credits_used incremented
- usage_cost_total_usd incremented
- interviews_used incremented

On usage events collection:

- subscription_usage_events
  - subscription_id
  - idempotency_key
  - usage payload
  - usage_cost_usd
  - credits_deducted
  - metadata

## 7) Frontend Implementation Blueprint

## 7.1 Practice flow (candidate)

In Practice page:

- POST /api/practice/start
- If backend returns payment/credit error (402 or insufficient credits), show clear message and route to candidate subscription page.

In Chat page (practice mode):

- On end, call /api/practice/{session_id}/end
- Read usage_deduction from response
- Show deducted credits and remaining credits in a completion summary or toast
- Trigger refresh of candidate subscription and cost-statistics UI after completion

## 7.2 Non-practice flow (candidate doing recruiter job interview)

In Chat page (non-practice mode):

- On end, call /api/interviews/{session_id}/end
- Backend deducts from recruiter plan
- Candidate should not see recruiter internal billing numbers unless product wants exposure

Recruiter-side dashboards/pages:

- Refresh recruiter credits/usage after interview completion
- Show updated credits_remaining and usage_cost_total_usd

## 7.3 UI messaging requirements

Error copy should distinguish:

- Candidate practice credits exhausted
- Recruiter credits exhausted for this job interview

Success summary should include:

- session cost in USD (usage_cost_usd)
- credits deducted
- remaining credits

## 8) API Contract Requirements

Any response that finalizes session should include these fields:

- usage_summary
- usage_deduction

Minimum usage_deduction fields required by frontend:

- success
- credits_deducted
- usage_cost_usd
- credits_remaining
- error_code (when success=false)

Start endpoints should return enough information for graceful gating:

- can_start_interview (or mapped error)
- error_code
- credits_remaining (if available)

## 9) Edge Cases and Rules

1. Idempotent end request

- Repeated end calls must not double-charge.
- Keep idempotency key unique per session.

2. Zero usage session

- Deduct MIN_USAGE_CREDITS (default 1) when session has zero measured cost.

3. Unlimited plans

- Do not decrement credits_remaining.
- Still record usage_cost_usd and interviews_used.

4. No active subscription

- Practice candidate: use free monthly fallback quota service.
- Non-practice recruiter: block start with clear error.

5. Partial failures

- If interview completion succeeds but deduction fails, persist failure in usage_deduction and surface retriable status.

## 10) Testing Checklist

## 10.1 Backend tests

1. Cost formula tests

- LLM-only, STT-only, TTS-only, mixed usage.

2. Conversion tests

- ceil behavior, min credit behavior, zero-cost behavior.

3. Deduction tests

- Candidate practice paid subscription.
- Candidate practice no subscription fallback.
- Recruiter non-practice paid subscription.
- Insufficient credits blocking.
- Idempotent replay on duplicate end call.

4. Persistence tests

- usage_summary and usage_deduction stored on session docs.
- subscription_usage_events unique idempotency index behavior.

## 10.2 Frontend tests

1. Practice start insufficient credits shows upgrade prompt.
2. Practice end shows credits deducted and remaining.
3. Non-practice start shows recruiter-credit-exhausted message.
4. Dashboards refresh after deduction.

## 11) Recommended Implementation Sequence

1. Confirm and lock pricing constants in CostTracker and PaymentConfig.
2. Standardize response schema for usage_deduction across both end endpoints.
3. Add/complete frontend summary UI for deduction results.
4. Add automated tests for idempotency and fallback behavior.
5. Add monitoring metrics for:

- total usage_cost_usd by audience
- total credits_deducted by audience
- deduction failures

## 12) Final Acceptance Criteria

Feature is complete when all are true:

1. Every ended interview (practice/non-practice) has usage_summary persisted.
2. Every ended interview has usage_deduction persisted (success or failure payload).
3. Practice charges candidate credits (or candidate free monthly fallback if no paid subscription).
4. Non-practice charges recruiter credits.
5. Frontend clearly communicates credit failures at start and credit deduction outcomes at end.
6. Duplicate end calls do not cause double deduction.
