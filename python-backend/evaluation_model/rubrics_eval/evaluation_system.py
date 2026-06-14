"""Main evaluation system orchestrator."""

from typing import List, Dict, Any, Tuple, Optional
import pandas as pd

from .config import Config
from .rubric_generator import RubricGenerator
from .answer_evaluator import AnswerEvaluator
from .answer_generator import AnswerGenerator
from .data_processor import DataProcessor
from .visualization import VisualizationUtils
from .communication_evaluator import CommunicationEvaluator


class EvaluationSystem:
    """Main class that orchestrates the entire evaluation process."""

    def __init__(self):
        """Initialize the evaluation system.

        Uses API key from config/environment variables.
        """
        # Load configuration
        Config.load_from_environment()
        Config.validate()

        # Initialize components
        self.rubric_generator = RubricGenerator()
        self.answer_evaluator = AnswerEvaluator()
        self.answer_generator = AnswerGenerator()
        self.data_processor = DataProcessor()
        self.visualization = VisualizationUtils()
        self.communication_evaluator = CommunicationEvaluator()

    def evaluate_single_answer(
        self, question: str, student_answer: str, rubrics: Optional[List[str]] = None
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """Evaluate a single answer against a question.

        Args:
            question: The question to evaluate against.
            student_answer: The student's answer.
            rubrics: Pre-generated rubrics. If None, generates new ones.

        Returns:
            Tuple of (average_score, evaluation_details).
        """
        if rubrics is None:
            rubrics = self.rubric_generator.generate_rubrics(question)

        if not rubrics:
            print(f"No rubrics generated for question: {question}")
            return 0.0, []

        return self.answer_evaluator.evaluate_answer(question, student_answer, rubrics)

    def evaluate_communication_score(self, question: str, student_answer: str) -> float:
        """Evaluate communication skills and return a single score.

        Args:
            question: The question to evaluate against.
            student_answer: The student's answer.

        Returns:
            Communication score from 0 to 100.
        """
        return self.communication_evaluator.evaluate_communication_score(
            question, student_answer
        )

    def evaluate_single_answer_fast(
        self, question: str, student_answer: str
    ) -> Tuple[float, List[Dict[str, Any]]]:
        return self.answer_evaluator.evaluate_answer_fast(question, student_answer)

    def generate_answer_spectrum(
        self, question: str, spectrum_type: str = "balanced"
    ) -> Tuple[List[str], List[str]]:
        """Generate a spectrum of answers for testing.

        Args:
            question: The question to generate answers for.
            spectrum_type: Type of spectrum ("balanced" or "relevance").

        Returns:
            Tuple of (titles, generated_answers).
        """
        if spectrum_type == "balanced":
            return self.answer_generator.generate_balanced_spectrum(question)
        elif spectrum_type == "relevance":
            return self.answer_generator.generate_sequential_relevance_spectrum(
                question
            )
        else:
            raise ValueError(f"Unknown spectrum type: {spectrum_type}")

    def evaluate_answer_spectrum(
        self, question: str, spectrum_type: str = "balanced"
    ) -> Dict[str, Any]:
        """Generate and evaluate a spectrum of answers for a question.

        Args:
            question: The question to process.
            spectrum_type: Type of spectrum to generate.

        Returns:
            Dictionary containing all results.
        """
        # Generate rubrics
        rubrics = self.rubric_generator.generate_rubrics(question)
        if not rubrics:
            return {"error": "Failed to generate rubrics", "question": question}

        # Generate answer spectrum
        titles, answers = self.generate_answer_spectrum(question, spectrum_type)
        if not answers:
            return {"error": "Failed to generate answers", "question": question}

        # Evaluate each answer
        evaluation_results = []
        scores = []

        for i, answer in enumerate(answers):
            score, details = self.answer_evaluator.evaluate_answer(
                question, answer, rubrics
            )
            evaluation_results.append(
                {
                    "title": titles[i] if i < len(titles) else f"Answer {i+1}",
                    "answer": answer,
                    "score": score,
                    "details": details,
                }
            )
            scores.append(score)

        return {
            "question": question,
            "rubrics": rubrics,
            "spectrum_type": spectrum_type,
            "results": evaluation_results,
            "scores": scores,
            "average_score": sum(scores) / len(scores) if scores else 0,
        }

    def process_dataset(
        self,
        dataset_path: str,
        question_column: str = "Question",
        spectrum_type: str = "balanced",
    ) -> List[Dict[str, Any]]:
        """Process an entire dataset of questions.

        Args:
            dataset_path: Path to the dataset file.
            question_column: Name of the column containing questions.
            spectrum_type: Type of answer spectrum to generate.

        Returns:
            List of results for each question.
        """
        # Load dataset
        df = self.data_processor.load_dataset(dataset_path)
        if df is None:
            return []

        # Extract questions
        questions = self.data_processor.extract_questions_from_dataframe(
            df, question_column
        )
        if not questions:
            return []

        # Process each question
        all_results = []
        for i, question in enumerate(questions):
            print(f"Processing question {i+1}/{len(questions)}: {question[:50]}...")
            result = self.evaluate_answer_spectrum(question, spectrum_type)
            all_results.append(result)

        return all_results

    def evaluate_test_answers(self, test_data_path: str) -> List[Dict[str, Any]]:
        """Evaluate answers from a test dataset.

        Args:
            test_data_path: Path to the test data JSON file.

        Returns:
            List of evaluation results.
        """
        # Load test data
        test_data = self.data_processor.load_json_data(test_data_path)
        if not test_data:
            return []

        questions_to_evaluate = test_data.get("results", [])
        evaluation_results = []

        for item in questions_to_evaluate:
            question = item.get("question")
            if not question:
                continue

            candidate_answers = item.get("candidate_answers", [])
            if not candidate_answers:
                continue

            # Generate rubrics for this question
            rubrics = self.rubric_generator.generate_rubrics(question)

            question_results = {
                "question": question,
                "rubrics": rubrics,
                "answer_evaluations": [],
            }

            # Evaluate each candidate answer
            for ans_data in candidate_answers:
                answer = ans_data.get("answer", "")
                ans_type = ans_data.get("type", "unknown")

                if answer:
                    score, details = self.answer_evaluator.evaluate_answer(
                        question, answer, rubrics
                    )
                    question_results["answer_evaluations"].append(
                        {
                            "type": ans_type,
                            "answer": answer,
                            "score": score,
                            "details": details,
                        }
                    )

            evaluation_results.append(question_results)

        return evaluation_results

    def save_results_to_csv(
        self,
        results: List[Dict[str, Any]],
        output_path: str,
        include_details: bool = False,
    ) -> bool:
        """Save evaluation results to CSV file.

        Args:
            results: List of evaluation results.
            output_path: Path to save the CSV file.
            include_details: Whether to include detailed rubric scores.

        Returns:
            True if successful, False otherwise.
        """
        try:
            rows = []

            for result in results:
                if "error" in result:
                    continue

                question = result["question"]
                evaluation_results = result.get("results", [])

                row = [question]

                # Add scores for each answer in the spectrum
                for eval_result in evaluation_results:
                    if include_details:
                        row.extend([eval_result["answer"], eval_result["score"]])
                    else:
                        row.append(eval_result["score"])

                rows.append(row)

            # Create column names
            if include_details:
                columns = ["Question"]
                for i in range(6):  # Assuming 6 answers in spectrum
                    columns.extend([f"Answer_{i+1}", f"Score_{i+1}"])
            else:
                columns = ["Question"] + [f"Score_{i+1}" for i in range(6)]

            return self.data_processor.save_to_csv(rows, columns, output_path)

        except Exception as e:
            print(f"Error saving results to CSV: {e}")
            return False

    def generate_visualizations(self, csv_path: str, output_dir: str = ".") -> bool:
        """Generate visualizations from CSV results.

        Args:
            csv_path: Path to the CSV file with results.
            output_dir: Directory to save visualizations.

        Returns:
            True if successful, False otherwise.
        """
        import os

        original_dir = os.getcwd()

        try:
            if output_dir != ".":
                os.chdir(output_dir)

            return self.visualization.plot_scores_from_csv(csv_path)

        finally:
            os.chdir(original_dir)
