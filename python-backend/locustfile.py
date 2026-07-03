"""
Load-test script for the two scale-critical paths this platform is sold on:
"a recruiter posts one job and gets up to ~2000 applicants."

  1. ApplicantUser  — concurrent job-application submissions, the endpoint
     Step 5 added rate limiting to (10/hour/IP) — this test intentionally
     exercises that limit so you can see the 429 behavior under load, not
     just the happy path.
  2. InterviewCandidateUser — concurrent AI-interview sessions (start +
     several answer submissions), the other half of the "2000 candidates"
     scenario once they've been screened in.

This is a ready-to-run tool, not a completed test run — it needs a live
backend plus seeded test data (see the "SETUP" section below) that doesn't
exist in an automated coding session. Actually running it and interpreting
the results (error rates, p95 latency, whether the CV-scoring background
queue or the bulk-invite email dispatch fall behind under load) is a
follow-up step for you.

SETUP
-----
1. Start the backend normally (`python app.py`) against a real/staging Mongo.
2. Seed test data:
   - At least one recruiter account with one published job (note its job_id).
   - At least one candidate account per simulated user, each with a CV already
     uploaded (job application requires a CV on file — see
     controllers/application_controller.py's apply_for_job).
   - Log in as a seeded candidate via POST /api/login to get a JWT, or reuse
     one you already have from the app.
3. Export the env vars below, then run Locust:

     export LOAD_TEST_JOB_ID=<a real job id>
     export LOAD_TEST_TOKEN=<a candidate JWT>
     locust -f locustfile.py --host=http://localhost:5000

   Locust opens a web UI (default http://localhost:8089) where you set the
   number of simulated users and spawn rate — start small (e.g. 50 users)
   before working up toward the ~2000-candidate scenario this product is
   sold on, since the CV-scoring background queue (services/background_processor.py)
   is a single serial worker and will visibly queue up long before the API
   layer itself falls over.
"""

import os
import random

from locust import HttpUser, task, between

JOB_ID = os.getenv("LOAD_TEST_JOB_ID", "")
AUTH_TOKEN = os.getenv("LOAD_TEST_TOKEN", "")


def _auth_headers():
    return {"Authorization": f"Bearer {AUTH_TOKEN}"} if AUTH_TOKEN else {}


class ApplicantUser(HttpUser):
    """Simulates a candidate repeatedly applying to the same job posting —
    the exact scenario the Step 5 rate limit (10/hour/IP) exists to blunt."""

    wait_time = between(1, 3)

    @task
    def apply_to_job(self):
        if not JOB_ID:
            return
        with self.client.post(
            f"/api/jobs/{JOB_ID}/apply",
            json={"cover_letter": "Excited to apply for this role."},
            headers=_auth_headers(),
            catch_response=True,
        ) as response:
            if response.status_code == 429:
                # Expected once a simulated user exceeds the rate limit —
                # mark it a success so it doesn't skew the failure rate; the
                # point of this scenario is to *observe* how often this
                # happens under realistic concurrency, not to treat it as a bug.
                response.success()
            elif response.status_code >= 500:
                response.failure(f"Unexpected server error: {response.status_code}")


class InterviewCandidateUser(HttpUser):
    """Simulates a candidate taking the AI interview end-to-end: start a
    session, then answer a handful of questions in sequence."""

    wait_time = between(2, 5)

    def on_start(self):
        self.session_id = None
        self.current_question = None

    @task
    def take_interview(self):
        if not AUTH_TOKEN:
            return

        start_resp = self.client.post(
            "/api/interviews/start",
            json={},
            headers=_auth_headers(),
            name="/api/interviews/start",
        )
        if start_resp.status_code != 200:
            return

        data = start_resp.json()
        self.session_id = data.get("session_id")
        questions = data.get("initial_questions") or []
        self.current_question = questions[0] if questions else None
        if not self.session_id or not self.current_question:
            return

        sample_answers = [
            "I have several years of experience building and shipping this kind of system.",
            "I'd approach it by first understanding the requirements, then designing for scale.",
            "In my last role I led a similar project end-to-end, from design through deployment.",
        ]

        # Simulate answering a handful of questions in one session, mirroring
        # a real interview rather than a single request.
        for _ in range(3):
            answer_resp = self.client.post(
                f"/api/interviews/{self.session_id}/answer",
                json={
                    "question": self.current_question,
                    "answer": random.choice(sample_answers),
                },
                headers=_auth_headers(),
                name="/api/interviews/[session_id]/answer",
            )
            if answer_resp.status_code != 200:
                break
            answer_data = answer_resp.json()
            if answer_data.get("interview_complete"):
                break
            self.current_question = answer_data.get("next_question")
            if not self.current_question:
                break
