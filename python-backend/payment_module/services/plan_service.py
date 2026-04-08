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
        self._backfill_plan_monthly_credits()
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
                    interviews_allowed=plan_data["interviews_allowed"],
                    monthly_credits=plan_data["monthly_credits"],
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
                    interviews_allowed=plan_data["interviews_allowed"],
                    monthly_credits=plan_data["monthly_credits"],
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
                        "description": "Advanced recruiter plan with 300 interviews per month",
                        "price_paise": 999900,
                        "interviews_allowed": 300,
                        "monthly_credits": 60000,
                        "validity_days": 30,
                        "audience": "recruiter",
                        "display_order": 3,
                        "updated_at": now,
                        "features": [
                            "300 AI-powered interviews/month",
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

    def _backfill_plan_monthly_credits(self):
        """Backfill missing monthly credits from defaults (or interview limits as fallback)."""
        try:
            defaults_by_slug = {
                payload["slug"]: int(
                    payload.get("monthly_credits", payload.get("interviews_allowed", 0))
                    or 0
                )
                for payload in PaymentConfig.DEFAULT_PLANS.values()
            }

            updated = 0
            for plan in self.collection.find(
                {"monthly_credits": {"$exists": False}},
                {"_id": 1, "slug": 1, "interviews_allowed": 1},
            ):
                fallback = int(plan.get("interviews_allowed", 0) or 0)
                credits = int(defaults_by_slug.get(plan.get("slug"), fallback))
                result = self.collection.update_one(
                    {"_id": plan["_id"]},
                    {
                        "$set": {
                            "monthly_credits": credits,
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )
                updated += result.modified_count

            if updated:
                logger.info(f"Backfilled monthly credits on {updated} legacy plans")
        except Exception as e:
            logger.error(f"Error backfilling monthly credits: {str(e)}")

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
        monthly_credits: Optional[int] = None,
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
            interviews_allowed: Number of interviews (-1 for unlimited)
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
                interviews_allowed=interviews_allowed,
                monthly_credits=(
                    monthly_credits
                    if monthly_credits is not None
                    else interviews_allowed
                ),
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
