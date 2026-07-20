"""
Payment Service - Orchestrates payment flow and business logic

Design Decisions:
1. Single responsibility: coordinates between Razorpay and DB
2. Never trusts frontend payment status
3. Idempotent webhook handling
4. Full payment lifecycle tracking
5. Refund support with status updates
"""

import logging
import uuid
import json
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from bson import ObjectId
from pymongo import ReturnDocument

from ..models.payment import Payment, PaymentSchema, PaymentStatus
from ..models.plan import Plan
from ..services.razorpay_service import RazorpayService
from ..services.plan_service import PlanService
from ..services.wallet_service import WalletService
from ..services.subscription_service import SubscriptionService
from ..config.settings import PaymentConfig

logger = logging.getLogger(__name__)


class PaymentService:
    """
    Central service for payment orchestration.

    Handles:
    - Payment initiation (order creation)
    - Payment verification
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
        self.razorpay_service = RazorpayService()
        self.plan_service = PlanService(db)
        self.wallet_service = WalletService(db)
        # Used by the order.paid webhook handler to activate subscriptions;
        # instantiated here so that path never hits an undefined attribute.
        self.subscription_service = SubscriptionService(db)

    def _ensure_indexes(self):
        """Create indexes if they don't exist"""
        try:
            PaymentSchema.create_indexes(self.db)
            logger.info("Payment indexes ensured")
        except Exception as e:
            logger.error(f"Error creating payment indexes: {str(e)}")

    def initiate_payment(
        self,
        employer_id: str,
        employer_email: str,
        employer_name: str,
        plan_id: str,
        buyer_type: str = "recruiter",
    ) -> Dict[str, Any]:
        """
        Initiate payment for a plan.

        Flow:
        1. Validate plan exists
        2. Generate idempotency key
        3. Create Razorpay order
        4. Create pending payment record
        5. Return order details for frontend checkout

        Args:
            employer_id: User ID
            employer_email: User email for receipts
            employer_name: User name
            plan_id: Plan to purchase

        Returns:
            Dict with order_id and checkout details or error
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

            plan_audience = getattr(plan, "audience", "recruiter")
            if buyer_type == "student":
                buyer_type = "candidate"
            if plan_audience != buyer_type:
                return {
                    "success": False,
                    "error": f"This plan is available only for {plan_audience}s",
                    "error_code": "plan_audience_mismatch",
                }

            # 2. Generate idempotency key (≤40 chars for Razorpay receipt limit)
            idempotency_key = f"ord_{uuid.uuid4().hex[:32]}"

            # 3. Create Razorpay order
            order_result = self.razorpay_service.create_order(
                employer_id=employer_id,
                employer_email=employer_email,
                plan_id=str(plan._id),
                plan_name=plan.name,
                price_paise=plan.price_paise,
                idempotency_key=idempotency_key,
            )

            if not order_result["success"]:
                return order_result

            razorpay_order_id = order_result["order_id"]

            # 4. Create pending payment record
            payment = Payment(
                employer_id=ObjectId(employer_id),
                plan_id=plan._id,
                amount_paise=plan.price_paise,
                currency=PaymentConfig.CURRENCY,
                status=PaymentStatus.PENDING,
                razorpay_order_id=razorpay_order_id,
                idempotency_key=idempotency_key,
                metadata={
                    "employer_name": employer_name,
                    "employer_email": employer_email,
                    "plan_name": plan.name,
                    "plan_slug": plan.slug,
                    "buyer_type": buyer_type,
                    "plan_audience": plan_audience,
                    "recharge_credits": int(plan.credits_allocated or 0),
                },
            )

            payment_result = self.collection.insert_one(payment.to_dict())
            payment._id = payment_result.inserted_id

            logger.info(f"Payment initiated: {payment._id} for employer {employer_id}")

            return {
                "success": True,
                "order_id": razorpay_order_id,
                "amount": order_result["amount"],
                "currency": order_result["currency"],
                "key_id": order_result["key_id"],
                "payment_id": str(payment._id),
                "prefill": {
                    "name": employer_name,
                    "email": employer_email,
                },
                "notes": {
                    "plan_id": str(plan._id),
                    "plan_name": plan.name,
                    "plan_slug": plan.slug,
                    "plan_audience": plan_audience,
                    "recharge_credits": int(plan.credits_allocated or 0),
                },
            }

        except Exception as e:
            logger.error(f"Payment initiation error: {str(e)}")
            return {
                "success": False,
                "error": "Failed to initiate payment",
                "error_code": "initiation_failed",
            }

    def _apply_recharge_credit(
        self,
        payment_doc: Dict[str, Any],
        payment: "Payment",
        razorpay_order_id: str,
        razorpay_payment_id: Optional[str],
    ) -> Tuple[Dict[str, Any], str, int]:
        """Credit the buyer's wallet for a succeeded recharge and record the
        outcome durably on the payment record.

        credit_wallet is idempotent on ``recharge:{order_id}``, so this is safe
        to call from BOTH the synchronous verify path and the async webhook
        path — whichever runs second is a no-op replay, never a double credit.

        The critical robustness guarantee: a payment can succeed at Razorpay but
        fail to credit the wallet (DB blip, etc.). We must never let that money
        vanish silently. On failure we flag the payment
        (``credit_status='failed'``, ``needs_reconciliation=True``), log at
        ERROR, and upsert a row into ``payment_reconciliations`` — a durable,
        queryable queue an admin/ops can replay. The webhook then self-heals the
        same idempotent credit when it arrives.

        Returns ``(credit_result, audience, recharge_credits)``.
        """
        metadata = payment_doc.get("metadata", {}) or {}
        audience = (
            metadata.get("plan_audience")
            or metadata.get("buyer_type")
            or "recruiter"
        )
        if audience == "student":
            audience = "candidate"

        recharge_credits = int(metadata.get("recharge_credits", 0) or 0)
        if recharge_credits <= 0:
            plan_id = payment_doc.get("plan_id")
            if plan_id:
                plan = self.plan_service.get_plan_by_id(str(plan_id), audience=audience)
                if plan:
                    recharge_credits = int(plan.credits_allocated or 0)

        owner_id = str(payment_doc.get("employer_id"))
        amount_paise = int(payment_doc.get("amount_paise", 0) or 0)

        credited = self.wallet_service.credit_wallet(
            owner_id=owner_id,
            audience=audience,
            credits=recharge_credits,
            transaction_type="recharge",
            reference_type="payment",
            reference_id=str(payment._id),
            metadata={
                "plan_id": str(payment_doc.get("plan_id") or ""),
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "amount_paise": amount_paise,
                "plan_name": metadata.get("plan_name"),
                "plan_slug": metadata.get("plan_slug"),
                "recharge_credits": recharge_credits,
            },
            idempotency_key=f"recharge:{razorpay_order_id}",
        )

        if credited.get("success"):
            self.collection.update_one(
                {"_id": payment._id},
                {
                    "$set": {
                        "credit_status": "completed",
                        "credit_completed_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    },
                    "$unset": {"needs_reconciliation": "", "credit_error": ""},
                },
            )
            # Clear any prior reconciliation row now that the credit landed.
            try:
                self.db["payment_reconciliations"].update_one(
                    {"razorpay_order_id": razorpay_order_id},
                    {"$set": {"resolved": True, "resolved_at": datetime.utcnow()}},
                )
            except Exception:
                pass
        else:
            error_msg = credited.get("error", "unknown error")
            logger.error(
                "CRITICAL: wallet credit FAILED after a SUCCEEDED payment. "
                "payment_id=%s order=%s owner=%s credits=%s error=%s — flagged "
                "for reconciliation (payment_reconciliations).",
                str(payment._id), razorpay_order_id, owner_id, recharge_credits, error_msg,
            )
            self.collection.update_one(
                {"_id": payment._id},
                {
                    "$set": {
                        "credit_status": "failed",
                        "credit_error": error_msg,
                        "needs_reconciliation": True,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            try:
                self.db["payment_reconciliations"].update_one(
                    {"razorpay_order_id": razorpay_order_id},
                    {
                        "$set": {
                            "payment_id": str(payment._id),
                            "owner_id": owner_id,
                            "audience": audience,
                            "recharge_credits": recharge_credits,
                            "razorpay_order_id": razorpay_order_id,
                            "razorpay_payment_id": razorpay_payment_id,
                            "amount_paise": amount_paise,
                            "error": error_msg,
                            "resolved": False,
                            "updated_at": datetime.utcnow(),
                        },
                        "$setOnInsert": {"created_at": datetime.utcnow()},
                    },
                    upsert=True,
                )
            except Exception as rec_exc:
                logger.error(
                    "Failed to enqueue reconciliation for order %s: %s",
                    razorpay_order_id, rec_exc,
                )

        return credited, audience, recharge_credits

    def verify_payment(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> Dict[str, Any]:
        """
        Verify payment signature after successful payment on frontend.

        CRITICAL: This verifies the payment was successful.

        Args:
            razorpay_order_id: Order ID from Razorpay
            razorpay_payment_id: Payment ID from Razorpay
            razorpay_signature: Signature from Razorpay

        Returns:
            Dict with verification result
        """
        try:
            # 1. Verify signature
            is_valid = self.razorpay_service.verify_payment_signature(
                razorpay_order_id, razorpay_payment_id, razorpay_signature
            )

            if not is_valid:
                logger.warning(
                    f"Invalid payment signature for order {razorpay_order_id}"
                )
                return {
                    "success": False,
                    "error": "Invalid payment signature",
                    "error_code": "invalid_signature",
                }

            # 2. Check for duplicate processing
            existing_payment = self.collection.find_one(
                {
                    "razorpay_order_id": razorpay_order_id,
                    "status": PaymentStatus.SUCCEEDED.value,
                }
            )

            if existing_payment:
                logger.info(
                    f"Duplicate verification for order {razorpay_order_id}, already processed"
                )
                return {"success": True, "message": "Already processed"}

            # 3. Fetch payment details from Razorpay
            payment_details = self.razorpay_service.fetch_payment(razorpay_payment_id)

            # 4. Update payment record
            update_result = self.collection.find_one_and_update(
                {"razorpay_order_id": razorpay_order_id},
                {
                    "$set": {
                        "status": PaymentStatus.SUCCEEDED.value,
                        "razorpay_payment_id": razorpay_payment_id,
                        "razorpay_signature": razorpay_signature,
                        "razorpay_response": payment_details,
                        "completed_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    }
                },
                return_document=ReturnDocument.AFTER,
            )

            if not update_result:
                logger.error(f"No payment record found for order {razorpay_order_id}")
                return {"success": False, "error": "Payment record not found"}

            payment = Payment.from_dict(update_result)

            credited, audience, _ = self._apply_recharge_credit(
                update_result, payment, razorpay_order_id, razorpay_payment_id
            )

            response = {
                "success": True,
                "message": "Payment verified successfully",
                "payment_id": str(payment._id),
                "wallet": self.wallet_service.get_wallet_summary(
                    owner_id=str(update_result.get("employer_id")),
                    audience=audience,
                ),
            }
            # The payment itself succeeded. If crediting the wallet did NOT, the
            # order is already flagged for reconciliation (see
            # _apply_recharge_credit) and the Razorpay webhook will replay the
            # same idempotent credit. Signal the client so it shows "credits
            # pending" instead of a balance it hasn't actually received yet.
            if not credited.get("success"):
                response["credit_status"] = "pending_reconciliation"
                response["message"] = (
                    "Payment received. Your credits are being finalized — if they "
                    "do not appear shortly, contact support with your payment id."
                )
            return response

        except Exception as e:
            logger.error(f"Payment verification error: {str(e)}")
            return {
                "success": False,
                "error": "Payment verification failed",
                "error_code": "verification_failed",
            }

    def process_webhook(self, payload: bytes, signature: str) -> Dict[str, Any]:
        """
        Process Razorpay webhook event.

        Handles:
        - payment.captured: Payment success
        - payment.failed: Payment failure
        - refund.created: Refund processed
        - order.paid: Order paid

        Args:
            payload: Raw webhook payload
            signature: X-Razorpay-Signature header

        Returns:
            Dict with processing result
        """
        try:
            # 1. Verify webhook signature
            is_valid, error = self.razorpay_service.verify_webhook_signature(
                payload, signature
            )

            if not is_valid:
                logger.warning(f"Webhook signature verification failed: {error}")
                return {
                    "success": False,
                    "error": error,
                    "error_code": "invalid_signature",
                }

            # 2. Parse event
            event = json.loads(payload.decode("utf-8"))
            event_type = event.get("event")
            event_data = event.get("payload", {})

            logger.info(f"Processing webhook: {event_type}")

            # 3. Route to appropriate handler
            if event_type == "payment.captured":
                return self._handle_payment_captured(event_data)

            elif event_type == "payment.failed":
                return self._handle_payment_failed(event_data)

            elif event_type == "refund.created":
                return self._handle_refund(event_data)

            elif event_type == "order.paid":
                return self._handle_order_paid(event_data)

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

    def _handle_payment_captured(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle successful payment capture.

        Args:
            event_data: Razorpay event payload

        Returns:
            Processing result
        """
        try:
            payment_entity = event_data.get("payment", {}).get("entity", {})
            razorpay_payment_id = payment_entity.get("id")
            razorpay_order_id = payment_entity.get("order_id")

            # Skip only when this order is fully done — succeeded AND already
            # credited. If a prior (synchronous verify) attempt marked the
            # payment succeeded but the wallet credit failed, we must NOT
            # short-circuit: this webhook is the self-heal path that replays the
            # idempotent credit and clears the reconciliation flag.
            existing_payment = self.collection.find_one(
                {
                    "razorpay_order_id": razorpay_order_id,
                    "status": PaymentStatus.SUCCEEDED.value,
                }
            )

            if existing_payment and existing_payment.get("credit_status") == "completed":
                logger.info(
                    f"Duplicate webhook for order {razorpay_order_id}, already credited"
                )
                return {"success": True, "message": "Already processed"}

            # Update payment record
            update_result = self.collection.find_one_and_update(
                {"razorpay_order_id": razorpay_order_id},
                {
                    "$set": {
                        "status": PaymentStatus.SUCCEEDED.value,
                        "razorpay_payment_id": razorpay_payment_id,
                        "razorpay_response": payment_entity,
                        "completed_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    }
                },
                return_document=ReturnDocument.AFTER,
            )

            if not update_result:
                logger.error(f"No payment record found for order {razorpay_order_id}")
                return {"success": False, "error": "Payment record not found"}

            payment = Payment.from_dict(update_result)

            # Idempotent credit shared with the synchronous verify path; on
            # failure it flags the payment + enqueues reconciliation instead of
            # losing the customer's credits silently.
            self._apply_recharge_credit(
                update_result, payment, razorpay_order_id, razorpay_payment_id
            )

            return {
                "success": True,
                "message": "Payment captured successfully",
                "payment_id": str(payment._id),
            }

        except Exception as e:
            logger.error(f"Error handling payment captured: {str(e)}")
            return {"success": False, "error": str(e)}

    def _handle_payment_failed(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed payment"""
        try:
            payment_entity = event_data.get("payment", {}).get("entity", {})
            razorpay_payment_id = payment_entity.get("id")
            razorpay_order_id = payment_entity.get("order_id")
            error_description = payment_entity.get("error_description", "Unknown error")

            self.collection.update_one(
                {"razorpay_order_id": razorpay_order_id},
                {
                    "$set": {
                        "status": PaymentStatus.FAILED.value,
                        "razorpay_payment_id": razorpay_payment_id,
                        "failure_reason": error_description,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

            logger.info(
                f"Payment failed for order {razorpay_order_id}: {error_description}"
            )
            return {"success": True, "message": "Failure recorded"}

        except Exception as e:
            logger.error(f"Error handling payment failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _handle_refund(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle refund event"""
        try:
            refund_entity = event_data.get("refund", {}).get("entity", {})
            razorpay_payment_id = refund_entity.get("payment_id")
            amount_refunded = refund_entity.get("amount", 0)

            # Find payment by razorpay_payment_id
            payment_data = self.collection.find_one(
                {"razorpay_payment_id": razorpay_payment_id}
            )

            if not payment_data:
                logger.warning(
                    f"No payment found for refund on payment {razorpay_payment_id}"
                )
                return {"success": True, "message": "Payment not found for refund"}

            # Determine if full or partial refund
            original_amount = payment_data.get("amount_paise", 0)
            is_full_refund = amount_refunded >= original_amount

            new_status = (
                PaymentStatus.REFUNDED
                if is_full_refund
                else PaymentStatus.PARTIALLY_REFUNDED
            )

            self.collection.update_one(
                {"razorpay_payment_id": razorpay_payment_id},
                {
                    "$set": {
                        "status": new_status.value,
                        "refund_amount_paise": amount_refunded,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

            logger.info(
                f"Refund processed for payment {razorpay_payment_id}: {amount_refunded} paise"
            )
            return {"success": True, "message": "Refund recorded"}

        except Exception as e:
            logger.error(f"Error handling refund: {str(e)}")
            return {"success": False, "error": str(e)}

    def _handle_order_paid(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle order paid event (similar to payment captured)"""
        try:
            order_entity = event_data.get("order", {}).get("entity", {})
            payment_entity = event_data.get("payment", {}).get("entity", {})

            razorpay_order_id = order_entity.get("id")
            razorpay_payment_id = payment_entity.get("id") if payment_entity else None

            # Check for duplicate processing
            existing_payment = self.collection.find_one(
                {
                    "razorpay_order_id": razorpay_order_id,
                    "status": PaymentStatus.SUCCEEDED.value,
                }
            )

            if existing_payment:
                logger.info(
                    f"Duplicate webhook for order {razorpay_order_id}, already processed"
                )
                return {"success": True, "message": "Already processed"}

            # Update payment record
            update_data = {
                "status": PaymentStatus.SUCCEEDED.value,
                "completed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }

            if razorpay_payment_id:
                update_data["razorpay_payment_id"] = razorpay_payment_id

            update_result = self.collection.find_one_and_update(
                {"razorpay_order_id": razorpay_order_id},
                {"$set": update_data},
                return_document=ReturnDocument.AFTER,
            )

            if update_result:
                payment = Payment.from_dict(update_result)

                # Activate subscription
                self.subscription_service.activate_subscription(
                    razorpay_order_id=razorpay_order_id, payment_id=payment._id
                )

            logger.info(f"Order paid for {razorpay_order_id}")
            return {"success": True, "message": "Order paid recorded"}

        except Exception as e:
            logger.error(f"Error handling order paid: {str(e)}")
            return {"success": False, "error": str(e)}

    def request_refund(
        self,
        payment_id: str,
        reason: str = "requested_by_customer",
        amount_paise: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Request a refund for a payment.

        Args:
            payment_id: Internal payment ID
            reason: Refund reason
            amount_paise: Partial refund amount (None for full)

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

            # Process refund via Razorpay
            refund_result = self.razorpay_service.process_refund(
                payment_id=payment.razorpay_payment_id,
                amount_paise=amount_paise,
                notes={"reason": reason},
            )

            if refund_result["success"]:
                # Update payment record
                refund_amount = refund_result["amount"]
                is_full_refund = refund_amount >= payment.amount_paise

                self.collection.update_one(
                    {"_id": payment._id},
                    {
                        "$set": {
                            "status": (
                                PaymentStatus.REFUNDED.value
                                if is_full_refund
                                else PaymentStatus.PARTIALLY_REFUNDED.value
                            ),
                            "refund_amount_paise": refund_amount,
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
        """Get payment history for an authenticated user id."""
        try:
            filters = {"$or": [{"employer_id": employer_id}]}
            try:
                filters["$or"].append({"employer_id": ObjectId(employer_id)})
            except Exception:
                pass
            payments = self.collection.find(filters).sort("created_at", -1).limit(limit)

            return [Payment.from_dict(p).to_api_response() for p in payments]
        except Exception as e:
            logger.error(f"Error fetching employer payments: {str(e)}")
            return []
