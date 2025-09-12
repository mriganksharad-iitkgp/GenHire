"""
Real Interview System for Domain-Agnostic Fundamental Questions.
This system orchestrates the complete interview flow with natural conversation management.
"""

import asyncio
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import json
from datetime import datetime

from .domain_agnostic_fundamental_generator import (
    FundamentalQuestionGenerator,
    FundamentalQuestion,
    InterviewState,
    DifficultyLevel,
)
from ..llm.base import BaseLLM


class InterviewPhase(Enum):
    """Different phases of the interview."""

    INTRODUCTION = "introduction"
    FUNDAMENTAL_QUESTIONS = "fundamental_questions"
    DEEP_DIVE = "deep_dive"
    WRAP_UP = "wrap_up"
    COMPLETED = "completed"


@dataclass
class InterviewSession:
    """Complete interview session state."""

    session_id: str
    candidate_name: str
    position: str
    phase: InterviewPhase
    start_time: datetime
    cv_content: Dict[str, str]
    jd_content: str

    # Question generation state
    question_generator: FundamentalQuestionGenerator
    interview_state: InterviewState

    # Conversation history
    conversation_history: List[Dict[str, Any]]
    current_question: Optional[FundamentalQuestion]

    # Session metrics
    total_time_spent: int  # in minutes
    questions_count: int
    average_response_quality: float

    # Flow control
    should_continue: bool
    needs_human_intervention: bool
    completion_reason: Optional[str]


