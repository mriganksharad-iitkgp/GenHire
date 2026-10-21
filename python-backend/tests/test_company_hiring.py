"""Local transactional company workflows; outbound mail/storage are explicit fakes."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
import io
import json
import os
import unittest
from unittest.mock import patch
from bson import ObjectId
import test_assessment_evaluation as evaluation_fixture
from models.hiring_workflow import WorkflowError
from services.company_hiring_service import CompanyHiringService, ensure_company_indexes
from services.screening_export_service import build_stage_export


class CompanyHiringTests(unittest.TestCase):
    def setUp(self):
        self.fixture = evaluation_fixture.EvaluationTests(methodName='runTest'); self.addCleanup(self.fixture.doCleanups); self.fixture.setUp()
        self.base, self.db = self.fixture.base, self.fixture.db
        self.flag = patch.dict(os.environ, {'GENHIRE_COMPANY_HIRING_ENABLED': 'true'}); self.flag.start(); self.addCleanup(self.flag.stop)
        ensure_company_indexes(self.db); self.service = CompanyHiringService(self.db, lambda: self.base.now)
        self.actor, self.candidate = self.base.actor, self.base.candidate
        self.fixture.submit(answer={'option_ids': ['optionA']}); self.fixture.evaluation.tick()
        self.app_id = str(self.base.app()['_id']); self.attempt_id = self.fixture.attempt_id
        self.db.applications.update_one({'_id': ObjectId(self.app_id)}, {'$set': dict(student_name='Candidate', student_email=self.candidate['email'])})

    def action(self, action, key=None, **kwargs):
        return self.service.action(self.actor, self.app_id, action, self.base.app()['workflow']['revision'], key or 'company-'+action, 'Reviewed objective results and company requirements.', **kwargs)

    def clone(self, **fields):
        app = deepcopy(self.base.app()); app['_id'] = ObjectId(); app.update(fields); self.db.applications.insert_one(app); return app

    def preview(self, items=None):
        return self.service.preview(self.actor, self.base.job_id, items or [self.app_id], 'Company interview invitation', 'Please contact our team to arrange your interview. <private>')

    def queue(self):
        preview = self.preview(); return self.service.queue(self.actor, self.base.job_id, preview['preview_id'], 'email-queue-key', True)

    def test_private_decision_release_safe_summary_revoke_and_unchanged_grades(self):
        report = self.fixture.report(); self.action('qualify')
        self.assertFalse(self.fixture.evaluation.report(self.candidate, self.attempt_id)['result_available'])
        candidate_history = self.service.workflow.history(self.app_id, self.candidate)
        self.assertIn('oa_review_updated', [e['action'] for e in candidate_history['events']])
        self.assertNotIn('company_qualify', json.dumps(candidate_history, default=str))
        self.assertEqual(next(s for s in self.base.app()['workflow']['stages'] if s['type'] == 'oa')['outcome'], 'pending')
        self.action('release')
        safe = self.fixture.evaluation.report(self.candidate, self.attempt_id)
        self.assertEqual((safe['summary']['score'], safe['summary']['outcome']), (100, 'cleared'))
        encoded = json.dumps(safe, default=str)
        self.assertNotIn('questions', encoded); self.assertNotIn('reason', encoded); self.assertNotIn('input_hash', encoded)
        self.action('revoke_release'); self.assertFalse(self.fixture.evaluation.report(self.candidate, self.attempt_id)['result_available'])
        self.assertEqual(self.fixture.report()['questions'], report['questions']); self.assertEqual(self.fixture.wallet()['total_debited'], 35)

    def test_concurrent_decision_replay_and_conflict(self):
        revision = self.base.app()['workflow']['revision']
        def qualify(_): return self.service.action(self.actor, self.app_id, 'qualify', revision, 'concurrent-qualification', 'Reviewed objective assessment results.')
        with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(qualify, range(2)))
        self.assertEqual(results[0], results[1]); self.assertEqual(self.db.company_decisions.count_documents({}), 1)
        with self.assertRaises(WorkflowError): self.service.action(self.actor, self.app_id, 'hold', revision, 'concurrent-qualification', 'Reviewed objective assessment results.')

    def test_qualification_holds_for_integrity_and_stale_review_blocks_advance(self):
        self.db.assessment_attempts.update_one({'_id': ObjectId(self.attempt_id)}, {'$set': {'integrity_policy': {'tier': 'basic'}}})
        with self.assertRaises(WorkflowError) as error: self.action('qualify')
        self.assertEqual(error.exception.code, 'integrity_hold')
        self.db.assessment_integrity_summaries.insert_one(dict(attempt_id=self.attempt_id, review_revision=1, review={'decision': 'reviewed_clear'}))
        self.action('qualify'); self.action('add_company_stage', name='Technical discussion')
        self.db.assessment_integrity_summaries.update_one({'attempt_id': self.attempt_id}, {'$set': {'review_revision': 2, 'review.decision': 'needs_followup'}})
        with self.assertRaises(WorkflowError) as error: self.action('advance')
        self.assertEqual(error.exception.code, 'decision_stale')

    def test_custom_company_round_manual_hire_and_stage_history(self):
        self.action('qualify'); self.action('add_company_stage', name='Technical discussion'); self.action('add_company_stage', key='add-hr-stage', name='HR discussion')
        first = self.action('advance'); self.assertTrue(first['current_stage_id'].startswith('company_'))
        self.assertFalse(self.fixture.evaluation.report(self.candidate, self.attempt_id)['result_available'])
        self.service.workflow.transition(self.app_id, self.actor, 'clear', first['revision'], 'technical-clear-key', 'Company interviewer approved technical round.')
        second = self.action('advance', key='advance-hr-key')
        result = self.service.workflow.transition(self.app_id, self.actor, 'clear', second['revision'], 'hr-clear-key', 'Company interviewer approved HR round.')
        hired = self.service.workflow.transition(self.app_id, self.actor, 'hire', result['revision'], 'company-hired-key', 'Company confirmed the final hiring decision.')
        self.assertEqual(hired['lifecycle'], 'hired')
        history = self.service.workflow.history(self.app_id, self.candidate)
        self.assertTrue(all(set(event) <= {'revision', 'action', 'occurred_at'} for event in history['events']))
        self.assertEqual(self.db.application_stages.count_documents({'application_id': self.app_id, 'type': 'company'}), 2)

    def test_missing_evaluation_not_converted_to_failed_candidate(self):
        self.db.assessment_evaluation_reports.update_one({'attempt_id': self.attempt_id}, {'$set': {'state': 'unavailable', 'score': None}})
        for action in ('qualify', 'not_qualify', 'hold'):
            with self.assertRaises(WorkflowError) as error: self.action(action)
            self.assertEqual(error.exception.code, 'result_unavailable')

    def test_screening_only_pipeline_can_add_and_enter_company_round(self):
        workflow = self.base.app()['workflow']
        screening = next(s for s in workflow['stages'] if s['type'] == 'screening'); screening.update(state='completed', outcome='cleared')
        next(s for s in workflow['stages'] if s['type'] == 'oa').update(enabled=False, state='skipped')
        workflow['current_stage_id'] = screening['stage_id']
        self.db.applications.update_one({'_id': ObjectId(self.app_id)}, {'$set': {'workflow': workflow}})
        self.action('add_company_stage', name='Company portfolio discussion'); self.action('advance')
        stage = next(s for s in self.base.app()['workflow']['stages'] if s['stage_id'] == self.base.app()['workflow']['current_stage_id'])
        self.assertEqual((stage['type'], stage['state']), ('company', 'eligible'))

    def test_threshold_override_has_reason_without_rewriting_objective_recommendation(self):
        self.db.assessment_evaluation_reports.update_one({'attempt_id': self.attempt_id}, {'$set': {'recommendation': 'not_cleared', 'score': 0}})
        self.action('qualify'); self.action('release')
        self.assertEqual(self.fixture.report()['score'], 0); self.assertEqual(self.fixture.report()['recommendation'], 'not_cleared')
        self.assertEqual(self.fixture.evaluation.report(self.candidate, self.attempt_id)['summary']['outcome'], 'cleared')

    def test_changed_decision_withdraws_old_release(self):
        self.action('qualify'); self.action('release'); self.action('not_qualify')
        self.assertFalse(self.fixture.report()['released']); self.assertNotIn('released_summary', self.fixture.report())

    def test_bulk_partial_outcomes_scope_stale_and_replay(self):
        other = self.clone(job_id=str(ObjectId()))
        revision = self.base.app()['workflow']['revision']
        items = [dict(application_id=self.app_id, expected_revision=revision), dict(application_id=str(other['_id']), expected_revision=revision)]
        result = self.service.bulk(self.actor, self.base.job_id, items, 'qualify', 'bulk-qualified-key', 'Reviewed each selected objective result.')
        self.assertEqual([item['ok'] for item in result['outcomes']], [True, False])
        again = self.service.bulk(self.actor, self.base.job_id, items, 'qualify', 'bulk-qualified-key', 'Reviewed each selected objective result.')
        self.assertTrue(again['outcomes'][0]['ok'])
        with self.assertRaises(WorkflowError) as error:
            self.service.bulk(self.actor, self.base.job_id, items[:1], 'qualify', 'bulk-qualified-key', 'Reviewed each selected objective result.')
        self.assertEqual(error.exception.code, 'idempotency_conflict')
        stale = self.service.bulk(self.actor, self.base.job_id, items[:1], 'hold', 'bulk-stale-key', 'Reviewed each selected objective result.')
        self.assertEqual(stale['outcomes'][0]['error_code'], 'stale_revision')

    def test_owner_admin_read_permissions_candidate_and_disabled_writes(self):
        for actor in (dict(self.actor, _id=ObjectId()), self.candidate):
            with self.assertRaises(WorkflowError): self.service.rows(actor, self.base.job_id)
            with self.assertRaises(WorkflowError): self.service.detail(actor, self.app_id)
        admin = dict(_id=ObjectId(), user_type='admin', permissions=['applications.read'])
        self.assertEqual(len(self.service.rows(admin, self.base.job_id)['rows']), 1)
        self.assertEqual(self.service.detail(admin, self.app_id)['objective_recommendation'], 'review_required')
        with self.assertRaises(WorkflowError): self.service.action(admin, self.app_id, 'qualify', self.base.app()['workflow']['revision'], 'read-admin-key', 'A sufficiently detailed decision reason.')
        with patch.dict(os.environ, {'GENHIRE_COMPANY_HIRING_ENABLED': 'false'}):
            with self.assertRaises(WorkflowError): self.action('qualify')
            self.assertEqual(len(self.service.rows(self.actor, self.base.job_id)['rows']), 1)

    def test_filtered_comparison_pagination_funnel_and_safe_export(self):
        self.clone(student_name='Other candidate')
        page = self.service.rows(self.actor, self.base.job_id, limit=1)
        self.assertTrue(page['has_more']); self.assertEqual(len(self.service.rows(self.actor, self.base.job_id, after=page['next_after'], limit=1)['rows']), 1)
        self.assertEqual(sum(item['count'] for item in page['funnel']), 2)
        filtered = self.service.rows(self.actor, self.base.job_id, qualification='review_required')
        self.assertEqual(len(filtered['rows']), 1)
        rows = self.service.export(self.actor, self.base.job_id); rows[0]['name'] = '=HYPERLINK("bad")'
        csv = build_stage_export(rows, 'csv').decode('utf-8-sig'); self.assertIn("'=HYPERLINK", csv); self.assertNotIn('input_hash', csv); self.assertNotIn('reason', csv)
        from openpyxl import load_workbook
        workbook = load_workbook(io.BytesIO(build_stage_export(rows, 'xlsx')))
        self.assertEqual(workbook.active.cell(2, 2).data_type, 's')

    def test_preview_deduplicates_contacts_without_sending_and_explicit_queue_replay(self):
        duplicate = self.clone()
        preview = self.preview([self.app_id, str(duplicate['_id'])])
        self.assertEqual((len(preview['recipients']), len(preview['skipped'])), (1, 1))
        with self.assertRaises(WorkflowError): self.service.queue(self.actor, self.base.job_id, preview['preview_id'], 'queue-approval-key', False)
        result = self.service.queue(self.actor, self.base.job_id, preview['preview_id'], 'queue-approval-key', True)
        self.assertEqual(self.service.queue(self.actor, self.base.job_id, preview['preview_id'], 'queue-approval-key', True), result)
        self.assertEqual(self.db.company_messages.count_documents({}), 1)

    def test_preview_expiry_and_changed_contact_or_revision_rejected(self):
        preview = self.preview(); self.action('qualify')
        with self.assertRaises(WorkflowError) as error: self.service.queue(self.actor, self.base.job_id, preview['preview_id'], 'stale-preview-key', True)
        self.assertEqual(error.exception.code, 'preview_stale'); self.assertEqual(self.db.company_messages.count_documents({}), 0)
        preview = self.preview(); self.base.now += timedelta(minutes=11)
        with self.assertRaises(WorkflowError) as error: self.service.queue(self.actor, self.base.job_id, preview['preview_id'], 'expired-preview-key', True)
        self.assertEqual(error.exception.code, 'preview_expired')

    def test_email_sender_off_by_default_and_changed_stage_cancelled(self):
        self.queue(); calls = []
        self.assertFalse(self.service.deliver_once(lambda *args: calls.append(args) or True)); self.assertEqual(calls, [])
        self.action('qualify')
        with patch.dict(os.environ, {'GENHIRE_HIRING_EMAILS_ENABLED': 'true'}): self.service.deliver_once(lambda *args: calls.append(args) or True)
        self.assertEqual(calls, []); self.assertEqual(self.db.company_messages.find_one({})['state'], 'cancelled')

    def test_unknown_delivery_not_retried_and_admin_evidence_reconciliation(self):
        self.queue(); calls = []
        with patch.dict(os.environ, {'GENHIRE_HIRING_EMAILS_ENABLED': 'true'}):
            self.assertTrue(self.service.deliver_once(lambda *args: calls.append(args) or False))
            self.assertFalse(self.service.deliver_once(lambda *args: calls.append(args) or True))
        self.assertEqual(len(calls), 1); self.assertIn('&lt;private&gt;', calls[0][2])
        doc = self.db.company_messages.find_one({}); self.assertEqual(doc['state'], 'delivery_unknown')
        with self.assertRaises(WorkflowError): self.service.reconcile_delivery(self.actor, str(doc['_id']), 'confirmed_sent', 'Provider log confirms delivery identifier 123.', 'reconcile-denied-key')
        result = self.service.reconcile_delivery(self.fixture.admin, str(doc['_id']), 'confirmed_sent', 'Provider log confirms delivery identifier 123.', 'reconcile-confirmed-key')
        self.assertEqual(result['state'], 'sent')

    def test_parallel_dispatch_claims_one_message_and_noop_is_not_delivery(self):
        self.queue(); calls = []
        with patch.dict(os.environ, {'GENHIRE_HIRING_EMAILS_ENABLED': 'true'}):
            with ThreadPoolExecutor(max_workers=2) as pool: list(pool.map(lambda _: self.service.deliver_once(lambda *args: calls.append(args) or True), range(2)))
        self.assertEqual(len(calls), 1); self.assertEqual(self.db.company_messages.find_one({})['state'], 'sent')

    def test_noop_provider_cannot_mark_queued_message_sent(self):
        self.queue()
        from types import SimpleNamespace
        with patch.dict(os.environ, {'GENHIRE_HIRING_EMAILS_ENABLED': 'true'}), patch('services.email_service.EmailService', return_value=SimpleNamespace(provider=SimpleNamespace(name='noop'))):
            self.assertFalse(self.service.deliver_once())
        self.assertEqual(self.db.company_messages.find_one({})['state'], 'queued')

    def test_revoked_recruiter_authorization_cancels_queued_email(self):
        self.queue(); self.db.users.update_one({'_id': self.actor['_id']}, {'$set': {'is_verified': False}})
        calls = []
        with patch.dict(os.environ, {'GENHIRE_HIRING_EMAILS_ENABLED': 'true'}): self.service.deliver_once(lambda *args: calls.append(args) or True)
        self.assertEqual(calls, []); self.assertEqual(self.db.company_messages.find_one({})['state'], 'cancelled')

    def test_http_auth_exports_and_nested_delivery_serialization(self):
        from flask import Flask
        from routes.company_hiring_routes import create_company_hiring_routes
        app = Flask(__name__); app.register_blueprint(create_company_hiring_routes(self.db)); client = app.test_client()
        self.assertEqual(client.get('/api/jobs/'+self.base.job_id+'/company-candidates').status_code, 401)
        with patch('middleware.auth_middleware.decode_user_from_token', return_value=(self.actor, None)):
            headers = {'Authorization': 'Bearer TEST_ONLY_FAKE_ACCOUNT_TOKEN'}
            response = client.get('/api/jobs/'+self.base.job_id+'/company-candidates', headers=headers)
            self.assertEqual(response.status_code, 200); self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
            response = client.get('/api/jobs/'+self.base.job_id+'/exports?format=csv', headers=headers)
            self.assertEqual(response.status_code, 200); self.assertIn('attachment', response.headers['Content-Disposition'])
            batch = self.queue(); response = client.get('/api/jobs/'+self.base.job_id+'/communications/'+batch['batch_id'], headers=headers)
            self.assertEqual(response.status_code, 200); self.assertIsInstance(response.json['messages'][0]['_id'], str)
