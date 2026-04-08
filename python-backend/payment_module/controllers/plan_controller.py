"""
Plan Controller - Handles plan-related API requests

Design Decisions:
1. Stateless controller (services injected)
2. Response formatting done here
3. Input validation at controller level
4. Admin endpoints separated (future)
"""

import logging
from typing import Tuple, Dict, Any

from ..services.plan_service import PlanService

logger = logging.getLogger(__name__)


class PlanController:
    """
    Controller for plan management endpoints.

    Endpoints:
    - GET /plans: List all active plans
    - GET /plans/<plan_id>: Get specific plan
    """

    def __init__(self, db):
        """
        Initialize with database connection.

        Args:
            db: MongoDB database instance
        """
        self.plan_service = PlanService(db)

    @staticmethod
    def _normalize_user_type(user_data: Dict[str, Any]) -> str:
        user_type = str(user_data.get("user_type") or "recruiter").strip().lower()
        if user_type == "student":
            return "candidate"
        return user_type

    def get_all_plans(self, user_data: Dict[str, Any]) -> Tuple[dict, int]:
        """
        Get all active plans.

        Returns:
            Tuple of (response_dict, status_code)
        """
        try:
            audience = self._normalize_user_type(user_data)
            if audience not in {"recruiter", "candidate"}:
                return {
                    "success": False,
                    "error": "Unsupported user type for plans",
                    "error_code": "unsupported_user_type",
                }, 403

            plans = self.plan_service.get_all_active_plans(audience=audience)

            return {"success": True, "data": {"plans": plans, "count": len(plans)}}, 200

        except Exception as e:
            logger.error(f"Error fetching plans: {str(e)}")
            return {
                "success": False,
                "error": "Failed to fetch plans",
                "error_code": "fetch_failed",
            }, 500

    def get_plan(self, plan_id: str, user_data: Dict[str, Any]) -> Tuple[dict, int]:
        """
        Get a specific plan by ID.

        Args:
            plan_id: Plan ObjectId string

        Returns:
            Tuple of (response_dict, status_code)
        """
        try:
            if not plan_id:
                return {
                    "success": False,
                    "error": "Plan ID is required",
                    "error_code": "missing_plan_id",
                }, 400

            audience = self._normalize_user_type(user_data)
            plan = self.plan_service.get_plan_by_id(plan_id, audience=audience)

            if not plan:
                return {
                    "success": False,
                    "error": "Plan not found",
                    "error_code": "not_found",
                }, 404

            return {"success": True, "data": plan.to_api_response()}, 200

        except Exception as e:
            logger.error(f"Error fetching plan {plan_id}: {str(e)}")
            return {
                "success": False,
                "error": "Failed to fetch plan",
                "error_code": "fetch_failed",
            }, 500

    def get_plan_by_slug(self, slug: str, user_data: Dict[str, Any]) -> Tuple[dict, int]:
        """
        Get a specific plan by slug.

        Args:
            slug: Plan slug (e.g., 'starter')

        Returns:
            Tuple of (response_dict, status_code)
        """
        try:
            if not slug:
                return {
                    "success": False,
                    "error": "Plan slug is required",
                    "error_code": "missing_slug",
                }, 400

            audience = self._normalize_user_type(user_data)
            plan = self.plan_service.get_plan_by_slug(slug, audience=audience)

            if not plan:
                return {
                    "success": False,
                    "error": "Plan not found",
                    "error_code": "not_found",
                }, 404

            return {"success": True, "data": plan.to_api_response()}, 200

        except Exception as e:
            logger.error(f"Error fetching plan by slug {slug}: {str(e)}")
            return {
                "success": False,
                "error": "Failed to fetch plan",
                "error_code": "fetch_failed",
            }, 500
