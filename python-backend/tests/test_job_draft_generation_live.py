"""Opt-in paid-provider QA, always using the disposable loopback test database.

Set GENHIRE_LIVE_DRAFT_QA=1 and GENHIRE_LIVE_PROVIDER_ENV_FILE to a private
server env file, then run through scripts/dev/run_workflow_integration.py.
GENHIRE_LIVE_OA_PROFILE=backend24 selects a synthetic 20-MCQ/4-coding workload.
Never publishes, executes generated code, or uses a real recruiter wallet.
"""
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from bson import ObjectId
from dotenv import dotenv_values
from workflow_test_support import MongoTestCase


@unittest.skipUnless(os.getenv('GENHIRE_LIVE_DRAFT_QA') == '1', 'Paid provider QA is explicitly opt-in.')
class FullDraftLiveTests(MongoTestCase):
    def test_real_jd_and_selected_questions_complete_for_one_charge(self):
        from models.job_setup import default_setup, template
        from services.job_draft_generation_service import JobDraftGenerationService
        from services.llm_fallback_service import create_assessment_llm_service

        source = Path(os.environ['GENHIRE_LIVE_PROVIDER_ENV_FILE']).resolve(strict=True)
        values = dotenv_values(source)
        allowed = {'GROQ_API_KEY', 'GOOGLE_API_KEY', 'DEEPSEEK_API_KEY', 'OPENAI_API_KEY',
            'DEEPSEEK_API_BASE', 'LLM_PROVIDER_PRIORITY', 'LLM_PRIMARY_PROVIDER',
            'LLM_SECONDARY_PROVIDER', 'LLM_TERTIARY_PROVIDER', 'LLM_GROQ_MODEL',
            'LLM_DEEPSEEK_MODEL', 'LLM_GEMINI_MODEL', 'GROQ_JSON_MAX_OUTPUT_TOKENS','GENHIRE_ASSESSMENT_GROQ_FALLBACK_MODEL'}
        env = {key: value for key, value in values.items() if key in allowed and value}
        env.update(GENHIRE_ASSESSMENT_GENERATION_ENABLED='true', RECRUITER_AI_JD_CREDITS='10')
        with patch.dict(os.environ, env):
            actor = dict(_id=ObjectId(), user_type='recruiter', is_verified=True)
            self.db.users.insert_one(actor)
            setup = default_setup()
            preset = template('data_scientist')
            setup['pipeline']['oa_enabled'] = True
            setup['oa'].update(template_id='data_scientist', sections=preset['sections'],
                duration_minutes=preset['duration_minutes'], mcq_mode='mixed')
            # Prefer small, fully specified tasks here: this checks orchestration
            # and schema completeness, not semantic or performance acceptance.
            setup['oa']['instructions'] = ('Synthetic QA. Coding problems: maximum contiguous sum and '
                'longest substring without duplicate characters. Use concise valid inputs, 16 cases each. '
                'SQL: grouped employee totals. MCQs: distinct Python, SQL, HTTP and data fundamentals.')
            brief = 'Synthetic QA: hire a Data Engineer in Remote, full time, 2 years experience. Salary competitive; Python and SQL required.'
            document = ''
            if os.getenv('GENHIRE_LIVE_OA_PROFILE') == 'backend24':
                setup['oa'].update(template_id='web_developer',specialization='backend',mcq_mode='single',duration_minutes=120,
                    sections=[dict(type=kind,count=count,difficulty=dict(easy=0,medium=count,hard=0),marks=[marks]*count,weight=weight,duration_minutes=minutes)
                        for kind,count,marks,weight,minutes in [('mcq',20,1,30,30),('coding',4,25,70,90)]])
                setup['oa']['instructions']='Create distinct backend engineering questions with compact adversarial inputs and concise correct references. Use 16 coding tests per problem.'
                brief='Synthetic QA only: hire a Backend Developer, remote, full-time, with Python, SQL, APIs and data structures skills. Salary competitive.'
            if os.getenv('GENHIRE_LIVE_OA_PROFILE') == 'backend_coding':
                setup['oa'].update(template_id='web_developer',specialization='backend',mcq_mode='single',duration_minutes=45,
                    sections=[dict(type='coding',count=1,difficulty=dict(easy=0,medium=1,hard=0),marks=[25],weight=100,duration_minutes=45)])
                setup['oa']['instructions']='Create one medium backend algorithm problem with 16 compact tests and correct reference solutions. No real company or candidate data.'
                brief='Synthetic QA: hire a Backend Developer, remote, full-time, Python and data structures required, salary competitive.'
            expected=sum(section['count'] for section in setup['oa']['sections'])
            expected_types={section['type'] for section in setup['oa']['sections'] if section['count']}
            service = JobDraftGenerationService(self.db, llm=create_assessment_llm_service())
            service.billing.wallet.credit_wallet(str(actor['_id']), 'recruiter', 100, 'recharge', idempotency_key='live-qa-only')
            service.enqueue(actor, brief, setup, 'live-full-draft-qa', 10, document)
            deadline = time.monotonic() + 900
            previous = None
            while time.monotonic() < deadline:
                service.run_once()
                result = service.get(actor, 'live-full-draft-qa')
                progress = (result['state'], result['completed_questions'], result.get('phase'), result.get('error_code'))
                if progress != previous:
                    print('LIVE QA state/count/phase/error:', progress, flush=True)
                    previous = progress
                if result['state'] in {'completed', 'failed'}:
                    break
                time.sleep(2)
            self.assertEqual(result['state'], 'completed', {k:result.get(k) for k in ('state','error_code','failure_stage','completed_questions')})
            self.assertEqual(len(result['questions']), expected)
            self.assertEqual({q['type'] for q in result['questions']}, expected_types)
            self.assertEqual(self.db.question_versions.count_documents({}), expected)
            wallet = self.db.credit_wallets.find_one({'owner_id':str(actor['_id'])})
            self.assertEqual((wallet['balance'], wallet['reserved_credits']), (90, 0))
            self.assertEqual(self.db.jobs.count_documents({}), 0)
            print('LIVE QA PASS: JD plus',expected,'configured questions; one 10-credit test charge; no published jobs.', flush=True)
