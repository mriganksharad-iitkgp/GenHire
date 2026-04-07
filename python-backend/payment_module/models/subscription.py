"""
Subscription Model - Tracks active plan subscriptions for employers

Design Decisions:
1. Separate from Payment - a subscription can have multiple payment attempts
2. Status state machine: pending -> active -> expired/cancelled
3. interviews_remaining decremented atomically for concurrency safety
4. expires_at indexed for efficient cleanup/notification queries
5. employer_id references users collection for recruiter type users
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
from bson import ObjectId


class SubscriptionStatus(Enum):
    """
    Subscription lifecycle states:
    - PENDING: Created, awaiting payment confirmation
    - ACTIVE: Payment confirmed, plan is usable
    - EXPIRED: Validity period ended
    - CANCELLED: Manually cancelled (with potential refund)
    - SUSPENDED: Temporarily disabled (e.g., payment dispute)
    """

    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"


@dataclass
class Subscription:
    """
    Represents an employer's active plan subscription.

    Attributes:
        employer_id: Reference to users collection (recruiter)
        plan_id: Reference to plans collection
        plan_snapshot: Denormalized plan data at time of purchase
        status: Current subscription status
        interviews_allowed: Total interviews from plan
        interviews_remaining: Decremented on each use
        interviews_used: Counter for analytics
        started_at: When plan became active
        expires_at: When plan validity ends
        payment_id: Reference to successful payment
        razorpay_order_id: Razorpay order ID
        metadata: Additional data (e.g., promo codes applied)
        created_at: Record creation time
        updated_at: Last modification time
    """

    employer_id: ObjectId
    plan_id: ObjectId
    plan_snapshot: Dict[str, Any]  # Denormalized plan data
    status: SubscriptionStatus = SubscriptionStatus.PENDING
    interviews_allowed: int = 0
    interviews_remaining: int = 0
    interviews_used: int = 0
    started_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    payment_id: Optional[ObjectId] = None
    razorpay_order_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    _id: Optional[ObjectId] = None

    @property
    def is_active(self) -> bool:
        """Check if subscription is currently active and not expired"""
        if self.status != SubscriptionStatus.ACTIVE:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True

    @property
    def is_unlimited(self) -> bool:
        """Check if subscription has unlimited interviews"""
        return self.interviews_allowed == -1

    @property
    def can_use_interview(self) -> bool:
        """Check if employer can conduct another interview"""
        if not self.is_active:
            return False
        if self.is_unlimited:
            return True
        return self.interviews_remaining > 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage"""
        data = {
            "employer_id": self.employer_id,
            "plan_id": self.plan_id,
            "plan_snapshot": self.plan_snapshot,
            "status": (
                self.status.value
                if isinstance(self.status, SubscriptionStatus)
                else self.status
            ),
            "interviews_allowed": self.interviews_allowed,
            "interviews_remaining": self.interviews_remaining,
            "interviews_used": self.interviews_used,
            "started_at": self.started_at,
            "expires_at": self.expires_at,
            "payment_id": self.payment_id,
            "razorpay_order_id": self.razorpay_order_id,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self._id:
            data["_id"] = self._id
        return data

    def to_api_response(self) -> Dict[str, Any]:
        """Convert to API response format"""
        # Support both old (price_cents) and new (price_paise) field names
        price_in_smallest = self.plan_snapshot.get(
            "price_paise", self.plan_snapshot.get("price_cents", 0)
        )
        usage_cost_total = 0.0
        if isinstance(self.metadata, dict):
            usage_cost_total = float(
                self.metadata.get("usage_cost_total_usd", 0.0) or 0.0
            )

        return {
            "id": str(self._id) if self._id else None,
            "plan": {
                "name": self.plan_snapshot.get("name"),
                "slug": self.plan_snapshot.get("slug"),
                "price": price_in_smallest / 100,
                "currency": "INR",
            },
            "status": (
                self.status.value
                if isinstance(self.status, SubscriptionStatus)
                else self.status
            ),
            "interviews_allowed": self.interviews_allowed,
            "interviews_remaining": self.interviews_remaining,
            "interviews_used": self.interviews_used,
            "credits_allocated": self.interviews_allowed,
            "credits_remaining": self.interviews_remaining,
            "credits_used": self.interviews_used,
            "usage_cost_total_usd": round(usage_cost_total, 6),
            "is_unlimited": self.is_unlimited,
            "is_active": self.is_active,
            "can_use_interview": self.can_use_interview,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Subscription":
        """Create Subscription from dictionary"""
        status = data.get("status", "pending")
        if isinstance(status, str):
            status = SubscriptionStatus(status)

        return cls(
            employer_id=data.get("employer_id"),
            plan_id=data.get("plan_id"),
            plan_snapshot=data.get("plan_snapshot", {}),
            status=status,
            interviews_allowed=data.get("interviews_allowed", 0),
            interviews_remaining=data.get("interviews_remaining", 0),
            interviews_used=data.get("interviews_used", 0),
            started_at=data.get("started_at"),
            expires_at=data.get("expires_at"),
            payment_id=data.get("payment_id"),
            razorpay_order_id=data.get("razorpay_order_id"),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", datetime.utcnow()),
            updated_at=data.get("updated_at", datetime.utcnow()),
            _id=data.get("_id"),
        )


class SubscriptionSchema:
    """
    MongoDB schema definition and index management for Subscriptions collection.

    Indexes:
    1. employer_id: Fast lookup of employer's subscriptions
    2. (employer_id, status): Find active subscription for employer
    3. expires_at: Background job to expire subscriptions
    4. razorpay_order_id (unique, sparse): Webhook idempotency
    5. (status, expires_at): Bulk status updates
    """

    COLLECTION_NAME = "subscriptions"

    INDEXES = [
        {"keys": [("employer_id", 1)], "name": "idx_subscription_employer"},
        {
            "keys": [("employer_id", 1), ("status", 1)],
            "name": "idx_subscription_employer_status",
        },
        {"keys": [("expires_at", 1)], "name": "idx_subscription_expires"},
        {
            "keys": [("razorpay_order_id", 1)],
            "unique": True,
            "sparse": True,
            "name": "idx_subscription_razorpay_order",
        },
        {
            "keys": [("status", 1), ("expires_at", 1)],
            "name": "idx_subscription_status_expires",
        },
        {"keys": [("plan_id", 1)], "name": "idx_subscription_plan"},
    ]

    @classmethod
    def create_indexes(cls, db):
        """Create indexes on the subscriptions collection"""
        collection = db[cls.COLLECTION_NAME]
        for index in cls.INDEXES:
            keys = index.pop("keys")
            collection.create_index(keys, **index)
            index["keys"] = keys  # Restore for potential re-use
