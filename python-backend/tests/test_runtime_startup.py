"""Local runtime/index regressions; no credentials or live database."""
import importlib.util
from pathlib import Path
import sys
import socket
import time
import unittest
from unittest.mock import patch
import mongomock
from pymongo.errors import DuplicateKeyError

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from config.indexes import ensure_application_identity_index
from core import runtime


class ApplicationIndexTests(unittest.TestCase):
    def test_existing_unique_variants_are_reused_and_still_enforce_duplicates(self):
        for keys, options in (([("job_id", 1), ("student_id", 1)], {}),
                              ([("job_id", 1), ("student_id", 1)], {"sparse": True}),
                              ([("student_id", 1), ("job_id", 1)], {})):
            collection = mongomock.MongoClient().db.applications
            collection.create_index(keys, name="uq_applications_job_student", unique=True, **options)
            before = collection.index_information()
            self.assertEqual(ensure_application_identity_index(collection), "uq_applications_job_student")
            self.assertEqual(before, collection.index_information())
            collection.insert_one({"job_id":"job", "student_id":"candidate"})
            with self.assertRaises(DuplicateKeyError):
                collection.insert_one({"job_id":"job", "student_id":"candidate"})

    def test_restrictive_partial_index_does_not_satisfy_guard(self):
        collection = mongomock.MongoClient().db.applications
        collection.create_index([("job_id", 1), ("student_id", 1)], unique=True,
                                partialFilterExpression={"is_visible": True}, name="visible_only")
        self.assertEqual(ensure_application_identity_index(collection), "uq_applications_job_student")
        self.assertIn("visible_only", collection.index_information())

    def test_missing_guard_is_created_without_deleting_records(self):
        collection = mongomock.MongoClient().db.applications
        collection.insert_one({"job_id":"job", "student_id":"candidate"})
        ensure_application_identity_index(collection)
        self.assertEqual(collection.count_documents({}), 1)
        self.assertTrue(collection.index_information()["uq_applications_job_student"]["unique"])


class RuntimeTests(unittest.TestCase):
    def test_incomplete_runtime_produces_actionable_instructions(self):
        missing = {"ready":False, "missing":["Flask-SocketIO"]}
        with patch.object(runtime, "runtime_status", return_value=missing), patch.object(runtime, "select_runtime", return_value=missing):
            with self.assertRaises(SystemExit) as error:
                runtime.ensure_local_runtime()
        self.assertIn("requirements.txt", str(error.exception))
        self.assertIn("Flask-SocketIO", str(error.exception))

    def test_complete_current_runtime_is_not_relaunched(self):
        ready = {"ready":True, "executable":sys.executable}
        with patch.object(runtime, "runtime_status", return_value=ready), patch.object(runtime, "select_runtime", return_value=ready), patch.object(runtime.os, "execv") as execute:
            runtime.ensure_local_runtime()
        execute.assert_not_called()


    def test_windows_handoff_waits_and_propagates_exit_code(self):
        start = time.monotonic()
        code = runtime.run_foreground(sys.executable, ["-c", "import time; time.sleep(0.15); raise SystemExit(7)"])
        self.assertEqual(code, 7)
        self.assertGreaterEqual(time.monotonic() - start, 0.15)

    def test_windows_runtime_selection_uses_foreground_handoff(self):
        current = {"ready":False, "executable":sys.executable}
        selected = {"ready":True, "executable":sys.executable + "-backend", "version":"3.12"}
        with patch.object(runtime, "runtime_status", return_value=current), patch.object(runtime, "select_runtime", return_value=selected), patch.object(runtime, "replace_process", side_effect=SystemExit(9)) as launch:
            with self.assertRaises(SystemExit) as error:
                runtime.ensure_local_runtime()
        self.assertEqual(error.exception.code, 9)
        launch.assert_called_once_with(selected["executable"], sys.argv)

    def test_busy_port_has_actionable_error(self):
        with socket.socket() as server:
            server.bind(("0.0.0.0", 0))
            server.listen(1)
            with self.assertRaises(SystemExit) as error:
                runtime.check_local_port(server.getsockname()[1])
        self.assertIn("Ctrl+C", str(error.exception))
        self.assertIn("port", str(error.exception))

    def test_invalid_port_is_rejected(self):
        with self.assertRaises(SystemExit):
            runtime.check_local_port(0)


if __name__ == "__main__":
    unittest.main()
