"""S2 regression tests. No real API calls, MongoDB writes or account secrets.

Run: python -m unittest discover -s python-backend/tests -v (from repo root).
Isolate package imports from the app's eager ML/session startup so these
tests require only the provider/speech dependencies in requirements.txt.
"""
import importlib
import os
import sys
import types
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
# Never read developer dotenv secrets during tests.
_dotenv_patch = patch("dotenv.load_dotenv", return_value=False)
_dotenv_patch.start()
for name in ("interview", "interview.core", "interview.config", "interview.llm",
             "evaluation_model", "evaluation_model.rubrics_eval", "controllers", "controllers.admin"):
    if name not in sys.modules:
        module = types.ModuleType(name)
        module.__path__ = [str(BACKEND.joinpath(*name.split(".")))]
        sys.modules[name] = module

from services.llm_fallback_service import LLMFallbackService, ProviderConfig, get_provider_priority, default_model_for, LLMAllProvidersExhaustedError
from services.usage_telemetry_service import extract_usage_from_response
from services.ai_pricing_service import token_cost_usd, deepseek_rates, groq_stt_cost
from services.provider_usage_service import record_provider_request, provider_costs_for_range
from services.deepseek_billing_service import fetch_deepseek_balance
from interview.core.cost_tracker import CostTracker, calculate_cost
from interview.config.settings import LLMConfig, LLMProvider
from interview.llm.factory import LLMFactory
from interview.llm.fallback_llm import FallbackLLM
from controllers.admin.cost_helpers import CostStatsHelpers


