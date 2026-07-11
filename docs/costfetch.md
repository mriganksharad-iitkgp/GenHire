# Fetching exact infrastructure/provider costs (vs. today's manual placeholders)

## Current state

The admin Cost Statistics page (`/admin/cost-statistics`) shows two kinds of numbers:

1. **AI usage cost lines** (CV scoring, JD generation, interviews, evaluations) — these
   are already computed from real, per-call data: logged token counts when available,
   or transcript-derived estimates otherwise (see `_action_assumptions` and
   `_build_token_cost_line` / `_build_interview_cost_line` in
   `python-backend/controllers/admin/cost_helpers.py`). **Nothing in this document
   changes that half** — it's already as exact as it can be without each provider
   exposing a per-request cost API.

2. **Infrastructure & provider cost** (GCP, Vercel, MongoDB Atlas, ZeptoMail,
   OpenAI, Gemini, Groq) — **GCP and OpenAI now fetch REAL date-ranged spend**
   when configured (Sections 1–2 below; each card shows a `usage_source` badge).
   The remaining providers — and the fallback for those two — are hand-entered
   monthly figures read from env vars (`INFRA_MONTHLY_*_INR` in `.env` /
   `.env.production`) via `_env_monthly_inr()` in `cost_stats_admin.py`, then
   pro-rated over the admin's selected date range:

   ```python
   prorated = (monthly_figure / 30) * days_in_selected_range
   ```

   A hand-entered figure needs a human to open each billing console, read the
   current-month total, and paste it into the env file — it drifts stale as the
   month progresses, and pro-rating a whole month over a partial range is an
   approximation.

This document covers the real-fetch integrations that exist (GCP, OpenAI — with
their one-time owner setup steps) and how to fetch the rest when their APIs make
it possible.

---

## 1. GCP — Billing Export to BigQuery (recommended path) — ✅ IMPLEMENTED

