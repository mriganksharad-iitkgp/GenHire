"""OnlineCompiler.io REST transport, native judging and durable dispatch intent."""
from datetime import datetime, timezone
import json
import math
import os
import re
import time
from urllib.parse import urlsplit
import requests
from pymongo.errors import DuplicateKeyError
from core.mongo_transactions import atomic
from config.assessment_execution import integer_setting, SQL_RUNTIMES, sql_enabled
from models.hiring_workflow import WorkflowError


def failure(code='executor_invalid_response',status=503):
    raise WorkflowError(code,'Execution is unavailable or requires review; your saved work is retained.',status) from None


def metric(value):
    if isinstance(value,bool):return None
    try:value=float(value)
    except (ValueError,TypeError):return None
    return value if math.isfinite(value) and value>=0 else None


def diagnostics(value):
    text=str(value or '').replace(os.getenv('ONLINECOMPILER_API_KEY','').strip() or '\0','[redacted]')
    return re.sub(r'[^\x09\x0a\x20-\x7e]','',re.sub(r'https?://\S+','[url]',text))[:4000]


class OnlineCompilerExecutionProvider:
    def __init__(self,db=None,session=None):self.db,self.session=db,session or requests.Session()

    def settings(self):
        base=os.getenv('ONLINECOMPILER_API_BASE_URL','https://api.onlinecompiler.io').rstrip('/')
        try:
            parsed=urlsplit(base)
            valid=parsed.scheme=='https' and parsed.hostname=='api.onlinecompiler.io' and parsed.port in (None,443) and not any((parsed.username,parsed.password,parsed.query,parsed.fragment,parsed.path))
        except ValueError:valid=False
        key=os.getenv('ONLINECOMPILER_API_KEY','').strip()
        if not valid or not key:failure('execution_not_configured')
        return base,key,integer_setting('OA_EXECUTION_TIMEOUT_MS',30000,1000,120000)/1000

    def request(self,path,payload=None,public=False):
        if public:
            base,key,timeout='https://api.onlinecompiler.io','',15
        else:base,key,timeout=self.settings()
        response=None;deadline=time.monotonic()+timeout
        try:
            response=self.session.request('GET' if payload is None else 'POST',base+path,
                headers={} if public else {'Authorization':key},json=payload,
                timeout=(5,timeout),stream=True,allow_redirects=False)
            if response.status_code==429:
                body=bytearray()
                for part in response.iter_content(4096):
                    body.extend(part)
                    if len(body)>=8192:break
                failure('provider_quota_exhausted' if b'month' in bytes(body).lower() else 'provider_rate_limit',429)
            if response.status_code in (401,403):failure('provider_authentication_failed')
            if response.status_code>=500:failure('provider_dispatch_unknown')
            if response.status_code!=200:failure('provider_request_rejected')
            content=bytearray()
            for part in response.iter_content(65536):
                if time.monotonic()>deadline:failure('provider_dispatch_unknown')
                content.extend(part)
                if len(content)>2*1024*1024:failure('executor_response_limit')
            return json.loads(content)
        except WorkflowError:raise
        except Exception:failure('provider_dispatch_unknown')
        finally:
            if response is not None:response.close()

    def compilers(self):return self.request('/api/compilers/',public=True)
    def usage(self):
        raw=self.request('/api/usage/')
        if not isinstance(raw,dict):failure()
        safe={key:raw[key] for key in ('month','submissions','monthly_limit','remaining','resets_at','submissions_per_minute','pending_submissions','running_submissions') if key in raw}
        if self.db is not None:self.db.oa_provider_usage_snapshots.insert_one(dict(checked_at=datetime.now(timezone.utc),**safe))
        return safe

    @staticmethod
    def validate_text(value,limit=100000):
        if not isinstance(value,str) or '\0' in value or len(value.encode('utf-8'))>limit:
            raise WorkflowError('invalid_execution_input','Source or stdin exceeds the provider input contract.',400)

    def run_code(self,compiler,code,input_text='',time_limit=2):
        self.validate_text(code);self.validate_text(input_text)
        if not 0<float(time_limit)<=30:raise WorkflowError('invalid_execution_input','Invalid execution time limit.',400)
        return self.request('/api/run-code-sync/',dict(compiler=compiler,code=code,input=input_text,time_limit=time_limit))

    def evaluate_code(self,compiler,code,cases,time_limit=2,checker='trim'):
        self.validate_text(code)
        limit=integer_setting('ONLINECOMPILER_TEST_BATCH_SIZE',4,1,80)
        if not isinstance(cases,list) or not 1<=len(cases)<=limit or checker not in ('trim','exact'):
            raise WorkflowError('invalid_execution_input','Invalid judging batch or checker.',400)
        for case in cases:
            self.validate_text(case.get('input',''));self.validate_text(case.get('expected_output'),65536)
            if type(case.get('hidden')) is not bool or type(case.get('weight',1)) not in (int,float) or not math.isfinite(case.get('weight',1)) or case.get('weight',1)<=0:
                raise WorkflowError('invalid_execution_input','Invalid test visibility or weight.',400)
        return self.request('/api/run-tests/',dict(compiler=compiler,code=code,tests=cases,time_limit=time_limit,
            checker=checker,scoring='weighted',stop_on_failure=False))

    def normalize(self,raw,compiler='',time_limit=2,output_limit=65536,memory_mb=512):
        if not isinstance(raw,dict) or raw.get('status') not in ('success','error') or type(raw.get('exit_code')) is not int:failure()
        output,error=raw.get('output',''),raw.get('error','')
        if not isinstance(output,str) or not isinstance(error,str):failure()
        code=raw['exit_code'];status='ok'
        if raw.get('truncated') is True or code==153 or len(output.encode())>output_limit:status='output_limit'
        elif code==124:status='time_limit'
        elif code==137:status='memory_limit'
        elif code!=0 or raw.get('signal') is not None:
            status='compile_error' if re.search(r'compil|error:|SyntaxError',error,re.I) else 'runtime_error'
        elif raw['status']!='success':failure('provider_execution_failed')
        result=dict(status=status)
        elapsed,memory=metric(raw.get('time')),metric(raw.get('memory'))
        if elapsed is not None:result['time_ms']=elapsed*1000
        if memory is not None:result['memory_kb']=memory
        allowance=1 if compiler=='openjdk-25' else 0
        if status=='ok' and elapsed is not None and elapsed>time_limit+allowance:result['status']='time_limit'
        if status=='ok' and memory is not None and memory>memory_mb*1024:result['status']='memory_limit'
        if result['status']=='ok':result['stdout']=output
        if error:result['diagnostics']=diagnostics(error)
        return result

    def normalize_judging(self,raw,cases):
        if not isinstance(raw,dict) or not isinstance(raw.get('tests'),list) or len(raw['tests'])!=len(cases):failure('invalid_judging_response')
        if raw.get('total')!=len(cases):failure('invalid_judging_response')
        statuses=dict(accepted='ok',wrong_answer='ok',compilation_error='compile_error',runtime_error='runtime_error',
            time_limit_exceeded='time_limit',memory_limit_exceeded='memory_limit',output_limit_exceeded='output_limit',
            internal_error='infrastructure_error',skipped='infrastructure_error')
        results=[]
        for item,case in zip(raw['tests'],cases):
            if not isinstance(item,dict) or item.get('verdict') not in statuses or item.get('hidden') is not case['hidden']:failure('invalid_judging_response')
            verdict=item['verdict']
            result=dict(status=statuses[verdict],passed=verdict=='accepted',native_judged=True)
            # Hidden native verdicts intentionally have no outputs or metrics.
            if not case['hidden']:
                for source,target in (('time','time_ms'),('memory','memory_kb')):
                    value=metric(item.get(source))
                    if value is not None:result[target]=value*1000 if source=='time' else value
                if item.get('error'):result['diagnostics']=diagnostics(item['error'])
            results.append(result)
        return results

    def _journal(self,identity,payload,runner,purpose,hidden_flags,language):
        from services.workflow_service import request_identity
        if self.db is None:failure('execution_journal_required')
        context=getattr(self,'context',{})
        self.settings();digest=request_identity(dict(payload=payload,context=context));now=datetime.now(timezone.utc);runs=len(hidden_flags)
        concurrency=integer_setting('OA_MAX_CONCURRENT_EXECUTIONS',2,1,100)
        rate=integer_setting('ONLINECOMPILER_RUNS_PER_MINUTE',30,1,100000)
        minute=now.strftime('%Y-%m-%dT%H:%M')
        def reserve(tx):
            old=self.db.oa_provider_requests.find_one({'_id':identity},session=tx)
            if old and old['request_hash']!=digest:raise WorkflowError('idempotency_conflict','Execution identity reused with different content.',409)
            if old and old['state']!='rejected':return False
            active=self.db.oa_provider_limits.find_one({'_id':'active'},session=tx) or {}
            usage=self.db.oa_provider_limits.find_one({'_id':minute},session=tx) or {}
            if active.get('count',0)>=concurrency:failure('provider_capacity',429)
            if usage.get('runs',0)+runs>rate:failure('provider_rate_limit',429)
            self.db.oa_provider_limits.update_one({'_id':'active'},{'$inc':{'count':1}},upsert=True,session=tx)
            self.db.oa_provider_limits.update_one({'_id':minute},{'$inc':{'runs':runs},'$set':{'expires_at':now}},upsert=True,session=tx)
            fields=dict(provider='onlinecompiler',request_hash=digest,state='dispatching',purpose=purpose,language=language,
                pool=context.get('pool','reference'),attempt_id=context.get('attempt_id'),owner_id=context.get('owner_id'),
                estimated_runs=runs,actual_runs=None,hidden_executions=sum(hidden_flags),public_executions=runs-sum(hidden_flags),created_at=now)
            if old:self.db.oa_provider_requests.update_one({'_id':identity},{'$set':fields,'$inc':{'request_count':1}},session=tx)
            else:self.db.oa_provider_requests.insert_one(dict(_id=identity,request_count=1,**fields),session=tx)
            return True
        try:fresh=atomic(self.db,reserve)
        except DuplicateKeyError:fresh=atomic(self.db,reserve)
        if not fresh:return self.result(identity)
        def settle(fields,release=True):
            def write(tx):
                changed=self.db.oa_provider_requests.update_one({'_id':identity,'state':'dispatching'},{'$set':fields},session=tx)
                if changed.matched_count and release:self.db.oa_provider_limits.update_one({'_id':'active','count':{'$gt':0}},{'$inc':{'count':-1}},session=tx)
            atomic(self.db,write)
        try:
            result,actual=runner()
            settle(dict(state='complete',result=result,actual_runs=actual,completed_at=datetime.now(timezone.utc)))
            return result
        except Exception as exc:
            code=exc.code if isinstance(exc,WorkflowError) else 'provider_dispatch_unknown'
            known=code in {'provider_rate_limit','provider_quota_exhausted','provider_authentication_failed','provider_request_rejected','invalid_execution_input'}
            settle(dict(state='rejected' if known else 'dispatch_unknown',error_code=code,actual_runs=0 if known else None),release=known)
            raise

    def execute(self,identity,compiler,code,input_text='',purpose='reference',hidden=False,time_ms=2000,memory_mb=512,output_limit=65536):
        self.validate_text(code);self.validate_text(input_text)
        payload=dict(operation='run',compiler=compiler,code=code,input=input_text,purpose=purpose,hidden=hidden,time_ms=time_ms,memory_mb=memory_mb,output_limit=output_limit)
        def run():return self.normalize(self.run_code(compiler,code,input_text,time_ms/1000),compiler,time_ms/1000,output_limit,memory_mb),1
        return self._journal(identity,payload,run,purpose,[hidden],compiler)

    def judge(self,identity,compiler,code,cases,time_ms=2000,checker='trim',purpose='grading'):
        self.validate_text(code)
        payload=dict(operation='judge',compiler=compiler,code=code,cases=cases,time_ms=time_ms,checker=checker,purpose=purpose)
        def run():
            raw=self.evaluate_code(compiler,code,cases,time_ms/1000,checker)
            result=self.normalize_judging(raw,cases)
            return result,sum(item.get('verdict')!='skipped' for item in raw['tests'])
        return self._journal(identity,payload,run,purpose,[case['hidden'] for case in cases],compiler)

    def result(self,identity):
        record=self.db.oa_provider_requests.find_one({'_id':identity})
        if not record or record['state']!='complete':failure('dispatch_reconciliation_required')
        return record['result']

    def run_sql(self,identity,question,case,purpose='reference'):
        from services.sql_result_codec import sql_source,sql_result
        sql=question['sql'];engine=sql['engine']
        if not sql_enabled(engine):failure('sql_engine_unavailable')
        try:source,marker=sql_source(engine,sql['schema_sql'],case['seed_sql'],sql['reference_query'],identity)
        except WorkflowError as exc:
            if exc.code!='invalid_sql_query':raise
            from services.workflow_service import request_identity
            digest=request_identity(dict(question=question,case=case['id'],purpose=purpose))
            result=dict(status='runtime_error',diagnostics='Use one read-only SELECT or WITH query.')
            def reject(tx):
                old=self.db.oa_provider_requests.find_one({'_id':identity},session=tx)
                if old:
                    if old['request_hash']!=digest:raise WorkflowError('idempotency_conflict','Execution identity reused.',409)
                    return old['result']
                self.db.oa_provider_requests.insert_one(dict(_id=identity,provider='onlinecompiler',request_hash=digest,
                    state='complete',result=result,purpose=purpose,language=SQL_RUNTIMES[engine],request_count=0,
                    estimated_runs=0,actual_runs=0,local_rejection=True,created_at=datetime.now(timezone.utc)),session=tx)
                return result
            try:return atomic(self.db,reject)
            except DuplicateKeyError:return atomic(self.db,reject)
        result=self.execute(identity,SQL_RUNTIMES[engine],source,purpose=purpose,hidden=case['visibility']=='hidden',time_ms=sql['time_ms'])
        return sql_result(result,marker)

    def evaluate_sql(self,identity,question,purpose='grading'):
        from services.assessment_scoring import comparison
        return [dict(case_id=case['id'],passed=comparison(question,case,result),status=result['status'])
            for case in question['sql']['datasets'] for result in [self.run_sql(identity+':'+case['id'],question,case,purpose)]]


