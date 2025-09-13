#!/usr/bin/env python3
"""
Interactive Test for the Interview System

This script provides a complete interactive interview experience in the terminal.
You can test the entire interview flow with real CV/JD inputs and provide answers
in real-time to experience the natural conversation flow.

The LLM provider, model, and API key are automatically configured from settings.py.

Usage:
    python -m interview.test

    Or with specific files:
    python -m interview.test --cv path/to/cv.pdf --jd path/to/jd.pdf

Features:
- Interactive Q&A session in terminal
- Real-time conversation flow
- Dynamic question generation based on answers
- Professional interview experience
- Session status tracking
- Final evaluation and feedback
- Auto-configured LLM from settings.py
"""

import os
import sys
import argparse
import json
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

# Add the parent directory to the path to import from interview module
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from interview.api import InterviewAPI
from interview.config.settings import LLMProvider, LLMConfig, InterviewConfig
from interview.llm import LLMFactory


class InterviewTester:
    """Interactive interview testing interface."""

    def __init__(self):
        """Initialize the interview tester using settings from config."""
        # Use default configuration from settings.py
        self.llm_config = LLMConfig()
        self.interview_config = InterviewConfig()

        print(f"🔧 Using LLM Provider: {self.llm_config.provider.value}")
        print(f"🤖 Using Model: {self.llm_config.model_name}")

        # Create LLM instance using factory
        try:
            self.llm = LLMFactory.create(self.llm_config)
            print(f"✅ LLM initialized successfully")
        except Exception as e:
            print(f"❌ Error initializing LLM: {str(e)}")
            raise

        # Initialize the API with the configured LLM
        self.api = InterviewAPI(
            llm_provider=self.llm_config.provider,
            model_name=self.llm_config.model_name,
            api_key=self.llm_config.api_key,
        )

        self.session_id = None
        self.question_count = 0
        self.qa_history = []

    def print_banner(self):
        """Print a welcome banner."""
        print("\n" + "=" * 70)
        print("🎯 INTERACTIVE INTERVIEW SYSTEM TEST")
        print("=" * 70)
        print("Experience the natural conversation flow of our AI interviewer!")
        print("Type your answers naturally - the system will adapt to your responses.")
        print("Type 'quit' or 'exit' to end the interview early.")
        print(
            f"🤖 Using: {self.llm_config.provider.value} - {self.llm_config.model_name}"
        )
        print("=" * 70 + "\n")

    def print_section(self, title: str, content: str = ""):
        """Print a formatted section."""
        print(f"\n📋 {title}")
        print("-" * (len(title) + 4))
        if content:
            print(content)

    def print_question(self, question: str, question_num: int):
        """Print a formatted interview question."""
        print(f"\n❓ Question {question_num}:")
        print("=" * 50)
        print(f"{question}")
        print("=" * 50)

    def print_feedback(self, evaluation: Dict[str, Any]):
        """Print evaluation feedback."""
        if not evaluation:
            return

        print(f"\n💡 Feedback:")
        if "score" in evaluation:
            score = evaluation["score"]
            print(f"   Score: {score:.1f}/10")

        if "feedback" in evaluation:
            print(f"   {evaluation['feedback']}")

    def get_user_input(self, prompt: str = "\n🎤 Your Answer: ") -> str:
        """Get user input with proper formatting."""
        try:
            return input(prompt).strip()
        except KeyboardInterrupt:
            print("\n\n👋 Interview interrupted by user.")
            return "quit"

    def start_interview_session(
        self, cv_path: str, jd_path: str, reference_docs: list = None
    ):
        """Start a new interview session."""
        self.print_section("Starting Interview Session")

        print(f"📄 CV: {cv_path}")
        print(f"📋 Job Description: {jd_path}")
        if reference_docs:
            print(f"📚 Reference Documents: {', '.join(reference_docs)}")

        print("\n🔄 Initializing interview session...")

        try:
            result = self.api.start_interview(
                cv_file_path=cv_path,
                job_description_path=jd_path,
                reference_documents=reference_docs or [],
            )

            if "error" in result:
                print(f"❌ Error starting interview: {result['error']}")
                return False

            self.session_id = result["session_id"]
            print(f"✅ Session created successfully! ID: {self.session_id}")

            # Display session info
            if "session_info" in result:
                info = result["session_info"]
                if "topics_identified" in info:
                    print(
                        f"\n🎯 Topics to cover: {', '.join(info['topics_identified'])}"
                    )
                if "estimated_duration" in info:
                    print(
                        f"⏱️  Estimated duration: {info['estimated_duration']} minutes"
                    )

            return True

        except Exception as e:
            print(f"❌ Error starting interview: {str(e)}")
            return False

    def conduct_interactive_interview(self):
        """Conduct the main interactive interview loop."""
        print("\n🚀 Starting Interactive Interview!")
        print("The interviewer will adapt questions based on your responses.")
        print("Answer naturally and honestly.\n")

        while True:
            # Get next question
            try:
                question_result = self.api.get_question(self.session_id)

                if "error" in question_result:
                    print(f"❌ Error getting question: {question_result['error']}")
                    break

                if question_result.get("interview_complete", False):
                    print("\n🎉 Interview completed!")
                    self.show_final_evaluation(question_result)
                    break

                question = question_result.get("question", "")
                if not question:
                    print("❌ No question received. Ending interview.")
                    break

                self.question_count += 1

                # Display question context if available
                if "context" in question_result:
                    context = question_result["context"]
                    if "current_topic" in context:
                        print(f"\n📚 Topic: {context['current_topic']}")
                    if "depth_level" in context:
                        print(f"🎯 Depth: {context['depth_level']}")

                # Show the question
                self.print_question(question, self.question_count)

                # Get user answer
                answer = self.get_user_input()

                # Check for exit conditions
                if answer.lower() in ["quit", "exit", "q"]:
                    print("\n👋 Ending interview early...")
                    self.end_interview_early()
                    break

                if not answer.strip():
                    print("⚠️  Empty answer. Please provide a response.")
                    continue

                # Submit answer and get feedback
                print("\n🔄 Evaluating your answer...")

                answer_result = self.api.submit_answer(
                    self.session_id, question, answer
                )

                if "error" in answer_result:
                    print(f"❌ Error submitting answer: {answer_result['error']}")
                    break

                # Store Q&A
                self.qa_history.append(
                    {
                        "question": question,
                        "answer": answer,
                        "evaluation": answer_result.get("current_evaluation"),
                    }
                )

                # Show feedback
                if "current_evaluation" in answer_result:
                    self.print_feedback(answer_result["current_evaluation"])

                # Show progress
                if "session_status" in answer_result:
                    status = answer_result["session_status"]
                    if "questions_asked" in status and "estimated_remaining" in status:
                        print(
                            f"\n📊 Progress: {status['questions_asked']} asked, ~{status['estimated_remaining']} remaining"
                        )

                # Check if interview is complete
                if answer_result.get("interview_complete", False):
                    print("\n🎉 Interview completed!")
                    self.show_final_evaluation(answer_result)
                    break

                # Brief pause for readability
                input("\n⏸️  Press Enter to continue to the next question...")

            except KeyboardInterrupt:
                print("\n\n👋 Interview interrupted by user.")
                self.end_interview_early()
                break
            except Exception as e:
                print(f"❌ Unexpected error: {str(e)}")
                break

    def show_final_evaluation(self, result: Dict[str, Any]):
        """Display the final interview evaluation."""
        self.print_section("FINAL INTERVIEW EVALUATION", "")

        if "final_evaluation" in result:
            evaluation = result["final_evaluation"]

            if "overall_score" in evaluation:
                score = evaluation["overall_score"]
                print(f"🎯 Overall Score: {score:.1f}/10")

            if "recommendation" in evaluation:
                print(f"\n💼 Recommendation: {evaluation['recommendation']}")

            if "strengths" in evaluation:
                print(f"\n✅ Strengths:")
                for strength in evaluation["strengths"]:
                    print(f"   • {strength}")

            if "areas_for_improvement" in evaluation:
                print(f"\n📈 Areas for Improvement:")
                for area in evaluation["areas_for_improvement"]:
                    print(f"   • {area}")

            if "detailed_feedback" in evaluation:
                print(f"\n📝 Detailed Feedback:")
                print(f"   {evaluation['detailed_feedback']}")

        else:
            print("No final evaluation available.")

        # Show session summary
        self.show_session_summary()

    def show_session_summary(self):
        """Show a summary of the interview session."""
        self.print_section("SESSION SUMMARY")

        print(f"📊 Total Questions Asked: {self.question_count}")
        print(f"⏱️  Session Duration: {datetime.now().strftime('%H:%M:%S')}")

        if self.qa_history:
            avg_score = sum(
                qa.get("evaluation", {}).get("score", 0) for qa in self.qa_history
            ) / len(self.qa_history)
            print(f"📈 Average Score: {avg_score:.1f}/10")

        print(f"\n📋 Questions & Answers:")
        for i, qa in enumerate(self.qa_history, 1):
            print(f"\n   Q{i}: {qa['question'][:80]}...")
            print(f"   A{i}: {qa['answer'][:80]}...")
            if qa.get("evaluation", {}).get("score"):
                print(f"   Score: {qa['evaluation']['score']:.1f}/10")

    def end_interview_early(self):
        """Handle early interview termination."""
        if self.session_id:
            try:
                result = self.api.end_interview(self.session_id)
                print("✅ Interview session ended properly.")
                if "partial_evaluation" in result:
                    self.show_final_evaluation(result)
                else:
                    self.show_session_summary()
            except Exception as e:
                print(f"⚠️  Error ending session: {str(e)}")

    def run_demo_mode(self, cv_path: str, jd_path: str):
        """Run a quick demo with sample answers."""
        self.print_section("DEMO MODE")
        print("Running automated demo with sample answers...")
        print(
            f"Using {self.llm_config.provider.value} with {self.llm_config.model_name}"
        )

        try:
            result = self.api.conduct_full_interview(
                cv_file_path=cv_path, job_description_path=jd_path, max_questions=3
            )

            if "error" in result:
                print(f"❌ Demo failed: {result['error']}")
                return

            print("✅ Demo completed successfully!")
            print(json.dumps(result, indent=2))

        except Exception as e:
            print(f"❌ Demo error: {str(e)}")


