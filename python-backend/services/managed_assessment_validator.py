"""Reference validation and execution through the approved OA provider boundary."""
from datetime import datetime, timezone
import hashlib
import json
import os
from config.assessment_execution import enabled, execution_status, runtime_profiles, SQL_RUNTIMES, sql_enabled
from models.assessment_content import validate_question
from models.hiring_workflow import WorkflowError
from services.assessment_harness import function_source
from services.oa_execution_provider import execution_provider
from services.workflow_service import request_identity


class ManagedAssessmentValidator:
    def __init__(self,db,validation_mode=False):
        self.db,self.validation_mode=db,validation_mode
        self.provider=execution_provider(db)

    @staticmethod
    def profile_hash():
        return request_identity(dict(contract='onlinecompiler-native-v1-sql-json-v1',runtimes=runtime_profiles(),sql=SQL_RUNTIMES,
            endpoint=os.getenv('ONLINECOMPILER_API_BASE_URL','https://api.onlinecompiler.io'),
            account=hashlib.sha256(os.getenv('ONLINECOMPILER_API_KEY','').encode()).hexdigest(),
            policy=os.getenv('GENHIRE_EXECUTOR_ISOLATION_POLICY_ID',''),timeout=os.getenv('OA_EXECUTION_TIMEOUT_MS','30000')))

    def acceptance_fence(self,session,now,sql=False):
        query=dict(profile_hash=self.profile_hash(),state='passed',expires_at={'$gt':now})
        if sql:query['sql_verified']=True
        changed=self.db.assessment_executor_attestations.update_one(query,{'$inc':{'activation_fence':1}},session=session)
        if not changed.matched_count:raise WorkflowError('live_validation_required','Current execution acceptance is required.',503)

    def capabilities(self):
        ready=enabled() and execution_status()['configured'] and bool(os.getenv('GENHIRE_EXECUTOR_ISOLATION_POLICY_ID'))
        record=self.db.assessment_executor_attestations.find_one(dict(profile_hash=self.profile_hash(),state='passed',expires_at={'$gt':datetime.now(timezone.utc)})) if ready else None
        return dict(available=bool(ready and (self.validation_mode or record)),sql_available=bool(ready and (self.validation_mode or (record or {}).get('sql_verified'))),
            profile_hash=self.profile_hash(),reason='Current coding and generic SQL isolation acceptance is required.')

    def heartbeat(self):
        hook=getattr(self,'progress_hook',None)
        if hook and not hook():raise WorkflowError('execution_lease_lost','Execution lease expired.',409)

    @staticmethod
    def check_runtime(q,language=None):
        if q['type']=='sql':
            sql=q['sql']
            if not sql_enabled(sql['engine']):raise WorkflowError('sql_engine_unavailable','Candidate execution supports enabled SQLite/DuckDB questions only. PostgreSQL is trusted authoring only.',503)
            if sql['engine_version']!=SQL_RUNTIMES[sql['engine']]:raise WorkflowError('runtime_changed','Revise and revalidate this SQL question against the selected runtime.',503)
        else:
            coding=q['coding']
            if coding['runtime_versions'][language]!=runtime_profiles()[language]['runtime_label']:
                raise WorkflowError('runtime_changed','Revise and revalidate this question against the selected runtime.',503)
            if coding['limits']['memory_mb']!=512 or coding['limits']['output_kb']!=64:
                raise WorkflowError('unsupported_execution_limits','Native hidden judging requires the provider hard limits: 512 MB memory and 64 KB output.',400)

    def execute_case(self,identity,q,case_id,language,purpose='reference'):
        capabilities=self.capabilities()
        if not capabilities['available'] or (q['type']=='sql' and not capabilities['sql_available']):
            raise WorkflowError('validator_unavailable','Current live execution acceptance is required.',503)
        self.check_runtime(q,language);self.heartbeat()
        if q['type']=='sql':
            case=next(c for c in q['sql']['datasets'] if c['id']==case_id)
            return self.provider.run_sql(identity,q,case,purpose)
        coding=q['coding'];case=next(c for c in coding['tests'] if c['id']==case_id)
        source=function_source(q,language,case_id) if coding['contract']=='function' else coding['reference_solutions'][language]
        compiler=runtime_profiles()[language]['compiler_id']
        stdin='' if coding['contract']=='function' else case['input']
        if purpose=='grading':
            expected=json.dumps(case['expected'],ensure_ascii=True,separators=(',',':')) if coding['contract']=='function' else case['expected']
            # Function return JSON needs semantic typed comparison. Preserve it
            # through the sync transport instead of comparing JSON formatting.
            if coding['contract']!='function':
                return self.provider.judge(identity,compiler,source,[dict(input=stdin,expected_output=expected,
                    hidden=case['visibility']=='hidden',weight=case['weight'])],coding['limits']['time_ms'],
                    'exact' if coding['comparison']=='exact' else 'trim',purpose)
        output=self.provider.execute(identity,compiler,source,stdin,purpose,case['visibility']=='hidden',
            coding['limits']['time_ms'],coding['limits']['memory_mb'],coding['limits']['output_kb']*1024)
        if purpose!='public' and output['status']=='ok' and not {'time_ms','memory_kb'}<=output.keys():
            raise WorkflowError('executor_resource_evidence_missing','Resource evidence is missing.',503)
        return output

    def execution_result(self,identity,question=None):
        raw=self.provider.result(identity)
        if isinstance(raw,list):return raw[0]
        if question and question['type']=='sql':
            from services.sql_result_codec import sql_result
            return sql_result(raw,'gh'+hashlib.sha256(identity.encode()).hexdigest()[:20])
        return raw

    def validate(self,question,content_hash):
        q=validate_question(question)
        if request_identity(q)!=content_hash:raise WorkflowError('content_changed','Question content hash changed.')
        if q['type']=='mcq':raise WorkflowError('invalid_type','MCQs use structural validation.',400)
        runs=[];coding=q.get('coding');purpose='acceptance' if self.validation_mode else 'reference'
        for language in coding['languages'] if coding else [q['sql']['engine']]:
            for case in coding['tests'] if coding else q['sql']['datasets']:
                identity='reference:'+self.profile_hash()+':'+content_hash+':'+language+':'+case['id']
                output=self.execute_case(identity,q,case['id'],language,purpose)
                run=dict(runtime=language,runtime_version=coding['runtime_versions'][language] if coding else q['sql']['engine_version'],case_id=case['id'],status=output['status'])
                if coding:
                    run.update(contract=coding['contract'],harness_version=coding['harness_version'])
                    if output['status']=='ok':
                        if coding['contract']=='function':
                            try:run['value']=json.loads(output['stdout'],parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
                            except ValueError:run['status']='runtime_error'
                        else:run['stdout']=output['stdout']
                else:run.update({key:output[key] for key in ('columns','rows') if key in output})
                runs.append(run)
        return dict(adapter_id='onlinecompiler-native-v1',execution_id=self.profile_hash()+':'+content_hash,
            isolation_policy_id=os.getenv('GENHIRE_EXECUTOR_ISOLATION_POLICY_ID',''),question_hash=content_hash,runs=runs)
