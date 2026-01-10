"""
Payment Model - Records all payment transactions

Design Decisions:
1. Idempotency key for safe retries (Stripe best practice)
2. Store full Stripe response for debugging/disputes
3. Amount in cents (consistent with Plan model)
4. Reference to subscription for linking
5. Support refunds with separate records
6. Payment status separate from subscription status
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
from bson import ObjectId


class PaymentStatus(Enum):
    """
    Payment transaction states:
    - PENDING: Checkout initiated, awaiting completion
    - PROCESSING: Payment submitted, awaiting confirmation
    - SUCCEEDED: Payment confirmed by Stripe
    - FAILED: Payment declined or errored
    - REFUNDED: Full refund processed
    - PARTIALLY_REFUNDED: Partial refund processed
    - CANCELLED: User cancelled before completion
    - DISPUTED: Chargeback initiated
    """

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    CANCELLED = "cancelled"
    DISPUTED = "disputed"


@dataclass
class Payment:
    """
    Represents a payment transaction.

    Attributes:
        employer_id: Reference to users collection
        subscription_id: Reference to subscriptions collection
        plan_id: Reference to plans collection
        amount_cents: Payment amount in cents
        currency: ISO currency code (e.g., 'usd')
        status: Current payment status
        stripe_session_id: Stripe Checkout Session ID
        stripe_payment_intent_id: Stripe PaymentIntent ID
        stripe_charge_id: Stripe Charge ID (for refunds)
        stripe_customer_id: Stripe Customer ID
        idempotency_key: Unique key for safe retries
        stripe_response: Full Stripe API response (for debugging)
        refund_amount_cents: Amount refunded (if any)
        refund_reason: Reason for refund
        failure_reason: Why payment failed (if applicable)
        metadata: Additional payment data
        created_at: Transaction initiation time
        updated_at: Last status change time
        completed_at: When payment succeeded/failed
    """

    employer_id: ObjectId
    plan_id: ObjectId
    amount_cents: int
    currency: str = "usd"
    status: PaymentStatus = PaymentStatus.PENDING
    subscription_id: Optional[ObjectId] = None
    stripe_session_id: Optional[str] = None
    stripe_payment_intent_id: Optional[str] = None
    stripe_charge_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    stripe_response: Optional[Dict[str, Any]] = None
    refund_amount_cents: int = 0
    refund_reason: Optional[str] = None
    failure_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    _id: Optional[ObjectId] = None

    @property
    def amount_dollars(self) -> float:
        """Convert cents to dollars"""
        return self.amount_cents / 100

    @property
    def refund_amount_dollars(self) -> float:
        """Convert refund cents to dollars"""
        return self.refund_amount_cents / 100

    @property
    def is_successful(self) -> bool:
        """Check if payment was successful"""
        return self.status == PaymentStatus.SUCCEEDED

    @property
    def is_refundable(self) -> bool:
        """Check if payment can be refunded"""
        return (
            self.status == PaymentStatus.SUCCEEDED and self.stripe_charge_id is not None
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage"""
        data = {
            "employer_id": self.employer_id,
            "subscription_id": self.subscription_id,
            "plan_id": self.plan_id,
            "amount_cents": self.amount_cents,
            "currency": self.currency,
            "status": (
                self.status.value
                if isinstance(self.status, PaymentStatus)
                else self.status
            ),
            "stripe_session_id": self.stripe_session_id,
            "stripe_payment_intent_id": self.stripe_payment_intent_id,
            "stripe_charge_id": self.stripe_charge_id,
            "stripe_customer_id": self.stripe_customer_id,
            "idempotency_key": self.idempotency_key,
            "stripe_response": self.stripe_response,
            "refund_amount_cents": self.refund_amount_cents,
            "refund_reason": self.refund_reason,
            "failure_reason": self.failure_reason,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }
        if self._id:
            data["_id"] = self._id
        return data

    def to_api_response(self) -> Dict[str, Any]:
        """Convert to API response format (excludes sensitive data)"""
        return {
            "id": str(self._id) if self._id else None,
            "subscription_id": (
                str(self.subscription_id) if self.subscription_id else None
            ),
            "amount": self.amount_dollars,
            "currency": self.currency,
            "status": (
                self.status.value
                if isinstance(self.status, PaymentStatus)
                else self.status
            ),
            "refund_amount": (
                self.refund_amount_dollars if self.refund_amount_cents > 0 else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Payment":
        """Create Payment from dictionary"""
        status = data.get("status", "pending")
        if isinstance(status, str):
            status = PaymentStatus(status)

        return cls(
            employer_id=data.get("employer_id"),
            subscription_id=data.get("subscription_id"),
            plan_id=data.get("plan_id"),
            amount_cents=data.get("amount_cents", 0),
            currency=data.get("currency", "usd"),
            status=status,
            stripe_session_id=data.get("stripe_session_id"),
            stripe_payment_intent_id=data.get("stripe_payment_intent_id"),
            stripe_charge_id=data.get("stripe_charge_id"),
            stripe_customer_id=data.get("stripe_customer_id"),
            idempotency_key=data.get("idempotency_key"),
            stripe_response=data.get("stripe_response"),
            refund_amount_cents=data.get("refund_amount_cents", 0),
            refund_reason=data.get("refund_reason"),
            failure_reason=data.get("failure_reason"),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", datetime.utcnow()),
            updated_at=data.get("updated_at", datetime.utcnow()),
            completed_at=data.get("completed_at"),
            _id=data.get("_id"),
        )


class PaymentSchema:
    """
    MongoDB schema definition and index management for Payments collection.

    Indexes:
    1. employer_id: List employer's payments
    2. subscription_id: Find payments for subscription
    3. stripe_session_id (unique, sparse): Webhook idempotency
    4. stripe_payment_intent_id (unique, sparse): PI lookup
    5. idempotency_key (unique, sparse): Retry safety
    6. (status, created_at): Analytics and reporting
    7. stripe_charge_id: Refund processing
    """

    COLLECTION_NAME = "payments"

    INDEXES = [
        {"keys": [("employer_id", 1)], "name": "idx_payment_employer"},
        {"keys": [("subscription_id", 1)], "name": "idx_payment_subscription"},
        {
            "keys": [("stripe_session_id", 1)],
            "unique": True,
            "sparse": True,
            "name": "idx_payment_stripe_session",
        },
        {
            "keys": [("stripe_payment_intent_id", 1)],
            "unique": True,
            "sparse": True,
            "name": "idx_payment_stripe_intent",
        },
        {
            "keys": [("idempotency_key", 1)],
            "unique": True,
            "sparse": True,
            "name": "idx_payment_idempotency",
        },
        {
            "keys": [("status", 1), ("created_at", -1)],
            "name": "idx_payment_status_created",
        },
        {
            "keys": [("stripe_charge_id", 1)],
            "sparse": True,
            "name": "idx_payment_stripe_charge",
        },
        {"keys": [("plan_id", 1)], "name": "idx_payment_plan"},
    ]

    @classmethod
    def create_indexes(cls, db):
        """Create indexes on the payments collection"""
        collection = db[cls.COLLECTION_NAME]
        for index in cls.INDEXES:
            keys = index.pop("keys")
            collection.create_index(keys, **index)
            index["keys"] = keys  # Restore for potential re-use
