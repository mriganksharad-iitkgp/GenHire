#!/usr/bin/env python3
"""
Debug script to identify the exact import issue with rubrics-eval.
"""

import sys
import os

# Add paths
current_dir = os.path.dirname(os.path.abspath(__file__))
rubrics_eval_path = os.path.join(current_dir, "evaluation model", "rubrics-eval")

print(f"Current directory: {current_dir}")
print(f"Rubrics-eval path: {rubrics_eval_path}")
print(f"Path exists: {os.path.exists(rubrics_eval_path)}")

# Check what files are in the directory
if os.path.exists(rubrics_eval_path):
    print(f"Files in rubrics-eval: {os.listdir(rubrics_eval_path)}")

# Try the simple approach
sys.path.insert(0, rubrics_eval_path)

try:
    print("\n🔄 Attempting to import evaluation_system...")
    from evaluation_system import EvaluationSystem

    print("✅ Direct import successful!")
    print(f"EvaluationSystem class: {EvaluationSystem}")

    # Try to instantiate
    try:
        eval_system = EvaluationSystem()
        print("✅ Instantiation successful!")
    except Exception as e:
        print(f"❌ Instantiation failed: {e}")

except ImportError as e:
    print(f"❌ Import failed: {e}")

    # Let's try to see what the specific error is
    print("\n🔍 Checking individual dependencies...")

    try:
        import config

        print("✅ config.py imported")
    except Exception as e:
        print(f"❌ config.py failed: {e}")

    try:
        import rubric_generator

        print("✅ rubric_generator.py imported")
    except Exception as e:
        print(f"❌ rubric_generator.py failed: {e}")

    try:
        import answer_evaluator

        print("✅ answer_evaluator.py imported")
    except Exception as e:
        print(f"❌ answer_evaluator.py failed: {e}")
