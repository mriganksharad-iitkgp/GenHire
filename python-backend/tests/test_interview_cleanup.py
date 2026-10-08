"""Abandoned setup and restart evidence regressions; no MongoDB/provider calls."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


class InterviewCleanupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        wallet_module = types.ModuleType("payment_module.services.wallet_service")
        wallet_module.WalletService = MagicMock()
        spec = importlib.util.spec_from_file_location("_interview_cleanup_under_test", BACKEND / "services/interview_credit_service.py")
        cls.service = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"payment_module.services.wallet_service": wallet_module}):
            spec.loader.exec_module(cls.service)

    def setUp(self):
        self.collections = {name: MagicMock() for name in ("users", "interviews", "applications", "jobs", "practice_sessions")}
        self.collections["interviews"].find.return_value = []
        self.collections["practice_sessions"].find.return_value = []
        for name in ("interviews", "practice_sessions"):
            self.collections[name].find_one.side_effect = lambda query, name=name: next(
                (doc for doc in self.collections[name].find.return_value if doc.get("_id") == query.get("_id")), None)
        self.manager = SimpleNamespace(sessions={})

    def test_sweep_includes_setup_and_finishing(self):
        self.service.run_refund_sweep_once(self.collections, self.manager)
        for name in ("interviews", "practice_sessions"):
            query = self.collections[name].find.call_args.args[0]
            self.assertIn("setup", query["status"]["$in"])
            self.assertIn("finishing", query["status"]["$in"])
            self.assertIn("$or", query)

    def test_memory_loss_does_not_refund_recorded_answers(self):
        doc = {"_id": "doc", "session_id": "session", "qa_pairs": [{"answer": "A substantive answer"}]}
        self.collections["interviews"].find.return_value = [doc]
        with patch.object(self.service, "finalize_stale_real_interview") as finalize, patch.object(self.service, "refund_stale_real_interview") as refund:
            stats = self.service.run_refund_sweep_once(self.collections, self.manager)
        finalize.assert_called_once()
        self.assertIsNone(finalize.call_args.args[3])
        refund.assert_not_called()
        self.assertEqual(stats["real_finalized"], 1)

    def test_sweep_rechecks_staleness_after_end_or_new_answer(self):
        self.collections["interviews"].find.return_value = [{"_id": "doc", "session_id": "session"}]
        self.collections["interviews"].find_one.side_effect = None
        self.collections["interviews"].find_one.return_value = None
        with patch.object(self.service, "finalize_stale_real_interview") as finalize, patch.object(self.service, "refund_stale_real_interview") as refund:
            stats = self.service.run_refund_sweep_once(self.collections, self.manager)
        finalize.assert_not_called(); refund.assert_not_called()
        self.assertEqual(stats["real_refunded"], 0)

    def test_interrupted_report_retains_transcript_and_no_invented_score(self):
        transcript = [{"role": "user", "text": "My answer"}]
        self.service.finalize_stale_real_interview(self.collections, self.manager,
            {"_id": "doc", "session_id": "session", "transcript": transcript,
             "proctoring_config": {"object_detection": False, "eyeball_tracking": False,
                "voice_detection": False, "gaze_heatmap": False, "dual_camera": False}}, None)
        update = self.collections["interviews"].update_one.call_args.args[1]["$set"]
        self.assertEqual(update["status"], "completed")
        self.assertEqual(update["transcript"], transcript)
        self.assertIsNone(update["final_score"])
        self.assertIsNone(update["proctoring_score"])
        self.assertEqual(update["evaluation"]["score_status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
