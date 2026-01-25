"""
Plan Model - Represents pricing plans for the hiring platform

Design Decisions:
1. Price stored in paise (integer) to avoid floating point issues (1 INR = 100 paise)
2. interviews_allowed = -1 indicates unlimited interviews
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
        name: Display name (e.g., "Starter", "Growth", "Enterprise")
        slug: URL-friendly identifier (e.g., "starter", "growth")
        description: Marketing description
        price_paise: Price in paise (99900 = ₹999.00)
        interviews_allowed: Number of interviews, -1 for unlimited
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
    interviews_allowed: int
    validity_days: int
    features: List[str] = field(default_factory=list)
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
        """Check if plan has unlimited interviews"""
        return self.interviews_allowed == -1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage"""
        data = {
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "price_paise": self.price_paise,
            "interviews_allowed": self.interviews_allowed,
            "validity_days": self.validity_days,
            "features": self.features,
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
            "interviews_allowed": self.interviews_allowed,
            "is_unlimited": self.is_unlimited,
            "validity_days": self.validity_days,
            "features": self.features,
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
            interviews_allowed=data.get("interviews_allowed", 0),
            validity_days=data.get("validity_days", 30),
            features=data.get("features", []),
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
