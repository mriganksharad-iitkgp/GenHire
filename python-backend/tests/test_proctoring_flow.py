"""Proctoring regressions: real Socket.IO clients, no external DB/API calls.

Run: python -m unittest discover -s python-backend/tests -p test_proctoring_flow.py -v
"""
import base64
import copy
import datetime
import importlib
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services import proctoring_service as policy


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.key = patch.object(policy, "_signing_key", return_value=b"test-pairing-secret")
        self.key.start()
        self.addCleanup(self.key.stop)

    def test_pairing_is_owner_session_bound_and_expires(self):
        with patch.object(policy.time, "time", return_value=1000):
            token = policy.create_mobile_pairing_token("session-a", "candidate")
        with patch.object(policy.time, "time", return_value=1010):
            self.assertTrue(policy.validate_mobile_pairing_token(token, "session-a", "candidate"))
            self.assertFalse(policy.validate_mobile_pairing_token(token, "session-b", "candidate"))
            self.assertFalse(policy.validate_mobile_pairing_token(token, "session-a", "someone-else"))
            self.assertFalse(policy.validate_mobile_pairing_token(token + "x", "session-a"))
        with patch.object(policy.time, "time", return_value=1000 + policy.MOBILE_PAIRING_TTL_SECONDS + 1):
            self.assertFalse(policy.validate_mobile_pairing_token(token, "session-a"))

    def test_readiness_requires_camera_mic_heartbeat_and_actual_preview(self):
        now = datetime.datetime(2026, 10, 8, 12)
        mobile = {"status": "ready", "camera_ready": True, "microphone_ready": True, "last_seen_at": now}
        doc = {"mobile_proctoring": mobile}
        self.assertFalse(policy.mobile_is_ready(doc, now))
        mobile["preview_frame_received_at"] = now
        self.assertTrue(policy.mobile_is_ready(doc, now))
        mobile["microphone_ready"] = False
        self.assertFalse(policy.mobile_is_ready(doc, now))
        mobile["microphone_ready"] = True
        self.assertFalse(policy.mobile_is_ready(doc, now + datetime.timedelta(seconds=16)))
        mobile["last_seen_at"] = now + datetime.timedelta(seconds=20)
        self.assertFalse(policy.mobile_is_ready(doc, now))

    def test_confirmation_cooldown_and_technical_errors(self):
        state = {}
        observation = {"available": True, "violations": [{"type": "multiple_faces", "message": "Multiple faces"}]}
        self.assertEqual(policy.record_observation(state, observation, now=0), [])
        for second in range(1, 15):
            policy.record_observation(state, observation, now=second)
        self.assertEqual(state["infractions"]["multiple_faces"], 1)
        self.assertEqual(state["proctoring_score"], 98)
        policy.record_observation(state, observation, now=16)
        self.assertEqual(state["infractions"]["multiple_faces"], 2)
        policy.record_observation(state, {"available": False, "errors": ["detector unavailable"]}, now=17)
        self.assertEqual(state["proctoring_score"], 96)
        self.assertEqual(state["analysis_errors"], 1)

    def test_manual_events_do_not_fake_camera_coverage(self):
        state = {}
        policy.record_manual_violation(state, "tab_switch", now=1)
        policy.record_manual_violation(state, "tab_switch", now=2)
        self.assertEqual(state["infractions"], {"manual_tab_switch": 1})
        self.assertNotIn("analyzed_frames", state)
        self.assertNotIn("analysis_errors", state)
        self.assertIsNone(policy.build_proctoring_report(state)["final_score"])

    def test_stale_companion_coverage_is_recorded_once_without_score_penalty(self):
        state = {"mobile_camera_ready": True, "infractions": {}}
        doc = {"dual_proctoring_required": True, "mobile_proctoring": {}}
        self.assertIsNotNone(policy.observe_mobile_coverage(state, doc))
        self.assertIsNone(policy.observe_mobile_coverage(state, doc))
        self.assertEqual(state["mobile_coverage_gaps"], 1)
        self.assertEqual(state["infractions"], {})
        now = datetime.datetime.now(datetime.timezone.utc)
        doc["mobile_proctoring"] = {"status": "ready", "camera_ready": True, "microphone_ready": True,
                                   "last_seen_at": now, "preview_frame_received_at": now}
        self.assertIsNone(policy.observe_mobile_coverage(state, doc))
        doc["mobile_proctoring"]["camera_ready"] = False
        self.assertIsNotNone(policy.observe_mobile_coverage(state, doc))
        self.assertEqual(state["mobile_coverage_gaps"], 2)

    def test_report_preserves_zero_missing_modules_and_worker_persistence(self):
        doc = {"proctoring_config": {"object_detection": True, "eyeball_tracking": True, "voice_detection": True, "gaze_heatmap": True, "dual_camera": True}}
        state = {"analyzed_frames": 4, "desktop_analyzed_frames": 2, "mobile_analyzed_frames": 2, "infractions": {"identity_mismatch": 20}, "capabilities": {"face_detection": True}}
        report = policy.build_proctoring_report(state, doc)
        self.assertEqual(report["final_score"], 0)
        self.assertEqual(report["status"], "partial")
        self.assertIn("voice_detection", report["missing_checks"])
        self.assertIn("gaze_heatmap", report["missing_checks"])
        doc["proctoring_report"] = report
        self.assertEqual(policy.build_proctoring_report(None, doc)["final_score"], 0)
        self.assertIsNone(policy.build_proctoring_report({"proctoring_score": 100}, doc)["final_score"])
        self.assertIsNone(policy.build_proctoring_report(state, {"proctoring_config": {}})["final_score"])


