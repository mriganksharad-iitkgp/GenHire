"""
Ultra-simplified interview session manager leveraging LLM intelligence.
"""

import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import datetime
import json

from ..config.settings import InterviewConfig, LLMConfig
from ..llm.factory import LLMFactory
from ..document.loader import DocumentLoader
from ..prompts.simplified_prompts import CV_JD_ANALYSIS_PROMPT
from ..utils.llm_response_handler import LLMResponseHandler
from .simplified_question_generator import SimplifiedQuestionGenerator


@dataclass
class SimplifiedInterviewSession:
    """Ultra-simplified interview session."""

    session_id: str
    cv_path: str
    jd_path: str
    reference_paths: List[str]
    questions_asked: int = 0
    is_complete: bool = False
    interview_history: str = ""
    analysis: Dict[str, Any] = None

    def __post_init__(self):
        if self.analysis is None:
            self.analysis = {}


class SimplifiedInterviewSessionManager:
    """Ultra-simplified session manager with only three core functions."""

    def __init__(self, config: InterviewConfig, llm_config: LLMConfig):
        self.config = config
        self.llm_config = llm_config
        self.sessions: Dict[str, SimplifiedInterviewSession] = {}
        self.llm = LLMFactory.create(llm_config)
        self.question_generator = SimplifiedQuestionGenerator(self.llm)
        self.max_questions = 10

    def create_session(
        self, cv_path: str, jd_path: str, reference_paths: List[str]
    ) -> Dict[str, Any]:
        """Create session, analyze CV-JD, and generate first question using prompts."""
        session_id = str(uuid.uuid4())

        try:
            # Load documents
            document_loader = DocumentLoader(cv_path, jd_path, reference_paths)
            validation = document_loader.validate_documents()
            if not all(validation.values()):
                return {"error": "Document validation failed", "validation": validation}

            cv_text = document_loader.get_cv_text()
            jd_text = document_loader.get_jd_text()

            # Analyze CV and JD using prompt
            analysis = self._analyze_cv_jd(cv_text, jd_text)

            # Generate first question using question generator
            first_question = self.question_generator.generate_first_question(analysis)

            # Create session
            session = SimplifiedInterviewSession(
                session_id=session_id,
                cv_path=cv_path,
                jd_path=jd_path,
                reference_paths=reference_paths,
                analysis=analysis,
            )
            self.sessions[session_id] = session

            return {
                "session_id": session_id,
                "first_question": first_question,
                "analysis": analysis,
            }

        except Exception as e:
            return {"error": f"Failed to create session: {str(e)}"}

    def submit_answer(
        self, session_id: str, question: str, answer: str
    ) -> Dict[str, Any]:
        """Submit answer and get next question with LLM handling all logic."""
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        if session.is_complete:
            return {"error": "Interview is already complete"}

        try:
            # Add to interview history
            session.interview_history += f"Q: {question}\nA: {answer}\n\n"
            session.questions_asked += 1

            # Check if interview should end
            if session.questions_asked >= self.max_questions:
                session.is_complete = True
                return {
                    "interview_complete": True,
                    "message": "Thank you for your time. The interview is now complete.",
                }

            # Generate next question using question generator
            next_response = self.question_generator.generate_next_question(
                session.interview_history,
                answer,
                session.analysis,
                session.questions_asked + 1,
                self.max_questions,
            )

            return {
                "interview_complete": False,
                "next_question": next_response,
                "progress": {
                    "questions_asked": session.questions_asked,
                    "estimated_remaining": max(
                        0, self.max_questions - session.questions_asked
                    ),
                },
            }

        except Exception as e:
            return {"error": f"Failed to process answer: {str(e)}"}

    def get_next_question(self, session_id: str) -> Dict[str, Any]:
        """Get the current status and any pending question for the session."""
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        if session.is_complete:
            return {"interview_complete": True}

        return {
            "questions_asked": session.questions_asked,
            "max_questions": self.max_questions,
            "is_complete": session.is_complete,
        }

    def _analyze_cv_jd(self, cv_text: str, jd_text: str) -> Dict[str, Any]:
        """Analyze CV and JD using the standardized prompt."""
        try:
            prompt = CV_JD_ANALYSIS_PROMPT.format(cv_text=cv_text, jd_text=jd_text)
            response = self.llm.complete(prompt)
            return LLMResponseHandler.parse_json_response(response)
        except Exception as e:
            raise Exception(f"Failed to analyze CV and JD: {str(e)}")
        try:
            prompt = CV_JD_ANALYSIS_PROMPT.format(cv_text=cv_text, jd_text=jd_text)
            response = self.llm.complete(prompt)
            print("CV-JD Analysis Response Object:", response.text)

            # Extract text from LLM response object
            response_text = (
                response.text if hasattr(response, "text") else str(response)
            )
            print("CV-JD Analysis Response in text:", response_text)

            return json.loads(response_text)
        except (json.JSONDecodeError, Exception) as e:
            raise Exception(f"Failed to analyze CV and JD: {str(e)}")
