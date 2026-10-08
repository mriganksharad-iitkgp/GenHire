"""Staging-only application load profile with a distinct signed account per user.

Set LOAD_TEST_CANDIDATES_FILE to an untracked JSON array of {token, cv_id}
(e.g. staging.load-test-accounts.json, ignored by Git).
Set LOAD_TEST_JOB_ID and LOAD_TEST_ALLOW_MUTATIONS=1, then run:
  locust -f scripts/dev/locustfile.py --host=https://your-staging-api

Do not reuse one token to simulate thousands of different candidates. This
profile submits one application per user, then reads dashboard state. Set
LOAD_TEST_REPEAT_APPLICATIONS=1 only for the separate abuse/replay scenario.
429/503 are visible failures in the load report and trigger server-directed
backoff; they are not hidden as successful requests. No interview credit or
face/device setup is exercised; test those with the two-device acceptance matrix.
"""
import json
import os
import threading
import time
from collections import deque
from pathlib import Path

from locust import HttpUser, between, task
from locust.exception import StopUser

JOB_ID = os.getenv("LOAD_TEST_JOB_ID", "")
_accounts = None
_lock = threading.Lock()


class ApplicantUser(HttpUser):
    wait_time = between(3, 7)

    def on_start(self):
        global _accounts
        if os.getenv("LOAD_TEST_ALLOW_MUTATIONS") != "1" or not JOB_ID:
            raise StopUser()
        with _lock:
            if _accounts is None:
                path = os.getenv("LOAD_TEST_CANDIDATES_FILE")
                if not path:
                    raise StopUser()
                candidates = json.loads(Path(path).read_text(encoding="utf-8"))
                tokens = [row.get("token") for row in candidates]
                if not candidates or not all(tokens) or len(set(tokens)) != len(tokens):
                    raise ValueError("Use one distinct signed token per simulated candidate")
                _accounts = deque(candidates)
            if not _accounts:
                raise StopUser()
            self.account = _accounts.popleft()
        self.headers = {"Authorization": "Bearer " + self.account["token"]}
        self.retry_at = 0
        self.applied = False
        self.submit()

    def classify(self, response):
        if response.status_code in (429, 503):
            try:
                delay = int(response.headers.get("Retry-After") or 3)
            except ValueError:
                delay = 3
            self.retry_at = time.monotonic() + max(1, delay)
            response.failure("throttled (429)" if response.status_code == 429 else "backpressure (503)")
        elif not response.ok:
            response.failure("unexpected status " + str(response.status_code))
        return response.status_code in (200, 201)

    @task(1)
    def submit(self):
        if time.monotonic() < self.retry_at:
            return
        if self.applied and os.getenv("LOAD_TEST_REPEAT_APPLICATIONS") != "1":
            return
        body = {"cover_letter": "Staging load verification"}
        if self.account.get("cv_id"):
            body["cv_id"] = self.account["cv_id"]
        with self.client.post("/api/jobs/" + JOB_ID + "/apply",
                              name="/api/jobs/:job/apply", json=body,
                              headers=self.headers, catch_response=True) as response:
            if self.classify(response):
                self.applied = True

    @task(4)
    def dashboard(self):
        if time.monotonic() < self.retry_at:
            return
        with self.client.get("/api/applications", headers=self.headers, catch_response=True) as response:
            self.classify(response)
