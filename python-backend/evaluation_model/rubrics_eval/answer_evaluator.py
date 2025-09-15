"""Answer evaluation module."""

from typing import List, Dict, Any, Tuple
from langchain_openai import ChatOpenAI
from .config import Config


class AnswerEvaluator:
    """Handles the evaluation of student answers against rubrics."""

    def __init__(self):
        """Initialize the answer evaluator.

        Uses API key from config/environment variables.
        """
        # Ensure config is loaded
        Config.load_from_environment()
        self.llm = ChatOpenAI(
            model=Config.EVALUATION_MODEL,
            api_key=Config.OPENAI_API_KEY,
            temperature=Config.EVALUATION_TEMPERATURE,
        )

    def evaluate_single_rubric(
        self, student_answer: str, question: str, rubric_item: str
    ) -> float:
        """Evaluate a student answer against a single rubric item.

        Args:
            student_answer: The student's answer to evaluate.
            question: The original question.
            rubric_item: The specific rubric criterion to evaluate against.

        Returns:
            Score from 1 to 100.
        """
        prompt = self._create_evaluation_prompt(student_answer, question, rubric_item)

        try:
            response = self.llm.invoke(prompt)
            result = response.content.strip()
            return float(result)
        except ValueError:
            print(
                f"Warning: Could not parse score from model response: '{result}'. Defaulting to 0."
            )
            return 0.0
        except Exception as e:
            print(f"An error occurred while evaluating rubric: {e}")
            return 0.0

    def evaluate_answer(
        self, question: str, student_answer: str, rubrics: List[str]
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """Evaluate a student answer against all rubrics.

        Args:
            question: The original question.
            student_answer: The student's answer to evaluate.
            rubrics: List of rubric criteria.

        Returns:
            Tuple of (average_score, evaluation_details).
        """
        if not rubrics:
            return 0.0, []

        rubric_scores = []
        evaluation_details = []

        for rubric in rubrics:
            score = self.evaluate_single_rubric(student_answer, question, rubric)
            rubric_scores.append(score)
            evaluation_details.append({"rubric": rubric, "score": score})

        final_average_score = sum(rubric_scores) / len(rubric_scores)
        return final_average_score, evaluation_details

    def _create_evaluation_prompt(
        self, student_answer: str, question: str, rubric_item: str
    ) -> str:
        """Create the prompt for evaluating a single rubric.

        Args:
            student_answer: The student's answer.
            question: The original question.
            rubric_item: The rubric criterion.

        Returns:
            The formatted prompt string.
        """
        return f"""
        You are an expert and strict teaching assistant. Your task is to evaluate a student's answer against a specific criterion from a grading rubric.

        **Question:**
        {question}

        **Student's Answer:**
        "{student_answer}"

        **Grading Criterion:**
        "{rubric_item}"

        Based on the factual correctness and completeness of the student's answer concerning the grading criterion, provide a score from 1 to 100.
        - A score of 100 means the criterion is fully and correctly addressed.
        - A score of 1 means the criterion is not addressed at all or is completely incorrect.

        Respond with only the integer score and nothing else.
        """

    def evaluate_multiple_answers(
        self, question: str, answers: List[str], rubrics: List[str]
    ) -> List[Tuple[float, List[Dict[str, Any]]]]:
        """Evaluate multiple answers for the same question.

        Args:
            question: The original question.
            answers: List of student answers to evaluate.
            rubrics: List of rubric criteria.

        Returns:
            List of evaluation results, one for each answer.
        """
        results = []
        for answer in answers:
            result = self.evaluate_answer(question, answer, rubrics)
            results.append(result)
        return results
