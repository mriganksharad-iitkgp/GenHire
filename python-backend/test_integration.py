"""
Simple integration test for experiential questions.
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
from interview.config.settings import LLMConfig
from interview.llm.factory import LLMFactory
from interview.document.loader import DocumentLoader


def test_integration():
    """Test the integration between components."""
    print("Testing Integration...")
    
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
        
        # Test question generation
        question, metadata = qg.get_next_question(context)
        print(f"First Question: {question[:100]}...")
        
        # Test experiential question generation
        context.interview_phase = InterviewPhase.EXPERIENTIAL_QUESTIONS
        exp_question, exp_metadata = qg.get_next_question(context)
        print(f"Experiential Question: {exp_question[:100]}...")
        
        print("SUCCESS: All tests passed!")
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_integration()
