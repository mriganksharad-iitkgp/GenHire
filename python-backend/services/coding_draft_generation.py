"""Small coding-authoring calls with private, resumable language checkpoints."""
from copy import deepcopy
import json

from models.hiring_workflow import WorkflowError
from models.job_setup import fields
from services.assessment_generation_schema import obj, question_response_schema
from services.assessment_generation_service import parse_generated, question_contract
from services.json_transport import escape_json_strings
from services.llm_fallback_service import LLMAllProvidersExhaustedError, LLMInvalidOutputError


def invalid_output(error):
    if isinstance(error, WorkflowError):
        return error.code in {'invalid_generation','invalid_job_setup','invalid_test_suite'}
    if not isinstance(error, LLMAllProvidersExhaustedError):
        return False
    for _, leaf in error.errors:
        if isinstance(leaf, (LLMInvalidOutputError, json.JSONDecodeError)):
            return True
        body = getattr(leaf, 'body', {}) or {}
        detail = body.get('error', body) if isinstance(body, dict) else {}
        if isinstance(detail,dict) and detail.get('code') in {'json_validate_failed','json_validation_failed'}:
            return True
    return False


def bounded_draft(llm, prompt, options, parse, before_call):
    for attempt in range(2):
        before_call()
        try:
            result = llm.invoke(prompt, **options)
            return parse(result.get('content'))
        except Exception as error:
            if attempt or not invalid_output(error):
                raise
            prompt += '\nThe previous output was incomplete or invalid. Return complete compact JSON, concise source and explanations, and every required field. Do not repeat large arrays.'
    raise AssertionError('Unreachable')


def generate_coding_draft(llm, context, progress, before_call):
    """One reference/test suite first, then short source translations per language.

    Mutations to progress are checkpointed by the enclosing durable operation
    only after a definite refusal. No partial question is published or banked.
    """
    requested = context['languages']
    base = 'python' if 'python' in requested else requested[0]
    spec = context['requests'][0]
    if 'question' not in progress:
        seed = dict(context, languages=[base], runtime_versions={base:context['runtime_versions'][base]})
        contract = question_contract('coding') + '\nDraft only; execution validation follows later. Avoid repeated questions.\n'
        options = dict(json_mode=True, defer_rate_limits=True, max_output_tokens=4096)
        schema = question_response_schema('coding',[base],context['coding_contract'])
        if schema:
            options['response_schema'] = schema
        q = bounded_draft(llm, contract+json.dumps(seed), options,
            lambda content:parse_generated(content,[spec])[0], before_call)
        if q['coding']['languages'] != [base] or q['coding']['contract'] != context['coding_contract']:
            raise WorkflowError('invalid_generation','Coding format differs from the request.',422)
        progress['question'] = q
    q = progress['question']
    coding = q['coding']
    for language in requested:
        if language in coding['reference_solutions']:
            continue
        translation = dict(task='translate_coding_sources', language=language,
            runtime_version=context['runtime_versions'][language], statement=q['statement'],
            coding_contract=coding['contract'],signature=coding['signature'],input_format=coding['input_format'],
            output_format=coding['output_format'],constraints=coding['constraints'],
            base_language=base,reference_solution=coding['reference_solutions'][base])
        prompt = ('Translate the supplied reference solution to the requested runtime without changing its algorithm or I/O. '
            'For function tasks use the exact signature and class Solution in Java/C++. '
            'Return only JSON with exactly starter_code (a concise valid TODO skeleton) and reference_solution '
            '(complete runnable source). No tests, explanation, markdown or extra keys.\n'
            'Draft only; execution validation follows later. Avoid repeated questions.\n'+json.dumps(translation))
        def parse_sources(content):
            try:
                def pairs(items):
                    value={}
                    for key,item in items:
                        if key in value:raise ValueError('Duplicate key')
                        value[key]=item
                    return value
                value=json.loads(escape_json_strings(content),object_pairs_hook=pairs)
                fields(value,{'starter_code','reference_solution'},'Coding sources',{'starter_code','reference_solution'})
                if any(not isinstance(s,str) or not s.strip() or len(s)>64000 for s in value.values()):
                    raise ValueError('Invalid coding source')
                return value
            except (ValueError,TypeError):
                raise WorkflowError('invalid_generation','Invalid translated coding source JSON.',422) from None
        sources=bounded_draft(llm,prompt,dict(json_mode=True,defer_rate_limits=True,max_output_tokens=4096,
            response_schema=obj(dict(starter_code={'type':'string'},reference_solution={'type':'string'}))),
            parse_sources,before_call)
        coding['starter_code'][language]=sources['starter_code']
        coding['reference_solutions'][language]=sources['reference_solution']
        coding['runtime_versions'][language]=context['runtime_versions'][language]
    result=deepcopy(q)
    result['coding']['languages']=requested[:]
    # The same strict complete-question validation still applies to the merged output.
    return parse_generated(json.dumps({'questions':[result]}),[spec])[0]
