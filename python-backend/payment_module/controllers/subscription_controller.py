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

    @staticmethod
    def _normalize_user_type(user_data: Dict[str, Any]) -> str:
        user_type = str(user_data.get("user_type") or "recruiter").strip().lower()
        if user_type == "student":
            return "candidate"
        return user_type

    def get_current_subscription(self, user_data: Dict[str, Any]) -> Tuple[dict, int]:
        """
        Get current active subscription for authenticated user.

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

            subscription = self.subscription_service.get_active_subscription(
                employer_id,
                audience=audience,
            )

            if not subscription:
                return {
                    "success": True,
                    "data": {
                        "has_subscription": False,
                        "subscription": None,
                        "message": "No active subscription",
                    },
                }, 200

            return {
                "success": True,
                "data": {
                    "has_subscription": True,
                    "subscription": subscription.to_api_response(),
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
        Decrement interview count for an employer.

        This should be called when an interview is initiated.
        Uses atomic operations to prevent race conditions.

        Args:
            user_data: Authenticated user data

        Returns:
            Tuple of (response_dict, status_code)
        """
        try:
            audience = self._normalize_user_type(user_data)
            if audience != "recruiter":
                return {
                    "success": False,
                    "error": "Only employers can use interviews",
                    "error_code": "unauthorized_user_type",
                }, 403

            employer_id = str(user_data.get("_id") or user_data.get("user_id"))

            result = self.subscription_service.use_interview(
                employer_id,
                audience=audience,
            )

            if result["success"]:
                return {
                    "success": True,
                    "data": {
                        "interviews_remaining": result["interviews_remaining"],
                        "interviews_used": result["interviews_used"],
                        "is_unlimited": result.get("is_unlimited", False),
                    },
                }, 200
            else:
                # Determine appropriate status code
                error_code = result.get("error_code", "unknown")
                status_code = 402 if error_code == "limit_exceeded" else 400
                if error_code == "no_subscription":
                    status_code = 402  # Payment Required

                return {
                    "success": False,
                    "error": result.get("error", "Failed to use interview"),
                    "error_code": error_code,
                }, status_code

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
                    "data": {"can_interview": False, "can_practice": False, "reason": "unsupported_user_type"},
                }, 200

            employer_id = str(user_data.get("_id") or user_data.get("user_id"))

            subscription = self.subscription_service.get_active_subscription(
                employer_id,
                audience=audience,
            )

            if not subscription:
                return {
                    "success": True,
                    "data": {
                        "can_interview": audience == "recruiter" and False,
                        "can_practice": audience == "candidate" and False,
                        "reason": "no_subscription",
                        "message": "Please purchase a plan to continue",
                    },
                }, 200

            if not subscription.can_use_interview:
                reason = "expired" if not subscription.is_active else "limit_reached"
                return {
                    "success": True,
                    "data": {
                        "can_interview": audience == "recruiter" and False,
                        "can_practice": audience == "candidate" and False,
                        "reason": reason,
                        "message": (
                            "Please purchase a new plan"
                            if reason == "expired"
                            else "Interview limit reached"
                        ),
                    },
                }, 200

            return {
                "success": True,
                "data": {
                    "can_interview": audience == "recruiter",
                    "can_practice": audience == "candidate",
                    "interviews_remaining": (
                        subscription.interviews_remaining
                        if not subscription.is_unlimited
                        else "unlimited"
                    ),
                    "expires_at": (
                        subscription.expires_at.isoformat()
                        if subscription.expires_at
                        else None
                    ),
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

            success = self.subscription_service.cancel_subscription(
                employer_id=employer_id,
                reason=reason,
                audience=audience,
            )

            if success:
                return {
                    "success": True,
                    "data": {"message": "Subscription cancelled successfully"},
                }, 200
            else:
                return {
                    "success": False,
                    "error": "No active subscription to cancel",
                    "error_code": "no_subscription",
                }, 404

        except Exception as e:
            logger.error(f"Error cancelling subscription: {str(e)}")
            return {
                "success": False,
                "error": "Failed to cancel subscription",
                "error_code": "cancel_failed",
            }, 500
