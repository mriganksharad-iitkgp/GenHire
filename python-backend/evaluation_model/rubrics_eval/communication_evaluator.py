"""Simple communication skill evaluator for interview responses."""

from typing import Optional
from langchain_openai import ChatOpenAI
from .config import Config


class CommunicationEvaluator:
    """Simple evaluator for communication skills in candidate responses."""

    def __init__(self):
        """Initialize the communication evaluator."""
        # Ensure config is loaded
        Config.load_from_environment()
        self.llm = ChatOpenAI(
            model=Config.EVALUATION_MODEL,
            api_key=Config.OPENAI_API_KEY,
            temperature=Config.EVALUATION_TEMPERATURE,
        )

    def evaluate_communication_score(self, question: str, answer: str) -> float:
        """Evaluate communication skills and return a single score (0-100).

        Args:
            question: The interview question asked
            answer: The candidate's response

        Returns:
            Communication score from 0 to 100
        """
        if not answer or not answer.strip():
            return 5.0  # Very low score for empty responses

        prompt = f"""
        You are an expert communication skills assessor evaluating a candidate's response in a technical interview.
        
        **Question Asked:**
        {question}
        
        **Candidate's Response:**
        "{answer}"
        
        Evaluate the communication effectiveness of this response on a scale of 0-100, considering:
        
        1. **Clarity & Coherence**: How clear and easy to follow is the response?
        2. **Structure & Organization**: Is the answer well-organized with logical flow?
        3. **Completeness**: Does the response adequately address the question?
        4. **Professional Expression**: Professional tone, grammar, and language usage?
        5. **Technical Communication**: Appropriate use of technical terms when relevant?
        
        **Scoring Guidelines:**
        - 90-100: Exceptional communication - very clear, well-structured, professional, complete
        - 80-89: Strong communication - mostly clear with good structure
        - 70-79: Good communication - generally clear but may lack some structure
        - 60-69: Adequate communication - understandable but with some issues
        - 50-59: Weak communication - unclear or poorly structured
        - 0-49: Poor communication - very difficult to understand or severely lacking
        
        Consider the length and depth appropriate for the question asked.
        
        Respond with only the integer score (0-100) and nothing else.
        """

        try:
            response = self.llm.invoke(prompt)
            score = float(response.content.strip())
            return max(0.0, min(100.0, score))  # Ensure score is within bounds
        except (ValueError, AttributeError) as e:
            print(f"Warning: Could not parse communication score: {e}. Using fallback.")
            return self._fallback_communication_score(answer)
        except Exception as e:
            print(f"Error evaluating communication: {e}")
            return self._fallback_communication_score(answer)

    def _fallback_communication_score(self, answer: str) -> float:
        """Provide a basic fallback communication score based on response characteristics."""

        if not answer or not answer.strip():
            return 5.0

        answer = answer.strip()
        word_count = len(answer.split())

        # Basic scoring based on response characteristics
        base_score = 50.0  # Start with average

        # Length scoring
        if word_count < 5:
            base_score = 25.0  # Very short response
        elif word_count < 15:
            base_score = 40.0  # Short response
        elif word_count < 50:
            base_score = 65.0  # Medium response
        elif word_count < 150:
            base_score = 75.0  # Good length
        else:
            base_score = 70.0  # Very long (might be verbose)

        # Basic structure checks
        if answer.count(".") > 0:  # Has sentences
            base_score += 5.0

        if answer.count(",") > 0:  # Has some structure
            base_score += 5.0

        # Check for technical terms (basic heuristic)
        technical_indicators = [
            "function",
            "method",
            "class",
            "variable",
            "algorithm",
            "data",
            "system",
            "process",
        ]
        if any(term in answer.lower() for term in technical_indicators):
            base_score += 5.0

        return min(85.0, base_score)  # Cap fallback score at 85
