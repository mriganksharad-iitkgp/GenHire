"""Data processing utilities."""

import json
import pandas as pd
from typing import List, Dict, Any, Optional
import os


class DataProcessor:
    """Handles data loading and processing operations."""

    @staticmethod
    def load_dataset(file_path: str) -> Optional[pd.DataFrame]:
        """Load dataset from file.

        Args:
            file_path: Path to the dataset file.

        Returns:
            DataFrame or None if loading fails.
        """
        try:
            if file_path.endswith(".csv"):
                return pd.read_csv(file_path)
            elif file_path.endswith(".txt"):
                return pd.read_csv(file_path)  # Assuming it's CSV format
            else:
                raise ValueError(f"Unsupported file format: {file_path}")
        except Exception as e:
            print(f"Error loading dataset from {file_path}: {e}")
            return None

    @staticmethod
    def load_json_data(file_path: str) -> Optional[Dict[str, Any]]:
        """Load JSON data from file.

        Args:
            file_path: Path to the JSON file.

        Returns:
            Dictionary or None if loading fails.
        """
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading JSON data from {file_path}: {e}")
            return None

    @staticmethod
    def save_to_csv(data: List[List[Any]], columns: List[str], file_path: str) -> bool:
        """Save data to CSV file.

        Args:
            data: List of rows to save.
            columns: Column names.
            file_path: Path to save the file.

        Returns:
            True if successful, False otherwise.
        """
        try:
            df = pd.DataFrame(data, columns=columns)
            df.to_csv(file_path, index=False)
            return True
        except Exception as e:
            print(f"Error saving data to {file_path}: {e}")
            return False

    @staticmethod
    def extract_questions_from_dataframe(
        df: pd.DataFrame, column_name: str = "Question"
    ) -> List[str]:
        """Extract questions from a DataFrame.

        Args:
            df: DataFrame containing questions.
            column_name: Name of the column containing questions.

        Returns:
            List of questions.
        """
        try:
            return df[column_name].tolist()
        except KeyError:
            print(f"Column '{column_name}' not found in DataFrame")
            return []

    @staticmethod
    def prepare_evaluation_dataset(
        questions: List[str], answer_lists: List[List[str]], scores: List[List[float]]
    ) -> List[List[Any]]:
        """Prepare dataset for evaluation results.

        Args:
            questions: List of questions.
            answer_lists: List of answer lists for each question.
            scores: List of score lists for each question.

        Returns:
            Prepared dataset rows.
        """
        dataset = []
        for i, question in enumerate(questions):
            row = [question]
            if i < len(answer_lists):
                for j, answer in enumerate(answer_lists[i]):
                    row.append(answer)
                    if i < len(scores) and j < len(scores[i]):
                        row.append(scores[i][j])
                    else:
                        row.append(0.0)
            dataset.append(row)
        return dataset

    @staticmethod
    def validate_file_path(file_path: str) -> bool:
        """Validate that a file path exists and is accessible.

        Args:
            file_path: Path to validate.

        Returns:
            True if file exists and is readable, False otherwise.
        """
        try:
            return os.path.exists(file_path) and os.path.isfile(file_path)
        except Exception as e:
            print(f"Error validating file path {file_path}: {e}")
            return False
