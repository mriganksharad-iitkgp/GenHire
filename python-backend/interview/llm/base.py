"""
Base LLM interface and common functionality.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from llama_index.core.llms.llm import LLM as LlamaIndexLLM
    from llama_index.core.base.llms.types import CompletionResponse

try:
    from llama_index.core.llms.llm import LLM as LlamaIndexLLM
    from llama_index.core.base.llms.types import CompletionResponse

    LLAMA_INDEX_AVAILABLE = True
except ImportError:
    LLAMA_INDEX_AVAILABLE = False
    LlamaIndexLLM = object
    CompletionResponse = object


@dataclass
class LLMResponse:
    """Response from an LLM completion."""

    text: str
    usage: Optional[Dict[str, int]] = None
    model: Optional[str] = None
    finish_reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_llama_index(cls, response: Any, model_name: str = None) -> "LLMResponse":
        """Create LLMResponse from llama_index CompletionResponse."""
        usage = None
        # Try to extract usage from raw response or additional_kwargs
        if hasattr(response, "raw") and hasattr(response.raw, "usage"):
            # OpenAI raw response
            try:
                usage = {
                    "prompt_tokens": response.raw.usage.prompt_tokens,
                    "completion_tokens": response.raw.usage.completion_tokens,
                    "total_tokens": response.raw.usage.total_tokens,
                }
            except AttributeError:
                pass
        
        if usage is None and hasattr(response, "additional_kwargs"):
            # Some providers put it here
            usage = response.additional_kwargs.get("usage") or response.additional_kwargs.get("token_usage")

        return cls(
            text=response.text,
            model=model_name,
            finish_reason="completed",
            metadata=getattr(response, "additional_kwargs", {}),
            usage=usage
        )


class BaseLLM(ABC):
    """Base class for all LLM providers using llama_index."""

    def __init__(self, model_name: str, api_key: str, **kwargs):
        self.model_name = model_name
        self.api_key = api_key
        self.config = kwargs
        self._llama_index_llm = None

    @abstractmethod
    def _create_llama_index_llm(self) -> Any:
        """Create the llama_index LLM instance."""
        pass

    @property
    def llama_index_llm(self) -> Any:
        """Get or create the llama_index LLM instance."""
        if self._llama_index_llm is None:
            self._llama_index_llm = self._create_llama_index_llm()
        return self._llama_index_llm

    def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate a completion for the given prompt."""
        try:
            llm = self.llama_index_llm
            response = llm.complete(prompt)
            return LLMResponse.from_llama_index(response, self.model_name)
        except Exception as e:
            raise RuntimeError(f"LLM completion failed: {str(e)}")

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the LLM service is available."""
        pass

    def validate_response(self, response: LLMResponse) -> bool:
        """Validate the LLM response."""
        return response.text is not None and len(response.text.strip()) > 0
