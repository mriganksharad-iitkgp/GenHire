"""Interview lifecycle regression tests with no database/provider credentials."""
import importlib.util
import math
import datetime
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
# Keep BSON class identity stable across scoped sys.modules route stubs.
from bson import ObjectId

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from services.interview_flow_service import (
    normalize_proctoring_config, evaluation_percentage, percentage,
    result_payload, cached_answer_result,
    json_safe,
    merge_usage_summaries,
)
from core.config import origin_is_allowed


class InterviewPolicyTests(unittest.TestCase):
    def test_legacy_jobs_are_single_camera_and_ai_flag_survives(self):
        self.assertFalse(normalize_proctoring_config({})["dual_camera"])
        self.assertTrue(normalize_proctoring_config({"ai_detection": True})["ai_detection"])

    def test_partial_edits_preserve_recruiter_settings(self):
        result = normalize_proctoring_config({"dual_camera": True}, {"object_detection": False})
        self.assertTrue(result["dual_camera"])
        self.assertFalse(result["object_detection"])

    def test_string_false_does_not_enable_paid_monitoring(self):
        with self.assertRaises(ValueError):
            normalize_proctoring_config({"dual_camera": "false"})
        with self.assertRaises(ValueError):
            normalize_proctoring_config([])

    def test_unavailable_score_never_becomes_zero_or_default(self):
        self.assertIsNone(evaluation_percentage({"quantitative_scores": {"answer_score": None, "language_score": None}}))
        self.assertEqual(evaluation_percentage({"quantitative_scores": {"answer_score": .8, "language_score": .6}}), 74)
        self.assertIsNone(percentage(math.nan))

    def test_terminal_replay_preserves_scores_and_report(self):
        result = result_payload({"session_id": "one", "status": "completed", "is_practice": True,
            "cv_score": .71, "final_score": 0, "proctoring_score": None,
            "proctoring_status": "disabled", "evaluation": {"score_status": "complete"}})
        self.assertEqual(result["cv_score"], 71)
        self.assertEqual(result["interview_score"], 0)
        self.assertIsNone(result["proctoring_score"])

    def test_answer_retry_replays_only_identical_accepted_answer(self):
        doc = {"last_answer": {"question": "q", "answer": "a", "result": {"next_question": "next"}}}
        self.assertTrue(cached_answer_result(doc, "q", "a")["idempotent_replay"])
        self.assertIsNone(cached_answer_result(doc, "q", "different"))
        doc["last_answer"]["result"]["repeated_question"] = True
        self.assertIsNone(cached_answer_result(doc, "q", "a"))

    def test_kiosk_origin_check_rejects_lookalikes(self):
        with patch.dict("os.environ", {"CORS_ORIGINS": "https://genhire.example"}):
            self.assertTrue(origin_is_allowed("http://localhost:32199"))
            self.assertTrue(origin_is_allowed("http://127.0.0.1:32199"))
            self.assertTrue(origin_is_allowed("https://genhire.example"))
            for origin in ("https://evil.example", "http://localhost.evil:32199", "http://localhost:0", "http://localhost:65536", "http://localhost:32199/evil"):
                self.assertFalse(origin_is_allowed(origin))

    def test_storage_metadata_preserves_enum_value(self):
        from enum import Enum
        class Phase(Enum):
            TECHNICAL = "technical"
        self.assertEqual(json_safe({"metadata": {"phase": Phase.TECHNICAL}}),
            {"metadata": {"phase": "technical"}})

    def test_late_evaluation_usage_adds_only_new_usage(self):
        merged = merge_usage_summaries({"total_prompt_tokens": 100, "total_cost": .02, "models": ["first"]},
            {"total_prompt_tokens": 50, "total_cost": .01, "models": ["second"], "source": "late"})
        self.assertEqual(merged["total_prompt_tokens"], 150)
        self.assertAlmostEqual(merged["total_cost"], .03)
        self.assertEqual(merged["models"], ["first", "second"])


class InterviewRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from flask import Flask
        cls.user = {"_id": "candidate-one"}
        cls.manager = MagicMock()
        cls.manager.sessions = {}
        cls.manager.config = SimpleNamespace(question_timeout_seconds=300, max_questions=10)
        def auth(fn):
            def wrapped(*args, **kwargs):
                return fn(cls.user, *args, **kwargs)
            wrapped.__name__ = fn.__name__
            return wrapped
        def module(name, **values):
            mod = types.ModuleType(name)
            mod.__dict__.update(values)
            return mod
        stubs = {
            "config.database": module("config.database", db_config=MagicMock()),
            "extensions": module("extensions", socketio=MagicMock()),
            "interview.runtime": module("interview.runtime", M_RECORDING_FOLDER=".", PROCTORING_FOLDER=".", RECORDING_FOLDER=".", TMP_FOLDER=".", gaze_recorder_service=MagicMock(), interview_manager=cls.manager, live_sessions={}),
            "interview.core.cost_tracker": module("interview.core.cost_tracker", CostTracker=MagicMock()),
            "middleware.auth_middleware": module("middleware.auth_middleware", token_required=auth),
            "payment_module.config.settings": module("payment_module.config.settings", PaymentConfig=MagicMock()),
            "payment_module.services.wallet_service": module("payment_module.services.wallet_service", WalletService=MagicMock()),
            "services.face_verification_service": module("services.face_verification_service", FACE_MODEL_NAME="stub", assess_face_image=MagicMock(), store_face_image=MagicMock(return_value="captured-id"), get_mode=lambda: "off"),
            "services.face_match_service": module("services.face_match_service"),
            "services.identity_card_service": module("services.identity_card_service"),
            "services.interview_credit_service": module("services.interview_credit_service", count_answered_questions=lambda *args: 0),
            "services.cv_scoring_service": module("services.cv_scoring_service", CVScoringService=MagicMock()),
            "services.email_service": module("services.email_service", EmailService=MagicMock()),
            "services.usage_telemetry_service": module("services.usage_telemetry_service", record_usage_event=MagicMock()),
            "services.llm_fallback_service": module("services.llm_fallback_service", default_model_for=MagicMock(), get_provider_priority=MagicMock()),
        }
        spec = importlib.util.spec_from_file_location("_interview_routes_under_test", BACKEND / "routes/interview_routes.py")
        cls.routes = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, stubs):
            spec.loader.exec_module(cls.routes)
        cls.app = Flask(__name__)
        cls.app.register_blueprint(cls.routes.interview_bp)
        cls.client = cls.app.test_client()

    def setUp(self):
        self.manager.reset_mock()
        self.manager.activate_session.return_value = {"status": "active", "question_deadline": 1234}
        self.real = MagicMock()
        self.practice = MagicMock()
        self.practice.find_one.return_value = None
        self.routes.init_interview_routes(MagicMock(), {"users": MagicMock(), "interviews": self.real,
            "applications": MagicMock(), "jobs": MagicMock(), "practice_sessions": self.practice})

    def test_non_owner_cannot_submit_or_finalize(self):
        self.real.find_one.return_value = None
        self.assertEqual(self.client.post("/api/interviews/session/answer", json={"question": "q", "answer": "a"}).status_code, 404)
        self.assertEqual(self.client.post("/api/interviews/session/end", json={}).status_code, 404)
        self.manager.submit_answer.assert_not_called()
        self.real.update_one.assert_not_called()

    def test_activation_requires_device_checks_face_and_fresh_phone(self):
        doc = {"_id": "doc", "session_id": "session", "user_id": "candidate-one", "status": "setup"}
        self.real.find_one.return_value = doc
        endpoint = "/api/interviews/session/activate"
        checks = {"camera_ready": True, "microphone_ready": True, "speaker_ready": True}
        self.assertEqual(self.client.post(endpoint, json={}).json["error_code"], "device_checks_required")
        self.assertEqual(self.client.post(endpoint, json=checks).json["error_code"], "face_capture_required")
        doc["identity_verification"] = {"status": "practice_captured"}
        doc["dual_proctoring_required"] = True
        self.assertEqual(self.client.post(endpoint, json=checks).json["error_code"], "mobile_camera_required")
        self.manager.activate_session.assert_not_called()
        doc["dual_proctoring_required"] = False
        self.assertEqual(self.client.post(endpoint, json=checks).status_code, 200)
        self.manager.activate_session.assert_called_once_with("session")

    def test_activation_retry_does_not_overwrite_original_checks_or_start(self):
        self.real.find_one.return_value = {"_id": "doc", "session_id": "session", "user_id": "candidate-one", "status": "active", "activated_at": datetime.datetime.now(datetime.timezone.utc)}
        self.assertEqual(self.client.post("/api/interviews/session/activate", json={}).status_code, 200)
        self.real.update_one.assert_not_called()

    def test_managed_screening_cutoff_blocks_activation_question_and_answer(self):
        from services.hiring_progression_service import now_utc
        doc = dict(_id='doc', session_id='session', user_id='candidate-one', status='active',
            screening_finish_by=now_utc()-datetime.timedelta(seconds=1))
        self.real.find_one.return_value = doc
        with patch.dict('os.environ', {'GENHIRE_WORKFLOW_ENABLED': 'true', 'GENHIRE_SCHEDULING_ENABLED': 'true'}):
            for method, endpoint, data in [('post', 'activate', {}), ('get', 'question', None), ('post', 'answer', {'question': 'q', 'answer': 'a'})]:
                response = getattr(self.client, method)('/api/interviews/session/'+endpoint, **({'json': data} if data is not None else {}))
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.json['error_code'], 'screening_window_closed')
        self.manager.submit_answer.assert_not_called()
        self.manager.activate_session.assert_not_called()

    def test_terminated_attempt_cannot_activate_answer_or_start_again(self):
        import mongomock
        database = mongomock.MongoClient().test
        app_id = database.applications.insert_one({"student_id": "candidate-one", "status": "shortlisted"}).inserted_id
        database.interviews.insert_one({"session_id": "session", "user_id": "candidate-one",
            "application_id": str(app_id), "status": "terminated", "integrity": {"count": 5}})
        self.routes.init_interview_routes(database, {name: database[name] for name in ("users", "interviews", "applications", "jobs", "practice_sessions")})
        self.assertEqual(self.client.post("/api/interviews/session/activate", json={}).status_code, 409)
        self.assertEqual(self.client.post("/api/interviews/session/answer", json={"question": "q", "answer": "a"}).status_code, 409)
        self.assertEqual(self.client.post("/api/interviews/start", json={"application_id": str(app_id)}).json["error_code"], "interview_attempt_locked")
        self.assertEqual(self.client.post("/api/interviews/session/end", json={}).json["status"], "interview_terminated")
        self.manager.submit_answer.assert_not_called()
        self.manager.activate_session.assert_not_called()

    def test_active_attempt_can_submit_after_many_monitoring_gaps(self):
        import mongomock
        database = mongomock.MongoClient().test
        database.interviews.insert_one({"session_id": "session", "user_id": "candidate-one", "status": "active",
            "integrity": {"version": 1, "count": 8, "counts_by_type": {"mobile_unavailable": 8},
                          "losses": {"mobile": {"since": datetime.datetime.now(datetime.timezone.utc), "reason": "mobile_unavailable"}}}})
        self.routes.init_interview_routes(database, {name: database[name] for name in ("users", "interviews", "applications", "jobs", "practice_sessions")})
        self.manager.checkpoint.return_value = None
        self.manager.submit_answer.return_value = {"next_question": "Next question", "current_evaluation": {}}
        response = self.client.post("/api/interviews/session/answer", json={"question": "q", "answer": "Spoken answer"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(database.interviews.find_one({"session_id": "session"})["status"], "active")

    def test_completed_end_retry_does_not_recompute_or_charge(self):
        self.real.find_one.return_value = {"session_id": "session", "user_id": "candidate-one", "status": "completed", "final_score": 82, "cv_score": 66}
        response = self.client.post("/api/interviews/session/end", json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["interview_score"], 82)
        self.real.update_one.assert_not_called()
        self.manager._generate_final_evaluation.assert_not_called()

    def test_completed_bootstrap_retains_database_status_and_zero_scores(self):
        self.real.find_one.return_value = {"session_id": "session", "user_id": "candidate-one",
            "status": "completed", "final_score": 0, "cv_score": 0, "evaluation": {"score_status": "complete"}}
        response = self.client.get("/api/interviews/session/session")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "completed")
        self.assertEqual(response.json["result_status"], "interview_ended")
        self.assertEqual(response.json["interview_score"], 0)

    def test_gaze_upload_does_not_process_another_candidates_session(self):
        self.real.find_one.return_value = None
        response = self.client.post("/api/interviews/session/gaze-recorder-results", json={"gazePoints": [{"x": 1}]})
        self.assertEqual(response.status_code, 404)
        self.real.update_one.assert_not_called()

    def test_report_bootstrap_has_safe_identity_evidence(self):
        self.real.find_one.return_value = {"session_id": "session", "user_id": "candidate-one", "status": "completed",
            "identity_verification": {"status": "score_pending", "captured_image_file_id": "private-gridfs-id"}}
        response = self.client.get("/api/interviews/session/session")
        identity = response.json["identity_verification"]
        self.assertTrue(identity["has_captured_image"])
        self.assertEqual(identity["status"], "score_pending")
        self.assertNotIn("captured_image_file_id", identity)

    def test_capture_quality_and_setup_policy_still_apply_to_auto_photos(self):
        self.real.find_one.return_value = {"_id": "doc", "session_id": "session", "user_id": "candidate-one", "status": "setup"}
        self.routes.face_service.assess_face_image.return_value = {"ok": False, "error_code": "multiple_faces_detected", "message": "Only one face is allowed"}
        response = self.client.post("/api/interviews/session/register-face", json={"image": "data:image/jpeg;base64,Zml4dHVyZQ=="})
        self.assertEqual(response.status_code, 400)
        self.real.update_one.assert_not_called()
        self.routes.face_service.assess_face_image.return_value = {"ok": True}
        with patch.object(self.routes.face_service, "decode_image", return_value=MagicMock(), create=True):
            response = self.client.post("/api/interviews/session/register-face", json={"image": "data:image/jpeg;base64,Zml4dHVyZQ=="})
        self.assertEqual(response.status_code, 200)
        self.real.find_one.return_value["status"] = "active"
        self.assertEqual(self.client.post("/api/interviews/session/register-face", json={"image": "data:image/jpeg;base64,Zml4dHVyZQ=="}).status_code, 409)

    def test_old_photo_score_cannot_replace_a_retake(self):
        self.real.update_one.return_value.matched_count = 0
        with patch.object(self.routes.identity_card_service, "load_identity_card", return_value=(b"card", "image/jpeg"), create=True), \
                patch.object(self.routes.face_match_service, "compare_faces", return_value={"available": True, "matched": True, "score": 90}, create=True):
            self.routes._score_identity_async("doc", "application", "card", b"old-capture", "session", "old-photo")
        self.assertEqual(self.real.update_one.call_args.args[0]["identity_verification.captured_image_file_id"], "old-photo")
        self.routes.applications_collection.update_one.assert_not_called()


if __name__ == "__main__":
    unittest.main()
