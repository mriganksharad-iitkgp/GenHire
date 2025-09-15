"""Visualization utilities for evaluation results."""

import pandas as pd
import matplotlib.pyplot as plt
from typing import List, Optional
import os


class VisualizationUtils:
    """Utilities for creating visualizations of evaluation results."""

    @staticmethod
    def plot_scores_from_csv(
        file_path: str, output_filename: Optional[str] = None
    ) -> bool:
        """Generate plots for scores from a CSV file.

        Args:
            file_path: Path to the CSV file containing scores.
            output_filename: Name of the output plot file. If None, uses default.

        Returns:
            True if successful, False otherwise.
        """
        try:
            # Read the CSV file
            df = pd.read_csv(file_path)

            # Identify score columns (assuming they are numbered)
            score_columns = ["2", "4", "6", "8", "10", "12"]

            # Convert score columns to numeric
            for col in score_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            # Filter available score columns
            available_score_columns = [
                col for col in score_columns if col in df.columns
            ]

            if not available_score_columns:
                print("No score columns found in the CSV file.")
                return False

            # Drop rows with NaN values in score columns
            df = df.dropna(subset=available_score_columns)

            if df.empty:
                print("No valid data to plot after cleaning.")
                return False

            return VisualizationUtils._create_score_plots(
                df, available_score_columns, output_filename
            )

        except FileNotFoundError:
            print(f"Error: The file '{file_path}' was not found.")
            return False
        except Exception as e:
            print(f"An error occurred: {e}")
            return False

    @staticmethod
    def _create_score_plots(
        df: pd.DataFrame,
        score_columns: List[str],
        output_filename: Optional[str] = None,
    ) -> bool:
        """Create score plots from DataFrame.

        Args:
            df: DataFrame containing the data.
            score_columns: List of column names containing scores.
            output_filename: Name of the output file.

        Returns:
            True if successful, False otherwise.
        """
        try:
            num_rows = len(df)

            # Create subplots
            if num_rows == 1:
                fig, ax = plt.subplots(1, 1, figsize=(10, 5))
                axes = [ax]
            else:
                fig, axes = plt.subplots(num_rows, 1, figsize=(10, 5 * num_rows))
                if num_rows == 1:
                    axes = [axes]

            # Create a plot for each row
            for index, row in df.iterrows():
                question = row.iloc[0]  # First column is the question
                scores = row[score_columns].values

                # Select appropriate axis
                ax = axes[index] if num_rows > 1 else axes[0]

                # Create x-axis labels
                x_labels = [f"Point {i+1}" for i in range(len(scores))]

                # Plot the scores
                ax.plot(x_labels, scores, marker="o", linestyle="-")
                ax.set_title(f'Scores for: "{str(question)[:80]}..."', fontsize=12)
                ax.set_ylabel("Score")
                ax.set_xlabel("Response Point")
                ax.grid(True)

            # Adjust layout
            plt.tight_layout()

            # Save the plot
            if output_filename is None:
                output_filename = "scores_plots.png"

            plt.savefig(output_filename)
            plt.close()

            print(f"Plot has been generated and saved as '{output_filename}'")
            return True

        except Exception as e:
            print(f"Error creating plots: {e}")
            return False

    @staticmethod
    def plot_score_distribution(
        scores: List[float], title: str = "Score Distribution"
    ) -> bool:
        """Plot score distribution histogram.

        Args:
            scores: List of scores to plot.
            title: Title for the plot.

        Returns:
            True if successful, False otherwise.
        """
        try:
            plt.figure(figsize=(10, 6))
            plt.hist(scores, bins=20, alpha=0.7, edgecolor="black")
            plt.title(title)
            plt.xlabel("Score")
            plt.ylabel("Frequency")
            plt.grid(True, alpha=0.3)

            # Add statistics
            mean_score = sum(scores) / len(scores) if scores else 0
            plt.axvline(
                mean_score, color="red", linestyle="--", label=f"Mean: {mean_score:.2f}"
            )
            plt.legend()

            plt.tight_layout()
            plt.savefig("score_distribution.png")
            plt.close()

            print("Score distribution plot saved as 'score_distribution.png'")
            return True

        except Exception as e:
            print(f"Error creating score distribution plot: {e}")
            return False
