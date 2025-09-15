#!/usr/bin/env python3
"""
Test script to verify the scoring integration in interactive interview.
"""

import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the parent directory to the path so we can import from interview
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interview.core.session_manager import InterviewSessionManager
from interview.config.settings import LLMConfig, LLMProvider, InterviewConfig


def test_scoring_integration():
    """Test that the scoring system works correctly."""
    print("🧪 Testing Scoring Integration")
    print("=" * 50)

    try:
        # Initialize systems
        llm_config = LLMConfig()
        interview_config = InterviewConfig(min_questions=5, max_questions=15)
        session_manager = InterviewSessionManager(interview_config, llm_config)

        print("✅ Session manager initialized")

        # Mock CV and JD data
        mock_cv = {
            "personal_info": "John Doe, Software Engineer",
            "experience": "3 years of Python development, Django, REST APIs",
            "skills": "Python, Django, JavaScript, MySQL, Git",
        }

        mock_jd = "We are looking for a Python developer with Django experience."

        # Initialize session
        session_manager.initialize_session(mock_cv, mock_jd)
        print("✅ Session initialized with mock data")

        # Test answer evaluation
        test_question = "Can you explain how Django ORM works?"
        test_answer = "Django ORM is an object-relational mapping system that allows you to interact with databases using Python objects instead of writing SQL queries directly. It provides models that represent database tables and allows you to perform operations like create, read, update, and delete using Python methods."

        print(f"\n🔄 Testing evaluation...")
        print(f"Question: {test_question}")
        print(f"Answer: {test_answer[:100]}...")

        # Submit answer for evaluation
        evaluation_result = session_manager.submit_answer(test_question, test_answer)

        print("\n📊 Evaluation Result:")
        print(f"   Overall Score: {evaluation_result.get('overall_score', 0):.2f}")
        print(f"   Method: {evaluation_result.get('evaluation_method', 'unknown')}")

        if "reasoning" in evaluation_result:
            print(f"   Reasoning: {evaluation_result['reasoning'][:100]}...")

        # Test statistics
        try:
            stats = session_manager.get_session_statistics()
            if stats:
                print(f"\n📈 Session Statistics:")
                print(f"   Average Score: {stats.get('average_score', 0):.2f}")
                print(f"   Total Answers: {stats.get('total_evaluated_answers', 0)}")
        except Exception as e:
            print(f"\n⚠️  Statistics not available: {e}")

        print("\n🎉 Scoring integration test completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Error during scoring test: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_scoring_integration()
    if success:
        print("\n✅ Ready for interactive interview with scoring!")
    else:
        print("\n❌ Scoring integration needs attention.")
