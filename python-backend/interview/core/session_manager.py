"""
Interview session manager with natural conversation flow.
"""

import re
import uuid
import sys
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
import threading

from evaluation_model.rubrics_eval.evaluation_system import EvaluationSystem
from ..config.settings import InterviewConfig, LLMConfig
from ..llm.factory import LLMFactory
from ..document.loader import DocumentLoader
from .prompt_based_question_generator import (
    PromptBasedQuestionGenerator as QuestionGenerator,
    ConversationContext,
    QuestionMetadata,
    InterviewPhase,
)
from .cost_tracker import CostTracker
from utils.ai_detection import check_ai_content


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
    interview_data: List[Dict[str, Any]] = field(default_factory=list)
    conversation_context: Optional[ConversationContext] = None
    current_question: Optional[str] = None
    current_question_metadata: Optional[QuestionMetadata] = None
    proctoring_config: Optional[dict] = None
    init_event: Optional[threading.Event] = None


class InterviewSessionManager:
    """Manages interview sessions with natural conversation flow."""

    def __init__(self, config: InterviewConfig, llm_config: LLMConfig):
        self.config = config
        self.llm_config = llm_config
        self.sessions: Dict[str, InterviewSession] = {}

        # Build fallback LLM chain from available API keys
        self.llm = self._create_fallback_llm(llm_config)

        # Initialize components
        self.question_generator = QuestionGenerator(self.llm, config=self.config)

        # Initialize evaluation system if available
        self.evaluation_system = EvaluationSystem()

    @staticmethod
    def _create_fallback_llm(primary_config: LLMConfig):
        """
        Create an LLM with fallback providers from available .env keys.

        Priority: primary_config provider first, then other available providers.
        """
        import os
        from ..config.settings import LLMProvider

        configs = [primary_config]
        seen_providers = {primary_config.provider}

        # Map of provider -> (env_key, default_model)
        fallback_options = [
            (LLMProvider.OPENAI, "OPENAI_API_KEY", "gpt-4o-mini"),
            (LLMProvider.GEMINI, "GOOGLE_API_KEY", "models/gemini-1.5-flash"),
            (LLMProvider.GROQ, "GROQ_API_KEY", "llama-3.3-70b-versatile"),
        ]

        for provider, env_key, default_model in fallback_options:
            if provider in seen_providers:
                continue
            api_key = os.getenv(env_key)
            if api_key:
                configs.append(LLMConfig(
                    provider=provider,
                    model_name=default_model,
                    api_key=api_key,
                    temperature=primary_config.temperature,
                    max_tokens=primary_config.max_tokens,
                    timeout_seconds=primary_config.timeout_seconds,
                ))
                seen_providers.add(provider)

        return LLMFactory.create_with_fallback(configs)


    def create_session(
        self,
        cv_path: str,
        jd_path: str,
        reference_paths: List[str],
        proctoring_config: Optional[dict] = None,
        pre_validated: bool = False,
    ) -> Dict[str, Any]:
        """Create a new interview session with natural conversation flow.

        Args:
            pre_validated: Skip document validation when the caller already wrote
                           the files from trusted DB data (avoids redundant I/O).
        """
        session_id = str(uuid.uuid4())
        cost_tracker = CostTracker()
        cost_tracker.start_session(session_id)
        token = cost_tracker.set_session_context(session_id)

        try:
            # Load documents once — reuse the same loader for validation AND the
            # background context thread so we never read the files twice.
            document_loader = DocumentLoader(cv_path, jd_path, reference_paths)

            # Validate only when the caller hasn't already guaranteed validity.
            if not pre_validated:
                validation = document_loader.validate_documents()
                if not all(validation.values()):
                    return {"error": "Document validation failed", "validation": validation}

            # Hardcoded first question for zero-lag initialization
            first_question = "Hello, I'm Alex. Great to meet you! Could you please give me a brief introduction about yourself and your background?"
            first_metadata = {
                "intent": "ICEBREAKER",
                "difficulty_level": "fresher",
                "expected_depth": "BRIEF",
                "topic_area": "General",
                "prerequisites": [],
                "interview_phase": "INTRODUCTION",
                "source": "fallback"
            }

            # Create session without conversation_context
            session = InterviewSession(
                session_id=session_id,
                cv_path=cv_path,
                jd_path=jd_path,
                reference_paths=reference_paths,
                conversation_context=None,
                current_question=first_question,
                current_question_metadata=first_metadata,
                proctoring_config=proctoring_config or {},
                init_event=threading.Event()
            )

            self.sessions[session_id] = session

            # Start background thread to build context.
            # Pass the already-created loader so the thread reuses the text
            # that was already read from disk — no second file read needed.
            threading.Thread(
                target=self._initialize_context_background,
                args=(session_id, document_loader),
                daemon=True
            ).start()

            return {
                "session_id": session_id,
                "first_question": first_question,
                "question_metadata": first_metadata,
                "conversation_context": {
                    "candidate_skill_level": "unknown",
                    "current_topic": "Introduction",
                    "interview_phase": "INTRODUCTION",
                },
            }

        except Exception as e:
            return {"error": f"Failed to create session: {str(e)}"}
        finally:
            cost_tracker.clear_session_context(token)

    def _initialize_context_background(self, session_id: str, document_loader) -> None:
        """Background task to initialize the conversation context.

        Receives the already-loaded DocumentLoader so it never touches disk again.
        """
        session = self._get_session(session_id)
        if not session:
            return

        try:
            resume_sections = document_loader.get_cv_sections()
            job_description = document_loader.get_jd_text()

            conversation_context = self.question_generator.initialize_conversation(
                resume_sections, job_description
            )
            # The hardcoded first question already serves as the greeting, so skip
            # the GREETING phase in the question generator to prevent a second greeting.
            conversation_context.has_been_greeted = True
            conversation_context.interview_phase = InterviewPhase.EXPERIENTIAL_QUESTIONS
            session.conversation_context = conversation_context
        except Exception as e:
            print(f"Background context init failed: {e}")
        finally:
            if session.init_event:
                session.init_event.set()

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
            cost_tracker = CostTracker()
            token = cost_tracker.set_session_context(session_id)
            provisional_evaluation = self._fallback_evaluation(question, answer)

            def evaluate_answer():
                if not self.evaluation_system:
                    return provisional_evaluation
                try:
                    with ThreadPoolExecutor(max_workers=2) as evaluator_pool:
                        technical_future = evaluator_pool.submit(
                            self.evaluation_system.evaluate_single_answer_fast,
                            question,
                            answer,
                        )
                        communication_future = evaluator_pool.submit(
                            self.evaluation_system.evaluate_communication_score,
                            question,
                            answer,
                        )
                        score, _details = technical_future.result()
                        communication_score = communication_future.result()
                    return self._convert_scores_to_standard_format(
                        technical_score=score,
                        communication_score=communication_score,
                        question=question,
                        answer=answer,
                    )
                except Exception as e:
                    print(f"Evaluation failed: {e}")
                    return provisional_evaluation

            # Wait for background initialization if it's still running
            if getattr(session, 'init_event', None):
                session.init_event.wait(timeout=45.0)

            # Generate next question using natural conversation flow
            if session.conversation_context is None:
                return {"error": "Conversation context not initialized"}

            # live path. Use the provisional score for adaptive topic selection.

            evaluation = provisional_evaluation.copy()

            def bg_evaluate_and_update():
                try:
                    eval_result = evaluate_answer()
                    evaluation.update(eval_result)
                    
                    if session.proctoring_config and session.proctoring_config.get("ai_detection", False):
                        ai_result = check_ai_content(answer)
                        if ai_result:
                            evaluation["ai_probability"] = ai_result.get("score")
                            evaluation["ai_detection_raw"] = ai_result.get("raw_response")
                except Exception as e:
                    print(f"Background evaluation failed: {e}")

            # Run heavy evaluation in background so the UI doesn't lag
            threading.Thread(target=bg_evaluate_and_update, daemon=True).start()

            # Generate next question using natural conversation flow
            try:
                next_question, next_metadata = self.question_generator.get_next_question(
                    session.conversation_context,
                    answer,
                    provisional_evaluation,
                )
            except Exception as e:
                # If we hit quota or all providers fail, gracefully end the interview
                error_str = str(e).lower()
                if "quota" in error_str or "limit" in error_str or "exhaust" in error_str or "failed" in error_str:
                    session.is_complete = True
                    # Record the current answer before ending
                    session.interview_history += f"Q: {question}\nA: {answer}\n\n"
                    session.questions_asked += 1
                    session.interview_data.append(
                        {
                            "question": question,
                            "answer": answer,
                            "evaluation": evaluation,
                            "question_metadata": None,
                            "timestamp": self._get_timestamp(),
                        }
                    )
                    final_evaluation = self._generate_final_evaluation(session)
                    return {
                        "interview_complete": True,
                        "current_evaluation": evaluation,
                        "final_evaluation": final_evaluation,
                        "conversation_summary": self._generate_conversation_summary(session),
                        "quota_exhausted": True,
                        "message": "The interview has ended early due to system capacity limits. Your progress has been saved."
                    }
                raise e

            session.interview_history += f"Q: {question}\nA: {answer}\n\n"
            session.questions_asked += 1
            session.interview_data.append(
                {
                    "question": question,
                    "answer": answer,
                    "evaluation": evaluation,
                    "question_metadata": (
                        asdict(session.current_question_metadata)
                        if hasattr(session.current_question_metadata, "__dataclass_fields__")
                        else session.current_question_metadata
                    ) if session.current_question_metadata else None,
                    "timestamp": self._get_timestamp(),
                }
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
                    "question_metadata": asdict(next_metadata) if hasattr(next_metadata, "__dataclass_fields__") else next_metadata,
                    "conversation_context": {
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
                        "interview_phase": (
                            session.conversation_context.interview_phase.value
                            if session.conversation_context
                            else "greeting"
                        ),
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
        finally:
            if "cost_tracker" in locals() and "token" in locals():
                cost_tracker.clear_session_context(token)

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
            "interview_phase": (
                session.conversation_context.interview_phase.value
                if session.conversation_context
                else "greeting"
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
                if hasattr(session.current_question_metadata, "__dataclass_fields__")
                else session.current_question_metadata
            ) if session.current_question_metadata else None,
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
                "interview_phase": (
                    session.conversation_context.interview_phase.value
                    if session.conversation_context
                    else "greeting"
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
        """Return True if the interview should continue, False when it should end."""
        return session.questions_asked < self.config.max_questions

    def _generate_conversation_summary(
        self, session: InterviewSession
    ) -> Dict[str, Any]:
        """Generate a summary of the conversation flow and dynamics."""

        if not session.interview_data:
            return {"error": "No conversation data available"}

        # Analyze conversation patterns
        answer_scores = [
            item["evaluation"].get("answer_score", 0.0) for item in session.interview_data
        ]
        language_scores = [
            item["evaluation"].get("language_score", 0.0) for item in session.interview_data
        ]
        
        topics_explored = (
            session.conversation_context.topics_covered
            if session.conversation_context
            else []
        )

        conversation_trend = "neutral"
        if len(answer_scores) >= 3:
            early_avg = (
                sum(answer_scores[: len(answer_scores) // 2]) / (len(answer_scores) // 2) if answer_scores else 0
            )
            late_avg = (
                sum(answer_scores[len(answer_scores) // 2 :]) / (len(answer_scores) - len(answer_scores) // 2)
                if answer_scores
                else 0
            )

            if late_avg > early_avg + 0.15:
                conversation_trend = "improving"
            elif late_avg < early_avg - 0.15:
                conversation_trend = "declining"

        return {
            "topics_covered": topics_explored,
            "conversation_trend": conversation_trend,
            "final_skill_assessment": (
                session.conversation_context.candidate_skill_level
                if session.conversation_context
                else "unknown"
            ),
            "total_questions": session.questions_asked,
            "average_answer_score": sum(answer_scores) / len(answer_scores) if answer_scores else 0,
            "average_language_score": sum(language_scores) / len(language_scores) if language_scores else 0,
            "conversation_energy": (
                session.conversation_context.conversation_energy
                if session.conversation_context
                else "neutral"
            ),
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
            "answer_score": sum(
                e.get("answer_score", e.get("technical_accuracy_score", 0))
                for e in evaluations
            )
            / len(evaluations),
            "language_score": sum(
                e.get("language_score", e.get("communication_score", 0))
                for e in evaluations
            )
            / len(evaluations),
        }

        # Generate qualitative assessment
        prompt = f"""
        You are a professional hiring manager writing a structured interview evaluation report.

        Interview Data:
        - Questions asked: {session.questions_asked}
        - Average Answer Score: {avg_scores['answer_score']:.2f} / 1.00
        - Average Language Score: {avg_scores['language_score']:.2f} / 1.00

        Interview transcript:
        {session.interview_history}

        Write a professional, structured evaluation with the following sections using markdown headers:

        ### 1. Overall Assessment
        Summarise the candidate's overall performance objectively. Note if answers were incomplete, evasive, or strong.

        ### 2. Key Strengths
        List any genuine strengths observed. If none were evident, state that briefly without embellishment.

        ### 3. Areas for Improvement
        Provide specific, actionable feedback on technical depth, communication clarity, or preparation gaps.

        ### 4. Hiring Recommendation
        Give one of: **Recommend Hire**, **Further Assessment Needed**, or **Do Not Recommend** — with a one-sentence justification.

        Guidelines: Be honest and objective. Avoid unnecessary harshness but do not inflate scores. If the candidate failed to engage meaningfully, say so clearly and professionally. Keep the total response under 400 words.
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

        reasoning = f"Answer evaluated using rubrics-based system. Quality: {quality} (score: {normalized_score:.2f})"

        return {
            "answer_score": normalized_score,
            "language_score": normalized_score,  # If only one score, use for both
            "relevance_score": normalized_score,
            "technical_accuracy_score": normalized_score,
            "communication_score": normalized_score,
            "reasoning": reasoning,
            "evaluation_method": "rubrics-eval",
        }

    def _convert_scores_to_standard_format(
        self,
        technical_score: float,
        communication_score: float,
        question: str,
        answer: str,
    ) -> Dict[str, Any]:
        """Convert technical and communication scores to the standard evaluation format."""

        # Normalize technical score (rubrics evaluation returns 0-100)
        if technical_score > 1.0:
            technical_normalized = max(0.0, min(1.0, technical_score / 100.0))
        else:
            technical_normalized = max(0.0, min(1.0, technical_score))

        # Normalize communication score (also 0-100)
        if communication_score > 1.0:
            communication_normalized = max(0.0, min(1.0, communication_score / 100.0))
        else:
            communication_normalized = max(0.0, min(1.0, communication_score))

        # Generate reasoning
        reasoning = f"Answer Score: {technical_score:.1f}/100, Language Score: {communication_score:.1f}/100"

        return {
            "answer_score": technical_normalized,
            "language_score": communication_normalized,
            "relevance_score": technical_normalized,
            "technical_accuracy_score": technical_normalized,
            "communication_score": communication_normalized,
            "overall_score": technical_normalized,  # Use technical score as proxy for overall logic if needed
            "reasoning": reasoning,
            "evaluation_method": "rubrics-eval-with-communication",
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

        final_answer_score = min(1.0, score + relevance_boost)

        return {
            "answer_score": final_answer_score,
            "language_score": score,
            "relevance_score": final_answer_score,
            "technical_accuracy_score": final_answer_score,
            "communication_score": score,  # Based on length/structure
            "overall_score": final_answer_score,
            "reasoning": f"{reasoning} Relevance check: {relevance_boost:.1f} boost applied.",
            "evaluation_method": "fallback",
        }
