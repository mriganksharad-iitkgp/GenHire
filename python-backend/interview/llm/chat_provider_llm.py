"""Interview adapter for the same modern provider clients used elsewhere."""
from .base import BaseLLM, LLMResponse
from services.llm_fallback_service import LLMFallbackService, ProviderConfig


class ChatProviderLLM(BaseLLM):
    provider_type = "deepseek"

    def __init__(self, model_name, api_key, **kwargs):
        super().__init__(model_name, api_key, **kwargs)
        self.service = LLMFallbackService(providers=[ProviderConfig(
            name=self.provider_type, provider_type=self.provider_type,
            model=model_name, api_key=api_key,
            temperature=kwargs.get("temperature", 0.7),
            timeout_seconds=kwargs.get("timeout_seconds", 30),
            max_tokens=kwargs.get("max_tokens"),
            max_retries=1,
            reasoning_effort="low" if self.provider_type == "groq" and model_name.startswith("openai/gpt-oss") else None,
        )])

    def _create_llama_index_llm(self):
        raise NotImplementedError("Interview completion uses the shared chat client")

    def complete(self, prompt, **kwargs):
        failure = "request_failed"
        try:
            result = self.service.invoke(prompt, defer_usage=True)
            finish = (getattr(result.get("raw_response"), "response_metadata", {}) or {}).get("finish_reason")
            if str(finish).lower() in {"length", "max_tokens"}:
                failure = "output_budget_exhausted"
                raise RuntimeError("Interview provider exhausted its output-token budget")
            if not str(result.get("content", "")).strip():
                failure = "empty_output"
                raise RuntimeError("Interview provider returned no text")
            return LLMResponse(text=result["content"], model=result["model_used"],
                               usage=result["usage"], finish_reason=finish or "completed",
                               metadata={"provider": result["provider_used"]})
        except Exception as exc:
            # Safe diagnostic labels without prompts, responses or credentials.
            causes = getattr(exc, "errors", [])
            if causes:
                cause = causes[-1][1]
                failure = f"{type(cause).__name__}:{getattr(cause, 'status_code', 'unknown')}"
            elif failure == "request_failed" and hasattr(exc, "errors"):
                failure = "provider_cooldown"
            raise RuntimeError(f"Interview provider request failed ({failure})") from exc

    def is_available(self):
        return bool(self.api_key)


class DeepSeekLLM(ChatProviderLLM):
    provider_type = "deepseek"


class GeminiChatLLM(ChatProviderLLM):
    provider_type = "google"


class GroqChatLLM(ChatProviderLLM):
    provider_type = "groq"
