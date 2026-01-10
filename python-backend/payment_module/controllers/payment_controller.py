"""
Payment Controller - Handles payment initiation and status

Design Decisions:
1. Auth middleware injects user info
2. Validation before service calls
3. Clear error responses
4. No sensitive data in responses
"""

import logging
from flask import request
from typing import Tuple, Dict, Any

from ..services.payment_service import PaymentService

logger = logging.getLogger(__name__)


class PaymentController:
    """
    Controller for payment endpoints.

    Endpoints:
    - POST /payments/initiate: Start checkout flow
    - GET /payments/<payment_id>: Get payment status
    - GET /payments/history: Get payment history
    - POST /payments/<payment_id>/refund: Request refund (admin)
    """

    def __init__(self, db):
        """
        Initialize with database connection.

        Args:
            db: MongoDB database instance
        """
        self.payment_service = PaymentService(db)

    def initiate_payment(self, user_data: Dict[str, Any]) -> Tuple[dict, int]:
        """
        Initiate payment for a plan.

        Expects JSON body:
        {
            "plan_id": "string"
        }

        Args:
            user_data: Authenticated user data from middleware

        Returns:
            Tuple of (response_dict, status_code)
        """
        try:
            # Validate user is a recruiter/employer
            if user_data.get("user_type") != "recruiter":
                return {
                    "success": False,
                    "error": "Only employers can purchase plans",
                    "error_code": "unauthorized_user_type",
                }, 403

            # Get request body
            data = request.get_json()
            if not data:
                return {
                    "success": False,
                    "error": "Request body is required",
                    "error_code": "missing_body",
                }, 400

            plan_id = data.get("plan_id")
            if not plan_id:
                return {
                    "success": False,
                    "error": "plan_id is required",
                    "error_code": "missing_plan_id",
                }, 400

            # Extract user info
            employer_id = str(user_data.get("_id") or user_data.get("user_id"))
            employer_email = user_data.get("email", "")
            employer_name = user_data.get("name", "")

            # Initiate payment
            result = self.payment_service.initiate_payment(
                employer_id=employer_id,
                employer_email=employer_email,
                employer_name=employer_name,
                plan_id=plan_id,
            )

            if result["success"]:
                return {
                    "success": True,
                    "data": {
                        "checkout_url": result["checkout_url"],
                        "session_id": result["session_id"],
                    },
                }, 200
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Payment initiation failed"),
                    "error_code": result.get("error_code", "initiation_failed"),
                }, 400

        except Exception as e:
            logger.error(f"Payment initiation error: {str(e)}")
            return {
                "success": False,
                "error": "Internal server error",
                "error_code": "internal_error",
            }, 500

    def get_payment_status(
        self, payment_id: str, user_data: Dict[str, Any]
    ) -> Tuple[dict, int]:
        """
        Get payment status by ID.

        Args:
            payment_id: Payment ObjectId string
            user_data: Authenticated user data

        Returns:
            Tuple of (response_dict, status_code)
        """
        try:
            if not payment_id:
                return {
                    "success": False,
                    "error": "Payment ID is required",
                    "error_code": "missing_payment_id",
                }, 400

            payment = self.payment_service.get_payment_by_id(payment_id)

            if not payment:
                return {
                    "success": False,
                    "error": "Payment not found",
                    "error_code": "not_found",
                }, 404

            # Verify ownership
            employer_id = str(user_data.get("_id") or user_data.get("user_id"))
            if str(payment.employer_id) != employer_id:
                return {
                    "success": False,
                    "error": "Not authorized to view this payment",
                    "error_code": "unauthorized",
                }, 403

            return {"success": True, "data": payment.to_api_response()}, 200

        except Exception as e:
            logger.error(f"Error fetching payment {payment_id}: {str(e)}")
            return {
                "success": False,
                "error": "Failed to fetch payment",
                "error_code": "fetch_failed",
            }, 500

    def get_payment_history(self, user_data: Dict[str, Any]) -> Tuple[dict, int]:
        """
        Get payment history for authenticated user.

        Args:
            user_data: Authenticated user data

        Returns:
            Tuple of (response_dict, status_code)
        """
        try:
            employer_id = str(user_data.get("_id") or user_data.get("user_id"))

            # Get limit from query params
            limit = request.args.get("limit", 20, type=int)
            limit = min(limit, 100)  # Max 100

            payments = self.payment_service.get_employer_payments(
                employer_id=employer_id, limit=limit
            )

            return {
                "success": True,
                "data": {"payments": payments, "count": len(payments)},
            }, 200

        except Exception as e:
            logger.error(f"Error fetching payment history: {str(e)}")
            return {
                "success": False,
                "error": "Failed to fetch payment history",
                "error_code": "fetch_failed",
            }, 500

    def request_refund(
        self, payment_id: str, user_data: Dict[str, Any]
    ) -> Tuple[dict, int]:
        """
        Request refund for a payment.

        Expects optional JSON body:
        {
            "reason": "string",
            "amount_cents": number (optional, for partial refund)
        }

        Args:
            payment_id: Payment ObjectId string
            user_data: Authenticated user data

        Returns:
            Tuple of (response_dict, status_code)
        """
        try:
            if not payment_id:
                return {
                    "success": False,
                    "error": "Payment ID is required",
                    "error_code": "missing_payment_id",
                }, 400

            # Verify payment ownership
            payment = self.payment_service.get_payment_by_id(payment_id)

            if not payment:
                return {
                    "success": False,
                    "error": "Payment not found",
                    "error_code": "not_found",
                }, 404

            employer_id = str(user_data.get("_id") or user_data.get("user_id"))
            if str(payment.employer_id) != employer_id:
                return {
                    "success": False,
                    "error": "Not authorized to refund this payment",
                    "error_code": "unauthorized",
                }, 403

            # Get optional refund details
            data = request.get_json() or {}
            reason = data.get("reason", "requested_by_customer")
            amount_cents = data.get("amount_cents")

            result = self.payment_service.request_refund(
                payment_id=payment_id, reason=reason, amount_cents=amount_cents
            )

            if result["success"]:
                return {
                    "success": True,
                    "data": {
                        "refund_id": result.get("refund_id"),
                        "amount_refunded": result.get("amount", 0) / 100,
                        "status": result.get("status"),
                    },
                }, 200
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Refund failed"),
                    "error_code": result.get("error_code", "refund_failed"),
                }, 400

        except Exception as e:
            logger.error(f"Refund request error: {str(e)}")
            return {
                "success": False,
                "error": "Internal server error",
                "error_code": "internal_error",
            }, 500