def usage_summary(db):
    snapshot=db.oa_provider_usage_snapshots.find_one({}, {'_id':0},sort=[('checked_at',-1)])
    price=metric(os.getenv('ONLINECOMPILER_MONTHLY_PLAN_USD','0'))
    allowance=metric((snapshot or {}).get('monthly_limit'))
    unit_cost=price/allowance if price is not None and allowance else None
    attempts=list(db.oa_provider_requests.aggregate([{'$match':{'attempt_id':{'$ne':None}}},{'$group':{
        '_id':'$attempt_id','estimated_runs':{'$sum':'$estimated_runs'},'known_actual_runs':{'$sum':'$actual_runs'}}}]))
    for attempt in attempts:attempt['estimated_allowance_cost_usd']=attempt['estimated_runs']*unit_cost if unit_cost is not None else None
    return dict(requests=list(db.oa_provider_requests.aggregate([{'$group':{
        '_id':{'purpose':'$purpose','language':'$language','state':'$state','pool':'$pool'},
        'requests':{'$sum':'$request_count'},'estimated_runs':{'$sum':'$estimated_runs'},'known_actual_runs':{'$sum':'$actual_runs'},
        'unknown_outcomes':{'$sum':{'$cond':[{'$eq':[{'$ifNull':['$actual_runs',None]},None]},1,0]}},
        'hidden_tests':{'$sum':'$hidden_executions'},'public_runs':{'$sum':'$public_executions'}}}])),
        per_attempt=attempts,
        account_snapshot=snapshot,
        monthly_plan_usd=os.getenv('ONLINECOMPILER_MONTHLY_PLAN_USD','0'),
        note='Provider runs are separate from GenHire wallet credits. Allowance cost assumes full subscription use; actual subscription expense per OA depends on monthly candidate volume. Unknown outcomes are not zero runs.')
