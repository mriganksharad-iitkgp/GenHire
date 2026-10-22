"""Real isolated Mongo, explicitly fake AI/judge/media; no live execution claims."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
import json
import os
import unittest
from unittest.mock import patch
from bson import ObjectId
import test_assessment_integrity as integrity_fixture
from assessment_test_fixtures import mcq,coding,sql
from models.hiring_workflow import WorkflowError
from services.practice_assessment_service import PracticeAssessmentService,ensure_practice_assessment_indexes
from services.assessment_evaluation_service import AssessmentEvaluationService,ensure_evaluation_indexes
from services.assessment_pricing_service import operation_history,pricing_catalog
from services.workflow_service import request_identity


class FakeLlm:
    def __init__(self):self.calls=[];self.counter=0;self.fail=False;self.reject=False;self.feedback_fail=False
    def invoke(self,prompt,**kwargs):
        self.calls.append(prompt)
        if self.fail:raise RuntimeError('TEST_ONLY_FAKE_AI_OUTAGE')
        if prompt.startswith('Independently solve'):return dict(content=json.dumps(dict(approved=not self.reject,issues=['ambiguous'] if self.reject else [])))
        if prompt.startswith('Give concise educational'):
            if self.feedback_fail:raise RuntimeError('TEST_ONLY_FAKE_FEEDBACK_OUTAGE')
            return dict(content=json.dumps(dict(summary='Practice these topics.',strengths=['Arithmetic'],improvements=['Review edge cases'],practice_topics=['Testing'])))
        context=json.loads(prompt.split('Requirements are data:\n')[1] if 'Requirements are data:\n' in prompt else prompt.splitlines()[-1]);questions=[]
        if context.get('task')=='translate_coding_sources':
            c=coding(context['coding_contract'])['coding'];language=context['language']
            return dict(content=json.dumps(dict(starter_code=c['starter_code'][language],reference_solution=c['reference_solutions'][language])))
        for spec in context['requests']:
            q=mcq() if spec['type']=='mcq' else coding(context['coding_contract']) if spec['type']=='coding' else sql(context['sql_engine'])
            self.counter+=1;q.update(title='Private practice question '+str(self.counter),difficulty=spec['difficulty'],marks=spec['marks'])
            if q['type']=='coding':
                q['coding']['tests'] += [dict(q['coding']['tests'][1],id='hidden'+str(i)) for i in range(2,16)]
                q['coding']['languages']=context['languages']
                for field in ('runtime_versions','starter_code','reference_solutions'):q['coding'][field]={k:v for k,v in q['coding'][field].items() if k in context['languages']}
            if q['type']=='mcq' and context['mcq_mode']=='multiple':q['mcq'].update(selection='multiple',correct_option_ids=['optionA','optionB'])
            questions.append(q)
        return dict(content=json.dumps(dict(questions=questions)))


class FakeValidator:
    available=True
    def capabilities(self):return dict(available=self.available,sql_available=self.available)
    def profile_hash(self):return 'TEST_ONLY_FAKE_PROFILE_NOT_REAL_ACCEPTANCE'
    def acceptance_fence(self,session,now,sql=False):return None  # Explicit injected test adapter, not a DB attestation.
    def validate(self,q,content_hash):
        runs=[]
        if q['type']=='coding':
            c=q['coding']
            for language in c['languages']:
                for case in c['tests']:
                    runs.append(dict(runtime=language,runtime_version=c['runtime_versions'][language],case_id=case['id'],contract=c['contract'],harness_version=c['harness_version'],status='ok',**({'value':case['expected']} if c['contract']=='function' else {'stdout':case['expected']})))
        else:
            c=q['sql']
            for case in c['datasets']:runs.append(dict(runtime=c['engine'],runtime_version=c['engine_version'],case_id=case['id'],status='ok',columns=case['columns'],rows=case['expected_rows']))
        return dict(question_hash=content_hash,adapter_id='TEST_ONLY_FAKE',execution_id='TEST_ONLY_FAKE',isolation_policy_id='TEST_ONLY_FAKE',runs=runs)


class PracticeAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.fixture=integrity_fixture.IntegrityTests(methodName='runTest');self.addCleanup(self.fixture.doCleanups);self.fixture.setUp()
        self.db,self.runtime,self.base=self.fixture.db,self.fixture.runtime,self.fixture.base
        self.actor=self.base.candidate;self.flags=patch.dict(os.environ,dict(GENHIRE_MOCK_OA_ENABLED='true',GENHIRE_MOCK_OA_CONTENT_ACCEPTED='true',GENHIRE_ASSESSMENT_GENERATION_ENABLED='true',GENHIRE_MOCK_OA_CREDITS='30',GENHIRE_OA_EVALUATION_ENABLED='true'))
        self.flags.start();self.addCleanup(self.flags.stop);ensure_practice_assessment_indexes(self.db);ensure_evaluation_indexes(self.db)
        self.llm,self.validator=FakeLlm(),FakeValidator()
        self.service=PracticeAssessmentService(self.db,lambda:self.base.now,runtime=self.runtime,llm=self.llm,validator=self.validator)
        self.runtime.billing.wallet.credit_wallet(str(self.actor['_id']),'candidate',300,'recharge',idempotency_key='practice-test-funds')
        self.config=deepcopy(self.base.config['oa']);self.config.update(source='ai',variant_count=1,advanced_analytics=False,plagiarism_check=False,proctoring_level='basic')
        self.admin=dict(_id=ObjectId(),user_type='admin',permissions=['applications.read','applications.write'])
        self.profile=patch('services.managed_assessment_validator.ManagedAssessmentValidator.profile_hash',return_value=self.validator.profile_hash());self.profile.start();self.addCleanup(self.profile.stop)
        self.capabilities=patch('services.managed_assessment_validator.ManagedAssessmentValidator.capabilities',return_value={'available':True,'sql_available':True});self.capabilities.start();self.addCleanup(self.capabilities.stop)
        self.fence=patch('services.managed_assessment_validator.ManagedAssessmentValidator.acceptance_fence',return_value=None);self.fence.start();self.addCleanup(self.fence.stop)
        labels=coding()['coding']['runtime_versions']
        self.profiles=patch('config.assessment_execution.runtime_profiles',return_value={l:dict(runtime_label=v,compiler_id=1,version_id=2) for l,v in labels.items()});self.profiles.start();self.addCleanup(self.profiles.stop)

    def wallet(self):return self.db.credit_wallets.find_one({'owner_id':str(self.actor['_id']),'audience':'candidate'})
    def buy(self,key='practice-purchase-key'):
        quote=self.service.quote(self.actor,self.config);self.purchase=self.service.purchase(self.actor,quote['quote_id'],key,True);return self.purchase
    def ready(self,key='practice-purchase-key'):
        self.buy(key)
        for _ in range(25):
            self.service.generation_once();p=self.db.practice_assessment_purchases.find_one({'_id':ObjectId(self.purchase['purchase_id'])})
            if p['state']!='generating':break
        self.assertEqual(p['state'],'ready',p.get('error_code'));self.invitation_id=p['invitation_id'];return p
    def start(self):
        grant=self.fixture.integrity.launch(self.actor,self.invitation_id,'practice-secure-launch','kiosk')
        session=self.fixture.integrity.redeem(self.invitation_id,grant['launch_code'],'practice-device-nonce-1234',dict(release_id='1.3.0',kiosk_active=True))
        self.scoped=self.fixture.integrity.authenticate(session['access_token']);self.fixture.integrity.preflight(self.scoped,self.invitation_id,'oa-integrity-v1',dict(visible=True,kiosk_active=True))
        self.scoped=self.fixture.integrity.authenticate(session['access_token']);self.started=self.runtime.start(self.scoped,self.invitation_id,'practice-attempt-start','oa-v1');self.attempt_id=self.started['attempt_id'];return self.started
    def submit(self,answer=None):
        attempt=self.runtime.view(self.scoped,self.attempt_id);revision=0
        if answer is not None:
            self.runtime.save(self.scoped,self.attempt_id,0,'practice-answer-key',{attempt['questions'][0]['id']:answer});revision=1
        return self.runtime.finalize(self.attempt_id,'candidate',self.scoped,revision)

    def test_reserve_generate_capture_scoped_start_resume_and_no_hiring_side_effects(self):
        initial_apps=self.db.applications.count_documents({});initial_jobs=self.db.jobs.count_documents({});self.buy()
        self.assertEqual((self.wallet()['balance'],self.wallet()['reserved_credits']),(270,30))
        self.service.generation_once();self.assertEqual((self.wallet()['balance'],self.wallet()['reserved_credits'],self.wallet()['total_debited']),(270,0,30))
        p=self.db.practice_assessment_purchases.find_one({'_id':ObjectId(self.purchase['purchase_id'])});self.invitation_id=p['invitation_id'];first=self.start()
        second=self.runtime.start(self.scoped,self.invitation_id,'practice-start-replay','oa-v1')
        from services.hiring_progression_service import utc
        self.assertEqual(first['attempt_id'],second['attempt_id']);self.assertEqual(utc(first['deadline']),utc(second['deadline']))
        self.assertEqual(self.db.applications.count_documents({}),initial_apps);self.assertEqual(self.db.jobs.count_documents({}),initial_jobs)
        self.assertEqual(self.db.assessment_question_exposures.find_one({'attempt_id':self.attempt_id})['pool'],'practice')
        with self.assertRaises(WorkflowError):self.runtime.view(self.actor,self.attempt_id)
        self.assertEqual(self.wallet()['total_debited'],30)

    def test_quote_approval_price_change_expiry_and_concurrent_purchase_replay(self):
        quote=self.service.quote(self.actor,self.config)
        with self.assertRaises(WorkflowError):self.service.purchase(self.actor,quote['quote_id'],'not-approved-purchase',False)
        with patch.dict(os.environ,{'GENHIRE_MOCK_OA_CREDITS':'35'}):
            with self.assertRaises(WorkflowError):self.service.purchase(self.actor,quote['quote_id'],'changed-price-purchase',True)
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.service.purchase(self.actor,quote['quote_id'],'concurrent-practice-purchase',True),range(2)))
        self.assertEqual(results[0]['purchase_id'],results[1]['purchase_id']);self.assertEqual(self.db.billing_operations.count_documents({'audience':'candidate'}),1)
        second=self.service.quote(self.actor,self.config)
        with self.assertRaises(WorkflowError):self.service.purchase(self.actor,second['quote_id'],'concurrent-practice-purchase',True)
        self.base.now+=timedelta(minutes=16)
        with self.assertRaises(WorkflowError):self.service.purchase(self.actor,second['quote_id'],'expired-practice-purchase',True)

    def test_generation_failure_returns_reservation_once(self):
        self.buy();self.llm.fail=True;self.service.generation_once();self.service.generation_once()
        self.assertEqual((self.wallet()['balance'],self.wallet()['reserved_credits'],self.wallet()['total_debited']),(300,0,0))
        self.assertEqual(self.db.assessment_versions.count_documents({'pool':'practice'}),0)

    def test_definite_rate_limit_retains_generated_batch_without_duplicate_charge(self):
        from services.llm_fallback_service import LLMRateLimitDeferred
        self.buy()
        original=self.llm.invoke
        refused=False
        def invoke(prompt, **kwargs):
            nonlocal refused
            if prompt.startswith('Independently solve') and not refused:
                refused=True
                raise LLMRateLimitDeferred(2)
            return original(prompt, **kwargs)
        self.llm.invoke=invoke
        self.service.generation_once()
        job=self.db.practice_generation_jobs.find_one({'purchase_id':self.purchase['purchase_id']})
        self.assertEqual(job['state'],'queued')
        self.assertEqual(len(job['generated_questions']),1)
        self.assertEqual(self.wallet()['reserved_credits'],30)
        self.base.now+=timedelta(seconds=5)
        self.service.generation_once()
        self.assertEqual(self.wallet()['total_debited'],30)
        self.assertEqual(sum('Requirements are data:' in p for p in self.llm.calls),1)
        self.assertEqual(self.db.assessment_versions.count_documents({'pool':'practice'}),1)

    def test_history_exposes_only_generation_counts_and_phase(self):
        self.config['sections'][0].update(count=6,difficulty=dict(easy=6,medium=0,hard=0),marks=[1]*6)
        self.buy();self.service.generation_once()
        purchase=self.service.history(self.actor)['purchases'][0]
        self.assertEqual(purchase['progress'],dict(ready_questions=3,total_questions=6,phase='queued'))
        self.assertNotIn('generated_questions',purchase)
        self.assertNotIn('question_version_ids',purchase)

    def test_quality_and_advice_requests_explicitly_instruct_json_transport(self):
        self.service.invoke('Independently solve and check fixture questions.')
        self.assertIn('JSON object',self.llm.calls[-1])
        self.service.invoke('Give concise educational fixture advice.')
        self.assertIn('JSON object',self.llm.calls[-1])

    def test_partial_batch_failure_never_captures_or_publishes_a_short_assessment(self):
        self.config['sections'][0].update(count=6,difficulty=dict(easy=6,medium=0,hard=0),marks=[1]*6)
        self.buy();self.service.generation_once();self.assertEqual(self.wallet()['reserved_credits'],30)
        self.llm.fail=True;self.service.generation_once()
        self.assertEqual((self.wallet()['balance'],self.wallet()['total_debited']),(300,0))
        self.assertEqual(self.db.assessment_versions.count_documents({'pool':'practice'}),0)

    def test_captured_ready_entry_expiry_does_not_reset_or_refund_purchase(self):
        self.ready();self.base.now+=timedelta(days=31);self.service.expire_ready()
        self.assertEqual(self.db.practice_assessment_purchases.find_one({'_id':ObjectId(self.purchase['purchase_id'])})['state'],'expired')
        self.assertEqual(self.wallet()['total_debited'],30)

    def test_generation_rejects_exact_live_content_without_reading_it_into_ai_prompt(self):
        self.buy()
        protected=mcq();protected['title']='Private practice question 1'
        self.db.question_versions.insert_one(dict(pool='recruitment',owner_id=str(self.base.actor['_id']),content_hash=request_identity(protected),content=protected))
        self.service.generation_once();self.assertEqual(self.wallet()['balance'],300)
        self.assertTrue(all('PRIVATE_RECRUITMENT' not in prompt for prompt in self.llm.calls))

    def test_selected_camera_cost_and_missing_media_gate(self):
        self.config['proctoring_level']='dual';quote=self.service.quote(self.actor,self.config)
        self.assertEqual(quote['total_credits'],40)
        with patch.dict(os.environ,{'GENHIRE_OA_MEDIA_ACCEPTED':'false'}):
            with self.assertRaises(WorkflowError):self.service.quote(self.actor,self.config)
        self.assertEqual(self.wallet()['reserved_credits'],0)

    def test_quality_rejection_unknown_external_call_and_disabled_generation_compensate(self):
        self.buy();self.llm.reject=True;self.service.generation_once();self.assertEqual(self.wallet()['balance'],300)
        self.llm.reject=False;self.buy('new-practice-purchase');self.db.practice_generation_jobs.update_one({'purchase_id':self.purchase['purchase_id']},{'$set':{'state':'generating'}})
        calls=len(self.llm.calls);self.service.generation_once();self.assertEqual(len(self.llm.calls),calls);self.assertEqual(self.wallet()['balance'],300)
        self.buy('disabled-practice-purchase')
        with patch.dict(os.environ,{'GENHIRE_MOCK_OA_ENABLED':'false'}):self.service.generation_once()
        self.assertEqual(self.wallet()['balance'],300)

    def test_multi_batch_generation_and_multiple_purchases_respect_existing_unique_indexes(self):
        self.config['sections'][0].update(count=7,difficulty=dict(easy=7,medium=0,hard=0),marks=[1]*7)
        self.ready();self.assertEqual(self.db.question_versions.count_documents({'pool':'practice'}),7)
        self.assertEqual(len(self.llm.calls),6)
        self.ready('second-practice-generation');self.assertEqual(self.db.assessment_versions.count_documents({'pool':'practice'}),2)
        self.assertEqual(self.db.assessment_invitations.count_documents({'pool':'practice'}),2);self.assertEqual(self.wallet()['total_debited'],60)

    def test_objective_practice_report_explanations_and_ai_advice_do_not_change_marks(self):
        self.ready();self.start();self.submit({'option_ids':['optionA']})
        evaluator=AssessmentEvaluationService(self.runtime);evaluator.reconcile();evaluator.tick()
        report=evaluator.report(self.actor,self.attempt_id);self.assertEqual(report['score'],100);self.assertTrue(report['result_available'])
        self.assertIn('correct_option_ids',json.dumps(report));self.assertEqual(report['ai_feedback']['state'],'queued')
        self.service.feedback_once();updated=evaluator.report(self.actor,self.attempt_id)
        self.assertEqual(updated['score'],100);self.assertEqual(updated['ai_feedback']['state'],'completed');self.assertEqual(self.wallet()['total_debited'],30)

    def test_zero_and_unanswered_are_real_marks_and_feedback_outage_is_truthful(self):
        self.ready();self.start();self.submit();evaluator=AssessmentEvaluationService(self.runtime);evaluator.reconcile();evaluator.tick()
        self.llm.feedback_fail=True;self.service.feedback_once();result=evaluator.report(self.actor,self.attempt_id)
        self.assertEqual(result['score'],0);self.assertEqual(result['ai_feedback']['state'],'unavailable');self.assertEqual(self.wallet()['total_debited'],30)

    def test_code_and_sql_contract_matrix_validates_private_pool_without_hidden_report_disclosure(self):
        for index,(kind,contract,engine) in enumerate([('coding','stdin_stdout','postgresql'),('coding','function','postgresql'),('sql','stdin_stdout','sqlite'),('sql','stdin_stdout','duckdb')]):
            self.config.update(coding_contract=contract,sql_engine=engine,sections=[dict(type=kind,count=1,difficulty=dict(easy=1,medium=0,hard=0),marks=[1],weight=100,duration_minutes=5)])
            self.ready('matrix-practice-'+str(index))
            q=self.db.question_versions.find_one({'pool':'practice','purchase_id':self.purchase['purchase_id']})
            self.assertTrue(q['practice_validation']['execution_verified']);self.assertEqual(q['pool'],'practice')
            # This is explicit fake reference evidence, not a real acceptance record.
            self.assertFalse(self.db.assessment_executor_attestations.find_one({}))
            self.start();self.submit();evaluator=AssessmentEvaluationService(self.runtime);evaluator.reconcile();evaluator.tick()
            report=evaluator.report(self.actor,self.attempt_id);self.assertEqual(report['score'],0)
            encoded=json.dumps(report,default=str)
            for hidden in ('PRIVATE_INPUT','PRIVATE_OUTPUT','9371','reference_query','reference_solutions'):self.assertNotIn(hidden,encoded)
        self.assertEqual(self.wallet()['total_debited'],120)

    def test_missing_executor_and_unimplemented_extras_cannot_be_purchased(self):
        self.config['sections'][0]['type']='coding';self.validator.available=False
        with self.assertRaises(WorkflowError):self.service.quote(self.actor,self.config)
        self.assertEqual(self.wallet()['reserved_credits'],0)
        self.config['sections'][0]['type']='mcq';self.config['advanced_analytics']=True
        with self.assertRaises(WorkflowError):self.service.quote(self.actor,self.config)

    def test_real_acceptance_fence_refuses_missing_attestation_even_with_stubbed_capabilities(self):
        self.fence.stop()
        from services.managed_assessment_validator import ManagedAssessmentValidator
        from core.mongo_transactions import atomic
        with self.assertRaises(WorkflowError):atomic(self.db,lambda session:ManagedAssessmentValidator(self.db).acceptance_fence(session,self.base.now))
        self.assertEqual(self.db.assessment_executor_attestations.count_documents({}),0)

    def test_paid_snapshot_not_repriced_and_own_history_billing_is_private(self):
        self.buy()
        with patch.dict(os.environ,{'GENHIRE_MOCK_OA_CREDITS':'45'}):self.service.generation_once()
        self.assertEqual(self.wallet()['total_debited'],30)
        operations=operation_history(self.db,self.actor)['operations'];self.assertEqual(operations[0]['price_snapshot']['total_credits'],30)
        self.assertEqual(operation_history(self.db,dict(self.actor,_id=ObjectId()))['operations'],[])
        with self.assertRaises(WorkflowError):operation_history(self.db,dict(self.actor,_id=ObjectId()),identifier=operations[0]['operation_id'])
        self.assertEqual(self.service.history(self.actor)['purchases'][0]['price']['total_credits'],30)

    def test_admin_verified_platform_failure_refunds_completed_purchase_once(self):
        self.ready();self.start();self.submit();evaluator=AssessmentEvaluationService(self.runtime);evaluator.reconcile()
        result=evaluator.platform_failure(self.admin,self.attempt_id,'practice-technical-failure','Operator verified permanently unusable platform execution.')
        self.assertEqual(result['state'],'unavailable');self.assertEqual(self.wallet()['balance'],300)
        evaluator.platform_failure(self.admin,self.attempt_id,'practice-technical-failure','Operator verified permanently unusable platform execution.')
        self.assertEqual(self.wallet()['balance'],300);self.assertEqual(self.db.billing_refunds.count_documents({}),1)

    def test_recruiter_cannot_access_practice_report_or_evidence_and_admin_can_accommodate(self):
        self.ready()
        with self.assertRaises(WorkflowError):self.service.invitation(self.base.actor,self.db.assessment_invitations.find_one({'_id':ObjectId(self.invitation_id)}))
        self.fixture.integrity.accommodate(self.admin,self.invitation_id,'practice-browser-accommodation',0,'Functional assistive browser accommodation approved.',True,False,10)
        policy=self.service.invitation(self.actor,self.db.assessment_invitations.find_one({'_id':ObjectId(self.invitation_id)}))['integrity_policy']
        self.assertEqual((policy['mode'],policy['extra_minutes']),('browser',10))

    def test_verified_ready_or_active_platform_failure_refund_and_retained_answers(self):
        for index,active in enumerate((False,True)):
            self.ready('support-practice-'+str(index))
            if active:
                self.start();attempt=self.runtime.view(self.scoped,self.attempt_id)
                self.runtime.save(self.scoped,self.attempt_id,0,'support-saved-answer',{attempt['questions'][0]['id']:{'option_ids':['optionA']}})
            key='support-disposition-'+str(index);reason='Operator verified an irrecoverable platform setup fault with logs.'
            with self.assertRaises(WorkflowError):self.service.platform_failure(self.actor,self.purchase['purchase_id'],key,reason)
            result=self.service.platform_failure(self.admin,self.purchase['purchase_id'],key,reason)
            self.assertEqual(result['billing_action'],'refund');self.assertEqual(self.service.platform_failure(self.admin,self.purchase['purchase_id'],key,reason),result)
            self.assertEqual(self.wallet()['balance'],300)
            if active:
                self.assertTrue(self.db.assessment_submissions.find_one({'attempt_id':self.attempt_id})['answers'])
                self.assertEqual(self.db.assessment_attempts.find_one({'_id':ObjectId(self.attempt_id)})['state'],'unavailable')

    def test_public_code_run_and_deadline_submission_share_runtime_without_hiring_events(self):
        self.config.update(coding_contract='function',sections=[dict(type='coding',count=1,difficulty=dict(easy=1,medium=0,hard=0),marks=[1],weight=100,duration_minutes=5)])
        p=self.ready();inv=self.db.assessment_invitations.find_one({'_id':ObjectId(self.invitation_id)})
        from services.hiring_progression_service import utc
        self.base.now=utc(inv['start_closes_at'])-timedelta(seconds=1);self.start()
        view=self.runtime.view(self.scoped,self.attempt_id);self.assertNotIn('9371',json.dumps(view,default=str))
        from services.assessment_public_run_service import AssessmentPublicRunService
        public=AssessmentPublicRunService(self.runtime);result=public.create(self.scoped,self.attempt_id,'practice-public-run',view['questions'][0]['id'],dict(language='python',source='def solve(value): return value'),{'value':4})
        self.assertEqual(set(result),{'run_id'})
        self.assertGreater(utc(self.started['deadline']),utc(inv['start_closes_at']))
        self.base.now=utc(self.started['deadline'])+timedelta(seconds=1);self.runtime.expire_due()
        self.assertEqual(self.db.assessment_attempts.find_one({'_id':ObjectId(self.attempt_id)})['state'],'submitted')
        self.assertEqual(self.db.stage_events.count_documents({'operation_key':{'$regex':self.attempt_id}}),0)

    def test_live_pool_substitution_and_direct_content_collision_fail_closed(self):
        self.ready();p=self.db.practice_assessment_purchases.find_one({'_id':ObjectId(self.purchase['purchase_id'])})
        q=self.db.question_versions.find_one({'pool':'practice'});self.db.question_versions.update_one({'_id':q['_id']},{'$set':{'pool':'recruitment'}})
        with self.assertRaises(WorkflowError):self.service.checked_content(p)
        self.assertEqual(self.db.assessment_attempts.count_documents({'pool':'practice'}),0)

    def test_http_public_catalog_private_purchase_history_and_candidate_quote(self):
        from flask import Flask
        from routes.practice_assessment_routes import create_practice_assessment_routes
        app=Flask(__name__);app.register_blueprint(create_practice_assessment_routes(self.db));client=app.test_client()
        self.assertEqual(client.get('/api/pricing/catalog').status_code,200)
        self.assertEqual(client.get('/api/practice/assessments').status_code,401)
        with patch('middleware.auth_middleware.decode_user_from_token',return_value=(self.actor,None)):
            response=client.get('/api/practice/assessments',headers={'Authorization':'Bearer TEST_ONLY_FAKE_ACCOUNT'})
            self.assertEqual(response.status_code,200);self.assertEqual(response.headers['Cache-Control'],'private, no-store')
            with patch('services.managed_assessment_validator.ManagedAssessmentValidator.capabilities',return_value={'available':False}):
                catalog=client.get('/api/practice/assessments/catalog',headers={'Authorization':'Bearer TEST_ONLY_FAKE_ACCOUNT'}).json
                self.assertEqual(catalog['section_availability'],dict(mcq=True,coding=False,sql=False))
                self.assertTrue(catalog['purchase_ready'])
            with patch.dict(os.environ,{'GENHIRE_MOCK_OA_CREDITS':'39'}):self.assertEqual(client.get('/api/pricing/catalog').json['credits']['mock_oa'],39)
