"""Opt-in local service/Mongo benchmark. Never calls a provider or application DB.

GENHIRE_RUN_OA_LOAD=true with the disposable replica-set runner enables it.
This is not an HTTP, secure-device, media, coding-judge or staging capacity claim.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import platform
from threading import Barrier
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from bson import ObjectId
from assessment_test_fixtures import coding
import test_assessment_runtime as runtime_fixture
from services.assessment_evaluation_service import AssessmentEvaluationService, ensure_evaluation_indexes
from services.oa_operations import snapshot
from scripts.admin.audit_workflow_foundation import audit
from models.hiring_workflow import WorkflowError


@unittest.skipUnless(os.getenv('GENHIRE_RUN_OA_LOAD') == 'true', 'Opt-in 100-client local benchmark.')
class PilotLoadTests(unittest.TestCase):
    def test_100_active_attempts_saves_submits_billing_and_bounded_queue(self):
        fixture = runtime_fixture.RuntimeTests(methodName='runTest')
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        db, base, runtime = fixture.db, fixture.base, fixture.runtime
        flags = patch.dict(os.environ, dict(JWT_SECRET_KEY='local-benchmark-only-not-a-production-key',
            GENHIRE_OA_EVALUATION_ENABLED='true', GENHIRE_OA_INTEGRITY_ENABLED='false',
            GENHIRE_OA_EXECUTION_QUEUE_LIMIT='25', GENHIRE_OA_EXECUTION_CONCURRENCY='2'))
        flags.start(); self.addCleanup(flags.stop)
        ensure_evaluation_indexes(db)
        base.billing.wallet.credit_wallet(str(base.actor['_id']), 'recruiter', 1000, 'recharge', idempotency_key='load-fixture-credit')
        original_app = base.app()
        original_invitation = deepcopy(fixture.invitation)
        original_events = list(db.stage_events.find({'application_id': str(original_app['_id'])}))
        original_views = list(db.application_stages.find({'application_id': str(original_app['_id'])}))
        actors = [(base.candidate, str(original_invitation['_id']))]
        # Copy only test fixture enrollment snapshots; no live publication gate
        # or real proctoring acceptance is bypassed by a production code path.
        for _ in range(99):
            actor = dict(base.candidate, _id=ObjectId())
            db.users.insert_one(actor)
            app = deepcopy(original_app); app['_id'] = ObjectId(); app['student_id'] = str(actor['_id'])
            invitation = deepcopy(original_invitation); invitation['_id'] = ObjectId()
            invitation.update(application_id=str(app['_id']), candidate_id=str(actor['_id']))
            next(s for s in app['workflow']['stages'] if s['type'] == 'oa')['invitation_id'] = str(invitation['_id'])
            db.applications.insert_one(app); db.assessment_invitations.insert_one(invitation)
            for collection, documents in ((db.stage_events, original_events), (db.application_stages, original_views)):
                copies = []
                for document in documents:
                    copied = deepcopy(document); copied['_id'] = ObjectId(); copied['application_id'] = str(app['_id'])
                    if copied.get('invitation_id'):
                        copied['invitation_id'] = str(invitation['_id'])
                    copies.append(copied)
                if copies: collection.insert_many(copies)
            actors.append((actor, str(invitation['_id'])))
        report = dict(scope='local Python services + disposable Mongo; one MCQ, no HTTP/media/providers',
            state='in_progress',
            clients=100, api_processes=1, mongo_nodes=1, mongo_max_pool_size=db.client.options.pool_options.max_pool_size, logical_cpus=os.cpu_count(),
            platform=platform.platform(), processor=platform.processor(), phases={},
            provider_calls=0, measured_provider_cost_usd=0,
            exclusions=['HTTP/TLS/Redis', 'kiosk/device accessibility', 'camera/GCS/detector', 'AI/code/SQL latency, quotas and cost'])
        target = Path(__file__).resolve().parents[2] / '.tmp/oa-step10-load.json'
        target.parent.mkdir(exist_ok=True)
        def persist():
            target.write_text(json.dumps(report, indent=2), encoding='utf-8')
        persist()

        def phase(name, items, operation, workers=100):
            barrier = Barrier(workers)
            def timed(item):
                barrier.wait(timeout=60)
                begin = time.perf_counter()
                try:
                    return operation(item), (time.perf_counter()-begin)*1000, None
                except Exception as exc:
                    return None, (time.perf_counter()-begin)*1000, getattr(exc, 'code', type(exc).__name__)
            begin = time.perf_counter()
            with ThreadPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(timed, items))
            elapsed = time.perf_counter()-begin
            durations = sorted(row[1] for row in results)
            errors = [row[2] for row in results if row[2]]
            report['phases'][name] = dict(operations=len(items), workers=workers, elapsed_seconds=round(elapsed, 3),
                p50_ms=round(durations[math.ceil(len(durations)*.5)-1], 2),
                p95_ms=round(durations[math.ceil(len(durations)*.95)-1], 2),
                p99_ms=round(durations[math.ceil(len(durations)*.99)-1], 2), errors=errors)
            print('OA_LOAD_PHASE '+name+' '+json.dumps(report['phases'][name]), flush=True)
            persist()
            self.assertFalse(errors, (name, errors))
            return [row[0] for row in results]

        attempts = phase('start', actors, lambda item: runtime.start(item[0], item[1], 'load-start-key', 'oa-v1'))
        self.assertEqual(db.assessment_attempts.count_documents({'state': 'in_progress'}), 100)
        qid = runtime.view(actors[0][0], attempts[0]['attempt_id'])['questions'][0]['id']
        items = list(zip(actors, attempts))
        phase('autosave', items, lambda item: runtime.save(item[0][0], item[1]['attempt_id'], 0, 'load-save-key', {qid: {'option_ids': ['optionA']}}))
        phase('submit', items, lambda item: runtime.finalize(item[1]['attempt_id'], 'candidate', item[0][0], 1))
        self.assertEqual(db.assessment_submissions.count_documents({}), 100)
        evaluator = AssessmentEvaluationService(runtime)
        evaluator.execution.executor = SimpleNamespace(profile_hash=lambda: 'local-unvalidated-no-provider')
        evaluator.reconcile(limit=100)
        # Exactly one evaluator claim per item; eight parallel durable workers.
        phase('mcq_evaluation', list(range(100)), lambda _: evaluator.tick(), workers=4)
        self.assertEqual(db.assessment_evaluation_reports.count_documents({'state': 'complete', 'score': 100}), 100)
        wallet = db.credit_wallets.find_one({})
        self.assertEqual((wallet['reserved_credits'], wallet['total_debited']), (0, 530))
        reconciliation = audit(db, base.job_id, str(base.actor['_id']))
        self.assertFalse(reconciliation['workflow_issues'], reconciliation)
        self.assertFalse(reconciliation['billing_issues'], reconciliation)
        q = coding()
        def enqueue(index):
            try:
                evaluator.execution.enqueue('load-task-'+str(index), q, 'hidden1', 'python', 'private test source', 'grading', 'load-fixture')
                return 'accepted'
            except WorkflowError as exc:
                if exc.code != 'execution_queue_full': raise
                return 'backpressure'
        admissions = phase('queue_admission', list(range(100)), enqueue)
        self.assertEqual(admissions.count('accepted'), 25)
        self.assertEqual(admissions.count('backpressure'), 75)
        phase('execution_claim', list(range(100)), lambda _: bool(evaluator.execution.claim()))
        capacity = snapshot(db, base.now)['execution_capacity']
        self.assertEqual((capacity['active'], capacity['held_tasks'], capacity['queued_counter'], capacity['queued_tasks']), (2, 2, 23, 23))
        report.update(state='local_checks_passed_not_production_acceptance', reconciliation=reconciliation, queue=dict(submitted=100, admitted=25, backpressure=75, capacity=capacity),
                      wallet=dict(captured_credits=530, reserved_credits=0), peak_active_attempts=100)
        persist()
        print('OA_LOCAL_LOAD '+json.dumps(report))
