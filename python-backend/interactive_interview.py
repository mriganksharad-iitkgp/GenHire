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
from interview.core.session_manager import InterviewSessionManager
from interview.config.settings import LLMConfig, LLMProvider, InterviewConfig
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


def display_answer_evaluation(evaluation_result):
    """Display the evaluation result for the candidate's answer."""
    if not evaluation_result:
        return

    print("\n" + "📊" + " " * 3 + "Answer Evaluation" + " " * 3 + "📊")
    print("-" * 40)

    # Overall score with color coding
    overall_score = evaluation_result.get("overall_score", 0.0)
    score_percentage = int(overall_score * 100)

    # Color coding based on score
    if overall_score >= 0.8:
        score_emoji = "🌟"
        score_label = "Excellent"
    elif overall_score >= 0.6:
        score_emoji = "✅"
        score_label = "Good"
    elif overall_score >= 0.4:
        score_emoji = "⚡"
        score_label = "Satisfactory"
    elif overall_score >= 0.2:
        score_emoji = "📈"
        score_label = "Needs Improvement"
    else:
        score_emoji = "🔍"
        score_label = "Poor"

    print(f"{score_emoji} Overall Score: {score_percentage}% ({score_label})")

    # Detailed scores if available
    if "relevance_score" in evaluation_result:
        rel_score = int(evaluation_result["relevance_score"] * 100)
        print(f"   🎯 Relevance: {rel_score}%")

    if "technical_accuracy_score" in evaluation_result:
        tech_score = int(evaluation_result["technical_accuracy_score"] * 100)
        print(f"   🔧 Technical Accuracy: {tech_score}%")

    if "communication_score" in evaluation_result:
        comm_score = int(evaluation_result["communication_score"] * 100)
        print(f"   💬 Communication: {comm_score}%")

    # Show evaluation method
    eval_method = evaluation_result.get("evaluation_method", "standard")
    if eval_method == "rubrics-eval":
        print(f"   🎓 Evaluated using: Advanced Rubrics System")
    elif eval_method == "fallback":
        print(f"   ⚠️  Evaluated using: Backup System")
    elif eval_method == "short-answer":
        print(f"   💭 Evaluated using: Short Answer Assessment")
    else:
        print(f"   📝 Evaluated using: Standard System")

    # Show reasoning if available
    reasoning = evaluation_result.get("reasoning", "")
    if reasoning and len(reasoning) > 20:  # Only show if meaningful
        print(f"\n💡 Feedback: {reasoning}")

    # Show score breakdown if available (from rubrics system)
    if "score_breakdown" in evaluation_result:
        breakdown = evaluation_result["score_breakdown"]
        print(f"\n📋 Score Breakdown:")
        for category, score in breakdown.items():
            if isinstance(score, (int, float)):
                print(f"   • {category.replace('_', ' ').title()}: {int(score * 100)}%")

    print("-" * 40)


