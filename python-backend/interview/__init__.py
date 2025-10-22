"""
Simplified Interview Module

A streamlined interview system focused on:
- CV and JD based question generation
- Natural conversation flow with minimal acknowledgments
- Modern technical interview questions
- Simple session management
"""

from .simple_interview import SimpleInterviewSystem, InterviewSessionManager
from .core.simplified_session_manager import SimplifiedInterviewSessionManager
from .core.simplified_question_generator import SimplifiedQuestionGenerator
from .config.settings import InterviewConfig, LLMConfig, LLMProvider, QuestionType

__version__ = "1.0.0"
__all__ = [
    # High-level API
    "InterviewAPI",
    "create_groq_interview",
    "create_openai_interview",
    # Core components
    "InterviewSessionManager",
    "PromptBasedQuestionGenerator",
    "LLMFactory",
    "DocumentProcessor",
    # Configuration
    "InterviewConfig",
    "LLMConfig",
    "LLMProvider",
    "QuestionType",
]
