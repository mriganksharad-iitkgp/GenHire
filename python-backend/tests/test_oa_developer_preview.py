"""Local harness contracts; real Mongo, no real compiler dispatch in this suite."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/dev'))
from oa_preview_app import Preview,create_app,fixture_questions,assert_preview_database
from workflow_test_support import MongoTestCase
from models.assessment_content import blueprint_match


class DeveloperPreviewTests(MongoTestCase):
    def setUp(self):
        super().setUp()
        self.local=self.db.client['genhire_oa_preview_'+uuid4().hex]
        self.addCleanup(lambda:self.db.client.drop_database(self.local.name))
        self.flags=patch.dict(os.environ,{'GENHIRE_ASSESSMENT_EXECUTION_ENABLED':'true','GENHIRE_EXECUTOR_ISOLATION_POLICY_ID':'dev-only',
            'OA_EXECUTION_PROVIDER':'onlinecompiler','OA_GENERIC_SQL_PROVIDER':'onlinecompiler','ONLINECOMPILER_API_KEY':'synthetic',
            'OA_ENABLE_SQLITE':'true','OA_ENABLE_DUCKDB':'true'})
        self.flags.start();self.addCleanup(self.flags.stop)
        self.preview=Preview(self.local)
        self.client=create_app(self.preview,'synthetic-preview-token').test_client()
        self.headers={'X-GenHire-Dev-Token':'synthetic-preview-token','Origin':'http://localhost:3000'}

    def test_loopback_database_and_origin_token_host_guards(self):
        with self.assertRaises(RuntimeError):assert_preview_database(self.db)
        self.assertEqual(self.client.get('/dev/status').status_code,401)
        for key,value in [('Origin','https://evil.example'),('Host','evil.example')]:
            self.assertEqual(self.client.get('/dev/status',headers={**self.headers,key:value}).status_code,403)
        self.assertEqual(self.client.options('/dev/status',headers={'Origin':'http://localhost:3000'}).status_code,204)

    def test_actual_candidate_workspace_is_prefilled_without_wallet_or_attestation(self):
        result=self.client.get('/api/assessment-attempts/'+self.preview.attempt_id,headers=self.headers)
        self.assertEqual(result.status_code,200)
        value=result.get_json();self.assertEqual(len(value['questions']),25);self.assertEqual(len(value['answers']),25)
        self.assertNotIn('reference_solutions',str(value));self.assertNotIn('hidden1',str(value))
        self.assertEqual(self.local.assessment_executor_attestations.count_documents({}),0)
        self.assertEqual(self.local.credit_transactions.count_documents({}),0)
        self.assertEqual(self.local.credit_wallets.count_documents({}),0)
        self.assertEqual(self.client.get('/api/assessment-attempts/000000000000000000000000',headers=self.headers).status_code,404)

    def test_reset_selectors_obey_real_blueprint_and_typed_contracts(self):
        for engine in ('sqlite','duckdb'):
            for contract in ('stdin_stdout','function'):
                result=self.client.post('/dev/reset',json=dict(engine=engine,contract=contract),headers=self.headers)
                self.assertEqual(result.status_code,200)
                attempt=self.local.assessment_attempts.find_one({'_id':__import__('bson').ObjectId(result.get_json()['attempt_id'])})
                blueprint_match(attempt['configuration'],fixture_questions(engine,contract))
        self.assertEqual(self.client.post('/dev/reset',json=dict(engine='postgresql'),headers=self.headers).status_code,400)

    def test_final_submission_uses_real_immutable_snapshot_and_reset_cannot_duplicate_it(self):
        before=self.local.assessment_attempts.find_one({})
        response=self.client.post('/dev/reset',json=dict(scenario='wrong',submit=True),headers=self.headers)
        self.assertEqual(response.status_code,200)
        submitted=self.local.assessment_submissions.find_one({})
        self.assertEqual(len(submitted['answers']),25);self.assertEqual(submitted['state'],'awaiting_evaluator')
        self.assertEqual(self.client.post('/dev/reset',json=dict(submit=True),headers=self.headers).status_code,409)
        self.assertEqual(self.local.assessment_submissions.count_documents({}),1)
        self.assertEqual(self.local.oa_provider_requests.count_documents({}),0)
        self.assertIsNotNone(before)

    def test_public_run_is_enqueued_through_real_service_without_hidden_cases_in_response(self):
        snapshot=self.preview.runtime.view(self.preview.actor,self.preview.attempt_id)
        qid=snapshot['questions'][0]['id'];answer=snapshot['answers'][qid]
        result=self.client.post('/api/assessment-attempts/'+self.preview.attempt_id+'/runs',
            json=dict(operation_key='developer-public-run',question_id=qid,answer=answer),headers=self.headers)
        self.assertEqual(result.status_code,200)
        self.assertEqual(set(result.get_json()),{'run_id'})
        record=self.local.assessment_public_runs.find_one({})
        self.assertEqual(record['purpose'] if 'purpose' in record else record['state'],'queued')
        self.assertEqual(self.local.oa_provider_requests.count_documents({}),0)


if __name__=='__main__':unittest.main()