class FundamentalInterviewSystem:
    """Complete system for conducting domain-agnostic fundamental interviews."""

    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self.active_sessions: Dict[str, InterviewSession] = {}

    def start_interview(
        self,
        session_id: str,
        candidate_name: str,
        position: str,
        cv_content: Dict[str, str],
        jd_content: str,
    ) -> Tuple[str, Dict[str, Any]]:
        """Start a new fundamental interview session."""

        # Initialize question generator
        question_generator = FundamentalQuestionGenerator(self.llm)
        interview_state = question_generator.initialize_interview(
            cv_content, jd_content
        )

        # Create interview session
        session = InterviewSession(
            session_id=session_id,
            candidate_name=candidate_name,
            position=position,
            phase=InterviewPhase.INTRODUCTION,
            start_time=datetime.now(),
            cv_content=cv_content,
            jd_content=jd_content,
            question_generator=question_generator,
            interview_state=interview_state,
            conversation_history=[],
            current_question=None,
            total_time_spent=0,
            questions_count=0,
            average_response_quality=0.0,
            should_continue=True,
            needs_human_intervention=False,
            completion_reason=None,
        )

        # Store session
        self.active_sessions[session_id] = session

        # Generate opening message and first question
        opening_message, session_info = self._generate_opening_sequence(session)

        return opening_message, session_info

    def get_next_interaction(
        self, session_id: str, candidate_answer: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Get the next question or interaction in the interview."""

        if session_id not in self.active_sessions:
            return "Session not found. Please start a new interview.", {
                "error": "session_not_found"
            }

        session = self.active_sessions[session_id]

        # Process candidate's answer if provided
        if candidate_answer and session.current_question:
            self._process_candidate_answer(session, candidate_answer)

        # Determine next action based on interview state
        if session.phase == InterviewPhase.INTRODUCTION:
            return self._handle_introduction_phase(session)
        elif session.phase == InterviewPhase.FUNDAMENTAL_QUESTIONS:
            return self._handle_fundamental_questions_phase(session)
        elif session.phase == InterviewPhase.DEEP_DIVE:
            return self._handle_deep_dive_phase(session)
        elif session.phase == InterviewPhase.WRAP_UP:
            return self._handle_wrap_up_phase(session)
        else:
            return self._handle_completion(session)

    def _generate_opening_sequence(
        self, session: InterviewSession
    ) -> Tuple[str, Dict[str, Any]]:
        """Generate the opening message and first question."""

        # Analyze extracted topics for personalized opening
        cv_topics = session.interview_state.cv_topics[:5]  # Top 5 topics
        jd_topics = session.interview_state.jd_topics[:5]
        relevant_topics = session.interview_state.relevant_topics[:3]
        domains = session.interview_state.technical_domains[:3]

        opening_prompt = f"""
Generate a warm, professional opening for a technical interview. The candidate is {session.candidate_name} 
applying for {session.position}.

From their CV, key technical areas include: {', '.join(cv_topics)}
The role requires: {', '.join(jd_topics)}
Relevant overlapping areas: {', '.join(relevant_topics)}
Main technical domains: {', '.join(domains)}

Create a personalized opening that:
1. Welcomes the candidate warmly
2. Briefly mentions the interview structure (fundamental questions)
3. References 1-2 relevant technical areas from their background
4. Sets expectations for theoretical/conceptual questions
5. Is encouraging and professional

Keep it conversational and under 100 words:
"""

        try:
            response = self.llm.complete(opening_prompt)
            opening_message = response.text.strip()
        except Exception as e:
            print(f"Error generating opening: {e}")
            opening_message = f"Welcome {session.candidate_name}! I'm excited to discuss your technical background for the {session.position} role. I'll be asking some fundamental questions about concepts relevant to your experience. Let's begin!"

        # Transition to fundamental questions phase
        session.phase = InterviewPhase.FUNDAMENTAL_QUESTIONS

        session_info = {
            "session_id": session.session_id,
            "phase": session.phase.value,
            "candidate_name": session.candidate_name,
            "position": session.position,
            "extracted_domains": domains,
            "relevant_topics": relevant_topics,
            "estimated_skill_level": session.interview_state.candidate_skill_level,
        }

        return opening_message, session_info

    def _handle_introduction_phase(
        self, session: InterviewSession
    ) -> Tuple[str, Dict[str, Any]]:
        """Handle the introduction phase."""

        # This should not be called as we handle introduction in opening sequence
        session.phase = InterviewPhase.FUNDAMENTAL_QUESTIONS
        return self._handle_fundamental_questions_phase(session)

    def _handle_fundamental_questions_phase(
        self, session: InterviewSession
    ) -> Tuple[str, Dict[str, Any]]:
        """Handle the main fundamental questions phase."""

        # Check if we should continue with fundamental questions
        if session.questions_count >= 8:  # Reasonable limit
            session.phase = InterviewPhase.WRAP_UP
            return self._handle_wrap_up_phase(session)

        # Generate next question
        if session.questions_count == 0:
            # First question
            question, formatted_question = (
                session.question_generator.get_opening_question()
            )
        else:
            # Subsequent questions
            last_answer = self._get_last_candidate_answer(session)
            last_evaluation = self._get_last_evaluation(session)
            question, formatted_question = session.question_generator.get_next_question(
                last_answer, last_evaluation
            )

        # Update session state
        session.current_question = question
        session.questions_count += 1

        # Add natural conversation flow
        final_question = self._add_conversation_context(session, formatted_question)

        # Log interaction
        self._log_interaction(
            session,
            "question",
            {
                "question": question.question,
                "topic": question.topic,
                "domain": question.domain,
                "difficulty": question.difficulty.value,
                "formatted_question": final_question,
            },
        )

        session_info = {
            "session_id": session.session_id,
            "phase": session.phase.value,
            "question_number": session.questions_count,
            "current_topic": question.topic,
            "current_domain": question.domain,
            "difficulty_level": question.difficulty.value,
            "progress": {
                "questions_asked": session.questions_count,
                "topics_covered": session.interview_state.topics_covered,
                "estimated_completion": min(8, session.questions_count + 3),
            },
        }

        return final_question, session_info

    def _handle_deep_dive_phase(
        self, session: InterviewSession
    ) -> Tuple[str, Dict[str, Any]]:
        """Handle deep dive into specific topics (if needed)."""

        # For now, transition directly to wrap up
        session.phase = InterviewPhase.WRAP_UP
        return self._handle_wrap_up_phase(session)

    def _handle_wrap_up_phase(
        self, session: InterviewSession
    ) -> Tuple[str, Dict[str, Any]]:
        """Handle the interview wrap-up."""

        # Generate wrap-up message
        summary = session.question_generator.get_interview_summary()

        wrap_up_prompt = f"""
Generate a professional, encouraging wrap-up message for the technical interview.

Interview Summary:
- Questions asked: {summary['total_questions']}
- Topics covered: {', '.join(summary['topics_covered'])}
- Candidate's technical domains: {', '.join(summary['technical_domains'])}
- Performance level: {summary['candidate_confidence']}

Create a wrap-up that:
1. Thanks the candidate for their time
2. Briefly acknowledges the areas discussed
3. Is positive and encouraging
4. Mentions next steps will be communicated
5. Keeps it professional and warm

Keep it under 80 words:
"""

        try:
            response = self.llm.complete(wrap_up_prompt)
            wrap_up_message = response.text.strip()
        except Exception as e:
            print(f"Error generating wrap-up: {e}")
            wrap_up_message = f"Thank you for the great discussion, {session.candidate_name}! We covered some excellent technical concepts today. We'll be in touch about next steps soon."

        # Mark session as completed
        session.phase = InterviewPhase.COMPLETED
        session.should_continue = False
        session.completion_reason = "normal_completion"

        # Log final interaction
        self._log_interaction(
            session, "wrap_up", {"message": wrap_up_message, "summary": summary}
        )

        session_info = {
            "session_id": session.session_id,
            "phase": session.phase.value,
            "completed": True,
            "summary": summary,
            "total_questions": session.questions_count,
            "conversation_history": session.conversation_history,
        }

        return wrap_up_message, session_info

    def _handle_completion(
        self, session: InterviewSession
    ) -> Tuple[str, Dict[str, Any]]:
        """Handle completed interview session."""

        return "Interview completed. Thank you for your time!", {
            "session_id": session.session_id,
            "status": "completed",
            "summary": session.question_generator.get_interview_summary(),
        }

    def _process_candidate_answer(self, session: InterviewSession, answer: str):
        """Process and evaluate the candidate's answer."""

        if not session.current_question:
            return

        # Evaluate the answer
        evaluation = session.question_generator.evaluate_answer(
            session.current_question, answer
        )

        # Update session metrics
        session.average_response_quality = (
            session.average_response_quality * (session.questions_count - 1)
            + evaluation["overall_score"]
        ) / session.questions_count

        # Log the answer and evaluation
        self._log_interaction(
            session,
            "answer",
            {
                "answer": answer,
                "evaluation": evaluation,
                "question": session.current_question.question,
            },
        )

        # Check if intervention is needed
        if evaluation["overall_score"] < 0.2 and session.questions_count > 2:
            session.needs_human_intervention = True

    def _add_conversation_context(
        self, session: InterviewSession, question: str
    ) -> str:
        """Add natural conversation context to questions."""

        # Add context based on conversation history
        if session.questions_count == 1:
            return question
        elif session.questions_count <= 3:
            context_phrases = ["Let's continue. ", "Next, ", "Moving on, ", "Great. "]
            return f"{context_phrases[session.questions_count % len(context_phrases)]}{question}"
        else:
            # Later in the conversation, be more natural
            if session.average_response_quality > 0.7:
                positive_transitions = [
                    "Excellent understanding! ",
                    "That's a solid answer. ",
                    "Great explanation. ",
                ]
                return f"{positive_transitions[session.questions_count % len(positive_transitions)]}{question}"
            else:
                neutral_transitions = ["I see. ", "Okay. ", "Let's try another topic. "]
                return f"{neutral_transitions[session.questions_count % len(neutral_transitions)]}{question}"

    def _get_last_candidate_answer(self, session: InterviewSession) -> Optional[str]:
        """Get the last candidate answer from conversation history."""

        for interaction in reversed(session.conversation_history):
            if interaction.get("type") == "answer":
                return interaction.get("data", {}).get("answer")
        return None

    def _get_last_evaluation(self, session: InterviewSession) -> Optional[Dict]:
        """Get the last answer evaluation from conversation history."""

        for interaction in reversed(session.conversation_history):
            if interaction.get("type") == "answer":
                return interaction.get("data", {}).get("evaluation")
        return None

    def _log_interaction(
        self, session: InterviewSession, interaction_type: str, data: Dict[str, Any]
    ):
        """Log an interaction in the conversation history."""

        interaction = {
            "timestamp": datetime.now().isoformat(),
            "type": interaction_type,
            "data": data,
        }
        session.conversation_history.append(interaction)

    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get current status of an interview session."""

        if session_id not in self.active_sessions:
            return {"error": "Session not found"}

        session = self.active_sessions[session_id]

        return {
            "session_id": session_id,
            "candidate_name": session.candidate_name,
            "position": session.position,
            "phase": session.phase.value,
            "questions_count": session.questions_count,
            "average_response_quality": session.average_response_quality,
            "should_continue": session.should_continue,
            "needs_human_intervention": session.needs_human_intervention,
            "completion_reason": session.completion_reason,
            "technical_domains": session.interview_state.technical_domains,
            "topics_covered": session.interview_state.topics_covered,
        }

    def end_session(
        self, session_id: str, reason: str = "manual_termination"
    ) -> Dict[str, Any]:
        """End an interview session."""

        if session_id not in self.active_sessions:
            return {"error": "Session not found"}

        session = self.active_sessions[session_id]
        session.phase = InterviewPhase.COMPLETED
        session.should_continue = False
        session.completion_reason = reason

        # Generate final summary
        summary = session.question_generator.get_interview_summary()

        return {
            "session_id": session_id,
            "status": "ended",
            "reason": reason,
            "summary": summary,
            "conversation_history": session.conversation_history,
        }

    def export_session_data(self, session_id: str) -> Dict[str, Any]:
        """Export complete session data for analysis."""

        if session_id not in self.active_sessions:
            return {"error": "Session not found"}

        session = self.active_sessions[session_id]
        summary = session.question_generator.get_interview_summary()

        return {
            "session_metadata": {
                "session_id": session.session_id,
                "candidate_name": session.candidate_name,
                "position": session.position,
                "start_time": session.start_time.isoformat(),
                "total_questions": session.questions_count,
                "average_response_quality": session.average_response_quality,
            },
            "technical_analysis": {
                "extracted_cv_topics": session.interview_state.cv_topics,
                "extracted_jd_topics": session.interview_state.jd_topics,
                "relevant_topics": session.interview_state.relevant_topics,
                "technical_domains": session.interview_state.technical_domains,
                "topics_covered": session.interview_state.topics_covered,
            },
            "interview_summary": summary,
            "conversation_history": session.conversation_history,
        }
