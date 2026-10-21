import unittest
from unittest.mock import Mock,patch
from services.llm_fallback_service import LLMFallbackService,ProviderConfig,LLMAllProvidersExhaustedError,LLMRateLimitDeferred,temporary_retry_after,LLMInvalidOutputError,is_quota_error,create_assessment_llm_service

class ProviderJSONRecoveryTests(unittest.TestCase):
    def test_authoring_backup_uses_separate_model_cooldown_when_primary_daily_quota_is_spent(self):
        import os
        cfg=ProviderConfig(name='groq',provider_type='groq',api_key='test',model='openai/gpt-oss-20b')
        error=RuntimeError('tokens per day limit');error.status_code=429;error.body={'error':{'code':'rate_limit_exceeded'}}
        primary=Mock();primary.bind.return_value.invoke.side_effect=error
        backup=Mock();backup.bind.return_value.invoke.return_value=Mock(content='{"ok":true}',usage_metadata={})
        with patch.dict(os.environ,{'GENHIRE_ASSESSMENT_GROQ_FALLBACK_MODEL':'openai/gpt-oss-120b'}),patch.object(LLMFallbackService,'_build_default_providers',return_value=[cfg]):
            service=create_assessment_llm_service()
        with patch.object(LLMFallbackService,'_create_llm',side_effect=lambda c:primary if c.model==cfg.model else backup),patch('services.provider_usage_service.record_provider_request'),patch('services.llm_fallback_service.time.sleep'):
            result=service.invoke('JSON',json_mode=True,defer_rate_limits=True,max_output_tokens=2048)
        self.assertEqual(result['model_used'],'openai/gpt-oss-120b')
        self.assertIn('groq',service._cooldowns);self.assertNotIn('groq_authoring_backup',service._cooldowns)
        self.assertTrue(result['fallback_triggered'])

    def test_authoring_backup_can_be_disabled_without_changing_global_model_chain(self):
        import os
        cfg=ProviderConfig(name='groq',provider_type='groq',api_key='test',model='openai/gpt-oss-20b')
        with patch.dict(os.environ,{'GENHIRE_ASSESSMENT_GROQ_FALLBACK_MODEL':''}),patch.object(LLMFallbackService,'_build_default_providers',return_value=[cfg]):
            self.assertEqual(len(create_assessment_llm_service()._providers),1)
    def test_truncation_and_json_rejection_never_mark_provider_quota_exhausted(self):
        self.assertFalse(is_quota_error(LLMInvalidOutputError('JSON response exceeded its output budget.')))
        rejected=RuntimeError('Private generated question discusses rate limits and billing quota')
        rejected.status_code=400;self.assertFalse(is_quota_error(rejected))
        llm=Mock();llm.bind.return_value.invoke.return_value=Mock(content='',response_metadata={'finish_reason':'length'})
        service=self.service()
        with patch.object(LLMFallbackService,'_create_llm',return_value=llm):
            with self.assertRaises(LLMAllProvidersExhaustedError):service.invoke('JSON',json_mode=True)
        self.assertEqual(service._cooldowns,{})

    def service(self):
        return LLMFallbackService([ProviderConfig(name='groq',provider_type='groq',api_key='test-only',model='test-only',max_retries=1)])
    def test_definite_json_rejection_retries_plain_once_with_valid_json(self):
        error=RuntimeError('private generated material');error.status_code=400;error.body={'error':{'code':'json_validate_failed'}}
        plain=Mock();plain.bind.return_value.invoke.side_effect=error
        plain.invoke.return_value=Mock(content='{"questions":[]}',usage_metadata={})
        with patch.object(LLMFallbackService,'_create_llm',return_value=plain),patch('services.provider_usage_service.record_provider_request'):
            result=self.service().invoke('Return JSON only',json_mode=True)
        self.assertEqual(result['content'],'{"questions":[]}');self.assertEqual(plain.invoke.call_count,1)

    def test_definite_strict_schema_rejection_can_recover_with_validated_plain_json(self):
        error=RuntimeError('rejected');error.status_code=400;error.body={'error':{'code':'json_validate_failed'}}
        plain=Mock();plain.bind.return_value.invoke.side_effect=error;plain.invoke.return_value=Mock(content='{"questions":[]}',usage_metadata={})
        provider=ProviderConfig(name='groq',provider_type='groq',api_key='test',model='openai/gpt-oss-20b',max_retries=1)
        schema={'type':'object','properties':{},'required':[],'additionalProperties':False}
        with patch.object(LLMFallbackService,'_create_llm',return_value=plain),patch('services.provider_usage_service.record_provider_request'):
            result=LLMFallbackService([provider]).invoke('Return JSON only',json_mode=True,response_schema=schema)
        self.assertEqual(result['content'],'{"questions":[]}');plain.invoke.assert_called_once()
    def test_json_tasks_receive_explicit_output_budget_and_low_gpt_oss_reasoning(self):
        provider=ProviderConfig(name='groq',provider_type='groq',api_key='test',model='openai/gpt-oss-20b',max_retries=1)
        llm=Mock();llm.bind.return_value.invoke.return_value=Mock(content='{"ok":true}',usage_metadata={})
        with patch.object(LLMFallbackService,'_create_llm',return_value=llm) as factory,patch('services.provider_usage_service.record_provider_request'):
            LLMFallbackService([provider]).invoke('JSON',json_mode=True)
        config=factory.call_args.args[0]
        self.assertGreaterEqual(config.max_tokens,8192);self.assertEqual(config.reasoning_effort,'low')

    def test_empty_json_completion_is_not_reported_as_success(self):
        plain=Mock();plain.bind.return_value.invoke.return_value=Mock(content='',response_metadata={'finish_reason':'length'})
        with patch.object(LLMFallbackService,'_create_llm',return_value=plain):
            with self.assertRaises(LLMAllProvidersExhaustedError):self.service().invoke('JSON',json_mode=True)

    def test_temporary_refusal_uses_retry_after_without_one_second_replay(self):
        error=RuntimeError('private request material');error.status_code=429
        error.response=Mock(headers={'retry-after':'17'})
        llm=Mock();llm.bind.return_value.invoke.side_effect=error
        service=self.service()
        with patch.object(LLMFallbackService,'_create_llm',return_value=llm),patch('services.llm_fallback_service.time.sleep') as sleep:
            for _ in range(2):
                with self.assertRaises(LLMRateLimitDeferred) as caught:
                    service.invoke('JSON',json_mode=True,defer_rate_limits=True)
                self.assertGreaterEqual(caught.exception.retry_after,17)
        sleep.assert_not_called();self.assertEqual(llm.bind.return_value.invoke.call_count,1)

    def test_daily_quota_and_funding_are_not_rescheduled_as_short_rate_limits(self):
        for status,message,delay in [(402,'billing','10'),(429,'tokens per day','10'),(429,'rate limit','3600')]:
            error=RuntimeError(message);error.status_code=status;error.response=Mock(headers={'retry-after':delay})
            self.assertIsNone(temporary_retry_after(error))

    def test_mcq_output_budget_can_be_smaller_than_code_budget(self):
        llm=Mock();llm.bind.return_value.invoke.return_value=Mock(content='{"ok":true}',usage_metadata={})
        with patch.object(LLMFallbackService,'_create_llm',return_value=llm) as factory,patch('services.provider_usage_service.record_provider_request'):
            self.service().invoke('JSON',json_mode=True,max_output_tokens=2048)
        self.assertEqual(factory.call_args.args[0].max_tokens,2048)

    def test_supported_groq_model_uses_constrained_schema_without_plain_fallback(self):
        llm=Mock();llm.bind.return_value.invoke.return_value=Mock(content='{"questions":[]}',usage_metadata={})
        provider=ProviderConfig(name='groq',provider_type='groq',api_key='test',model='openai/gpt-oss-20b',max_retries=1)
        schema={'type':'object','properties':{},'required':[],'additionalProperties':False}
        with patch.object(LLMFallbackService,'_create_llm',return_value=llm),patch('services.provider_usage_service.record_provider_request'):
            LLMFallbackService([provider]).invoke('JSON',json_mode=True,response_schema=schema)
        fmt=llm.bind.call_args.kwargs['response_format']
        self.assertEqual(fmt['type'],'json_schema');self.assertTrue(fmt['json_schema']['strict'])
        llm.invoke.assert_not_called()

    def test_size_refusal_reduces_output_budget_and_preserves_complete_brief(self):
        error=RuntimeError('Request too large. Limit 8000, Requested 9809.')
        error.status_code=413;error.body={'error':{'code':'rate_limit_exceeded'}}
        llm=Mock();llm.bind.return_value.invoke.side_effect=[error,Mock(content='{"ok":true}',usage_metadata={})]
        provider=ProviderConfig(name='groq',provider_type='groq',api_key='test',model='openai/gpt-oss-20b')
        with patch.object(LLMFallbackService,'_create_llm',return_value=llm) as factory,patch('services.provider_usage_service.record_provider_request'):
            result=LLMFallbackService([provider]).invoke('Complete unmodified brief',json_mode=True)
        self.assertEqual(result['content'],'{"ok":true}')
        self.assertEqual([call.args[0].max_tokens for call in factory.call_args_list],[8192,6127])
        self.assertEqual([call.args[0] for call in llm.bind.return_value.invoke.call_args_list],['Complete unmodified brief']*2)

    def test_unknown_network_failure_never_uses_plain_recovery(self):
        plain=Mock();plain.bind.return_value.invoke.side_effect=TimeoutError('unknown result')
        with patch.object(LLMFallbackService,'_create_llm',return_value=plain):
            with self.assertRaises(LLMAllProvidersExhaustedError):self.service().invoke('JSON',json_mode=True)
        plain.invoke.assert_not_called()
    def test_recovery_does_not_accept_non_json_output(self):
        error=RuntimeError('rejected');error.status_code=400;error.body={'error':{'code':'json_validate_failed'}}
        plain=Mock();plain.bind.return_value.invoke.side_effect=error;plain.invoke.return_value=Mock(content='not JSON')
        with patch.object(LLMFallbackService,'_create_llm',return_value=plain):
            with self.assertRaises(LLMAllProvidersExhaustedError):self.service().invoke('JSON',json_mode=True)


class JSONTransportTests(unittest.TestCase):
    def test_raw_source_newline_and_regex_escape_are_preserved(self):
        import json
        from services.json_transport import escape_json_strings
        raw='{"source":"line1'+chr(10)+'line2 '+chr(92)+'s"}'
        parsed=json.loads(escape_json_strings(raw))
        self.assertEqual(parsed['source'],'line1'+chr(10)+'line2 '+chr(92)+'s')
    def test_valid_json_unchanged_and_missing_structure_is_not_invented(self):
        import json
        from services.json_transport import escape_json_strings
        raw='{"value":"a'+chr(92)+'n","number":12}'
        self.assertEqual(escape_json_strings(raw),raw)
        with self.assertRaises(json.JSONDecodeError):json.loads(escape_json_strings('{"value":'))
        with self.assertRaises(json.JSONDecodeError):json.loads(escape_json_strings('{"value":"'+chr(92)+'uZZZZ"}'))
