"""
Subscription Service - Business logic for subscription management

Design Decisions:
1. Only one active subscription per employer at a time
2. Atomic interview decrement to prevent race conditions
3. Plan snapshot stored at purchase time (price protection)
4. Expiration handled by status check, not background job
5. Support for subscription extension
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from bson import ObjectId
from pymongo import ReturnDocument

from ..models.subscription import Subscription, SubscriptionSchema, SubscriptionStatus
from ..models.plan import Plan
from ..config.settings import PaymentConfig

logger = logging.getLogger(__name__)


def _normalize_validity_days(raw_validity_days: Any, default_days: int = 30) -> int:
    """Normalize validity period and enforce monthly 30-day duration over legacy 28."""
    try:
        validity_days = int(raw_validity_days)
    except (TypeError, ValueError):
        validity_days = default_days

    if validity_days == 28:
        return 30

    return max(1, validity_days)


class SubscriptionService:
    """
    Service for managing employer subscriptions.

    Handles:
    - Creating pending subscriptions
    - Activating after payment
    - Tracking interview usage
    - Checking subscription validity
    """

    def __init__(self, db):
        """
        Initialize with database connection.

        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.collection = db[SubscriptionSchema.COLLECTION_NAME]
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Create indexes if they don't exist"""
        try:
            SubscriptionSchema.create_indexes(self.db)
            logger.info("Subscription indexes ensured")
        except Exception as e:
            logger.error(f"Error creating subscription indexes: {str(e)}")

    def create_pending_subscription(
        self, employer_id: str, plan: Plan, razorpay_order_id: str
    ) -> Optional[Subscription]:
        """
        Create a pending subscription when checkout is initiated.

        The subscription remains pending until payment is confirmed
        via webhook or verification.

        Args:
            employer_id: User ID
            plan: Plan being purchased
            razorpay_order_id: Razorpay order ID

        Returns:
            Created Subscription or None
        """
        try:
            # Create plan snapshot for price protection
            plan_snapshot = {
                "name": plan.name,
                "slug": plan.slug,
                "price_paise": plan.price_paise,
                "interviews_allowed": plan.interviews_allowed,
                "validity_days": _normalize_validity_days(plan.validity_days),
                "features": plan.features,
            }

            subscription = Subscription(
                employer_id=ObjectId(employer_id),
                plan_id=plan._id,
                plan_snapshot=plan_snapshot,
                status=SubscriptionStatus.PENDING,
                interviews_allowed=plan.interviews_allowed,
                interviews_remaining=plan.interviews_allowed,
                razorpay_order_id=razorpay_order_id,
            )

            result = self.collection.insert_one(subscription.to_dict())
            subscription._id = result.inserted_id

            logger.info(
                f"Created pending subscription {result.inserted_id} for employer {employer_id}"
            )
            return subscription

        except Exception as e:
            logger.error(f"Error creating subscription: {str(e)}")
            return None

    def activate_subscription(
        self, razorpay_order_id: str, payment_id: ObjectId
    ) -> Optional[Subscription]:
        """
        Activate subscription after successful payment.

        Called by webhook handler or payment verification after payment confirmation.

        Args:
            razorpay_order_id: Razorpay order ID
            payment_id: Internal payment record ID

        Returns:
            Activated Subscription or None
        """
        try:
            # Find the pending subscription
            sub_data = self.collection.find_one(
                {
                    "razorpay_order_id": razorpay_order_id,
                    "status": SubscriptionStatus.PENDING.value,
                }
            )

            if not sub_data:
                logger.warning(f"No pending subscription for order {razorpay_order_id}")
                return None

            subscription = Subscription.from_dict(sub_data)

            # Calculate expiration
            validity_days = _normalize_validity_days(
                subscription.plan_snapshot.get("validity_days", 30)
            )
            started_at = datetime.utcnow()
            expires_at = started_at + timedelta(days=validity_days)

            # Cancel any existing active subscription for this employer
            self._cancel_existing_active(subscription.employer_id)

            # Activate the subscription
            result = self.collection.find_one_and_update(
                {"_id": subscription._id},
                {
                    "$set": {
                        "status": SubscriptionStatus.ACTIVE.value,
                        "started_at": started_at,
                        "expires_at": expires_at,
                        "payment_id": payment_id,
                        "updated_at": datetime.utcnow(),
                    }
                },
                return_document=ReturnDocument.AFTER,
            )

            if result:
                logger.info(
                    f"Activated subscription {subscription._id} for employer {subscription.employer_id}"
                )
                return Subscription.from_dict(result)

            return None

        except Exception as e:
            logger.error(f"Error activating subscription: {str(e)}")
            return None

    def _cancel_existing_active(self, employer_id: ObjectId):
        """
        Cancel any existing active subscriptions for an employer.

        Only one active subscription allowed at a time.
        New purchases replace old subscriptions.
        """
        try:
            result = self.collection.update_many(
                {"employer_id": employer_id, "status": SubscriptionStatus.ACTIVE.value},
                {
                    "$set": {
                        "status": SubscriptionStatus.CANCELLED.value,
                        "updated_at": datetime.utcnow(),
                        "metadata.cancelled_reason": "replaced_by_new_subscription",
                    }
                },
            )

            if result.modified_count > 0:
                logger.info(
                    f"Cancelled {result.modified_count} existing subscriptions for employer {employer_id}"
                )

        except Exception as e:
            logger.error(f"Error cancelling existing subscriptions: {str(e)}")

    def get_active_subscription(self, employer_id: str) -> Optional[Subscription]:
        """
        Get the active subscription for an employer.

        Handles automatic expiration check.
        Tries both ObjectId and string formats for employer_id lookup.

        Args:
            employer_id: User ID (string)

        Returns:
            Active Subscription or None
        """
        try:
            # Try with ObjectId first (standard format)
            sub_data = self.collection.find_one(
                {
                    "employer_id": ObjectId(employer_id),
                    "status": SubscriptionStatus.ACTIVE.value,
                }
            )

            # If not found, try with string format (for legacy data)
            if not sub_data:
                sub_data = self.collection.find_one(
                    {
                        "employer_id": employer_id,
                        "status": SubscriptionStatus.ACTIVE.value,
                    }
                )

            if not sub_data:
                logger.debug(f"No active subscription found for employer {employer_id}")
                return None

            subscription = Subscription.from_dict(sub_data)

            # Check if expired
            if subscription.expires_at and datetime.utcnow() > subscription.expires_at:
                # Mark as expired
                self._expire_subscription(subscription._id)
                logger.info(f"Subscription {subscription._id} has expired")
                return None

            return subscription

        except Exception as e:
            logger.error(f"Error fetching subscription for {employer_id}: {str(e)}")
            return None

    def get_subscription_by_order(
        self, razorpay_order_id: str
    ) -> Optional[Subscription]:
        """
        Get subscription by Razorpay order ID.

        Used for webhook processing.

        Args:
            razorpay_order_id: Razorpay order ID

        Returns:
            Subscription or None
        """
        try:
            sub_data = self.collection.find_one(
                {"razorpay_order_id": razorpay_order_id}
            )

            if sub_data:
                return Subscription.from_dict(sub_data)
            return None

        except Exception as e:
            logger.error(f"Error fetching subscription by order: {str(e)}")
            return None

    def use_interview(self, employer_id: str) -> Dict[str, Any]:
        """
        Decrement interview count atomically.

        Critical for concurrency - uses atomic $inc operation.

        Args:
            employer_id: User ID

        Returns:
            Dict with success status and remaining interviews
        """
        try:
            # First, get and validate the subscription
            subscription = self.get_active_subscription(employer_id)

            if not subscription:
                return {
                    "success": False,
                    "error": "No active subscription",
                    "error_code": "no_subscription",
                }

            # Check if can use interview
            if not subscription.can_use_interview:
                if not subscription.is_active:
                    return {
                        "success": False,
                        "error": "Subscription expired or inactive",
                        "error_code": "subscription_inactive",
                    }
                return {
                    "success": False,
                    "error": "Interview limit reached",
                    "error_code": "limit_exceeded",
                }

            # For unlimited plans, just increment used count
            if subscription.is_unlimited:
                self.collection.update_one(
                    {"_id": subscription._id},
                    {
                        "$inc": {"interviews_used": 1},
                        "$set": {"updated_at": datetime.utcnow()},
                    },
                )
                return {
                    "success": True,
                    "interviews_remaining": -1,  # Unlimited
                    "interviews_used": subscription.interviews_used + 1,
                    "is_unlimited": True,
                }

            # Atomic decrement for limited plans
            # Only decrement if remaining > 0
            result = self.collection.find_one_and_update(
                {"_id": subscription._id, "interviews_remaining": {"$gt": 0}},
                {
                    "$inc": {"interviews_remaining": -1, "interviews_used": 1},
                    "$set": {"updated_at": datetime.utcnow()},
                },
                return_document=ReturnDocument.AFTER,
            )

            if not result:
                return {
                    "success": False,
                    "error": "Failed to decrement interviews - limit may have been reached",
                    "error_code": "decrement_failed",
                }

            updated_sub = Subscription.from_dict(result)

            logger.info(
                f"Interview used by employer {employer_id}. Remaining: {updated_sub.interviews_remaining}"
            )

            return {
                "success": True,
                "interviews_remaining": updated_sub.interviews_remaining,
                "interviews_used": updated_sub.interviews_used,
                "is_unlimited": False,
            }

        except Exception as e:
            logger.error(f"Error using interview for {employer_id}: {str(e)}")
            return {
                "success": False,
                "error": "Internal error",
                "error_code": "internal_error",
            }

    def _expire_subscription(self, subscription_id: ObjectId):
        """Mark subscription as expired"""
        try:
            self.collection.update_one(
                {"_id": subscription_id},
                {
                    "$set": {
                        "status": SubscriptionStatus.EXPIRED.value,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            logger.info(f"Subscription {subscription_id} marked as expired")
        except Exception as e:
            logger.error(f"Error expiring subscription: {str(e)}")

    def cancel_subscription(
        self, employer_id: str, reason: str = "user_requested"
    ) -> bool:
        """
        Cancel an active subscription.

        Args:
            employer_id: User ID
            reason: Cancellation reason

        Returns:
            Success boolean
        """
        try:
            result = self.collection.update_one(
                {
                    "employer_id": ObjectId(employer_id),
                    "status": SubscriptionStatus.ACTIVE.value,
                },
                {
                    "$set": {
                        "status": SubscriptionStatus.CANCELLED.value,
                        "updated_at": datetime.utcnow(),
                        "metadata.cancelled_reason": reason,
                    }
                },
            )

            return result.modified_count > 0

        except Exception as e:
            logger.error(f"Error cancelling subscription: {str(e)}")
            return False

    def get_subscription_history(
        self, employer_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get subscription history for an employer.

        Args:
            employer_id: User ID
            limit: Max records to return

        Returns:
            List of subscription API responses
        """
        try:
            subscriptions = (
                self.collection.find({"employer_id": ObjectId(employer_id)})
                .sort("created_at", -1)
                .limit(limit)
            )

            return [Subscription.from_dict(s).to_api_response() for s in subscriptions]

        except Exception as e:
            logger.error(f"Error fetching subscription history: {str(e)}")
            return []

    def expire_old_subscriptions(self) -> int:
        """
        Background task to expire old subscriptions.

        Should be called periodically (e.g., via cron).

        Returns:
            Number of subscriptions expired
        """
        try:
            result = self.collection.update_many(
                {
                    "status": SubscriptionStatus.ACTIVE.value,
                    "expires_at": {"$lt": datetime.utcnow()},
                },
                {
                    "$set": {
                        "status": SubscriptionStatus.EXPIRED.value,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

            if result.modified_count > 0:
                logger.info(f"Expired {result.modified_count} subscriptions")

            return result.modified_count

        except Exception as e:
            logger.error(f"Error expiring subscriptions: {str(e)}")
            return 0
