"""
Simple prompt-based question generator using the technical interview prompts.
This is designed to work with the existing session manager without modifications.
"""

import re
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from ..llm.base import BaseLLM
from ..config.settings import QuestionType, InterviewConfig
from ..prompts import (
    CV_KEYWORDS_EXTRACTION_PROMPT,
    SKILL_LEVEL_ASSESSMENT_PROMPT,
    GREETING_PROMPT,
    FALLBACK_GREETING,
    STRUCTURE_EXPLANATION_PROMPT,
    FALLBACK_STRUCTURE_EXPLANATION,
    EXPERIENTIAL_QUESTION_PROMPT,
    FALLBACK_EXPERIENTIAL_QUESTION,
    TECHNICAL_QUESTION_PROMPT,
    FALLBACK_TECHNICAL_QUESTION,
    PERFORMANCE_GUIDANCE,
    PREVIOUS_ANSWER_CONTEXT,
    CLOSING_PROMPT,
    FALLBACK_CLOSING,
)


class InterviewPhase(Enum):
    """Different phases of the interview."""

    GREETING = "greeting"
    STRUCTURE_EXPLANATION = "structure_explanation"
    EXPERIENTIAL_QUESTIONS = "experiential_questions"
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
    cv_experiences: List[str] = None
    cv_projects: List[str] = None
    experiential_questions_asked: int = 0
    last_mentioned_concepts: List[str] = None  # Track what candidate mentioned
    conversation_history: List[Dict[str, str]] = None  # Track Q&A pairs

    def __post_init__(self):
        if self.previous_answers is None:
            self.previous_answers = []
        if self.cv_keywords is None:
            self.cv_keywords = []
        if self.cv_experiences is None:
            self.cv_experiences = []
        if self.cv_projects is None:
            self.cv_projects = []
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
    interview_phase: InterviewPhase


