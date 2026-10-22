"""Operator-only live OnlineCompiler.io acceptance; no fixture can enable production."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import os
import uuid
import time
from models.assessment_content import validate_question
from models.hiring_workflow import WorkflowError
from services.assessment_validation import verify_reference_results
from services.managed_assessment_validator import ManagedAssessmentValidator
from services.workflow_service import request_identity

from config.assessment_execution import RUNTIMES, SQL_RUNTIMES
TARGETS = dict(RUNTIMES)
REVIEW_CHECKS = ('code_network_denied', 'code_filesystem_isolated', 'code_hard_resource_limits',
    'sql_network_denied', 'sql_file_access_denied', 'sql_role_escape_denied',
    'sql_output_limit_verified', 'sql_crash_recovery_verified', 'provider_isolation_evidence_reviewed')

def security_review(value, policy):
    if (not policy or not isinstance(value,dict) or value.get('policy_id')!=policy
        or any(value.get(k) is not True for k in REVIEW_CHECKS)
        or any(not isinstance(value.get(k),str) or not 5<=len(value[k])<=200 for k in ('reviewed_by','evidence_reference'))):
        raise WorkflowError('isolation_review_required','A current operator review of OnlineCompiler.io isolation is required.',503)
    try: reviewed=datetime.fromisoformat(value['reviewed_at'].replace('Z','+00:00'))
    except (KeyError,TypeError,ValueError): raise WorkflowError('isolation_review_required','Review timestamp is required.',503) from None
    now=datetime.now(timezone.utc)
    if reviewed.tzinfo is None or not now-timedelta(days=7)<=reviewed<=now:
        raise WorkflowError('isolation_review_required','Review must be timezone-aware and within seven days.',503)
    return deepcopy(value)

def canaries(run_id):
    base=dict(schema_version=1,title='Live OnlineCompiler.io acceptance '+run_id,statement='Echo one integer.',difficulty='easy',topics=['Acceptance'],marks=1,explanation='Operator-only canary.')
    sources=dict(python='print(int(input()))',javascript="console.log(Number(require('fs').readFileSync(0,'utf8').trim()));",
        nodejs="console.log(Number(require('fs').readFileSync(0,'utf8').trim()));",
        java='class Main {\n    public static void main(String[] args) {\n        System.out.print(new java.util.Scanner(System.in).nextInt());\n    }\n}\n',
        cpp='#include <iostream>\n\nint main() {\n    int n;\n    std::cin >> n;\n    std::cout << n;\n    return 0;\n}\n',
        c='#include <stdio.h>\n\nint main() {\n    int n;\n    scanf("%d", &n);\n    printf("%d", n);\n    return 0;\n}\n')
    q=dict(base,type='coding',coding=dict(contract='stdin_stdout',signature=None,harness_version='genhire_fn_v1',input_format='Integer',output_format='Integer',constraints='Signed integer',
        languages=list(TARGETS),runtime_versions=dict(TARGETS),starter_code=dict(sources),reference_solutions=sources,
        limits=dict(time_ms=5000,memory_mb=512,output_kb=64),comparison='trim_trailing_whitespace',tests=[dict(id=name,visibility=visibility,input=str(n),expected=str(n),weight=1,explanation='') for name,visibility,n in [('sample','sample',2),('hidden','hidden',-9371)]]))
    result=[('stdin_stdout',validate_question(q),True,None)]
    refs=dict(python='def solve(value):\n    return value\n',javascript='function solve(value) {\n    return value;\n}\n',nodejs='function solve(value) {\n    return value;\n}\n',java='class Solution {\n    public int solve(int value) {\n        return value;\n    }\n}\n',cpp='class Solution {\npublic:\n    int solve(int value) {\n        return value;\n    }\n};\n')
    fn=deepcopy(q);fn['coding'].update(contract='function',signature=dict(name='solve',parameters=[dict(name='value',type='integer')],return_type='integer'),languages=list(refs),runtime_versions={l:TARGETS[l] for l in refs},starter_code=refs,reference_solutions=refs)
    for case in fn['coding']['tests']:case.update(input={'value':int(case['input'])},expected=int(case['expected']))
    result.append(('function',validate_question(fn),True,None))
    bad=deepcopy(q)
    for case in bad['coding']['tests']:case['expected']='99999'
    result.append(('wrong_answer',bad,False,'output_mismatch'))
    return result

VERSION_SOURCES=dict(python='import sys; print(sys.version)',nodejs='console.log(process.version)',
    java='class Main {public static void main(String[] a){System.out.print(Runtime.version());}}',
    cpp='#include <iostream>\nint main(){std::cout<<__VERSION__;}',c='#include <stdio.h>\nint main(){printf("%s",__VERSION__);}')

class ExecutorPreflight:
    def __init__(self,db):
        self.db=db;self.validator=ManagedAssessmentValidator(db,validation_mode=True)

    def run(self,review):
        review=security_review(review,os.getenv('GENHIRE_EXECUTOR_ISOLATION_POLICY_ID',''))
        if not self.validator.capabilities()['available']:
            raise WorkflowError('execution_not_configured','Configure OnlineCompiler.io and enable explicit live execution first.',503)
        provider=self.validator.provider
        def paced(method):
            def call(*args,**kwargs):
                deadline=time.monotonic()+125
                while True:
                    try:return method(*args,**kwargs)
                    except WorkflowError as exc:
                        if exc.code not in ('provider_rate_limit','provider_capacity') or time.monotonic()>=deadline:raise
                        self.validator.heartbeat()
                        time.sleep(2)
            return call
        provider.execute=paced(provider.execute)
        provider.judge=paced(provider.judge)
        profile=self.validator.profile_hash();run_id=uuid.uuid4().hex;now=datetime.now(timezone.utc)
        self.db.assessment_executor_preflights.insert_one(dict(_id=run_id,profile_hash=profile,state='running',created_at=now,security_review=review))
        self.db.assessment_executor_attestations.update_many({'profile_hash':profile},{'$set':{'state':'checking','sql_verified':False}})
        try:
            catalog=self.validator.provider.compilers()['compilers']
            if not set(RUNTIMES.values())|set(SQL_RUNTIMES.values()) <= {x['id'] for x in catalog}:
                raise WorkflowError('unsupported_provider_languages','Required languages are missing from the live provider catalog.',503)
            versions={}
            for language,source in VERSION_SOURCES.items():
                output=self.validator.provider.execute('preflight:'+run_id+':version:'+language,RUNTIMES[language],source,purpose='acceptance')
                if output['status']!='ok' or not output.get('stdout','').strip():raise WorkflowError('version_probe_failed','Runtime discovery failed.',503)
                versions[language]=output['stdout'].strip()[:500]
            for name,q,expected,reason in canaries(run_id):
                evidence=verify_reference_results(q,self.validator.validate(q,request_identity(q)))
                if evidence['passed']!=expected:raise WorkflowError('code_canary_failed','Code execution/scoring acceptance failed.',503)
            cases=[dict(input='2',expected_output='4',hidden=False,weight=1),dict(input='3',expected_output='999',hidden=False,weight=2),dict(input='4',expected_output='8',hidden=True,weight=3)]
            judged=provider.judge('preflight:'+run_id+':native','python-3.14','print(int(input())*2)',cases,purpose='acceptance')
            if [r['passed'] for r in judged]!=[True,False,True] or any(k in judged[2] for k in ('stdout','diagnostics','time_ms','memory_kb')):
                raise WorkflowError('native_judging_failed','Weighted native judging or hidden result acceptance failed.',503)
            sql_verified=False;sql_error=None
            try:
                # Reusing the exact table name with new seeds in separate requests
                # must succeed and return only each request's own controlled data.
                for engine in SQL_RUNTIMES:
                    for n in (73917,-62819):
                        identity='preflight:'+run_id+':'+engine+':'+str(n)
                        q=dict(type='sql',sql=dict(engine=engine,time_ms=10000,
                            schema_sql='CREATE TABLE isolation_values (value INTEGER, label VARCHAR(50), optional_value DECIMAL(10,2));',
                            reference_query='SELECT value, label, optional_value FROM isolation_values ORDER BY value'))
                        case=dict(id='probe',visibility='hidden',seed_sql=f"INSERT INTO isolation_values VALUES ({n+1}, 'Unicode \u96ea', 1.25), ({n}, 'NULL', NULL), ({n}, 'NULL', NULL);")
                        output=self.validator.provider.run_sql(identity,q,case,'acceptance')
                        if output.get('status')!='ok' or output.get('columns')!=['value','label','optional_value'] or output.get('rows')!=[[n,'NULL',None],[n,'NULL',None],[n+1,'Unicode \u96ea',1.25]]:
                            raise WorkflowError('sql_isolation_failed','Controlled SQL datasets or typed result handling failed.',503)
                    q['sql'].update(schema_sql='CREATE TABLE empty_values (value INTEGER);',reference_query='SELECT value FROM empty_values')
                    case.update(seed_sql='')
                    empty=self.validator.provider.run_sql('preflight:'+run_id+':'+engine+':empty',q,case,'acceptance')
                    if empty.get('status')!='ok' or empty.get('columns')!=['value'] or empty.get('rows')!=[]:
                        raise WorkflowError('sql_empty_result_failed','Empty result metadata could not be verified.',503)
                    versions[engine]=SQL_RUNTIMES[engine]
                sql_verified=True
            except Exception as exc:
                sql_error=exc.code if isinstance(exc,WorkflowError) else 'sql_acceptance_failed'
            self.db.assessment_executor_attestations.update_one({'profile_hash':profile},{'$set':dict(
                state='passed',provider='onlinecompiler',sql_verified=sql_verified,sql_error=sql_error,
                runtime_versions=versions,security_review=review,preflight_id=run_id,passed_at=now,expires_at=now+timedelta(hours=24))},upsert=True)
            self.db.assessment_executor_preflights.update_one({'_id':run_id},{'$set':dict(state='passed',sql_verified=sql_verified,sql_error=sql_error,runtime_versions=versions)})
            return dict(state='passed',sql_verified=sql_verified,sql_error=sql_error,preflight_id=run_id,runtime_versions=versions)
        except Exception as exc:
            self.db.assessment_executor_preflights.update_one({'_id':run_id},{'$set':dict(state='failed',error_code=exc.code if isinstance(exc,WorkflowError) else 'preflight_failed')})
            self.db.assessment_executor_attestations.update_many({'profile_hash':profile},{'$set':dict(state='failed',sql_verified=False)})
            raise
