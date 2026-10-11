"""Concurrency/outage tests with isolated Mongo/Redis emulators; no external service calls."""
import importlib.util
import os
import sys
import threading
import time
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import fakeredis
import jwt
import mongomock
from bson import ObjectId
from flask import Flask
from pymongo.errors import DuplicateKeyError

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from middleware import rate_limiter as limits

SECRET = "test-only-robustness-signing-secret-32-bytes"


def isolated_module(name, relative, stubs):
    spec = importlib.util.spec_from_file_location(name, BACKEND / relative)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


class RequestProtectionTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {
            "FLASK_ENV": "development", "REDIS_URL": "", "RATE_LIMIT_REQUIRE_REDIS": "false",
            "API_MAX_INFLIGHT": "128", "RATE_LIMIT_APPLICATION_CALLS": "5",
            "RATE_LIMIT_MEMORY_KEYS": "20000", "TRUSTED_PROXY_HOPS": "0",
        })
        self.environment.start()
        self.counter = patch.object(limits, "store", limits.CounterStore())
        self.counter.start()
        self.secret = patch("core.security.get_jwt_secret", return_value=SECRET)
        self.secret.start()
        self.addCleanup(self.environment.stop)
        self.addCleanup(self.counter.stop)
        self.addCleanup(self.secret.stop)

    def app(self, handler=None):
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.add_url_rule("/jobs/<job>/apply", "apply_for_job",
                         handler or (lambda job: {"ok": True}), methods=["POST"])
        app.add_url_rule("/health", "health", lambda: {"ok": True})
        limits.install_request_protection(app)
        return app

    def headers(self, user="a" * 24):
        token = jwt.encode({"user_id": user, "exp": time.time() + 3600}, SECRET, algorithm="HS256")
        return {"Authorization": "Bearer " + token}

    def test_many_concurrent_attempts_only_allow_account_quota(self):
        app = self.app()
        def send(index):
            with app.test_client() as client:
                response = client.post(f"/jobs/job-{index}/apply", headers=self.headers())
                return response.status_code, response.headers.get("Retry-After")
        with ThreadPoolExecutor(max_workers=20) as pool:
            responses = list(pool.map(send, range(40)))
        self.assertEqual(sum(status == 200 for status, _ in responses), 5)
        self.assertEqual(sum(status == 429 for status, _ in responses), 35)
        self.assertTrue(all(int(retry) > 0 for status, retry in responses if status == 429))

    def test_accounts_on_same_ip_have_independent_action_budgets(self):
        with self.app().test_client() as client:
            for _ in range(5):
                self.assertEqual(client.post("/jobs/one/apply", headers=self.headers()).status_code, 200)
            self.assertEqual(client.post("/jobs/two/apply", headers=self.headers()).status_code, 429)
            self.assertEqual(client.post("/jobs/two/apply", headers=self.headers("b" * 24)).status_code, 200)

    def test_forged_forwarded_headers_do_not_reset_network_identity(self):
        with self.app().test_client() as client:
            results = [client.post("/jobs/one/apply", headers={"X-Forwarded-For": f"192.0.2.{i}"})
                       for i in range(6)]
        self.assertEqual(results[-1].status_code, 429)

    def test_invalid_jwt_cannot_choose_its_own_account_bucket(self):
        with self.app().test_client() as client:
            results = []
            for i in range(6):
                fake = jwt.encode({"user_id": str(i).zfill(24)}, "incorrect-secret", algorithm="HS256")
                results.append(client.post("/jobs/one/apply", headers={"Authorization": "Bearer " + fake}))
        self.assertEqual(results[-1].status_code, 429)

    def test_options_and_health_do_not_consume_action_quota(self):
        with self.app().test_client() as client:
            for _ in range(12):
                self.assertEqual(client.options("/jobs/one/apply").status_code, 200)
                self.assertEqual(client.get("/health").status_code, 200)
            self.assertEqual(client.post("/jobs/one/apply").status_code, 200)

    def test_outage_rejects_before_handler_and_does_not_fall_back(self):
        handler = MagicMock(return_value={"ok": True})
        with self.app(handler).test_client() as client, patch.object(limits.store, "hit", side_effect=limits.StoreUnavailable):
            response = client.post("/jobs/one/apply")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["error_code"], "protection_unavailable")
        handler.assert_not_called()

    def test_legacy_decorator_does_not_replay_handler_exception(self):
        app = Flask(__name__)
        calls = []
        @limits.rate_limit(10, 60)
        def broken():
            calls.append(1)
            raise RuntimeError("business operation failed")
        with app.test_request_context("/"):
            with self.assertRaises(RuntimeError):
                broken()
        self.assertEqual(len(calls), 1)

    def test_capacity_rejects_busy_then_releases_after_completion(self):
        started, release = threading.Event(), threading.Event()
        def slow(job):
            started.set()
            release.wait(5)
            return {"ok": True}
        with patch.dict(os.environ, {"API_MAX_INFLIGHT": "1"}):
            app = self.app(slow)
        def send():
            with app.test_client() as client:
                return client.post("/jobs/one/apply").status_code
        with ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(send)
            self.assertTrue(started.wait(2))
            try:
                with app.test_client() as client:
                    response = client.post("/jobs/two/apply")
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(response.json["error_code"], "capacity_busy")
            finally:
                release.set()
            self.assertEqual(first.result(), 200)
        self.assertEqual(send(), 200)

    def test_capacity_releases_even_when_handler_raises(self):
        def fail(job):
            raise RuntimeError("failure")
        app = self.app(fail)
        with app.test_client() as client:
            with self.assertRaises(RuntimeError):
                client.post("/jobs/one/apply")
        self.assertEqual(app.extensions["request_protection"]["active"]["requests"], 0)

    def test_production_redis_boot_failure_is_actionable_without_credentials(self):
        with patch.dict(os.environ, {"RATE_LIMIT_REQUIRE_REDIS": "true"}), patch.object(
                limits.store, "_client", side_effect=TimeoutError("rediss://user:private-password@host")):
            with self.assertRaises(RuntimeError) as caught:
                self.app()
        self.assertIn("TimeoutError", str(caught.exception))
        self.assertNotIn("private-password", str(caught.exception))
        self.assertNotIn("rediss://", str(caught.exception))

    def test_redis_remote_tls_budget_is_bounded_and_has_no_automatic_retries(self):
        import redis
        with patch.dict(os.environ, {
                "REDIS_URL": "rediss://test-only", "REDIS_CONNECT_TIMEOUT_MS": "5000",
                "REDIS_SOCKET_TIMEOUT_MS": "2000"}), patch.object(redis.Redis, "from_url") as connect:
            limits.CounterStore()._client()
        options = connect.call_args.kwargs
        self.assertEqual(options["socket_connect_timeout"], 5)
        self.assertEqual(options["socket_timeout"], 2)
        self.assertEqual(options["retry"].get_retries(), 0)

    def test_invalid_timeout_does_not_create_a_redis_connection(self):
        import redis
        with patch.dict(os.environ, {
                "REDIS_URL": "rediss://test-only", "REDIS_CONNECT_TIMEOUT_MS": "0"}), patch.object(
                redis.Redis, "from_url") as connect:
            with self.assertRaises(ValueError):
                limits.CounterStore()._client()
        connect.assert_not_called()

    def test_configured_redis_outage_never_creates_local_counters(self):
        counter = limits.CounterStore()
        counter.redis_url = "redis://test-only"
        counter.redis = MagicMock()
        counter.redis.eval.side_effect = ConnectionError("unavailable")
        with patch.dict(os.environ, {"REDIS_URL": "redis://test-only"}):
            with self.assertRaises(limits.StoreUnavailable):
                counter.hit("one", 60)
        self.assertEqual(counter.windows, {})

    def test_socket_throttling_uses_native_acknowledgement_without_running_handler(self):
        app = Flask(__name__)
        calls = []
        @limits.socket_limit("socket_control")
        def handler(data):
            calls.append(data)
            return {"ok": True}
        with app.test_request_context("/"):
            from flask import request
            request.sid = "test-socket"
            with patch.object(limits, "check_limit", return_value=limits.rejection(429, "rate_limited", 12, "socket_control")):
                result = handler({})
        self.assertEqual(result["retry_after"], 12)
        self.assertEqual(result["error_code"], "rate_limited")
        self.assertEqual(calls, [])

    def test_local_memory_has_expiry_and_identity_cap(self):
        counter = limits.CounterStore()
        with patch.dict(os.environ, {"RATE_LIMIT_MEMORY_KEYS": "2"}), patch.object(limits.time, "monotonic", return_value=100):
            counter.hit("a", 5); counter.hit("b", 5)
            with self.assertRaises(limits.StoreUnavailable):
                counter.hit("c", 5)
        with patch.object(limits.time, "monotonic", return_value=140):
            self.assertEqual(counter.hit("c", 5)[0], 1)
        self.assertEqual(len(counter.windows), 1)

    def test_production_requires_shared_redis_at_boot(self):
        with patch.dict(os.environ, {"RATE_LIMIT_REQUIRE_REDIS": "true"}):
            with self.assertRaises(RuntimeError):
                self.app()

    def test_lua_atomic_counter_shared_across_two_instances(self):
        server = fakeredis.FakeServer()
        first, second = limits.CounterStore(), limits.CounterStore()
        first.redis = fakeredis.FakeRedis(server=server)
        second.redis = fakeredis.FakeRedis(server=server)
        first.redis_url = second.redis_url = "redis://test-only"
        with patch.dict(os.environ, {"REDIS_URL": "redis://test-only"}):
            with ThreadPoolExecutor(max_workers=20) as pool:
                counts = list(pool.map(lambda i: (first if i % 2 else second).hit("shared", 60)[0], range(100)))
        self.assertEqual(sorted(counts), list(range(1, 101)))
        self.assertGreater(first.redis.ttl("shared"), 0)

    def test_target_auth_budget_survives_ip_changes_and_case_changes(self):
        app = Flask(__name__)
        app.add_url_rule("/login", "login", lambda: {"ok": True}, methods=["POST"])
        limits.install_request_protection(app)
        with app.test_client() as client:
            responses = [client.post("/login", json={"identifier": " PERSON@example.com "},
                         environ_overrides={"REMOTE_ADDR": f"192.0.2.{i}"}) for i in range(11)]
        self.assertEqual(responses[-1].status_code, 429)

    def test_critical_routes_have_distinct_policies(self):
        expectations = {
            "apply_for_job": "application", "generate_jd_with_ai": "ai",
            "start_interview": "interview_start", "start_practice_interview": "interview_start",
            "submit_answer": "interview_answer", "transcribe": "speech",
            "speech_token": "speech_token", "send_invites": "invite_send", "upload_cv": "upload",
        }
        for name, policy in expectations.items():
            self.assertEqual(limits.route_policy("bp." + name, "POST"), policy)
        self.assertEqual(limits.route_policy("payment.initiate_payment", "POST", "/api/payment/recharge/initiate"), "payment")


class ApplicationAndWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        email = types.ModuleType("services.email_service")
        email.EmailService = MagicMock()
        usage = types.ModuleType("services.usage_telemetry_service")
        usage.record_usage_event = MagicMock()
        cls.worker_module = isolated_module("robustness_worker", "services/background_processor.py",
                                           {"services.email_service": email, "services.usage_telemetry_service": usage})
        scoring = types.ModuleType("services.cv_scoring_service"); scoring.CVScoringService = MagicMock()
        cv = types.ModuleType("controllers.cv_controller"); cv.CVController = MagicMock()
        background = types.ModuleType("services.background_processor"); background.get_background_processor = MagicMock()
        extensions = types.ModuleType("extensions"); extensions.socketio = MagicMock()
        cls.controller_module = isolated_module("robustness_application", "controllers/application_controller.py", {
            "services.email_service": email, "services.cv_scoring_service": scoring,
            "controllers.cv_controller": cv, "services.background_processor": background, "extensions": extensions,
        })

    def setUp(self):
        self.db = mongomock.MongoClient().db
        self.collections = {key: self.db[key] for key in ("applications", "jobs", "users", "interviews")}
        self.db.applications.create_index([("job_id", 1), ("student_id", 1)], unique=True)
        self.job_id, self.user_id = ObjectId(), ObjectId()
        self.db.jobs.insert_one({"_id": self.job_id, "status": "active", "title": "Engineer", "applicants": 0})
        self.controller = self.controller_module.ApplicationController.__new__(self.controller_module.ApplicationController)
        for name, collection in self.collections.items():
            setattr(self.controller, name + "_collection", collection)
        self.controller.db_collections = self.collections
        self.controller.cv_controller = MagicMock()
        self.controller.cv_controller.get_cv_by_id.return_value = {
            "cv_id": "cv-one", "extracted_text": "Candidate experience and skills", "metadata": {},
        }
        self.controller.cv_scoring_service = MagicMock()
        self.controller.background_processor = MagicMock()
        self.controller._emit_application_update = MagicMock()

    def apply(self):
        return self.controller.apply_for_job(str(self.job_id), str(self.user_id), {}, {"name": "Candidate"}, "cv-one")

    def worker(self, service=None):
        worker = self.worker_module.BackgroundProcessor()
        worker.configure(self.collections, service)
        worker._publish_progress = MagicMock()
        return worker

    def test_critical_index_rollout_rejects_legacy_conflicts_without_deleting_rows(self):
        env_loader = types.ModuleType("config.env_loader")
        env_loader.load_environment = lambda: None
        module = isolated_module("robustness_database", "config/database.py", {"config.env_loader": env_loader})
        config = module.DatabaseConfig.__new__(module.DatabaseConfig)
        for kind in ("duplicate", "noncanonical"):
            database = mongomock.MongoClient().db
            config.db = database
            doc = {"job_id": str(self.job_id), "student_id": str(self.user_id)}
            database.applications.insert_one(doc)
            if kind == "duplicate":
                database.applications.insert_one({"job_id": str(self.job_id), "student_id": str(self.user_id)})
            else:
                database.applications.update_one({}, {"$set": {"job_id": str(self.job_id).upper()}})
            count = database.applications.count_documents({})
            with self.assertRaises(RuntimeError):
                config._ensure_indexes()
            self.assertEqual(database.applications.count_documents({}), count)

    def test_concurrent_apply_has_one_record_counter_and_queue_wakeup(self):
        barrier = threading.Barrier(16)
        def send(_):
            barrier.wait()
            return self.apply()
        with ThreadPoolExecutor(max_workers=16) as pool:
            responses = list(pool.map(send, range(16)))
        self.assertEqual(sum(status == 201 for _, status in responses), 1)
        self.assertEqual(sum(status == 200 for _, status in responses), 15)
        self.assertEqual(self.db.applications.count_documents({}), 1)
        self.assertEqual(self.db.jobs.find_one()["applicants"], 1)
        self.controller.background_processor.enqueue_cv_scoring.assert_called_once()
        self.assertEqual(len({data["application_id"] for data, _ in responses}), 1)

    def test_invite_conversion_is_conditional_and_counted_once(self):
        self.db.applications.insert_one({
            "job_id": str(self.job_id), "student_id": str(self.user_id),
            "processing_status": "awaiting_candidate", "invite_type": "apply",
        })
        with ThreadPoolExecutor(max_workers=12) as pool:
            responses = list(pool.map(lambda _: self.apply(), range(12)))
        self.assertEqual(sum(status == 201 for _, status in responses), 1)
        self.assertEqual(self.db.jobs.find_one()["applicants"], 1)
        self.assertEqual(self.db.applications.count_documents({}), 1)

    def test_replay_returns_existing_id_even_after_job_closes(self):
        first, _ = self.apply()
        self.db.jobs.update_one({"_id": self.job_id}, {"$set": {"status": "closed"}})
        replay, status = self.apply()
        self.assertEqual(status, 200)
        self.assertEqual(replay["application_id"], first["application_id"])

    def test_closed_and_expired_jobs_reject_new_application(self):
        for fields in ({"status": "closed"}, {"status": "active", "deadline": "2020-01-01"}):
            self.db.jobs.update_one({"_id": self.job_id}, {"$set": fields})
            self.assertEqual(self.apply()[1], 409)
        self.assertEqual(self.db.applications.count_documents({}), 0)

    def test_invalid_job_id_is_a_validation_error(self):
        result = self.controller.apply_for_job("invalid", str(self.user_id), {}, {}, "cv-one")
        self.assertEqual(result[1], 400)

    def test_real_worker_keeps_submission_independent_of_slow_scoring(self):
        entered, release = threading.Event(), threading.Event()
        service = MagicMock()
        def score(*args):
            entered.set()
            release.wait(3)
            return {"total_score": 84}
        service.calculate_cv_score_from_text.side_effect = score
        worker = self.worker(service)
        self.controller.background_processor = worker
        self.controller.cv_scoring_service = service
        worker.start()
        try:
            result, status = self.apply()
            self.assertEqual(status, 201)
            self.assertTrue(result["application_id"])
            self.assertTrue(entered.wait(2))
            self.assertFalse(release.is_set())
        finally:
            release.set()
            worker.stop()

    def test_invite_background_slot_remains_reserved_until_dispatch_finishes(self):
        from services import bounded_executor
        entered, release = threading.Event(), threading.Event()
        def dispatch():
            entered.set()
            release.wait(3)
        with patch.object(bounded_executor, "_invite_slots", threading.BoundedSemaphore(1)):
            permit = bounded_executor.reserve_invite_dispatch()
            permit.dispatch(dispatch)
            try:
                self.assertTrue(entered.wait(2))
                self.assertIsNone(bounded_executor.reserve_invite_dispatch())
            finally:
                release.set()
            for _ in range(100):
                if permit.released:
                    break
                time.sleep(0.01)
            self.assertTrue(permit.released)
            next_permit = bounded_executor.reserve_invite_dispatch()
            self.assertIsNotNone(next_permit)
            next_permit.release()

    def test_enqueue_never_calls_provider_synchronously(self):
        service = MagicMock()
        worker = self.worker(service)
        worker.enqueue_cv_scoring("one", {}, {}, self.collections, service)
        service.calculate_cv_score.assert_not_called()
        service.calculate_cv_score_from_text.assert_not_called()

    def test_worker_preserves_submitted_parsed_cv_and_job_snapshot(self):
        details = {"skills": ["Python"]}
        self.controller.cv_controller.get_cv_by_id.return_value["parsed_details"] = details
        self.db.jobs.update_one({}, {"$set": {"description": "Original role"}})
        self.apply()
        self.db.jobs.update_one({}, {"$set": {"description": "Changed role"}})
        task = self.worker()._claim_task()
        self.assertEqual(task["cv_data"]["cv_details"], details)
        self.assertEqual(task["jd_data"]["job"]["description"], "Original role")

    def test_durable_work_survives_new_worker_and_only_one_can_claim(self):
        self.apply()
        one, two = self.worker(), self.worker()
        with ThreadPoolExecutor(max_workers=2) as pool:
            tasks = list(pool.map(lambda w: w._claim_task(), (one, two)))
        self.assertEqual(sum(task is not None for task in tasks), 1)
        task = next(task for task in tasks if task)
        self.assertEqual(task["cv_data"]["cv_text"], "Candidate experience and skills")

    def test_expired_lease_recovery_fences_old_worker_result(self):
        self.apply()
        worker = self.worker()
        old = worker._claim_task()
        self.db.applications.update_one({}, {"$set": {"scoring_lease_until": datetime.utcnow() - timedelta(seconds=1)}})
        new = self.worker()._claim_task()
        self.assertNotEqual(old["lease_token"], new["lease_token"])
        result = self.db.applications.update_one(worker._task_filter(old), {"$set": {"cv_score": 99}})
        self.assertEqual(result.modified_count, 0)

    def test_failed_scoring_schedules_persistent_retry_without_timers(self):
        self.apply()
        service = MagicMock()
        service.calculate_cv_score_from_text.return_value = {"is_fallback": True}
        worker = self.worker(service); task = worker._claim_task()
        before = datetime.utcnow()
        worker._process_cv_scoring(task)
        doc = self.db.applications.find_one()
        self.assertEqual(doc["processing_status"], "scoring_retrying")
        self.assertGreater(doc["scoring_next_retry_at"], before + timedelta(seconds=20))
        self.assertIsNone(self.worker()._claim_task())

    def test_invalid_provider_scores_retry_instead_of_deciding_eligibility(self):
        for score in (float("nan"), float("inf"), -1, 101, True, "84"):
            with self.subTest(score=score):
                self.db.applications.delete_many({})
                self.apply()
                service = MagicMock()
                service.calculate_cv_score_from_text.return_value = {"total_score": score}
                worker = self.worker(service)
                worker._process_cv_scoring(worker._claim_task())
                doc = self.db.applications.find_one()
                self.assertEqual(doc["status"], "pending")
                self.assertIsNone(doc["cv_score"])
                self.assertEqual(doc["processing_status"], "scoring_retrying")

    def test_readiness_repeated_requests_share_short_cached_dependency_check(self):
        module = isolated_module("robustness_system", "routes/system_routes.py", {})
        database = MagicMock()
        app = Flask(__name__)
        app.register_blueprint(module.create_system_routes(database))
        with patch.dict(os.environ, {"REDIS_URL": "", "RATE_LIMIT_REQUIRE_REDIS": "false"}), app.test_client() as client:
            for _ in range(20):
                self.assertEqual(client.get("/health").status_code, 200)
        self.assertEqual(database.command.call_count, 1)

    def test_provider_exhaustion_never_invents_a_score_or_shortlists(self):
        self.apply()
        worker = self.worker()
        task = worker._claim_task(); task["retry_count"] = worker.MAX_SCORING_RETRIES
        worker._process_cv_scoring(task)
        doc = self.db.applications.find_one()
        self.assertEqual(doc["processing_status"], "scoring_failed")
        self.assertIsNone(doc["cv_score"])
        self.assertEqual(doc["status"], "pending")

    def test_recruiter_change_during_result_write_preserves_score_without_rescoring(self):
        self.apply()
        service = MagicMock()
        service.calculate_cv_score_from_text.return_value = {"total_score": 84}
        worker = self.worker(service); task = worker._claim_task()
        original = self.db.applications.update_one
        def race(query, update, *args, **kwargs):
            if "status" in query:
                original({"_id": query["_id"]}, {"$set": {"status": "selected", "status_reason": "Recruiter selected"}})
            return original(query, update, *args, **kwargs)
        with patch.object(self.db.applications, "update_one", side_effect=race):
            worker._process_cv_scoring(task)
        doc = self.db.applications.find_one()
        self.assertEqual(doc["status"], "selected")
        self.assertEqual(doc["status_reason"], "Recruiter selected")
        self.assertEqual(doc["cv_score"], 84)
        self.assertEqual(doc["processing_status"], "completed")
        service.calculate_cv_score_from_text.assert_called_once()

    def test_authentication_database_overload_is_not_an_invalid_token(self):
        # Load auth with an isolated database boundary, never the real configuration.
        config = types.ModuleType("config.database")
        config.db_config = MagicMock()
        from pymongo.errors import WaitQueueTimeoutError
        config.db_config.get_collections.side_effect = WaitQueueTimeoutError("busy")
        module = isolated_module("robustness_auth", "middleware/auth_middleware.py", {"config.database": config})
        token = jwt.encode({"user_id": str(self.user_id)}, module._JWT_SECRET_KEY, algorithm="HS256")
        with self.assertRaises(WaitQueueTimeoutError):
            module.decode_user_from_token(token)

    def test_success_publishes_real_score_and_preserves_recruiter_decision(self):
        self.apply()
        service = MagicMock()
        service.calculate_cv_score_from_text.return_value = {"total_score": 84, "score_breakdown": {"skills": 84}}
        worker = self.worker(service); task = worker._claim_task()
        self.db.applications.update_one({}, {"$set": {"status": "rejected", "status_reason": "Recruiter review"}})
        with patch.object(self.worker_module, "_notify_candidate_of_status"):
            worker._process_cv_scoring(task)
        doc = self.db.applications.find_one()
        self.assertEqual(doc["cv_score"], 84)
        self.assertEqual(doc["status"], "rejected")
        self.assertEqual(doc["status_reason"], "Recruiter review")
        self.assertEqual(doc["processing_status"], "completed")


if __name__ == "__main__":
    unittest.main()
