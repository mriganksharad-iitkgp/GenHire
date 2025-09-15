"""
Maimport uuid
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict

from evaluation_model.rubrics_eval.evaluation_system import EvaluationSystem
from ..config.settings import InterviewConfig, LLMConfig
from ..llm.factory import LLMFactory
from ..document.loader import DocumentLoaderview session manager with natural conversation flow.
"""

import re
import uuid
import sys
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict

from evaluation_model.rubrics_eval.evaluation_system import EvaluationSystem
from ..config.settings import InterviewConfig, LLMConfig
from ..llm.factory import LLMFactory
from ..document.loader import DocumentLoader
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

        # Initialize evaluation system if available
        self.evaluation_system = EvaluationSystem()

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
            # Evaluate the answer using rubrics-eval system
            if self.evaluation_system:
                try:
                    # evaluate_single_answer returns (score, details)
                    score, details = self.evaluation_system.evaluate_single_answer(
                        question=question, student_answer=answer
                    )

                    # Convert single score to expected format
                    evaluation = self._convert_single_score_to_standard_format(
                        score, question, answer
                    )
                except Exception as e:
                    print(f"Rubrics evaluation failed: {e}")
                    # Fallback to basic evaluation
                    evaluation = self._fallback_evaluation(question, answer)
            else:
                # Fallback to basic evaluation
                evaluation = self._fallback_evaluation(question, answer)

            # Record the interaction
            session.interview_history += f"Q: {question}\nA: {answer}\n\n"
            session.questions_asked += 1

            session.interview_data.append(
                {
                    "question": question,
                    "answer": answer,
                    "evaluation": evaluation,  # evaluation is already a dict
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
                answer_evaluation=evaluation,  # evaluation is already a dict
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
                    "current_evaluation": evaluation,  # evaluation is already a dict
                    "final_evaluation": final_evaluation,
                    "conversation_summary": self._generate_conversation_summary(
                        session
                    ),
                }
            else:
                return {
                    "interview_complete": False,
                    "current_evaluation": evaluation,  # evaluation is already a dict
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

    def _convert_single_score_to_standard_format(
        self, score: float, question: str, answer: str
    ) -> Dict[str, Any]:
        """Convert single rubrics-eval score to the standard evaluation format."""

        # Rubrics evaluation returns scores from 0-100, we need to normalize to 0-1
        if score > 1.0:  # Assuming it's in 0-100 range
            normalized_score = max(0.0, min(1.0, score / 100.0))
        else:  # Already in 0-1 range
            normalized_score = max(0.0, min(1.0, score))

        # Generate basic reasoning based on score
        if normalized_score >= 0.8:
            quality = "excellent"
        elif normalized_score >= 0.6:
            quality = "good"
        elif normalized_score >= 0.4:
            quality = "satisfactory"
        elif normalized_score >= 0.2:
            quality = "needs improvement"
        else:
            quality = "poor"

        reasoning = f"Answer evaluated using rubrics-based system. Overall quality: {quality} (score: {normalized_score:.2f})"

        return {
            "relevance_score": normalized_score,
            "technical_accuracy_score": normalized_score,
            "communication_score": normalized_score,
            "overall_score": normalized_score,
            "reasoning": reasoning,
            "evaluation_method": "rubrics-eval",
        }

    def _fallback_evaluation(self, question: str, answer: str) -> Dict[str, Any]:
        """Provide a basic fallback evaluation when rubrics-eval is not available."""

        # Basic scoring based on answer length and content
        answer_length = len(answer.strip())

        if answer_length == 0:
            score = 0.0
            reasoning = "No answer provided."
        elif answer_length < 10:
            score = 0.2
            reasoning = "Answer too brief to demonstrate understanding."
        elif answer_length < 50:
            score = 0.4
            reasoning = "Answer provides minimal detail."
        elif answer_length < 150:
            score = 0.6
            reasoning = "Answer provides adequate detail."
        else:
            score = 0.8
            reasoning = "Answer provides comprehensive detail."

        # Simple keyword matching for technical relevance
        question_lower = question.lower()
        answer_lower = answer.lower()

        # Extract potential technical terms from question
        technical_keywords = []
        for word in question_lower.split():
            if len(word) > 3 and word not in [
                "what",
                "how",
                "why",
                "when",
                "where",
                "which",
                "explain",
                "describe",
            ]:
                technical_keywords.append(word)

        # Check if answer mentions relevant terms
        relevance_boost = 0
        for keyword in technical_keywords[:5]:  # Check top 5 keywords
            if keyword in answer_lower:
                relevance_boost += 0.1

        final_score = min(1.0, score + relevance_boost)

        return {
            "relevance_score": final_score,
            "technical_accuracy_score": final_score,
            "communication_score": score,  # Based on length/structure
            "overall_score": final_score,
            "reasoning": f"{reasoning} Relevance check: {relevance_boost:.1f} boost applied.",
            "evaluation_method": "fallback",
        }
