"""
Payment Service - Orchestrates payment flow and business logic

Design Decisions:
1. Single responsibility: coordinates between Stripe and DB
2. Never trusts frontend payment status
3. Idempotent webhook handling
4. Full payment lifecycle tracking
5. Refund support with status updates
"""

import logging
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from bson import ObjectId
from pymongo import ReturnDocument

from ..models.payment import Payment, PaymentSchema, PaymentStatus
from ..models.plan import Plan
from ..services.stripe_service import StripeService
from ..services.subscription_service import SubscriptionService
from ..services.plan_service import PlanService
from ..config.settings import PaymentConfig

logger = logging.getLogger(__name__)


class PaymentService:
    """
    Central service for payment orchestration.

    Handles:
    - Payment initiation
    - Webhook processing
    - Refunds
    - Payment status tracking
    """

    def __init__(self, db):
        """
        Initialize with database connection and dependent services.

        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.collection = db[PaymentSchema.COLLECTION_NAME]
        self._ensure_indexes()

        # Initialize dependent services
        self.stripe_service = StripeService()
        self.subscription_service = SubscriptionService(db)
        self.plan_service = PlanService(db)

    def _ensure_indexes(self):
        """Create indexes if they don't exist"""
        try:
            PaymentSchema.create_indexes(self.db)
            logger.info("Payment indexes ensured")
        except Exception as e:
            logger.error(f"Error creating payment indexes: {str(e)}")

    def initiate_payment(
        self, employer_id: str, employer_email: str, employer_name: str, plan_id: str
    ) -> Dict[str, Any]:
        """
        Initiate payment for a plan.

        Flow:
        1. Validate plan exists
        2. Generate idempotency key
        3. Create Stripe checkout session
        4. Create pending payment record
        5. Create pending subscription
        6. Return checkout URL

        Args:
            employer_id: User ID
            employer_email: User email for receipts
            employer_name: User name
            plan_id: Plan to purchase

        Returns:
            Dict with checkout_url or error
        """
        try:
            # 1. Validate plan
            plan = self.plan_service.get_plan_by_id(plan_id)
            if not plan:
                return {
                    "success": False,
                    "error": "Plan not found or inactive",
                    "error_code": "invalid_plan",
                }

            # 2. Generate idempotency key
            idempotency_key = f"pay_{employer_id}_{plan_id}_{uuid.uuid4().hex[:8]}"

            # 3. Create Stripe checkout session
            checkout_result = self.stripe_service.create_checkout_session(
                employer_id=employer_id,
                employer_email=employer_email,
                plan_id=str(plan._id),
                plan_name=plan.name,
                price_cents=plan.price_cents,
                idempotency_key=idempotency_key,
            )

            if not checkout_result["success"]:
                return checkout_result

            stripe_session_id = checkout_result["session_id"]

            # 4. Create pending payment record
            payment = Payment(
                employer_id=ObjectId(employer_id),
                plan_id=plan._id,
                amount_cents=plan.price_cents,
                currency=PaymentConfig.CURRENCY,
                status=PaymentStatus.PENDING,
                stripe_session_id=stripe_session_id,
                idempotency_key=idempotency_key,
                metadata={
                    "employer_name": employer_name,
                    "employer_email": employer_email,
                    "plan_name": plan.name,
                },
            )

            payment_result = self.collection.insert_one(payment.to_dict())
            payment._id = payment_result.inserted_id

            # 5. Create pending subscription
            subscription = self.subscription_service.create_pending_subscription(
                employer_id=employer_id, plan=plan, stripe_session_id=stripe_session_id
            )

            if subscription:
                # Link subscription to payment
                self.collection.update_one(
                    {"_id": payment._id},
                    {"$set": {"subscription_id": subscription._id}},
                )

            logger.info(f"Payment initiated: {payment._id} for employer {employer_id}")

            return {
                "success": True,
                "checkout_url": checkout_result["checkout_url"],
                "session_id": stripe_session_id,
                "payment_id": str(payment._id),
            }

        except Exception as e:
            logger.error(f"Payment initiation error: {str(e)}")
            return {
                "success": False,
                "error": "Failed to initiate payment",
                "error_code": "initiation_failed",
            }

    def process_webhook(self, payload: bytes, signature: str) -> Dict[str, Any]:
        """
        Process Stripe webhook event.

        Handles:
        - checkout.session.completed: Payment success
        - checkout.session.expired: Payment timeout
        - payment_intent.payment_failed: Payment failure
        - charge.refunded: Refund processed

        Args:
            payload: Raw webhook payload
            signature: Stripe signature header

        Returns:
            Dict with processing result
        """
        try:
            # 1. Verify webhook signature
            is_valid, event, error = self.stripe_service.verify_webhook_signature(
                payload, signature
            )

            if not is_valid:
                logger.warning(f"Webhook signature verification failed: {error}")
                return {
                    "success": False,
                    "error": error,
                    "error_code": "invalid_signature",
                }

            event_type = event["type"]
            event_data = event["data"]["object"]

            logger.info(f"Processing webhook: {event_type}")

            # 2. Route to appropriate handler
            if event_type == "checkout.session.completed":
                return self._handle_checkout_completed(event_data)

            elif event_type == "checkout.session.expired":
                return self._handle_checkout_expired(event_data)

            elif event_type == "payment_intent.payment_failed":
                return self._handle_payment_failed(event_data)

            elif event_type == "charge.refunded":
                return self._handle_refund(event_data)

            else:
                # Acknowledge unhandled events
                logger.info(f"Unhandled webhook event type: {event_type}")
                return {"success": True, "message": "Event acknowledged"}

        except Exception as e:
            logger.error(f"Webhook processing error: {str(e)}")
            return {
                "success": False,
                "error": "Webhook processing failed",
                "error_code": "processing_failed",
            }

    def _handle_checkout_completed(
        self, session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle successful checkout completion.

        Critical: This is where payment becomes "official"
        - Never trust frontend success redirects
        - Only this webhook confirms payment

        Args:
            session_data: Stripe session object

        Returns:
            Processing result
        """
        try:
            session_id = session_data["id"]
            payment_status = session_data.get("payment_status")

            # Only process if payment was actually paid
            if payment_status != "paid":
                logger.warning(
                    f"Checkout completed but payment status is {payment_status}"
                )
                return {"success": True, "message": "Payment not yet confirmed"}

            # Check for duplicate processing (idempotency)
            existing_payment = self.collection.find_one(
                {
                    "stripe_session_id": session_id,
                    "status": PaymentStatus.SUCCEEDED.value,
                }
            )

            if existing_payment:
                logger.info(
                    f"Duplicate webhook for session {session_id}, already processed"
                )
                return {"success": True, "message": "Already processed"}

            # Get full session details from Stripe
            full_session = self.stripe_service.retrieve_checkout_session(session_id)
            if not full_session:
                logger.error(f"Could not retrieve session {session_id}")
                return {"success": False, "error": "Session retrieval failed"}

            # Extract IDs
            payment_intent = full_session.get("payment_intent")
            payment_intent_id = (
                payment_intent.id if hasattr(payment_intent, "id") else payment_intent
            )

            charge_id = None
            customer_id = None

            # Get charge ID from payment intent
            if payment_intent and hasattr(payment_intent, "charges"):
                charges = payment_intent.charges.data
                if charges:
                    charge_id = charges[0].id

            # Get customer ID
            customer = full_session.get("customer")
            if customer:
                customer_id = customer.id if hasattr(customer, "id") else customer

            # Update payment record
            update_result = self.collection.find_one_and_update(
                {"stripe_session_id": session_id},
                {
                    "$set": {
                        "status": PaymentStatus.SUCCEEDED.value,
                        "stripe_payment_intent_id": payment_intent_id,
                        "stripe_charge_id": charge_id,
                        "stripe_customer_id": customer_id,
                        "stripe_response": (
                            dict(full_session)
                            if hasattr(full_session, "__iter__")
                            else None
                        ),
                        "completed_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    }
                },
                return_document=ReturnDocument.AFTER,
            )

            if not update_result:
                logger.error(f"No payment record found for session {session_id}")
                return {"success": False, "error": "Payment record not found"}

            payment = Payment.from_dict(update_result)

            # Activate subscription
            subscription = self.subscription_service.activate_subscription(
                stripe_session_id=session_id, payment_id=payment._id
            )

            if subscription:
                logger.info(
                    f"Payment {payment._id} completed, subscription {subscription._id} activated"
                )
            else:
                logger.warning(
                    f"Payment {payment._id} completed but subscription activation failed"
                )

            return {
                "success": True,
                "message": "Payment processed successfully",
                "payment_id": str(payment._id),
            }

        except Exception as e:
            logger.error(f"Error handling checkout completed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _handle_checkout_expired(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle expired checkout session"""
        try:
            session_id = session_data["id"]

            self.collection.update_one(
                {"stripe_session_id": session_id},
                {
                    "$set": {
                        "status": PaymentStatus.CANCELLED.value,
                        "failure_reason": "Checkout session expired",
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

            logger.info(f"Checkout expired for session {session_id}")
            return {"success": True, "message": "Expiration recorded"}

        except Exception as e:
            logger.error(f"Error handling checkout expired: {str(e)}")
            return {"success": False, "error": str(e)}

    def _handle_payment_failed(
        self, payment_intent_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle failed payment"""
        try:
            pi_id = payment_intent_data["id"]
            failure_message = payment_intent_data.get("last_payment_error", {}).get(
                "message", "Unknown error"
            )

            self.collection.update_one(
                {"stripe_payment_intent_id": pi_id},
                {
                    "$set": {
                        "status": PaymentStatus.FAILED.value,
                        "failure_reason": failure_message,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

            logger.info(f"Payment failed for intent {pi_id}: {failure_message}")
            return {"success": True, "message": "Failure recorded"}

        except Exception as e:
            logger.error(f"Error handling payment failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _handle_refund(self, charge_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle refund event"""
        try:
            charge_id = charge_data["id"]
            amount_refunded = charge_data.get("amount_refunded", 0)

            # Determine if full or partial refund
            original_amount = charge_data.get("amount", 0)
            is_full_refund = amount_refunded >= original_amount

            new_status = (
                PaymentStatus.REFUNDED
                if is_full_refund
                else PaymentStatus.PARTIALLY_REFUNDED
            )

            self.collection.update_one(
                {"stripe_charge_id": charge_id},
                {
                    "$set": {
                        "status": new_status.value,
                        "refund_amount_cents": amount_refunded,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

            logger.info(
                f"Refund processed for charge {charge_id}: {amount_refunded} cents"
            )
            return {"success": True, "message": "Refund recorded"}

        except Exception as e:
            logger.error(f"Error handling refund: {str(e)}")
            return {"success": False, "error": str(e)}

    def request_refund(
        self,
        payment_id: str,
        reason: str = "requested_by_customer",
        amount_cents: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Request a refund for a payment.

        Args:
            payment_id: Internal payment ID
            reason: Refund reason
            amount_cents: Partial refund amount (None for full)

        Returns:
            Refund result
        """
        try:
            payment_data = self.collection.find_one({"_id": ObjectId(payment_id)})

            if not payment_data:
                return {
                    "success": False,
                    "error": "Payment not found",
                    "error_code": "not_found",
                }

            payment = Payment.from_dict(payment_data)

            if not payment.is_refundable:
                return {
                    "success": False,
                    "error": "Payment is not refundable",
                    "error_code": "not_refundable",
                }

            # Process refund via Stripe
            refund_result = self.stripe_service.process_refund(
                charge_id=payment.stripe_charge_id,
                amount_cents=amount_cents,
                reason=reason,
            )

            if refund_result["success"]:
                # Update payment record
                refund_amount = refund_result["amount"]
                is_full_refund = refund_amount >= payment.amount_cents

                self.collection.update_one(
                    {"_id": payment._id},
                    {
                        "$set": {
                            "status": (
                                PaymentStatus.REFUNDED.value
                                if is_full_refund
                                else PaymentStatus.PARTIALLY_REFUNDED.value
                            ),
                            "refund_amount_cents": refund_amount,
                            "refund_reason": reason,
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )

                # Cancel associated subscription
                if payment.subscription_id:
                    self.db["subscriptions"].update_one(
                        {"_id": payment.subscription_id},
                        {
                            "$set": {
                                "status": "cancelled",
                                "metadata.cancelled_reason": "refund_processed",
                            }
                        },
                    )

                logger.info(f"Refund processed for payment {payment_id}")

            return refund_result

        except Exception as e:
            logger.error(f"Refund request error: {str(e)}")
            return {
                "success": False,
                "error": "Refund processing failed",
                "error_code": "refund_failed",
            }

    def get_payment_by_id(self, payment_id: str) -> Optional[Payment]:
        """Get payment by ID"""
        try:
            payment_data = self.collection.find_one({"_id": ObjectId(payment_id)})
            if payment_data:
                return Payment.from_dict(payment_data)
            return None
        except Exception as e:
            logger.error(f"Error fetching payment: {str(e)}")
            return None

    def get_employer_payments(self, employer_id: str, limit: int = 20) -> list:
        """Get payment history for an employer"""
        try:
            payments = (
                self.collection.find({"employer_id": ObjectId(employer_id)})
                .sort("created_at", -1)
                .limit(limit)
            )

            return [Payment.from_dict(p).to_api_response() for p in payments]
        except Exception as e:
            logger.error(f"Error fetching employer payments: {str(e)}")
            return []
