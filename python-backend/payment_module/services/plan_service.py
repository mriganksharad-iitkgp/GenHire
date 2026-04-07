"""
Plan Service - Business logic for plan management

Design Decisions:
1. Seed default plans on first access
2. Cache plans in memory (low-frequency updates)
3. Sync with Stripe on plan creation/update
4. Soft delete for audit trail
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId
from pymongo import ASCENDING

from ..models.plan import Plan, PlanSchema
from ..config.settings import PaymentConfig

logger = logging.getLogger(__name__)


class PlanService:
    """
    Service for managing pricing plans.

    Handles:
    - CRUD operations for plans
    - Default plan seeding
    - Plan validation
    """

    def __init__(self, db):
        """
        Initialize with database connection.

        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.collection = db[PlanSchema.COLLECTION_NAME]
        self._ensure_indexes()
        self._seed_default_plans()
        self._ensure_default_plans_exist()
        self._backfill_plan_audience()
        self._remove_plan_usage_fields()
        self._migrate_legacy_candidate_plans()
        self._migrate_legacy_enterprise_to_recruiter_max()

    def _ensure_indexes(self):
        """Create indexes if they don't exist"""
        try:
            PlanSchema.create_indexes(self.db)
            logger.info("Plan indexes ensured")
        except Exception as e:
            logger.error(f"Error creating plan indexes: {str(e)}")

    def _seed_default_plans(self):
        """
        Seed default plans if none exist.

        This ensures the system has usable plans on first deployment.
        """
        try:
            existing = self.collection.count_documents({"is_active": True})
            if existing > 0:
                logger.info(f"Found {existing} existing plans, skipping seed")
                return

            logger.info("Seeding default plans...")

            for slug, plan_data in PaymentConfig.DEFAULT_PLANS.items():
                plan = Plan(
                    name=plan_data["name"],
                    slug=plan_data["slug"],
                    description=plan_data["description"],
                    price_paise=plan_data["price_paise"],
                    credits_allocated=plan_data.get(
                        "credits_allocated", plan_data.get("interviews_allowed", 0)
                    ),
                    validity_days=plan_data["validity_days"],
                    features=plan_data["features"],
                    is_active=plan_data["is_active"],
                    display_order=plan_data["display_order"],
                )

                self.collection.insert_one(plan.to_dict())
                logger.info(f"Seeded plan: {plan.name}")

            logger.info("Default plans seeded successfully")

        except Exception as e:
            logger.error(f"Error seeding plans: {str(e)}")

    def _ensure_default_plans_exist(self):
        """Ensure every configured default plan exists by slug (safe additive seed)."""
        try:
            for _, plan_data in PaymentConfig.DEFAULT_PLANS.items():
                existing = self.collection.find_one({"slug": plan_data["slug"]})
                if existing:
                    continue

                plan = Plan(
                    name=plan_data["name"],
                    slug=plan_data["slug"],
                    description=plan_data["description"],
                    price_paise=plan_data["price_paise"],
                    credits_allocated=plan_data.get(
                        "credits_allocated", plan_data.get("interviews_allowed", 0)
                    ),
                    validity_days=plan_data["validity_days"],
                    features=plan_data["features"],
                    audience=plan_data.get("audience", "recruiter"),
                    is_popular=plan_data.get("is_popular", False),
                    is_active=plan_data["is_active"],
                    display_order=plan_data["display_order"],
                )

                self.collection.insert_one(plan.to_dict())
                logger.info(f"Added missing default plan: {plan.name} ({plan.slug})")
        except Exception as e:
            logger.error(f"Error ensuring default plans: {str(e)}")

    def _backfill_plan_audience(self):
        """Backfill missing audience for legacy plans as recruiter."""
        try:
            result = self.collection.update_many(
                {"audience": {"$exists": False}},
                {"$set": {"audience": "recruiter", "updated_at": datetime.utcnow()}},
            )
            if result.modified_count:
                logger.info(
                    f"Backfilled audience on {result.modified_count} legacy plans"
                )
        except Exception as e:
            logger.error(f"Error backfilling plan audience: {str(e)}")

    def _migrate_legacy_candidate_plans(self):
        """Normalize legacy candidate plans to the current credit-based defaults."""
        try:
            now = datetime.utcnow()
            candidate_defaults = {
                "candidate-free": {
                    "name": "Free Tier",
                    "description": "Free plan with 1,500 practice credits per month",
                    "credits_allocated": 1500,
                    "price_paise": 0,
                    "features": [
                        "1,500 Practice Credits/month",
                        "Smart practice feedback",
                        "Basic interview analytics",
                    ],
                    "is_popular": False,
                    "display_order": 1,
                },
                "candidate-pro": {
                    "name": "Candidate Pro",
                    "description": "30,000 practice credits per month for active preparation",
                    "credits_allocated": 30000,
                    "price_paise": 99900,
                    "features": [
                        "30,000 Practice Credits/month",
                        "Detailed interview scoring",
                        "Priority report generation",
                    ],
                    "is_popular": True,
                    "display_order": 2,
                },
                "candidate-max": {
                    "name": "Candidate Max",
                    "description": "70,000 practice credits per month for intensive preparation",
                    "credits_allocated": 70000,
                    "price_paise": 149900,
                    "features": [
                        "70,000 Practice Credits/month",
                        "Advanced analytics dashboard",
                        "Priority support",
                    ],
                    "is_popular": False,
                    "display_order": 3,
                },
            }

            for slug, defaults in candidate_defaults.items():
                result = self.collection.update_one(
                    {"slug": slug, "audience": "candidate"},
                    {
                        "$set": {
                            "name": defaults["name"],
                            "description": defaults["description"],
                            "price_paise": defaults["price_paise"],
                            "credits_allocated": defaults["credits_allocated"],
                            "interviews_allowed": defaults["credits_allocated"],
                            "validity_days": 30,
                            "features": defaults["features"],
                            "is_popular": defaults["is_popular"],
                            "display_order": defaults["display_order"],
                            "updated_at": now,
                        }
                    },
                )

                if result.modified_count:
                    logger.info(f"Normalized candidate plan defaults for {slug}")
        except Exception as e:
            logger.error(f"Error normalizing candidate plans: {str(e)}")

    def _remove_plan_usage_fields(self):
        """Remove runtime usage fields from plan templates; these belong to subscriptions."""
        try:
            result = self.collection.update_many(
                {
                    "$or": [
                        {"credits_remaining": {"$exists": True}},
                        {"credits_used": {"$exists": True}},
                    ]
                },
                {
                    "$unset": {
                        "credits_remaining": "",
                        "credits_used": "",
                    },
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )
            if result.modified_count:
                logger.info(
                    f"Removed runtime usage fields from {result.modified_count} plan template(s)"
                )
        except Exception as e:
            logger.error(f"Error removing plan usage fields: {str(e)}")

    def _migrate_legacy_enterprise_to_recruiter_max(self):
        """Remove legacy recruiter enterprise plans and enforce recruiter-max defaults."""
        try:
            now = datetime.utcnow()
            max_result = self.collection.update_one(
                {"slug": "recruiter-max", "audience": "recruiter"},
                {
                    "$set": {
                        "name": "Recruiter Max",
                        "slug": "recruiter-max",
                        "description": "Advanced recruiter plan with 180,000 credits per month",
                        "price_paise": 999900,
                        "credits_allocated": 180000,
                        "validity_days": 30,
                        "audience": "recruiter",
                        "display_order": 3,
                        "updated_at": now,
                        "features": [
                            "180,000 AI usage credits/month",
                            "Custom integrations",
                            "Advanced analytics and reporting",
                            "Custom branding",
                            "Priority support",
                        ],
                    }
                },
            )

            delete_result = self.collection.delete_many(
                {
                    "$or": [
                        {"slug": "enterprise"},
                        {"name": "Enterprise", "audience": "recruiter"},
                    ]
                }
            )

            if max_result.modified_count:
                logger.info("Normalized recruiter-max plan defaults")
            if delete_result.deleted_count:
                logger.info(
                    f"Deleted {delete_result.deleted_count} legacy enterprise plan(s)"
                )
        except Exception as e:
            logger.error(f"Error normalizing recruiter plans: {str(e)}")

    @staticmethod
    def _audience_filter(audience: Optional[str]) -> Dict[str, Any]:
        if audience == "recruiter":
            return {
                "$or": [
                    {"audience": "recruiter"},
                    {"audience": {"$exists": False}},
                ]
            }
        if audience == "candidate":
            return {"audience": "candidate"}
        return {}

    def get_all_active_plans(
        self, audience: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all active plans sorted by display order.

        Returns:
            List of plan API responses
        """
        try:
            filters = {"is_active": True}
            if audience in {"recruiter", "candidate"}:
                filters.update(self._audience_filter(audience))

            plans = self.collection.find(filters).sort("display_order", ASCENDING)

            return [Plan.from_dict(p).to_api_response() for p in plans]

        except Exception as e:
            logger.error(f"Error fetching plans: {str(e)}")
            return []

    def get_plan_by_id(
        self, plan_id: str, audience: Optional[str] = None
    ) -> Optional[Plan]:
        """
        Get plan by ID.

        Args:
            plan_id: Plan ObjectId string

        Returns:
            Plan object or None
        """
        try:
            filters = {"_id": ObjectId(plan_id), "is_active": True}
            filters.update(self._audience_filter(audience))
            plan_data = self.collection.find_one(filters)

            if plan_data:
                return Plan.from_dict(plan_data)
            return None

        except Exception as e:
            logger.error(f"Error fetching plan {plan_id}: {str(e)}")
            return None

    def get_plan_by_slug(
        self, slug: str, audience: Optional[str] = None
    ) -> Optional[Plan]:
        """
        Get plan by slug identifier.

        Args:
            slug: Plan slug (e.g., 'starter')

        Returns:
            Plan object or None
        """
        try:
            filters = {"slug": slug, "is_active": True}
            filters.update(self._audience_filter(audience))
            plan_data = self.collection.find_one(filters)

            if plan_data:
                return Plan.from_dict(plan_data)
            return None

        except Exception as e:
            logger.error(f"Error fetching plan by slug {slug}: {str(e)}")
            return None

    def create_plan(
        self,
        name: str,
        slug: str,
        description: str,
        price_paise: int,
        interviews_allowed: int,
        validity_days: int,
        features=None,
        display_order: int = 0,
        audience: str = "recruiter",
        is_popular: bool = False,
    ) -> Optional[Plan]:
        """
        Create a new plan.

        Args:
            name: Display name
            slug: URL-friendly identifier
            description: Marketing description
            price_paise: Price in paise (100 paise = 1 INR)
            interviews_allowed: Legacy alias for credits_allocated (-1 for unlimited)
            validity_days: Plan validity period
            features: List of feature strings
            display_order: Sort order

        Returns:
            Created Plan or None
        """
        try:
            # Check for duplicate slug
            existing = self.collection.find_one({"slug": slug})
            if existing:
                logger.warning(f"Plan with slug {slug} already exists")
                return None

            plan = Plan(
                name=name,
                slug=slug,
                description=description,
                price_paise=price_paise,
                credits_allocated=interviews_allowed,
                validity_days=validity_days,
                features=features or [],
                display_order=display_order,
                audience=audience,
                is_popular=is_popular,
            )

            result = self.collection.insert_one(plan.to_dict())
            plan._id = result.inserted_id

            logger.info(f"Created plan: {name} (ID: {result.inserted_id})")
            return plan

        except Exception as e:
            logger.error(f"Error creating plan: {str(e)}")
            return None

    def update_plan(self, plan_id: str, updates: Dict[str, Any]) -> Optional[Plan]:
        """
        Update plan fields.

        Args:
            plan_id: Plan ObjectId string
            updates: Fields to update

        Returns:
            Updated Plan or None
        """
        try:
            # Prevent updating certain fields
            protected_fields = ["_id", "slug", "created_at"]
            for field in protected_fields:
                updates.pop(field, None)

            updates["updated_at"] = datetime.utcnow()

            result = self.collection.find_one_and_update(
                {"_id": ObjectId(plan_id)}, {"$set": updates}, return_document=True
            )

            if result:
                return Plan.from_dict(result)
            return None

        except Exception as e:
            logger.error(f"Error updating plan {plan_id}: {str(e)}")
            return None

    def deactivate_plan(self, plan_id: str) -> bool:
        """
        Soft delete a plan (deactivate).

        Args:
            plan_id: Plan ObjectId string

        Returns:
            Success boolean
        """
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(plan_id)},
                {"$set": {"is_active": False, "updated_at": datetime.utcnow()}},
            )

            return result.modified_count > 0

        except Exception as e:
            logger.error(f"Error deactivating plan {plan_id}: {str(e)}")
            return False
