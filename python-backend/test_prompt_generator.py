"""
Test for the new prompt-based question generator using real LLM and actual CV/JD files.
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


def test_real_question_generator():
    """Test the prompt-based question generator with real LLM and actual CV/JD."""
    print("Testing Prompt-Based Question Generator with Real LLM...")

    # Set up paths to the actual CV and JD files
    cv_path = "e:\\BTP\\product-prototyping-lab\\python-backend\\uploads\\cv\\software_engineering_cv.pdf"
    jd_path = "e:\\BTP\\product-prototyping-lab\\python-backend\\uploads\\jd\\software_engineering_job_description.pdf"
    reference_paths = []  # Empty for now

    # Check if files exist
    if not os.path.exists(cv_path):
        print(f"❌ CV file not found: {cv_path}")
        return
    if not os.path.exists(jd_path):
        print(f"❌ JD file not found: {jd_path}")
        return

    print(f"✓ CV file found: {cv_path}")
    print(f"✓ JD file found: {jd_path}")

    # Use default LLM configuration from settings.py
    llm_config = LLMConfig()  # Uses default GEMINI configuration
    print(f"✓ Using LLM: {llm_config.provider.value} - {llm_config.model_name}")

    try:
        # Initialize real LLM
        llm = LLMFactory.create(llm_config)
        print("✓ LLM initialized successfully")

        # Initialize question generator
        qg = PromptBasedQuestionGenerator(llm)
        print("✓ Question generator created")

        # Load and process documents
        print("\n1. Loading and processing documents...")
        document_loader = DocumentLoader(cv_path, jd_path, reference_paths)

        # Validate documents
        validation = document_loader.validate_documents()
        print(f"   Document validation: {validation}")

        if not all(validation.values()):
            print("❌ Document validation failed")
            return

        # Get resume sections and job description
        resume_sections = document_loader.get_cv_sections()
        job_description = document_loader.get_jd_text()

        print(f"   ✓ Resume sections: {list(resume_sections.keys())}")
        print(f"   ✓ JD text length: {len(job_description)} characters")

        # Test 2: Initialize conversation with real data
        print("\n2. Testing conversation initialization...")
        context = qg.initialize_conversation(resume_sections, job_description)
        print(f"   ✓ Candidate name: {context.candidate_name}")
        print(f"   ✓ Job title: {context.job_title}")
        print(f"   ✓ CV keywords: {context.cv_keywords}")
        print(f"   ✓ Initial phase: {context.interview_phase}")
        print(f"   ✓ Skill level: {context.candidate_skill_level}")

        # Test 3: Generate greeting with real LLM
        print("\n3. Testing greeting generation with real LLM...")
        question, metadata = qg.get_next_question(context)
        print(f"   ✓ Greeting: {question}")
        print(f"   ✓ Phase after greeting: {context.interview_phase}")

        # Test 4: Generate structure explanation
        print("\n4. Testing structure explanation...")
        question, metadata = qg.get_next_question(context)
        print(f"   ✓ Structure: {question}")
        print(f"   ✓ Phase after structure: {context.interview_phase}")

        # Test 5: Generate technical questions with real LLM
        print("\n5. Testing technical questions with real LLM...")
        for i in range(2):
            question, metadata = qg.get_next_question(
                context,
                f"This is a sample answer for question {i+1}.",
                {"overall_score": 0.7},
            )
            print(f"   ✓ Question {i+1}: {question}")
            print(f"   ✓ Topic area: {metadata.topic_area}")
            print(f"   ✓ Difficulty: {metadata.difficulty_level}")

        print(f"   ✓ Questions asked: {context.question_count}")
        print(f"   ✓ Topics covered: {context.topics_covered}")

        # Test 6: Continue until candidate questions phase
        print("\n6. Testing transition to candidate questions...")
        max_iterations = 10  # Prevent infinite loop
        iterations = 0

        while (
            context.interview_phase == InterviewPhase.TECHNICAL_QUESTIONS
            and iterations < max_iterations
        ):
            question, metadata = qg.get_next_question(
                context, "Good technical answer", {"overall_score": 0.8}
            )
            iterations += 1

        print(f"   ✓ Current phase: {context.interview_phase}")
        if context.interview_phase == InterviewPhase.CANDIDATE_QUESTIONS:
            print(f"   ✓ Invitation: {question}")

        # Test 7: Answer candidate question
        if context.interview_phase == InterviewPhase.CANDIDATE_QUESTIONS:
            print("\n7. Testing candidate question response...")
            question, metadata = qg.get_next_question(
                context, "What technologies does your team use for backend development?"
            )
            print(f"   ✓ Response: {question}")

        # Test 8: Generate closing
        print("\n8. Testing closing generation...")
        question, metadata = qg.get_next_question(context, "No more questions")
        print(f"   ✓ Phase: {context.interview_phase}")
        print(f"   ✓ Closing: {question}")

        print(f"\n✅ All tests completed successfully!")
        print(f"Total questions asked: {context.question_count}")
        print(f"Final interview phase: {context.interview_phase}")

    except Exception as e:
        print(f"❌ Error during testing: {str(e)}")
        import traceback

        traceback.print_exc()


def test_cv_processing():
    """Test CV processing specifically."""
    print("\nTesting CV Processing...")

    cv_path = "e:\\BTP\\product-prototyping-lab\\python-backend\\uploads\\cv\\software_engineering_cv.pdf"
    jd_path = "e:\\BTP\\product-prototyping-lab\\python-backend\\uploads\\jd\\software_engineering_job_description.pdf"

    try:
        document_loader = DocumentLoader(cv_path, jd_path, [])
        resume_sections = document_loader.get_cv_sections()
        job_description = document_loader.get_jd_text()

        print("Resume sections:")
        for section, content in resume_sections.items():
            print(
                f"  {section}: {content[:100]}..."
                if len(content) > 100
                else f"  {section}: {content}"
            )

        print(f"\nJob Description: {job_description[:200]}...")

    except Exception as e:
        print(f"❌ Error processing documents: {str(e)}")


if __name__ == "__main__":
    test_cv_processing()
    print("\n" + "=" * 80 + "\n")
    test_real_question_generator()
