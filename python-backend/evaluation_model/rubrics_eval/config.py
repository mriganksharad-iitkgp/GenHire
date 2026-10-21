"""Configuration module for the rubrics evaluation system."""

import os
from typing import Optional
from config.env_loader import load_environment

load_environment()

class Config:
    """Configuration class for the evaluation system."""

    # Optional legacy key; evaluation uses the configured provider chain.
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    RUBRIC_GENERATION_MODEL: str = os.getenv("LLM_DEEPSEEK_MODEL", "deepseek-flash")
    EVALUATION_MODEL: str = os.getenv("LLM_DEEPSEEK_MODEL", "deepseek-flash")
    ANSWER_GENERATION_MODEL: str = os.getenv("LLM_DEEPSEEK_MODEL", "deepseek-flash")

    # Temperature settings
    RUBRIC_GENERATION_TEMPERATURE: float = 1.0
    EVALUATION_TEMPERATURE: float = 1.0
    ANSWER_GENERATION_TEMPERATURE: float = 0.7

    # LangChain Configuration
    LANGCHAIN_TRACING_V2: str = os.getenv("LANGCHAIN_TRACING_V2", "false")
    LANGCHAIN_ENDPOINT: str = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
    LANGCHAIN_API_KEY: Optional[str] = None

    # Default file paths (can be overridden)
    DEFAULT_DATASET_PATH: str = "datasets/ml_dataset.txt"
    DEFAULT_TEST_ANSWERS_PATH: str = "datasets/test_answers.json"

    @classmethod
    def load_from_environment(cls) -> None:
        """Load configuration from environment variables."""

        cls.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        cls.LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")
        cls.LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "false")
        cls.LANGCHAIN_ENDPOINT = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")

        # Set environment variables for LangChain
        if cls.LANGCHAIN_TRACING_V2:
            os.environ["LANGCHAIN_TRACING_V2"] = cls.LANGCHAIN_TRACING_V2
        if cls.LANGCHAIN_ENDPOINT:
            os.environ["LANGCHAIN_ENDPOINT"] = cls.LANGCHAIN_ENDPOINT
        if cls.LANGCHAIN_API_KEY:
            os.environ["LANGCHAIN_API_KEY"] = cls.LANGCHAIN_API_KEY
        if cls.OPENAI_API_KEY:
            os.environ["OPENAI_API_KEY"] = cls.OPENAI_API_KEY

    @classmethod
    def validate(cls) -> None:
        """Validate the configuration."""
        from services.llm_fallback_service import PROVIDER_SPECS, get_provider_priority
        if not any(os.getenv(PROVIDER_SPECS[p]["key_env"]) for p in get_provider_priority()):
            raise ValueError("Configure DEEPSEEK_API_KEY, GOOGLE_API_KEY or GROQ_API_KEY")
