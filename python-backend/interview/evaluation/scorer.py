"""
Evaluation and scoring system for interview responses.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity

    EMBEDDING_AVAILABLE = True
except ImportError:
    EMBEDDING_AVAILABLE = False

from ..llm.base import BaseLLM


@dataclass
class EvaluationResult:
    """Result of an evaluation."""

    relevance_score: float
    technical_accuracy_score: float
    communication_score: float
    overall_score: float
    feedback: str
    strengths: List[str]
    improvements: List[str]


class EvaluationScorer:
    """Handles evaluation and scoring of interview responses."""

    def __init__(self, llm: BaseLLM, embedding_model: str = "all-MiniLM-L6-v2"):
        self.llm = llm
        self.embedding_model_name = embedding_model

        if EMBEDDING_AVAILABLE:
            self.embedding_model = SentenceTransformer(embedding_model)
        else:
            print(
                "Warning: sentence-transformers not available. Some features may be limited."
            )
            self.embedding_model = None

    def calculate_relevance_score(
        self, user_answer: str, expected_answer: str
    ) -> float:
        """Calculate relevance score using cosine similarity."""
        if not EMBEDDING_AVAILABLE or not self.embedding_model:
            # Fallback to simple text matching
            return self._simple_text_similarity(user_answer, expected_answer)

        try:
            user_embedding = self.embedding_model.encode([user_answer])
            expected_embedding = self.embedding_model.encode([expected_answer])

            similarity = cosine_similarity(user_embedding, expected_embedding)[0][0]
            return float(max(0.0, min(1.0, similarity)))

        except Exception as e:
            print(f"Error calculating relevance score: {e}")
            return self._simple_text_similarity(user_answer, expected_answer)

    def calculate_technical_accuracy(
        self, question: str, answer: str, context: str
    ) -> float:
        """Evaluate technical accuracy of the answer."""
        prompt = f"""
        Evaluate the technical accuracy of this answer on a scale of 0.0 to 1.0.
        
        Question: {question}
        
        Answer: {answer}
        
        Context/Reference: {context}
        
        Rate the technical accuracy considering:
        - Correctness of facts and concepts
        - Proper use of technical terminology
        - Completeness of the explanation
        
        Return only a decimal number between 0.0 and 1.0.
        """

        try:
            response = self.llm.complete(prompt)
            score_text = response.text.strip()

            # Extract numeric score
            import re

            match = re.search(r"(\d+\.?\d*)", score_text)
            if match:
                score = float(match.group(1))
                return max(0.0, min(1.0, score))

            return 0.5  # Default if parsing fails

        except Exception as e:
            print(f"Error calculating technical accuracy: {e}")
            return 0.5

    def calculate_communication_score(self, answer: str) -> float:
        """Evaluate communication quality of the answer."""
        if not answer or len(answer.strip()) < 10:
            return 0.0

        prompt = f"""
        Evaluate the communication quality of this answer on a scale of 0.0 to 1.0.
        
        Answer: {answer}
        
        Rate the communication considering:
        - Clarity and coherence
        - Structure and organization
        - Grammar and language use
        - Conciseness vs completeness
        
        Return only a decimal number between 0.0 and 1.0.
        """

        try:
            response = self.llm.complete(prompt)
            score_text = response.text.strip()

            # Extract numeric score
            import re

            match = re.search(r"(\d+\.?\d*)", score_text)
            if match:
                score = float(match.group(1))
                return max(0.0, min(1.0, score))

            return 0.5  # Default if parsing fails

        except Exception as e:
            print(f"Error calculating communication score: {e}")
            return 0.5

    def generate_feedback(
        self, question: str, answer: str, scores: Dict[str, float]
    ) -> Tuple[str, List[str], List[str]]:
        """Generate qualitative feedback for the answer."""
        prompt = f"""
        Provide constructive feedback for this interview answer.
        
        Question: {question}
        Answer: {answer}
        
        Scores:
        - Relevance: {scores.get('relevance', 0):.2f}
        - Technical Accuracy: {scores.get('technical_accuracy', 0):.2f} 
        - Communication: {scores.get('communication', 0):.2f}
        
        Provide:
        1. Overall feedback (2-3 sentences)
        2. Key strengths (list 2-3 points)
        3. Areas for improvement (list 2-3 points)
        
        Format your response as:
        FEEDBACK: [overall feedback]
        STRENGTHS: [strength1] | [strength2] | [strength3]
        IMPROVEMENTS: [improvement1] | [improvement2] | [improvement3]
        """

        try:
            response = self.llm.complete(prompt)
            text = response.text.strip()

            # Parse response
            feedback = ""
            strengths = []
            improvements = []

            lines = text.split("\n")
            for line in lines:
                if line.startswith("FEEDBACK:"):
                    feedback = line.replace("FEEDBACK:", "").strip()
                elif line.startswith("STRENGTHS:"):
                    strengths_text = line.replace("STRENGTHS:", "").strip()
                    strengths = [
                        s.strip() for s in strengths_text.split("|") if s.strip()
                    ]
                elif line.startswith("IMPROVEMENTS:"):
                    improvements_text = line.replace("IMPROVEMENTS:", "").strip()
                    improvements = [
                        i.strip() for i in improvements_text.split("|") if i.strip()
                    ]

            return feedback, strengths, improvements

        except Exception as e:
            print(f"Error generating feedback: {e}")
            return "Unable to generate feedback at this time.", [], []

    def evaluate_answer(
        self,
        question: str,
        user_answer: str,
        expected_answer: str,
        context: str = "",
        weights: Dict[str, float] = None,
    ) -> EvaluationResult:
        """Complete evaluation of an interview answer."""

        if weights is None:
            weights = {
                "relevance": 0.4,
                "technical_accuracy": 0.4,
                "communication": 0.2,
            }

        # Calculate individual scores
        relevance_score = self.calculate_relevance_score(user_answer, expected_answer)
        technical_accuracy_score = self.calculate_technical_accuracy(
            question, user_answer, context
        )
        communication_score = self.calculate_communication_score(user_answer)

        # Calculate weighted overall score
        overall_score = (
            relevance_score * weights["relevance"]
            + technical_accuracy_score * weights["technical_accuracy"]
            + communication_score * weights["communication"]
        )

        # Generate feedback
        scores = {
            "relevance": relevance_score,
            "technical_accuracy": technical_accuracy_score,
            "communication": communication_score,
        }

        feedback, strengths, improvements = self.generate_feedback(
            question, user_answer, scores
        )

        return EvaluationResult(
            relevance_score=relevance_score,
            technical_accuracy_score=technical_accuracy_score,
            communication_score=communication_score,
            overall_score=overall_score,
            feedback=feedback,
            strengths=strengths,
            improvements=improvements,
        )

    def _simple_text_similarity(self, text1: str, text2: str) -> float:
        """Simple text similarity fallback when embeddings aren't available."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0
