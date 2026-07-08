"""Credit-wallet reporting: per-candidate/per-recruiter credit summaries and activity lines."""

import datetime
from bson import ObjectId
from payment_module.services.wallet_service import WalletService


class CreditAdmin:
    def _get_wallet_service(self):
        if getattr(self, '_wallet_service', None) is None:
            self._wallet_service = WalletService(self.users_collection.database)
        return self._wallet_service

    def _credit_description(self, transaction):
        metadata = transaction.get('metadata') or {}
        parts = []
        plan_name = metadata.get('plan_name') or metadata.get('plan_slug') or metadata.get('name') or metadata.get('slug')
        if plan_name:
            parts.append(str(plan_name))
        reason = metadata.get('reason') or metadata.get('description')
        if reason:
            parts.append(str(reason))

        reference_type = transaction.get('reference_type')
        reference_id = transaction.get('reference_id')
        if not parts and (reference_type or reference_id):
            parts.append(f"{reference_type or 'reference'}:{reference_id or ''}".strip(':'))

        if not parts:
            return str(transaction.get('transaction_type') or 'Credit transaction')

        return ' - '.join(parts)

    def _format_tx_timestamp(self, value):
        if isinstance(value, datetime.datetime):
            return value.strftime("%Y-%m-%d %H:%M")
        text = str(value or "")
        try:
            parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return text

    def _is_proctored_tx(self, tx):
        metadata = tx.get("metadata") or {}
        if "proctoring_enabled" in metadata:
            return bool(metadata.get("proctoring_enabled"))
        proctoring_config = metadata.get("proctoring_config")
        if isinstance(proctoring_config, dict):
            return any(bool(value) for value in proctoring_config.values())
        return False

    def _credit_activity_label(self, tx):
        tx_type = str(tx.get("transaction_type") or "")
        if tx_type == "practice_interview":
            return (
                "Practice Interview (Proctored)"
                if self._is_proctored_tx(tx)
                else "Practice Interview (Non-Proctored)"
            )
        if tx_type == "real_interview_recruiter":
            return (
                "Real Interview (Proctored)"
                if self._is_proctored_tx(tx)
                else "Real Interview (Non-Proctored)"
            )
        if tx_type == "ai_jd_generation":
            return "AI JD Generation"
        if tx_type == "migration_recharge":
            return "Migration Recharge"
        return str(tx_type or "activity").replace("_", " ").title()

    def _format_activity_row(self, tx):
        delta = int(tx.get("delta_credits", 0) or 0)
        credits_deducted = abs(delta) if delta < 0 else 0
        return {
            "id": tx.get("id"),
            "activity_type": self._credit_activity_label(tx),
            "transaction_type": tx.get("transaction_type"),
            "credits_deducted": credits_deducted,
            "delta_credits": delta,
            "balance_after": int(tx.get("balance_after", 0) or 0),
            "remaining_balance": int(tx.get("balance_after", 0) or 0),
            "timestamp": self._format_tx_timestamp(tx.get("created_at")),
        }

    def _credit_summary_rows(self, audience, start_dt, end_dt):
        wallet_service = self._get_wallet_service()
        transaction_collection = wallet_service.transaction_collection
        recharge_types = list(wallet_service.RECHARGE_TRANSACTION_TYPES)

        user_docs = list(self.users_collection.find({'user_type': audience}, {'name': 1, 'email': 1}))
        rows = []

        for user in user_docs:
            owner_id = str(user.get('_id'))
            wallet_summary = wallet_service.get_wallet_summary(owner_id, audience)
            current_balance = int(wallet_summary.get('credits_balance', 0) or 0)

            last_recharge_tx = transaction_collection.find_one(
                {
                    'owner_id': owner_id,
                    'audience': audience,
                    'transaction_type': {'$in': recharge_types},
                },
                sort=[('created_at', -1)],
            )
            last_recharge_date = self._safe_iso(last_recharge_tx.get('created_at')) if last_recharge_tx else None
            last_recharge_meta = last_recharge_tx.get('metadata') if last_recharge_tx else {}
            last_recharge_plan = None
            if last_recharge_meta:
                last_recharge_plan = last_recharge_meta.get('plan_name') or last_recharge_meta.get('plan_slug')

            usage_query = {
                'owner_id': owner_id,
                'audience': audience,
                'created_at': {'$gte': start_dt, '$lte': end_dt},
                'delta_credits': {'$lt': 0},
            }
            usage_docs = transaction_collection.find(usage_query, {'delta_credits': 1})
            total_usage = sum(abs(int(doc.get('delta_credits', 0) or 0)) for doc in usage_docs)

            rows.append({
                f'{audience}_id': owner_id,
                'name': user.get('name', ''),
                'email': user.get('email', ''),
                'current_balance_inr': float(current_balance),
                'last_recharge_date': last_recharge_date,
                'last_recharge_plan': last_recharge_plan,
                'total_usage_inr': float(total_usage),
            })

        rows.sort(key=lambda item: (-item.get('current_balance_inr', 0), item.get('name') or ''))
        return rows

    def _credit_lines_for_owner(self, owner_id, audience, start_dt, end_dt):
        wallet_service = self._get_wallet_service()
        tx_list = wallet_service.get_transactions(
            owner_id,
            audience,
            limit=100,
            kind="deductions",
        )

        recent_activity = [
            self._format_activity_row(tx)
            for tx in tx_list
            if int(tx.get("delta_credits", 0) or 0) < 0
        ][:50]

        total_amount = sum(int(row.get("credits_deducted", 0) or 0) for row in recent_activity)

        return [
            {
                "key": "deductions",
                "title": "Recent Credit Activity",
                "count": len(recent_activity),
                "total_amount_inr": self._round_money(total_amount),
                "lines": [
                    {
                        "id": row.get("id") or "",
                        "timestamp": row.get("timestamp"),
                        "activity_type": row.get("activity_type"),
                        "credits_deducted": row.get("credits_deducted"),
                        "remaining_balance": row.get("remaining_balance"),
                        "balance_after": row.get("balance_after"),
                        "amount_inr": row.get("credits_deducted"),
                    }
                    for row in recent_activity
                ],
            }
        ]

    def get_candidate_credit_summary(self, current_user, start_date=None, end_date=None):
        try:
            period_mode, period_start, period_end, error_response, error_status = self._resolve_timeline_window('month', start_date, end_date)
            if error_response:
                return error_response, error_status

            rows = self._credit_summary_rows('candidate', period_start, period_end)
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
            print(f"Error getting candidate credit summary: {str(e)}")
            print(traceback.format_exc())
            return {'error': 'Failed to get candidate credit summary'}, 500

    def get_candidate_credit_lines(self, current_user, candidate_id, start_date=None, end_date=None):
        try:
            period_mode, period_start, period_end, error_response, error_status = self._resolve_timeline_window('month', start_date, end_date)
            if error_response:
                return error_response, error_status

            try:
                candidate_doc = self.users_collection.find_one({'_id': ObjectId(candidate_id), 'user_type': 'candidate'}, {'name': 1, 'email': 1})
            except Exception:
                candidate_doc = self.users_collection.find_one({'_id': candidate_id, 'user_type': 'candidate'}, {'name': 1, 'email': 1})

            if not candidate_doc:
                return {'error': 'Candidate not found'}, 404

            candidate_id_str = str(candidate_doc.get('_id'))
            categories = self._credit_lines_for_owner(candidate_id_str, 'candidate', period_start, period_end)

            return {
                'timeline': {
                    'period_mode': period_mode,
                    'start_date': self._safe_iso(period_start),
                    'end_date': self._safe_iso(period_end),
                    'days': max(1, (period_end - period_start).days),
                },
                'candidate': {
                    'id': candidate_id_str,
                    'name': candidate_doc.get('name', 'Unknown Candidate'),
                    'email': candidate_doc.get('email', ''),
                },
                'categories': categories,
            }, 200
        except Exception as e:
            import traceback
            print(f"Error getting candidate credit lines: {str(e)}")
            print(traceback.format_exc())
            return {'error': 'Failed to get candidate credit lines'}, 500

    def get_recruiter_credit_summary(self, current_user, start_date=None, end_date=None):
        try:
            period_mode, period_start, period_end, error_response, error_status = self._resolve_timeline_window('month', start_date, end_date)
            if error_response:
                return error_response, error_status

            rows = self._credit_summary_rows('recruiter', period_start, period_end)
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
            print(f"Error getting recruiter credit summary: {str(e)}")
            print(traceback.format_exc())
            return {'error': 'Failed to get recruiter credit summary'}, 500

    def get_recruiter_credit_lines(self, current_user, recruiter_id, start_date=None, end_date=None):
        try:
            period_mode, period_start, period_end, error_response, error_status = self._resolve_timeline_window('month', start_date, end_date)
            if error_response:
                return error_response, error_status

            try:
                recruiter_doc = self.users_collection.find_one({'_id': ObjectId(recruiter_id), 'user_type': 'recruiter'}, {'name': 1, 'email': 1})
            except Exception:
                recruiter_doc = self.users_collection.find_one({'_id': recruiter_id, 'user_type': 'recruiter'}, {'name': 1, 'email': 1})

            if not recruiter_doc:
                return {'error': 'Recruiter not found'}, 404

            recruiter_id_str = str(recruiter_doc.get('_id'))
            categories = self._credit_lines_for_owner(recruiter_id_str, 'recruiter', period_start, period_end)

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
            }, 200
        except Exception as e:
            import traceback
            print(f"Error getting recruiter credit lines: {str(e)}")
            print(traceback.format_exc())
            return {'error': 'Failed to get recruiter credit lines'}, 500
