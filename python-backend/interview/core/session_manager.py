"""
Interview session manager with natural conversation flow.
"""

import re
import uuid
import sys
import os
import time
import logging
import math
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field, replace
import threading
import tempfile

from evaluation_model.rubrics_eval.evaluation_system import EvaluationSystem
from evaluation_model.rubrics_eval.answer_classifier import (
    classify_answer,
    is_junk,
    non_answer_score_and_reason,
)
from ..config.settings import InterviewConfig, LLMConfig
from ..llm.factory import LLMFactory
from ..document.loader import DocumentLoader
from .prompt_based_question_generator import (
    ConversationContext,
    QuestionMetadata,
    InterviewPhase,
    ConversationDepth,
)
from .direct_question_generator import DirectQuestionGenerator as QuestionGenerator
from .direct_question_generator import QuestionValidationError
from .cost_tracker import CostTracker
from utils.ai_detection import check_ai_content

logger = logging.getLogger(__name__)
_EVALUATION_SLOTS = threading.BoundedSemaphore(8)


def _plain_metadata(value):
    """Question metadata is stored in MongoDB and returned as JSON."""
    if hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _plain_metadata(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_metadata(item) for item in value]
    return value


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
    # Epoch-seconds timestamp of when `current_question` was last (re)served —
    # drives the client-side no-response timeout (see get_next_question/submit_answer).
    question_served_at: Optional[float] = None
    # Set when the interview is force-ended after exhausting LLM retries, so the
    # recruiter's report can distinguish "candidate disengaged" from "we broke".
    ended_early_reason: Optional[str] = None
    question_generator: Optional[Any] = None
    answer_lock: Any = field(default_factory=threading.RLock, repr=False)
    evaluation_events: List[Any] = field(default_factory=list, repr=False)
    activated_at: Optional[float] = None
    final_evaluation: Optional[Dict[str, Any]] = None
    preparation_answers: Optional[List[Dict[str, Any]]] = None
    max_questions: int = 12


