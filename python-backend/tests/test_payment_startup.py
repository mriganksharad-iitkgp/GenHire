"""HTTP startup must not scan wallets; maintenance must retain bonus rules.

All database work uses mongomock or mocks; no network or private dotenv inputs.
"""
from contextlib import ExitStack
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from flask import Blueprint
import mongomock

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def module(name, **attributes):
    result = types.ModuleType(name)
    result.__dict__.update(attributes)
    return result


class PaymentStartupTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {
            "FLASK_ENV": "development", "FLASK_SECRET_KEY": "test-only-secret",
            "JWT_SECRET_KEY": "test-only-jwt-secret", "REDIS_URL": "",
            "RATE_LIMIT_REQUIRE_REDIS": "false", "FORCE_HTTPS": "false",
            "GENHIRE_DISABLE_JOBS": "1", "RAZORPAY_KEY_ID": "",
            "RAZORPAY_KEY_SECRET": "", "SENTRY_DSN": "",
        }, clear=True))
        self.stack.enter_context(patch("dotenv.load_dotenv", return_value=False))
        self.stack.enter_context(patch.dict(sys.modules, {
            "middleware.auth_middleware": module("middleware.auth_middleware",
                token_required=lambda view: view, recruiter_required=lambda view: view),
        }))
        from payment_module.services.wallet_service import WalletService
        self.wallet_type = WalletService
        self.stack.enter_context(patch.object(WalletService, "_indexes_created", False))

    def test_application_is_ready_without_reading_historical_accounts(self):
        database = MagicMock()
        database["users"].find.side_effect = AssertionError("Historical account scan blocks startup")
        db_config = MagicMock()
        db_config.connect.return_value = database
        db_config.get_collections.return_value = {"users": database["users"]}
        stubs = {
            "config.database": module("config.database", db_config=db_config),
            "core.extensions": module("core.extensions", socketio=MagicMock()),
            "controllers.admin_controller": module("controllers.admin_controller", AdminController=MagicMock()),
            "jobs.runner": module("jobs.runner", start_all=MagicMock()),
            "sockets": module("sockets", register_all=MagicMock()),
            "interview.runtime": module("interview.runtime", PROCTORING_FOLDER="test-only",
                RECORDING_FOLDER="test-only", TMP_FOLDER="test-only", interview_manager=MagicMock()),
        }
        for route, symbol in {
            "auth": "auth_bp", "profile": "profile_bp", "job": "job_bp",
            "application": "application_bp", "file": "file_bp", "practice": "practice_bp",
            "admin": "admin_bp", "invite": "invite_bp", "identity": "identity_bp",
            "speech": "speech_bp", "interview": "interview_bp",
        }.items():
            name = f"routes.{route}_routes"
            stubs[name] = module(name, **{symbol: Blueprint(f"test_{route}", __name__)})
        stubs["routes.admin_routes"].init_admin_routes = MagicMock()
        stubs["routes.interview_routes"].init_interview_routes = MagicMock()
        stubs["routes.cv_routes"] = module("routes.cv_routes",
            create_cv_routes=lambda collections: Blueprint("test_cv", __name__))
        stubs["routes.cost_routes"] = module("routes.cost_routes",
            create_cost_routes=lambda db: Blueprint("test_cost", __name__))

        spec = importlib.util.spec_from_file_location("_payment_startup_factory", BACKEND / "core/factory.py")
        factory = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, stubs), \
                patch("config.env_loader.load_environment"), \
                patch("services.gcs_service.is_gcs_configured", return_value=True), \
                patch.object(self.wallet_type, "bootstrap_signup_bonus_for_all_users") as scan:
            spec.loader.exec_module(factory)
            app = factory.create_app()
            client = app.test_client()
            self.assertEqual(client.get("/health").status_code, 200)
            self.assertEqual(client.get("/api/payment/health").status_code, 200)
        scan.assert_not_called()
        database["users"].find.assert_not_called()

    def load_backfill(self):
        spec = importlib.util.spec_from_file_location("_bonus_backfill", BACKEND / "scripts/migrations/backfill_signup_bonuses.py")
        backfill = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(backfill)
        return backfill.backfill

    def test_default_maintenance_inventory_is_read_only_and_excludes_invites(self):
        db = mongomock.MongoClient().db
        db.users.insert_many([{"email": "candidate@example.test"}, {"is_invite_only": True}])
        before = db.list_collection_names()
        self.assertEqual(self.load_backfill()(db), {"eligible_accounts": 1})
        self.assertEqual(db.list_collection_names(), before)

    def test_pack_sync_runs_once_per_database_but_retries_after_failure(self):
        from payment_module.services.plan_service import PlanService
        client = mongomock.MongoClient()
        with patch.object(PlanService, "_ensure_indexes", return_value=True), \
                patch.object(PlanService, "_seed_default_plans", side_effect=[False, True, True]) as seed, \
                patch.object(PlanService, "_remove_plan_usage_fields", return_value=True):
            PlanService(client.primary); PlanService(client.primary); PlanService(client.primary)
            self.assertEqual(seed.call_count, 2)
            PlanService(client.another)
            self.assertEqual(seed.call_count, 3)

    def test_real_pack_sync_preserves_prices_and_existing_wallets(self):
        from payment_module.services.plan_service import PlanService
        from payment_module.config.settings import PaymentConfig
        db = mongomock.MongoClient().db
        db.credit_wallets.insert_one({"owner_id": "existing", "balance": 83})
        service = PlanService(db)
        before = list(service.collection.find())
        PlanService(db)
        self.assertEqual(list(service.collection.find()), before)
        self.assertEqual(db.credit_wallets.find_one({"owner_id": "existing"})["balance"], 83)
        for configured in PaymentConfig.DEFAULT_PLANS.values():
            stored = service.collection.find_one({"slug": configured["slug"]})
            self.assertEqual(stored["price_paise"], configured["price_paise"])

    def test_explicit_backfill_is_idempotent_and_preserves_signup_exclusions(self):
        db = mongomock.MongoClient().db
        db.users.insert_many([
            {"_id": "candidate", "user_type": "candidate", "email": "candidate@example.test"},
            {"_id": "recruiter", "user_type": "recruiter", "email": "recruiter@example.test"},
            {"_id": "invite", "user_type": "candidate", "is_invite_only": True},
        ])
        backfill = self.load_backfill()
        self.assertEqual(backfill(db, apply=True), {"granted": 2, "skipped": 0})
        balances = list(db.credit_wallets.find({}, {"_id": 0, "owner_id": 1, "balance": 1}))
        self.assertEqual(backfill(db, apply=True), {"granted": 0, "skipped": 2})
        self.assertEqual(list(db.credit_wallets.find({}, {"_id": 0, "owner_id": 1, "balance": 1})), balances)
        self.assertIsNone(db.credit_wallets.find_one({"owner_id": "invite"}))

        db.users.delete_one({"_id": "candidate"})
        db.users.insert_one({"_id": "recreated", "user_type": "candidate", "email": "candidate@example.test"})
        self.assertEqual(backfill(db, apply=True), {"granted": 0, "skipped": 2})
        self.assertEqual(db.credit_wallets.find_one({"owner_id": "recreated"})["balance"], 0)


if __name__ == "__main__":
    unittest.main()
