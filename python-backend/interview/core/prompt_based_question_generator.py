"""
Simple prompt-based question generator using the technical interview prompts.
This is designed to work with the existing session manager without modifications.
"""

import re
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from ..llm.base import BaseLLM
from ..config.settings import QuestionType


class InterviewPhase(Enum):
    """Different phases of the interview."""

    GREETING = "greeting"
    STRUCTURE_EXPLANATION = "structure_explanation"
    TECHNICAL_QUESTIONS = "technical_questions"
    CLOSING = "closing"


class ConversationDepth(Enum):
    """Levels of conversation depth."""

    SURFACE = "surface"
    MODERATE = "moderate"
    DEEP = "deep"
    EXPERT = "expert"


class QuestionIntent(Enum):
    """Intent behind asking a question."""

    EXPLORE_NEW_TOPIC = "explore_new_topic"
    CLARIFY_UNDERSTANDING = "clarify_understanding"
    PROBE_DEEPER = "probe_deeper"
    ASSESS_EXPERIENCE = "assess_experience"
    VERIFY_KNOWLEDGE = "verify_knowledge"
    TRANSITION_TOPIC = "transition_topic"


@dataclass
class ConversationContext:
    """Context tracking for natural conversation flow."""

    current_topic: str
    depth_level: ConversationDepth
    topics_covered: List[str]
    candidate_skill_level: str
    answer_quality_trend: List[float]
    follow_up_count: int
    needs_topic_change: bool
    conversation_energy: str
    has_been_greeted: bool = False
    previous_answers: List[str] = None
    question_count: int = 0
    interview_phase: InterviewPhase = InterviewPhase.GREETING
    candidate_name: str = "candidate"
    cv_keywords: List[str] = None
    job_title: str = "Software Developer"

    def __post_init__(self):
        if self.previous_answers is None:
            self.previous_answers = []
        if self.cv_keywords is None:
            self.cv_keywords = []


@dataclass
class QuestionMetadata:
    """Metadata for generated questions."""

    question_type: QuestionType
    intent: QuestionIntent
    difficulty_level: str
    expected_depth: ConversationDepth
    topic_area: str
    prerequisites: List[str]