class DetectionTests(unittest.TestCase):
    def test_real_frame_decoding_and_mobile_side_view(self):
        import cv2
        import numpy as np
        import security_check
        ok, jpeg = cv2.imencode(".jpg", np.zeros((100, 100, 3), dtype=np.uint8))
        self.assertTrue(ok)
        data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
        frame = security_check.decode_frame(data_url)
        self.assertEqual(frame.shape, (100, 100, 3))
        desktop = security_check.analyze_frame(frame, config={"eyeball_tracking": False, "object_detection": False})
        mobile = security_check.analyze_frame(frame, config={"object_detection": False}, source="mobile")
        self.assertTrue(desktop["available"])
        self.assertEqual(desktop["violations"][0]["type"], "no_face")
        self.assertEqual(mobile["violations"], [])
        with self.assertRaises(ValueError):
            security_check.decode_frame("%%%invalid%%")
        with self.assertRaises(ValueError):
            security_check.decode_frame("x" * (security_check.MAX_FRAME_BYTES * 2 + 1))

    def test_object_and_multiple_person_warnings_require_real_detector_result(self):
        import security_check
        objects = [{"class": "cell phone", "confidence": .9}, {"class": "book", "confidence": .8}, {"class": "person", "confidence": .9}, {"class": "person", "confidence": .85}]
        with patch.object(security_check, "detect_faces", return_value=[]), patch.object(security_check, "_objects", return_value=(True, objects)):
            result = security_check.analyze_frame(None, source="mobile")
        self.assertEqual({v["type"] for v in result["violations"]}, {"phone_detected", "prohibited_object", "multiple_faces"})
        with patch.object(security_check, "detect_faces", side_effect=RuntimeError), patch.object(security_check, "_objects", return_value=(False, [])):
            unavailable = security_check.analyze_frame(None)
        self.assertFalse(unavailable["available"])
        self.assertEqual(unavailable["violations"], [])


class _Collection:
    def __init__(self, docs=()):
        self.docs = list(docs)

    @staticmethod
    def _value(doc, key):
        for part in key.split("."):
            doc = doc.get(part) if isinstance(doc, dict) else None
        return doc

    def find_one(self, query, projection=None):
        return next((copy.deepcopy(doc) for doc in self.docs if all(self._value(doc, key) == value for key, value in query.items())), None)

    def update_one(self, query, update):
        for doc in self.docs:
            if all(self._value(doc, key) == value for key, value in query.items()):
                for key, value in update.get("$set", {}).items():
                    node = doc
                    parts = key.split(".")
                    for part in parts[:-1]:
                        node = node.setdefault(part, {})
                    node[parts[-1]] = copy.deepcopy(value)
                return


