"""Exercise the real optional-body route and report retries without accounts."""
import ast
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import MagicMock
from flask import Flask, jsonify, request
from services import interview_completion_service as completion


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.collection = MagicMock()
        self.collection.find_one.return_value = {"session_id": "one", "user_id": "owner"}
        self.collection.update_one.return_value.matched_count = 1
        self.release = threading.Event()
        self.started = threading.Event()
        self.calls = []
        def finish(user, sid, data):
            self.calls.append((user, sid, data))
            self.started.set()
            self.release.wait(2)
            return jsonify({"status": "interview_ended", "interview_score": 71})
        source = ast.parse((Path(__file__).parents[1] / "routes/interview_routes.py").read_text(encoding="utf-8"))
        fn = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "end_interview")
        fn.decorator_list = []
        namespace = {"request": request, "jsonify": jsonify, "interviews_collection": self.collection, "_complete_interview": finish}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "interview_routes.py", "exec"), namespace)
        self.app.add_url_rule("/end", view_func=lambda: namespace["end_interview"]({"_id": "owner"}, "one"), methods=["POST"])
        completion._jobs.clear()

    def tearDown(self):
        self.release.set()
        for future, _ in list(completion._jobs.values()):
            future.result(timeout=3)
        completion._jobs.clear()

    def test_empty_post_and_json_post_observe_one_report_job(self):
        client = self.app.test_client()
        start = time.monotonic()
        response = client.post("/end")
        self.assertEqual(response.status_code, 202)
        self.assertLess(time.monotonic() - start, .3)
        self.assertTrue(response.json["report_pending"])
        self.assertTrue(self.started.wait(1))
        self.assertEqual(client.post("/end", json={}).status_code, 202)
        self.release.set()
        future = next(iter(completion._jobs.values()))[0]
        future.result(timeout=1)
        result = client.post("/end", json={})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["interview_score"], 71)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][2], {})

    def test_other_owner_and_invalid_body_do_not_queue_work(self):
        client = self.app.test_client()
        self.assertEqual(client.post("/end", json=[]).status_code, 400)
        self.release.set()
        self.assertEqual(client.post("/end", json=["invalid"]).status_code, 400)
        self.collection.find_one.return_value = None
        self.assertEqual(client.post("/end").status_code, 404)

    def test_another_worker_lease_is_polled_without_duplicate_completion(self):
        self.collection.update_one.return_value.matched_count = 0
        client = self.app.test_client()
        self.assertEqual(client.post("/end").status_code, 202)
        self.assertEqual(self.calls, [])
        self.collection.update_one.return_value.matched_count = 1
        self.release.set()
        response = client.post("/end")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.calls), 1)


if __name__ == "__main__":
    unittest.main()