def interactive_interview():
    """Run an interactive interview session."""
    print("🎯 Interactive AI Interview Session")
    print("=" * 80)
    print("Welcome! You'll be having a real conversation with Alex Rivera,")
    print("an AI interviewer using your actual CV and the job description.")
    print("Type your responses naturally - this is a real interview simulation!")
    print_separator()

    # Set up paths to the actual CV and JD files

    # cv_path = "e:\\BTP\\product-prototyping-lab\\python-backend\\uploads\\cv\\software_engineering_cv.pdf"
    # jd_path = "e:\\BTP\\product-prototyping-lab\\python-backend\\uploads\\jd\\software_engineering_job_description.pdf"

    cv_path = "C:\\Users\\Acer\\OneDrive - iitkgp.ac.in\\Desktop\\main2\\product-prototyping-lab\\python-backend\\uploads\\cv\\MyAICV.pdf"
    jd_path = "C:\\Users\\Acer\\OneDrive - iitkgp.ac.in\\Desktop\\main2\\product-prototyping-lab\\python-backend\\uploads\\jd\\Senior-AI-Engineer-JD.pdf"
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

        # Initialize session manager for answer evaluation
        interview_config = InterviewConfig(min_questions=5, max_questions=15)
        session_manager = InterviewSessionManager(interview_config, llm_config)

        # Load and process documents
        document_loader = DocumentLoader(cv_path, jd_path, reference_paths)
        validation = document_loader.validate_documents()

        if not all(validation.values()):
            print("❌ Document validation failed")
            return

        resume_sections = document_loader.get_cv_sections()
        job_description = document_loader.get_jd_text()

        # Initialize both systems
        context = qg.initialize_conversation(resume_sections, job_description)

        # Create a session with session manager for evaluation
        session_result = session_manager.create_session(
            cv_path, jd_path, reference_paths
        )
        if "error" in session_result:
            print(f"❌ Failed to create evaluation session: {session_result['error']}")
            return

        session_id = session_result["session_id"]
        print(f"✅ Evaluation session created: {session_id[:8]}...")

        print(f"\n📋 Interview Setup Complete:")
        print(f"   Candidate: {context.candidate_name}")
        print(f"   Position: {context.job_title}")
        print(f"   Your CV Keywords: {', '.join(context.cv_keywords)}")
        print(f"   Assessed Skill Level: {context.candidate_skill_level}")

        # Show evaluation system info
        try:
            if (
                hasattr(session_manager, "evaluation_system")
                and session_manager.evaluation_system
            ):
                print(f"   🎓 Evaluation: Advanced Rubrics System")
            else:
                print(f"   📝 Evaluation: Standard System")
        except:
            print(f"   📝 Evaluation: Standard System")

        print_separator()
        print("🚀 Starting the interview... Be yourself and answer naturally!")
        print("📊 Your answers will be evaluated and scored in real-time!")
        print("🎯 You'll see detailed feedback after each technical question.")
        print("(Type 'exit' at any time to end the interview)")
        print_separator()

        # Interview loop
        interview_active = True
        question_count = 0
        last_answer = None
        last_evaluation = None
        current_question = None

        while interview_active:
            try:
                # Get next question from AI interviewer
                if question_count == 0:
                    # First question (greeting)
                    current_question, metadata = qg.get_next_question(context)
                else:
                    # Subsequent questions with previous answer and evaluation
                    current_question, metadata = qg.get_next_question(
                        context,
                        last_answer,
                        last_evaluation,
                    )

                # Display the question
                print_interviewer_message(current_question)

                # Show current phase info
                phase_emojis = {
                    InterviewPhase.GREETING: "👋",
                    InterviewPhase.STRUCTURE_EXPLANATION: "📋",
                    InterviewPhase.EXPERIENTIAL_QUESTIONS: "💼",
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

                # Evaluate ALL answers (not just technical ones) using session manager
                if (
                    last_answer.strip() and len(last_answer.strip()) > 3
                ):  # Only evaluate substantial answers
                    print("\n🔄 Evaluating your answer...")
                    try:
                        # Use session manager to evaluate the answer
                        eval_result = session_manager.submit_answer(
                            session_id, current_question, last_answer
                        )

                        if "error" in eval_result:
                            print(f"⚠️  Evaluation error: {eval_result['error']}")
                            # Use fallback evaluation
                            last_evaluation = {
                                "overall_score": 0.7,
                                "evaluation_method": "fallback",
                            }
                        else:
                            # Extract evaluation from session manager result
                            last_evaluation = eval_result.get("current_evaluation", {})

                            # Display the evaluation for ALL questions
                            display_answer_evaluation(last_evaluation)

                            # Check if interview is complete from session manager
                            if eval_result.get("interview_complete", False):
                                print_separator()
                                print("🎉 Interview Complete!")

                                # Show final evaluation
                                final_eval = eval_result.get("final_evaluation", {})
                                if final_eval:
                                    print("\n📊 Final Evaluation:")
                                    if "overall_score" in final_eval:
                                        final_score = int(
                                            final_eval["overall_score"] * 100
                                        )
                                        print(
                                            f"   🎯 Overall Performance: {final_score}%"
                                        )

                                    if "summary" in final_eval:
                                        print(f"   📝 Summary: {final_eval['summary']}")

                                # Show conversation summary
                                conv_summary = eval_result.get(
                                    "conversation_summary", {}
                                )
                                if conv_summary:
                                    print(f"\n📋 Interview Summary:")
                                    if "topics_covered" in conv_summary:
                                        print(
                                            f"   Topics Covered: {', '.join(conv_summary['topics_covered'])}"
                                        )
                                    if "total_questions" in conv_summary:
                                        print(
                                            f"   Total Questions: {conv_summary['total_questions']}"
                                        )
                                    if "average_score" in conv_summary:
                                        avg_score = int(
                                            conv_summary["average_score"] * 100
                                        )
                                        print(f"   Average Score: {avg_score}%")

                                print(
                                    "\nThank you for participating in this AI interview simulation!"
                                )
                                break

                    except Exception as eval_error:
                        print(
                            f"⚠️  Evaluation temporarily unavailable: {str(eval_error)}"
                        )
                        import traceback

                        traceback.print_exc()
                        # Use fallback evaluation
                        last_evaluation = {
                            "overall_score": 0.7,
                            "evaluation_method": "fallback",
                        }
                else:
                    # For very short answers, use neutral evaluation
                    last_evaluation = {
                        "overall_score": 0.7,
                        "evaluation_method": "short-answer",
                    }

                question_count += 1

                # Show progress after questions
                if context.interview_phase == InterviewPhase.TECHNICAL_QUESTIONS:
                    topics_left = [
                        kw
                        for kw in context.cv_keywords
                        if kw not in context.topics_covered
                    ]
                    if topics_left:
                        print(f"\n📝 Upcoming Topics: {', '.join(topics_left[:3])}")

                # Also check for natural interview completion (as backup)
                if (
                    context.interview_phase == InterviewPhase.CLOSING
                    and question_count > 8
                ):
                    print_separator()
                    print("🎉 Interview naturally completed!")
                    print(f"\n📊 Basic Interview Summary:")
                    print(f"   Total Questions: {context.question_count}")
                    print(f"   Topics Covered: {', '.join(context.topics_covered)}")
                    print(f"   Your Skill Level: {context.candidate_skill_level}")
                    print(
                        "\nThank you for participating in this AI interview simulation!"
                    )
                    break

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

    # cv_path = "e:\\BTP\\product-prototyping-lab\\python-backend\\uploads\\cv\\software_engineering_cv.pdf"
    # jd_path = "e:\\BTP\\product-prototyping-lab\\python-backend\\uploads\\jd\\software_engineering_job_description.pdf"

    cv_path = "C:\\Users\\Acer\\OneDrive - iitkgp.ac.in\\Desktop\\main2\\product-prototyping-lab\\python-backend\\uploads\\cv\\MyAICV.pdf"
    jd_path = "C:\\Users\\Acer\\OneDrive - iitkgp.ac.in\\Desktop\main2\\product-prototyping-lab\\python-backend\\uploads\\jd\\AI_JD.pdf"

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
