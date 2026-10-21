"""Synthetic operator preflight failures; no paid transport or real attestation."""
from datetime import datetime, timezone
import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import mongomock
from models.hiring_workflow import WorkflowError
from services.assessment_executor_preflight import ExecutorPreflight, REVIEW_CHECKS


class PreflightSafetyTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().db
        self.worker = ExecutorPreflight(self.db)
        self.worker.validator = SimpleNamespace(capabilities=lambda: {'available': True}, profile_hash=lambda:'synthetic-test-profile',
            client=Mock(side_effect=WorkflowError('catalog_unavailable', 'Synthetic catalog outage.', 503)))
        self.db.assessment_executor_attestations.insert_one({'profile_hash':'synthetic-test-profile','state':'passed'})
        self.review = dict(policy_id='test-policy', reviewed_by='test-operator', evidence_reference='synthetic-private-fixture',
                           reviewed_at=datetime.now(timezone.utc).isoformat(), **{key:True for key in REVIEW_CHECKS})
        environment=patch.dict(os.environ, {'GENHIRE_EXECUTOR_ISOLATION_POLICY_ID':'test-policy',
            'GENHIRE_SPHERE_MONTHLY_SUBMISSION_LIMIT':'500', 'GENHIRE_SQL_MONTHLY_EXECUTION_LIMIT':'200'})
        environment.start(); self.addCleanup(environment.stop)

    def test_insufficient_monthly_budget_preserves_current_acceptance_and_dispatches_nothing(self):
        month=datetime.now(timezone.utc).strftime('%Y-%m')
        self.db.sql_execution_limits.insert_one({'_id':month,'count':189})
        with self.assertRaises(WorkflowError) as error: self.worker.run(self.review)
        self.assertEqual(error.exception.code, 'preflight_budget_insufficient')
        self.worker.validator.client.assert_not_called()
        self.assertEqual(self.db.assessment_executor_preflights.count_documents({}), 0)
        self.assertEqual(self.db.assessment_executor_attestations.find_one({})['state'], 'passed')

    def test_catalog_failure_is_audited_and_revokes_instead_of_sticking_in_checking(self):
        self.assertEqual(self.worker.check_budget(), {'sphere':28,'sql':12})
        with patch('config.assessment_execution.runtime_profiles', return_value={}):
            with self.assertRaises(WorkflowError): self.worker.run(self.review)
        self.assertEqual(self.db.assessment_executor_preflights.find_one({})['error_code'], 'catalog_unavailable')
        self.assertEqual(self.db.assessment_executor_attestations.find_one({})['state'], 'failed')