class PromptBasedQuestionGenerator:
    """
    Simple question generator that uses the technical interview prompt structure.
    Works with existing session manager without requiring changes.
    """

    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self.conversation_context = None
        self.available_topics = []
        self.cv_content = ""
        self.resume_sections = {}

    def initialize_conversation(
        self, resume_sections: Dict[str, str], job_description: str = ""
    ) -> ConversationContext:
        """Initialize conversation context based on resume and job description."""
        self.resume_sections = resume_sections
        self.cv_content = " ".join(resume_sections.values())

        # Extract keywords from CV
        cv_keywords = self._extract_cv_keywords(self.cv_content)

        # Extract job title from job description
        job_title = self._extract_job_title(job_description)

        # Assess initial skill level
        skill_level = self._assess_initial_skill_level(resume_sections)

        # Extract candidate name if possible
        candidate_name = self._extract_candidate_name(resume_sections)

        # Select starting topic
        starting_topic = cv_keywords[0] if cv_keywords else "technical background"

        context = ConversationContext(
            current_topic=starting_topic,
            depth_level=ConversationDepth.SURFACE,
            topics_covered=[],
            candidate_skill_level=skill_level,
            answer_quality_trend=[],
            follow_up_count=0,
            needs_topic_change=False,
            conversation_energy="neutral",
            has_been_greeted=False,
            question_count=0,
            interview_phase=InterviewPhase.GREETING,
            candidate_name=candidate_name,
            cv_keywords=cv_keywords,
            job_title=job_title,
        )

        self.conversation_context = context
        return context

    def get_next_question(
        self,
        context: ConversationContext,
        last_answer: Optional[str] = None,
        answer_evaluation: Optional[Dict] = None,
    ) -> Tuple[str, QuestionMetadata]:
        """Generate the next question based on current context and interview phase."""

        if context.interview_phase == InterviewPhase.GREETING:
            question = self._generate_greeting(context)
            context.interview_phase = InterviewPhase.STRUCTURE_EXPLANATION
            context.has_been_greeted = True

        elif context.interview_phase == InterviewPhase.STRUCTURE_EXPLANATION:
            question = self._generate_structure_explanation(context)
            context.interview_phase = InterviewPhase.TECHNICAL_QUESTIONS

        elif context.interview_phase == InterviewPhase.TECHNICAL_QUESTIONS:
            if (
                context.question_count >= 20
            ):  # After 20 technical questions, go to closing (increased from 15)
                context.interview_phase = InterviewPhase.CLOSING
                question = self._generate_closing(context)
            else:
                question = self._generate_technical_question(
                    context, last_answer, answer_evaluation
                )

        elif context.interview_phase == InterviewPhase.CLOSING:
            question = "Thank you for your time. The interview is now complete."

        else:
            question = self._generate_technical_question(
                context, last_answer, answer_evaluation
            )

        # Create metadata
        metadata = QuestionMetadata(
            question_type=QuestionType.TECHNICAL,
            intent=QuestionIntent.ASSESS_EXPERIENCE,
            difficulty_level=context.candidate_skill_level,
            expected_depth=context.depth_level,
            topic_area=context.current_topic,
            prerequisites=[],
        )

        context.question_count += 1
        return question, metadata

    def _generate_greeting(self, context: ConversationContext) -> str:
        """Generate brief greeting using the prompt template."""
        prompt = f"""You are Alex Rivera, Senior Hiring Manager at TechNova. Give a brief, warm greeting for the {context.job_title} technical interview. Keep it very short (under 15 seconds). Just introduce yourself briefly and confirm they're ready. Output only your spoken dialogue.

Example format:
"Hi {context.candidate_name}! I'm Alex Rivera from TechNova. Ready to dive into some technical questions about your background?"

Generate a brief greeting:"""

        try:
            response = self.llm.complete(prompt)
            return (
                response.text.strip()
                if response and hasattr(response, "text")
                else self._fallback_greeting(context)
            )
        except Exception:
            return self._fallback_greeting(context)

    def _generate_structure_explanation(self, context: ConversationContext) -> str:
        """Generate brief structure explanation using the prompt template."""
        cv_keywords_str = (
            ", ".join(context.cv_keywords[:3])
            if context.cv_keywords
            else "your technical background"
        )

        prompt = f"""briefly explain this will be a technical interview focused on {cv_keywords_str} from their CV. Keep it very short - just mention you'll ask technical questions based on their experience. Don't go into detailed timing. Get straight to the technical questions.

Generate a brief structure explanation:"""

        try:
            response = self.llm.complete(prompt)
            return (
                response.text.strip()
                if response and hasattr(response, "text")
                else self._fallback_structure_explanation(context)
            )
        except Exception:
            return self._fallback_structure_explanation(context)

    def _generate_technical_question(
        self,
        context: ConversationContext,
        last_answer: Optional[str] = None,
        answer_evaluation: Optional[Dict] = None,
    ) -> str:
        """Generate technical questions using the prompt template."""

        cv_keywords_str = (
            ", ".join(context.cv_keywords)
            if context.cv_keywords
            else "technical skills"
        )

        # Build context about previous answers
        previous_context = ""
        if last_answer:
            score = (
                answer_evaluation.get("overall_score", 0.5)
                if answer_evaluation
                else 0.5
            )
            if score < 0.4:
                previous_context = "The candidate struggled with the previous question. Provide a hint or ask a simpler follow-up."
            elif score > 0.8:
                previous_context = "The candidate answered well. You can ask a slightly more challenging question."

        prompt = f"""ask a fundamental, academically grounded technical question directly tied to these CV keywords: {cv_keywords_str}. 

The question should:
- Test theoretical knowledge and understanding
- Be based on technologies/concepts from their CV
- Have clear, academic answers
- Be appropriate for a {context.job_title} role
- Focus on concepts like: {context.current_topic}

{previous_context}

Topics already covered: {context.topics_covered}

Examples of good technical questions:
- "Can you explain how [technology from CV] works under the hood?"
- "What are the key differences between [concept A] and [concept B] that you've used?"
- "Describe the core principles behind [framework/technology from CV]"

Generate one focused technical question:"""

        try:
            response = self.llm.complete(prompt)
            question = (
                response.text.strip()
                if response and hasattr(response, "text")
                else self._fallback_technical_question(context)
            )

            # Update topics covered - but don't switch topics too frequently
            if context.current_topic not in context.topics_covered:
                context.topics_covered.append(context.current_topic)

            # Switch topic for next question (but only after asking 2-3 questions on current topic)
            if (
                context.cv_keywords
                and len(context.topics_covered) < len(context.cv_keywords)
                and context.question_count % 3 == 0
            ):  # Switch topic every 3 questions
                next_topic = next(
                    (
                        kw
                        for kw in context.cv_keywords
                        if kw not in context.topics_covered
                    ),
                    context.current_topic,
                )
                context.current_topic = next_topic

            return question

        except Exception:
            return self._fallback_technical_question(context)

    def _generate_closing(self, context: ConversationContext) -> str:
        """Generate closing using the prompt template."""
        positive_aspect = (
            context.cv_keywords[0] if context.cv_keywords else "technical knowledge"
        )

        prompt = f"""close warmly: "Thank you, {context.candidate_name}, for sharing your expertise—your {positive_aspect} knowledge was impressive." Outline next steps: "We'll review and follow up within 3 business days via email." End positively.

Generate the closing:"""

        try:
            response = self.llm.complete(prompt)
            return (
                response.text.strip()
                if response and hasattr(response, "text")
                else self._fallback_closing(context)
            )
        except Exception:
            return self._fallback_closing(context)

    # Helper methods for extraction and fallbacks

    def _extract_cv_keywords(self, cv_content: str) -> List[str]:
        """Extract technical keywords from CV content."""
        # Common technical keywords to look for
        tech_keywords = [
            "python",
            "javascript",
            "java",
            "react",
            "nodejs",
            "mongodb",
            "sql",
            "mysql",
            "postgresql",
            "html",
            "css",
            "django",
            "flask",
            "express",
            "angular",
            "vue",
            "typescript",
            "docker",
            "kubernetes",
            "aws",
            "azure",
            "git",
            "machine learning",
            "data science",
            "api",
            "rest",
            "graphql",
        ]

        found_keywords = []
        cv_lower = cv_content.lower()

        for keyword in tech_keywords:
            if keyword in cv_lower:
                found_keywords.append(keyword.title())

        return found_keywords[:5]  # Return top 5 keywords

    def _extract_job_title(self, job_description: str) -> str:
        """Extract job title from job description."""
        # Simple extraction - look for common job titles
        job_titles = [
            "software developer",
            "software engineer",
            "full stack developer",
            "frontend developer",
            "backend developer",
            "data scientist",
            "machine learning engineer",
            "devops engineer",
        ]

        jd_lower = job_description.lower()
        for title in job_titles:
            if title in jd_lower:
                return title.title()

        return "Software Developer"

    def _extract_candidate_name(self, resume_sections: Dict[str, str]) -> str:
        """Extract candidate name from resume sections."""
        # Look in personal info or contact sections
        for section_name, content in resume_sections.items():
            if "personal" in section_name.lower() or "contact" in section_name.lower():
                # Simple name extraction - first line that looks like a name
                lines = content.split("\n")
                for line in lines[:3]:  # Check first 3 lines
                    line = line.strip()
                    if len(line.split()) == 2 and line.replace(" ", "").isalpha():
                        return line
        return "candidate"

    def _assess_initial_skill_level(self, resume_sections: Dict[str, str]) -> str:
        """Assess initial skill level from resume."""
        cv_text = " ".join(resume_sections.values()).lower()

        # Count experience indicators
        experience_indicators = [
            "years",
            "senior",
            "lead",
            "architect",
            "expert",
            "advanced",
        ]
        skill_indicators = ["proficient", "experienced", "skilled", "familiar"]

        exp_count = sum(
            1 for indicator in experience_indicators if indicator in cv_text
        )
        skill_count = sum(1 for indicator in skill_indicators if indicator in cv_text)

        if exp_count >= 3:
            return "advanced"
        elif exp_count >= 1 or skill_count >= 2:
            return "intermediate"
        else:
            return "beginner"

    # Fallback methods

    def _fallback_greeting(self, context: ConversationContext) -> str:
        return f"Hi {context.candidate_name}! I'm Alex Rivera from TechNova. Ready for some technical questions?"

    def _fallback_structure_explanation(self, context: ConversationContext) -> str:
        return f"I'll ask you technical questions based on your CV experience. Let's start!"

    def _fallback_technical_question(self, context: ConversationContext) -> str:
        return f"Can you tell me about your experience with {context.current_topic} and how you've applied it in your projects?"

    def _fallback_closing(self, context: ConversationContext) -> str:
        return f"Thank you {context.candidate_name} for your time today. Your technical knowledge was impressive. We'll be in touch within 3 business days with next steps."
