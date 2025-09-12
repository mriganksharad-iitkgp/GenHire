"""
LLM Factory for creating LLM instances based on provider.
"""

from typing import Dict, Type
from ..config.settings import LLMProvider, LLMConfig
from .base import BaseLLM
from .groq_llm import GroqLLM
from .openai_llm import OpenAILLM
from .gemini_llm import GeminiLLM


class LLMFactory:
    """Factory class for creating LLM instances."""

    _providers: Dict[LLMProvider, Type[BaseLLM]] = {
        LLMProvider.GROQ: GroqLLM,
        LLMProvider.OPENAI: OpenAILLM,
        LLMProvider.GEMINI: GeminiLLM,
    }

    @classmethod
    def create(cls, config: LLMConfig) -> BaseLLM:
        """Create an LLM instance based on the provider."""
        if config.provider not in cls._providers:
            raise ValueError(f"Unsupported LLM provider: {config.provider}")

        provider_class = cls._providers[config.provider]

        return provider_class(
            model_name=config.model_name,
            api_key=config.api_key,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout_seconds=config.timeout_seconds,
        )

    @classmethod
    def register_provider(cls, provider: LLMProvider, llm_class: Type[BaseLLM]):
        """Register a new LLM provider."""
        cls._providers[provider] = llm_class

    @classmethod
    def get_available_providers(cls) -> list[LLMProvider]:
        """Get list of available providers."""
        available = []
        for provider, llm_class in cls._providers.items():
            try:
                # Try to instantiate with dummy config to check availability
                instance = llm_class("test", "test")
                if hasattr(instance, "is_available"):
                    available.append(provider)
            except ImportError:
                continue
        return available
