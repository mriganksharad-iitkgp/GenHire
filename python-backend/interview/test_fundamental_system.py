"""
Test script for the domain-agnostic fundamental interview system.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interview.core.fundamental_interview_system import FundamentalInterviewSystem
from interview.llm.factory import LLMFactory


def test_fundamental_interview():
    """Test the fundamental interview system with sample data."""

    # Initialize LLM (you'll need to configure this based on your setup)
    try:
        llm = LLMFactory.create_llm("gemini")  # or "openai", "groq"
    except Exception as e:
        print(f"Error initializing LLM: {e}")
        print("Please configure your LLM in the factory.")
        return

    # Create interview system
    interview_system = FundamentalInterviewSystem(llm)

    # Sample CV data (can be from any domain)
    sample_cv = {
        "experience": """
        Senior Data Scientist at TechCorp (2020-2023)
        - Led machine learning projects for customer segmentation
        - Implemented deep learning models using TensorFlow and PyTorch
        - Worked with large datasets using Python, pandas, and SQL
        - Collaborated with cross-functional teams on product analytics
        
        Data Analyst at StartupInc (2018-2020)
        - Performed statistical analysis and data visualization
        - Built automated reporting dashboards using Tableau
        - Conducted A/B testing for product features
        """,
        "skills": """
        Programming: Python, R, SQL, Java
        Machine Learning: TensorFlow, PyTorch, scikit-learn, XGBoost
        Data Tools: pandas, numpy, matplotlib, seaborn, Tableau, Power BI
        Databases: PostgreSQL, MongoDB, Redis
        Cloud: AWS, Google Cloud, Azure
        Statistics: Hypothesis testing, regression analysis, time series
        """,
        "education": """
        M.S. in Data Science, University of Technology (2018)
        B.S. in Computer Science, State University (2016)
        """,
    }

    # Sample Job Description
    sample_jd = """
    Senior Machine Learning Engineer
    
    We are looking for an experienced ML Engineer to join our AI team.
    
    Requirements:
    - 3+ years experience in machine learning and data science
    - Strong programming skills in Python
    - Experience with deep learning frameworks (TensorFlow, PyTorch)
    - Knowledge of statistical methods and data analysis
    - Experience with cloud platforms (AWS, GCP)
    - Understanding of MLOps and model deployment
    - Strong problem-solving and analytical skills
    
    Responsibilities:
    - Design and implement machine learning models
    - Optimize model performance and scalability
    - Collaborate with data scientists and engineers
    - Deploy models to production environments
    """

    print("🚀 Starting Domain-Agnostic Fundamental Interview Test")
    print("=" * 60)

    # Start interview
    session_id = "test_session_123"
    opening_message, session_info = interview_system.start_interview(
        session_id=session_id,
        candidate_name="Alex Johnson",
        position="Senior Machine Learning Engineer",
        cv_content=sample_cv,
        jd_content=sample_jd,
    )

    print(f"📋 Session Info:")
    for key, value in session_info.items():
        print(f"  {key}: {value}")
    print()

    print(f"💬 Opening Message:")
    print(f"  {opening_message}")
    print()

    # Simulate interview conversation
    conversation_count = 0
    max_questions = 5  # Limit for demo

    while conversation_count < max_questions:
        print(f"❓ Question {conversation_count + 1}:")
        print("-" * 40)

        # Get next question
        question, question_info = interview_system.get_next_interaction(session_id)

        print(f"Interviewer: {question}")
        print()
        print(f"📊 Question Info:")
        for key, value in question_info.items():
            if key != "progress":
                print(f"  {key}: {value}")
            else:
                print(f"  progress:")
                for pk, pv in value.items():
                    print(f"    {pk}: {pv}")
        print()

        # Simulate candidate answer (in real scenario, this would come from user input)
        sample_answers = [
            "Machine learning is a subset of artificial intelligence that enables computers to learn and make decisions from data without being explicitly programmed. It involves algorithms that can identify patterns in data and make predictions or classifications. The main types include supervised learning for labeled data, unsupervised learning for pattern discovery, and reinforcement learning for decision-making through trial and error.",
            "Deep learning uses neural networks with multiple hidden layers to automatically learn complex patterns from data. Unlike traditional machine learning that requires manual feature engineering, deep learning can automatically extract features from raw data. It's particularly effective for image recognition, natural language processing, and other complex tasks where the relationships between inputs and outputs are highly non-linear.",
            "Statistical hypothesis testing is a method to make inferences about population parameters based on sample data. You start with a null hypothesis and an alternative hypothesis, collect data, calculate a test statistic, and compare it to a critical value or p-value to determine if you can reject the null hypothesis. Common tests include t-tests for means, chi-square tests for categorical data, and ANOVA for comparing multiple groups.",
            "Model overfitting occurs when a machine learning model learns the training data too well, including noise and irrelevant details, making it perform poorly on new, unseen data. Signs include high training accuracy but low validation accuracy. Prevention methods include cross-validation, regularization techniques like L1/L2, early stopping, dropout in neural networks, and using more training data.",
            "Cloud computing provides scalable infrastructure for machine learning through services like compute instances, storage, and managed ML platforms. Benefits include automatic scaling, reduced infrastructure management, access to specialized hardware like GPUs/TPUs, and managed services for model training and deployment. Challenges include data security, vendor lock-in, cost management, and latency for real-time applications.",
        ]

        if conversation_count < len(sample_answers):
            candidate_answer = sample_answers[conversation_count]
            print(f"Candidate: {candidate_answer}")
            print()

            # Process the answer
            next_question, next_info = interview_system.get_next_interaction(
                session_id, candidate_answer
            )

            conversation_count += 1

            if next_info.get("completed"):
                print("✅ Interview completed!")
                break
        else:
            conversation_count += 1

    # Get final session status
    print("\n" + "=" * 60)
    print("📊 Final Session Status:")
    final_status = interview_system.get_session_status(session_id)
    for key, value in final_status.items():
        if isinstance(value, list):
            print(f"  {key}: {', '.join(value) if value else 'None'}")
        else:
            print(f"  {key}: {value}")

    # Export session data
    print("\n" + "=" * 60)
    print("📁 Session Export:")
    export_data = interview_system.export_session_data(session_id)

    print(f"Technical Analysis:")
    tech_analysis = export_data.get("technical_analysis", {})
    print(f"  CV Topics: {', '.join(tech_analysis.get('extracted_cv_topics', [])[:5])}")
    print(f"  JD Topics: {', '.join(tech_analysis.get('extracted_jd_topics', [])[:5])}")
    print(f"  Relevant Topics: {', '.join(tech_analysis.get('relevant_topics', []))}")
    print(
        f"  Technical Domains: {', '.join(tech_analysis.get('technical_domains', []))}"
    )

    print(f"\nInterview Summary:")
    summary = export_data.get("interview_summary", {})
    for key, value in summary.items():
        if isinstance(value, list):
            print(f"  {key}: {', '.join(value) if value else 'None'}")
        else:
            print(f"  {key}: {value}")

    print("\n✨ Test completed successfully!")


if __name__ == "__main__":
    test_fundamental_interview()
