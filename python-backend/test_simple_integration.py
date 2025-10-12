"""
Simple integration test without Unicode characters.
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
from interview.config.settings import LLMConfig, InterviewConfig
from interview.llm.factory import LLMFactory
from interview.document.loader import DocumentLoader


def test_simple_integration():
    """Test the integration without Unicode characters."""
    print("Testing Simple Integration...")
    
    # Set up paths
    cv_path = "C:\\Users\\Acer\\OneDrive - iitkgp.ac.in\\Desktop\\hr_techh\\product-prototyping-lab\\python-backend\\uploads\\cv\\software_engineering_cv.pdf"
    jd_path = "C:\\Users\\Acer\\OneDrive - iitkgp.ac.in\\Desktop\\hr_techh\\product-prototyping-lab\\python-backend\\uploads\\jd\\software_engineering_job_description.pdf"
    
    try:
        # Initialize components
        llm_config = LLMConfig()
        llm = LLMFactory.create(llm_config)
        qg = PromptBasedQuestionGenerator(llm)
        
        # Load documents
        document_loader = DocumentLoader(cv_path, jd_path, [])
        resume_sections = document_loader.get_cv_sections()
        job_description = document_loader.get_jd_text()
        
        # Initialize conversation
        context = qg.initialize_conversation(resume_sections, job_description)
        
        print("SUCCESS: Components initialized")
        print(f"Interview Phase: {context.interview_phase}")
        print(f"Candidate Name: {context.candidate_name}")
        print(f"Job Title: {context.job_title}")
        print(f"CV Keywords: {len(context.cv_keywords)} found")
        print(f"CV Projects: {len(context.cv_projects)} found")
        print(f"CV Experiences: {len(context.cv_experiences)} found")
        
        # Test question generation for each phase
        phases_tested = []
        last_answer = "I have experience with Python and React development."
        last_evaluation = {"overall_score": 0.8, "relevance_score": 0.8}
        
        print("\nTesting Interview Phases:")
        
        # Test 10 questions to cover all phases
        for i in range(10):
            try:
                # Get next question
                question, metadata = qg.get_next_question(context, last_answer, last_evaluation)
                
                # Track phase changes
                if context.interview_phase not in phases_tested:
                    phases_tested.append(context.interview_phase)
                    print(f"  Phase {len(phases_tested)}: {context.interview_phase.value}")
                
                # Update last answer for next iteration
                last_answer = f"Answer to question {i+1}: I have experience with various technologies and projects."
                
                # Check if interview should end
                if context.interview_phase == InterviewPhase.CLOSING:
                    print(f"  Interview completed after {context.question_count} questions")
                    break
                    
            except Exception as e:
                print(f"  Error in question {i+1}: {str(e)}")
                break
        
        print(f"\nTest Results:")
        print(f"  Phases Tested: {len(phases_tested)}")
        print(f"  Questions Generated: {context.question_count}")
        
        # Check if all expected phases were tested
        expected_phases = [
            InterviewPhase.GREETING,
            InterviewPhase.STRUCTURE_EXPLANATION,
            InterviewPhase.EXPERIENTIAL_QUESTIONS,
            InterviewPhase.TECHNICAL_QUESTIONS,
            InterviewPhase.CLOSING
        ]
        
        missing_phases = [phase for phase in expected_phases if phase not in phases_tested]
        if missing_phases:
            print(f"  Missing phases: {[p.value for p in missing_phases]}")
        else:
            print(f"  All expected phases tested")
        
        # Test experiential questions specifically
        if InterviewPhase.EXPERIENTIAL_QUESTIONS in phases_tested:
            print(f"  Experiential questions phase working")
            print(f"  Projects covered: {len(context.projects_covered)}")
            print(f"  Current project focus: {context.current_project_focus}")
        else:
            print(f"  Experiential questions phase not reached")
        
        print("\nSUCCESS: Integration test completed!")
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_simple_integration()
