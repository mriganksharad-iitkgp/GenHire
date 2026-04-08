# Actual Cost Calculation Guide

This document describes the implemented actual-cost calculation approach for Admin Cost Statistics, including how each required parameter is fetched or derived for candidate and recruiter usage.

## 1. Objective

Compute AI usage cost from real usage data whenever available, and use deterministic fallback only when real usage metadata is missing.

## 2. Core Principles

1. Provider usage first.

- If prompt_tokens and completion_tokens exist in stored usage metadata, those values are used directly.

2. Deterministic fallback when metadata is missing.

- tokens_by_words = words / 0.75
- tokens_by_chars = characters / 4
- estimated_tokens = round(max(tokens_by_words, tokens_by_chars))

3. Category-specific accounting rules.

- Interview and practice interview use interview-specific token/media logic.
- Evaluation categories use evaluation-specific token logic.

4. Timeline-aware query-time aggregation.

- All summaries and lines are recomputed for selected date range.

## 3. Timeline and Scope

Selected range is applied via start_date and end_date across relevant timestamp fields per collection.

Main analytics scopes:

- Candidate usage:
  - practice_interview
  - practice_interview_evaluation
- Recruiter usage:
  - ai_interview
  - ai_interview_evaluation
  - cv_scoring
  - ai_jd_generation

## 4. Data Sources by Category

### 4.1 Practice Interview (Candidate)

Source collections and fields:

- practice_sessions
- transcript, qa_pairs or qa_history/interview_data fallback
- evaluation
- created_at, completed_at, updated_at
- optional stored usage fields: prompt_tokens, completion_tokens, stt_seconds, tts_characters, usage/token_usage/cost_usage blocks

### 4.2 Real Interview (Recruiter)

Source collections and fields:

- applications for ownership and status
- interviews report merged into application context when available
- transcript, qa_pairs
- evaluation
- created_at, completed_at, updated_at
- optional stored usage fields and usage metadata

### 4.3 Interview Evaluation (Practice + Real)

Source:

- interview report/session evaluation payload
- transcript or qa_pairs for Q+A prompt context

### 4.4 CV Scoring

Source:

- application.cv_snapshot.text
- application.jd_snapshot.text
- application.cv_score_breakdown
- optional stored provider usage metadata

### 4.5 AI JD Generation

Source priority:

1. usage events metadata.prompt_text and metadata.generated_jd_text
2. provider token metadata if available
3. fallback from job fields (title, department, location, type, experience, salary, description, skills, responsibilities, requirements, benefits)

## 5. Token Estimation Rule (Fallback)

When provider prompt/completion usage is not available:

1. Count words from non-whitespace chunks.
2. Count characters from full text.
3. Compute:

- tokens_by_words = words / 0.75
- tokens_by_chars = chars / 4

4. Use:

- estimated_tokens = round(max(tokens_by_words, tokens_by_chars))

This rule is applied to all text-derived token paths.

## 6. Interview-Specific Accounting Logic

Applies to:

- ai_interview
- practice_interview

### 6.1 Message Stream Construction

Message stream priority:

1. transcript list
2. fallback from qa_pairs, qa_history, or interview_data by mapping:

- question -> assistant message
- answer -> user message

### 6.2 Per-Interview Token Breakdown

From ordered message stream:

- question_tokens: sum of question message tokens
- answer_tokens: sum of answer message tokens
- qa_total_tokens: question_tokens + answer_tokens

### 6.3 Prompt Tokens for Interview Cost

Prompt tokens are cumulative context tokens across turns.

For turn n, prompt includes all prior Q+A plus current pair context.
Total prompt_tokens is the sum of that cumulative prompt across all turns.

### 6.4 Completion Tokens for Interview Cost

Completion tokens are sum of generated question tokens only.

### 6.5 STT for Interview Cost

STT seconds are derived from answer tokens:

- stt_seconds = answer_tokens \* 0.4

Fallback order if answer token path is unavailable:

1. created_at to completed_at
2. created_at to updated_at
3. first to last qa_pairs timestamp

### 6.6 TTS Proxy for Interview Cost

TTS proxy value uses question token total.

## 7. Evaluation-Specific Accounting Logic

Applies to:

- ai_interview_evaluation
- practice_interview_evaluation

1. Prompt tokens:

- total Q+A tokens from interview report/session context

2. Completion tokens:

- tokens from evaluation payload text only
- no question-generation tokens added here

3. STT and TTS are not used for evaluation categories.

## 8. Provider Usage First Behavior

For each row, if stored usage metadata has prompt_tokens/completion_tokens:

- use those values directly
- mark usage source as actual

If usage_source indicates assumed, placeholder values are ignored so report/text derivation can run.

If values are zero or default placeholders and derived values are available, derived values are preferred.

## 9. Cost Formula Application

### 9.1 Token-only categories

Categories:

- cv_scoring
- ai_jd_generation
- ai_interview_evaluation
- practice_interview_evaluation

Formula:

- ((prompt_tokens / 1,000,000 _ input_rate) + (completion_tokens / 1,000,000 _ output_rate)) \* INR_conversion

### 9.2 Interview categories with media

Categories:

- ai_interview
- practice_interview

Formula:

- [LLM_token_cost + STT_cost + TTS_cost] \* INR_conversion

Where:

- LLM_token_cost = prompt/completion formula above
- STT_cost = (stt_seconds / 60) \* stt_rate
- TTS_cost = (tts_proxy_value / 1,000,000) \* tts_rate

## 10. Pricing and Conversion

Pricing source:

- interview/core/cost_tracker.py

Conversion:

- INR conversion fixed at 83

Rates used by category model:

- input rate
- output rate
- stt_rate
- tts_rate

## 11. Ownership Mapping

Candidate rows:

- practice sessions are mapped by candidate user_id

Recruiter rows:

- interviews and CV scoring mapped via recruiter_id or job ownership mapping
- JD generation mapped via recruiter usage events or recruiter-owned jobs fallback

## 12. Aggregation Outputs

1. Line-level endpoints return detailed rows with:

- timestamp, model, prompt_tokens, completion_tokens, optional stt_seconds/tts proxy, formula, cost

2. Summary endpoints return:

- count, total_cost_inr, avg_cost_inr per category and per actor

3. Aggregate cost endpoint composes AI totals from line-level computed rows, not simple static multipliers.

## 13. UI Formatting Notes

Current UI behavior:

- STT is shown with truncation to 2 decimals.
- STT/TTS columns are shown only for interview/practice-interview categories in drilldown tables.

## 14. Known Practical Notes

1. Provider usage remains the highest-trust source when present.
2. Fallback token estimation is deterministic and reproducible, but still an approximation.
3. Historical rows with missing transcripts or missing usage metadata may still require fallback assumptions.
4. Newer rows are more accurate where telemetry/report fields are persisted.

## 15. Verification Checklist

1. Pick one interview report row and manually verify:

- question_tokens
- answer_tokens
- cumulative prompt tokens
- evaluation tokens

2. Compare line-level computed cost with formula output.

3. Confirm summary totals equal sum of row costs for selected timeline.

4. Confirm provider-usage rows do not use fallback estimators when metadata exists.
