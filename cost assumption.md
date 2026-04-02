# Admin Cost Statistics - Assumptions

This document lists all assumptions used by the Admin Cost Statistics page and its backend API.

## Scope and Access Assumptions

- Endpoint is admin-only and requires a valid bearer token plus admin authorization.
- Source endpoint used by the page: `GET /api/admin/cost-statistics`.
- Currency displayed and computed is INR.

## Timeline Assumptions

- UI always sends a custom date range (`start_date`, `end_date`) instead of using preset period filters.
- UI end date is fixed to today (present date) and cannot be changed manually.
- Backend accepts date in `YYYY-MM-DD` or ISO datetime format.
- If only date (no time) is provided, backend assumes:
- Start date at `00:00:00.000000`.
- End date at `23:59:59.999999`.
- If dates are invalid, API returns 400.
- If start date is after end date, API returns 400.
- If no custom start date is passed, fallback period windows are assumed as:
- `week` = last 7 days.
- `month` = last 30 days.
- `quarter` = last 90 days.
- `year` = last 365 days.
- Date filtering across collections is based on OR over configured date fields per entity.

## Exchange Rate and Pricing Source Assumptions

- INR conversion is fixed at `1 USD = 83 INR`.
- LLM/STT/TTS pricing is taken from `interview/core/cost_tracker.py` (`CostTracker.PRICING`).
- Pricing values are treated as assumed/approximate.
- STT default assumed rate is `0.024 USD/min` if missing.
- TTS default assumed rate is `4.00 USD per 1M chars` if missing.

## Activity Counting Assumptions

- Completed interview count is applications with:
- `is_visible = true`.
- `status` in `interviewed, selected, rejected`.
- CV scoring count is applications where `cv_score` exists and is not null.
- JD generation count uses number of jobs in timeline.
- Practice interview count uses number of practice sessions in timeline.
- Interview evaluation count is completed interview applications with `interview_score` present.
- Practice evaluation count is practice sessions where `evaluation` exists and is not null.

## Per-Action AI Usage Assumptions

- CV scoring uses model `gemini-1.5-flash-latest` with:
- Prompt tokens/action = `1800`.
- Completion tokens/action = `600`.
- AI JD generation uses model `llama-3.3-70b-versatile` with:
- Prompt tokens/action = `1500`.
- Completion tokens/action = `1200`.
- AI interview uses model `gpt-4o` with:
- Prompt tokens/action = `4200`.
- Completion tokens/action = `2100`.
- STT seconds/action = `900`.
- TTS characters/action = `22000`.
- Interview evaluation uses model `gpt-5-mini` with:
- Prompt tokens/action = `1500`.
- Completion tokens/action = `1000`.
- Practice interview evaluation uses same assumptions as interview evaluation.

## AI Cost Formula Assumptions

- Token-based line items use:
- `count × ((prompt_tokens/1M × input_rate) + (completion_tokens/1M × output_rate)) × INR conversion`.
- Interview and practice interview use combined media + LLM formula:
- `count × [LLM token cost + STT(sec/60 × stt_rate) + TTS(chars/1M × tts_rate)] × INR conversion`.
- Average line-item cost is `total_cost / count`, with safe 0 when count is 0.

## Infrastructure Cost Assumptions

- Monthly Cloudflare assumption = `INR 5000`.
- Monthly MongoDB assumption = `INR 3000`.
- Pro-rating is linear by days in selected window using:
- `(monthly_cost / 30) × days`.
- Cloudflare GPU share is a derived split ratio:
- `245 / (245 + 100)`.
- Cloudflare GPU component is informational and not added separately again.
- Total infrastructure cost = prorated Cloudflare + prorated MongoDB.

## Incoming Money Assumptions

- Incoming money includes only payments with `status = succeeded` in the selected timeline.
- Timeline match for succeeded payments uses OR on `completed_at` or `created_at`.
- Payment amount source is `amount_paise / 100`.
- Plan identity grouping key is effectively `plan_slug + plan_price`.
- Audience defaults to recruiter if ambiguous or invalid.
- Plan metadata can be resolved from:
- plan document.
- payment `metadata`.
- payment `plan_snapshot` fallback.

## Refund Assumptions

- Refund adjustment includes payment statuses:
- `refunded`.
- `partially_refunded`.
- Refund timeline match uses OR on `updated_at` or `created_at`.
- Refund total uses `refund_amount_paise / 100`.
- Net incoming after refunds = `total incoming - total refunded`.

## Profitability Assumptions

- Gross profit = `total incoming - total cost`.
- Net profit = `net incoming after refunds - total cost`.
- Gross margin percent = `(gross profit / total incoming) × 100`, else 0 when denominator is 0.
- Net margin percent = `(net profit / net incoming after refunds) × 100`, else 0 when denominator is 0.

## UI Presentation Assumptions

- Admin page defaults to last 30 days (start date = today - 30).
- Date picker allows changing only start date; end date remains today.
- Missing values are treated/displayed as zero in charts and tables.
- Plan-wise incoming chart expects recognizable slugs/names for labels:
- Candidate Pro.
- Candidate Max.
- Recruiter Pro/Professional.
- Recruiter Max.
- CSV export filename assumes `admin-cost-statistics-<start>-to-<end>.csv`.
- CSV includes timeline, AI costs, infrastructure costs, incoming, refunds, and profitability rows.

## Data Availability and Reliability Assumptions

- DB connection and required collections are available.
- Missing model pricing falls back to zero rates at line-item level in admin API calculations.
- Rounding is done to 2 decimals for INR totals presented by this endpoint.
- Timeline day count for prorating uses integer day difference with minimum 1 day.
