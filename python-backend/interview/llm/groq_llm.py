"""
Groq LLM implementation using llama_index.
"""

import os
from typing import Optional, Any
from .base import BaseLLM, LLMResponse

try:
    from llama_index.llms.groq import Groq

    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


class GroqLLM(BaseLLM):
    """Groq LLM implementation using llama_index."""

    def __init__(self, model_name: str, api_key: str, **kwargs):
        super().__init__(model_name, api_key, **kwargs)

        if not GROQ_AVAILABLE:
            raise ImportError(
                "Groq library not available. Install with: pip install llama-index-llms-groq"
            )

        # Set environment variable for llama-index
        os.environ["GROQ_API_KEY"] = api_key

    def _create_llama_index_llm(self) -> Any:
        """Create the llama_index Groq LLM instance."""
        return Groq(
            model=self.model_name,
            api_key=self.api_key,
            temperature=self.config.get("temperature", 0.7),
            max_tokens=self.config.get("max_tokens"),
        )

    def is_available(self) -> bool:
        """Check if Groq service is available."""
        try:
            # Simple test completion
            test_response = self.complete("Hello")
            return self.validate_response(test_response)
        except Exception:
            return False
