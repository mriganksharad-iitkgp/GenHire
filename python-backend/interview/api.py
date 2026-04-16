"""
High-level API for the interview system.

This module provides a simplified interface for using the interview system.
"""

from typing import Dict, List, Any, Optional
from pathlib import Path

from .config.settings import (
    InterviewConfig,
    LLMConfig,
    LLMProvider,
    DocumentConfig,
    EvaluationConfig,
)
from .core.session_manager import InterviewSessionManager


class InterviewAPI:
    """High-level API for the interview system."""

    def __init__(
        self,
        llm_provider: LLMProvider = LLMProvider.GROQ,
        model_name: str = "llama-3.3-70b-versatile",
        api_key: str = None,
        **config_overrides,
    ):
        """
        Initialize the Interview API.

        Args:
            llm_provider: The LLM provider to use
            model_name: The model name for the provider
            api_key: API key for the LLM provider
            **config_overrides: Override default configuration values
        """

        if not api_key:
            raise ValueError("API key is required")

        # Create configurations
        self.interview_config = InterviewConfig(**config_overrides)
        self.llm_config = LLMConfig(
            provider=llm_provider, model_name=model_name, api_key=api_key
        )

        # Initialize session manager
        self.session_manager = InterviewSessionManager(
            config=self.interview_config, llm_config=self.llm_config
        )

    def start_interview(
        self,
        cv_file_path: str,
        job_description_path: str,
        reference_documents: List[str] = None,
        proctoring_config: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Start a new interview session.

        Args:
            cv_file_path: Path to the candidate's CV (PDF format)
            job_description_path: Path to the job description (PDF format)
            reference_documents: List of paths to reference documents

        Returns:
            Dictionary containing session_id and initial questions
        """

        # Validate file paths
        if not Path(cv_file_path).exists():
            return {"error": f"CV file not found: {cv_file_path}"}

        if not Path(job_description_path).exists():
            return {"error": f"Job description file not found: {job_description_path}"}

        if reference_documents is None:
            reference_documents = []

        # Validate reference documents
        for ref_path in reference_documents:
            if not Path(ref_path).exists():
                return {"error": f"Reference document not found: {ref_path}"}

        return self.session_manager.create_session(
            cv_path=cv_file_path,
            jd_path=job_description_path,
            reference_paths=reference_documents,
            proctoring_config=proctoring_config,
        )

    def get_question(self, session_id: str) -> Dict[str, Any]:
        """
        Get the next question for the interview.

        Args:
            session_id: The interview session ID

        Returns:
            Dictionary containing the next question
        """
        return self.session_manager.get_next_question(session_id)

    def submit_answer(
        self, session_id: str, question: str, answer: str
    ) -> Dict[str, Any]:
        """
        Submit an answer and get feedback/next question.

        Args:
            session_id: The interview session ID
            question: The question that was answered
            answer: The candidate's answer

        Returns:
            Dictionary containing evaluation and next steps
        """
        return self.session_manager.submit_answer(session_id, question, answer)

    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """
        Get the current status of an interview session.

        Args:
            session_id: The interview session ID

        Returns:
            Dictionary containing session status information
        """
        return self.session_manager.get_session_status(session_id)

    def end_interview(self, session_id: str) -> Dict[str, Any]:
        """
        End an interview session and get final evaluation.

        Args:
            session_id: The interview session ID

        Returns:
            Dictionary containing final evaluation
        """
        return self.session_manager.end_session(session_id)

    def conduct_full_interview(
        self,
        cv_file_path: str,
        job_description_path: str,
        reference_documents: List[str] = None,
        max_questions: int = None,
        proctoring_config: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Conduct a complete simulated interview (for testing/demo purposes).

        Args:
            cv_file_path: Path to the candidate's CV
            job_description_path: Path to the job description
            reference_documents: List of reference document paths
            max_questions: Maximum number of questions to ask

        Returns:
            Complete interview results
        """

        # Start interview
        session_result = self.start_interview(
            cv_file_path, job_description_path, reference_documents, proctoring_config
        )

        if "error" in session_result:
            return session_result

        session_id = session_result["session_id"]

        interview_results = {
            "session_info": session_result,
            "qa_pairs": [],
            "final_evaluation": None,
        }

        question_count = 0
        max_questions = max_questions or 5  # Default to 5 questions

        # Simulate the interview
        while question_count < max_questions:
            # Get current question
            question_result = self.get_question(session_id)

            if "error" in question_result:
                break

            if question_result.get("interview_complete", False):
                if "final_evaluation" in question_result:
                    interview_results["final_evaluation"] = question_result[
                        "final_evaluation"
                    ]
                break

            question = question_result.get("question", "")
            if not question:
                break

            # Generate a sample answer for demo purposes
            sample_answer = (
                f"This is a sample answer to question {question_count + 1}: {question}"
            )

            answer_result = self.submit_answer(session_id, question, sample_answer)

            interview_results["qa_pairs"].append(
                {
                    "question": question,
                    "answer": sample_answer,
                    "evaluation": answer_result.get("current_evaluation"),
                }
            )

            if answer_result.get("interview_complete"):
                interview_results["final_evaluation"] = answer_result.get(
                    "final_evaluation"
                )
                break

            question_count += 1

        return interview_results


# Convenience functions for quick setup
def create_groq_interview(api_key: str, **config) -> InterviewAPI:
    """Create an interview API instance using Groq."""
    return InterviewAPI(
        llm_provider=LLMProvider.GROQ,
        model_name="llama-3.3-70b-versatile",
        api_key=api_key,
        **config,
    )


def create_openai_interview(api_key: str, model: str, **config) -> InterviewAPI:
    """Create an interview API instance using OpenAI."""
    return InterviewAPI(
        llm_provider=LLMProvider.OPENAI, model_name=model, api_key=api_key, **config
    )
