"""
Simplified question generator that leverages LLM intelligence for domain analysis.
Creates theoretical first-round interview questions based on CV-JD analysis.
"""

from typing import Dict, List, Optional, Any
from ..llm.base import BaseLLM
from ..utils.llm_response_handler import LLMResponseHandler
from ..prompts.simplified_prompts import (
    FIRST_QUESTION_PROMPT,
    NEXT_QUESTION_PROMPT,
)


class SimplifiedQuestionGenerator:
    """
    Ultra-simplified question generator using intelligent prompts:
    - Generate first question from CV-JD analysis
    - Intelligently decide between follow-up vs new concept questions
    - Analyze interview history to determine optimal question flow
    """

    def __init__(self, llm: BaseLLM):
        self.llm = llm

    def generate_first_question(self, analysis: Dict[str, Any]) -> str:
        """Generate first question using standardized prompt."""
        try:
            prompt = FIRST_QUESTION_PROMPT.format(
                job_role=analysis.get("job_role", "Software Developer"),
                experience_level=analysis.get("experience_level", "mid"),
                key_skills=", ".join(analysis.get("key_skills", [])),
                years_experience=analysis.get("years_experience", ""),
                primary_domain=analysis.get("primary_domain", "technical"),
            )
            response = self.llm.complete(prompt)
            return LLMResponseHandler.extract_clean_text(response)
        except Exception as e:
            raise Exception(f"Failed to generate first question: {str(e)}")

    def generate_next_question(
        self,
        interview_history: str,
        last_answer: str,
        analysis: Dict[str, Any],
        question_number: int,
        max_questions: int,
    ) -> str:
        """Generate next question with intelligent follow-up logic using standardized prompt."""
        try:
            prompt = NEXT_QUESTION_PROMPT.format(
                job_role=analysis.get("job_role", ""),
                interview_history=interview_history[
                    -2000:
                ],  # Keep more context for better analysis
                last_answer=last_answer,
                question_number=question_number,
                max_questions=max_questions,
                experience_level=analysis.get("experience_level", "mid"),
                primary_domain=analysis.get("primary_domain", "technical"),
            )
            response = self.llm.complete(prompt)
            return LLMResponseHandler.extract_clean_text(response)
        except Exception as e:
            raise Exception(f"Failed to generate next question: {str(e)}")
