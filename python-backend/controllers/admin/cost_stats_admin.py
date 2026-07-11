"""Cost statistics: platform cost overview plus per-candidate/per-recruiter usage summaries and line items."""

import datetime
import os

from bson import ObjectId


def _env_monthly_inr(name, default):
    """Monthly INR figure from env — lets the owner keep real billing numbers
    (GCP invoice, OpenAI/Gemini/Groq spend, Cloudflare, MongoDB Atlas) current
    without a code change: update the env var, restart, done."""
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return float(default)


class CostStatsAdmin:
    def get_cost_statistics(
        self, current_user, period="month", start_date=None, end_date=None
    ):
        """Get timeline-based admin cost and profitability statistics."""
        try:
            from config.database import db_config
            from interview.core.cost_tracker import CostTracker

            def _safe_iso(dt_val):
                return dt_val.isoformat() if dt_val else None

            def _round_money(value):
                return round(float(value or 0.0), 2)

            def _safe_div(num, den):
                return (num / den) if den else 0.0

            def _parse_date(date_value, end_of_day=False):
                if not date_value:
                    return None

                parsed = None
                try:
                    parsed = datetime.datetime.fromisoformat(
                        str(date_value).replace("Z", "+00:00")
                    )
                except Exception:
                    try:
                        parsed = datetime.datetime.strptime(str(date_value), "%Y-%m-%d")
                    except Exception:
                        return None

                if parsed.tzinfo is not None:
                    parsed = parsed.astimezone(datetime.timezone.utc).replace(
                        tzinfo=None
                    )

                if len(str(date_value)) <= 10:
                    parsed = parsed.replace(
                        hour=23 if end_of_day else 0,
                        minute=59 if end_of_day else 0,
                        second=59 if end_of_day else 0,
                        microsecond=999999 if end_of_day else 0,
                    )

                return parsed

            def _period_window(period_value):
                now = datetime.datetime.utcnow()
                normalized_period = (period_value or "month").lower()

                if normalized_period == "week":
                    start = now - datetime.timedelta(days=7)
                elif normalized_period == "quarter":
                    start = now - datetime.timedelta(days=90)
                elif normalized_period == "year":
                    start = now - datetime.timedelta(days=365)
                else:
                    normalized_period = "month"
                    start = now - datetime.timedelta(days=30)

                return normalized_period, start, now

            def _build_date_range_query(base_query, date_fields, start_dt, end_dt):
                if not date_fields:
                    return base_query

                date_conditions = [
                    {field_name: {"$gte": start_dt, "$lte": end_dt}}
                    for field_name in date_fields
                ]

                return {"$and": [base_query, {"$or": date_conditions}]}

            def _count_documents_with_window(
                collection, base_query, date_fields, start_dt, end_dt
            ):
                if collection is None:
                    return 0
                query = _build_date_range_query(
                    base_query, date_fields, start_dt, end_dt
                )
                return collection.count_documents(query)

            def _monthly_cost_for_window(monthly_cost, start_dt, end_dt):
                if not monthly_cost:
                    return 0.0
                total_days = max(1, (end_dt - start_dt).days)
                return (monthly_cost / 30.0) * total_days

            def _llm_cost_usd(
                pricing_map, model_key, prompt_tokens, completion_tokens, action_count
            ):
                rates = pricing_map.get(model_key, {})
                input_rate = rates.get("input", 0.0)
                output_rate = rates.get("output", 0.0)
                prompt_cost = (prompt_tokens / 1_000_000.0) * input_rate
                completion_cost = (completion_tokens / 1_000_000.0) * output_rate
                return (prompt_cost + completion_cost) * max(action_count, 0)

            normalized_period, period_start, period_end = _period_window(period)
            requested_start = _parse_date(start_date, end_of_day=False)
            requested_end = _parse_date(end_date, end_of_day=True) if end_date else None

            if start_date and requested_start is None:
                return {"error": "Invalid start_date format. Use YYYY-MM-DD."}, 400

            if end_date and requested_end is None:
                return {"error": "Invalid end_date format. Use YYYY-MM-DD."}, 400

            if requested_end is None:
                requested_end = datetime.datetime.utcnow()

            if requested_start:
                period_start = requested_start
                period_end = requested_end
                normalized_period = "custom"

            if period_start > period_end:
                return {
                    "error": "Invalid timeline. start_date cannot be after end_date."
                }, 400

            db = db_config.get_db()
            if db is None:
                return {"error": "Database connection unavailable."}, 500
            plans_collection = db.plans
            payments_collection = db.payments

            plans_list = list(plans_collection.find({}))
            plans_by_id = {plan_doc.get("_id"): plan_doc for plan_doc in plans_list}

            pricing = CostTracker.PRICING
            inr_per_usd = 83.0

            # Monthly infrastructure/provider figures — env-driven placeholder
            # values for now (owner updates them from each billing console);
            # automatic fetch from GCP Billing/provider APIs is a planned
            # feature. GCP is itemized per service.
            gcp_service_assumptions = {
                "cloud_run": ("Cloud Run", _env_monthly_inr("INFRA_MONTHLY_GCP_CLOUD_RUN_INR", 500.0)),
                "cloud_build": ("Cloud Build", _env_monthly_inr("INFRA_MONTHLY_GCP_CLOUD_BUILD_INR", 100.0)),
                "cloud_storage": ("Cloud Storage", _env_monthly_inr("INFRA_MONTHLY_GCP_CLOUD_STORAGE_INR", 100.0)),
                "artifact_registry": ("Artifact Registry", _env_monthly_inr("INFRA_MONTHLY_GCP_ARTIFACT_REGISTRY_INR", 100.0)),
                "other": ("Other GCP services", _env_monthly_inr("INFRA_MONTHLY_GCP_OTHER_INR", 0.0)),
            }
            monthly_infra_assumptions = {
                "gcp": sum(value for _, value in gcp_service_assumptions.values()),
                "vercel": _env_monthly_inr("INFRA_MONTHLY_VERCEL_INR", 0.0),
                "mongodb": _env_monthly_inr("INFRA_MONTHLY_MONGODB_INR", 3000.0),
                "openai": _env_monthly_inr("INFRA_MONTHLY_OPENAI_INR", 500.0),
                "gemini": _env_monthly_inr("INFRA_MONTHLY_GEMINI_INR", 0.0),
                "groq": _env_monthly_inr("INFRA_MONTHLY_GROQ_INR", 0.0),
                # Legacy — only shown if a value is still configured.
                "cloudflare": _env_monthly_inr("INFRA_MONTHLY_CLOUDFLARE_INR", 0.0),
            }

            # Single source of truth for fallback assumptions (gpt-4o-mini
            # across the board) — see CostStatsHelpers._action_assumptions.
            action_assumptions = self._action_assumptions()

            def _aggregate_line_item(key, title, model, formula, lines):
                total = sum(float(line.get('cost_inr', 0.0) or 0.0) for line in lines)
                count = len(lines)
                return {
                    'key': key,
                    'title': title,
                    'count': int(count),
                    'model': model,
                    'formula': formula,
                    'total_cost_inr': _round_money(total),
                    'avg_cost_inr': _round_money(_safe_div(total, count)),
                }

            cv_lines = []
            jd_lines = []
            interview_lines = []
            interview_eval_lines = []
            practice_lines = []
            practice_eval_lines = []

            cv_query = _build_date_range_query(
                {'cv_score': {'$exists': True, '$ne': None}},
                ['cv_score_calculated_at', 'updated_at', 'created_at'],
                period_start,
                period_end,
            )
            cv_apps = list(self.applications_collection.find(cv_query)) if self.applications_collection is not None else []
            for app in cv_apps:
                cv_lines.append(
                    self._build_token_cost_line(
                        app,
                        'cv_scoring',
                        'Total CV Score Calculation Cost',
                        action_assumptions['cv_scoring'],
                        ['cv_score_calculated_at', 'updated_at', 'created_at'],
                        source_meta={
                            'type': 'application',
                            'id': str(app.get('_id') or ''),
                            'label': app.get('job_title') or 'Application',
                        }
                    )
                )

            jd_events = self._get_usage_events(
                actor_type='recruiter',
                action_types=['ai_jd_generation'],
                period_start=period_start,
                period_end=period_end,
            )
            if jd_events:
                for event in jd_events:
                    jd_lines.append(
                        self._build_token_cost_line(
                            event,
                            'ai_jd_generation',
                            'Total AI JD Generation Cost',
                            action_assumptions['ai_jd_generation'],
                            ['occurred_at', 'created_at'],
                            source_meta=event.get('source') or {},
                        )
                    )
            else:
                jobs_query = _build_date_range_query(
                    {},
                    ['created_at', 'updated_at'],
                    period_start,
                    period_end,
                )
                jobs = list(self.jobs_collection.find(jobs_query)) if self.jobs_collection is not None else []
                for job in jobs:
                    jd_lines.append(
                        self._build_token_cost_line(
                            job,
                            'ai_jd_generation',
                            'Total AI JD Generation Cost',
                            action_assumptions['ai_jd_generation'],
                            ['updated_at', 'created_at'],
                            source_meta={
                                'type': 'job',
                                'id': str(job.get('_id') or ''),
                                'label': job.get('title') or 'Job',
                            }
                        )
                    )

            interview_query = _build_date_range_query(
                {'is_visible': True, 'status': {'$in': ['interviewed', 'selected', 'screening_cleared', 'rejected']}},
                ['completed_at', 'updated_at', 'created_at'],
                period_start,
                period_end,
            )
            interview_apps = list(self.applications_collection.find(interview_query)) if self.applications_collection is not None else []
            interview_reports = self._latest_interview_reports_by_application([app.get('_id') for app in interview_apps])

            for app in interview_apps:
                app_with_context = self._merge_application_interview_context(
                    app,
                    interview_reports.get(str(app.get('_id') or ''))
                )

                interview_lines.append(
                    self._build_interview_cost_line(
                        app_with_context,
                        'ai_interview',
                        'Total AI Interview Cost',
                        action_assumptions['ai_interview'],
                        ['completed_at', 'updated_at', 'created_at'],
                        source_meta={
                            'type': 'application',
                            'id': str(app.get('_id') or ''),
                            'label': app.get('job_title') or 'Application',
                        }
                    )
                )

                if self._has_interview_evaluation(app_with_context):
                    app_with_eval_context = self._with_evaluation_context(app_with_context)
                    interview_eval_lines.append(
                        self._build_token_cost_line(
                            app_with_eval_context,
                            'ai_interview_evaluation',
                            'Total AI Interview Evaluation Cost',
                            action_assumptions['evaluation'],
                            ['completed_at', 'updated_at', 'created_at'],
                            source_meta={
                                'type': 'application',
                                'id': str(app.get('_id') or ''),
                                'label': app.get('job_title') or 'Application',
                            }
                        )
                    )

            # Only sessions that actually finished are charged/costed here —
            # matching the real-interview line's status filter above.
            # Without this, abandoned/still-active sessions (no real token
            # usage) fell back to the full assumed baseline cost per session,
            # inflating the practice-cost total for sessions that never
            # really ran.
            practice_query = _build_date_range_query(
                {'is_practice': True, 'status': 'completed'},
                ['created_at', 'updated_at', 'completed_at'],
                period_start,
                period_end,
            )
            practice_sessions = list(self.practice_sessions_collection.find(practice_query)) if self.practice_sessions_collection is not None else []
            for session in practice_sessions:
                practice_lines.append(
                    self._build_interview_cost_line(
                        session,
                        'practice_interview',
                        'Practice Interview Cost',
                        action_assumptions['ai_interview'],
                        ['completed_at', 'updated_at', 'created_at'],
                        source_meta={
                            'type': 'practice_session',
                            'id': session.get('session_id') or str(session.get('_id') or ''),
                            'label': session.get('role') or 'Practice Session',
                        }
                    )
                )

                session_with_eval_context = self._with_evaluation_context(session)
                practice_eval_lines.append(
                    self._build_token_cost_line(
                        session_with_eval_context,
                        'practice_interview_evaluation',
                        'Practice Interview Evaluation Cost',
                        action_assumptions['evaluation'],
                        ['completed_at', 'updated_at', 'created_at'],
                        source_meta={
                            'type': 'practice_session',
                            'id': session.get('session_id') or str(session.get('_id') or ''),
                            'label': session.get('role') or 'Practice Session',
                        }
                    )
                )

            cv_item = _aggregate_line_item(
                'cv_scoring',
                'Total CV Score Calculation Cost',
                action_assumptions['cv_scoring']['model'],
                'count × ((prompt/1M × input_rate) + (completion/1M × output_rate)) × INR conversion',
                cv_lines,
            )
            jd_item = _aggregate_line_item(
                'ai_jd_generation',
                'Total AI JD Generation Cost',
                action_assumptions['ai_jd_generation']['model'],
                'count × ((prompt/1M × input_rate) + (completion/1M × output_rate)) × INR conversion',
                jd_lines,
            )
            interview_item = _aggregate_line_item(
                'ai_interview',
                'Total AI Interview Cost',
                action_assumptions['ai_interview']['model'],
                'count × [LLM token cost + STT(sec/60×rate) + TTS(chars/1M×rate)] × INR conversion',
                interview_lines,
            )
            interview_eval_item = _aggregate_line_item(
                'ai_interview_evaluation',
                'Total AI Interview Evaluation Cost',
                action_assumptions['evaluation']['model'],
                'count × ((prompt/1M × input_rate) + (completion/1M × output_rate)) × INR conversion',
                interview_eval_lines,
            )
            practice_item = _aggregate_line_item(
                'practice_interview',
                'Practice Interview Cost',
                action_assumptions['ai_interview']['model'],
                'count × [LLM token cost + STT(sec/60×rate) + TTS(chars/1M×rate)] × INR conversion',
                practice_lines,
            )
            practice_eval_item = _aggregate_line_item(
                'practice_interview_evaluation',
                'Practice Interview Evaluation Cost',
                action_assumptions['evaluation']['model'],
                'count × ((prompt/1M × input_rate) + (completion/1M × output_rate)) × INR conversion',
                practice_eval_lines,
            )

            ai_cost_line_items = [
                cv_item,
                jd_item,
                interview_item,
                interview_eval_item,
                practice_item,
                practice_eval_item,
            ]
            total_ai_cost_inr = sum(
                item.get("total_cost_inr", 0.0) for item in ai_cost_line_items
            )

            cv_scoring_count = len(cv_lines)
            jd_generation_count = len(jd_lines)
            completed_interviews = len(interview_lines)
            interview_evaluation_count = len(interview_eval_lines)
            practice_interview_count = len(practice_lines)
            practice_evaluation_count = len(practice_eval_lines)

            # Fixed display set (owner-chosen): GCP itemized + Vercel +
            # MongoDB + the three LLM provider keys. Values are env-entered
            # placeholders until automatic billing fetch is implemented; every
            # requested entry is always returned (even at 0) so the admin UI
            # shows the full structure. Legacy Cloudflare appears only if
            # still configured.
            gcp_breakdown = []
            for service_key, (service_label, service_monthly) in gcp_service_assumptions.items():
                gcp_breakdown.append({
                    "key": service_key,
                    "label": service_label,
                    "monthly_assumption_inr": _round_money(service_monthly),
                    "prorated_cost_inr": _round_money(
                        _monthly_cost_for_window(service_monthly, period_start, period_end)
                    ),
                })

            infra_labels = {
                "gcp": "Google Cloud Platform",
                "vercel": "Vercel",
                "mongodb": "MongoDB Atlas",
                "openai": "OpenAI API",
                "gemini": "Google Gemini API",
                "groq": "Groq API",
                "cloudflare": "Cloudflare (legacy)",
            }
            infrastructure_costs = {}
            total_infra_prorated = 0.0
            for infra_key, infra_label in infra_labels.items():
                monthly_value = monthly_infra_assumptions.get(infra_key, 0.0)
                if infra_key == "cloudflare" and monthly_value <= 0:
                    continue
                prorated_value = _monthly_cost_for_window(
                    monthly_value, period_start, period_end
                )
                total_infra_prorated += prorated_value
                entry = {
                    "label": infra_label,
                    "monthly_assumption_inr": _round_money(monthly_value),
                    "prorated_cost_inr": _round_money(prorated_value),
                    "note": "Env-entered placeholder — automatic billing fetch planned.",
                }
                if infra_key == "gcp":
                    entry["breakdown"] = gcp_breakdown
                infrastructure_costs[infra_key] = entry

            total_infrastructure_cost_inr = _round_money(total_infra_prorated)
            total_cost_inr = _round_money(
                total_ai_cost_inr + total_infrastructure_cost_inr
            )

            payments_query = {
                "$and": [
                    {"status": "succeeded"},
                    {
                        "$or": [
                            {
                                "completed_at": {
                                    "$gte": period_start,
                                    "$lte": period_end,
                                }
                            },
                            {"created_at": {"$gte": period_start, "$lte": period_end}},
                        ]
                    },
                ]
            }
            succeeded_payments = (
                list(payments_collection.find(payments_query))
                if payments_collection is not None
                else []
            )

            def _resolve_payment_plan(payment_doc):
                plan_doc = plans_by_id.get(payment_doc.get("plan_id"))
                snapshot = payment_doc.get("metadata", {}) or {}
                if not plan_doc:
                    fallback_snapshot = payment_doc.get("plan_snapshot") or {}
                    snapshot = {**fallback_snapshot, **snapshot}

                plan_name = (
                    (plan_doc or {}).get("name")
                    or snapshot.get("plan_name")
                    or snapshot.get("name")
                    or "Unknown Plan"
                )
                plan_slug = (
                    (plan_doc or {}).get("slug")
                    or snapshot.get("plan_slug")
                    or snapshot.get("slug")
                    or "unknown-plan"
                )
                audience = (
                    (plan_doc or {}).get("audience")
                    or snapshot.get("owner_type")
                    or snapshot.get("audience")
                    or "recruiter"
                )
                if audience not in {"candidate", "recruiter"}:
                    audience = "recruiter"

                price_paise = (
                    (plan_doc or {}).get("price_paise")
                    or snapshot.get("price_paise")
                    or 0
                )

                return {
                    "name": plan_name,
                    "slug": plan_slug,
                    "audience": audience,
                    "price_inr": _round_money((price_paise or 0) / 100.0),
                }

            incoming_summary = {
                "candidate": {
                    "plans": {},
                    "succeeded_payment_count": 0,
                    "migration_payment_count": 0,
                    "total_incoming_inr": 0.0,
                },
                "recruiter": {
                    "plans": {},
                    "succeeded_payment_count": 0,
                    "migration_payment_count": 0,
                    "total_incoming_inr": 0.0,
                },
            }

            for payment_doc in succeeded_payments:
                payment_amount_inr = (payment_doc.get("amount_paise", 0) or 0) / 100.0
                plan_data = _resolve_payment_plan(payment_doc)
                audience = plan_data["audience"]
                plan_key = f"{plan_data['slug']}::{plan_data['price_inr']}"
                payment_metadata = payment_doc.get("metadata", {}) or {}
                is_migration_payment = bool(payment_metadata.get("migration"))

                if plan_key not in incoming_summary[audience]["plans"]:
                    incoming_summary[audience]["plans"][plan_key] = {
                        "plan_name": plan_data["name"],
                        "plan_slug": plan_data["slug"],
                        "plan_price_inr": plan_data["price_inr"],
                        "succeeded_payment_count": 0,
                        "migration_payment_count": 0,
                        "incoming_amount_inr": 0.0,
                    }

                incoming_summary[audience]["plans"][plan_key][
                    "succeeded_payment_count"
                ] += 1
                if is_migration_payment:
                    incoming_summary[audience]["plans"][plan_key][
                        "migration_payment_count"
                    ] += 1
                incoming_summary[audience]["plans"][plan_key][
                    "incoming_amount_inr"
                ] += payment_amount_inr
                incoming_summary[audience]["succeeded_payment_count"] += 1
                if is_migration_payment:
                    incoming_summary[audience]["migration_payment_count"] += 1
                incoming_summary[audience]["total_incoming_inr"] += payment_amount_inr

            refund_query = {
                "$and": [
                    {"status": {"$in": ["refunded", "partially_refunded"]}},
                    {
                        "$or": [
                            {"updated_at": {"$gte": period_start, "$lte": period_end}},
                            {"created_at": {"$gte": period_start, "$lte": period_end}},
                        ]
                    },
                ]
            }
            refund_payments = (
                list(payments_collection.find(refund_query))
                if payments_collection is not None
                else []
            )
            refund_total_inr = _round_money(
                sum(
                    (p.get("refund_amount_paise", 0) or 0) / 100.0
                    for p in refund_payments
                )
            )

            candidate_plans = sorted(
                [
                    {
                        **plan_row,
                        "incoming_amount_inr": _round_money(
                            plan_row["incoming_amount_inr"]
                        ),
                    }
                    for plan_row in incoming_summary["candidate"]["plans"].values()
                ],
                key=lambda item: (-item["incoming_amount_inr"], item["plan_name"]),
            )
            recruiter_plans = sorted(
                [
                    {
                        **plan_row,
                        "incoming_amount_inr": _round_money(
                            plan_row["incoming_amount_inr"]
                        ),
                    }
                    for plan_row in incoming_summary["recruiter"]["plans"].values()
                ],
                key=lambda item: (-item["incoming_amount_inr"], item["plan_name"]),
            )

            candidate_total_incoming = _round_money(
                incoming_summary["candidate"]["total_incoming_inr"]
            )
            recruiter_total_incoming = _round_money(
                incoming_summary["recruiter"]["total_incoming_inr"]
            )
            total_incoming = _round_money(
                candidate_total_incoming + recruiter_total_incoming
            )
            net_incoming_after_refunds = _round_money(total_incoming - refund_total_inr)

            profit_gross = _round_money(total_incoming - total_cost_inr)
            profit_net = _round_money(net_incoming_after_refunds - total_cost_inr)
            margin_gross = (
                round((_safe_div(profit_gross, total_incoming) * 100.0), 2)
                if total_incoming > 0
                else 0.0
            )
            margin_net = (
                round((_safe_div(profit_net, net_incoming_after_refunds) * 100.0), 2)
                if net_incoming_after_refunds > 0
                else 0.0
            )

            return {
                "timeline": {
                    "period_mode": normalized_period,
                    "start_date": _safe_iso(period_start),
                    "end_date": _safe_iso(period_end),
                    "days": max(1, (period_end - period_start).days),
                },
                "cost_statistics": {
                    "currency": "INR",
                    "ai_costs": ai_cost_line_items,
                    "total_ai_cost_inr": _round_money(total_ai_cost_inr),
                    "infrastructure_costs": {
                        **infrastructure_costs,
                        "total_infrastructure_cost_inr": total_infrastructure_cost_inr,
                    },
                    "total_cost_inr": total_cost_inr,
                },
                "incoming_money": {
                    "candidate": {
                        "plans": candidate_plans,
                        "succeeded_payment_count": incoming_summary["candidate"][
                            "succeeded_payment_count"]
                        ,
                        "migration_payment_count": incoming_summary["candidate"][
                            "migration_payment_count"]
                        ,
                        "total_incoming_inr": candidate_total_incoming,
                    },
                    "recruiter": {
                        "plans": recruiter_plans,
                        "succeeded_payment_count": incoming_summary["recruiter"][
                            "succeeded_payment_count"]
                        ,
                        "migration_payment_count": incoming_summary["recruiter"][
                            "migration_payment_count"]
                        ,
                        "total_incoming_inr": recruiter_total_incoming,
                    },
                    "total_incoming_inr": total_incoming,
                    "refund_adjustments": {
                        "refund_events_count": len(refund_payments),
                        "total_refunded_inr": refund_total_inr,
                    },
                    "net_incoming_after_refunds_inr": net_incoming_after_refunds,
                },
                "profitability": {
                    "cost_total_inr": total_cost_inr,
                    "incoming_total_inr": total_incoming,
                    "net_incoming_after_refunds_inr": net_incoming_after_refunds,
                    "profit_gross_inr": profit_gross,
                    "profit_net_inr": profit_net,
                    "margin_gross_pct": margin_gross,
                    "margin_net_pct": margin_net,
                },
                "activity_counts": {
                    "cv_scoring": int(cv_scoring_count),
                    "ai_jd_generation": int(jd_generation_count),
                    "ai_interview": int(completed_interviews),
                    "ai_interview_evaluation": int(interview_evaluation_count),
                    "practice_interview": int(practice_interview_count),
                    "practice_interview_evaluation": int(practice_evaluation_count),
                },
                "assumptions": {
                    "pricing_reference": "interview/core/cost_tracker.py",
                    "inr_per_usd": inr_per_usd,
                    "timeline_fallback_period": period,
                    "evaluation_assumption_tokens": {
                        "prompt": action_assumptions["evaluation"]["prompt_tokens"],
                        "completion": action_assumptions["evaluation"]["completion_tokens"],
                    },
                    "monthly_infrastructure_assumptions_inr": monthly_infra_assumptions,
                },
            }, 200

        except Exception as e:
            import traceback

            print(f"Error getting admin cost statistics: {str(e)}")
            print(traceback.format_exc())
            return {'error': 'Failed to get cost statistics'}, 500

    def get_candidate_usage_summary(self, current_user, period='month', start_date=None, end_date=None):
        try:
            period_mode, period_start, period_end, error_response, error_status = self._resolve_timeline_window(period, start_date, end_date)
            if error_response:
                return error_response, error_status

            assumptions = self._action_assumptions()

            # Burner (invite-only) candidates are excluded — they're blocked
            # from Practice mode (sponsored accounts are scoped to their
            # invited interview only), so they'd otherwise show up as
            # permanent zero-activity rows in this practice-usage report.
            candidate_docs = list(self.users_collection.find(
                {'user_type': 'candidate', 'is_invite_only': {'$ne': True}},
                {'name': 1, 'email': 1},
            ))
            candidate_map = {str(doc['_id']): doc for doc in candidate_docs}
            summary_map = {
                candidate_id: {
                    'candidate_id': candidate_id,
                    'name': doc.get('name', 'Unknown Candidate'),
                    'email': doc.get('email', ''),
                    'practice_interview_count': 0,
                    'practice_interview_total_cost_inr': 0.0,
                    'practice_interview_actual_total_cost_inr': 0.0,
                    'practice_interview_evaluation_count': 0,
                    'practice_interview_evaluation_total_cost_inr': 0.0,
                    'practice_interview_evaluation_actual_total_cost_inr': 0.0,
                }
                for candidate_id, doc in candidate_map.items()
            }

            candidate_ids = list(candidate_map.keys())
            # Only completed sessions are costed (matches the platform-wide
            # cost line above) — abandoned/still-active sessions have no
            # real token usage and would otherwise fall back to a full
            # assumed baseline cost, inflating this candidate's total.
            practice_query = self._build_date_range_query(
                {'is_practice': True, 'status': 'completed', 'user_id': {'$in': candidate_ids}},
                ['created_at', 'updated_at', 'completed_at'],
                period_start,
                period_end,
            )
            practice_sessions = list(self.practice_sessions_collection.find(practice_query)) if self.practice_sessions_collection is not None else []

            for session in practice_sessions:
                candidate_id = self._find_matching_user_id(candidate_map, session.get('user_id'))
                if not candidate_id:
                    continue

                practice_line = self._build_interview_cost_line(
                    session,
                    'practice_interview',
                    'Practice Interview Cost',
                    assumptions['ai_interview'],
                    ['completed_at', 'updated_at', 'created_at'],
                    source_meta={
                        'type': 'practice_session',
                        'id': session.get('session_id') or str(session.get('_id') or ''),
                        'label': session.get('role') or 'Practice Session',
                    }
                )
                summary_map[candidate_id]['practice_interview_count'] += 1
                summary_map[candidate_id]['practice_interview_total_cost_inr'] += float(practice_line['cost_inr'])
                summary_map[candidate_id]['practice_interview_actual_total_cost_inr'] += float(practice_line.get('actual_cost_inr') or 0.0)

                session_with_eval_context = self._with_evaluation_context(session)
                evaluation_line = self._build_token_cost_line(
                    session_with_eval_context,
                    'practice_interview_evaluation',
                    'Practice Interview Evaluation Cost',
                    assumptions['evaluation'],
                    ['completed_at', 'updated_at', 'created_at'],
                    source_meta={
                        'type': 'practice_session',
                        'id': session.get('session_id') or str(session.get('_id') or ''),
                        'label': session.get('role') or 'Practice Session',
                    }
                )
                summary_map[candidate_id]['practice_interview_evaluation_count'] += 1
                summary_map[candidate_id]['practice_interview_evaluation_total_cost_inr'] += float(evaluation_line['cost_inr'])
                summary_map[candidate_id]['practice_interview_evaluation_actual_total_cost_inr'] += float(evaluation_line.get('actual_cost_inr') or 0.0)

            incoming_map = self._user_succeeded_incoming_map(period_start, period_end, audience='candidate')
            plan_map = self._active_plan_name_map(audience='candidate')

            rows = []
            for candidate_id, row in summary_map.items():
                practice_total = float(row['practice_interview_total_cost_inr'])
                eval_total = float(row['practice_interview_evaluation_total_cost_inr'])
                practice_actual_total = float(row['practice_interview_actual_total_cost_inr'])
                eval_actual_total = float(row['practice_interview_evaluation_actual_total_cost_inr'])
                practice_count = int(row['practice_interview_count'])
                eval_count = int(row['practice_interview_evaluation_count'])
                total_actions = practice_count + eval_count
                total_cost = practice_total + eval_total
                total_actual_cost = practice_actual_total + eval_actual_total

                rows.append({
                    'candidate_id': candidate_id,
                    'name': row['name'],
                    'email': row['email'],
                    'enrolled_plan': plan_map.get(candidate_id, 'Free'),
                    'incoming_amount_inr': incoming_map.get(candidate_id, 0.0),
                    'practice_interview_count': practice_count,
                    'practice_interview_total_cost_inr': self._round_money(practice_total),
                    'practice_interview_actual_total_cost_inr': self._round_money(practice_actual_total),
                    'practice_interview_avg_cost_inr': self._round_money(self._safe_div(practice_total, practice_count)),
                    'practice_interview_evaluation_count': eval_count,
                    'practice_interview_evaluation_total_cost_inr': self._round_money(eval_total),
                    'practice_interview_evaluation_actual_total_cost_inr': self._round_money(eval_actual_total),
                    'practice_interview_evaluation_avg_cost_inr': self._round_money(self._safe_div(eval_total, eval_count)),
                    'total_actions': total_actions,
                    'total_usage_cost_inr': self._round_money(total_cost),
                    'total_actual_usage_cost_inr': self._round_money(total_actual_cost) if total_actual_cost > 0 else None,
                    'avg_usage_cost_inr': self._round_money(self._safe_div(total_cost, total_actions)),
                    'avg_actual_usage_cost_inr': self._round_money(self._safe_div(total_actual_cost, total_actions)) if total_actual_cost > 0 else None,
                })

            rows.sort(key=lambda item: (-item['total_usage_cost_inr'], item['name']))

            return {
                'timeline': {
                    'period_mode': period_mode,
                    'start_date': self._safe_iso(period_start),
                    'end_date': self._safe_iso(period_end),
                    'days': max(1, (period_end - period_start).days),
                },
                'rows': rows,
                'total_candidates': len(rows),
            }, 200

        except Exception as e:
            import traceback
            print(f"Error getting candidate usage summary: {str(e)}")
            print(traceback.format_exc())
            return {'error': 'Failed to get candidate usage summary'}, 500

    def get_candidate_usage_lines(self, current_user, candidate_id, period='month', start_date=None, end_date=None, page=1, limit=50, search=''):
        try:
            period_mode, period_start, period_end, error_response, error_status = self._resolve_timeline_window(period, start_date, end_date)
            if error_response:
                return error_response, error_status

            try:
                candidate_doc = self.users_collection.find_one({'_id': ObjectId(candidate_id), 'user_type': 'candidate'}, {'name': 1, 'email': 1})
            except Exception:
                candidate_doc = self.users_collection.find_one({'_id': candidate_id, 'user_type': 'candidate'}, {'name': 1, 'email': 1})

            if not candidate_doc:
                return {'error': 'Candidate not found'}, 404

            assumptions = self._action_assumptions()

            candidate_id_str = str(candidate_doc.get('_id'))
            candidate_id_variants = [candidate_id_str]
            if ObjectId.is_valid(candidate_id_str):
                candidate_id_variants.append(ObjectId(candidate_id_str))

            practice_query = self._build_date_range_query(
                {'is_practice': True, 'user_id': {'$in': candidate_id_variants}},
                ['created_at', 'updated_at', 'completed_at'],
                period_start,
                period_end,
            )
            sessions = list(self.practice_sessions_collection.find(practice_query)) if self.practice_sessions_collection is not None else []

            practice_lines = []
            practice_eval_lines = []

            for session in sessions:
                practice_lines.append(
                    self._build_interview_cost_line(
                        session,
                        'practice_interview',
                        'Practice Interview Cost',
                        assumptions['ai_interview'],
                        ['completed_at', 'updated_at', 'created_at'],
                        source_meta={
                            'type': 'practice_session',
                            'id': session.get('session_id') or str(session.get('_id') or ''),
                            'label': session.get('role') or 'Practice Session',
                        }
                    )
                )
                session_with_eval_context = self._with_evaluation_context(session)
                practice_eval_lines.append(
                    self._build_token_cost_line(
                        session_with_eval_context,
                        'practice_interview_evaluation',
                        'Practice Interview Evaluation Cost',
                        assumptions['evaluation'],
                        ['completed_at', 'updated_at', 'created_at'],
                        source_meta={
                            'type': 'practice_session',
                            'id': session.get('session_id') or str(session.get('_id') or ''),
                            'label': session.get('role') or 'Practice Session',
                        }
                    )
                )

            raw_categories = [
                self._line_category_summary('practice_interview', 'Practice Interview Cost', practice_lines),
                self._line_category_summary('practice_interview_evaluation', 'Practice Interview Evaluation Cost', practice_eval_lines),
            ]

            categories = []
            for category in raw_categories:
                paged = self._search_and_paginate_lines(category['lines'], search=search, page=page, limit=limit)
                categories.append({
                    **category,
                    'lines': paged['items'],
                    'line_pagination': paged['pagination'],
                })

            total_count = sum(category['count'] for category in categories)
            total_cost = sum(float(category['total_cost_inr']) for category in categories)
            actual_cost_values = [category.get('total_actual_cost_inr') for category in categories if category.get('total_actual_cost_inr') is not None]
            total_actual_cost = sum(float(value or 0.0) for value in actual_cost_values)

            return {
                'timeline': {
                    'period_mode': period_mode,
                    'start_date': self._safe_iso(period_start),
                    'end_date': self._safe_iso(period_end),
                    'days': max(1, (period_end - period_start).days),
                },
                'candidate': {
                    'id': str(candidate_doc.get('_id')),
                    'name': candidate_doc.get('name', 'Unknown Candidate'),
                    'email': candidate_doc.get('email', ''),
                },
                'categories': categories,
                'summary': {
                    'total_actions': total_count,
                    'total_usage_cost_inr': self._round_money(total_cost),
                    'total_actual_usage_cost_inr': self._round_money(total_actual_cost) if actual_cost_values else None,
                    'avg_usage_cost_inr': self._round_money(self._safe_div(total_cost, total_count)),
                    'avg_actual_usage_cost_inr': self._round_money(self._safe_div(total_actual_cost, total_count)) if actual_cost_values else None,
                }
            }, 200

        except Exception as e:
            import traceback
            print(f"Error getting candidate usage lines: {str(e)}")
            print(traceback.format_exc())
            return {'error': 'Failed to get candidate usage lines'}, 500

    def _recruiter_id_from_job(self, job_doc):
        return str(job_doc.get('recruiter_id') or job_doc.get('created_by') or '')

    def _recruiter_id_from_application(self, application_doc):
        recruiter_id = application_doc.get('recruiter_id')
        if recruiter_id:
            return str(recruiter_id)

        job_id = application_doc.get('job_id')
        if not job_id:
            return ''

        job_doc = None
        try:
            job_doc = self.jobs_collection.find_one({'_id': ObjectId(job_id)}, {'recruiter_id': 1, 'created_by': 1})
        except Exception:
            job_doc = self.jobs_collection.find_one({'_id': job_id}, {'recruiter_id': 1, 'created_by': 1})

        if not job_doc:
            return ''

        return self._recruiter_id_from_job(job_doc)

    def get_recruiter_usage_summary(self, current_user, period='month', start_date=None, end_date=None):
        try:
            period_mode, period_start, period_end, error_response, error_status = self._resolve_timeline_window(period, start_date, end_date)
            if error_response:
                return error_response, error_status

            assumptions = self._action_assumptions()

            recruiter_docs = list(self.users_collection.find({'user_type': 'recruiter'}, {'name': 1, 'email': 1}))
            recruiter_map = {str(doc['_id']): doc for doc in recruiter_docs}
            recruiter_ids = list(recruiter_map.keys())

            summary_map = {
                recruiter_id: {
                    'recruiter_id': recruiter_id,
                    'name': doc.get('name', 'Unknown Recruiter'),
                    'email': doc.get('email', ''),
                    'real_interview_count': 0,
                    'real_interview_total_cost_inr': 0.0,
                    'real_interview_actual_total_cost_inr': 0.0,
                    'real_interview_evaluation_count': 0,
                    'real_interview_evaluation_total_cost_inr': 0.0,
                    'real_interview_evaluation_actual_total_cost_inr': 0.0,
                    'ai_jd_generation_count': 0,
                    'ai_jd_generation_total_cost_inr': 0.0,
                    'ai_jd_generation_actual_total_cost_inr': 0.0,
                    'cv_score_count': 0,
                    'cv_score_total_cost_inr': 0.0,
                    'cv_score_actual_total_cost_inr': 0.0,
                }
                for recruiter_id, doc in recruiter_map.items()
            }

            jd_events = self._get_usage_events(
                actor_type='recruiter',
                action_types=['ai_jd_generation'],
                period_start=period_start,
                period_end=period_end,
            )

            if jd_events:
                for event in jd_events:
                    recruiter_id = self._find_matching_user_id(recruiter_map, event.get('actor_id'))
                    if not recruiter_id:
                        continue
                    jd_line = self._build_token_cost_line(
                        event,
                        'ai_jd_generation',
                        'Total AI JD Generation Cost',
                        assumptions['ai_jd_generation'],
                        ['occurred_at', 'created_at'],
                        source_meta=event.get('source') or {},
                    )
                    summary_map[recruiter_id]['ai_jd_generation_count'] += 1
                    summary_map[recruiter_id]['ai_jd_generation_total_cost_inr'] += float(jd_line['cost_inr'])
                    summary_map[recruiter_id]['ai_jd_generation_actual_total_cost_inr'] += float(jd_line.get('actual_cost_inr') or 0.0)
            else:
                jobs_query = self._build_date_range_query(
                    {
                        '$or': [
                            {'created_by': {'$in': recruiter_ids}},
                            {'recruiter_id': {'$in': recruiter_ids}},
                        ]
                    },
                    ['created_at', 'updated_at'],
                    period_start,
                    period_end,
                )
                jobs = list(self.jobs_collection.find(jobs_query)) if self.jobs_collection is not None else []
                for job in jobs:
                    recruiter_id = self._find_matching_user_id(recruiter_map, self._recruiter_id_from_job(job))
                    if not recruiter_id:
                        continue
                    jd_line = self._build_token_cost_line(
                        job,
                        'ai_jd_generation',
                        'Total AI JD Generation Cost',
                        assumptions['ai_jd_generation'],
                        ['updated_at', 'created_at'],
                        source_meta={
                            'type': 'job',
                            'id': str(job.get('_id') or ''),
                            'label': job.get('title') or 'Job',
                        }
                    )
                    summary_map[recruiter_id]['ai_jd_generation_count'] += 1
                    summary_map[recruiter_id]['ai_jd_generation_total_cost_inr'] += float(jd_line['cost_inr'])
                    summary_map[recruiter_id]['ai_jd_generation_actual_total_cost_inr'] += float(jd_line.get('actual_cost_inr') or 0.0)

            cv_query = self._build_date_range_query(
                {'cv_score': {'$exists': True, '$ne': None}},
                ['cv_score_calculated_at', 'updated_at', 'created_at'],
                period_start,
                period_end,
            )
            cv_apps = list(self.applications_collection.find(cv_query)) if self.applications_collection is not None else []
            for app in cv_apps:
                recruiter_id = self._find_matching_user_id(recruiter_map, self._recruiter_id_from_application(app))
                if not recruiter_id:
                    continue
                cv_line = self._build_token_cost_line(
                    app,
                    'cv_scoring',
                    'Total CV Score Calculation Cost',
                    assumptions['cv_scoring'],
                    ['cv_score_calculated_at', 'updated_at', 'created_at'],
                    source_meta={
                        'type': 'application',
                        'id': str(app.get('_id') or ''),
                        'label': app.get('job_title') or 'Application',
                    }
                )
                summary_map[recruiter_id]['cv_score_count'] += 1
                summary_map[recruiter_id]['cv_score_total_cost_inr'] += float(cv_line['cost_inr'])
                summary_map[recruiter_id]['cv_score_actual_total_cost_inr'] += float(cv_line.get('actual_cost_inr') or 0.0)

            base_app_query = {
                'recruiter_id': {'$in': recruiter_ids}
            }
            interview_query = self._build_date_range_query(
                {
                    **base_app_query,
                    'is_visible': True,
                    'status': {'$in': ['interviewed', 'selected', 'screening_cleared', 'rejected']},
                },
                ['completed_at', 'updated_at', 'created_at'],
                period_start,
                period_end,
            )
            interview_apps = list(self.applications_collection.find(interview_query)) if self.applications_collection is not None else []
            interview_reports = self._latest_interview_reports_by_application([app.get('_id') for app in interview_apps])
            for app in interview_apps:
                app_with_context = self._merge_application_interview_context(
                    app,
                    interview_reports.get(str(app.get('_id') or ''))
                )
                recruiter_id = self._find_matching_user_id(recruiter_map, self._recruiter_id_from_application(app))
                if not recruiter_id:
                    continue
                interview_line = self._build_interview_cost_line(
                    app_with_context,
                    'ai_interview',
                    'Total Real Interview Cost',
                    assumptions['ai_interview'],
                    ['completed_at', 'updated_at', 'created_at'],
                    source_meta={
                        'type': 'application',
                        'id': str(app.get('_id') or ''),
                        'label': app.get('job_title') or 'Application',
                    }
                )
                summary_map[recruiter_id]['real_interview_count'] += 1
                summary_map[recruiter_id]['real_interview_total_cost_inr'] += float(interview_line['cost_inr'])
                summary_map[recruiter_id]['real_interview_actual_total_cost_inr'] += float(interview_line.get('actual_cost_inr') or 0.0)

                if self._has_interview_evaluation(app_with_context):
                    app_with_eval_context = self._with_evaluation_context(app_with_context)
                    eval_line = self._build_token_cost_line(
                        app_with_eval_context,
                        'ai_interview_evaluation',
                        'Total Real Interview Evaluation Cost',
                        assumptions['evaluation'],
                        ['completed_at', 'updated_at', 'created_at'],
                        source_meta={
                            'type': 'application',
                            'id': str(app.get('_id') or ''),
                            'label': app.get('job_title') or 'Application',
                        }
                    )
                    summary_map[recruiter_id]['real_interview_evaluation_count'] += 1
                    summary_map[recruiter_id]['real_interview_evaluation_total_cost_inr'] += float(eval_line['cost_inr'])
                    summary_map[recruiter_id]['real_interview_evaluation_actual_total_cost_inr'] += float(eval_line.get('actual_cost_inr') or 0.0)

            incoming_map = self._user_succeeded_incoming_map(period_start, period_end, audience='recruiter')
            plan_map = self._active_plan_name_map(audience='recruiter')

            rows = []
            for recruiter_id, row in summary_map.items():
                interview_total = float(row['real_interview_total_cost_inr'])
                interview_eval_total = float(row['real_interview_evaluation_total_cost_inr'])
                jd_total = float(row['ai_jd_generation_total_cost_inr'])
                cv_total = float(row['cv_score_total_cost_inr'])
                interview_actual_total = float(row['real_interview_actual_total_cost_inr'])
                interview_eval_actual_total = float(row['real_interview_evaluation_actual_total_cost_inr'])
                jd_actual_total = float(row['ai_jd_generation_actual_total_cost_inr'])
                cv_actual_total = float(row['cv_score_actual_total_cost_inr'])
                interview_count = int(row['real_interview_count'])
                interview_eval_count = int(row['real_interview_evaluation_count'])
                jd_count = int(row['ai_jd_generation_count'])
                cv_count = int(row['cv_score_count'])

                total_actions = interview_count + interview_eval_count + jd_count + cv_count
                total_cost = interview_total + interview_eval_total + jd_total + cv_total
                total_actual_cost = interview_actual_total + interview_eval_actual_total + jd_actual_total + cv_actual_total

                rows.append({
                    'recruiter_id': recruiter_id,
                    'name': row['name'],
                    'email': row['email'],
                    'enrolled_plan': plan_map.get(recruiter_id, 'Free'),
                    'incoming_amount_inr': incoming_map.get(recruiter_id, 0.0),
                    'real_interview_count': interview_count,
                    'real_interview_total_cost_inr': self._round_money(interview_total),
                    'real_interview_actual_total_cost_inr': self._round_money(interview_actual_total),
                    'real_interview_avg_cost_inr': self._round_money(self._safe_div(interview_total, interview_count)),
                    'real_interview_evaluation_count': interview_eval_count,
                    'real_interview_evaluation_total_cost_inr': self._round_money(interview_eval_total),
                    'real_interview_evaluation_actual_total_cost_inr': self._round_money(interview_eval_actual_total),
                    'real_interview_evaluation_avg_cost_inr': self._round_money(self._safe_div(interview_eval_total, interview_eval_count)),
                    'ai_jd_generation_count': jd_count,
                    'ai_jd_generation_total_cost_inr': self._round_money(jd_total),
                    'ai_jd_generation_actual_total_cost_inr': self._round_money(jd_actual_total),
                    'ai_jd_generation_avg_cost_inr': self._round_money(self._safe_div(jd_total, jd_count)),
                    'cv_score_count': cv_count,
                    'cv_score_total_cost_inr': self._round_money(cv_total),
                    'cv_score_actual_total_cost_inr': self._round_money(cv_actual_total),
                    'cv_score_avg_cost_inr': self._round_money(self._safe_div(cv_total, cv_count)),
                    'total_actions': total_actions,
                    'total_usage_cost_inr': self._round_money(total_cost),
                    'total_actual_usage_cost_inr': self._round_money(total_actual_cost) if total_actual_cost > 0 else None,
                    'avg_usage_cost_inr': self._round_money(self._safe_div(total_cost, total_actions)),
                    'avg_actual_usage_cost_inr': self._round_money(self._safe_div(total_actual_cost, total_actions)) if total_actual_cost > 0 else None,
                })

            rows.sort(key=lambda item: (-item['total_usage_cost_inr'], item['name']))

            return {
                'timeline': {
                    'period_mode': period_mode,
                    'start_date': self._safe_iso(period_start),
                    'end_date': self._safe_iso(period_end),
                    'days': max(1, (period_end - period_start).days),
                },
                'rows': rows,
                'total_recruiters': len(rows),
            }, 200

        except Exception as e:
            import traceback
            print(f"Error getting recruiter usage summary: {str(e)}")
            print(traceback.format_exc())
            return {'error': 'Failed to get recruiter usage summary'}, 500

    def get_recruiter_usage_lines(self, current_user, recruiter_id, period='month', start_date=None, end_date=None, page=1, limit=50, search=''):
        try:
            period_mode, period_start, period_end, error_response, error_status = self._resolve_timeline_window(period, start_date, end_date)
            if error_response:
                return error_response, error_status

            try:
                recruiter_doc = self.users_collection.find_one({'_id': ObjectId(recruiter_id), 'user_type': 'recruiter'}, {'name': 1, 'email': 1})
            except Exception:
                recruiter_doc = self.users_collection.find_one({'_id': recruiter_id, 'user_type': 'recruiter'}, {'name': 1, 'email': 1})

            if not recruiter_doc:
                return {'error': 'Recruiter not found'}, 404

            recruiter_id_str = str(recruiter_doc.get('_id'))
            assumptions = self._action_assumptions()

            jd_lines = []
            cv_lines = []
            interview_lines = []
            interview_eval_lines = []

            recruiter_id_variants = [recruiter_id_str]
            if ObjectId.is_valid(recruiter_id_str):
                recruiter_id_variants.append(ObjectId(recruiter_id_str))

            jd_events = self._get_usage_events(
                actor_type='recruiter',
                actor_id=recruiter_id_str,
                action_types=['ai_jd_generation'],
                period_start=period_start,
                period_end=period_end,
            )

            if jd_events:
                for event in jd_events:
                    jd_lines.append(
                        self._build_token_cost_line(
                            event,
                            'ai_jd_generation',
                            'Total AI JD Generation Cost',
                            assumptions['ai_jd_generation'],
                            ['occurred_at', 'created_at'],
                            source_meta=event.get('source') or {},
                        )
                    )
            else:
                jobs_query = self._build_date_range_query(
                    {
                        '$or': [
                            {'created_by': {'$in': recruiter_id_variants}},
                            {'recruiter_id': {'$in': recruiter_id_variants}},
                        ]
                    },
                    ['created_at', 'updated_at'],
                    period_start,
                    period_end,
                )
                jobs = list(self.jobs_collection.find(jobs_query)) if self.jobs_collection is not None else []
                for job in jobs:
                    jd_lines.append(
                        self._build_token_cost_line(
                            job,
                            'ai_jd_generation',
                            'Total AI JD Generation Cost',
                            assumptions['ai_jd_generation'],
                            ['updated_at', 'created_at'],
                            source_meta={
                                'type': 'job',
                                'id': str(job.get('_id') or ''),
                                'label': job.get('title') or 'Job',
                            }
                        )
                    )

            base_app_query = {
                '$or': [
                    {'recruiter_id': recruiter_id_str},
                    {'recruiter_id': ObjectId(recruiter_id_str)} if ObjectId.is_valid(recruiter_id_str) else {'recruiter_id': recruiter_id_str}
                ]
            }

            cv_query = self._build_date_range_query(
                {**base_app_query, 'cv_score': {'$exists': True, '$ne': None}},
                ['cv_score_calculated_at', 'updated_at', 'created_at'],
                period_start,
                period_end,
            )
            cv_apps = list(self.applications_collection.find(cv_query)) if self.applications_collection is not None else []
            for app in cv_apps:
                cv_lines.append(
                    self._build_token_cost_line(
                        app,
                        'cv_scoring',
                        'Total CV Score Calculation Cost',
                        assumptions['cv_scoring'],
                        ['cv_score_calculated_at', 'updated_at', 'created_at'],
                        source_meta={
                            'type': 'application',
                            'id': str(app.get('_id') or ''),
                            'label': app.get('job_title') or 'Application',
                        }
                    )
                )

            interview_query = self._build_date_range_query(
                {
                    **base_app_query,
                    'is_visible': True,
                    'status': {'$in': ['interviewed', 'selected', 'screening_cleared', 'rejected']},
                },
                ['completed_at', 'updated_at', 'created_at'],
                period_start,
                period_end,
            )
            interview_apps = list(self.applications_collection.find(interview_query)) if self.applications_collection is not None else []
            interview_reports = self._latest_interview_reports_by_application([app.get('_id') for app in interview_apps])
            for app in interview_apps:
                app_with_context = self._merge_application_interview_context(
                    app,
                    interview_reports.get(str(app.get('_id') or ''))
                )
                interview_lines.append(
                    self._build_interview_cost_line(
                        app_with_context,
                        'ai_interview',
                        'Total Real Interview Cost',
                        assumptions['ai_interview'],
                        ['completed_at', 'updated_at', 'created_at'],
                        source_meta={
                            'type': 'application',
                            'id': str(app.get('_id') or ''),
                            'label': app.get('job_title') or 'Application',
                        }
                    )
                )

                if self._has_interview_evaluation(app_with_context):
                    app_with_eval_context = self._with_evaluation_context(app_with_context)
                    interview_eval_lines.append(
                        self._build_token_cost_line(
                            app_with_eval_context,
                            'ai_interview_evaluation',
                            'Total Real Interview Evaluation Cost',
                            assumptions['evaluation'],
                            ['completed_at', 'updated_at', 'created_at'],
                            source_meta={
                                'type': 'application',
                                'id': str(app.get('_id') or ''),
                                'label': app.get('job_title') or 'Application',
                            }
                        )
                    )

            raw_categories = [
                self._line_category_summary('ai_interview', 'Total Real Interview Cost', interview_lines),
                self._line_category_summary('ai_interview_evaluation', 'Total Real Interview Evaluation Cost', interview_eval_lines),
                self._line_category_summary('ai_jd_generation', 'Total AI JD Generation Cost', jd_lines),
                self._line_category_summary('cv_scoring', 'Total CV Score Calculation Cost', cv_lines),
            ]

            categories = []
            for category in raw_categories:
                paged = self._search_and_paginate_lines(category['lines'], search=search, page=page, limit=limit)
                categories.append({
                    **category,
                    'lines': paged['items'],
                    'line_pagination': paged['pagination'],
                })

            total_count = sum(category['count'] for category in categories)
            total_cost = sum(float(category['total_cost_inr']) for category in categories)
            actual_cost_values = [category.get('total_actual_cost_inr') for category in categories if category.get('total_actual_cost_inr') is not None]
            total_actual_cost = sum(float(value or 0.0) for value in actual_cost_values)

            return {
                'timeline': {
                    'period_mode': period_mode,
                    'start_date': self._safe_iso(period_start),
                    'end_date': self._safe_iso(period_end),
                    'days': max(1, (period_end - period_start).days),
                },
                'recruiter': {
                    'id': recruiter_id_str,
                    'name': recruiter_doc.get('name', 'Unknown Recruiter'),
                    'email': recruiter_doc.get('email', ''),
                },
                'categories': categories,
                'summary': {
                    'total_actions': total_count,
                    'total_usage_cost_inr': self._round_money(total_cost),
                    'total_actual_usage_cost_inr': self._round_money(total_actual_cost) if actual_cost_values else None,
                    'avg_usage_cost_inr': self._round_money(self._safe_div(total_cost, total_count)),
                    'avg_actual_usage_cost_inr': self._round_money(self._safe_div(total_actual_cost, total_count)) if actual_cost_values else None,
                }
            }, 200

        except Exception as e:
            import traceback
            print(f"Error getting recruiter usage lines: {str(e)}")
            print(traceback.format_exc())
            return {'error': 'Failed to get recruiter usage lines'}, 500
