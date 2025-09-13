"""
Interactive test for the prompt-based question generator.
Allows you to have a real conversation with the AI interviewer.
"""

import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the parent directory to the path so we can import from interview
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interview.core.prompt_based_question_generator import (
    PromptBasedQuestionGenerator,
    ConversationContext,
    InterviewPhase,
)
from interview.config.settings import LLMConfig, LLMProvider
from interview.llm.factory import LLMFactory
from interview.document.loader import DocumentLoader


def print_separator():
    """Print a visual separator."""
    print("\n" + "=" * 80 + "\n")


def print_interviewer_message(message):
    """Print interviewer message with formatting."""
    print(f"🤖 Alex Rivera (Interviewer): {message}")


def get_candidate_response():
    """Get candidate response from input."""
    print("\n👤 Your Response:")
    response = input(">> ")
    return response.strip()


def interactive_interview():
    """Run an interactive interview session."""
    print("🎯 Interactive AI Interview Session")
    print("=" * 80)
    print("Welcome! You'll be having a real conversation with Alex Rivera,")
    print("an AI interviewer using your actual CV and the job description.")
    print("Type your responses naturally - this is a real interview simulation!")
    print_separator()

    # Set up paths to the actual CV and JD files
    cv_path = "e:\\BTP\\product-prototyping-lab\\python-backend\\uploads\\cv\\software_engineering_cv.pdf"
    jd_path = "e:\\BTP\\product-prototyping-lab\\python-backend\\uploads\\jd\\software_engineering_job_description.pdf"
    reference_paths = []

    # Check if files exist
    if not os.path.exists(cv_path):
        print(f"❌ CV file not found: {cv_path}")
        return
    if not os.path.exists(jd_path):
        print(f"❌ JD file not found: {jd_path}")
        return

    print(f"✅ Using CV: {os.path.basename(cv_path)}")
    print(f"✅ Using JD: {os.path.basename(jd_path)}")

    # Use default LLM configuration from settings.py
    llm_config = LLMConfig()
    print(
        f"✅ AI Interviewer powered by: {llm_config.provider.value} ({llm_config.model_name})"
    )

    try:
        # Initialize the interview system
        print("\n🔧 Initializing AI interviewer...")
        llm = LLMFactory.create(llm_config)
        qg = PromptBasedQuestionGenerator(llm)

        # Load and process documents
        document_loader = DocumentLoader(cv_path, jd_path, reference_paths)
        validation = document_loader.validate_documents()

        if not all(validation.values()):
            print("❌ Document validation failed")
            return

        resume_sections = document_loader.get_cv_sections()
        job_description = document_loader.get_jd_text()

        # Initialize conversation
        context = qg.initialize_conversation(resume_sections, job_description)

        print(f"\n📋 Interview Setup Complete:")
        print(f"   Candidate: {context.candidate_name}")
        print(f"   Position: {context.job_title}")
        print(f"   Your CV Keywords: {', '.join(context.cv_keywords[:5])}")
        print(f"   Assessed Skill Level: {context.candidate_skill_level}")

        print_separator()
        print("🚀 Starting the interview... Be yourself and answer naturally!")
        print("(Type 'exit' at any time to end the interview)")
        print_separator()

        # Interview loop
        interview_active = True
        question_count = 0

        while interview_active:
            try:
                # Get next question from AI interviewer
                if question_count == 0:
                    # First question (greeting)
                    question, metadata = qg.get_next_question(context)
                else:
                    # Subsequent questions with previous answer
                    question, metadata = qg.get_next_question(
                        context,
                        last_answer,
                        {"overall_score": 0.7},  # Simulated evaluation
                    )

                # Display the question
                print_interviewer_message(question)

                # Show current phase info
                phase_emojis = {
                    InterviewPhase.GREETING: "👋",
                    InterviewPhase.STRUCTURE_EXPLANATION: "📋",
                    InterviewPhase.TECHNICAL_QUESTIONS: "🔬",
                    InterviewPhase.CLOSING: "👋",
                }

                phase_emoji = phase_emojis.get(context.interview_phase, "💬")
                print(
                    f"\n{phase_emoji} Interview Phase: {context.interview_phase.value.replace('_', ' ').title()}"
                )

                if context.interview_phase == InterviewPhase.TECHNICAL_QUESTIONS:
                    print(f"🎯 Current Topic: {context.current_topic}")
                    print(f"📊 Questions Asked: {context.question_count}")

                # Get candidate response
                last_answer = get_candidate_response()

                # Check for exit command
                if last_answer.lower() in ["exit", "quit", "end"]:
                    print("\n👋 Ending interview session. Thank you!")
                    break

                question_count += 1

                # Check if interview is naturally complete
                if (
                    context.interview_phase == InterviewPhase.CLOSING
                    and question_count > 1
                ):
                    print_separator()
                    print("🎉 Interview Complete!")
                    print("\n📊 Interview Summary:")
                    print(f"   Total Questions: {context.question_count}")
                    print(f"   Topics Covered: {', '.join(context.topics_covered)}")
                    print(f"   Final Phase: {context.interview_phase.value}")
                    print(f"   Your Skill Level: {context.candidate_skill_level}")
                    print(
                        "\nThank you for participating in this AI interview simulation!"
                    )
                    break

                # Show progress after technical questions
                if context.interview_phase == InterviewPhase.TECHNICAL_QUESTIONS:
                    topics_left = [
                        kw
                        for kw in context.cv_keywords
                        if kw not in context.topics_covered
                    ]
                    if topics_left:
                        print(f"\n📝 Upcoming Topics: {', '.join(topics_left[:3])}")

                print_separator()

            except KeyboardInterrupt:
                print("\n\n👋 Interview interrupted. Goodbye!")
                break

            except Exception as e:
                print(f"\n❌ Error during interview: {str(e)}")
                print("The interview will continue...")
                continue

    except Exception as e:
        print(f"❌ Failed to initialize interview: {str(e)}")
        import traceback

        traceback.print_exc()