class InterviewSessionManager:
    """Manages interview sessions with natural conversation flow."""

    def __init__(self, config: InterviewConfig, llm_config: LLMConfig):
        self.config = config
        self.llm_config = llm_config
        self.sessions: Dict[str, InterviewSession] = {}

        # Build fallback LLM chain from available API keys
        self.llm = self._create_fallback_llm(llm_config)

        # Initialize components
        # Reasoning tokens share the output budget with the spoken question.
        from services.interview_voice_policy import bounded_number
        self.question_llm = self._create_fallback_llm(replace(llm_config,
            max_tokens=int(bounded_number("INTERVIEW_QUESTION_MAX_TOKENS", 1024, 512, 4096)),
            timeout_seconds=bounded_number("INTERVIEW_PROVIDER_TIMEOUT_SECONDS", 4, 2, 8)))
        self.question_generator = QuestionGenerator(self.question_llm, config=self.config)
        self.report_llm = self._create_fallback_llm(replace(
            llm_config, max_tokens=4096, temperature=0.3, timeout_seconds=20))

        # Initialize evaluation system if available
        self.evaluation_system = EvaluationSystem()

    @staticmethod
    def _create_fallback_llm(primary_config: LLMConfig):
        """
        Create an LLM whose provider ORDER follows the app-wide priority
        (LLM_PROVIDER_PRIORITY, default deepseek -> gemini -> groq — see
        services/llm_fallback_service.py). primary_config supplies the
        generation settings (temperature/max_tokens/timeout); INTERVIEW_LLM_MODEL
        pins the first provider's model when it belongs to that provider.
        """
        import os
        from ..config.settings import LLMProvider
        from services.llm_fallback_service import (
            PROVIDER_SPECS,
            default_model_for,
            get_provider_priority,
        )

        chain_to_enum = {
            "deepseek": LLMProvider.DEEPSEEK,
            "groq": LLMProvider.GROQ,
            "google": LLMProvider.GEMINI,
            "openai": LLMProvider.OPENAI,
        }

        def model_belongs_to(model_name: str, provider: str) -> bool:
            name = (model_name or "").lower()
            if provider == "deepseek":
                return name.startswith("deepseek-")
            if provider == "openai":
                return name.startswith(("gpt", "o1", "o3", "o4"))
            if provider == "google":
                return "gemini" in name or "gemma" in name
            if provider == "groq":
                return name.startswith("openai/") or any(tag in name for tag in ("llama", "mixtral", "qwen", "kimi"))
            return False

        interview_model = os.getenv("INTERVIEW_LLM_MODEL", "").strip()

        configs = []
        for index, provider in enumerate(get_provider_priority()):
            api_key = os.getenv(PROVIDER_SPECS[provider]["key_env"])
            if not api_key:
                continue
            model_name = default_model_for(provider)
            # Honor the legacy per-interview model pin only on the provider it
            # actually belongs to (a gpt-* pin must not be sent to Groq).
            if interview_model and model_belongs_to(interview_model, provider):
                model_name = interview_model
            configs.append(LLMConfig(
                provider=chain_to_enum[provider],
                model_name=model_name,
                api_key=api_key,
                temperature=primary_config.temperature,
                max_tokens=primary_config.max_tokens,
                timeout_seconds=primary_config.timeout_seconds,
            ))

        if not configs:
            configs = [primary_config]

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
            document_loader = DocumentLoader(cv_path, jd_path, [])

            # Validate only when the caller hasn't already guaranteed validity.
            if not pre_validated:
                validation = document_loader.validate_documents()
                if not all(validation.values()):
                    return {"error": "Document validation failed", "validation": validation}

            # Each candidate owns mutable role banks, CV data and source metadata.
            # Sharing this generator let a concurrent session replace another CV.
            generator = QuestionGenerator(getattr(self, "question_llm", self.llm), config=self.config)
            conversation_context = generator.initialize_conversation(
                document_loader.get_cv_sections(), document_loader.get_jd_text(), use_llm=False
            )
            conversation_context.has_been_greeted = True
            conversation_context.interview_phase = (
                InterviewPhase.EXPERIENTIAL_QUESTIONS
                if self.config.include_experiential_questions
                else InterviewPhase.TECHNICAL_QUESTIONS
            )

            first_question, generated_metadata = generator.first_question(conversation_context)
            first_metadata = _plain_metadata(generated_metadata)

            # Create session without conversation_context
            session = InterviewSession(
                session_id=session_id,
                cv_path=cv_path,
                jd_path=jd_path,
                reference_paths=reference_paths,
                conversation_context=conversation_context,
                current_question=first_question,
                current_question_metadata=first_metadata,
                proctoring_config=proctoring_config or {},
                init_event=threading.Event(),
                question_served_at=None,
                question_generator=generator,
                max_questions=self.config.max_questions,
            )

            self.sessions[session_id] = session

            session.init_event.set()

            return {
                "session_id": session_id,
                "first_question": first_question,
                "question_metadata": first_metadata,
                "conversation_context": {
                    "candidate_skill_level": "unknown",
                    "current_topic": "Introduction",
                    "interview_phase": "INTRODUCTION",
                },
                "question_timeout_seconds": self.config.question_timeout_seconds,
                "question_deadline": None,
                "setup_required": True,
                # Single source of truth for the client's question counter —
                # the frontend previously hardcoded its own copy of this.
                "max_questions": session.max_questions,
            }

        except Exception as e:
            logger.error(f"Failed to create session [session={session_id}]: {e}", exc_info=True)
            if isinstance(e, QuestionValidationError):
                return {"error": "The interviewer could not prepare the opening question. Please retry; your interview has not started.",
                        "error_code": "opening_question_unavailable"}
            return {"error": f"Failed to create session: {str(e)}"}
        finally:
            cost_tracker.clear_session_context(token)

    def checkpoint(self, session_id):
        session = self.sessions.get(session_id)
        if not session:
            return None
        return _plain_metadata({
            "current_question": session.current_question,
            "current_question_metadata": session.current_question_metadata,
            "question_served_at": session.question_served_at,
            "activated_at": session.activated_at,
            "questions_asked": session.questions_asked,
            "is_complete": session.is_complete,
            "max_questions": session.max_questions,
            "interview_data": session.interview_data,
            "conversation_context": session.conversation_context,
        })

    def restore_session(self, doc, cv_text, jd_text):
        """Rehydrate a trusted owned Mongo checkpoint without a debit/provider call."""
        session_id = doc["session_id"]
        saved = doc.get("engine_checkpoint") or {}
        existing = self.sessions.get(session_id)
        if existing and saved.get("questions_asked", 0) <= existing.questions_asked:
            return existing
        # Old active sessions may use their persisted last response; never
        # silently restart their question sequence at the introduction.
        last = (doc.get("last_answer") or {}).get("result") or {}
        question = saved.get("current_question") or last.get("next_question")
        if not question and not saved.get("is_complete") and doc.get("status") == "active" and doc.get("qa_pairs"):
            raise ValueError("The saved current question is missing; submitted answers are retained.")
        generator = QuestionGenerator(getattr(self, "question_llm", self.llm), config=self.config)
        # Existing attempts retain their original length after a rollout.
        limit = saved.get("max_questions", doc.get("max_questions", 10))
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
            limit = 10
        generator.config = replace(self.config, max_questions=limit, min_questions=limit)
        with tempfile.TemporaryDirectory(prefix="genhire-restore-") as directory:
            cv_path, jd_path = os.path.join(directory, "cv.txt"), os.path.join(directory, "jd.txt")
            for path, content in ((cv_path, cv_text), (jd_path, jd_text)):
                with open(path, "w", encoding="utf-8") as output:
                    output.write(content)
            loader = DocumentLoader(cv_path, jd_path, [])
            context = generator.initialize_conversation(loader.get_cv_sections(), loader.get_jd_text(), use_llm=False)
        for key, value in (saved.get("conversation_context") or {}).items():
            if hasattr(context, key):
                if key == "depth_level":
                    value = ConversationDepth(value)
                elif key == "interview_phase":
                    value = InterviewPhase(value)
                setattr(context, key, value)
        context.has_been_greeted = True
        if not saved.get("conversation_context"):
            context.interview_phase = InterviewPhase.EXPERIENTIAL_QUESTIONS if self.config.include_experiential_questions else InterviewPhase.TECHNICAL_QUESTIONS
            context.question_count = len(doc.get("qa_pairs") or [])
            context.previous_answers = [item.get("answer", "") for item in doc.get("qa_pairs") or []]
        session = InterviewSession(session_id=session_id, cv_path=doc.get("cv_path", ""),
            jd_path=doc.get("jd_path", ""), reference_paths=[], conversation_context=context,
            current_question=question if saved.get("is_complete") else question or "Hello, I'm Alex. Great to meet you! Could you please give me a brief introduction about yourself and your background?",
            current_question_metadata=saved.get("current_question_metadata") or {"source": "restored", "topic_area": "General"},
            interview_data=saved.get("interview_data") or doc.get("qa_pairs") or [],
            questions_asked=saved.get("questions_asked", len(doc.get("qa_pairs") or [])),
            is_complete=saved.get("is_complete", False), proctoring_config=doc.get("proctoring_config") or {},
            question_generator=generator, init_event=threading.Event(),
            max_questions=limit,
            question_served_at=saved.get("question_served_at") or (last.get("question_deadline") - self.config.question_timeout_seconds if last.get("question_deadline") else None),
            activated_at=saved.get("activated_at"))
        context.conversation_history = [{"question": item.get("question", ""), "answer": item.get("answer", "")}
                                        for item in session.interview_data]
        context.asked_questions = [item["question"] for item in context.conversation_history] + ([session.current_question] if session.current_question else [])
        context.question_count = session.questions_asked
        session.interview_history = "".join(f"Q: {item['question']}\nA: {item['answer']}\n\n" for item in session.interview_data)
        # Keep completed local rubrics when importing a newer checkpoint.
        if existing:
            for old, item in zip(existing.interview_data, session.interview_data):
                if old.get("question") == item.get("question") and old.get("answer") == item.get("answer"):
                    if (old.get("evaluation") or {}).get("evaluation_status") == "complete":
                        item["evaluation"] = dict(old["evaluation"])
        session.init_event.set()
        # Evaluations that belonged to a killed worker cannot remain pending
        # forever. Preserve their answers and explicitly mark unavailable work.
        for item in session.interview_data:
            if (item.get("evaluation") or {}).get("evaluation_status") == "pending":
                item["evaluation"]["evaluation_status"] = "unavailable"
        self.sessions[session_id] = session
        CostTracker().start_session(session_id)
        return session

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

            conversation_context = (session.question_generator or self.question_generator).initialize_conversation(
                resume_sections, job_description, use_llm=False
            )
            # The generated first question already serves as the greeting, so skip
            # the GREETING phase in the question generator to prevent a second greeting.
            conversation_context.has_been_greeted = True
            conversation_context.interview_phase = InterviewPhase.EXPERIENTIAL_QUESTIONS
            session.conversation_context = conversation_context
        except Exception as e:
            logger.error(f"Background context init failed [session={session_id}]: {e}", exc_info=True)
        finally:
            if session.init_event:
                session.init_event.set()

    def submit_answer(
        self, session_id: str, question: str, answer: str
    ) -> Dict[str, Any]:
        session = self._get_session(session_id)
        if not session:
            return {"error": "Session not found"}
        if not session.answer_lock.acquire(blocking=False):
            return {"error": "An answer is already being processed", "error_code": "answer_in_progress"}
        try:
            if session.current_question and question.strip() != session.current_question.strip():
                return {"error": "This question has already been answered. Refresh the current question before retrying.", "error_code": "stale_question", "current_question": session.current_question}
            return self._submit_answer_locked(session_id, question, answer)
        finally:
            session.answer_lock.release()

    def activate_session(self, session_id: str) -> Dict[str, Any]:
        """Start pacing after device, identity and optional mobile checks finish."""
        session = self._get_session(session_id)
        if not session:
            return {"error": "Session not found"}
        with session.answer_lock:
            if session.is_complete:
                return {"error": "Interview is already complete"}
            if session.activated_at is None:
                session.activated_at = time.time()
                session.question_served_at = session.activated_at
            return {
                "session_id": session_id,
                "status": "active",
                "first_question": session.current_question,
                "question_timeout_seconds": self.config.question_timeout_seconds,
                "question_deadline": session.question_served_at + self.config.question_timeout_seconds,
                "max_questions": session.max_questions,
            }

    def _submit_answer_locked(
        self, session_id: str, question: str, answer: str
    ) -> Dict[str, Any]:
        """Submit an answer and get evaluation/next question using natural conversation flow."""
        session = self._get_session(session_id)
        if not session:
            return {"error": "Session not found"}

        if session.is_complete:
            return {"error": "Interview is already complete"}

        # Repeat-intent must be caught BEFORE the message is treated as a scored
        # answer: otherwise "can you repeat that?" gets evaluated as a low-quality
        # answer to the previous question, and both question counters still
        # advance even though nothing new was actually asked.
        if (
            session.current_question
            and (session.question_generator or self.question_generator).user_requested_repeat(answer)
        ):
            session.question_served_at = time.time()
            return {
                "interview_complete": False,
                "current_evaluation": None,
                "repeated_question": True,
                "next_question": session.current_question,
                "question_metadata": _plain_metadata(session.current_question_metadata),
                "conversation_context": {
                    "current_topic": session.conversation_context.current_topic,
                    "depth_level": session.conversation_context.depth_level.value,
                    "topics_covered": session.conversation_context.topics_covered,
                    "candidate_skill_level": session.conversation_context.candidate_skill_level,
                    "conversation_energy": session.conversation_context.conversation_energy,
                    "interview_phase": session.conversation_context.interview_phase.value,
                },
                "progress": {
                    "questions_asked": session.questions_asked,
                    "estimated_remaining": max(
                        0, session.max_questions - session.questions_asked
                    ),
                },
                "question_timeout_seconds": self.config.question_timeout_seconds,
                "question_deadline": session.question_served_at + self.config.question_timeout_seconds,
            }

        try:
            cost_tracker = CostTracker()
            token = cost_tracker.set_session_context(session_id)

            # Classify before ever spending an LLM call: empty/canned-non-answer/
            # gibberish/confidently-non-English answers get a fast, deterministic,
            # correctly-low score instead of the old length-only fallback (which
            # would score a long "I don't know, I don't know, ..." as "adequate").
            # This value also feeds get_next_question()'s difficulty adaptation
            # below, so a junk answer correctly reads as a struggle, not a success.
            classification = classify_answer(answer)
            answer_is_junk = is_junk(classification)
            if answer_is_junk:
                junk_score, junk_reason = non_answer_score_and_reason(classification)
                provisional_evaluation = {
                    "answer_score": junk_score,
                    "language_score": junk_score,
                    "relevance_score": junk_score,
                    "technical_accuracy_score": junk_score,
                    "communication_score": junk_score,
                    "overall_score": junk_score,
                    "reasoning": junk_reason,
                    "evaluation_method": "pre_classified",
                }
            else:
                provisional_evaluation = self._fallback_evaluation(question, answer)

            def evaluate_answer():
                if not self.evaluation_system:
                    return provisional_evaluation
                try:
                    with ThreadPoolExecutor(max_workers=2) as evaluator_pool:
                        technical_future = evaluator_pool.submit(
                            copy_context().run,
                            self.evaluation_system.evaluate_single_answer_fast,
                            question,
                            answer,
                        )
                        communication_future = evaluator_pool.submit(
                            copy_context().run,
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
                    logger.error(f"Evaluation failed [session={session_id}]: {e}", exc_info=True)
                    return provisional_evaluation

            # Generate next question using natural conversation flow
            if session.conversation_context is None:
                return {"error": "Conversation context not initialized"}

            # live path. Use the provisional score for adaptive topic selection.

            evaluation = provisional_evaluation.copy()
            evaluation["evaluation_status"] = "complete" if answer_is_junk else "pending"
            completed_evaluation = threading.Event()

            def bg_evaluate_and_update():
                eval_token = CostTracker().set_session_context(session_id)
                try:
                    eval_result = evaluate_answer()
                    evaluation.update(eval_result)

                    if session.proctoring_config and session.proctoring_config.get("ai_detection", False):
                        ai_result = check_ai_content(answer)
                        # Always set the key so the response schema is consistent
                        # regardless of whether detection ran successfully — a
                        # missing key previously meant "unknown," indistinguishable
                        # from "not enabled."
                        evaluation["ai_probability"] = ai_result.get("score") if ai_result else None
                        evaluation["ai_detection_raw"] = ai_result.get("raw_response") if ai_result else None
                except Exception as e:
                    logger.error(f"Background evaluation failed [session={session_id}]: {e}", exc_info=True)
                finally:
                    evaluation["evaluation_status"] = (
                        "complete" if evaluation.get("evaluation_method", "").startswith("rubrics-eval") else "unavailable"
                    )
                    completed_evaluation.set()
                    CostTracker().clear_session_context(eval_token)
                    _EVALUATION_SLOTS.release()

            # One bounded pass through the provider chain. On failure keep the
            # current question for an explicit retry without ending the attempt.
            next_question, next_metadata, generation_error = None, None, None
            MAX_QUESTION_GEN_RETRIES = 0 if session.questions_asked + 1 >= session.max_questions else 1
            for attempt in range(MAX_QUESTION_GEN_RETRIES):
                try:
                    next_question, next_metadata = (session.question_generator or self.question_generator).get_next_question(
                        session.conversation_context,
                        answer,
                        provisional_evaluation,
                    )
                    generation_error = None
                    break
                except Exception as e:
                    generation_error = e
                    logger.warning(
                        f"get_next_question attempt {attempt + 1}/{MAX_QUESTION_GEN_RETRIES} failed "
                        f"[session={session_id}]: {e}"
                    )
                    if attempt < MAX_QUESTION_GEN_RETRIES - 1:
                        time.sleep(min(2 ** attempt, 4))

            if generation_error is not None:
                return {"error": "The interviewer could not prepare the next question. Retry your saved answer.",
                        "error_code": "next_question_unavailable", "retryable": True}

            # Start scoring only after the next question succeeds. Failed retries
            # must not consume two more LLM calls or compete with the live turn.
            session.evaluation_events.append(completed_evaluation)
            # Skip the (two-LLM-call) background evaluation entirely for
            # pre-classified junk — there's nothing useful for the LLM to score,
            # and the deterministic provisional_evaluation above is already final.
            if not answer_is_junk:
                if _EVALUATION_SLOTS.acquire(blocking=False):
                    threading.Thread(target=bg_evaluate_and_update, daemon=True).start()
                else:
                    evaluation["evaluation_status"] = "unavailable"
                    evaluation["reasoning"] = "Evaluation capacity was temporarily unavailable; this answer needs review."
                    completed_evaluation.set()
            else:
                completed_evaluation.set()

            session.interview_history += f"Q: {question}\nA: {answer}\n\n"
            # Mirror the question generator's own counter instead of maintaining
            # a second independent increment — the generator's phase-transition
            # logic (technical -> HR -> closing) and this termination check must
            # never be able to drift apart.
            session.questions_asked = session.conversation_context.question_count
            if MAX_QUESTION_GEN_RETRIES == 0:
                session.questions_asked += 1
            session.question_served_at = time.time()
            session.interview_data.append(
                {
                    "question": question,
                    "answer": answer,
                    "evaluation": evaluation,
                    "question_metadata": _plain_metadata(session.current_question_metadata),
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
                final_evaluation = {"score_status": "pending"}

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
                    "question_metadata": _plain_metadata(next_metadata),
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
                            0, session.max_questions - session.questions_asked
                        ),
                    },
                    "question_timeout_seconds": self.config.question_timeout_seconds,
                    "question_deadline": session.question_served_at + self.config.question_timeout_seconds,
                }

        except Exception as e:
            logger.error(f"Failed to process answer [session={session_id}]: {e}", exc_info=True)
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
                100, (session.questions_asked / session.max_questions) * 100
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
            "question_metadata": _plain_metadata(session.current_question_metadata),
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

        with session.answer_lock:
            session.is_complete = True
            final_evaluation = self._generate_final_evaluation(session)

        return {"session_ended": True, "final_evaluation": final_evaluation}

    def _should_continue_interview(self, session: InterviewSession) -> bool:
        """Return True if the interview should continue, False when it should end."""
        return session.questions_asked < session.max_questions

    def _generate_conversation_summary(
        self, session: InterviewSession
    ) -> Dict[str, Any]:
        """Generate a summary of the conversation flow and dynamics."""

        if not session.interview_data:
            return {"error": "No conversation data available"}

        # Analyze conversation patterns
        verified = [item["evaluation"] for item in session.interview_data
                    if item["evaluation"].get("evaluation_status") == "complete"]
        answer_scores = [item.get("answer_score", 0.0) for item in verified]
        language_scores = [item.get("language_score", 0.0) for item in verified]
        
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
            "average_answer_score": sum(answer_scores) / len(answer_scores) if answer_scores else None,
            "average_language_score": sum(language_scores) / len(language_scores) if language_scores else None,
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
        if session.final_evaluation is not None:
            # A bounded finalization may precede the last evaluator. Rebuild
            # only once evidence changed; do not freeze an unavailable result.
            previous_pending = session.final_evaluation.get("pending_answers", 0)
            still_pending = sum(item["evaluation"].get("evaluation_status") == "pending"
                                for item in session.interview_data)
            if not previous_pending or still_pending >= previous_pending:
                return session.final_evaluation
        if not session.interview_data:
            return {"error": "No interview data available for evaluation"}

        # Do not persist a length-based placeholder while the last answer is
        # still being scored. Share one wait budget across all answer workers.
        wait_until = time.monotonic() + 30.0
        for event in session.evaluation_events:
            event.wait(max(0.0, wait_until - time.monotonic()))
        all_evaluations = [dict(item["evaluation"]) for item in session.interview_data]
        evaluations = [e for e in all_evaluations if e.get("evaluation_method") == "pre_classified"
                       or (e.get("evaluation_method", "").startswith("rubrics-eval") and e.get("evaluation_status") != "pending")]
        pending = sum(e.get("evaluation_status") == "pending" for e in all_evaluations)
        score_status = "complete" if len(evaluations) == len(all_evaluations) else ("partial" if evaluations else "unavailable")

        avg_scores = {
            "answer_score": sum(
                e.get("answer_score", e.get("technical_accuracy_score", 0))
                for e in evaluations
            )
            / len(evaluations) if evaluations else None,
            "language_score": sum(
                e.get("language_score", e.get("communication_score", 0))
                for e in evaluations
            )
            / len(evaluations) if evaluations else None,
        }

        from .preparation_report import preparation_prompt, parse_preparation_report
        prompt = preparation_prompt(session, session.question_generator or self.question_generator,
                                    avg_scores, {"scored": len(evaluations), "total": len(all_evaluations), "status": score_status})
        try:
            # One structured report call, never on the live answer path. Give ten
            # preparation answers enough output tokens, independent of question limits.
            reporter = QuestionGenerator(self.report_llm, config=self.config)
            reporter.completion_budget_seconds = 35
            report_token = CostTracker().set_session_context(session.session_id)
            try:
                response = reporter._complete_llm(prompt)
                qualitative_assessment, preparation = parse_preparation_report(response.text, len(session.interview_data))
                session.preparation_answers = preparation
            finally:
                CostTracker().clear_session_context(report_token)
        except Exception as e:
            logger.error(
                f"Failed to generate assessment/preparation answers [session={session.session_id}]: {type(e).__name__}",
                exc_info=True,
            )
            qualitative_assessment = (
                f"### Overall Assessment\n{session.questions_asked} answers were recorded. "
                f"Verified rubric scores are available for {len(evaluations)} of {len(all_evaluations)} answers.\n\n"
                "### Areas for Improvement\nReview the question and answer breakdown for specific feedback.\n\n"
                "### Hiring Recommendation\nFurther Assessment Needed. The evaluation service did not produce a complete report."
            )

        result = {
            "quantitative_scores": avg_scores,
            "qualitative_assessment": qualitative_assessment,
            "score_status": score_status,
            "scored_answers": len(evaluations),
            "total_answers": len(all_evaluations),
            "pending_answers": pending,
            "preparation_status": "complete" if session.preparation_answers else "unavailable",
            "per_question_evaluations": [
                {"question_number": index + 1, "question": item["question"], "answer": item["answer"],
                 "evaluation": evaluation, "question_metadata": item.get("question_metadata"),
                 **(session.preparation_answers[index] if session.preparation_answers else
                    {"suggested_answer_status": "unavailable"})}
                for index, (item, evaluation) in enumerate(zip(session.interview_data, all_evaluations))
            ],
            "interview_metadata": {
                "questions_asked": session.questions_asked,
                "session_duration": round(time.time() - session.activated_at, 1) if session.activated_at else 0,
                "completion_status": (
                    "ended_early_technical_failure"
                    if session.ended_early_reason
                    else ("complete" if session.is_complete else "incomplete")
                ),
                "ended_early_reason": session.ended_early_reason,
            },
        }
        session.final_evaluation = result
        return result

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime

        return datetime.now().isoformat()

    def _convert_single_score_to_standard_format(
        self, score: float, question: str, answer: str
    ) -> Dict[str, Any]:
        """Convert single rubrics-eval score to the standard evaluation format."""

        normalized_score = self._normalize_rubric_score(score)

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

        technical_normalized = self._normalize_rubric_score(technical_score)
        communication_normalized = self._normalize_rubric_score(communication_score)

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

    @staticmethod
    def _normalize_rubric_score(score):
        # This provider's documented contract is always 0-100, including 1.
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
            raise ValueError("Evaluator returned an invalid score")
        return max(0.0, min(1.0, score / 100.0))

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