**Status: the backend integration is live** in
`python-backend/services/gcp_billing_service.py`. Once the console-side setup
below is done and `GCP_BILLING_EXPORT_BQ_TABLE` is set in the env, the admin
cost page automatically switches the GCP card from env placeholders to real
per-service spend for the selected timeline (source badge: "GCP Billing export
(actual)"), plus the current invoice month's accrued total shown as
"Outstanding". Until then it falls back to the `INFRA_MONTHLY_GCP_*` env
figures.

GCP does **not** have a simple "give me cost for date range X–Y" REST endpoint for
ad-hoc queries. The supported mechanism is **Cloud Billing Export**: GCP writes a row
per SKU per day into a BigQuery table, and you query that table like any other data.

### Setup (one-time, console work — do this yourself, not via code)

1. GCP Console → Billing → **Billing export** → **BigQuery export** → enable
   "Standard usage cost" export for the `hr-tech-2026` project's billing account.
   Pick/create a dataset, e.g. `billing_export`. GCP starts writing new rows going
   forward (it does not backfill history from before export was enabled).
2. Grant the existing `genhire-backend@hr-tech-2026.iam.gserviceaccount.com` service
   account (already used for GCS + credentials in `.env.production`) the
   **BigQuery Data Viewer** + **BigQuery Job User** IAM roles on that dataset, so the
   backend can query it with the credentials it already has.

### Query (exact cost for an arbitrary date range, itemized by service)

```sql
SELECT
  service.description AS service,
  SUM(cost) AS cost_usd,
  SUM((SELECT SUM(c.amount) FROM UNNEST(credits) c)) AS credits_usd
FROM `hr-tech-2026.billing_export.gcp_billing_export_v1_<BILLING_ACCOUNT_ID>`
WHERE usage_start_time >= @start_date
  AND usage_start_time <  @end_date
GROUP BY service
ORDER BY cost_usd DESC
```

`cost_usd + credits_usd` (credits are negative) gives the *net* figure — this is what
the current `Cloud Run ₹54.01 − ₹53.40 savings = ₹0.62 net` line on the console
represents; the export table has both components separately.

### Backend integration sketch

Add a `python-backend/services/gcp_billing_service.py`:

```python
from google.cloud import bigquery

def fetch_gcp_costs_for_range(start_date, end_date):
    client = bigquery.Client()  # reuses GOOGLE_APPLICATION_CREDENTIALS already set
    query = """
        SELECT service.description AS service, SUM(cost) AS cost_usd,
               SUM((SELECT SUM(c.amount) FROM UNNEST(credits) c)) AS credit_usd
        FROM `hr-tech-2026.billing_export.gcp_billing_export_v1_XXXXXX`
        WHERE usage_start_time >= @start AND usage_start_time < @end
        GROUP BY service
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("start", "TIMESTAMP", start_date),
        bigquery.ScalarQueryParameter("end", "TIMESTAMP", end_date),
    ])
    rows = client.query(query, job_config=job_config).result()
    return {r.service: (r.cost_usd or 0) + (r.credit_usd or 0) for r in rows}
```

Call this from `cost_stats_admin.py` in place of the itemized `_env_monthly_inr()`
GCP block (lines ~160–164), converting USD→INR with a live or configured FX rate,
and map service names (`"Cloud Run"`, `"Artifact Registry"`, `"Cloud Build"`,
`"Cloud Storage"`) onto the existing `gcp_breakdown` keys.

**New dependency**: `google-cloud-bigquery` (not currently in
`python-backend/requirements.txt`).

**Cost of querying**: BigQuery's own free tier is 1 TB scanned/month — a table this
small (a few thousand rows/month) costs nothing to query.

---

## 2. OpenAI — Usage API — ✅ IMPLEMENTED

**Status: the backend integration is live** in
`python-backend/services/openai_billing_service.py`. Create an **Admin API
key** (platform.openai.com → Settings → Organization → Admin keys, scope
`api.usage.read`) and set it as `OPENAI_ADMIN_API_KEY` — the admin cost page
then shows real OpenAI spend for the selected timeline (source badge: "OpenAI
Costs API (actual)"). **Balance remaining**: OpenAI has NO official balance
endpoint (the old `dashboard/billing/credit_grants` needs browser session
cookies, not API keys) — mirror the dashboard figure manually into
`OPENAI_CREDIT_BALANCE_USD` and it is displayed with a "manually mirrored"
note.

OpenAI exposes a real, date-ranged usage/cost API (Admin API, org-level key required
— not the same key as `OPENAI_API_KEY` used for inference calls).

- `GET https://api.openai.com/v1/organization/costs?start_time=<unix>&end_time=<unix>&bucket_width=1d`
- Requires an **Admin API key** (Organization → API keys → create with the
  `api.usage.read` scope), generated separately from the project inference key.
- Returns a time-bucketed series of `amount.value` (USD) per day, optionally
  grouped by line item / project.

```python
import requests

def fetch_openai_cost(start_ts, end_ts, admin_key):
    resp = requests.get(
        "https://api.openai.com/v1/organization/costs",
        headers={"Authorization": f"Bearer {admin_key}"},
        params={"start_time": start_ts, "end_time": end_ts, "bucket_width": "1d"},
        timeout=15,
    )
    resp.raise_for_status()
    buckets = resp.json()["data"]
    return sum(item["amount"]["value"] for b in buckets for item in b["results"])
```

Currently low-priority: per project memory, the OpenAI key has **zero quota** (every
call 429s), so real spend is ₹0 regardless — but wiring this up costs nothing and
future-proofs the day billing credit is added.

**New env var needed**: `OPENAI_ADMIN_API_KEY` (distinct from `OPENAI_API_KEY`).

---

## 3. Gemini — via the same GCP Billing Export

Gemini API usage on a **pay-as-you-go** Google Cloud project bills through the same
Cloud Billing account as GCP, so it shows up as its own `service.description`
(`"Generative Language API"` or `"Vertex AI"`, depending on which endpoint is used)
in the exact same BigQuery export table from Section 1 — no separate integration
needed once GCP export is wired up.

**Caveat**: this project is currently on the **Gemini free tier**
(`gemini-flash-lite-latest` only, per project memory) — free-tier usage does **not**
generate billing export rows at all (there's nothing to bill). The query will
correctly return ₹0/no-rows for Gemini until/unless the project is moved to a paid
tier, which is the accurate reflection of current spend.

---

## 4. Groq — no billing API today

Groq does not currently publish a usage/cost REST API (confirmed by their public
docs as of this writing — token/rate-limit headers exist per-request, but no
aggregate billing endpoint). The only way to see spend is the Groq Console
dashboard (`console.groq.com/usage`), manually.

**Recommendation**: keep `INFRA_MONTHLY_GROQ_INR` as a manually-updated env
placeholder (already ₹0 today — free tier, no card on file — see
`_llm_pricing_reference()` in `cost_helpers.py`). Revisit this section if Groq ships
a billing API; until then automating it isn't possible.

---

## 5. Vercel — REST API

Vercel exposes a real usage API, scoped to a team/account:

- `GET https://api.vercel.com/v1/teams/<team_id>/usage` (or the account-level
  equivalent for personal/Hobby accounts) with a personal **Access Token**
  (Vercel dashboard → Settings → Tokens).
- On the **Hobby (free)** plan there is no monetary cost to report (₹0 by
  definition — see `_infra_plan_reference()`), but the usage endpoint still
  returns consumption against the plan's included quotas (GB-hours, bandwidth),
  which is useful to surface as a "% of free tier used" warning before the project
  outgrows Hobby and starts incurring real Pro-plan cost.

```python
def fetch_vercel_usage(team_id, token):
    resp = requests.get(
        f"https://api.vercel.com/v6/teams/{team_id}/usage",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()
```

**New env var needed**: `VERCEL_ACCESS_TOKEN`, `VERCEL_TEAM_ID`.

---

## 6. MongoDB Atlas — Admin API

Atlas has a real, documented Admin API for invoices:

- `GET https://cloud.mongodb.com/api/atlas/v2/orgs/{orgId}/invoices` (Digest auth
  with an Atlas **Programmatic API Key** — Organization → Access Manager → API
  Keys, needs "Organization Billing Viewer" role).
- Returns actual invoiced amounts per billing cycle. For a finer date range than a
  full invoice period, the `/invoices/{invoiceId}/lineitems` endpoint itemizes by
  cluster/day where available.

```python
from requests.auth import HTTPDigestAuth

def fetch_atlas_invoices(org_id, public_key, private_key):
    resp = requests.get(
        f"https://cloud.mongodb.com/api/atlas/v2/orgs/{org_id}/invoices",
        auth=HTTPDigestAuth(public_key, private_key),
        headers={"Accept": "application/vnd.atlas.2023-11-15+json"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()
```

**New env vars needed**: `ATLAS_ORG_ID`, `ATLAS_PUBLIC_KEY`, `ATLAS_PRIVATE_KEY`.

Currently `INFRA_MONTHLY_MONGODB_INR=3000` is a flat estimate (shared cluster
tier); this API would replace it with the real invoiced figure.

---

## 7. ZeptoMail — credit-based email pricing

ZeptoMail (Zoho) bills in prepaid credits: **1 credit = ₹150 = 10,000
transactional emails, valid 6 months from purchase**. The platform's assumed
volume is **30,000 emails/month → 3 credits → ₹450/month**, which is what
`INFRA_MONTHLY_ZEPTOMAIL_INR=450` reflects on the admin cost page.

ZeptoMail has no public billing/credit-balance REST API; remaining credits are
visible on the ZeptoMail console (Mail Agents → credits). Update the env figure
if the volume assumption changes (e.g. 50k emails/mo → 5 credits → ₹750).

---

## Recommended rollout order

1. ~~**GCP Billing Export → BigQuery**~~ (Section 1) — **DONE**: backend
   integration shipped; only the console-side export enablement + env var
   remain (owner action). Also covers Gemini for free (Section 3).
2. ~~**OpenAI Costs API**~~ (Section 2) — **DONE**: backend integration
   shipped; only the Admin API key creation remains (owner action).
3. **MongoDB Atlas Admin API** (Section 6) — next-biggest known line item
   (₹3,000/mo estimate), real invoice data readily available.
4. **Vercel REST API** (Section 5) — ₹0 cost either way on Hobby, but useful for
   the free-tier-quota warning.
5. **Groq** (Section 4) — not automatable today; leave as manual env placeholder.
6. **ZeptoMail** (Section 7) — no billing API; manual env figure from the
   credit math.

## Where this plugs into the existing code

The GCP and OpenAI fetches are integrated in `cost_stats_admin.py`'s
`get_cost_statistics()`: `services/gcp_billing_service.py` /
`services/openai_billing_service.py` are tried first for the selected window,
and the `INFRA_MONTHLY_*` env placeholders (pro-rated via
`_monthly_cost_for_window()`) remain the fallback when unconfigured or
unreachable — the page never breaks if a billing API is briefly down. Each
infra card carries a `usage_source` field (`billing_export` / `costs_api` /
`env_placeholder`) so the admin always knows whether a number is actual or
assumed. Future Atlas/Vercel integrations should follow the same pattern:
fetch → INR dict for the window → fall back to the env figure.
