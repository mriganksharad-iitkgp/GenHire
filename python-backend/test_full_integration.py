"""
Comprehensive integration test for the full interview flow with experiential questions.
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


def test_full_interview_flow():
    """Test the complete interview flow with experiential questions."""
    print("Testing Full Interview Flow...")
    
    # Set up paths
    cv_path = "C:\\Users\\Acer\\OneDrive - iitkgp.ac.in\\Desktop\\hr_techh\\product-prototyping-lab\\python-backend\\uploads\\cv\\software_engineering_cv.pdf"
    jd_path = "C:\\Users\\Acer\\OneDrive - iitkgp.ac.in\\Desktop\\hr_techh\\product-prototyping-lab\\python-backend\\uploads\\jd\\software_engineering_job_description.pdf"
    
    try:
        # Initialize components
        llm_config = LLMConfig()
        llm = LLMFactory.create(llm_config)
        qg = PromptBasedQuestionGenerator(llm)
        
        # Initialize session manager
        interview_config = InterviewConfig(min_questions=5, max_questions=25)
        session_manager = InterviewSessionManager(interview_config, llm_config)
        
        # Load documents
        document_loader = DocumentLoader(cv_path, jd_path, [])
        resume_sections = document_loader.get_cv_sections()
        job_description = document_loader.get_jd_text()
        
        # Initialize conversation
        context = qg.initialize_conversation(resume_sections, job_description)
        
        # Create session
        session_result = session_manager.create_session(cv_path, jd_path, [])
        if "error" in session_result:
            print(f"ERROR: Failed to create session: {session_result['error']}")
            return
        
        session_id = session_result["session_id"]
        print(f"✅ Session created: {session_id[:8]}...")
        
        # Test interview flow phases
        phases_tested = []
        last_answer = "I have experience with Python and React development."
        last_evaluation = {"overall_score": 0.8, "relevance_score": 0.8}
        
        print("\n🔄 Testing Interview Phases:")
        
        # Test each phase
        for i in range(15):  # Test 15 questions to cover all phases
            try:
                # Get next question
                question, metadata = qg.get_next_question(context, last_answer, last_evaluation)
                
                # Track phase changes
                if context.interview_phase not in phases_tested:
                    phases_tested.append(context.interview_phase)
                    print(f"   Phase {len(phases_tested)}: {context.interview_phase.value}")
                
                # Simulate answer submission
                if i > 0:  # Skip first question (greeting)
                    eval_result = session_manager.submit_answer(session_id, question, last_answer)
                    if "error" in eval_result:
                        print(f"   ⚠️  Evaluation error: {eval_result['error']}")
                    else:
                        last_evaluation = eval_result.get("current_evaluation", {})
                
                # Update last answer for next iteration
                last_answer = f"Answer to question {i+1}: I have experience with various technologies and projects."
                
                # Check if interview should end
                if context.interview_phase == InterviewPhase.CLOSING:
                    print(f"   ✅ Interview completed after {context.question_count} questions")
                    break
                    
            except Exception as e:
                print(f"   ❌ Error in question {i+1}: {str(e)}")
                break
        
        print(f"\n📊 Test Results:")
        print(f"   Phases Tested: {len(phases_tested)}")
        print(f"   Questions Generated: {context.question_count}")
        print(f"   CV Projects Found: {len(context.cv_projects)}")
        print(f"   CV Keywords Found: {len(context.cv_keywords)}")
        
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
            print(f"   ⚠️  Missing phases: {[p.value for p in missing_phases]}")
        else:
            print(f"   ✅ All expected phases tested")
        
        # Test experiential questions specifically
        if InterviewPhase.EXPERIENTIAL_QUESTIONS in phases_tested:
            print(f"   ✅ Experiential questions phase working")
            print(f"   Projects covered: {len(context.projects_covered)}")
            print(f"   Current project focus: {context.current_project_focus}")
        else:
            print(f"   ❌ Experiential questions phase not reached")
        
        print("\n✅ Full integration test completed successfully!")
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_full_interview_flow()
