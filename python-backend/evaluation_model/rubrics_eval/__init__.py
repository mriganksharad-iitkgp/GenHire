"""
Rubrics Evaluation System

A modular system for generating rubrics, evaluating answers, and creating test datasets.
"""

from importlib import import_module

# Importing the cheap answer classifier must not initialize plotting, data
# processing, or provider clients. Preserve the public class exports lazily.
_EXPORTS = {
    "Config": "config",
    "RubricGenerator": "rubric_generator",
    "AnswerEvaluator": "answer_evaluator",
    "AnswerGenerator": "answer_generator",
    "DataProcessor": "data_processor",
    "VisualizationUtils": "visualization",
    "CommunicationEvaluator": "communication_evaluator",
    "EvaluationSystem": "evaluation_system",
}


def __getattr__(name):
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f".{module}", __name__), name)
    globals()[name] = value
    return value

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
