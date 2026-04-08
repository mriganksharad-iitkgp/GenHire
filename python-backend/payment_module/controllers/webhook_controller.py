"""
Webhook Controller - Handles Razorpay webhook events

Design Decisions:
1. Raw body parsing for signature verification
2. Always returns 200 to Razorpay (acknowledge receipt)
3. Idempotent processing (duplicate events are OK)
4. Detailed logging for debugging
"""

import logging
from flask import request
from typing import Tuple

from ..services.payment_service import PaymentService

logger = logging.getLogger(__name__)


class WebhookController:
    """
    Controller for Razorpay webhook endpoint.

    CRITICAL SECURITY:
    - Always verify webhook signatures
    - Use raw request body (not parsed JSON)
    - Never trust frontend payment confirmations
    """

    def __init__(self, db):
        """
        Initialize with database connection.

        Args:
            db: MongoDB database instance
        """
        self.payment_service = PaymentService(db)

    def handle_razorpay_webhook(self) -> Tuple[dict, int]:
        """
        Process incoming Razorpay webhook.

        Important: Must use raw request body for signature verification.

        Returns:
            Tuple of (response_dict, status_code)
        """
        try:
            # Get raw body for signature verification
            payload = request.get_data()

            # Get Razorpay signature header
            signature = request.headers.get("X-Razorpay-Signature")

            if not signature:
                logger.warning("Webhook received without signature")
                return {"success": False, "error": "Missing signature"}, 400

            # Process webhook
            result = self.payment_service.process_webhook(
                payload=payload, signature=signature
            )

            # Always return 200 to Razorpay to acknowledge receipt
            # Even if processing failed, we don't want Razorpay to retry
            # unless it's a signature issue
            if result.get("error_code") == "invalid_signature":
                logger.error("Invalid webhook signature")
                return {"success": False, "error": "Invalid signature"}, 400

            # Log processing result
            if result["success"]:
                logger.info(
                    f"Webhook processed successfully: {result.get('message', 'OK')}"
                )
            else:
                logger.warning(
                    f"Webhook processing issue: {result.get('error', 'Unknown')}"
                )

            # Return 200 to acknowledge receipt
            return {"success": True, "received": True}, 200

        except Exception as e:
            logger.error(f"Webhook error: {str(e)}")
            # Still return 200 to prevent Razorpay retries for internal errors
            # We'll have logs to debug
            return {
                "success": True,
                "received": True,
                "note": "Processing error logged",
            }, 200
