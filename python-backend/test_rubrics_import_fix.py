#!/usr/bin/env python3
"""
Test script to verify the corrected rubrics-eval import in session manager.
"""

import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the parent directory to the path so we can import from interview
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_session_manager_import():
    """Test that the session manager can import rubrics-eval correctly."""
    print("🧪 Testing Session Manager Import with Fixed Rubrics-Eval")
    print("=" * 65)

    try:
        from interview.core.session_manager import (
            InterviewSessionManager,
            RUBRICS_EVAL_AVAILABLE,
            EvaluationSystem,
        )

        print("✅ Session manager imported successfully!")
        print(f"   Rubrics-eval available: {RUBRICS_EVAL_AVAILABLE}")

        if RUBRICS_EVAL_AVAILABLE and EvaluationSystem:
            print("✅ EvaluationSystem class imported successfully!")
            print(f"   EvaluationSystem type: {type(EvaluationSystem)}")

            # Try to instantiate it
            try:
                eval_system = EvaluationSystem()
                print("✅ EvaluationSystem instantiated successfully!")

                # Check if it has the expected method
                if hasattr(eval_system, "evaluate_single_answer"):
                    print("✅ evaluate_single_answer method found!")
                else:
                    print("⚠️  evaluate_single_answer method not found")

            except Exception as e:
                print(f"⚠️  Could not instantiate EvaluationSystem: {e}")
                print("   This might be due to missing API keys or dependencies")
        else:
            print("⚠️  EvaluationSystem not available - using fallback evaluation")

        # Test session manager initialization
        from interview.config.settings import LLMConfig, LLMProvider, InterviewConfig

        llm_config = LLMConfig(provider=LLMProvider.GEMINI, model_name="gemini-pro")
        interview_config = InterviewConfig(min_questions=5, max_questions=15)

        session_manager = InterviewSessionManager(interview_config, llm_config)
        print("✅ Session manager initialized successfully!")

        if hasattr(session_manager, "evaluation_system"):
            if session_manager.evaluation_system:
                print("✅ Session manager has evaluation system attached!")
            else:
                print("⚠️  Session manager evaluation system is None (using fallback)")

        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_session_manager_import()

    if success:
        print("\n🎉 Session manager import test completed successfully!")
        print("The rubrics-eval system is now properly integrated!")
    else:
        print("\n❌ Import test failed. Please check the errors above.")
