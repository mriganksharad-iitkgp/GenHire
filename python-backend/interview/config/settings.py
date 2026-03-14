"""
Configuration settings for the interview module.
"""

from dataclasses import dataclass
import os
from typing import Dict, List, Optional
from enum import Enum
from dotenv import load_dotenv

load_dotenv()


class LLMProvider(Enum):
    """Supported LLM providers."""

    GROQ = "groq"
    OPENAI = "openai"
    GEMINI = "gemini"


class QuestionType(Enum):
    """Types of interview questions."""

    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    SITUATIONAL = "situational"
    EXPERIENCE = "experience"
    DEFINITION = "definition"
    STRUCTURE_EXPLANATION = "structure_explanation"
    EXPERIENTIAL = "experiential"


@dataclass
class InterviewConfig:
    """Configuration for interview sessions."""

    max_questions: int = 20
    min_questions: int = 8
    question_timeout_seconds: int = 300
    similarity_threshold: float = 0.7
    default_llm_provider: LLMProvider = LLMProvider.OPENAI
    default_model: str = os.getenv("INTERVIEW_LLM_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    embedding_model: str = "all-MiniLM-L6-v2"
    
    # Structure explanation phase settings
    include_structure_explanation: bool = False  # Disabled - goes directly to questions
    structure_explanation_timeout_seconds: int = 120

    # Experiential questions phase settings
    include_experiential_questions: bool = True
    experiential_questions_limit: int = 2  # Limit CV-based questions to 2


@dataclass
class LLMConfig:
    """Configuration for LLM providers."""

    provider: LLMProvider = LLMProvider.OPENAI
    model_name: str = os.getenv("INTERVIEW_LLM_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    api_key: str = os.getenv("OPENAI_API_KEY", "")
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    timeout_seconds: int = 30


@dataclass
class DocumentConfig:
    """Configuration for document processing."""

    max_file_size_mb: int = 10
    supported_formats: Optional[List[str]] = None
    chunk_size: int = 512
    overlap_size: int = 50

    def __post_init__(self):
        if self.supported_formats is None:
            self.supported_formats = [".pdf", ".txt", ".docx"]


@dataclass
class EvaluationConfig:
    """Configuration for evaluation scoring."""

    relevance_weight: float = 0.4
    technical_accuracy_weight: float = 0.4
    communication_weight: float = 0.2
    min_answer_length: int = 10
    max_answer_length: int = 1000