def find_sample_files():
    """Find sample CV and JD files in the uploads directory."""
    base_path = Path(__file__).parent.parent / "uploads"

    cv_path = base_path / "cv"
    jd_path = base_path / "jd"

    cv_files = list(cv_path.glob("*.pdf")) if cv_path.exists() else []
    jd_files = list(jd_path.glob("*.pdf")) if jd_path.exists() else []

    return cv_files, jd_files


def get_file_paths_interactively():
    """Get CV and JD file paths from user input."""
    print("\n📁 File Path Configuration")
    print("=" * 50)

    # Get CV path
    while True:
        cv_input = input(
            "📄 Enter CV file path (or press Enter to auto-find): "
        ).strip()

        if not cv_input:
            # Try to auto-find CV files
            print("🔍 Looking for CV files...")
            cv_files, _ = find_sample_files()
            if cv_files:
                print("Found CV files:")
                for i, file in enumerate(cv_files, 1):
                    print(f"  {i}. {file}")

                while True:
                    try:
                        choice = input(
                            f"Choose CV file (1-{len(cv_files)}) or enter custom path: "
                        ).strip()
                        if choice.isdigit() and 1 <= int(choice) <= len(cv_files):
                            cv_path = str(cv_files[int(choice) - 1])
                            break
                        elif choice and Path(choice).exists():
                            cv_path = choice
                            break
                        elif choice:
                            print(f"❌ File not found: {choice}")
                        else:
                            print("⚠️ Please make a selection.")
                    except ValueError:
                        if choice and Path(choice).exists():
                            cv_path = choice
                            break
                        print("❌ Invalid selection.")
                break
            else:
                print("❌ No CV files found in uploads/cv/")
                cv_input = input("📄 Please enter CV file path manually: ").strip()
                if cv_input and Path(cv_input).exists():
                    cv_path = cv_input
                    break
                else:
                    print("❌ Invalid file path. Please try again.")
        else:
            if Path(cv_input).exists():
                cv_path = cv_input
                break
            else:
                print(f"❌ File not found: {cv_input}")

    # Get JD path
    while True:
        jd_input = input(
            "📋 Enter Job Description file path (or press Enter to auto-find): "
        ).strip()

        if not jd_input:
            # Try to auto-find JD files
            print("🔍 Looking for JD files...")
            _, jd_files = find_sample_files()
            if jd_files:
                print("Found JD files:")
                for i, file in enumerate(jd_files, 1):
                    print(f"  {i}. {file}")

                while True:
                    try:
                        choice = input(
                            f"Choose JD file (1-{len(jd_files)}) or enter custom path: "
                        ).strip()
                        if choice.isdigit() and 1 <= int(choice) <= len(jd_files):
                            jd_path = str(jd_files[int(choice) - 1])
                            break
                        elif choice and Path(choice).exists():
                            jd_path = choice
                            break
                        elif choice:
                            print(f"❌ File not found: {choice}")
                        else:
                            print("⚠️ Please make a selection.")
                    except ValueError:
                        if choice and Path(choice).exists():
                            jd_path = choice
                            break
                        print("❌ Invalid selection.")
                break
            else:
                print("❌ No JD files found in uploads/jd/")
                jd_input = input("📋 Please enter JD file path manually: ").strip()
                if jd_input and Path(jd_input).exists():
                    jd_path = jd_input
                    break
                else:
                    print("❌ Invalid file path. Please try again.")
        else:
            if Path(jd_input).exists():
                jd_path = jd_input
                break
            else:
                print(f"❌ File not found: {jd_input}")

    print(f"\n✅ Selected files:")
    print(f"   📄 CV: {cv_path}")
    print(f"   📋 JD: {jd_path}")

    return cv_path, jd_path


