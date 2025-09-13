"""
Main interview session manager with natural conversation flow.
"""

import re
import uuid
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict

from ..config.settings import InterviewConfig, LLMConfig
from ..llm.factory import LLMFactory
from ..document.loader import DocumentLoader
from ..evaluation.scorer import EvaluationScorer
from .prompt_based_question_generator import (
    PromptBasedQuestionGenerator as QuestionGenerator,
    ConversationContext,
    QuestionMetadata,
)


@dataclass
class InterviewSession:
    """Represents an active interview session with natural conversation flow."""

    session_id: str
    cv_path: str
    jd_path: str
    reference_paths: List[str]
    questions_asked: int = 0
    is_complete: bool = False
    interview_history: str = ""
    interview_data: List[Dict[str, Any]] = None
    conversation_context: Optional[ConversationContext] = None
    current_question: Optional[str] = None
    current_question_metadata: Optional[QuestionMetadata] = None

    def __post_init__(self):
        if self.interview_data is None:
            self.interview_data = []


class InterviewSessionManager:
    """Manages interview sessions with natural conversation flow."""

    def __init__(self, config: InterviewConfig, llm_config: LLMConfig):
        self.config = config
        self.llm_config = llm_config
        self.sessions: Dict[str, InterviewSession] = {}

        # Initialize LLM
        self.llm = LLMFactory.create(llm_config)

        # Initialize components
        self.question_generator = QuestionGenerator(self.llm)
        self.evaluation_scorer = EvaluationScorer(self.llm, config.embedding_model)

    def create_session(
        self, cv_path: str, jd_path: str, reference_paths: List[str]
    ) -> Dict[str, Any]:
        """Create a new interview session with natural conversation flow."""
        session_id = str(uuid.uuid4())

        try:
            # Load documents
            document_loader = DocumentLoader(cv_path, jd_path, reference_paths)

            # Validate documents
            validation = document_loader.validate_documents()
            if not all(validation.values()):
                return {"error": "Document validation failed", "validation": validation}

            # Get resume sections
            resume_sections = document_loader.get_cv_sections()

            # Get job description text
            job_description = document_loader.get_jd_text()

            # Initialize conversation context
            conversation_context = self.question_generator.initialize_conversation(
                resume_sections, job_description
            )

            # Generate the first question
            first_question, first_metadata = self.question_generator.get_next_question(
                conversation_context
            )

            # Create session
            session = InterviewSession(
                session_id=session_id,
                cv_path=cv_path,
                jd_path=jd_path,
                reference_paths=reference_paths,
                conversation_context=conversation_context,
                current_question=first_question,
                current_question_metadata=first_metadata,
            )

            self.sessions[session_id] = session

            return {
                "session_id": session_id,
                "first_question": first_question,
                "question_metadata": asdict(first_metadata),
                "conversation_context": {
                    "candidate_skill_level": conversation_context.candidate_skill_level,
                    "current_topic": conversation_context.current_topic,
                },
            }

        except Exception as e:
            return {"error": f"Failed to create session: {str(e)}"}

    def submit_answer(
        self, session_id: str, question: str, answer: str
    ) -> Dict[str, Any]:
        """Submit an answer and get evaluation/next question using natural conversation flow."""
        session = self._get_session(session_id)
        if not session:
            return {"error": "Session not found"}

        if session.is_complete:
            return {"error": "Interview is already complete"}

        try:
            # Load document context for evaluation
            document_loader = DocumentLoader(
                session.cv_path, session.jd_path, session.reference_paths
            )

            # Generate expected answer for comparison
            context = self._get_relevant_context(question, document_loader)
            expected_answer = self._generate_expected_answer(question, context)

            # Evaluate the answer
            evaluation = self.evaluation_scorer.evaluate_answer(
                question=question,
                user_answer=answer,
                expected_answer=expected_answer,
                context=context,
            )

            # Record the interaction
            session.interview_history += f"Q: {question}\nA: {answer}\n\n"
            session.questions_asked += 1

            session.interview_data.append(
                {
                    "question": question,
                    "answer": answer,
                    "evaluation": asdict(evaluation),
                    "question_metadata": (
                        asdict(session.current_question_metadata)
                        if session.current_question_metadata
                        else None
                    ),
                    "timestamp": self._get_timestamp(),
                }
            )

            # Generate next question using natural conversation flow
            next_question, next_metadata = self.question_generator.get_next_question(
                session.conversation_context,
                last_answer=answer,
                answer_evaluation=asdict(evaluation),
            )

            # Update session with next question
            session.current_question = next_question
            session.current_question_metadata = next_metadata

            # Check if interview should continue
            should_continue = self._should_continue_interview(session)

            if not should_continue:
                session.is_complete = True
                final_evaluation = self._generate_final_evaluation(session)

                return {
                    "interview_complete": True,
                    "current_evaluation": asdict(evaluation),
                    "final_evaluation": final_evaluation,
                    "conversation_summary": self._generate_conversation_summary(
                        session
                    ),
                }
            else:
                return {
                    "interview_complete": False,
                    "current_evaluation": asdict(evaluation),
                    "next_question": next_question,
                    "question_metadata": asdict(next_metadata),
                    "conversation_context": {
                        "current_topic": session.conversation_context.current_topic,
                        "depth_level": session.conversation_context.depth_level.value,
                        "topics_covered": session.conversation_context.topics_covered,
                        "candidate_skill_level": session.conversation_context.candidate_skill_level,
                        "conversation_energy": session.conversation_context.conversation_energy,
                    },
                    "progress": {
                        "questions_asked": session.questions_asked,
                        "estimated_remaining": max(
                            0, self.config.min_questions - session.questions_asked
                        ),
                    },
                }

        except Exception as e:
            return {"error": f"Failed to process answer: {str(e)}"}

    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get current status of an interview session."""
        session = self._get_session(session_id)
        if not session:
            return {"error": "Session not found"}

        return {
            "session_id": session_id,
            "is_complete": session.is_complete,
            "questions_asked": session.questions_asked,
            "current_topic": (
                session.conversation_context.current_topic
                if session.conversation_context
                else "unknown"
            ),
            "topics_covered": (
                session.conversation_context.topics_covered
                if session.conversation_context
                else []
            ),
            "candidate_skill_level": (
                session.conversation_context.candidate_skill_level
                if session.conversation_context
                else "unknown"
            ),
            "conversation_energy": (
                session.conversation_context.conversation_energy
                if session.conversation_context
                else "neutral"
            ),
            "progress_percentage": min(
                100, (session.questions_asked / self.config.min_questions) * 100
            ),
        }

    def get_next_question(self, session_id: str) -> Dict[str, Any]:
        """Get the current/next question for the interview session."""
        session = self._get_session(session_id)
        if not session:
            return {"error": "Session not found"}

        if session.is_complete:
            return {"interview_complete": True}

        if not session.current_question:
            return {"error": "No current question available"}

        return {
            "question": session.current_question,
            "question_metadata": (
                asdict(session.current_question_metadata)
                if session.current_question_metadata
                else None
            ),
            "context": {
                "current_topic": (
                    session.conversation_context.current_topic
                    if session.conversation_context
                    else "unknown"
                ),
                "depth_level": (
                    session.conversation_context.depth_level.value
                    if session.conversation_context
                    else "beginner"
                ),
                "candidate_skill_level": (
                    session.conversation_context.candidate_skill_level
                    if session.conversation_context
                    else "unknown"
                ),
            },
            "interview_complete": False,
        }

    def end_session(self, session_id: str) -> Dict[str, Any]:
        """Manually end a session and generate final evaluation."""
        session = self._get_session(session_id)
        if not session:
            return {"error": "Session not found"}

        session.is_complete = True
        final_evaluation = self._generate_final_evaluation(session)

        return {"session_ended": True, "final_evaluation": final_evaluation}

    def _should_continue_interview(self, session: InterviewSession) -> bool:
        """Determine if the interview should continue based on various factors."""

        # Basic length constraints
        if session.questions_asked >= self.config.max_questions:
            return False

        # Always continue if we haven't asked at least 8 questions (increased from min_questions)
        if session.questions_asked < 8:
            return True

        # Check conversation quality only after 8+ questions
        if len(session.interview_data) >= 2:
            recent_scores = [
                item["evaluation"]["overall_score"]
                for item in session.interview_data[-2:]
            ]
            avg_recent_score = sum(recent_scores) / len(recent_scores)

            # If conversation is going very poorly, end early (but only after 8 questions)
            if avg_recent_score < 0.3 and session.questions_asked >= 10:
                return False

            # If conversation is excellent and we've covered enough topics, can end
            # But require at least 10 questions and 5 topics
            if (
                avg_recent_score > 0.8
                and len(session.conversation_context.topics_covered) >= 5
                and session.questions_asked >= 10
            ):
                return False

        # Check topic coverage - require more topics before ending
        if len(session.conversation_context.topics_covered) >= 8:
            return False

        return True

    def _generate_conversation_summary(
        self, session: InterviewSession
    ) -> Dict[str, Any]:
        """Generate a summary of the conversation flow and dynamics."""

        if not session.interview_data:
            return {"error": "No conversation data available"}

        # Analyze conversation patterns
        scores = [
            item["evaluation"]["overall_score"] for item in session.interview_data
        ]
        topics_explored = session.conversation_context.topics_covered

        conversation_trend = "neutral"
        if len(scores) >= 3:
            early_avg = (
                sum(scores[: len(scores) // 2]) / (len(scores) // 2) if scores else 0
            )
            late_avg = (
                sum(scores[len(scores) // 2 :]) / (len(scores) - len(scores) // 2)
                if scores
                else 0
            )

            if late_avg > early_avg + 0.15:
                conversation_trend = "improving"
            elif late_avg < early_avg - 0.15:
                conversation_trend = "declining"

        return {
            "topics_covered": topics_explored,
            "conversation_trend": conversation_trend,
            "final_skill_assessment": session.conversation_context.candidate_skill_level,
            "total_questions": session.questions_asked,
            "average_score": sum(scores) / len(scores) if scores else 0,
            "conversation_energy": session.conversation_context.conversation_energy,
        }

    def _get_session(self, session_id: str) -> Optional[InterviewSession]:
        """Get session by ID."""
        return self.sessions.get(session_id)

    def _get_relevant_context(
        self, question: str, document_loader: DocumentLoader
    ) -> str:
        """Get relevant context for a question."""
        # Simplified context retrieval - just return combined document text
        return (
            document_loader.cv_text[:500]
            + "\n"  # First 500 chars of CV
            + document_loader.jd_text[:500]  # First 500 chars of JD
        )

    def _generate_expected_answer(self, question: str, context: str) -> str:
        """Generate expected answer for comparison."""
        # Simplified expected answer generation
        prompt = f"Answer this interview question based on the context:\n\nContext: {context}\n\nQuestion: {question}\n\nAnswer:"

        try:
            response = self.llm.complete(prompt)
            return response.text
        except Exception as e:
            return f"Standard answer for: {question}"

    def _generate_final_evaluation(self, session: InterviewSession) -> Dict[str, Any]:
        """Generate comprehensive final evaluation."""
        if not session.interview_data:
            return {"error": "No interview data available for evaluation"}

        # Calculate aggregate scores
        evaluations = [item["evaluation"] for item in session.interview_data]

        avg_scores = {
            "relevance": sum(e["relevance_score"] for e in evaluations)
            / len(evaluations),
            "technical_accuracy": sum(
                e["technical_accuracy_score"] for e in evaluations
            )
            / len(evaluations),
            "communication": sum(e["communication_score"] for e in evaluations)
            / len(evaluations),
            "overall": sum(e["overall_score"] for e in evaluations) / len(evaluations),
        }

        # Generate qualitative assessment
        prompt = f"""
        Provide a comprehensive interview evaluation based on the following data:
        
        Number of questions: {session.questions_asked}
        Average scores:
        - Relevance: {avg_scores['relevance']:.2f}
        - Technical Accuracy: {avg_scores['technical_accuracy']:.2f}
        - Communication: {avg_scores['communication']:.2f}
        - Overall: {avg_scores['overall']:.2f}
        
        Interview transcript:
        {session.interview_history}
        
        Provide a structured evaluation covering:
        1. Overall assessment
        2. Key strengths observed
        3. Areas for improvement
        4. Recommendation (hire/no hire/further assessment)
        """

        try:
            response = self.llm.complete(prompt)
            qualitative_assessment = response.text
        except Exception as e:
            qualitative_assessment = f"Error generating assessment: {e}"

        return {
            "quantitative_scores": avg_scores,
            "qualitative_assessment": qualitative_assessment,
            "interview_metadata": {
                "questions_asked": session.questions_asked,
                "session_duration": "N/A",  # Could track actual duration
                "completion_status": (
                    "complete" if session.is_complete else "incomplete"
                ),
            },
        }

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime

        return datetime.now().isoformat()
