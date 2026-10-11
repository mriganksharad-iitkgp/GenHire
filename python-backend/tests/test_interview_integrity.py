"""Durable policy tests, including restart, simultaneous callbacks and lockout."""
import datetime as dt
import unittest
from unittest.mock import patch, MagicMock

import mongomock
from bson import ObjectId
from services import interview_integrity_service as policy
from services.proctoring_service import mobile_is_ready


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient(tz_aware=True).test
        self.collection = self.db.interviews
        self.now = dt.datetime.now(dt.timezone.utc)
        self.application = self.db.applications.insert_one({}).inserted_id
        self.doc = {"_id": ObjectId(), "session_id": "owned-session", "user_id": "candidate", "status": "active",
                    "application_id": str(self.application), "activated_at": self.now - dt.timedelta(seconds=30)}
        self.collection.insert_one(self.doc)
        self.notifications = patch("extensions.socketio.emit", MagicMock())
        self.notifications.start()
        self.addCleanup(self.notifications.stop)

    def stored(self):
        return self.collection.find_one({"_id": self.doc["_id"]})

    def test_fifth_distinct_episode_terminates_and_locks_application(self):
        for number in range(1, 6):
            result = policy.reconcile(self.collection, self.stored(), {"desktop": "tab_switch"}, now=self.now)
            self.assertEqual(result["count"], number)
            self.assertEqual(result["terminated"], number == 5)
            # Multiple callbacks from the same absence are one interruption.
            duplicate = policy.reconcile(self.collection, self.stored(), {"desktop": "window_blur"}, now=self.now)
            self.assertEqual(duplicate["count"], number)
            if number < 5:
                policy.reconcile(self.collection, self.stored(), restored=["desktop"], now=self.now)
        self.assertTrue(self.db.applications.find_one({"_id": self.application})["interview_attempt_locked"])
        self.assertEqual(self.stored()["termination_reason"], "interruption_limit")

    def test_stale_worker_cas_cannot_double_count_an_open_loss(self):
        stale = self.stored()
        policy.reconcile(self.collection, self.stored(), {"desktop": "tab_switch"}, now=self.now)
        result = policy.reconcile(self.collection, stale, {"desktop": "window_blur"}, now=self.now)
        self.assertEqual(result["count"], 1)

    def test_sustained_loss_ends_after_recovery_window_without_five_fake_strikes(self):
        policy.reconcile(self.collection, self.stored(), {"mobile": "mobile_unavailable"}, now=self.now)
        result = policy.reconcile(self.collection, self.stored(), now=self.now + dt.timedelta(seconds=60))
        self.assertTrue(result["terminated"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(self.stored()["termination_reason"], "monitoring_not_restored")

    def test_actual_frames_heartbeat_front_camera_and_visibility_gate_health(self):
        self.collection.update_one({"_id": self.doc["_id"]}, {"$set": {
            "dual_proctoring_required": True,
            "desktop_monitoring": {"last_seen_at": self.now, "frame_at": self.now, "visible": True,
                                   "focused": True, "secure_view": True, "devices_ready": True},
            "mobile_proctoring": {"status": "recording", "camera_ready": True, "microphone_ready": True,
                                  "last_seen_at": self.now, "preview_frame_received_at": self.now,
                                  "page_visible": True, "facing_mode": "user"}}})
        self.assertEqual(policy.check_health(self.collection, self.stored(), self.now)["count"], 0)
        self.collection.update_one({"_id": self.doc["_id"]}, {"$set": {"mobile_proctoring.page_visible": False}})
        self.assertEqual(policy.check_health(self.collection, self.stored(), self.now)["count"], 1)
        self.assertEqual(policy.check_health(self.collection, self.stored(), self.now)["count"], 1)
        self.collection.update_one({"_id": self.doc["_id"]}, {"$set": {"mobile_proctoring.page_visible": True}})
        self.assertFalse(policy.check_health(self.collection, self.stored(), self.now)["losses"])
        self.collection.update_one({"_id": self.doc["_id"]}, {"$set": {"mobile_proctoring.facing_mode": "environment"}})
        self.assertFalse(mobile_is_ready(self.stored(), self.now))

    def test_setup_and_unmonitored_practice_do_not_accumulate_interruptions(self):
        for flags in ({"status": "setup"}, {"is_practice": True, "proctoring_enabled": False}):
            doc = dict(self.stored(), **flags)
            result = policy.reconcile(self.collection, doc, {"desktop": "tab_switch"}, now=self.now)
            self.assertEqual(result["count"], 0)

    def test_expired_preview_cannot_be_replaced_by_only_a_heartbeat(self):
        mobile = {"status": "ready", "camera_ready": True, "microphone_ready": True, "page_visible": True,
                  "facing_mode": "user", "last_seen_at": self.now,
                  "preview_frame_received_at": self.now - dt.timedelta(seconds=16)}
        self.assertFalse(mobile_is_ready({"mobile_proctoring": mobile}, self.now))


class EngineRecoveryTests(unittest.TestCase):
    def test_same_session_restores_current_question_answers_deadline_and_context(self):
        # Match the existing isolated provider test setup; do not load dotenv.
        import tests.test_s2_stack
        from interview.core.session_manager import InterviewSessionManager
        from interview.config.settings import InterviewConfig
        manager = InterviewSessionManager.__new__(InterviewSessionManager)
        manager.config = InterviewConfig()
        manager.llm = MagicMock()
        manager.sessions = {}
        doc = {"session_id": "original-session", "status": "active", "proctoring_config": {},
               "engine_checkpoint": {"current_question": "Explain your project.", "questions_asked": 2,
                                     "question_served_at": 1000, "activated_at": 900,
                                     "interview_data": [{"question": "q", "answer": "saved answer", "evaluation": {}}]}}
        session = manager.restore_session(doc, "Skills: Python, SQL. Experience: built a hiring platform.", "Software engineer: Python and SQL.")
        self.assertEqual(session.session_id, "original-session")
        self.assertEqual(session.current_question, "Explain your project.")
        self.assertEqual(session.questions_asked, 2)
        self.assertEqual(session.interview_data[0]["answer"], "saved answer")
        self.assertEqual(session.question_served_at, 1000)
        self.assertEqual(session.activated_at, 900)
        manager.llm.generate_response.assert_not_called()
        saved = manager.checkpoint(session.session_id)
        manager.sessions.clear()
        restored = manager.restore_session(dict(doc, engine_checkpoint=saved), "Skills: Python.", "Python engineer.")
        self.assertEqual(restored.conversation_context.depth_level, session.conversation_context.depth_level)
        self.assertEqual(restored.current_question, session.current_question)
        self.assertEqual(set(manager.sessions), {"original-session"})


if __name__ == "__main__":
    unittest.main()
