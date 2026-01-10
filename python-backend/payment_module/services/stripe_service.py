"""
Stripe Service - Handles all Stripe API interactions

Design Decisions:
1. Centralized Stripe API calls for maintainability
2. Webhook signature verification for security
3. Checkout Session for PCI compliance (vs direct charges)
4. Idempotency keys for safe retries
5. Customer creation for better Stripe dashboard UX
6. Metadata attachment for debugging
"""

import stripe
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import uuid

from ..config.settings import PaymentConfig

# Configure logging
logger = logging.getLogger(__name__)


class StripeService:
    """
    Service class for Stripe API operations.

    This class encapsulates all Stripe interactions:
    - Creating checkout sessions
    - Verifying webhook signatures
    - Processing refunds
    - Managing customers
    """

    def __init__(self):
        """Initialize Stripe with API key"""
        stripe.api_key = PaymentConfig.STRIPE_SECRET_KEY
        self.webhook_secret = PaymentConfig.STRIPE_WEBHOOK_SECRET

        if not stripe.api_key:
            logger.error("Stripe API key not configured")
            raise ValueError("STRIPE_SECRET_KEY is required")

    def create_checkout_session(
        self,
        employer_id: str,
        employer_email: str,
        plan_id: str,
        plan_name: str,
        price_cents: int,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a Stripe Checkout Session for plan purchase.

        Why Checkout Session over PaymentIntent?
        - Hosted payment page (PCI compliant)
        - Built-in card validation
        - Automatic receipt emails
        - Easy refund handling

        Args:
            employer_id: Internal user ID
            employer_email: Email for receipts
            plan_id: Internal plan ID
            plan_name: Plan display name
            price_cents: Amount in cents
            idempotency_key: For safe retries

        Returns:
            Dict with session_id and checkout_url
        """
        try:
            # Generate idempotency key if not provided
            if not idempotency_key:
                idempotency_key = (
                    f"checkout_{employer_id}_{plan_id}_{uuid.uuid4().hex[:8]}"
                )

            # Create checkout session
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": PaymentConfig.CURRENCY,
                            "unit_amount": price_cents,
                            "product_data": {
                                "name": plan_name,
                                "description": f"Hiring Plan - {plan_name}",
                            },
                        },
                        "quantity": 1,
                    }
                ],
                mode="payment",
                success_url=PaymentConfig.PAYMENT_SUCCESS_URL
                + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=PaymentConfig.PAYMENT_CANCEL_URL,
                customer_email=employer_email,
                client_reference_id=employer_id,  # Links session to our user
                metadata={
                    "employer_id": employer_id,
                    "plan_id": plan_id,
                    "plan_name": plan_name,
                    "idempotency_key": idempotency_key,
                },
                expires_at=int(
                    (datetime.utcnow().timestamp()) + 30 * 60
                ),  # 30 min expiry
                idempotency_key=idempotency_key,
            )

            logger.info(
                f"Created checkout session {session.id} for employer {employer_id}"
            )

            return {
                "success": True,
                "session_id": session.id,
                "checkout_url": session.url,
                "idempotency_key": idempotency_key,
            }

        except stripe.error.IdempotencyError as e:
            # Same idempotency key with different params
            logger.warning(f"Idempotency conflict: {str(e)}")
            return {
                "success": False,
                "error": "Duplicate request with conflicting parameters",
                "error_code": "idempotency_conflict",
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout: {str(e)}")
            return {
                "success": False,
                "error": str(e.user_message or e),
                "error_code": e.code,
            }

    def verify_webhook_signature(
        self, payload: bytes, signature: str
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Verify Stripe webhook signature and parse event.

        CRITICAL SECURITY:
        - Never trust unverified webhooks
        - Signature prevents spoofed events
        - Use raw payload bytes (not parsed JSON)

        Args:
            payload: Raw request body (bytes)
            signature: Stripe-Signature header value

        Returns:
            Tuple of (is_valid, event_dict, error_message)
        """
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )

            logger.info(f"Verified webhook: {event['type']} - {event['id']}")

            return True, event, None

        except ValueError as e:
            logger.error(f"Invalid webhook payload: {str(e)}")
            return False, None, "Invalid payload"

        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {str(e)}")
            return False, None, "Invalid signature"

    def retrieve_checkout_session(
        self, session_id: str, expand: list = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve checkout session details from Stripe.

        Args:
            session_id: Stripe session ID
            expand: List of fields to expand (e.g., ['payment_intent', 'customer'])

        Returns:
            Session data or None if not found
        """
        try:
            expand = expand or ["payment_intent", "customer"]
            session = stripe.checkout.Session.retrieve(session_id, expand=expand)
            return session

        except stripe.error.StripeError as e:
            logger.error(f"Error retrieving session {session_id}: {str(e)}")
            return None

    def process_refund(
        self,
        charge_id: str,
        amount_cents: Optional[int] = None,
        reason: str = "requested_by_customer",
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a refund for a charge.

        Args:
            charge_id: Stripe charge ID
            amount_cents: Amount to refund (None for full refund)
            reason: Refund reason for Stripe
            idempotency_key: For safe retries

        Returns:
            Dict with refund details or error
        """
        try:
            if not idempotency_key:
                idempotency_key = f"refund_{charge_id}_{uuid.uuid4().hex[:8]}"

            refund_params = {
                "charge": charge_id,
                "reason": reason,
            }

            if amount_cents:
                refund_params["amount"] = amount_cents

            refund = stripe.Refund.create(
                **refund_params, idempotency_key=idempotency_key
            )

            logger.info(f"Processed refund {refund.id} for charge {charge_id}")

            return {
                "success": True,
                "refund_id": refund.id,
                "amount": refund.amount,
                "status": refund.status,
            }

        except stripe.error.StripeError as e:
            logger.error(f"Refund error for {charge_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e.user_message or e),
                "error_code": getattr(e, "code", "unknown"),
            }

    def create_or_get_customer(
        self, email: str, name: str, employer_id: str
    ) -> Optional[str]:
        """
        Create or retrieve Stripe customer.

        Args:
            email: Customer email
            name: Customer name
            employer_id: Internal user ID

        Returns:
            Stripe customer ID or None
        """
        try:
            # Search for existing customer
            customers = stripe.Customer.search(query=f'email:"{email}"')

            if customers.data:
                return customers.data[0].id

            # Create new customer
            customer = stripe.Customer.create(
                email=email, name=name, metadata={"employer_id": employer_id}
            )

            return customer.id

        except stripe.error.StripeError as e:
            logger.error(f"Customer error for {email}: {str(e)}")
            return None

    def retrieve_payment_intent(
        self, payment_intent_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve PaymentIntent details.

        Args:
            payment_intent_id: Stripe PaymentIntent ID

        Returns:
            PaymentIntent data or None
        """
        try:
            return stripe.PaymentIntent.retrieve(payment_intent_id)
        except stripe.error.StripeError as e:
            logger.error(
                f"Error retrieving payment intent {payment_intent_id}: {str(e)}"
            )
            return None