def main():
    """Main function to run the interactive interview test."""
    parser = argparse.ArgumentParser(
        description="Interactive Interview System Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m interview.test                    # Interactive mode with sample files
  python -m interview.test --demo             # Quick demo mode
  python -m interview.test --cv resume.pdf --jd job.pdf
        """,
    )

    parser.add_argument("--cv", help="Path to CV file (PDF)")
    parser.add_argument("--jd", help="Path to Job Description file (PDF)")
    parser.add_argument("--reference", nargs="*", help="Reference document paths")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run automated demo instead of interactive mode",
    )

    args = parser.parse_args()

    # Get file paths - prioritize command line args, then interactive input
    cv_path = args.cv
    jd_path = args.jd

    if not cv_path or not jd_path:
        if args.demo:
            # For demo mode, try to find files automatically first
            print("🔍 Demo mode: Looking for sample files...")
            cv_files, jd_files = find_sample_files()

            if not cv_path and cv_files:
                cv_path = str(cv_files[0])
                print(f"📄 Using CV: {cv_path}")

            if not jd_path and jd_files:
                jd_path = str(jd_files[0])
                print(f"📋 Using JD: {jd_path}")

            # If still missing files in demo mode, use interactive input
            if not cv_path or not jd_path:
                print("❌ Could not auto-find sample files for demo mode.")
                cv_path, jd_path = get_file_paths_interactively()
        else:
            # Interactive mode - always ask for file paths if not provided
            cv_path, jd_path = get_file_paths_interactively()

    # Final validation
    if not cv_path or not Path(cv_path).exists():
        print("❌ CV file not found. Please provide a valid CV file path.")
        return 1

    if not jd_path or not Path(jd_path).exists():
        print("❌ Job Description file not found. Please provide a valid JD file path.")
        return 1

    try:
        # Initialize tester with configuration from settings.py
        tester = InterviewTester()

        tester.print_banner()

        if args.demo:
            # Run demo mode
            tester.run_demo_mode(cv_path, jd_path)
        else:
            # Start interactive session
            if tester.start_interview_session(cv_path, jd_path, args.reference):
                tester.conduct_interactive_interview()
            else:
                print("❌ Failed to start interview session.")
                return 1

        print("\n🎉 Thank you for testing the interview system!")
        return 0

    except Exception as e:
        print(f"❌ Fatal error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
