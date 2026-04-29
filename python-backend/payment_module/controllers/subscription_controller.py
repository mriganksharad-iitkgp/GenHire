"""
Subscription Controller - Handles subscription queries and interview usage

Design Decisions:
1. Interview usage is atomic to prevent race conditions
2. Subscription expiry checked on every access
3. Clear feedback on limit states
"""

import logging
from flask import request
from typing import Tuple, Dict, Any

from ..services.subscription_service import SubscriptionService
from ..services.plan_service import PlanService
from ..services.wallet_service import WalletService

logger = logging.getLogger(__name__)


class SubscriptionController:
    """
    Controller for subscription endpoints.

    Endpoints:
    - GET /subscriptions/me: Get current subscription
    - GET /subscriptions/history: Get subscription history
    - POST /interviews/use: Decrement interview count
    - GET /subscriptions/check: Quick validity check
    """

    def __init__(self, db):
        """
        Initialize with database connection.

        Args:
            db: MongoDB database instance
        """
        self.subscription_service = SubscriptionService(db)
        self.plan_service = PlanService(db)
        self.wallet_service = WalletService(db)

    @staticmethod
    def _normalize_user_type(user_data: Dict[str, Any]) -> str:
        user_type = str(user_data.get("user_type") or "recruiter").strip().lower()
        if user_type == "student":
            return "candidate"
        return user_type

    def get_current_subscription(self, user_data: Dict[str, Any]) -> Tuple[dict, int]:
        """Return wallet summary in a backward-compatible response envelope."""
        try:
            audience = self._normalize_user_type(user_data)
            if audience not in {"recruiter", "candidate"}:
                return {
                    "success": False,
                    "error": "Unsupported user type for subscriptions",
                    "error_code": "unauthorized_user_type",
                }, 403

            employer_id = str(user_data.get("_id") or user_data.get("user_id"))
            wallet_summary = self.wallet_service.get_wallet_summary(
                owner_id=employer_id,
                audience=audience,
            )
            latest_pack = wallet_summary.get("latest_recharge") or {}

            subscription_like = {
                "plan": {
                    "name": latest_pack.get("plan_name"),
                    "slug": latest_pack.get("plan_slug"),
                    "price": (
                        float(latest_pack.get("amount_paise", 0) or 0) / 100.0
                    ),
                    "currency": "INR",
                    "monthly_credits": int(latest_pack.get("recharge_credits", 0) or 0),
                },
                "status": "active",
                "credits_balance": int(wallet_summary.get("credits_balance", 0) or 0),
                "credits_allocated": int(wallet_summary.get("total_credited", 0) or 0),
                "credits_remaining": int(wallet_summary.get("credits_balance", 0) or 0),
                "credits_used": int(wallet_summary.get("total_debited", 0) or 0),
                "total_credited": int(wallet_summary.get("total_credited", 0) or 0),
                "total_debited": int(wallet_summary.get("total_debited", 0) or 0),
                "expires_at": None,
                "is_unlimited": False,
                "is_active": True,
                "can_use_interview": int(wallet_summary.get("credits_balance", 0) or 0) > 0,
            }

            return {
                "success": True,
                "data": {
                    "has_subscription": True,
                    "subscription": subscription_like,
                    "wallet": wallet_summary,
                },
            }, 200

        except Exception as e:
            logger.error(f"Error fetching subscription: {str(e)}")
            return {
                "success": False,
                "error": "Failed to fetch subscription",
                "error_code": "fetch_failed",
            }, 500

    def get_subscription_history(self, user_data: Dict[str, Any]) -> Tuple[dict, int]:
        """
        Get subscription history for authenticated user.

        Args:
            user_data: Authenticated user data

        Returns:
            Tuple of (response_dict, status_code)
        """
        try:
            employer_id = str(user_data.get("_id") or user_data.get("user_id"))
            audience = self._normalize_user_type(user_data)

            limit = request.args.get("limit", 10, type=int)
            limit = min(limit, 50)

            subscriptions = self.subscription_service.get_subscription_history(
                employer_id=employer_id, limit=limit, audience=audience
            )

            return {
                "success": True,
                "data": {"subscriptions": subscriptions, "count": len(subscriptions)},
            }, 200

        except Exception as e:
            logger.error(f"Error fetching subscription history: {str(e)}")
            return {
                "success": False,
                "error": "Failed to fetch history",
                "error_code": "fetch_failed",
            }, 500

    def use_interview(self, user_data: Dict[str, Any]) -> Tuple[dict, int]:
        """
        Deprecated legacy endpoint.

        Args:
            user_data: Authenticated user data

        Returns:
            Tuple of (response_dict, status_code)
        """
        try:
            return {
                "success": False,
                "error": "Manual interview credit deduction is deprecated. Credits are deducted by the practice, AI JD, and real interview flows.",
                "error_code": "deprecated_endpoint",
            }, 410

        except Exception as e:
            logger.error(f"Error using interview: {str(e)}")
            return {
                "success": False,
                "error": "Internal server error",
                "error_code": "internal_error",
            }, 500

    def check_subscription_validity(
        self, user_data: Dict[str, Any]
    ) -> Tuple[dict, int]:
        """
        Quick check if employer can conduct interviews.

        Lightweight endpoint for frontend validation.

        Args:
            user_data: Authenticated user data

        Returns:
            Tuple of (response_dict, status_code)
        """
        try:
            audience = self._normalize_user_type(user_data)
            if audience not in {"recruiter", "candidate"}:
                return {
                    "success": True,
                    "data": {
                        "can_interview": False,
                        "can_practice": False,
                        "reason": "unsupported_user_type",
                    },
                }, 200

            employer_id = str(user_data.get("_id") or user_data.get("user_id"))

            wallet_summary = self.wallet_service.get_wallet_summary(
                owner_id=employer_id,
                audience=audience,
            )
            can_use = int(wallet_summary.get("credits_balance", 0) or 0) > 0

            return {
                "success": True,
                "data": {
                    "can_interview": audience == "recruiter" and can_use,
                    "can_practice": audience == "candidate" and can_use,
                    "credits_remaining": int(wallet_summary.get("credits_balance", 0) or 0),
                    "credits_used": int(wallet_summary.get("total_debited", 0) or 0),
                    "credits_allocated": int(wallet_summary.get("total_credited", 0) or 0),
                    "interviews_remaining": int(wallet_summary.get("credits_balance", 0) or 0),
                    "expires_at": None,
                },
            }, 200

        except Exception as e:
            logger.error(f"Error checking validity: {str(e)}")
            return {
                "success": False,
                "error": "Validation check failed",
                "error_code": "check_failed",
            }, 500

    def cancel_subscription(self, user_data: Dict[str, Any]) -> Tuple[dict, int]:
        """
        Cancel current active subscription.

        Note: Does not trigger automatic refund.

        Args:
            user_data: Authenticated user data

        Returns:
            Tuple of (response_dict, status_code)
        """
        try:
            audience = self._normalize_user_type(user_data)
            if audience not in {"recruiter", "candidate"}:
                return {
                    "success": False,
                    "error": "Unsupported user type for subscriptions",
                    "error_code": "unauthorized_user_type",
                }, 403

            employer_id = str(user_data.get("_id") or user_data.get("user_id"))

            # Get reason from request body
            data = request.get_json() or {}
            reason = data.get("reason", "user_requested")

            return {
                "success": True,
                "data": {
                    "message": "Recharge wallet model is active. Cancellation is not required.",
                    "reason": reason,
                },
            }, 200

        except Exception as e:
            logger.error(f"Error cancelling subscription: {str(e)}")
            return {
                "success": False,
                "error": "Failed to cancel subscription",
                "error_code": "cancel_failed",
            }, 500

    def get_credit_transactions(self, user_data: Dict[str, Any]) -> Tuple[dict, int]:
        try:
            audience = self._normalize_user_type(user_data)
            owner_id = str(user_data.get("_id") or user_data.get("user_id"))
            limit = request.args.get("limit", 20, type=int)
            kind = request.args.get("kind", "all")
            transactions = self.wallet_service.get_transactions(
                owner_id, audience, limit, kind=kind
            )
            return {
                "success": True,
                "data": {
                    "transactions": transactions,
                    "count": len(transactions),
                },
            }, 200
        except Exception as e:
            logger.error(f"Error fetching credit transactions: {str(e)}")
            return {
                "success": False,
                "error": "Failed to fetch transactions",
                "error_code": "fetch_failed",
            }, 500
