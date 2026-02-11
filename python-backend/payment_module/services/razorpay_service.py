"""
Razorpay Service - Handles all Razorpay API interactions

Design Decisions:
1. Centralized Razorpay API calls for maintainability
2. Webhook signature verification for security
3. Order creation for payment handling
4. Idempotency for safe retries
5. Customer creation for better dashboard UX
6. Metadata attachment for debugging
"""

import razorpay
import hmac
import hashlib
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import uuid

from ..config.settings import PaymentConfig

# Configure logging
logger = logging.getLogger(__name__)


class RazorpayService:
    """
    Service class for Razorpay API operations.

    This class encapsulates all Razorpay interactions:
    - Creating orders
    - Verifying webhook signatures
    - Processing refunds
    - Managing customers
    """

    def __init__(self):
        """Initialize Razorpay with API keys"""
        self.key_id = PaymentConfig.RAZORPAY_KEY_ID
        self.key_secret = PaymentConfig.RAZORPAY_KEY_SECRET
        self.webhook_secret = PaymentConfig.RAZORPAY_WEBHOOK_SECRET

        if not self.key_id or not self.key_secret:
            logger.error("Razorpay API keys not configured")
            raise ValueError("RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are required")

        self.client = razorpay.Client(auth=(self.key_id, self.key_secret))

    def create_order(
        self,
        employer_id: str,
        employer_email: str,
        plan_id: str,
        plan_name: str,
        price_paise: int,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a Razorpay Order for plan purchase.

        Args:
            employer_id: Internal user ID
            employer_email: Email for receipts
            plan_id: Internal plan ID
            plan_name: Plan display name
            price_paise: Amount in paise (smallest currency unit)
            idempotency_key: For safe retries

        Returns:
            Dict with order_id and order details
        """
        try:
            # Generate idempotency key if not provided (must be ≤40 chars for Razorpay receipt)
            if not idempotency_key:
                idempotency_key = f"ord_{uuid.uuid4().hex[:32]}"

            # Ensure receipt is ≤40 characters (Razorpay limit)
            receipt = (
                idempotency_key[:35] if len(idempotency_key) > 40 else idempotency_key
            )

            # Create order
            order_data = {
                "amount": price_paise,
                "currency": PaymentConfig.CURRENCY.upper(),
                "receipt": receipt,
                "notes": {
                    "employer_id": employer_id,
                    "employer_email": employer_email,
                    "plan_id": plan_id,
                    "plan_name": plan_name,
                    "idempotency_key": idempotency_key,
                },
            }

            order = self.client.order.create(data=order_data)

            logger.info(
                f"Created Razorpay order {order['id']} for employer {employer_id}"
            )

            return {
                "success": True,
                "order_id": order["id"],
                "amount": order["amount"],
                "currency": order["currency"],
                "key_id": self.key_id,
                "idempotency_key": idempotency_key,
                "order": order,
            }

        except razorpay.errors.BadRequestError as e:
            logger.error(f"Razorpay bad request error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "bad_request",
            }

        except Exception as e:
            logger.error(f"Razorpay error creating order: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "order_creation_failed",
            }

    def verify_payment_signature(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> bool:
        """
        Verify Razorpay payment signature.

        CRITICAL SECURITY:
        - Never trust unverified payments
        - Signature prevents spoofed confirmations

        Args:
            razorpay_order_id: Order ID from Razorpay
            razorpay_payment_id: Payment ID from Razorpay
            razorpay_signature: Signature from Razorpay

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            params_dict = {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            }

            self.client.utility.verify_payment_signature(params_dict)
            logger.info(f"Verified payment signature for order {razorpay_order_id}")
            return True

        except razorpay.errors.SignatureVerificationError as e:
            logger.error(f"Invalid payment signature: {str(e)}")
            return False

    def verify_webhook_signature(
        self, payload: bytes, signature: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify Razorpay webhook signature.

        CRITICAL SECURITY:
        - Never trust unverified webhooks
        - Signature prevents spoofed events

        Args:
            payload: Raw request body (bytes)
            signature: X-Razorpay-Signature header value

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Razorpay uses HMAC-SHA256 for webhook signatures
            expected_signature = hmac.new(
                self.webhook_secret.encode("utf-8"),
                payload,
                hashlib.sha256,
            ).hexdigest()

            if hmac.compare_digest(expected_signature, signature):
                logger.info("Verified webhook signature")
                return True, None
            else:
                logger.error("Invalid webhook signature")
                return False, "Invalid signature"

        except Exception as e:
            logger.error(f"Webhook signature verification error: {str(e)}")
            return False, str(e)

    def fetch_payment(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch payment details from Razorpay.

        Args:
            payment_id: Razorpay payment ID

        Returns:
            Payment data or None if not found
        """
        try:
            payment = self.client.payment.fetch(payment_id)
            return payment

        except Exception as e:
            logger.error(f"Error fetching payment {payment_id}: {str(e)}")
            return None

    def fetch_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch order details from Razorpay.

        Args:
            order_id: Razorpay order ID

        Returns:
            Order data or None if not found
        """
        try:
            order = self.client.order.fetch(order_id)
            return order

        except Exception as e:
            logger.error(f"Error fetching order {order_id}: {str(e)}")
            return None

    def process_refund(
        self,
        payment_id: str,
        amount_paise: Optional[int] = None,
        notes: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Process a refund for a payment.

        Args:
            payment_id: Razorpay payment ID
            amount_paise: Amount to refund in paise (None for full refund)
            notes: Additional notes for the refund

        Returns:
            Dict with refund details or error
        """
        try:
            refund_data = {}

            if amount_paise:
                refund_data["amount"] = amount_paise

            if notes:
                refund_data["notes"] = notes

            refund = self.client.payment.refund(payment_id, refund_data)

            logger.info(f"Processed refund {refund['id']} for payment {payment_id}")

            return {
                "success": True,
                "refund_id": refund["id"],
                "amount": refund["amount"],
                "status": refund["status"],
                "payment_id": refund["payment_id"],
            }

        except razorpay.errors.BadRequestError as e:
            logger.error(f"Refund error for {payment_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "bad_request",
            }

        except Exception as e:
            logger.error(f"Refund error for {payment_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "refund_failed",
            }

    def fetch_refund(self, payment_id: str, refund_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch refund details from Razorpay.

        Args:
            payment_id: Razorpay payment ID
            refund_id: Razorpay refund ID

        Returns:
            Refund data or None if not found
        """
        try:
            refund = self.client.payment.refund_fetch(payment_id, refund_id)
            return refund

        except Exception as e:
            logger.error(f"Error fetching refund {refund_id}: {str(e)}")
            return None

    def capture_payment(self, payment_id: str, amount_paise: int) -> Dict[str, Any]:
        """
        Capture an authorized payment.

        Args:
            payment_id: Razorpay payment ID
            amount_paise: Amount to capture in paise

        Returns:
            Dict with capture result
        """
        try:
            payment = self.client.payment.capture(payment_id, amount_paise)

            logger.info(f"Captured payment {payment_id}")

            return {
                "success": True,
                "payment": payment,
            }

        except Exception as e:
            logger.error(f"Capture error for {payment_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "capture_failed",
            }
