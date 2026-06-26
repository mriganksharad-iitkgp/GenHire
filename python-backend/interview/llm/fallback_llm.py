"""
Fallback LLM wrapper for transparent mid-session provider switching.

Holds an ordered list of BaseLLM instances and tries each one in order.
When a quota error is detected on the current provider, seamlessly switches
to the next available provider without interrupting the caller.
"""

import logging
from typing import List, Optional

from .base import BaseLLM, LLMResponse, LLMQuotaExhaustedError

logger = logging.getLogger(__name__)


class FallbackLLM(BaseLLM):
    """
    A wrapper LLM that delegates to an ordered list of BaseLLM providers.

    On quota exhaustion (LLMQuotaExhaustedError) or RuntimeError from the
    current provider, it transparently switches to the next one.

    Usage::

        fallback = FallbackLLM(providers=[openai_llm, gemini_llm, groq_llm])
        response = fallback.complete(prompt)
        print(fallback.current_provider_name)  # which provider actually responded
    """

    def __init__(self, providers: List[BaseLLM]):
        if not providers:
            raise ValueError("At least one LLM provider is required")

        # Use the first provider's config for the base class
        primary = providers[0]
        super().__init__(
            model_name=primary.model_name,
            api_key=primary.api_key,
            **primary.config,
        )

        self._providers = providers
        self._current_index = 0
        self._current_provider_name = primary.model_name

    @property
    def current_provider(self) -> BaseLLM:
        """The provider currently being used."""
        return self._providers[self._current_index]

    @property
    def current_provider_name(self) -> str:
        """Human-readable name of the current provider."""
        return self._current_provider_name

    def _create_llama_index_llm(self):
        """Delegate to the current provider."""
        return self.current_provider.llama_index_llm

    def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """
        Try completing with the current provider; on quota error, switch
        to the next available provider transparently.
        """
        errors = []

        for i in range(len(self._providers)):
            provider_idx = (self._current_index + i) % len(self._providers)
            provider = self._providers[provider_idx]

            try:
                response = provider.complete(prompt, **kwargs)

                # Update current provider if we switched
                if provider_idx != self._current_index:
                    old_name = self._current_provider_name
                    self._current_index = provider_idx
                    self._current_provider_name = provider.model_name
                    logger.warning(
                        f"Interview LLM switched from '{old_name}' to "
                        f"'{provider.model_name}' due to previous provider failure"
                    )

                return response

            except LLMQuotaExhaustedError as e:
                logger.warning(
                    f"Provider '{provider.model_name}' quota exhausted: {e}. "
                    f"Trying next provider..."
                )
                errors.append((provider.model_name, e))
                continue

            except RuntimeError as e:
                logger.warning(
                    f"Provider '{provider.model_name}' failed: {e}. "
                    f"Trying next provider..."
                )
                errors.append((provider.model_name, e))
                continue

        # All providers exhausted
        error_summary = "; ".join(f"{name}: {err}" for name, err in errors)
        raise RuntimeError(
            f"All interview LLM providers failed. Errors: {error_summary}"
        )

    def is_available(self) -> bool:
        """Return True if any provider is available."""
        return any(p.is_available() for p in self._providers)

    def validate_response(self, response: LLMResponse) -> bool:
        """Validate the LLM response."""
        return response.text is not None and len(response.text.strip()) > 0