class SocketTests(unittest.TestCase):
    def setUp(self):
        from flask import Flask
        from flask_socketio import SocketIO
        self.app = Flask(__name__)
        self.app.config["SECRET_KEY"] = "test"
        self.sio = SocketIO(self.app, async_mode="threading")
        self.doc = {"_id": "db-id", "session_id": "session-a", "user_id": "candidate", "status": "setup", "proctoring_config": {"dual_camera": True, "object_detection": False, "eyeball_tracking": False, "voice_detection": False, "gaze_heatmap": False}}
        self.collection = _Collection([self.doc])
        collections = {"interviews": self.collection, "practice_sessions": _Collection()}
        runtime = types.ModuleType("interview.runtime")
        runtime.live_sessions = {}
        extension = types.ModuleType("extensions")
        extension.socketio = self.sio
        database = types.ModuleType("config.database")
        database.db_config = types.SimpleNamespace(get_collections=lambda: collections)
        auth = types.ModuleType("middleware.auth_middleware")
        auth.decode_user_from_token = lambda token: ({"_id": "candidate" if token == "owner" else "outsider"}, None) if token in {"owner", "outsider"} else (None, "invalid token")
        self.patches = patch.dict(sys.modules, {"interview.runtime": runtime, "extensions": extension, "config.database": database, "middleware.auth_middleware": auth})
        self.patches.start()
        self.addCleanup(self.patches.stop)
        self.runtime = runtime
        self.key = patch.object(policy, "_signing_key", return_value=b"test-pairing-secret")
        self.key.start()
        self.addCleanup(self.key.stop)
        for name in ("sockets.proctoring_sockets", "sockets.mobile_sockets", "sockets.session_access"):
            sys.modules.pop(name, None)
        self.desktop_handlers = importlib.import_module("sockets.proctoring_sockets")
        self.mobile_handlers = importlib.import_module("sockets.mobile_sockets")
        self.owner = self.sio.test_client(self.app, auth={"token": "owner"})
        self.outsider = self.sio.test_client(self.app, auth={"token": "outsider"})
        self.phone = self.sio.test_client(self.app)
        self.addCleanup(self.cleanup_clients)

    def cleanup_clients(self):
        for client in (self.owner, self.outsider, self.phone):
            if client.is_connected():
                client.disconnect()

    def join_phone(self):
        token = policy.create_mobile_pairing_token("session-a", "candidate")
        return self.phone.emit("join_mobile_session", {"session_id": "session-a", "pairing_token": token}, callback=True)

    def test_anonymous_and_other_candidate_cannot_join_control_or_score(self):
        for client in (self.phone, self.outsider):
            result = client.emit("join_interview_session", {"session_id": "session-a"}, callback=True)
            self.assertFalse(result["ok"])
            self.assertFalse(client.emit("control_mobile_recording", {"session_id": "session-a", "action": "start"}, callback=True)["ok"])
        self.assertFalse(self.phone.emit("join_mobile_session", {"session_id": "session-a"}, callback=True)["ok"])
        self.assertTrue(self.owner.emit("join_interview_session", {"session_id": "session-a"}, callback=True)["ok"])
        self.assertTrue(self.join_phone()["ok"])

    def test_setup_camera_preview_and_heartbeat_gate_start_then_disconnect(self):
        import cv2
        import numpy as np
        self.owner.emit("join_interview_session", {"session_id": "session-a"})
        self.assertTrue(self.join_phone()["ok"])
        ready = self.phone.emit("mobile_status_update", {"session_id": "session-a", "status": "ready", "camera_ready": True, "microphone_ready": True}, callback=True)
        self.assertFalse(ready["ready"])
        self.assertFalse(self.phone.emit("mobile_proctoring_frame", {"session_id": "session-a", "image": "bad"}, callback=True)["ok"])
        _, image = cv2.imencode(".jpg", np.zeros((100, 100, 3), dtype=np.uint8))
        frame = base64.b64encode(image).decode()
        preview = self.phone.emit("mobile_proctoring_frame", {"session_id": "session-a", "image": frame}, callback=True)
        self.assertTrue(preview["preview_received"])
        self.assertEqual(self.runtime.live_sessions, {})
        stored = self.collection.find_one({"session_id": "session-a"})
        self.assertTrue(policy.mobile_is_ready(stored))
        self.runtime.live_sessions["session-a"] = {"registered_face": b"registered", "owner_id": "candidate", "analyzed_frames": 0, "infractions": {}}
        self.assertFalse(self.owner.emit("start_proctoring", {"session_id": "session-a"}, callback=True)["ok"])
        self.collection.update_one({"session_id": "session-a"}, {"$set": {"status": "active"}})
        self.assertTrue(self.owner.emit("start_proctoring", {"session_id": "session-a"}, callback=True)["ok"])
        self.owner.get_received()
        self.outsider.get_received()
        scored = self.owner.emit("proctoring_frame", {"session_id": "session-a", "image": frame}, callback=True)
        self.assertTrue(scored["accepted"])
        self.assertEqual(self.runtime.live_sessions["session-a"]["desktop_analyzed_frames"], 1)
        self.assertFalse(any(event["name"] == "proctoring_status" for event in self.outsider.get_received()))
        self.phone.disconnect()
        self.assertFalse(policy.mobile_is_ready(self.collection.find_one({"session_id": "session-a"})))
        self.assertTrue(any(event["name"] == "mobile_disconnected" for event in self.owner.get_received()))

    def test_terminal_companion_rejoin_requires_token_and_grants_no_live_access(self):
        self.collection.update_one({"session_id": "session-a"}, {"$set": {"status": "completed"}})
        self.assertFalse(self.phone.emit("join_mobile_session", {"session_id": "session-a"}, callback=True)["ok"])
        result = self.join_phone()
        self.assertEqual(result, {"ok": True, "session_status": "completed", "terminal": True})
        self.assertFalse(self.phone.emit("mobile_status_update", {"session_id": "session-a", "status": "recording"}, callback=True)["ok"])
        self.assertNotIn("mobile_proctoring", self.collection.find_one({"session_id": "session-a"}))

    def test_replacing_companion_revokes_previous_transport(self):
        self.assertTrue(self.join_phone()["ok"])
        replacement = self.sio.test_client(self.app)
        try:
            token = policy.create_mobile_pairing_token("session-a", "candidate")
            self.assertTrue(replacement.emit("join_mobile_session", {"session_id": "session-a", "pairing_token": token}, callback=True)["ok"])
            self.assertFalse(self.phone.is_connected())
            self.assertTrue(replacement.is_connected())
            self.assertEqual(self.collection.find_one({"session_id": "session-a"})["mobile_proctoring"]["status"], "connected")
        finally:
            if replacement.is_connected():
                replacement.disconnect()


if __name__ == "__main__":
    unittest.main()
