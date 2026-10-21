"""Opt-in real-provider practice QA, with only synthetic data and a loopback DB.

No application accounts, wallet funds, execution attestations or kiosks are used.
"""
import os
from pathlib import Path
import time
import re
import unittest
from datetime import timedelta
from unittest.mock import patch
from dotenv import dotenv_values
import test_practice_assessment as practice_fixture


@unittest.skipUnless(os.getenv('GENHIRE_LIVE_PRACTICE_QA') == '1', 'Real provider QA is explicitly opt-in.')
class LivePracticeTests(unittest.TestCase):
    def test_synthetic_mcq_generation_checks_and_publishes_once(self):
        fixture=practice_fixture.PracticeAssessmentTests(methodName='runTest')
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        initial_jobs=fixture.db.jobs.count_documents({})
        allowed={'GROQ_API_KEY','GOOGLE_API_KEY','DEEPSEEK_API_KEY','OPENAI_API_KEY',
            'DEEPSEEK_API_BASE','LLM_PROVIDER_PRIORITY','LLM_PRIMARY_PROVIDER','LLM_SECONDARY_PROVIDER',
            'LLM_TERTIARY_PROVIDER','LLM_GROQ_MODEL','LLM_DEEPSEEK_MODEL','LLM_GEMINI_MODEL',
            'GROQ_JSON_MAX_OUTPUT_TOKENS','GENHIRE_ASSESSMENT_GROQ_FALLBACK_MODEL'}
        values=dotenv_values(Path(os.environ['GENHIRE_LIVE_PROVIDER_ENV_FILE']).resolve(strict=True))
        with patch.dict(os.environ,{k:v for k,v in values.items() if k in allowed and v}):
            from services.llm_fallback_service import create_assessment_llm_service
            fixture.service.llm=create_assessment_llm_service()
            original=fixture.service.llm.invoke
            def diagnostic_invoke(prompt, **options):
                try:return original(prompt, **options)
                except Exception as error:
                    words={'schema','response_format','unsupported','not','supported','invalid','valid','messages','max_tokens','json','model','strict','parameter','required','properties','additionalproperties','less','greater','temperature','reasoning','tokens','limit'}
                    for provider,leaf in getattr(error,'errors',[]):
                        hint=' '.join(w for w in re.findall(r'[a-z_]+',str(leaf).lower()) if w in words)[:180]
                        print('LIVE provider diagnostic:',provider,type(leaf).__name__,getattr(leaf,'status_code',None),'hint=',hint,flush=True)
                    raise
            fixture.service.llm.invoke=diagnostic_invoke
            fixture.config.update(instructions='Synthetic private practice QA: distinct Python and HTTP fundamentals. No real candidate or company data.',
                sections=[dict(type='mcq',count=6,difficulty=dict(easy=3,medium=3,hard=0),marks=[1]*6,weight=100,duration_minutes=10)],duration_minutes=10)
            fixture.buy('synthetic-live-practice-qa')
            deadline=time.monotonic()+300
            while time.monotonic()<deadline:
                fixture.service.generation_once()
                purchase=fixture.service.history(fixture.actor)['purchases'][0]
                print('LIVE practice state/count:',purchase['state'],purchase['progress']['ready_questions'],flush=True)
                if purchase['state']!='generating':break
                time.sleep(2);fixture.base.now+=timedelta(seconds=2)
            self.assertEqual(purchase['state'],'ready',purchase.get('error_code'))
            self.assertEqual(purchase['progress']['ready_questions'],6)
            self.assertEqual(fixture.wallet()['total_debited'],30)
            self.assertEqual(fixture.wallet()['reserved_credits'],0)
            self.assertEqual(fixture.db.billing_operations.count_documents({'audience':'candidate'}),1)
            self.assertEqual(fixture.db.jobs.count_documents({}),initial_jobs)
            print('LIVE practice PASS: 6 original MCQs plus quality checks, one test-wallet capture; no real accounts charged.',flush=True)
