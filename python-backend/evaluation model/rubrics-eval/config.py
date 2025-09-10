"""Configuration module for the rubrics evaluation system."""

import os
from typing import Optional


class Config:
    """Configuration class for the evaluation system."""

    # OpenAI Configuration
    OPENAI_API_KEY: Optional[str] = None
    RUBRIC_GENERATION_MODEL: str = "gpt-4o"
    EVALUATION_MODEL: str = "gpt-4o-mini"
    ANSWER_GENERATION_MODEL: str = "gpt-4o"

    # Temperature settings
    RUBRIC_GENERATION_TEMPERATURE: float = 0.0
    EVALUATION_TEMPERATURE: float = 0.0
    ANSWER_GENERATION_TEMPERATURE: float = 0.7

    # LangChain Configuration
    LANGCHAIN_TRACING_V2: str = "true"
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: Optional[str] = None

    # Default file paths (can be overridden)
    DEFAULT_DATASET_PATH: str = "datasets/ml_dataset.txt"
    DEFAULT_TEST_ANSWERS_PATH: str = "datasets/test_answers.json"

    @classmethod
    def load_from_environment(cls) -> None:
        """Load configuration from environment variables."""
        cls.OPENAI_API_KEY = cls._get_api_key()
        cls.LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")

        # Set environment variables for LangChain
        if cls.LANGCHAIN_TRACING_V2:
            os.environ["LANGCHAIN_TRACING_V2"] = cls.LANGCHAIN_TRACING_V2
        if cls.LANGCHAIN_ENDPOINT:
            os.environ["LANGCHAIN_ENDPOINT"] = cls.LANGCHAIN_ENDPOINT
        if cls.LANGCHAIN_API_KEY:
            os.environ["LANGCHAIN_API_KEY"] = cls.LANGCHAIN_API_KEY
        if cls.OPENAI_API_KEY:
            os.environ["OPENAI_API_KEY"] = cls.OPENAI_API_KEY

    @staticmethod
    def _get_api_key() -> str:
        """Get OpenAI API key from environment variables."""
        # Get API key from environment variables only
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError(
                "Error: OPENAI_API_KEY not found. "
                "Please set it in Colab Secrets or as an environment variable."
            )

        return api_key

    @classmethod
    def validate(cls) -> None:
        """Validate the configuration."""
        if not cls.OPENAI_API_KEY:
            raise ValueError("OpenAI API key is required")