S2_ENV = {"LLM_PROVIDER_PRIORITY": "deepseek,gemini,groq", "DEEPSEEK_API_KEY": "test-deepseek",
          "GOOGLE_API_KEY": "test-google", "GROQ_API_KEY": "test-groq",
          "DEEPSEEK_PRICING_MODE": "peak", "STT_PROVIDER": "groq"}


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, S2_ENV, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_default_order_excludes_leftover_openai_key(self):
        os.environ.pop("LLM_PROVIDER_PRIORITY")
        os.environ["OPENAI_API_KEY"] = "leftover-key"
        self.assertEqual(get_provider_priority(), ["deepseek", "google", "groq"])
        self.assertEqual([p.name for p in LLMFallbackService()._providers], ["deepseek", "google", "groq"])

    def test_explicit_chain_does_not_append_providers(self):
        os.environ["LLM_PROVIDER_PRIORITY"] = "gemini,google,groq"
        self.assertEqual(get_provider_priority(), ["google", "groq"])

    def test_explicit_model_wins_over_legacy_cv_pin(self):
        os.environ.update(LLM_GEMINI_MODEL="gemini-3.1-flash-lite", CV_SCORING_MODEL="obsolete-model")
        self.assertEqual(default_model_for("google"), "gemini-3.1-flash-lite")

    def test_deepseek_client_routes_to_deepseek_with_thinking_disabled(self):
        llm = LLMFallbackService._create_llm(ProviderConfig(
            "deepseek", "deepseek", "test-key", "deepseek-flash"))
        self.assertIn("api.deepseek.com", llm.openai_api_base)
        self.assertEqual(llm.extra_body, {"thinking": {"type": "disabled"}})
        self.assertEqual(llm.model_name, "deepseek-flash")

    def test_gemini_and_groq_clients_accept_requested_models(self):
        for provider, model in (("google", "gemini-3.1-flash-lite"), ("groq", "openai/gpt-oss-20b")):
            llm = LLMFallbackService._create_llm(ProviderConfig(provider, provider, "test-key", model))
            self.assertIsNotNone(llm)

    def test_interview_groq_reasoning_budget_and_truncation_fallback(self):
        from interview.llm.chat_provider_llm import GroqChatLLM
        provider = GroqChatLLM("openai/gpt-oss-20b", "test-key", max_tokens=1024)
        config = provider.service._providers[0]
        client = LLMFallbackService._create_llm(config)
        self.assertEqual(client.model_kwargs["reasoning_effort"], "low")
        self.assertEqual(client.max_tokens, 1024)
        response = {"content": "", "raw_response": SimpleNamespace(response_metadata={"finish_reason": "length"})}
        with patch.object(provider.service, "invoke", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "output_budget_exhausted"):
                provider.complete("Ask a short question")

    def test_interview_two_failed_providers_reach_groq_on_followup(self):
        from interview.llm.chat_provider_llm import DeepSeekLLM, GeminiChatLLM, GroqChatLLM
        primary, secondary, third = DeepSeekLLM("deepseek-flash", "test"), GeminiChatLLM("gemini-3.1-flash-lite", "test"), GroqChatLLM("openai/gpt-oss-20b", "test", max_tokens=1024)
        chain = FallbackLLM([primary, secondary, third])
        def response(text):
            return {"content": text, "model_used": third.model_name, "provider_used": "groq", "usage": {}, "raw_response": SimpleNamespace(response_metadata={"finish_reason": "stop"})}
        with patch.object(primary.service, "invoke", side_effect=RuntimeError("402")), patch.object(secondary.service, "invoke", side_effect=RuntimeError("429")), patch.object(third.service, "invoke", side_effect=[response("What did you build?"), response("How did you test it?")]):
            self.assertEqual(chain.complete("first").text, "What did you build?")
            self.assertEqual(chain.complete("followup").text, "How did you test it?")

    def _exercise_failover(self, failures, images=None):
        service = LLMFallbackService(providers=[ProviderConfig(p, p, "test", default_model_for(p), max_retries=1)
                                               for p in ("deepseek", "google", "groq")])
        called = []
        def create(cfg):
            called.append(cfg.name)
            if cfg.name in failures:
                raise RuntimeError("429 quota exhausted")
            return SimpleNamespace(invoke=lambda prompt: SimpleNamespace(
                content="answer", usage_metadata={"input_tokens": 10, "output_tokens": 2}, response_metadata={}))
        with patch.object(service, "_create_llm", side_effect=create), patch("services.provider_usage_service.record_provider_request") as ledger:
            result = service.invoke("Question", images=images)
        self.assertEqual(ledger.call_count, 1)
        return service, called, result

    def test_falls_back_to_gemini_before_groq(self):
        service, called, result = self._exercise_failover({"deepseek"})
        self.assertEqual(called, ["deepseek", "google"])
        self.assertEqual(result["provider_used"], "google")
        self.assertTrue(result["fallback_triggered"])
        self.assertTrue(service._is_on_cooldown("deepseek"))

    def test_falls_back_to_groq_after_both_fail(self):
        _, called, result = self._exercise_failover({"deepseek", "google"})
        self.assertEqual(called, ["deepseek", "google", "groq"])
        self.assertEqual(result["model_used"], "openai/gpt-oss-20b")

    def test_billing_402_cools_down_instead_of_delaying_every_question(self):
        service = LLMFallbackService(providers=[ProviderConfig("deepseek", "deepseek", "test", "deepseek-flash", max_retries=1),
                                               ProviderConfig("groq", "groq", "test", "openai/gpt-oss-20b", max_retries=1)])
        class BalanceError(Exception):
            status_code = 402
        calls = []
        def create(config):
            calls.append(config.name)
            if config.name == "deepseek":
                raise BalanceError("Payment required")
            return SimpleNamespace(invoke=lambda prompt: SimpleNamespace(content="Which API design decision mattered?", usage_metadata={}, response_metadata={}))
        with patch.object(service, "_create_llm", side_effect=create), patch("services.provider_usage_service.record_provider_request"):
            service.invoke("question one")
            service.invoke("question two")
        self.assertEqual(calls, ["deepseek", "groq", "groq"])

    def test_text_only_groq_is_skipped_for_vision(self):
        service = LLMFallbackService(providers=[ProviderConfig("groq", "groq", "test", "openai/gpt-oss-20b")])
        with patch.object(service, "_create_llm") as create:
            with self.assertRaises(LLMAllProvidersExhaustedError):
                service.invoke("Describe", images=[(b"image", "image/png")])
            create.assert_not_called()

    def test_interview_factory_uses_shared_clients(self):
        providers = [LLMConfig(provider=p, api_key="test", model_name=m) for p, m in (
            (LLMProvider.DEEPSEEK, "deepseek-flash"), (LLMProvider.GEMINI, "gemini-3.1-flash-lite"),
            (LLMProvider.GROQ, "openai/gpt-oss-20b"))]
        chain = LLMFactory.create_with_fallback(providers)
        self.assertIsInstance(chain, FallbackLLM)
        self.assertEqual([p.provider_type for p in chain._providers], ["deepseek", "google", "groq"])

    def test_evaluation_no_longer_requires_openai(self):
        from evaluation_model.rubrics_eval.config import Config
        Config.load_from_environment()
        Config.validate()
        self.assertIsNone(Config.OPENAI_API_KEY)

    def test_evaluation_honors_disabled_tracing(self):
        from evaluation_model.rubrics_eval.config import Config
        with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "false", "LANGCHAIN_ENDPOINT": "https://trace.example.test"}):
            Config.load_from_environment()
            self.assertEqual(os.environ["LANGCHAIN_TRACING_V2"], "false")
            self.assertEqual(Config.LANGCHAIN_ENDPOINT, "https://trace.example.test")


class UsageTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, S2_ENV, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        CostTracker().reset()

    def test_langchain_dict_usage_and_zero_output(self):
        usage = extract_usage_from_response(SimpleNamespace(
            usage_metadata={"input_tokens": 15, "output_tokens": 0}, response_metadata={}))
        self.assertEqual(usage["completion_tokens"], 0)
        self.assertEqual(usage["usage_source"], "actual")

    def test_deepseek_cache_counts_preserved(self):
        response = SimpleNamespace(response_metadata={"token_usage": {
            "prompt_tokens": 1000, "completion_tokens": 500, "prompt_cache_hit_tokens": 800}},
            usage_metadata={"input_tokens": 1000, "output_tokens": 500})
        usage = extract_usage_from_response(response)
        self.assertEqual(usage["prompt_cache_hit_tokens"], 800)
        self.assertAlmostEqual(token_cost_usd("deepseek-flash", usage), 0.0006648)

    def test_sdk_usage_and_unknown_model(self):
        usage = extract_usage_from_response(SimpleNamespace(usage=SimpleNamespace(model_dump=lambda: {
            "prompt_tokens": 10, "completion_tokens": 2, "prompt_tokens_details": {"cached_tokens": 5}})))
        self.assertEqual(usage["prompt_cache_hit_tokens"], 5)
        self.assertIsNone(token_cost_usd("unknown", usage))

    def test_peak_offpeak_and_auto_rates(self):
        os.environ["DEEPSEEK_PRICING_MODE"] = "auto"
        self.assertEqual(deepseek_rates(datetime(2026, 10, 5, 2))["input"], 0.30)
        self.assertEqual(deepseek_rates(datetime(2026, 10, 5, 12))["input"], 0.15)
        self.assertEqual(deepseek_rates(datetime(2026, 10, 4, 2))["input"], 0.15)

    def test_whisper_minimum_per_request(self):
        self.assertAlmostEqual(groq_stt_cost(1), 10 / 3600 * 0.04)
        self.assertAlmostEqual(groq_stt_cost(900), 0.01)

    def test_session_cost_uses_reported_tokens_and_cache(self):
        tracker = CostTracker()
        tracker.start_session("test")
        usage = {"prompt_tokens": 1000, "completion_tokens": 500, "prompt_cache_hit_tokens": 800}
        tracker.add_usage("question_generation", "deepseek-flash", 1000, 500, session_id="test", usage=usage)
        self.assertAlmostEqual(tracker.get_summary("test")["total_cost"], round(0.0006648, 6))

    def test_context_speech_usage_belongs_to_correct_session(self):
        tracker = CostTracker()
        token = tracker.set_session_context("context-session")
        try:
            tracker.add_stt_usage("interview_stt", 30)
            tracker.add_tts_usage("interview_tts", 100)
        finally:
            tracker.clear_session_context(token)
        self.assertEqual(tracker.get_summary("context-session")["total_stt_seconds"], 30)
        self.assertEqual(tracker.get_summary("context-session")["total_tts_characters"], 100)

    def test_fallback_session_summary_uses_groq_stt(self):
        summary = CostTracker().build_usage_summary(stt_seconds=900, tts_characters=4000)
        self.assertAlmostEqual(summary["total_cost"], 0.026)

    def test_ledger_snapshots_prices_once_and_stores_no_prompt(self):
        from config.database import db_config
        db = MagicMock()
        usage = {"prompt_tokens": 1000, "completion_tokens": 500, "prompt_cache_hit_tokens": 800, "usage_source": "actual"}
        with patch.object(db_config, "db", db):
            record_provider_request("deepseek", "deepseek-flash", usage)
        event = db["ai_provider_requests"].insert_one.call_args.args[0]
        self.assertAlmostEqual(event["estimated_cost_usd"], 0.0006648)
        self.assertEqual(event["rates"]["cached_input"], 0.006)
        self.assertNotIn("prompt", event)

    def test_timeline_aggregation_filters_event_dates(self):
        db = MagicMock()
        db["ai_provider_requests"].aggregate.return_value = [{"_id": "deepseek", "cost_usd": 0.5, "request_count": 2}]
        start, end = datetime(2026, 10, 1), datetime(2026, 10, 5)
        rows = provider_costs_for_range(db, start, end)
        pipeline = db["ai_provider_requests"].aggregate.call_args.args[0]
        self.assertEqual(pipeline[0]["$match"]["occurred_at"], {"$gte": start, "$lte": end})
        self.assertEqual(rows["deepseek"]["cost_usd"], 0.5)

    def test_admin_timeline_uses_ist_day_boundaries(self):
        self.assertEqual(CostStatsHelpers()._parse_date("2026-10-05"), datetime(2026, 10, 4, 18, 30))

    def test_admin_reference_follows_env(self):
        reference = CostStatsHelpers()._llm_pricing_reference()
        self.assertEqual([p["provider"] for p in reference["providers"]], ["DeepSeek", "Google Gemini", "Groq"])
        self.assertEqual(reference["providers"][2]["model"], "openai/gpt-oss-20b")

    def test_admin_interview_line_keeps_per_request_speech_cost(self):
        class Helpers(CostStatsHelpers):
            MAX_DERIVED_STT_SECONDS = 7200
        helpers = Helpers()
        os.environ["INR_PER_USD"] = "100"
        line = helpers._build_interview_cost_line(
            {"prompt_tokens": 100, "completion_tokens": 50, "stt_seconds": 12,
             "tts_characters": 100, "usage_summary": {
                 "stt_model": "whisper-large-v3-turbo", "stt_cost_usd": 0.0002222222,
                 "tts_cost_usd": 0.0004, "total_actual_cost": 0.00009}},
            "ai_interview", "Interview", helpers._action_assumptions()["ai_interview"], [])
        # Two six-second requests incur two separate ten-second minimums.
        self.assertEqual(line["rates"]["stt_provider"], "groq")
        self.assertAlmostEqual(line["rates"]["stt_usd_per_hour"], 0.04)
        self.assertAlmostEqual(line["actual_cost_inr"], 0.07)

    def test_live_balance_uses_normal_key_and_handles_cny(self):
        from services.deepseek_billing_service import _cache
        _cache.update(key=None, at=0, value=None)
        response = MagicMock()
        response.json.return_value = {"is_available": True, "balance_infos": [{"currency": "CNY", "total_balance": "10.00"}]}
        with patch("services.deepseek_billing_service.requests.get", return_value=response) as get:
            value = fetch_deepseek_balance()
        self.assertEqual(value["balances"][0]["currency"], "CNY")
        self.assertEqual(get.call_args.kwargs["headers"]["Authorization"], "Bearer test-deepseek")

    def test_missing_key_balance_is_not_configured(self):
        os.environ.pop("DEEPSEEK_API_KEY")
        self.assertEqual(fetch_deepseek_balance()["status"], "not_configured")

    def test_admin_api_returns_ledger_spend_and_separate_balance(self):
        from controllers.admin.cost_stats_admin import CostStatsAdmin
        from config.database import db_config
        class Admin(CostStatsHelpers, CostStatsAdmin):
            applications_collection = jobs_collection = practice_sessions_collection = interviews_collection = None
            def _get_usage_events(self, **kwargs):
                return []
        class Collection:
            def find(self, *args, **kwargs):
                return []
            def count_documents(self, *args, **kwargs):
                return 0
            def aggregate(self, pipeline):
                self.pipeline = pipeline
                return [{"_id": "deepseek", "cost_usd": 0.123456, "request_count": 2,
                         "prompt_tokens": 100, "completion_tokens": 10, "cached_tokens": 50,
                         "unpriced_requests": 0}]
        class Database:
            def __init__(self):
                self.collection = Collection()
            def __getitem__(self, key):
                return self.collection
            def __getattr__(self, key):
                return self.collection
        db = Database()
        os.environ["INR_PER_USD"] = "100"
        gcp_module = SimpleNamespace(fetch_gcp_service_costs=lambda *a: None,
                                     fetch_gcp_current_month_outstanding=lambda: None)
        balance = {"status": "available", "balances": [{"currency": "CNY", "total_balance": "20.00"}]}
        with patch.object(db_config, "get_db", return_value=db), \
             patch.dict(sys.modules, {"services.gcp_billing_service": gcp_module}), \
             patch("services.openai_billing_service.fetch_openai_costs_usd", return_value=None), \
             patch("services.openai_billing_service.get_openai_credit_balance_usd", return_value=None), \
             patch("services.deepseek_billing_service.fetch_deepseek_balance", return_value=balance):
            payload, status = Admin().get_cost_statistics({}, start_date="2026-10-05", end_date="2026-10-05")
        self.assertEqual(status, 200, payload)
        costs = payload["cost_statistics"]["infrastructure_costs"]
        self.assertEqual(costs["deepseek"]["cost_usd"], 0.123456)
        self.assertEqual(costs["deepseek"]["cost_inr"], 12.35)
        self.assertEqual(costs["deepseek"]["balances"][0]["currency"], "CNY")
        self.assertFalse(costs["deepseek"]["included_in_infrastructure_total"])
        self.assertEqual(costs["total_infrastructure_cost_inr"], 0)
        self.assertEqual(db.collection.pipeline[0]["$match"]["occurred_at"]["$gte"], datetime(2026, 10, 4, 18, 30))


class SpeechTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, S2_ENV, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        CostTracker().reset()
        from google.auth.exceptions import DefaultCredentialsError
        self.adc = patch("google.auth.default", side_effect=DefaultCredentialsError("No test ADC"))
        self.adc.start()
        self.addCleanup(self.adc.stop)

    def test_cloud_run_tts_uses_attached_service_account(self):
        from services.google_speech_service import GoogleSpeechService
        credentials = MagicMock()
        with patch("groq.Groq"), \
             patch("google.auth.default", return_value=(credentials, "test-project")) as adc, \
             patch("google.cloud.texttospeech_v1beta1.TextToSpeechClient") as tts:
            service = GoogleSpeechService()
        tts.assert_called_once_with(credentials=credentials)
        adc.assert_called_once_with(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        self.assertIs(service.tts_client, tts.return_value)
        self.assertIsNone(service.speech_client)

    def test_groq_stt_works_without_google_credentials(self):
        import base64
        from services.google_speech_service import GoogleSpeechService
        with patch("groq.Groq") as groq:
            groq.return_value.audio.transcriptions.create.return_value = SimpleNamespace(text="Hello", duration=12)
            service = GoogleSpeechService()
        self.assertIsNone(service.tts_client)
        with patch("services.provider_usage_service.enqueue_provider_request") as ledger:
            self.assertEqual(service.speech_to_text(base64.b64encode(b"webm").decode(), session_id="s"), "Hello")
        call = service.groq_client.audio.transcriptions.create.call_args
        self.assertEqual(call.kwargs["model"], "whisper-large-v3-turbo")
        self.assertEqual(call.kwargs["response_format"], "verbose_json")
        self.assertEqual(ledger.call_args.kwargs["metadata"]["billed_seconds"], 12)

    def test_caption_words_have_context_and_filter_likely_silence_hallucinations(self):
        from services.google_speech_service import GoogleSpeechService
        response = MagicMock(text="Python Thank you", duration=8)
        response.model_dump.return_value = {"words": [
            {"word": "Python", "start": 0, "end": 1},
            {"word": "Thank you", "start": 5, "end": 6}],
            "segments": [{"start": 4, "end": 8, "no_speech_prob": .95, "avg_logprob": -1.4}]}
        with patch("groq.Groq") as groq:
            groq.return_value.audio.transcriptions.create.return_value = response
            service = GoogleSpeechService()
        with patch("services.provider_usage_service.enqueue_provider_request"):
            result = service.speech_to_text(b"RIFFfake", encoding="LINEAR16", caption_prompt="A previous confirmed sentence")
        self.assertEqual(result["text"], "Python")
        options = service.groq_client.audio.transcriptions.create.call_args.kwargs
        self.assertEqual(options["prompt"], "A previous confirmed sentence")
        self.assertEqual(options["timestamp_granularities"], ["word", "segment"])
        self.assertEqual(options["timeout"], 6)

    def test_failed_stt_does_not_record_success_or_charge_session(self):
        from services.google_speech_service import GoogleSpeechService
        with patch("groq.Groq") as groq:
            groq.return_value.audio.transcriptions.create.side_effect = RuntimeError("network failure")
            service = GoogleSpeechService()
        with patch("services.provider_usage_service.enqueue_provider_request") as ledger:
            with self.assertRaises(RuntimeError):
                service.speech_to_text(b"webm")
            ledger.assert_not_called()
        self.assertEqual(CostTracker().get_summary()["total_stt_seconds"], 0)

    def test_word_timestamps_escape_ssml_and_map_back_to_original_text(self):
        from services.google_speech_service import GoogleSpeechService
        with patch("groq.Groq"):
            service = GoogleSpeechService()
        service.tts_client = MagicMock()
        service.tts_client.synthesize_speech.return_value = SimpleNamespace(audio_content=b"mp3", timepoints=[SimpleNamespace(mark_name="w0", time_seconds=0), SimpleNamespace(mark_name="w1", time_seconds=.4)])
        with patch("services.provider_usage_service.enqueue_provider_request"):
            result = service.text_to_speech("Explain A&B", with_timestamps=True)
        payload = service.tts_client.synthesize_speech.call_args.kwargs["request"]
        self.assertIn("A&amp;B", payload["input"].ssml)
        self.assertEqual(result["timepoints"], [{"time_seconds": 0, "char_end": 7}, {"time_seconds": .4, "char_end": 11}])
        self.assertTrue(payload["enable_time_pointing"])
        with patch("services.provider_usage_service.enqueue_provider_request"):
            unicode_result = service.text_to_speech("Hi \U0001f44b", with_timestamps=True)
        self.assertEqual(unicode_result["timepoints"][-1]["char_end"], 5)

    def test_standard_tts_only_and_success_count(self):
        from services.google_speech_service import GoogleSpeechService
        with patch("groq.Groq"):
            service = GoogleSpeechService()
        service.tts_client = MagicMock()
        service.tts_client.synthesize_speech.return_value = SimpleNamespace(audio_content=b"mp3")
        with patch("services.provider_usage_service.enqueue_provider_request"):
            self.assertTrue(service.text_to_speech("Hello", session_id="s"))
        self.assertEqual(CostTracker().get_summary("s")["total_tts_characters"], 5)
        self.assertEqual(service.tts_client.synthesize_speech.call_args.kwargs["timeout"], 8)
        self.assertIsNone(service.tts_client.synthesize_speech.call_args.kwargs["retry"])
        with self.assertRaises(ValueError):
            service.text_to_speech("Hello", voice_name="en-US-Neural2-C")


if __name__ == "__main__":
    unittest.main()
