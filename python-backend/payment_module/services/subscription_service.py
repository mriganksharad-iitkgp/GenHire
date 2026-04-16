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
import math
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import math
from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

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
        self.usage_events_collection = db["subscription_usage_events"]
        self._ensure_indexes()
        self._backfill_subscription_credits()

    def _backfill_subscription_credits(self):
        """Populate legacy subscription documents with credit fields."""
        try:
            legacy_filter = {
                "$or": [
                    {"credits_allocated": {"$exists": False}},
                    {"credits_remaining": {"$exists": False}},
                    {"credits_used": {"$exists": False}},
                ]
            }

            updated_count = 0
            for subscription_doc in self.collection.find(legacy_filter):
                interviews_allowed = int(
                    subscription_doc.get("interviews_allowed", 0) or 0
                )
                interviews_remaining = int(
                    subscription_doc.get(
                        "interviews_remaining", interviews_allowed
                    )
                    or 0
                )
                interviews_used = int(
                    subscription_doc.get(
                        "interviews_used",
                        max(0, interviews_allowed - interviews_remaining),
                    )
                    or 0
                )

                credits_allocated = int(
                    subscription_doc.get("credits_allocated", interviews_allowed)
                    or 0
                )
                credits_remaining = int(
                    subscription_doc.get("credits_remaining", interviews_remaining)
                    or 0
                )
                credits_used = int(
                    subscription_doc.get("credits_used", interviews_used) or 0
                )

                updates = {}
                if subscription_doc.get("credits_allocated") != credits_allocated:
                    updates["credits_allocated"] = credits_allocated
                if subscription_doc.get("credits_remaining") != credits_remaining:
                    updates["credits_remaining"] = credits_remaining
                if subscription_doc.get("credits_used") != credits_used:
                    updates["credits_used"] = credits_used

                if updates:
                    updates["updated_at"] = datetime.utcnow()
                    self.collection.update_one(
                        {"_id": subscription_doc["_id"]}, {"$set": updates}
                    )
                    updated_count += 1

            if updated_count > 0:
                logger.info(
                    "Backfilled credit fields for %s legacy subscription documents",
                    updated_count,
                )
        except Exception as e:
            logger.warning(f"Skipping subscription credit backfill: {str(e)}")
    

    def _ensure_indexes(self):
        """Create indexes if they don't exist"""
        try:
            SubscriptionSchema.create_indexes(self.db)
            self.usage_events_collection.create_index(
                [("idempotency_key", 1)],
                unique=True,
                name="uniq_subscription_usage_idempotency",
            )
            self.usage_events_collection.create_index(
                [("subscription_id", 1), ("created_at", -1)],
                name="idx_subscription_usage_subscription_created",
            )
            logger.info("Subscription indexes ensured")
        except Exception as e:
            logger.error(f"Error creating subscription indexes: {str(e)}")

    def _credits_from_usage_cost(self, usage_cost_usd: float) -> int:
        credit_per_usd = max(
            1, int(getattr(PaymentConfig, "CREDIT_PER_USD", 1000) or 1000)
        )
        min_credits = max(1, int(getattr(PaymentConfig, "MIN_USAGE_CREDITS", 1) or 1))

        if usage_cost_usd <= 0:
            return min_credits

        calculated = int(math.ceil(float(usage_cost_usd) * credit_per_usd))
        return max(min_credits, calculated)

    def check_credit_availability(
        self, employer_id: str, audience: str = "recruiter"
    ) -> Dict[str, Any]:
        """Check whether a user can start an interview based on remaining credits."""
        try:
            subscription = self.get_active_subscription(employer_id, audience=audience)
            min_start_credits = max(
                1,
                int(getattr(PaymentConfig, "START_INTERVIEW_MIN_CREDITS", 1) or 1),
            )

            if not subscription:
                return {
                    "success": False,
                    "can_start_interview": False,
                    "error": "No active subscription",
                    "error_code": "no_subscription",
                    "credits_remaining": 0,
                    "credits_allocated": 0,
                    "credits_used": 0,
                    "is_unlimited": False,
                    "plan_owner": audience,
                }

            credits_remaining = (
                -1
                if subscription.is_unlimited
                else int(subscription.interviews_remaining or 0)
            )

            can_start = bool(
                subscription.is_unlimited or credits_remaining >= min_start_credits
            )
            if not can_start:
                return {
                    "success": False,
                    "can_start_interview": False,
                    "error": "Insufficient credits to start interview",
                    "error_code": "insufficient_credits",
                    "credits_remaining": credits_remaining,
                    "credits_allocated": int(subscription.interviews_allowed or 0),
                    "credits_used": int(subscription.interviews_used or 0),
                    "is_unlimited": bool(subscription.is_unlimited),
                    "plan_owner": audience,
                }

            return {
                "success": True,
                "can_start_interview": True,
                "credits_remaining": credits_remaining,
                "credits_allocated": int(subscription.interviews_allowed or 0),
                "credits_used": int(subscription.interviews_used or 0),
                "is_unlimited": bool(subscription.is_unlimited),
                "plan_owner": audience,
            }
        except Exception as e:
            logger.error(
                f"Error checking credit availability for {employer_id}: {str(e)}"
            )
            return {
                "success": False,
                "can_start_interview": False,
                "error": "Internal error",
                "error_code": "internal_error",
                "credits_remaining": 0,
                "credits_allocated": 0,
                "credits_used": 0,
                "is_unlimited": False,
                "plan_owner": audience,
            }

    def consume_usage_credits(
        self,
        employer_id: str,
        usage_summary: Optional[Dict[str, Any]] = None,
        audience: str = "recruiter",
        idempotency_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Deduct usage-based credits at interview end with idempotency."""
        usage_summary = usage_summary or {}
        metadata = metadata or {}

        if not idempotency_key:
            return {
                "success": False,
                "error": "idempotency_key is required",
                "error_code": "invalid_request",
            }

        existing_event = self.usage_events_collection.find_one(
            {"idempotency_key": idempotency_key}
        )
        if existing_event:
            return {
                "success": True,
                "idempotent_replay": True,
                "credits_deducted": int(existing_event.get("credits_deducted", 0) or 0),
                "usage_cost_usd": float(
                    existing_event.get("usage_cost_usd", 0.0) or 0.0
                ),
                "credits_remaining": int(
                    existing_event.get("credits_remaining", 0) or 0
                ),
                "credits_used": int(existing_event.get("credits_used", 0) or 0),
                "credits_allocated": int(
                    existing_event.get("credits_allocated", 0) or 0
                ),
                "is_unlimited": bool(existing_event.get("is_unlimited", False)),
                "interviews_used": int(existing_event.get("interviews_used", 0) or 0),
                "source": "subscription",
            }

        subscription = self.get_active_subscription(employer_id, audience=audience)
        if not subscription:
            return {
                "success": False,
                "error": "No active subscription",
                "error_code": "no_subscription",
            }

        usage_cost_usd = float(usage_summary.get("total_cost", 0.0) or 0.0)
        requested_credits = self._credits_from_usage_cost(usage_cost_usd)
        credits_to_deduct = 0 if subscription.is_unlimited else requested_credits

        if subscription.is_unlimited:
            updated_doc = self.collection.find_one_and_update(
                {"_id": subscription._id},
                {
                    "$inc": {
                        "interviews_used": 1,
                        "metadata.usage_cost_total_usd": usage_cost_usd,
                    },
                    "$set": {"updated_at": datetime.utcnow()},
                },
                return_document=ReturnDocument.AFTER,
            )
        else:
            updated_doc = self.collection.find_one_and_update(
                {
                    "_id": subscription._id,
                    "interviews_remaining": {"$gte": credits_to_deduct},
                },
                {
                    "$inc": {
                        "interviews_remaining": -credits_to_deduct,
                        "interviews_used": credits_to_deduct,
                        "metadata.usage_cost_total_usd": usage_cost_usd,
                    },
                    "$set": {"updated_at": datetime.utcnow()},
                },
                return_document=ReturnDocument.AFTER,
            )

            if not updated_doc:
                fresh = self.get_active_subscription(employer_id, audience=audience)
                return {
                    "success": False,
                    "error": "Insufficient credits",
                    "error_code": "insufficient_credits",
                    "credits_deducted": 0,
                    "usage_cost_usd": round(usage_cost_usd, 6),
                    "credits_remaining": int(
                        (fresh.interviews_remaining if fresh else 0) or 0
                    ),
                    "credits_used": int((fresh.interviews_used if fresh else 0) or 0),
                    "credits_allocated": int(
                        (fresh.interviews_allowed if fresh else 0) or 0
                    ),
                    "is_unlimited": bool(fresh.is_unlimited) if fresh else False,
                }

        updated_sub = Subscription.from_dict(updated_doc)
        event_doc = {
            "subscription_id": updated_sub._id,
            "idempotency_key": idempotency_key,
            "employer_id": str(employer_id),
            "audience": audience,
            "usage": usage_summary,
            "usage_cost_usd": round(usage_cost_usd, 6),
            "credits_deducted": int(credits_to_deduct),
            "credits_allocated": int(updated_sub.interviews_allowed or 0),
            "credits_remaining": int(updated_sub.interviews_remaining or 0),
            "credits_used": int(updated_sub.interviews_used or 0),
            "is_unlimited": bool(updated_sub.is_unlimited),
            "interviews_used": int(updated_sub.interviews_used or 0),
            "metadata": metadata,
            "created_at": datetime.utcnow(),
        }

        try:
            self.usage_events_collection.insert_one(event_doc)
        except DuplicateKeyError:
            replay_event = self.usage_events_collection.find_one(
                {"idempotency_key": idempotency_key}
            )
            if replay_event:
                return {
                    "success": True,
                    "idempotent_replay": True,
                    "credits_deducted": int(
                        replay_event.get("credits_deducted", 0) or 0
                    ),
                    "usage_cost_usd": float(
                        replay_event.get("usage_cost_usd", 0.0) or 0.0
                    ),
                    "credits_remaining": int(
                        replay_event.get("credits_remaining", 0) or 0
                    ),
                    "credits_used": int(replay_event.get("credits_used", 0) or 0),
                    "credits_allocated": int(
                        replay_event.get("credits_allocated", 0) or 0
                    ),
                    "is_unlimited": bool(replay_event.get("is_unlimited", False)),
                    "interviews_used": int(replay_event.get("interviews_used", 0) or 0),
                    "source": "subscription",
                }

        return {
            "success": True,
            "credits_deducted": int(credits_to_deduct),
            "usage_cost_usd": round(usage_cost_usd, 6),
            "credits_remaining": int(updated_sub.interviews_remaining or 0),
            "credits_used": int(updated_sub.interviews_used or 0),
            "credits_allocated": int(updated_sub.interviews_allowed or 0),
            "is_unlimited": bool(updated_sub.is_unlimited),
            "interviews_used": int(updated_sub.interviews_used or 0),
            "source": "subscription",
        }

    def create_pending_subscription(
        self,
        employer_id: str,
        plan: Plan,
        razorpay_order_id: str,
        owner_type: str = "recruiter",
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
                "monthly_credits": getattr(
                    plan, "monthly_credits", plan.interviews_allowed
                ),
                "validity_days": _normalize_validity_days(plan.validity_days),
                "features": plan.features,
                "audience": getattr(plan, "audience", owner_type),
            }

            credits_allocated = int(
                getattr(plan, "monthly_credits", plan.interviews_allowed) or 0
            )

            subscription = Subscription(
                employer_id=ObjectId(employer_id),
                plan_id=plan._id,
                plan_snapshot=plan_snapshot,
                status=SubscriptionStatus.PENDING,
                interviews_allowed=plan.interviews_allowed,
                interviews_remaining=plan.interviews_allowed,
                credits_allocated=credits_allocated,
                credits_remaining=credits_allocated,
                razorpay_order_id=razorpay_order_id,
                metadata={"owner_type": owner_type},
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
            defaults_by_slug = {
                payload.get("slug"): int(
                    payload.get("monthly_credits", payload.get("interviews_allowed", 0))
                    or 0
                )
                for payload in PaymentConfig.DEFAULT_PLANS.values()
            }
            plan_slug = subscription.plan_snapshot.get("slug")
            fallback_allocated = defaults_by_slug.get(
                plan_slug, subscription.interviews_allowed
            )
            credits_allocated = int(
                subscription.plan_snapshot.get(
                    "monthly_credits",
                    fallback_allocated,
                )
                or 0
            )

            # Cancel any existing active subscription for this employer
            self._cancel_existing_active(
                subscription.employer_id,
                owner_type=subscription.plan_snapshot.get("audience", "recruiter"),
            )

            # Activate the subscription
            result = self.collection.find_one_and_update(
                {"_id": subscription._id},
                {
                    "$set": {
                        "status": SubscriptionStatus.ACTIVE.value,
                        "started_at": started_at,
                        "expires_at": expires_at,
                        "credits_allocated": credits_allocated,
                        "credits_remaining": credits_allocated,
                        "credits_used": 0,
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

    def _cancel_existing_active(
        self, employer_id: ObjectId, owner_type: str = "recruiter"
    ):
        """
        Cancel any existing active subscriptions for an employer.

        Only one active subscription allowed at a time.
        New purchases replace old subscriptions.
        """
        try:
            result = self.collection.update_many(
                {
                    "employer_id": employer_id,
                    "status": SubscriptionStatus.ACTIVE.value,
                    "$or": [
                        {"plan_snapshot.audience": owner_type},
                        (
                            {"plan_snapshot.audience": {"$exists": False}}
                            if owner_type == "recruiter"
                            else {"plan_snapshot.audience": owner_type}
                        ),
                    ],
                },
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

    def get_active_subscription(
        self, employer_id: str, audience: Optional[str] = None
    ) -> Optional[Subscription]:
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
            audience_filter = {}
            if audience in {"recruiter", "candidate"}:
                if audience == "recruiter":
                    audience_filter = {
                        "$or": [
                            {"plan_snapshot.audience": "recruiter"},
                            {"plan_snapshot.audience": {"$exists": False}},
                        ]
                    }
                else:
                    audience_filter = {"plan_snapshot.audience": "candidate"}

            # Try with ObjectId first (standard format)
            sub_data = self.collection.find_one(
                {
                    "employer_id": ObjectId(employer_id),
                    "status": SubscriptionStatus.ACTIVE.value,
                    **audience_filter,
                }
            )

            # If not found, try with string format (for legacy data)
            if not sub_data:
                sub_data = self.collection.find_one(
                    {
                        "employer_id": employer_id,
                        "status": SubscriptionStatus.ACTIVE.value,
                        **audience_filter,
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

    def check_credit_availability(
        self,
        employer_id: str,
        audience: str = "recruiter",
        min_required_credits: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Check whether user can start an interview based on active subscription credits."""
        try:
            subscription = self.get_active_subscription(employer_id, audience=audience)
            if not subscription:
                return {
                    "success": False,
                    "can_start_interview": False,
                    "error": "No active subscription",
                    "error_code": "no_subscription",
                }

            required = (
                int(min_required_credits)
                if min_required_credits is not None
                else int(PaymentConfig.START_INTERVIEW_MIN_CREDITS)
            )
            required = max(0, required)

            has_credits = subscription.credits_remaining >= required
            can_start = subscription.is_active and (
                subscription.is_unlimited or has_credits
            )

            return {
                "success": True,
                "can_start_interview": can_start,
                "required_credits": required,
                "credits_remaining": subscription.credits_remaining,
                "credits_used": subscription.credits_used,
                "credits_allocated": subscription.credits_allocated,
                "subscription_id": str(subscription._id) if subscription._id else None,
                "is_unlimited": subscription.is_unlimited,
                "error_code": None if can_start else "insufficient_credits",
            }
        except Exception as e:
            logger.error(
                f"Error checking credit availability for {employer_id}: {str(e)}"
            )
            return {
                "success": False,
                "can_start_interview": False,
                "error": "Internal error",
                "error_code": "internal_error",
            }

    def consume_usage_credits(
        self,
        employer_id: str,
        usage: Dict[str, Any],
        audience: str = "recruiter",
        idempotency_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Deduct credits from actual measured interview usage."""
        try:
            subscription = self.get_active_subscription(employer_id, audience=audience)
            if not subscription:
                return {
                    "success": False,
                    "error": "No active subscription",
                    "error_code": "no_subscription",
                }

            usage_cost_usd = self._round_cost(
                self._calculate_usage_cost_usd(usage or {})
            )
            credits_to_deduct = self._credits_from_usage_cost(usage_cost_usd)

            event_doc = {
                "subscription_id": subscription._id,
                "employer_id": subscription.employer_id,
                "idempotency_key": idempotency_key,
                "usage": usage or {},
                "usage_cost_usd": usage_cost_usd,
                "credits_deducted": credits_to_deduct,
                "metadata": metadata or {},
                "created_at": datetime.utcnow(),
            }

            if idempotency_key:
                try:
                    self.usage_collection.insert_one(event_doc)
                except DuplicateKeyError:
                    latest = self.collection.find_one({"_id": subscription._id})
                    latest_sub = (
                        Subscription.from_dict(latest) if latest else subscription
                    )
                    return {
                        "success": True,
                        "idempotent_replay": True,
                        "credits_deducted": 0,
                        "usage_cost_usd": usage_cost_usd,
                        "credits_remaining": latest_sub.credits_remaining,
                        "credits_used": latest_sub.credits_used,
                        "credits_allocated": latest_sub.credits_allocated,
                    }

            if subscription.is_unlimited:
                updated_doc = self.collection.find_one_and_update(
                    {"_id": subscription._id},
                    {
                        "$inc": {
                            "usage_cost_total_usd": usage_cost_usd,
                            "interviews_used": 1,
                        },
                        "$set": {"updated_at": datetime.utcnow()},
                    },
                    return_document=ReturnDocument.AFTER,
                )
            else:
                updated_doc = self.collection.find_one_and_update(
                    {
                        "_id": subscription._id,
                        "credits_remaining": {"$gte": credits_to_deduct},
                    },
                    {
                        "$inc": {
                            "credits_remaining": -credits_to_deduct,
                            "credits_used": credits_to_deduct,
                            "usage_cost_total_usd": usage_cost_usd,
                            "interviews_used": 1,
                        },
                        "$set": {"updated_at": datetime.utcnow()},
                    },
                    return_document=ReturnDocument.AFTER,
                )

            if not updated_doc:
                if idempotency_key:
                    self.usage_collection.delete_one(
                        {
                            "subscription_id": subscription._id,
                            "idempotency_key": idempotency_key,
                        }
                    )
                return {
                    "success": False,
                    "error": "Insufficient credits",
                    "error_code": "insufficient_credits",
                    "required_credits": credits_to_deduct,
                    "credits_remaining": subscription.credits_remaining,
                }

            updated_sub = Subscription.from_dict(updated_doc)

            return {
                "success": True,
                "idempotent_replay": False,
                "credits_deducted": (
                    0 if updated_sub.is_unlimited else credits_to_deduct
                ),
                "usage_cost_usd": usage_cost_usd,
                "credits_remaining": updated_sub.credits_remaining,
                "credits_used": updated_sub.credits_used,
                "credits_allocated": updated_sub.credits_allocated,
                "is_unlimited": updated_sub.is_unlimited,
                "interviews_used": updated_sub.interviews_used,
            }

        except Exception as e:
            logger.error(f"Error consuming usage credits for {employer_id}: {str(e)}")
            return {
                "success": False,
                "error": "Internal error",
                "error_code": "internal_error",
            }

    def use_interview(
        self, employer_id: str, audience: str = "recruiter"
    ) -> Dict[str, Any]:
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
            subscription = self.get_active_subscription(employer_id, audience=audience)

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
                    "credits_remaining": subscription.credits_remaining,
                    "credits_used": subscription.credits_used,
                    "credits_allocated": subscription.credits_allocated,
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
                "credits_remaining": updated_sub.credits_remaining,
                "credits_used": updated_sub.credits_used,
                "credits_allocated": updated_sub.credits_allocated,
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
        self,
        employer_id: str,
        reason: str = "user_requested",
        audience: str = "recruiter",
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
                    **(
                        {
                            "$or": [
                                {"plan_snapshot.audience": "recruiter"},
                                {"plan_snapshot.audience": {"$exists": False}},
                            ]
                        }
                        if audience == "recruiter"
                        else {"plan_snapshot.audience": audience}
                    ),
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
        self, employer_id: str, limit: int = 10, audience: Optional[str] = None
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
            audience_filter = {}
            if audience in {"recruiter", "candidate"}:
                if audience == "recruiter":
                    audience_filter = {
                        "$or": [
                            {"plan_snapshot.audience": "recruiter"},
                            {"plan_snapshot.audience": {"$exists": False}},
                        ]
                    }
                else:
                    audience_filter = {"plan_snapshot.audience": "candidate"}

            subscriptions = (
                self.collection.find(
                    {"employer_id": ObjectId(employer_id), **audience_filter}
                )
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
