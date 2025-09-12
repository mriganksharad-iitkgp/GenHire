"""
Interview Module

A comprehensive interview management system with support for:
- Multiple LLM providers
- Document processing and analysis
- Question generation
- Interview session management
- Evaluation and scoring
"""

from .api import (
    InterviewAPI,
    create_groq_interview,
    create_openai_interview,
)
from .core.session_manager import InterviewSessionManager
from .core.question_generator import QuestionGenerator
from .llm.factory import LLMFactory
from .document.processor import DocumentProcessor
from .evaluation.scorer import EvaluationScorer
from .config.settings import InterviewConfig, LLMConfig, LLMProvider, QuestionType

__version__ = "1.0.0"
__all__ = [
    # High-level API
    "InterviewAPI",
    "create_groq_interview",
    "create_openai_interview",
    # Core components
    "InterviewSessionManager",
    "QuestionGenerator",
    "LLMFactory",
    "DocumentProcessor",
    "EvaluationScorer",
    # Configuration
    "InterviewConfig",
    "LLMConfig",
    "LLMProvider",
    "QuestionType",
]