def demo_mode():
    """Run a quick demo showing what the system extracts from CV/JD."""
    print("📄 CV/JD Analysis Demo")
    print("=" * 50)

    cv_path = "e:\\BTP\\product-prototyping-lab\\python-backend\\uploads\\cv\\software_engineering_cv.pdf"
    jd_path = "e:\\BTP\\product-prototyping-lab\\python-backend\\uploads\\jd\\software_engineering_job_description.pdf"

    try:
        document_loader = DocumentLoader(cv_path, jd_path, [])
        resume_sections = document_loader.get_cv_sections()
        job_description = document_loader.get_jd_text()

        # Initialize just to see what gets extracted
        llm_config = LLMConfig()
        llm = LLMFactory.create(llm_config)
        qg = PromptBasedQuestionGenerator(llm)
        context = qg.initialize_conversation(resume_sections, job_description)

        print("✅ Successfully analyzed your documents!")
        print(f"\n👤 Extracted Candidate Info:")
        print(f"   Name: {context.candidate_name}")
        print(f"   Skill Level: {context.candidate_skill_level}")

        print(f"\n💼 Job Analysis:")
        print(f"   Position: {context.job_title}")

        print(f"\n🔧 Technical Keywords Found:")
        for i, keyword in enumerate(context.cv_keywords, 1):
            print(f"   {i}. {keyword}")

        print(f"\n📋 Resume Sections Processed:")
        for section, content in resume_sections.items():
            content_preview = content[:100] + "..." if len(content) > 100 else content
            print(f"   {section}: {content_preview}")

        print(f"\n📄 Job Description Preview:")
        print(f"   {job_description[:200]}...")

    except Exception as e:
        print(f"❌ Error analyzing documents: {str(e)}")


def main():
    """Main menu for interactive testing."""
    print("🤖 AI Interview System - Interactive Testing")
    print("=" * 60)
    print("Choose an option:")
    print("1. Start Interactive Interview (Full Experience)")
    print("2. Document Analysis Demo (Quick Overview)")
    print("3. Exit")

    while True:
        choice = input("\nEnter your choice (1-3): ").strip()

        if choice == "1":
            print_separator()
            interactive_interview()
            break
        elif choice == "2":
            print_separator()
            demo_mode()
            print_separator()
            # Ask if they want to continue to full interview
            continue_choice = (
                input("Would you like to start the full interactive interview? (y/n): ")
                .strip()
                .lower()
            )
            if continue_choice in ["y", "yes"]:
                print_separator()
                interactive_interview()
            break
        elif choice == "3":
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please enter 1, 2, or 3.")


if __name__ == "__main__":
    main()
