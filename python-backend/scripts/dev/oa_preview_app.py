"""Standalone developer OA harness. Never registered by the production app.

Uses real runtime/save/finalize/public-run/evaluation services on a disposable
loopback replica set. Local validation mode is not production acceptance.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import secrets
import threading
from urllib.parse import urlsplit
from bson import ObjectId
from flask import Flask, jsonify, request


def assert_preview_database(db):
    if not db.name.startswith('genhire_oa_preview_') or db.client.address[0] not in ('127.0.0.1','localhost','::1'):
        raise RuntimeError('Developer preview requires its own loopback database.')


def fixture_questions(engine='sqlite', contract='stdin_stdout'):
    from services.assessment_executor_preflight import canaries
    from services.role_assessment_templates import sql_question
    from models.assessment_content import validate_question
    if engine not in ('sqlite','duckdb') or contract not in ('stdin_stdout','function'):
        from models.hiring_workflow import WorkflowError
        raise WorkflowError('invalid_preview','Choose SQLite/DuckDB and a supported coding contract.',400)
    base=canaries('developer')[1 if contract=='function' else 0][1]
    questions=[]
    for index in range(3):
        q=deepcopy(base);q['title']=f'Developer coding {index+1}: echo an integer'
        q['coding']['limits']['time_ms']=2000
        questions.append(validate_question(q))
    for index in range(2):
        q=sql_question(index,'easy',1,engine)
        q['sql']['datasets']=q['sql']['datasets'][:2]
        questions.append(validate_question(q))
    for index in range(20):
        questions.append(validate_question(dict(schema_version=1,type='mcq',title=f'Developer MCQ {index+1}',
            statement='Which number is even?',difficulty='easy',topics=['Developer preview'],marks=1,
            explanation='Two is even.',mcq=dict(selection='single',options=[dict(id='even',text='2'),dict(id='odd',text='3')],correct_option_ids=['even']))))
    return questions


class Preview:
    def __init__(self,db,validator=None):
        assert_preview_database(db)
        from services.assessment_runtime_service import AssessmentRuntimeService,ensure_runtime_indexes
        from services.assessment_evaluation_service import AssessmentEvaluationService,ensure_evaluation_indexes
        from services.assessment_public_run_service import AssessmentPublicRunService
        from services.managed_assessment_validator import ManagedAssessmentValidator
        self.db=db;self.lock=threading.RLock();self.stop=threading.Event();self.worker_error=None
        self.actor=dict(_id=ObjectId(),user_type='candidate',is_active=True)
        self.runtime=AssessmentRuntimeService(db,lambda:datetime.now(timezone.utc))
        ensure_runtime_indexes(db);ensure_evaluation_indexes(db)
        # Validation-mode availability is confined to this process/database.
        # No fake isolation attestation or production feature bypass is written.
        self.validator=validator or ManagedAssessmentValidator(db,validation_mode=True)
        self.public=AssessmentPublicRunService(self.runtime);self.public.executor=self.validator
        self.evaluation=AssessmentEvaluationService(self.runtime);self.evaluation.execution.executor=self.validator
        self.reset()

    def reset(self,engine='sqlite',contract='stdin_stdout',scenario='correct'):
        from models.assessment_content import candidate_question
        from models.hiring_workflow import WorkflowError
        from services.workflow_service import request_identity
        if scenario not in ('correct','wrong','compile_error','timeout'):raise WorkflowError('invalid_preview','Unknown test scenario.',400)
        with self.lock:
            if self.db.assessment_execution_tasks.find_one({'state':{'$in':['queued','running','dispatching','dispatch_unknown']}}):
                raise WorkflowError('preview_busy','Finish or reconcile the pending run before resetting. Restart the harness to discard an ambiguous local session.',409)
            if self.db.assessment_submissions.find_one({'state':{'$in':['awaiting_evaluator','evaluating']}}):
                raise WorkflowError('preview_busy','Wait for the submitted test to finish before resetting.',409)
            questions=fixture_questions(engine,contract);now=self.runtime.clock()
            version_id,purchase_id,attempt_id,invitation_id=[ObjectId() for _ in range(4)]
            self.attempt_id,self.invitation_id=str(attempt_id),str(invitation_id)
            ids=[];bindings=[];public=[];answers={}
            owner=str(self.actor['_id'])
            for index,q in enumerate(questions):
                identifier=ObjectId();qid=str(identifier);digest=request_identity(q)
                self.db.question_versions.insert_one(dict(_id=identifier,owner_id=owner,pool='practice',content=q,content_hash=digest))
                ids.append(qid);bindings.append(dict(question_version_id=qid,content_hash=digest));public.append(dict(id=qid,**candidate_question(q)))
                if q['type']=='mcq':answers[qid]=dict(option_ids=['odd' if scenario=='wrong' else 'even'])
                elif q['type']=='sql':answers[qid]=dict(language='sql',source='SELECT 0 AS incorrect_column' if scenario=='wrong' else q['sql']['reference_query'])
                else:
                    language='python';source=q['coding']['reference_solutions'][language]
                    if scenario=='wrong':source='def solve(value):\n    return 0' if contract=='function' else 'print(0)'
                    if index==0 and scenario=='compile_error':language='cpp';source='int main( {'
                    if index==0 and scenario=='timeout':source='def solve(value):\n    while True: pass' if contract=='function' else 'while True: pass'
                    answers[qid]=dict(language=language,source=source)
            configuration=dict(timer_mode='shared',duration_minutes=1440,languages=questions[0]['coding']['languages'],coding_contract=contract,sql_engine=engine,mcq_mode='single',
                sections=[dict(type=kind,count=count,difficulty=dict(easy=count,medium=0,hard=0),marks=[1]*count,weight=weight,duration_minutes=1440)
                    for kind,count,weight in [('coding',3,60),('sql',2,30),('mcq',20,10)]])
            self.db.assessment_versions.insert_one(dict(_id=version_id,pool='practice',owner_id=owner,state='published',configuration=configuration,question_version_ids=ids))
            self.db.practice_assessment_purchases.insert_one(dict(_id=purchase_id,candidate_id=owner,state='started',price=dict(total_credits=0)))
            self.db.assessment_attempts.insert_one(dict(_id=attempt_id,pool='practice',owner_id=owner,candidate_id=owner,purchase_id=str(purchase_id),
                invitation_id=str(invitation_id),assessment_version_id=str(version_id),runtime_version=1,state='in_progress',revision=0,
                started_at=now,deadline=now+timedelta(days=1),configuration=configuration,questions=public,question_bindings=bindings,answers={},
                sections=[dict(index=i,type=s['type'],opens_at=now,closes_at=now+timedelta(days=1),question_ids=[v['id'] for v in public if v['type']==s['type']]) for i,s in enumerate(configuration['sections'])]))
            # Prefill through the actual answer-validation/revision service.
            self.runtime.save(self.actor,self.attempt_id,0,'preview-prefill-'+str(attempt_id),answers)
            self.options=dict(engine=engine,contract=contract,scenario=scenario)
            return dict(invitation_id=self.invitation_id,attempt_id=self.attempt_id,**self.options)

    def submit(self):
        with self.lock:
            snapshot=self.runtime.view(self.actor,self.attempt_id)
            return self.runtime.finalize(self.attempt_id,'candidate',self.actor,snapshot['revision'])

    def status(self):
        with self.lock:
            job=self.db.assessment_evaluation_jobs.find_one({'attempt_id':self.attempt_id}) or {}
            report=self.db.assessment_evaluation_reports.find_one({'attempt_id':self.attempt_id})
            tasks=list(self.db.assessment_execution_tasks.aggregate([{'$match':{'attempt_id':self.attempt_id}},{'$group':{'_id':'$state','count':{'$sum':1}}}]))
            journals=list(self.db.oa_provider_requests.aggregate([{'$group':{'_id':'$state','runs':{'$sum':'$actual_runs'},'requests':{'$sum':'$request_count'}}}]))
            cases=[dict(question=task['question']['title'],case_id=task['case_id'],purpose=task['purpose'],state=task['state'],
                **{key:task.get('result',{})[key] for key in ('status','passed') if key in task.get('result',{})})
                for task in self.db.assessment_execution_tasks.find({'attempt_id':self.attempt_id}).sort('created_at',1)]
            value=dict(invitation_id=self.invitation_id,attempt_id=self.attempt_id,**self.options,
                state=job.get('state','editable'),error_code=job.get('error_code') if job.get('state') not in ('complete',None) else self.worker_error,
                tasks=tasks,case_results=cases,provider_usage=journals,local_database=True,production_acceptance=False,grading_runs_per_submission=7)
            if report:value['report']={k:report[k] for k in ('state','score','sections','questions')}
            return value

    def work_once(self):
        with self.lock:
            self.public.tick();self.evaluation.tick()
            # Public.tick already advances the same execution queue once.

    def work(self):
        while not self.stop.is_set():
            try:self.work_once();self.worker_error=None
            except Exception as exc:self.worker_error=getattr(exc,'code','preview_worker_error')
            self.stop.wait(.25)


def create_app(preview,token,frontend_port=3000):
    from models.hiring_workflow import WorkflowError
    app=Flask('genhire_local_oa_preview');app.config['MAX_CONTENT_LENGTH']=1024*1024
    origins={f'http://{host}:{frontend_port}' for host in ('localhost','127.0.0.1')}

    @app.before_request
    def guard():
        host=urlsplit('http://'+request.host).hostname
        if host not in ('127.0.0.1','localhost') or request.remote_addr not in ('127.0.0.1','::1'):
            return jsonify(error='Loopback developer preview only.'),403
        if request.headers.get('Origin') and request.headers['Origin'] not in origins:
            return jsonify(error='Unapproved preview origin.'),403
        if request.method=='OPTIONS':return '',204
        if not secrets.compare_digest(request.headers.get('X-GenHire-Dev-Token',''),token):
            return jsonify(error='Open the developer URL printed by the local preview launcher.'),401

    @app.after_request
    def cors(response):
        if request.headers.get('Origin') in origins:response.headers['Access-Control-Allow-Origin']=request.headers['Origin']
        response.headers['Vary']='Origin';response.headers['Cache-Control']='no-store'
        response.headers['Access-Control-Allow-Headers']='Content-Type, X-GenHire-Dev-Token'
        response.headers['Access-Control-Allow-Methods']='GET, POST, OPTIONS'
        return response

    @app.errorhandler(WorkflowError)
    def workflow_error(exc):return jsonify(error=str(exc),error_code=exc.code),exc.status

    @app.errorhandler(Exception)
    def failure(exc):
        from werkzeug.exceptions import HTTPException
        if isinstance(exc,HTTPException):return jsonify(error=exc.name),exc.code
        return jsonify(error='Local preview request failed; no final score was invented.',error_code='preview_request_failed'),500

    def safe(value):
        if isinstance(value,datetime):return value.isoformat()
        if isinstance(value,ObjectId):return str(value)
        if isinstance(value,dict):return {k:safe(v) for k,v in value.items()}
        if isinstance(value,list):return [safe(v) for v in value]
        return value

    @app.route('/dev/status')
    def status():return jsonify(safe(preview.status()))

    @app.post('/dev/reset')
    def reset():
        body=request.get_json() or {}
        result=preview.reset(body.get('engine','sqlite'),body.get('contract','stdin_stdout'),body.get('scenario','correct'))
        if body.get('submit') is True:preview.submit()
        return jsonify(result)

    @app.route('/api/<path:path>',methods=['GET','POST'])
    def api(path):
        with preview.lock:
            parts=path.split('/');body=request.get_json(silent=True) or {}
            if parts==['assessment-invitations',preview.invitation_id] and request.method=='GET':
                return jsonify(dict(state='accepted',security_required=False,pool='practice',attempt_id=preview.attempt_id))
            if len(parts)<2 or parts[:2]!=['assessment-attempts',preview.attempt_id]:
                return jsonify(error='Only the current disposable developer attempt is accessible.'),404
            identifier=preview.attempt_id
            if len(parts)==2 and request.method=='GET':return jsonify(safe(preview.runtime.view(preview.actor,identifier)))
            if parts[2:]==['answers'] and request.method=='POST':return jsonify(preview.runtime.save(preview.actor,identifier,body.get('expected_revision'),body.get('operation_key'),body.get('answers')))
            if parts[2:]==['submit'] and request.method=='POST':return jsonify(preview.runtime.finalize(identifier,'candidate',preview.actor,body.get('expected_revision')))
            if parts[2:]==['runs'] and request.method=='POST':return jsonify(preview.public.create(preview.actor,identifier,body.get('operation_key'),body.get('question_id'),body.get('answer'),body.get('custom_input')))
            if len(parts)==4 and parts[2]=='runs' and request.method=='GET':return jsonify(preview.public.result(preview.actor,identifier,parts[3]))
            if parts[2:]==['evaluation'] and request.method=='GET':return jsonify(safe(preview.evaluation.report(preview.actor,identifier)))
            return jsonify(error='Unsupported developer preview operation.'),404
    return app
