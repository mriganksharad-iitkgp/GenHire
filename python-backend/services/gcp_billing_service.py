"""Real GCP cost fetch via the Cloud Billing → BigQuery export table.

GCP has no REST endpoint for "cost by service for a date range"; the supported
mechanism is the Standard Usage Cost billing export, which writes one row per
SKU per day into a BigQuery table. Once the owner enables that export in the
Billing Console (console-only — there is no API/CLI to enable it) and sets
GCP_BILLING_EXPORT_BQ_TABLE, this module gives the admin cost page real
per-service figures for any selected timeline plus the current invoice month's
accrued total ("outstanding to pay" on a postpaid account).

Setup (owner, one-time):
  1. GCP Console → Billing → Billing export → BigQuery export → enable
     "Standard usage cost" into a dataset (e.g. `billing_export`) in project
     hr-tech-2026. Rows appear within ~24h of enabling; no backfill.
  2. Grant the backend service account (genhire-backend@hr-tech-2026.iam.
     gserviceaccount.com) the roles BigQuery Data Viewer + BigQuery Job User.
  3. Set GCP_BILLING_EXPORT_BQ_TABLE to the full table id, e.g.
     hr-tech-2026.billing_export.gcp_billing_export_v1_XXXXXX_XXXXXX_XXXXXX

Everything degrades gracefully: missing env var / library / permissions →
fetch functions return None and the admin page falls back to the
INFRA_MONTHLY_GCP_* env placeholders (marked as such in the UI).
"""

import datetime
import json
import logging
import os
from services.shared_cache import cache

logger = logging.getLogger(__name__)

def _billing_cache_parts(key):
    return [os.getenv('GCP_BILLING_EXPORT_BQ_TABLE', ''), os.getenv('GCP_BILLING_EXPORT_BQ_LOCATION', ''), key]


# Maps BigQuery `service.description` values onto the admin page's fixed
# GCP breakdown keys; anything unmatched lands in "other".
_SERVICE_KEY_MAP = {
    "Cloud Run": "cloud_run",
    "Cloud Build": "cloud_build",
    "Cloud Storage": "cloud_storage",
    "Artifact Registry": "artifact_registry",
    "Compute Engine": "compute_engine",
    "VM Manager": "vm_manager",
    "Networking": "networking",
}


def _load_credentials():
    """Same credential resolution as GoogleSpeechService: inline JSON in the
    env var or a file path, either GOOGLE_APPLICATION_CREDENTIALS_JSON or
    GOOGLE_APPLICATION_CREDENTIALS. Returns None when unconfigured."""
    try:
        from google.oauth2 import service_account
    except ImportError:
        return None

    for env_name in ("GOOGLE_APPLICATION_CREDENTIALS_JSON", "GOOGLE_APPLICATION_CREDENTIALS"):
        raw = (os.getenv(env_name) or "").strip()
        if not raw:
            continue
        if raw.startswith("{"):
            try:
                return service_account.Credentials.from_service_account_info(json.loads(raw))
            except Exception as e:
                logger.error("gcp_billing: bad inline JSON in %s: %s", env_name, e)
        elif os.path.exists(raw):
            try:
                return service_account.Credentials.from_service_account_file(raw)
            except Exception as e:
                logger.error("gcp_billing: bad key file %s: %s", raw, e)
    return None


def _bq_client():
    table = (os.getenv("GCP_BILLING_EXPORT_BQ_TABLE") or "").strip()
    if not table:
        return None, None
    try:
        from google.cloud import bigquery
    except ImportError:
        logger.warning("gcp_billing: google-cloud-bigquery not installed; falling back to env placeholders")
        return None, None

    credentials = _load_credentials()
    if credentials is None:
        logger.warning("gcp_billing: GCP credentials unavailable; falling back to env placeholders")
        return None, None

    project = table.split(".")[0] if "." in table else None
    try:
        client = bigquery.Client(project=project, credentials=credentials)
    except Exception as e:
        logger.error("gcp_billing: could not create BigQuery client: %s", e)
        return None, None
    return client, table


