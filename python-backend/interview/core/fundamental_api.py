"""
Integration wrapper for the domain-agnostic fundamental interview system.
This provides a simple interface to integrate with the existing interview API.
"""

from typing import Dict, List, Optional, Tuple, Any
from .fundamental_interview_system import FundamentalInterviewSystem
from ..llm.factory import LLMFactory


class FundamentalInterviewAPI:
    """Simple API wrapper for fundamental interviews."""

    def __init__(self, llm_provider: str = "gemini"):
        """Initialize with specified LLM provider."""
        self.llm = LLMFactory.create_llm(llm_provider)
        self.interview_system = FundamentalInterviewSystem(self.llm)

    def start_fundamental_interview(
        self,
        candidate_name: str,
        position: str,
        cv_sections: Dict[str, str],
        job_description: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Start a new fundamental interview session.

        Args:
            candidate_name: Name of the candidate
            position: Position being interviewed for
            cv_sections: Dictionary with CV sections (experience, skills, education, etc.)
            job_description: Full job description text
            session_id: Optional session ID (will generate if not provided)

        Returns:
            Dictionary with opening message and session info
        """

        if not session_id:
            import uuid

            session_id = f"fundamental_{uuid.uuid4().hex[:12]}"

        try:
            opening_message, session_info = self.interview_system.start_interview(
                session_id=session_id,
                candidate_name=candidate_name,
                position=position,
                cv_content=cv_sections,
                jd_content=job_description,
            )

            return {
                "success": True,
                "session_id": session_id,
                "opening_message": opening_message,
                "session_info": session_info,
                "next_action": "get_first_question",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to start fundamental interview",
            }

    def get_next_question(
        self, session_id: str, previous_answer: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get the next question in the interview.

        Args:
            session_id: Interview session ID
            previous_answer: Candidate's answer to previous question (optional)

        Returns:
            Dictionary with next question and session status
        """

        try:
            question, question_info = self.interview_system.get_next_interaction(
                session_id=session_id, candidate_answer=previous_answer
            )

            if question_info.get("completed"):
                return {
                    "success": True,
                    "session_id": session_id,
                    "interview_completed": True,
                    "final_message": question,
                    "summary": question_info.get("summary", {}),
                    "next_action": "interview_complete",
                }
            else:
                return {
                    "success": True,
                    "session_id": session_id,
                    "question": question,
                    "question_info": question_info,
                    "interview_completed": False,
                    "next_action": "await_answer",
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to get next question",
            }

    def submit_answer(self, session_id: str, answer: str) -> Dict[str, Any]:
        """
        Submit an answer and get the next question.

        Args:
            session_id: Interview session ID
            answer: Candidate's answer

        Returns:
            Dictionary with next question or completion status
        """

        return self.get_next_question(session_id, answer)

    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get current session status."""

        try:
            status = self.interview_system.get_session_status(session_id)
            return {"success": True, "status": status}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def end_interview(
        self, session_id: str, reason: str = "completed"
    ) -> Dict[str, Any]:
        """End the interview session."""

        try:
            result = self.interview_system.end_session(session_id, reason)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_interview_data(self, session_id: str) -> Dict[str, Any]:
        """Export complete interview data."""

        try:
            data = self.interview_system.export_session_data(session_id)
            return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Example usage functions
def demo_data_science_interview():
    """Demo with a data science candidate."""

    api = FundamentalInterviewAPI()

    cv_data = {
        "experience": "Senior Data Scientist with 5 years experience in ML, deep learning, and statistical analysis",
        "skills": "Python, TensorFlow, PyTorch, SQL, AWS, statistical modeling, data visualization",
        "education": "PhD in Statistics, MS in Computer Science",
    }

    jd_data = "Senior ML Engineer position requiring expertise in machine learning, deep learning, and production ML systems"

    # Start interview
    result = api.start_fundamental_interview(
        candidate_name="Dr. Sarah Chen",
        position="Senior ML Engineer",
        cv_sections=cv_data,
        job_description=jd_data,
    )

    return result


def demo_web_development_interview():
    """Demo with a web development candidate."""

    api = FundamentalInterviewAPI()

    cv_data = {
        "experience": "Full-stack developer with 3 years experience in React, Node.js, and cloud deployment",
        "skills": "JavaScript, React, Node.js, MongoDB, AWS, Docker, REST APIs",
        "education": "BS in Computer Science",
    }

    jd_data = "Full-stack Developer position requiring React, Node.js, database design, and scalable web applications"

    # Start interview
    result = api.start_fundamental_interview(
        candidate_name="Alex Rodriguez",
        position="Full-stack Developer",
        cv_sections=cv_data,
        job_description=jd_data,
    )

    return result


def demo_finance_tech_interview():
    """Demo with a finance technology candidate."""

    api = FundamentalInterviewAPI()

    cv_data = {
        "experience": "Quantitative Analyst with 4 years in algorithmic trading and risk modeling",
        "skills": "Python, R, C++, financial modeling, derivatives pricing, time series analysis, Monte Carlo methods",
        "education": "MS in Financial Engineering, BS in Mathematics",
    }

    jd_data = "Senior Quant Developer for developing trading algorithms, risk management systems, and quantitative models"

    # Start interview
    result = api.start_fundamental_interview(
        candidate_name="Michael Thompson",
        position="Senior Quant Developer",
        cv_sections=cv_data,
        job_description=jd_data,
    )

    return result


if __name__ == "__main__":
    print("🧪 Testing Domain-Agnostic Fundamental Interview API")
    print("=" * 60)

    # Test different domains
    domains = [
        ("Data Science", demo_data_science_interview),
        ("Web Development", demo_web_development_interview),
        ("Finance Technology", demo_finance_tech_interview),
    ]

    for domain_name, demo_func in domains:
        print(f"\n📊 {domain_name} Interview Demo:")
        print("-" * 40)

        try:
            result = demo_func()
            if result["success"]:
                print(f"✅ Started successfully!")
                print(f"Session ID: {result['session_id']}")
                print(f"Opening: {result['opening_message'][:100]}...")

                # Show extracted info
                session_info = result.get("session_info", {})
                if "extracted_domains" in session_info:
                    print(f"Domains: {', '.join(session_info['extracted_domains'])}")
                if "relevant_topics" in session_info:
                    print(
                        f"Relevant Topics: {', '.join(session_info['relevant_topics'][:3])}"
                    )
            else:
                print(f"❌ Failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            print(f"❌ Exception: {e}")

    print(f"\n✨ API Demo completed!")
