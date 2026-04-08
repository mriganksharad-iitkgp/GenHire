"""
Evaluation Model Package

Contains various evaluation systems for the interview platform.
"""

# Import from rubrics-eval directory (handle hyphen in folder name)
import sys
import os
from .rubrics_eval.evaluation_system import EvaluationSystem

__version__ = "1.0.0"
# Make it available at package level
__all__ = ["EvaluationSystem"]

