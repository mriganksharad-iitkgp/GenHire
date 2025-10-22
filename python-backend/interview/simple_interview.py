"""
Simplified interview module entry point.
This provides a clean interface for the interview system without complex dependencies.
"""

from .core.simplified_session_manager import SimplifiedInterviewSessionManager
from .config.settings import InterviewConfig, LLMConfig, LLMProvider


class SimpleInterviewSystem:
    """
    Simplified interview system that focuses on CV-JD based question generation
    with natural conversation flow and minimal acknowledgments.
    """

    def __init__(self, groq_api_key: str = None, openai_api_key: str = None):
        """Initialize with API keys."""

        # Use default configurations
        self.interview_config = InterviewConfig()

        # Configure LLM - prefer OpenAI if available, fallback to Groq
        if openai_api_key:
            self.llm_config = LLMConfig(
                provider=LLMProvider.OPENAI,
                model_name="gpt-4o-mini",
                api_key=openai_api_key,
            )
        elif groq_api_key:
            self.llm_config = LLMConfig(
                provider=LLMProvider.GROQ,
                model_name="llama-3.3-70b-versatile",
                api_key=groq_api_key,
            )
        else:
            raise ValueError("Either groq_api_key or openai_api_key must be provided")

        # Initialize the simplified session manager
        self.session_manager = SimplifiedInterviewSessionManager(
            config=self.interview_config, llm_config=self.llm_config
        )

    def create_session(
        self, cv_path: str, jd_path: str, reference_paths: list = None
    ) -> dict:
        """Create a new interview session."""
        if reference_paths is None:
            reference_paths = []

        return self.session_manager.create_session(cv_path, jd_path, reference_paths)

    def submit_answer(self, session_id: str, question: str, answer: str) -> dict:
        """Submit an answer and get the next question."""
        return self.session_manager.submit_answer(session_id, question, answer)

    def get_session_status(self, session_id: str) -> dict:
        """Get current session status."""
        session = self.session_manager.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        return {
            "session_id": session_id,
            "is_complete": session.is_complete,
            "questions_asked": session.questions_asked,
            "job_role": session.analysis.get("job_role", ""),
            "experience_level": session.analysis.get("experience_level", ""),
            "key_skills": session.analysis.get("key_skills", []),
            "primary_domain": session.analysis.get("primary_domain", ""),
        }

    def end_session(self, session_id: str) -> dict:
        """End the interview session and get final evaluation."""
        session = self.session_manager.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        session.is_complete = True

        # Generate simple evaluation from interview history
        evaluation = {
            "summary": "Interview completed successfully.",
            "questions_asked": session.questions_asked,
            "interview_history": session.interview_history,
            "final_note": f"Candidate completed {session.questions_asked} questions for {session.analysis.get('job_role', 'the role')}.",
        }

        return {
            "session_ended": True,
            "evaluation": evaluation,
            "total_questions": session.questions_asked,
        }


# Backward compatibility - maintain the same interface as before
class InterviewSessionManager:
    """Backward compatibility wrapper for the existing app.py interface."""

    def __init__(self, config=None, llm_config=None):
        # Extract API key from llm_config or environment
        import os

        groq_api_key = None
        openai_api_key = None

        if llm_config:
            if llm_config.provider == LLMProvider.GROQ:
                groq_api_key = llm_config.api_key
            elif llm_config.provider == LLMProvider.OPENAI:
                openai_api_key = llm_config.api_key

        # Fallback to environment variables
        if not groq_api_key and not openai_api_key:
            groq_api_key = os.getenv("GROQ_API_KEY")
            openai_api_key = os.getenv("OPENAI_API_KEY")

        self.simple_system = SimpleInterviewSystem(
            groq_api_key=groq_api_key, openai_api_key=openai_api_key
        )

        # Store sessions for backward compatibility
        self.sessions = {}

    def create_session(self, cv_path: str, jd_path: str, reference_paths: list) -> dict:
        """Create session with backward compatibility."""
        result = self.simple_system.create_session(cv_path, jd_path, reference_paths)

        if "session_id" in result:
            # Store minimal session info for backward compatibility
            session_id = result["session_id"]
            self.sessions[session_id] = {
                "cv_path": cv_path,
                "jd_path": jd_path,
                "reference_paths": reference_paths,
                "is_complete": False,
                "interview_data": [],
            }

            # Transform response to match expected format
            return {
                "session_id": session_id,
                "first_question": result["first_question"],
                "similarity_score": 0.8,  # Placeholder
                "analysis": result.get("analysis", {}),
            }

        return result

    def submit_answer(self, session_id: str, question: str, answer: str) -> dict:
        """Submit answer with backward compatibility."""
        result = self.simple_system.submit_answer(session_id, question, answer)

        # Update local session tracking
        if session_id in self.sessions:
            self.sessions[session_id]["interview_data"].append(
                {"question": question, "answer": answer}
            )

            if result.get("interview_complete"):
                self.sessions[session_id]["is_complete"] = True

        return result

    def get_next_question(self, session_id: str) -> dict:
        """Get next question - simplified since questions are generated on answer submission."""
        return {"message": "Use submit_answer to get the next question"}

    def _generate_final_evaluation(self, session_info) -> dict:
        """Generate final evaluation for backward compatibility."""
        return {
            "summary": "Interview completed successfully.",
            "final_score": 85,  # Placeholder score
        }
