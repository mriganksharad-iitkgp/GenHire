"""
Plan Model - Represents pricing plans for the hiring platform

Design Decisions:
1. Price stored in cents (integer) to avoid floating point issues
2. interviews_allowed = -1 indicates unlimited interviews
3. Soft delete via is_active flag for data integrity
4. Stripe product/price IDs stored for direct integration
5. Compound index on (slug, is_active) for efficient lookups
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId


@dataclass
class Plan:
    """
    Represents a hiring plan that employers can purchase.

    Attributes:
        name: Display name (e.g., "Starter", "Growth", "Enterprise")
        slug: URL-friendly identifier (e.g., "starter", "growth")
        description: Marketing description
        price_cents: Price in cents (4900 = $49.00)
        interviews_allowed: Number of interviews, -1 for unlimited
        validity_days: How long the plan is valid after purchase
        features: List of feature descriptions for display
        stripe_product_id: Stripe Product ID for this plan
        stripe_price_id: Stripe Price ID for checkout
        is_active: Whether plan is available for purchase
        display_order: Sort order for display
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    name: str
    slug: str
    description: str
    price_cents: int
    interviews_allowed: int
    validity_days: int
    features: List[str] = field(default_factory=list)
    stripe_product_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    is_active: bool = True
    display_order: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    _id: Optional[ObjectId] = None

    @property
    def price_dollars(self) -> float:
        """Convert cents to dollars for display"""
        return self.price_cents / 100

    @property
    def is_unlimited(self) -> bool:
        """Check if plan has unlimited interviews"""
        return self.interviews_allowed == -1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage"""
        data = {
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "price_cents": self.price_cents,
            "interviews_allowed": self.interviews_allowed,
            "validity_days": self.validity_days,
            "features": self.features,
            "stripe_product_id": self.stripe_product_id,
            "stripe_price_id": self.stripe_price_id,
            "is_active": self.is_active,
            "display_order": self.display_order,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self._id:
            data["_id"] = self._id
        return data

    def to_api_response(self) -> Dict[str, Any]:
        """Convert to API response (excludes internal fields)"""
        return {
            "id": str(self._id) if self._id else None,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "price": self.price_dollars,
            "price_cents": self.price_cents,
            "interviews_allowed": self.interviews_allowed,
            "is_unlimited": self.is_unlimited,
            "validity_days": self.validity_days,
            "features": self.features,
            "display_order": self.display_order,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Plan":
        """Create Plan from dictionary"""
        return cls(
            name=data.get("name", ""),
            slug=data.get("slug", ""),
            description=data.get("description", ""),
            price_cents=data.get("price_cents", 0),
            interviews_allowed=data.get("interviews_allowed", 0),
            validity_days=data.get("validity_days", 30),
            features=data.get("features", []),
            stripe_product_id=data.get("stripe_product_id"),
            stripe_price_id=data.get("stripe_price_id"),
            is_active=data.get("is_active", True),
            display_order=data.get("display_order", 0),
            created_at=data.get("created_at", datetime.utcnow()),
            updated_at=data.get("updated_at", datetime.utcnow()),
            _id=data.get("_id"),
        )


class PlanSchema:
    """
    MongoDB schema definition and index management for Plans collection.

    Indexes:
    1. slug (unique): Fast lookups by plan identifier
    2. (is_active, display_order): Efficient listing of active plans
    3. stripe_price_id: Webhook processing lookup
    """

    COLLECTION_NAME = "plans"

    INDEXES = [
        {"keys": [("slug", 1)], "unique": True, "name": "idx_plan_slug_unique"},
        {
            "keys": [("is_active", 1), ("display_order", 1)],
            "name": "idx_plan_active_order",
        },
        {
            "keys": [("stripe_price_id", 1)],
            "sparse": True,
            "name": "idx_plan_stripe_price",
        },
    ]

    @classmethod
    def create_indexes(cls, db):
        """Create indexes on the plans collection"""
        collection = db[cls.COLLECTION_NAME]
        for index in cls.INDEXES:
            keys = index.pop("keys")
            collection.create_index(keys, **index)
            index["keys"] = keys  # Restore for potential re-use
