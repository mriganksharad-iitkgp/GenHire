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
        )])

    def _create_llama_index_llm(self):
        raise NotImplementedError("Interview completion uses the shared chat client")

    def complete(self, prompt, **kwargs):
        try:
            result = self.service.invoke(prompt)
            return LLMResponse(text=result["content"], model=result["model_used"],
                               usage=result["usage"], finish_reason="completed",
                               metadata={"provider": result["provider_used"]})
        except Exception as exc:
            raise RuntimeError("Interview provider request failed") from exc

    def is_available(self):
        return bool(self.api_key)


class DeepSeekLLM(ChatProviderLLM):
    provider_type = "deepseek"


class GeminiChatLLM(ChatProviderLLM):
    provider_type = "google"


class GroqChatLLM(ChatProviderLLM):
    provider_type = "groq"