class PromptBasedQuestionGenerator:
    """
    Simple question generator that uses the technical interview prompt structure.
    Works with existing session manager without requiring changes.
    """

    def __init__(self, llm: BaseLLM, config: Optional[InterviewConfig] = None):
        """Initialize the question generator with an LLM instance and configuration."""
        self.llm = llm
        self.config = config or InterviewConfig()
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

        # Extract keywords from CV and JD (JD-weighted)
        cv_keywords = self._extract_cv_keywords(self.cv_content, job_description)

        # Extract job title from job description
        job_title = self._extract_job_title(job_description)

        # Assess initial skill level
        skill_level = self._assess_initial_skill_level(resume_sections)

        # Extract candidate name if possible
        candidate_name = self._extract_candidate_name(resume_sections)

        # Select starting topic
        starting_topic = cv_keywords[0] if cv_keywords else "technical background"

        # Extract experiences and projects
        experiences = self._extract_experiences(resume_sections)
        projects = self._extract_projects(resume_sections)

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
            cv_experiences=experiences,
            cv_projects=projects,
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
            if self.config.include_structure_explanation:
                question = self._generate_structure_explanation(context)
                # Move to experiential questions next
                context.interview_phase = (
                    InterviewPhase.EXPERIENTIAL_QUESTIONS
                    if self.config.include_experiential_questions
                    else InterviewPhase.TECHNICAL_QUESTIONS
                )
            else:
                # Skip structure explanation if disabled in config
                context.interview_phase = (
                    InterviewPhase.EXPERIENTIAL_QUESTIONS
                    if self.config.include_experiential_questions
                    else InterviewPhase.TECHNICAL_QUESTIONS
                )
                question = (
                    self._generate_experiential_question(context, last_answer, answer_evaluation)
                    if self.config.include_experiential_questions
                    else self._generate_technical_question(context, last_answer, answer_evaluation)
                )

        elif context.interview_phase == InterviewPhase.EXPERIENTIAL_QUESTIONS:
            # Ask experiential questions up to the configured limit, then move to technical
            question = self._generate_experiential_question(
                context, last_answer, answer_evaluation
            )
            context.experiential_questions_asked += 1
            if context.experiential_questions_asked >= self.config.experiential_questions_limit:
                context.interview_phase = InterviewPhase.TECHNICAL_QUESTIONS

        elif context.interview_phase == InterviewPhase.TECHNICAL_QUESTIONS:
            if (
                context.question_count >= 20
            ):  # After 20 technical questions, go to closing
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

        # Create metadata based on current phase
        if context.interview_phase == InterviewPhase.STRUCTURE_EXPLANATION:
            question_type = QuestionType.STRUCTURE_EXPLANATION
            intent = QuestionIntent.CLARIFY_UNDERSTANDING
        elif context.interview_phase == InterviewPhase.GREETING:
            question_type = QuestionType.BEHAVIORAL
            intent = QuestionIntent.EXPLORE_NEW_TOPIC
        elif context.interview_phase == InterviewPhase.CLOSING:
            question_type = QuestionType.BEHAVIORAL
            intent = QuestionIntent.TRANSITION_TOPIC
        elif context.interview_phase == InterviewPhase.EXPERIENTIAL_QUESTIONS:
            question_type = QuestionType.EXPERIENTIAL
            intent = QuestionIntent.ASSESS_EXPERIENCE
        else:
            question_type = QuestionType.TECHNICAL
            intent = QuestionIntent.PROBE_DEEPER

        metadata = QuestionMetadata(
            question_type=question_type,
            intent=intent,
            difficulty_level=context.candidate_skill_level,
            expected_depth=context.depth_level,
            topic_area=context.current_topic,
            prerequisites=[],
            interview_phase=context.interview_phase,
        )

        context.question_count += 1
        return question, metadata

    def _generate_greeting(self, context: ConversationContext) -> str:
        """Generate brief greeting using the prompt template."""
        cv_keywords = (
            ", ".join(context.cv_keywords[:2])
            if context.cv_keywords
            else "their technical background"
        )
        primary_technology = (
            context.cv_keywords[0] if context.cv_keywords else "technology"
        )

        prompt = GREETING_PROMPT.format(
            job_title=context.job_title,
            cv_keywords=cv_keywords,
            candidate_name=context.candidate_name,
            primary_technology=primary_technology,
        )

        try:
            response = self.llm.complete(prompt)
            return (
                response.text.strip()
                if response and hasattr(response, "text")
                else self._fallback_greeting(context)
            )
        except Exception:
            return self._fallback_greeting(context)

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
            score = answer_evaluation.get("relevance_score", 0.5)

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
                performance_guidance = PERFORMANCE_GUIDANCE["struggled"]
            elif score < 0.6:
                performance_guidance = PERFORMANCE_GUIDANCE["partial"]
            elif score < 0.8:
                performance_guidance = PERFORMANCE_GUIDANCE["good"]
            else:
                performance_guidance = PERFORMANCE_GUIDANCE["excellent"]

            # Extract key concepts from their answer for follow-up
            concepts_mentioned = (
                ", ".join(mentioned_concepts[:3])
                if mentioned_concepts
                else "the topics discussed"
            )
            previous_context = PREVIOUS_ANSWER_CONTEXT.format(
                last_answer_preview=last_answer[:200],
                concepts_mentioned=concepts_mentioned,
                score=score,
                performance_guidance=performance_guidance,
            )

        # Determine question type based on context
        if context.question_count <= 8:
            question_type = "foundational"
        elif context.question_count <= 10:
            question_type = "practical application"
        else:
            question_type = "advanced/scenario-based"

        prompt = TECHNICAL_QUESTION_PROMPT.format(
            cv_keywords=cv_keywords_str,
            current_topic=context.current_topic,
            question_type=question_type,
            topics_covered=context.topics_covered,
            previous_context=previous_context,
            performance_guidance=(
                performance_guidance
                if "performance_guidance" in locals()
                else "Ask an appropriate follow-up question"
            ),
        )

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

        prompt = CLOSING_PROMPT.format(
            candidate_name=context.candidate_name, positive_aspect=positive_aspect
        )

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

    def _extract_cv_keywords(self, cv_content: str, jd_content: str) -> List[str]:
        """Extract technical keywords from CV and JD content using LLM (JD-weighted)."""
        if not (cv_content.strip() or jd_content.strip()):
            return ["General Programming"]

        prompt = CV_KEYWORDS_EXTRACTION_PROMPT.format(cv_content=cv_content, jd_content=jd_content)

        try:
            response = self.llm.complete(prompt)
            if response and hasattr(response, "text"):
                keywords_text = response.text.strip()
                # Parse the comma-separated response
                keywords = [kw.strip() for kw in keywords_text.split(",") if kw.strip()]
                # Clean and format keywords
                formatted_keywords = []
                for keyword in keywords[:15]:  # Limit to 15 keywords
                    cleaned = keyword.strip().strip('"').strip("'")
                    if cleaned and len(cleaned) > 1:
                        formatted_keywords.append(cleaned)

                return (
                    formatted_keywords
                    if formatted_keywords
                    else self._fallback_extract_cv_keywords(cv_content, jd_content)
                )
            else:
                return self._fallback_extract_cv_keywords(cv_content, jd_content)

        except Exception as e:
            print(f"Error extracting CV/JD keywords with LLM: {e}")
            return self._fallback_extract_cv_keywords(cv_content, jd_content)

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
        """Assess initial skill level from resume using LLM analysis."""
        cv_text = " ".join(resume_sections.values())

        if not cv_text.strip():
            return "beginner"

        prompt = SKILL_LEVEL_ASSESSMENT_PROMPT.format(cv_content=cv_text)

        try:
            response = self.llm.complete(prompt)
            if response and hasattr(response, "text"):
                skill_level = response.text.strip().lower()
                # Validate and return appropriate skill level
                if "advanced" in skill_level:
                    return "advanced"
                elif "intermediate" in skill_level:
                    return "intermediate"
                elif "beginner" in skill_level:
                    return "beginner"
                else:
                    # If LLM response is unclear, fall back to keyword analysis
                    return self._fallback_assess_skill_level(cv_text)
            else:
                return self._fallback_assess_skill_level(cv_text)

        except Exception as e:
            print(f"Error assessing skill level with LLM: {e}")
            return self._fallback_assess_skill_level(cv_text)

    # Fallback methods

    def _fallback_greeting(self, context: ConversationContext) -> str:
        tech_mention = f" with {context.cv_keywords[0]}" if context.cv_keywords else ""
        return FALLBACK_GREETING.format(
            candidate_name=context.candidate_name, tech_mention=tech_mention
        )

    def _fallback_extract_cv_keywords(self, cv_content: str, jd_content: str = "") -> List[str]:
        """Fallback method for CV keyword extraction when LLM fails."""
        # Comprehensive technical keywords covering all major domains
        tech_keywords = [
            # Programming Languages
            "python",
            "javascript",
            "java",
            "c++",
            "c#",
            "go",
            "rust",
            "swift",
            "kotlin",
            "typescript",
            "php",
            "ruby",
            "scala",
            "r",
            "matlab",
            "perl",
            # Web Technologies
            "react",
            "angular",
            "vue",
            "nodejs",
            "django",
            "flask",
            "spring",
            "express",
            "html",
            "css",
            "bootstrap",
            "tailwind",
            "sass",
            "webpack",
            "next.js",
            "nuxt",
            # Mobile Development
            "react native",
            "flutter",
            "ionic",
            "xamarin",
            "android",
            "ios",
            "swift ui",
            # Databases & Storage
            "sql",
            "mysql",
            "postgresql",
            "mongodb",
            "redis",
            "elasticsearch",
            "cassandra",
            "oracle",
            "sqlite",
            # Cloud & DevOps
            "aws",
            "azure",
            "gcp",
            "docker",
            "kubernetes",
            "jenkins",
            "github actions",
            "gitlab ci",
            "terraform",
            "ansible",
            "prometheus",
            "grafana",
            # Data & ML
            "pandas",
            "numpy",
            "scikit-learn",
            "tensorflow",
            "pytorch",
            "spark",
            "hadoop",
            "tableau",
            "power bi",
            # Architecture & APIs
            "microservices",
            "rest",
            "graphql",
            "grpc",
            "system design",
            "design patterns",
            "clean code",
            # Security & Testing
            "oauth",
            "jwt",
            "owasp",
            "unit testing",
            "integration testing",
            "selenium",
            "jest",
            "pytest"
        ]
        cv_lower = (cv_content or "").lower()
        jd_lower = (jd_content or "").lower()

        found_jd = [kw for kw in tech_keywords if kw in jd_lower]
        found_cv = [kw for kw in tech_keywords if kw in cv_lower]

        ordered = []
        for kw in found_jd + found_cv:
            if kw not in ordered:
                ordered.append(kw)

        if not ordered:
            ordered = [
                "python","system design","rest","react","docker","aws","ci/cd","postgresql","unit testing","kubernetes","microservices","logging"
            ]

        def present(k: str) -> str:
            mapping = {"ci/cd": "CI/CD", "rest": "REST APIs", "jwt": "JWT"}
            return mapping.get(k, k.title() if k.isalpha() else k)

        return [present(k) for k in ordered][:12]

    def _fallback_assess_skill_level(self, cv_text: str) -> str:
        """Fallback method for skill level assessment when LLM fails."""
        cv_lower = cv_text.lower()

        # Enhanced experience indicators
        advanced_indicators = [
            "senior",
            "lead",
            "architect",
            "principal",
            "director",
            "manager",
            "team lead",
            "tech lead",
            "staff engineer",
            "expert",
            "specialist",
        ]

        intermediate_indicators = [
            "mid",
            "intermediate",
            "experienced",
            "developer ii",
            "engineer ii",
            "associate",
            "skilled",
            "proficient",
            "3 years",
            "4 years",
            "5 years",
        ]

        beginner_indicators = [
            "junior",
            "entry",
            "trainee",
            "intern",
            "graduate",
            "fresher",
            "1 year",
            "2 years",
            "recent graduate",
        ]

        # Count indicators
        advanced_count = sum(
            1 for indicator in advanced_indicators if indicator in cv_lower
        )
        intermediate_count = sum(
            1 for indicator in intermediate_indicators if indicator in cv_lower
        )
        beginner_count = sum(
            1 for indicator in beginner_indicators if indicator in cv_lower
        )

        # Assess based on counts
        if advanced_count >= 2:
            return "advanced"
        elif intermediate_count >= 2 or advanced_count >= 1:
            return "intermediate"
        elif beginner_count >= 1:
            return "beginner"
        else:
            return "intermediate"  # Default to intermediate if unclear

    def _fallback_technical_question(self, context: ConversationContext) -> str:
        return FALLBACK_TECHNICAL_QUESTION.format(current_topic=context.current_topic)

    def _fallback_closing(self, context: ConversationContext) -> str:
        primary_technology = (
            context.cv_keywords[0] if context.cv_keywords else "technology"
        )
        return FALLBACK_CLOSING.format(
            candidate_name=context.candidate_name, primary_technology=primary_technology
        )

    def _generate_structure_explanation(self, context: ConversationContext) -> str:
        """Generate a brief explanation of the interview structure."""
        try:
            response = self.llm.complete(STRUCTURE_EXPLANATION_PROMPT)
            return (
                response.text.strip()
                if response and hasattr(response, "text")
                else FALLBACK_STRUCTURE_EXPLANATION
            )
        except Exception:
            return FALLBACK_STRUCTURE_EXPLANATION

    def _generate_experiential_question(
        self,
        context: ConversationContext,
        last_answer: Optional[str] = None,
        answer_evaluation: Optional[Dict] = None,
    ) -> str:
        """Generate an experiential question based on CV experiences and projects."""
        experiences_str = "\n".join(context.cv_experiences or [])
        projects_str = "\n".join(context.cv_projects or [])
        topics_covered_str = ", ".join(context.topics_covered or []) or "none"

        prompt = EXPERIENTIAL_QUESTION_PROMPT.format(
            candidate_name=context.candidate_name,
            job_title=context.job_title,
            cv_experiences=experiences_str,
            cv_projects=projects_str,
            topics_covered=topics_covered_str,
        )

        try:
            response = self.llm.complete(prompt)
            return (
                response.text.strip()
                if response and hasattr(response, "text")
                else FALLBACK_EXPERIENTIAL_QUESTION
            )
        except Exception:
            return FALLBACK_EXPERIENTIAL_QUESTION

    def _extract_experiences(self, resume_sections: Dict[str, str]) -> List[str]:
        """Extract experience items from resume sections."""
        items: List[str] = []
        for name, content in resume_sections.items():
            if any(k in name.lower() for k in ["experience", "work", "employment"]):
                for line in content.splitlines():
                    line = line.strip(" -*•")
                    if len(line) > 6:
                        items.append(line)
        # Deduplicate and limit
        seen = set()
        result: List[str] = []
        for it in items:
            key = it.lower()
            if key not in seen:
                seen.add(key)
                result.append(it)
        return result[:10]

    def _extract_projects(self, resume_sections: Dict[str, str]) -> List[str]:
        """Extract project items from resume sections."""
        items: List[str] = []
        for name, content in resume_sections.items():
            if "project" in name.lower():
                for line in content.splitlines():
                    line = line.strip(" -*•")
                    if len(line) > 4:
                        items.append(line)
        # Deduplicate and limit
        seen = set()
        result: List[str] = []
        for it in items:
            key = it.lower()
            if key not in seen:
                seen.add(key)
                result.append(it)
        return result[:10]
