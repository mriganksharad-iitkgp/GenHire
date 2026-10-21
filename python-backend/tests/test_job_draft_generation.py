from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
from unittest.mock import patch
from bson import ObjectId
from workflow_test_support import MongoTestCase
from assessment_test_fixtures import mcq, coding, sql
from models.job_setup import default_setup
from models.hiring_workflow import WorkflowError
from services.job_draft_generation_service import JobDraftGenerationService


class JobDraftGenerationTests(MongoTestCase):
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ, {'RECRUITER_AI_JD_CREDITS':'10','GENHIRE_ASSESSMENT_GENERATION_ENABLED':'true'})
        env.start();self.addCleanup(env.stop)
        self.actor=dict(_id=ObjectId(),user_type='recruiter',is_verified=True)
        self.db.users.insert_one(self.actor)
        self.setup=default_setup();self.setup['pipeline']['oa_enabled']=True
        self.setup['oa']['sections']=[dict(type=kind,count=1,difficulty=dict(easy=1,medium=0,hard=0),marks=[1],weight=weight,duration_minutes=10)
            for kind,weight in [('mcq',20),('coding',50),('sql',30)]]
        self.data=dict(title='Data Engineer',department='Engineering',location='Remote',type='Full-time',experience='2 years',salary='Competitive',
            description='Build reliable data applications.',skills=['Python','SQL'],responsibilities=['Build'],requirements=['SQL'],benefits=[])
        class LLM:
            calls=0
            def invoke(inner,prompt,**kwargs):
                inner.calls+=1
                context=json.loads(prompt.split('Avoid repeated questions.\n')[1].split('\nThe previous output')[0])
                if context.get('task')=='translate_coding_sources':
                    source=coding()['coding'];language=context['language']
                    return dict(content=json.dumps(dict(starter_code=source['starter_code'][language],reference_solution=source['reference_solutions'][language])))
                spec=context['requests'][0];q={'mcq':mcq,'coding':coding,'sql':sql}[spec['type']]()
                if spec['type']=='coding':
                    languages=context['languages'];q['coding']['languages']=languages
                    for key in ('starter_code','reference_solutions','runtime_versions'):
                        q['coding'][key]={language:q['coding'][key][language] for language in languages}
                    q['coding']['tests']=[dict(q['coding']['tests'][i%2],id='case'+str(i+1)) for i in range(16)]
                q.update(difficulty=spec['difficulty'],marks=spec['marks'])
                return dict(content=json.dumps({'questions':[q]}))
        self.llm=LLM();self.jd_calls=0
        def jd(brief,owner):
            self.jd_calls+=1
            return dict(job_data=deepcopy(self.data)),200
        self.service=JobDraftGenerationService(self.db,self.llm,jd)
        self.service.billing.wallet.credit_wallet(str(self.actor['_id']),'recruiter',100,'recharge',idempotency_key='draft-test-funding')

    def enqueue(self,key='draft-operation-1',setup=None):
        return self.service.enqueue(self.actor,'Hire a data engineer',setup or self.setup,key,10)

    def wallet(self):
        return self.db.credit_wallets.find_one({'owner_id':str(self.actor['_id'])})

    def test_whole_jd_and_three_types_cost_ten_and_remain_unvalidated_private_drafts(self):
        job=self.enqueue();self.assertEqual(self.wallet()['balance'],90)
        self.assertEqual(self.wallet()['reserved_credits'],10)
        self.assertTrue(self.service.run_once())
        result=self.service.get(self.actor,'draft-operation-1')
        self.assertEqual(result['state'],'completed');self.assertEqual(result['credits'],10)
        self.assertEqual([q['type'] for q in result['questions']],['mcq','coding','sql'])
        self.assertEqual(result['job_data']['status'],'draft')
        self.assertEqual(self.wallet()['balance'],90);self.assertEqual(self.wallet()['reserved_credits'],0)
        self.assertEqual(self.db.question_versions.count_documents({'source':'ai'}),3)
        self.assertEqual(self.db.question_validations.count_documents({}),0)
        self.assertEqual(self.db.assessment_versions.count_documents({}),0)
        self.assertEqual(self.db.jobs.count_documents({}),0)
        self.assertEqual(self.enqueue()['id'],job['id'])
        self.assertFalse(self.service.run_once());self.assertEqual(self.llm.calls,6)

    def test_jd_only_has_same_price_and_no_question_calls(self):
        c=deepcopy(self.setup);c['pipeline']['oa_enabled']=False
        self.enqueue(setup=c);self.service.run_once()
        result=self.service.get(self.actor,'draft-operation-1')
        self.assertEqual(result['state'],'completed');self.assertEqual(result['questions'],[])
        self.assertEqual(self.wallet()['balance'],90);self.assertEqual(self.llm.calls,0)

    def test_duplicate_concurrent_enqueue_reserves_once(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.enqueue(),range(2)))
        self.assertEqual(results[0]['id'],results[1]['id']);self.assertEqual(self.wallet()['balance'],90)
        self.assertEqual(self.db.job_draft_generations.count_documents({}),1)

    def test_key_conflict_and_second_pending_request_are_rejected(self):
        self.enqueue()
        with self.assertRaises(WorkflowError):self.service.enqueue(self.actor,'Different job',self.setup,'draft-operation-1',10)
        with self.assertRaises(WorkflowError):self.enqueue('draft-operation-2')
        self.assertEqual(self.wallet()['balance'],90)

    def test_invalid_question_refunds_entire_operation_without_partial_bank_writes(self):
        self.enqueue();self.llm.invoke=lambda *a,**kw:dict(content='{"questions":[]}')
        self.service.run_once();result=self.service.get(self.actor,'draft-operation-1')
        self.assertEqual(result['state'],'failed');self.assertTrue(result['credits_released'])
        self.assertEqual(self.wallet()['balance'],100);self.assertEqual(self.db.question_versions.count_documents({}),0)
        self.assertFalse(self.service.run_once())

    def test_expired_unknown_call_refunds_without_provider_replay(self):
        self.enqueue()
        self.db.job_draft_generations.update_one({}, {'$set':dict(state='generating',lease_until=datetime.now(timezone.utc)-timedelta(seconds=1))})
        self.service.run_once()
        self.assertEqual(self.service.get(self.actor,'draft-operation-1')['error_code'],'external_outcome_unknown')
        self.assertEqual(self.jd_calls,0);self.assertEqual(self.wallet()['balance'],100)

    def test_unauthorized_read_and_unverified_write_rejected(self):
        self.enqueue()
        other=dict(_id=ObjectId(),user_type='recruiter',is_verified=True)
        with self.assertRaises(WorkflowError):self.service.get(other,'draft-operation-1')
        with self.assertRaises(WorkflowError):self.service.enqueue(dict(self.actor,is_verified=False),'Hire',self.setup,'draft-other-key',10)

    def test_invalid_count_and_stale_price_do_not_charge(self):
        c=deepcopy(self.setup);c['oa']['sections'][0]['count']=101
        for config,cost in [(c,10),(self.setup,9)]:
            with self.assertRaises(WorkflowError):self.service.enqueue(self.actor,'Hire data engineer',config,'draft-operation-1',cost)
        self.assertEqual(self.wallet()['balance'],100)

    def test_revoked_actor_during_generation_refunds_without_storing_content(self):
        self.enqueue()
        def jd(*args):
            self.db.users.update_one({'_id':self.actor['_id']},{'$set':{'is_verified':False}})
            return dict(job_data=self.data),200
        self.service.jd_generator=jd;self.service.run_once()
        self.assertEqual(self.wallet()['balance'],100);self.assertEqual(self.db.question_versions.count_documents({}),0)

    def test_internal_jd_call_cannot_double_charge_the_combined_operation(self):
        from controllers.job_controller import JobController
        from unittest.mock import Mock
        controller=JobController.__new__(JobController)
        controller.jobs_collection=self.db.jobs
        controller.wallet_service=Mock()
        controller.wallet_service.debit_wallet.side_effect=AssertionError('Combined operation must not charge twice')
        controller.wallet_service.get_wallet_summary.return_value={}
        with patch('services.llm_fallback_service.LLMFallbackService') as factory, patch('controllers.job_controller.record_usage_event'):
            factory.return_value.invoke.return_value=dict(content=json.dumps(self.data),model_used='test-only',usage={})
            result,status=controller.generate_jd_with_ai('Hire data engineer',str(self.actor['_id']),charge_credits=False)
        self.assertEqual(status,200,result);self.assertEqual(result['credits_deducted'],0)
        controller.wallet_service.debit_wallet.assert_not_called()

    def test_http_queue_active_lookup_scope_and_validation(self):
        from flask import Flask
        from routes.job_setup_routes import create_job_setup_routes
        actor=[self.actor]
        def auth(fn):
            def wrapped(*args,**kwargs):return fn(actor[0],*args,**kwargs)
            wrapped.__name__=fn.__name__;return wrapped
        with patch('routes.job_setup_routes.token_required',auth):
            app=Flask(__name__);app.register_blueprint(create_job_setup_routes(self.db))
        client=app.test_client()
        payload=dict(prompt='Hire a data engineer',configuration=self.setup,operation_key='http-draft-operation',accepted_credits=10)
        result=client.post('/api/job-draft-generations',json=payload)
        self.assertEqual(result.status_code,200,result.json)
        self.assertNotIn('questions',result.json['generation'])
        self.assertEqual(client.get('/api/job-draft-generations/active').json['generation']['id'],result.json['generation']['id'])
        self.assertEqual(client.get('/api/job-draft-generations/http-draft-operation').status_code,200)
        self.assertEqual(client.post('/api/job-draft-generations',json=dict(payload,unexpected=True)).status_code,400)
        self.assertEqual(client.post('/api/job-draft-generations',json=dict(payload,accepted_credits=9)).status_code,409)
        actor[0]=dict(_id=ObjectId(),user_type='recruiter',is_verified=True)
        self.assertEqual(client.get('/api/job-draft-generations/http-draft-operation').status_code,404)
        actor[0]=dict(_id=ObjectId(),user_type='candidate')
        self.assertEqual(client.post('/api/job-draft-generations',json=payload).status_code,403)

    def test_cancel_releases_once_and_prevents_late_uncertain_enqueue(self):
        self.enqueue()
        self.assertEqual(self.service.cancel(self.actor,'draft-operation-1')['state'],'failed')
        self.service.cancel(self.actor,'draft-operation-1')
        self.assertEqual(self.wallet()['balance'],100);self.assertFalse(self.service.run_once())
        self.service.cancel(self.actor,'draft-not-yet-received')
        with self.assertRaises(WorkflowError):self.enqueue('draft-not-yet-received')
        self.assertEqual(self.wallet()['balance'],100)

    def test_cancel_during_provider_call_never_stores_partial_questions(self):
        self.enqueue()
        original=self.llm.invoke
        def invoke(*args,**kwargs):
            result=original(*args,**kwargs)
            self.service.cancel(self.actor,'draft-operation-1')
            return result
        self.llm.invoke=invoke;self.service.run_once()
        self.assertEqual(self.wallet()['balance'],100);self.assertEqual(self.llm.calls,1)
        self.assertEqual(self.db.question_versions.count_documents({}),0)

    def test_invalid_question_contract_gets_one_repair_in_same_charge(self):
        original=self.llm.invoke;calls=[0]
        def invoke(prompt,**kwargs):
            calls[0]+=1
            if calls[0]==1:return dict(content='{"questions":[]}')
            return original(prompt,**kwargs)
        self.llm.invoke=invoke;self.enqueue();self.service.run_once()
        result=self.service.get(self.actor,'draft-operation-1')
        self.assertEqual(result['state'],'completed');self.assertEqual(calls[0],7)
        self.assertEqual(self.wallet()['balance'],90)
    def test_provider_failure_reports_safe_reason_and_phase_and_refunds(self):
        from services.llm_fallback_service import LLMAllProvidersExhaustedError
        self.llm.invoke=lambda *a,**k:(_ for _ in ()).throw(LLMAllProvidersExhaustedError('private provider response'))
        self.enqueue();self.service.run_once();result=self.service.get(self.actor,'draft-operation-1')
        self.assertEqual(result['error_code'],'providers_unavailable');self.assertEqual(result['failure_stage'],'mcq')
        self.assertEqual(self.wallet()['balance'],100);self.assertNotIn('private provider response',str(result))
    def test_unrequested_ai_metadata_does_not_fail_valid_job_fields(self):
        self.data['unrequested_ai_metadata']='omit this field'
        self.enqueue();self.service.run_once();result=self.service.get(self.actor,'draft-operation-1')
        self.assertEqual(result['state'],'completed');self.assertNotIn('unrequested_ai_metadata',result['job_data'])

    def test_twenty_mcqs_are_generated_in_small_batches_with_matching_slots(self):
        setup=deepcopy(self.setup)
        setup['oa']['sections']=[dict(type='mcq',count=20,difficulty=dict(easy=5,medium=10,hard=5),marks=list(range(1,21)),weight=100,duration_minutes=30)]
        calls=[]
        def invoke(prompt,**kwargs):
            context=json.loads(prompt.split('Avoid repeated questions.\n')[1].split('\nThe previous output')[0]);calls.append((context,kwargs,prompt))
            questions=[]
            for index,spec in enumerate(context['requests']):
                q=mcq();q.update(title=f'Unique question {len(calls)}-{index}',difficulty=spec['difficulty'],marks=spec['marks'])
                questions.append(q)
            return dict(content=json.dumps(dict(questions=questions)))
        self.llm.invoke=invoke;self.enqueue(setup=setup);self.service.run_once()
        result=self.service.get(self.actor,'draft-operation-1')
        self.assertEqual(result['state'],'completed');self.assertEqual(len(result['questions']),20)
        self.assertEqual(len(calls),7);self.assertEqual([len(c[0]['requests']) for c in calls],[3,3,3,3,3,3,2])
        self.assertTrue(all('reference_solutions' not in c[2] for c in calls))
        self.assertEqual([q['content']['marks'] for q in result['questions']],list(range(1,21)))
        self.assertEqual(self.wallet()['balance'],90)

    def test_rate_limit_checkpoint_resumes_questions_without_repeating_jd_or_charging_again(self):
        from services.llm_fallback_service import LLMRateLimitDeferred
        original=self.llm.invoke;calls=[0]
        def invoke(prompt,**kwargs):
            calls[0]+=1
            if calls[0]==2:raise LLMRateLimitDeferred(12)
            return original(prompt,**kwargs)
        self.llm.invoke=invoke;self.enqueue();self.service.run_once()
        result=self.service.get(self.actor,'draft-operation-1')
        self.assertEqual(result['state'],'queued');self.assertEqual(result['completed_questions'],1)
        self.assertEqual(result['phase'],'waiting_provider');self.assertNotIn('checkpoint',result)
        self.assertEqual(self.wallet()['reserved_credits'],10);self.assertEqual(self.wallet()['balance'],90)
        self.assertFalse(self.service.run_once())
        self.db.job_draft_generations.update_one({}, {'$set':{'lease_until':datetime.now(timezone.utc)-timedelta(seconds=1)}})
        # Simulate a different worker process; no in-memory state is required.
        worker=JobDraftGenerationService(self.db,self.llm,self.service.jd_generator)
        worker.run_once();result=worker.get(self.actor,'draft-operation-1')
        self.assertEqual(result['state'],'completed');self.assertEqual(len(result['questions']),3)
        self.assertEqual(self.jd_calls,1);self.assertEqual(calls[0],7)
        self.assertEqual(self.wallet()['balance'],90);self.assertEqual(self.wallet()['reserved_credits'],0)
        self.assertNotIn('checkpoint',self.db.job_draft_generations.find_one({}))

    def test_cancellation_while_waiting_refunds_and_prevents_resume(self):
        from services.llm_fallback_service import LLMRateLimitDeferred
        self.llm.invoke=lambda *a,**k:(_ for _ in ()).throw(LLMRateLimitDeferred(20))
        self.enqueue();self.service.run_once();self.service.cancel(self.actor,'draft-operation-1')
        self.db.job_draft_generations.update_one({}, {'$set':{'lease_until':datetime.now(timezone.utc)-timedelta(seconds=1)}})
        self.assertFalse(self.service.run_once());self.assertEqual(self.wallet()['balance'],100)
        self.assertEqual(self.db.question_versions.count_documents({}),0)

    def test_jd_phase_temporary_refusal_also_defers_with_same_reservation(self):
        from services.llm_fallback_service import LLMRateLimitDeferred
        original=self.service.jd_generator;calls=[0]
        def jd(*args):
            calls[0]+=1
            if calls[0]==1:raise LLMRateLimitDeferred(10)
            return original(*args)
        self.service.jd_generator=jd;self.enqueue();self.service.run_once()
        result=self.service.get(self.actor,'draft-operation-1')
        self.assertEqual((result['state'],result['completed_questions']),('queued',0))
        self.assertEqual(self.wallet()['reserved_credits'],10)
        self.db.job_draft_generations.update_one({}, {'$set':{'lease_until':datetime.now(timezone.utc)-timedelta(seconds=1)}})
        self.service.run_once();self.assertEqual(self.service.get(self.actor,'draft-operation-1')['state'],'completed')
        self.assertEqual(self.wallet()['balance'],90)

    def test_partial_coding_language_progress_survives_rate_limit_and_worker_restart(self):
        from services.llm_fallback_service import LLMRateLimitDeferred
        original=self.llm.invoke;stages=[];refused=[False]
        def invoke(prompt,**kwargs):
            context=json.loads(prompt.split('Avoid repeated questions.\n')[1].split('\nThe previous output')[0])
            task=context.get('task','question');stages.append((task,context.get('language')))
            if task=='translate_coding_sources' and context['language']=='java' and not refused[0]:
                refused[0]=True;raise LLMRateLimitDeferred(5)
            return original(prompt,**kwargs)
        self.llm.invoke=invoke;self.enqueue();self.service.run_once()
        record=self.db.job_draft_generations.find_one({})
        self.assertEqual(record['state'],'queued');self.assertEqual(record['completed_questions'],1)
        private=record['checkpoint']['coding_progress']['question']['coding']
        self.assertEqual(set(private['reference_solutions']),{'python','javascript'})
        self.assertNotIn('checkpoint',self.service.get(self.actor,'draft-operation-1'))
        self.db.job_draft_generations.update_one({}, {'$set':{'lease_until':datetime.now(timezone.utc)-timedelta(seconds=1)}})
        worker=JobDraftGenerationService(self.db,self.llm,self.service.jd_generator);worker.run_once()
        result=worker.get(self.actor,'draft-operation-1');self.assertEqual(result['state'],'completed')
        self.assertEqual(stages.count(('translate_coding_sources','javascript')),1)
        self.assertEqual(stages.count(('translate_coding_sources','java')),2)
        self.assertEqual(self.jd_calls,1);self.assertEqual(self.wallet()['balance'],90)
        coding_question=next(q['content'] for q in result['questions'] if q['type']=='coding')
        self.assertEqual(set(coding_question['coding']['reference_solutions']),set(self.setup['oa']['languages']))
        self.assertEqual(len(coding_question['coding']['tests']),16)

    def test_truncated_coding_core_gets_one_bounded_retry_without_losing_prior_questions(self):
        from services.llm_fallback_service import LLMAllProvidersExhaustedError,LLMInvalidOutputError
        original=self.llm.invoke;truncated=[False]
        def invoke(prompt,**kwargs):
            context=json.loads(prompt.split('Avoid repeated questions.\n')[1].split('\nThe previous output')[0])
            if context.get('requests',[{}])[0].get('type')=='coding' and not truncated[0]:
                truncated[0]=True
                raise LLMAllProvidersExhaustedError('safe output failure',errors=[('groq',LLMInvalidOutputError('Exceeded output budget'))])
            return original(prompt.split('\nThe previous output')[0],**kwargs)
        self.llm.invoke=invoke;self.enqueue();self.service.run_once()
        self.assertEqual(self.service.get(self.actor,'draft-operation-1')['state'],'completed')
        self.assertEqual(self.wallet()['balance'],90);self.assertEqual(self.wallet()['reserved_credits'],0)

    def test_resume_older_five_question_checkpoint_with_new_small_batches(self):
        setup=deepcopy(self.setup)
        setup['oa']['sections']=[dict(type='mcq',count=8,difficulty=dict(easy=8,medium=0,hard=0),marks=[1]*8,weight=100,duration_minutes=30)]
        self.enqueue(setup=setup)
        accepted=[]
        for index in range(5):
            question=mcq();question['title']=f'Previously accepted {index}';accepted.append(question)
        self.db.job_draft_generations.update_one({}, {'$set':dict(completed_questions=5,checkpoint=dict(job_data=self.data,questions=accepted))})
        def invoke(prompt,**kwargs):
            context=json.loads(prompt.split('Avoid repeated questions.\n')[1]);questions=[]
            self.assertEqual(len(context['requests']),3)
            for index,spec in enumerate(context['requests']):
                q=mcq();q.update(title=f'Remaining {index}',difficulty=spec['difficulty'],marks=spec['marks']);questions.append(q)
            return dict(content=json.dumps(dict(questions=questions)))
        self.llm.invoke=invoke;self.service.run_once()
        result=self.service.get(self.actor,'draft-operation-1')
        self.assertEqual(result['state'],'completed');self.assertEqual(len(result['questions']),8)
        self.assertEqual(self.jd_calls,0);self.assertEqual(self.wallet()['balance'],90)
