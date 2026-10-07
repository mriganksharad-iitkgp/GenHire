"""
LLM Factory for creating LLM instances based on provider.
"""

import logging
from typing import Dict, List, Type
from ..config.settings import LLMProvider, LLMConfig
from .base import BaseLLM
from .openai_llm import OpenAILLM
from .fallback_llm import FallbackLLM
from .chat_provider_llm import DeepSeekLLM, GeminiChatLLM, GroqChatLLM

logger = logging.getLogger(__name__)


class LLMFactory:
    """Factory class for creating LLM instances."""

    _providers: Dict[LLMProvider, Type[BaseLLM]] = {
        LLMProvider.GROQ: GroqChatLLM,
        LLMProvider.OPENAI: OpenAILLM,
        LLMProvider.GEMINI: GeminiChatLLM,
        LLMProvider.DEEPSEEK: DeepSeekLLM,
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
    def create_with_fallback(cls, configs: List[LLMConfig]) -> BaseLLM:
        """
        Create a FallbackLLM that tries providers in the order given.

        If only one config is provided, returns a simple LLM instance.
        If multiple configs are provided, wraps them in a FallbackLLM that
        transparently switches on quota exhaustion.

        Args:
            configs: Ordered list of LLMConfig objects (primary first)

        Returns:
            BaseLLM instance (either simple or FallbackLLM wrapper)
        """
        if not configs:
            raise ValueError("At least one LLMConfig is required")

        if len(configs) == 1:
            return cls.create(configs[0])

        providers = []
        for cfg in configs:
            try:
                llm = cls.create(cfg)
                providers.append(llm)
                logger.info(
                    f"Registered fallback provider: {cfg.provider.value} "
                    f"({cfg.model_name})"
                )
            except Exception as e:
                logger.warning(
                    f"Skipping provider {cfg.provider.value}: {e}"
                )

        if not providers:
            raise ValueError("No valid LLM providers could be created")

        if len(providers) == 1:
            return providers[0]

        logger.info(
            f"Created FallbackLLM with {len(providers)} providers: "
            f"{[p.model_name for p in providers]}"
        )
        return FallbackLLM(providers=providers)

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
