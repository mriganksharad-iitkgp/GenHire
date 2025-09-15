#!/usr/bin/env python3
"""
Rubrics Evaluation System - Legacy Interface

This file maintains backward compatibility with the original monolithic implementation
while using the new modular architecture underneath.

For new projects, use the modular components directly:
- from evaluation_system import EvaluationSystem
- from rubric_generator import RubricGenerator
- etc.
"""

import os
import sys
import warnings
from typing import List, Dict, Any, Tuple, Optional

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from config import Config
    from evaluation_system import EvaluationSystem
    from rubric_generator import RubricGenerator
    from answer_evaluator import AnswerEvaluator
    from answer_generator import AnswerGenerator
    from data_processor import DataProcessor
    from visualization import VisualizationUtils
except ImportError as e:
    print(f"Import error: {e}")
    print("Please install required dependencies: pip install -r requirements.txt")
    sys.exit(1)

# Initialize global system components for backward compatibility
_eval_system = None


def _get_eval_system():
    """Get or create the global evaluation system instance."""
    global _eval_system
    if _eval_system is None:
        try:
            Config.load_from_environment()
            _eval_system = EvaluationSystem()
        except Exception as e:
            raise ValueError(f"Failed to initialize evaluation system: {e}")
    return _eval_system


# Legacy function interfaces for backward compatibility
def generate_rubrics_for_question(question: str) -> List[str]:
    """Legacy function: Generate rubrics for a question."""
    warnings.warn(
        "generate_rubrics_for_question is deprecated. Use RubricGenerator.generate_rubrics() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _get_eval_system().rubric_generator.generate_rubrics(question)


def evaluate_rubric_score(
    student_answer: str, question: str, rubric_item: str
) -> float:
    """Legacy function: Evaluate a single rubric item."""
    warnings.warn(
        "evaluate_rubric_score is deprecated. Use AnswerEvaluator.evaluate_single_rubric() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _get_eval_system().answer_evaluator.evaluate_single_rubric(
        student_answer, question, rubric_item
    )


def generate_and_evaluate_answer(
    question: str, student_answer: str, rubrics: Optional[List[str]] = None
) -> Tuple[float, List[Dict[str, Any]]]:
    """Legacy function: Generate and evaluate answer."""
    warnings.warn(
        "generate_and_evaluate_answer is deprecated. Use EvaluationSystem.evaluate_single_answer() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _get_eval_system().evaluate_single_answer(question, student_answer, rubrics)


def generate_balanced_spectrum(question: str) -> Tuple[List[str], List[str]]:
    """Legacy function: Generate balanced answer spectrum."""
    warnings.warn(
        "generate_balanced_spectrum is deprecated. Use AnswerGenerator.generate_balanced_spectrum() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _get_eval_system().answer_generator.generate_balanced_spectrum(question)


def generate_sequential_relevance_spectrum(
    question: str,
) -> Tuple[List[str], List[str]]:
    """Legacy function: Generate sequential relevance spectrum."""
    warnings.warn(
        "generate_sequential_relevance_spectrum is deprecated. Use AnswerGenerator.generate_sequential_relevance_spectrum() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _get_eval_system().answer_generator.generate_sequential_relevance_spectrum(
        question
    )


def plot_scores_from_csv(file_path: str) -> bool:
    """Legacy function: Plot scores from CSV."""
    warnings.warn(
        "plot_scores_from_csv is deprecated. Use VisualizationUtils.plot_scores_from_csv() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return VisualizationUtils.plot_scores_from_csv(file_path)


def main():
    """Main function demonstrating the refactored system."""
    print("🔄 Running Legacy Interface (Refactored Backend)")
    print("=" * 60)

    try:
        # Test basic functionality
        question = (
            "What is the difference between supervised and unsupervised learning?"
        )
        print(f"Testing with question: {question}")

        # Generate rubrics
        rubrics = generate_rubrics_for_question(question)
        print(f"Generated {len(rubrics)} rubrics:")
        for i, rubric in enumerate(rubrics, 1):
            print(f"  {i}. {rubric}")

        # Test answer evaluation
        student_answer = "Supervised learning uses labeled data, unsupervised learning finds patterns in unlabeled data."
        score, details = generate_and_evaluate_answer(question, student_answer, rubrics)

        print(f"\nEvaluation Result:")
        print(f"Overall Score: {score:.2f}")
        print("Rubric Details:")
        for detail in details:
            print(f"  - {detail['rubric']}: {detail['score']:.1f}")

        print("\n✅ Legacy interface working with refactored backend!")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
