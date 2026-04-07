"""
Plan Model - Represents pricing plans for the hiring platform

Design Decisions:
1. Price stored in paise (integer) to avoid floating point issues (1 INR = 100 paise)
2. credits_allocated = -1 indicates unlimited credits
3. Soft delete via is_active flag for data integrity
4. Compound index on (slug, is_active) for efficient lookups
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
        name: Display name (e.g., "Free Tier", "Recruiter Pro", "Recruiter Max")
        slug: URL-friendly identifier (e.g., "free", "professional", "recruiter-max")
        description: Marketing description
        price_paise: Price in paise (99900 = ₹999.00)
        credits_allocated: Number of credits, -1 for unlimited
        validity_days: How long the plan is valid after purchase
        features: List of feature descriptions for display
        is_active: Whether plan is available for purchase
        display_order: Sort order for display
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    name: str
    slug: str
    description: str
    price_paise: int
    credits_allocated: int
    validity_days: int
    features: List[str] = field(default_factory=list)
    audience: str = "recruiter"
    is_popular: bool = False
    is_active: bool = True
    display_order: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    _id: Optional[ObjectId] = None

    @property
    def price_rupees(self) -> float:
        """Convert paise to rupees for display"""
        return self.price_paise / 100

    @property
    def is_unlimited(self) -> bool:
        """Check if plan has unlimited credits"""
        return self.credits_allocated == -1

    @property
    def interviews_allowed(self) -> int:
        """Legacy alias kept for compatibility."""
        return self.credits_allocated

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage"""
        data = {
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "price_paise": self.price_paise,
            "credits_allocated": self.credits_allocated,
            "interviews_allowed": self.interviews_allowed,
            "validity_days": self.validity_days,
            "features": self.features,
            "audience": self.audience,
            "is_popular": self.is_popular,
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
            "price": self.price_rupees,
            "price_paise": self.price_paise,
            "currency": "INR",
            "credits_allocated": self.credits_allocated,
            "interviews_allowed": self.interviews_allowed,
            "is_unlimited": self.is_unlimited,
            "validity_days": self.validity_days,
            "features": self.features,
            "audience": self.audience,
            "is_popular": self.is_popular,
            "display_order": self.display_order,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Plan":
        """Create Plan from dictionary (supports both old price_cents and new price_paise)"""
        # Support both old field name (price_cents) and new (price_paise) for backward compatibility
        price = data.get("price_paise", data.get("price_cents", 0))
        return cls(
            name=data.get("name", ""),
            slug=data.get("slug", ""),
            description=data.get("description", ""),
            price_paise=price,
            credits_allocated=data.get(
                "credits_allocated",
                data.get("interviews_allowed", 0),
            ),
            validity_days=data.get("validity_days", 30),
            features=data.get("features", []),
            audience=data.get("audience", "recruiter"),
            is_popular=data.get("is_popular", False),
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
    """

    COLLECTION_NAME = "plans"

    INDEXES = [
        {"keys": [("slug", 1)], "unique": True, "name": "idx_plan_slug_unique"},
        {
            "keys": [("audience", 1), ("is_active", 1), ("display_order", 1)],
            "name": "idx_plan_audience_active_order",
        },
        {
            "keys": [("is_active", 1), ("display_order", 1)],
            "name": "idx_plan_active_order",
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
