"""
Rubrics Evaluation System

A modular system for generating rubrics, evaluating answers, and creating test datasets.
"""

from .config import Config
from .rubric_generator import RubricGenerator
from .answer_evaluator import AnswerEvaluator
from .answer_generator import AnswerGenerator
from .data_processor import DataProcessor
from .visualization import VisualizationUtils
from .communication_evaluator import CommunicationEvaluator
from .evaluation_system import EvaluationSystem

__version__ = "1.0.0"
__author__ = "BTP Team"

__all__ = [
    "Config",
    "RubricGenerator",
    "AnswerEvaluator",
    "AnswerGenerator",
    "DataProcessor",
    "VisualizationUtils",
    "CommunicationEvaluator",
    "EvaluationSystem",
]
