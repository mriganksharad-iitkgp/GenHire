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
    last_mentioned_concepts: List[str] = None  # Track what candidate mentioned
    conversation_history: List[Dict[str, str]] = None  # Track Q&A pairs

    def __post_init__(self):
        if self.previous_answers is None:
            self.previous_answers = []
        if self.cv_keywords is None:
            self.cv_keywords = []
        if self.last_mentioned_concepts is None:
            self.last_mentioned_concepts = []
        if self.conversation_history is None:
            self.conversation_history = []


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
        prompt = f"""You are Alex Rivera, Senior Hiring Manager at TechNova. Give a warm, natural greeting for the {context.job_title} technical interview. 

Be conversational and friendly. Mention you've reviewed their CV and are excited to discuss their experience with {", ".join(context.cv_keywords[:2]) if context.cv_keywords else "their technical background"}.

Keep it brief but engaging (15-20 seconds max). Output only your spoken dialogue.

Example tone:
"Hi {context.candidate_name}! I'm Alex Rivera from TechNova. I've been looking over your CV and I'm really excited to discuss your experience with {context.cv_keywords[0] if context.cv_keywords else 'technology'}. Ready to dive in?"

Generate a warm, personalized greeting:"""

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

        prompt = f"""As Alex Rivera, briefly and conversationally explain the interview format. Mention you'll have a technical discussion about their experience with {cv_keywords_str}. 

Make it sound like a friendly conversation, not a formal test. Be encouraging and set a positive tone.

Keep it very brief - just a quick overview before jumping into the technical discussion.

Example tone:
"Perfect! So today we'll have a friendly technical chat about your experience with {cv_keywords_str}. I'm curious to hear about the projects you've worked on and dive into some of the technical details. Sound good?"

Generate a brief, encouraging structure explanation:"""

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

        # Build context about previous answers and score
        previous_context = ""
        acknowledgment = ""
        follow_up_strategy = ""

        if last_answer and answer_evaluation:
            score = answer_evaluation.get("overall_score", 0.5)

            # Extract key concepts mentioned by candidate
            mentioned_concepts = self._extract_concepts_from_answer(last_answer)
            context.last_mentioned_concepts = mentioned_concepts

            # Store conversation history
            if context.conversation_history:
                last_question = context.conversation_history[-1].get("question", "")
                context.conversation_history.append(
                    {
                        "question": last_question,
                        "answer": (
                            last_answer[:200] + "..."
                            if len(last_answer) > 200
                            else last_answer
                        ),
                        "score": score,
                    }
                )

            # Analyze the candidate's answer to provide contextual response
            if score < 0.3:
                performance_guidance = "The candidate struggled with this concept. Acknowledge their effort positively, then ask a simpler foundational question to help build their confidence."
            elif score < 0.6:
                performance_guidance = "The candidate shows partial understanding. Acknowledge what they got right, then ask a follow-up question that builds on their response to deepen their knowledge."
            elif score < 0.8:
                performance_guidance = "The candidate demonstrated good understanding. Give positive acknowledgment of their explanation, then ask a slightly more advanced question to test deeper knowledge."
            else:
                performance_guidance = "The candidate showed excellent understanding. Acknowledge their strong answer enthusiastically, then ask a challenging question or explore a different but related area."

            # Extract key concepts from their answer for follow-up
            concepts_mentioned = (
                ", ".join(mentioned_concepts[:3])
                if mentioned_concepts
                else "the topics discussed"
            )
            previous_context = f"""
Previous answer context: The candidate just explained: "{last_answer[:200]}..."
Key concepts they mentioned: {concepts_mentioned}
Score: {score:.2f}/1.0
Performance guidance: {performance_guidance}
"""

        # Determine question type based on context
        if context.question_count <= 3:
            question_type = "foundational"
        elif context.question_count <= 6:
            question_type = "practical application"
        else:
            question_type = "advanced/scenario-based"

        prompt = f"""You are Alex Rivera, an experienced technical interviewer. You're having a natural conversation with a candidate about their technical background.

CANDIDATE'S CV TECHNOLOGIES: {cv_keywords_str}
CURRENT FOCUS TOPIC: {context.current_topic}
QUESTION TYPE NEEDED: {question_type}
TOPICS ALREADY COVERED: {context.topics_covered}

{previous_context}

INSTRUCTIONS:
1. FIRST: Create a natural acknowledgment of their previous answer based on what they actually said
2. THEN: Ask a {question_type} question about {context.current_topic}
3. Make the acknowledgment specific to their response content, not generic
4. Reference specific concepts they mentioned when possible
5. Keep it conversational and encouraging
6. Follow the performance guidance: {performance_guidance if 'performance_guidance' in locals() else 'Ask an appropriate follow-up question'}

QUESTION TYPES BY STAGE:
- Foundational (Questions 1-8): Basic concepts, definitions, "how does X work?"
- Practical Application (Questions 9-10): "How have you used X?", "What challenges did you face?"
- Advanced/Scenario (Questions 11+): Complex scenarios, trade-offs, best practices

EXAMPLES OF NATURAL, CONTEXTUAL ACKNOWLEDGMENTS:
- "I like how you mentioned [specific concept from their answer]. Now, building on that..."
- "That's a solid approach with [technology they mentioned]. Tell me about..."
- "Good point about [specific detail]. In your experience, how do you handle..."
- "Interesting that you've worked with [tool/framework]. When you're using that..."

Generate a natural, conversational response with contextual acknowledgment:"""

        try:
            response = self.llm.complete(prompt)
            question = (
                response.text.strip()
                if response and hasattr(response, "text")
                else self._fallback_technical_question_with_context(
                    context, last_answer, score if "score" in locals() else 0.5
                )
            )

            # Update topics covered - but don't switch topics too frequently
            if context.current_topic not in context.topics_covered:
                context.topics_covered.append(context.current_topic)

            # Smarter topic switching based on conversation flow
            should_switch_topic = self._should_switch_topic(context, answer_evaluation)
            if should_switch_topic:
                next_topic = self._get_next_topic(context)
                if next_topic:
                    context.current_topic = next_topic

            return question

        except Exception as e:
            print(f"Error generating question: {e}")
            return self._fallback_technical_question_with_context(
                context, last_answer, score if "score" in locals() else 0.5
            )

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

    def _extract_concepts_from_answer(self, answer: str) -> List[str]:
        """Extract technical concepts mentioned by the candidate in their answer."""
        if not answer:
            return []

        # Common technical terms to look for
        technical_terms = [
            # Databases
            "sql",
            "mysql",
            "postgresql",
            "mongodb",
            "database",
            "query",
            "index",
            "join",
            "acid",
            "transaction",
            "schema",
            "normalization",
            "foreign key",
            "primary key",
            # Programming
            "python",
            "javascript",
            "java",
            "react",
            "nodejs",
            "django",
            "flask",
            "api",
            "rest",
            "graphql",
            "function",
            "class",
            "object",
            "variable",
            "loop",
            "array",
            # Cloud/DevOps
            "aws",
            "azure",
            "docker",
            "kubernetes",
            "server",
            "deployment",
            "cloud",
            "lambda",
            "ec2",
            "s3",
            "load balancer",
            "scaling",
            "microservices",
            # General CS
            "algorithm",
            "data structure",
            "performance",
            "optimization",
            "security",
            "authentication",
            "authorization",
            "encryption",
            "caching",
            "testing",
        ]

        answer_lower = answer.lower()
        found_concepts = []

        for term in technical_terms:
            if term in answer_lower:
                found_concepts.append(term)

        return found_concepts[:5]  # Return top 5 concepts mentioned

    def _should_switch_topic(
        self, context: ConversationContext, answer_evaluation: Optional[Dict]
    ) -> bool:
        """Determine if we should switch to a new topic based on conversation flow."""

        # Don't switch too early
        if context.question_count < 3:
            return False

        # Switch every 3-4 questions, but also consider performance
        base_switch_interval = 3

        if answer_evaluation:
            score = answer_evaluation.get("overall_score", 0.5)

            # If they're struggling (< 0.4), switch sooner to find their strengths
            if score < 0.4 and context.question_count % 2 == 0:
                return True

            # If they're doing well (> 0.8), can explore topic longer
            if score > 0.8:
                base_switch_interval = 4

        # Check if it's time to switch based on interval
        questions_on_current_topic = context.question_count % base_switch_interval
        return questions_on_current_topic == 0 and len(context.cv_keywords) > len(
            context.topics_covered
        )

    def _get_next_topic(self, context: ConversationContext) -> Optional[str]:
        """Get the next topic to explore based on CV keywords."""
        uncovered_topics = [
            topic
            for topic in context.cv_keywords
            if topic not in context.topics_covered
        ]

        if uncovered_topics:
            return uncovered_topics[0]

        # If all CV topics covered, cycle back to previous topics for deeper exploration
        if context.topics_covered:
            return context.topics_covered[
                context.question_count % len(context.topics_covered)
            ]

        return None

    def _fallback_technical_question_with_context(
        self, context: ConversationContext, last_answer: str = "", score: float = 0.5
    ) -> str:
        """Fallback method that includes contextual acknowledgment."""
        base_question = f"Can you tell me about your experience with {context.current_topic} and how you've applied it in your projects?"

        if last_answer:
            # Generate a simple contextual acknowledgment based on score
            if score < 0.4:
                acknowledgment = "I appreciate you working through that. Let me ask about something else - "
            elif score < 0.7:
                acknowledgment = "That's helpful context. Now, "
            else:
                acknowledgment = "Great insights! Building on that, "

            return f"{acknowledgment}{base_question.lower()}"
        return base_question

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
        tech_mention = f" with {context.cv_keywords[0]}" if context.cv_keywords else ""
        return f"Hi {context.candidate_name}! I'm Alex Rivera from TechNova. I've been reviewing your CV and I'm excited to discuss your experience{tech_mention}. Ready to get started?"

    def _fallback_structure_explanation(self, context: ConversationContext) -> str:
        cv_keywords_str = (
            ", ".join(context.cv_keywords[:2])
            if context.cv_keywords
            else "your technical background"
        )
        return f"Great! So today we'll have a technical conversation about your experience with {cv_keywords_str}. I'm looking forward to hearing about your projects and diving into some technical details!"

    def _fallback_technical_question(self, context: ConversationContext) -> str:
        return f"Tell me about your experience with {context.current_topic} - how have you used it in your projects, and what challenges have you encountered?"

    def _fallback_closing(self, context: ConversationContext) -> str:
        return f"Thank you {context.candidate_name} for such an engaging technical discussion! Your insights about {context.cv_keywords[0] if context.cv_keywords else 'technology'} were really impressive. We'll review everything and follow up within 3 business days with next steps."