def fetch_gcp_service_costs(start_dt, end_dt):
    return cache.remember('gcp-billing', _billing_cache_parts(['range', start_dt.isoformat(), end_dt.isoformat()]),
                          lambda: _fetch_service_costs(start_dt, end_dt), 600)


def _fetch_service_costs(start_dt, end_dt):
    """Net cost (usage cost + credits, i.e. what actually gets billed) per
    service for [start_dt, end_dt), in the billing account's currency.

    Returns {'services': {key: inr}, 'total': inr, 'currency': str} or None
    when the export isn't configured/reachable.
    """
    client, table = _bq_client()
    if client is None:
        return None

    from google.cloud import bigquery

    query = f"""
        SELECT
          service.description AS service,
          ANY_VALUE(currency) AS currency,
          SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS net_cost
        FROM `{table}`
        WHERE usage_start_time >= @start AND usage_start_time < @end
        GROUP BY service
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("start", "TIMESTAMP", start_dt),
            bigquery.ScalarQueryParameter("end", "TIMESTAMP", end_dt),
        ]
    )
    # Recent BigQuery clients infer job location from the referenced table;
    # the env var is an escape hatch if that inference ever misroutes.
    location = os.getenv("GCP_BILLING_EXPORT_BQ_LOCATION") or None
    try:
        rows = list(client.query(query, job_config=job_config, location=location).result(timeout=30))
    except Exception as e:
        logger.error("gcp_billing: range query failed: %s", e)
        return None

    # A freshly enabled export sits EMPTY for up to ~48h (and never backfills
    # days before enablement). An empty result would render as a misleading
    # "actual Rs.0" — treat it as not-ready and let the caller fall back to
    # the env-entered console figures until real rows land.
    if not rows:
        logger.info("gcp_billing: export table has no rows for this window yet; falling back to env estimates")
        return None

    services = {
        "cloud_run": 0.0, "cloud_build": 0.0, "cloud_storage": 0.0,
        "artifact_registry": 0.0, "compute_engine": 0.0, "vm_manager": 0.0,
        "networking": 0.0, "other": 0.0,
    }
    currency = "INR"
    for row in rows:
        key = _SERVICE_KEY_MAP.get(row.service, "other")
        services[key] += float(row.net_cost or 0.0)
        if row.currency:
            currency = row.currency
    return {"services": services, "total": sum(services.values()), "currency": currency}


def fetch_gcp_current_month_outstanding():
    invoice_month = datetime.datetime.utcnow().strftime('%Y%m')
    return cache.remember('gcp-billing', _billing_cache_parts(['outstanding', invoice_month]),
                          _fetch_current_month_outstanding, 600)


def _fetch_current_month_outstanding():
    """Accrued net cost for the current invoice month (invoice.month =
    YYYYMM) — on a postpaid billing account this is the amount outstanding
    to pay so far this month. Returns {'amount': float, 'currency': str,
    'invoice_month': 'YYYYMM'} or None."""
    client, table = _bq_client()
    if client is None:
        return None

    from google.cloud import bigquery

    invoice_month = datetime.datetime.utcnow().strftime("%Y%m")
    query = f"""
        SELECT
          ANY_VALUE(currency) AS currency,
          SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS net_cost
        FROM `{table}`
        WHERE invoice.month = @invoice_month
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("invoice_month", "STRING", invoice_month)]
    )
    location = os.getenv("GCP_BILLING_EXPORT_BQ_LOCATION") or None
    try:
        rows = list(client.query(query, job_config=job_config, location=location).result(timeout=30))
    except Exception as e:
        logger.error("gcp_billing: outstanding query failed: %s", e)
        return None

    if not rows or rows[0].net_cost is None:
        return {"amount": 0.0, "currency": "INR", "invoice_month": invoice_month}
    return {
        "amount": float(rows[0].net_cost),
        "currency": rows[0].currency or "INR",
        "invoice_month": invoice_month,
    }
