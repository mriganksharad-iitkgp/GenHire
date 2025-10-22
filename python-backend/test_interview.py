"""
Simple test script to run the interview system in terminal.
"""

import os
import sys
from pathlib import Path

# Add the current directory to Python path so we can import interview module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from interview.simple_interview import SimpleInterviewSystem


def get_actual_files():
    """Get actual CV and JD file paths from uploads folder."""

    # Use actual files from uploads
    cv_path = os.path.abspath("uploads/cv/software_engineering_cv.pdf")
    jd_path = os.path.abspath("uploads/jd/software_engineering_job_description.pdf")

    # Check if files exist
    if not os.path.exists(cv_path):
        raise FileNotFoundError(f"CV file not found: {cv_path}")
    if not os.path.exists(jd_path):
        raise FileNotFoundError(f"JD file not found: {jd_path}")

    return cv_path, jd_path


def main():
    """Main function to run the interview."""
    print("🎯 Simplified Interview System Test")
    print("=" * 50)

    # Set up API key (you need to set this)
    groq_api_key = os.getenv("GROQ_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not groq_api_key and not openai_api_key:
        print(
            "❌ Error: Please set GROQ_API_KEY or OPENAI_API_KEY environment variable"
        )
        print("\nOn Windows:")
        print("set GROQ_API_KEY=your_api_key_here")
        print("OR")
        print("set OPENAI_API_KEY=your_api_key_here")
        return

    try:
        # Initialize the interview system
        print("🔧 Initializing interview system...")
        interview_system = SimpleInterviewSystem(
            groq_api_key=groq_api_key, openai_api_key=openai_api_key
        )
        print("✅ System initialized successfully!")

        # Get actual CV and JD files
        print("\n📁 Using actual CV and JD files...")
        cv_path, jd_path = get_actual_files()
        print(f"✅ Using CV: {os.path.basename(cv_path)}")
        print(f"✅ Using JD: {os.path.basename(jd_path)}")

        # Create interview session
        print("\n🚀 Creating interview session...")
        session_result = interview_system.create_session(cv_path, jd_path)

        if "error" in session_result:
            print(f"❌ Error creating session: {session_result['error']}")
            return

        session_id = session_result["session_id"]
        print(f"✅ Session created: {session_id}")

        # Show analysis
        if "analysis" in session_result:
            analysis = session_result["analysis"]
            print(f"\n📊 Analysis Results:")
            print(f"   Job Role: {analysis.get('job_role', 'N/A')}")
            print(f"   Experience Level: {analysis.get('experience_level', 'N/A')}")
            print(f"   Domain: {analysis.get('primary_domain', 'N/A')}")
            print(f"   Key Skills: {', '.join(analysis.get('key_skills', []))}")

        # Show first question
        print(f"\n❓ First Question:")
        print(f"   {session_result.get('first_question', 'No question generated')}")

        # Interactive Q&A loop
        question_number = 1
        current_question = session_result.get("first_question", "")

        while True:
            print(f"\n" + "=" * 50)
            print(f"Question {question_number}: {current_question}")
            print("-" * 50)

            # Get user answer
            answer = input("Your answer (or 'quit' to exit): ").strip()

            if answer.lower() == "quit":
                break

            if not answer:
                print("Please provide an answer.")
                continue

            # Submit answer
            print("🔄 Processing your answer...")
            result = interview_system.submit_answer(
                session_id, current_question, answer
            )

            if "error" in result:
                print(f"❌ Error: {result['error']}")
                break

            # Check if interview is complete
            if result.get("interview_complete"):
                print("✅ Interview completed!")
                break

            # Get next question
            current_question = result.get("next_question", "")
            if not current_question:
                print("No more questions available.")
                break

            question_number += 1

        # Show final status
        print("\n📋 Final Session Status:")
        status = interview_system.get_session_status(session_id)
        print(f"   Questions Asked: {status.get('questions_asked', 0)}")
        print(f"   Interview Complete: {status.get('is_complete', False)}")

        # End session
        print("\n🏁 Ending interview session...")
        end_result = interview_system.end_session(session_id)
        print("✅ Interview session ended successfully!")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback

        traceback.print_exc()

    finally:
        # No cleanup needed since we're using actual files
        print("\n✅ Test completed!")
        pass


if __name__ == "__main__":
    main()
