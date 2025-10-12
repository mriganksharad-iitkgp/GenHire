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
from ..prompts import (
    CV_KEYWORDS_EXTRACTION_PROMPT,
    SKILL_LEVEL_ASSESSMENT_PROMPT,
    GREETING_PROMPT,
    FALLBACK_GREETING,
    STRUCTURE_EXPLANATION_PROMPT,
    FALLBACK_STRUCTURE_EXPLANATION,
    TECHNICAL_QUESTION_PROMPT,
    FALLBACK_TECHNICAL_QUESTION,
    PERFORMANCE_GUIDANCE,
    PREVIOUS_ANSWER_CONTEXT,
    CLOSING_PROMPT,
    FALLBACK_CLOSING,
)
from ..prompts.experiential_question_prompts import (
    EXPERIENTIAL_QUESTION_PROMPT,
    FALLBACK_EXPERIENTIAL_QUESTION,
    EXPERIENTIAL_PERFORMANCE_GUIDANCE,
    EXPERIENTIAL_ANSWER_CONTEXT,
    EXPERIENTIAL_QUESTION_TEMPLATES,
    EXPERIENTIAL_FOLLOW_UPS,
    EXPERIENTIAL_QUESTION_FLOW,
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
    last_mentioned_concepts: List[str] = None  # Track what candidate mentioned
    conversation_history: List[Dict[str, str]] = None  # Track Q&A pairs
    cv_projects: List[Dict[str, str]] = None  # Track projects from CV
    cv_experiences: List[Dict[str, str]] = None  # Track work experiences from CV
    current_project_focus: str = None  # Current project being discussed
    projects_covered: List[str] = None  # Projects already discussed

    def __post_init__(self):
        if self.previous_answers is None:
            self.previous_answers = []
        if self.cv_keywords is None:
            self.cv_keywords = []
        if self.last_mentioned_concepts is None:
            self.last_mentioned_concepts = []
        if self.conversation_history is None:
            self.conversation_history = []
        if self.cv_projects is None:
            self.cv_projects = []
        if self.cv_experiences is None:
            self.cv_experiences = []
        if self.projects_covered is None:
            self.projects_covered = []


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

        # Extract projects and experiences from CV
        cv_projects = self._extract_cv_projects(resume_sections)
        cv_experiences = self._extract_cv_experiences(resume_sections)

        # Extract job title from job description
        job_title = self._extract_job_title(job_description)

        # Assess initial skill level
        skill_level = self._assess_initial_skill_level(resume_sections)

        # Extract candidate name if possible
        candidate_name = self._extract_candidate_name(resume_sections)

        # Select starting topic
        starting_topic = cv_keywords[0] if cv_keywords else "technical background"
        
        # Select starting project for experiential questions
        starting_project = cv_projects[0]["name"] if cv_projects else "your most recent project"

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
            cv_projects=cv_projects,
            cv_experiences=cv_experiences,
            current_project_focus=starting_project,
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
            context.interview_phase = InterviewPhase.EXPERIENTIAL_QUESTIONS
        
        elif context.interview_phase == InterviewPhase.EXPERIENTIAL_QUESTIONS:
            if context.question_count >= 7:
                context.interview_phase = InterviewPhase.TECHNICAL_QUESTIONS
                question = self._generate_technical_question(
                    context, last_answer, answer_evaluation
                )
            else:
                question = self._generate_experiential_question(
                    context, last_answer, answer_evaluation
                )
                                                
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
        if context.interview_phase == InterviewPhase.EXPERIENTIAL_QUESTIONS:
            metadata = QuestionMetadata(
                question_type=QuestionType.TECHNICAL,  # Using TECHNICAL as base type
                intent=QuestionIntent.ASSESS_EXPERIENCE,
                difficulty_level=context.candidate_skill_level,
                expected_depth=context.depth_level,
                topic_area=context.current_project_focus or "project experience",
                prerequisites=[],
            )
        else:
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

    def _generate_structure_explanation(self, context: ConversationContext) -> str:
        """Generate brief structure explanation using the prompt template."""
        cv_keywords_str = (
            ", ".join(context.cv_keywords)
            if context.cv_keywords
            else "your technical background"
        )

        prompt = STRUCTURE_EXPLANATION_PROMPT.format(cv_keywords=cv_keywords_str)

        try:
            response = self.llm.complete(prompt)
            return (
                response.text.strip()
                if response and hasattr(response, "text")
                else self._fallback_structure_explanation(context)
            )
        except Exception:
            return self._fallback_structure_explanation(context)

    def _generate_experiential_question(
        self,
        context: ConversationContext,
        last_answer: Optional[str] = None,
        answer_evaluation: Optional[Dict] = None,
    ) -> str:
        """Generate experiential questions using the prompt template."""
        
        # Prepare CV projects and experiences for the prompt
        cv_projects_str = self._format_cv_projects_for_prompt(context.cv_projects)
        cv_experiences_str = self._format_cv_experiences_for_prompt(context.cv_experiences)
        
        # Build context about previous answers and score
        previous_context = ""
        acknowledgment = ""
        follow_up_strategy = ""

        if last_answer and answer_evaluation:
            score = answer_evaluation.get("relevance_score", 0.5)

            # Extract key projects/experiences mentioned by candidate
            mentioned_projects = self._extract_projects_from_answer(last_answer)
            mentioned_technologies = self._extract_technologies_from_answer(last_answer)

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
                performance_guidance = EXPERIENTIAL_PERFORMANCE_GUIDANCE["vague"]
            elif score < 0.6:
                performance_guidance = EXPERIENTIAL_PERFORMANCE_GUIDANCE["surface"]
            elif score < 0.8:
                performance_guidance = EXPERIENTIAL_PERFORMANCE_GUIDANCE["detailed"]
            else:
                performance_guidance = EXPERIENTIAL_PERFORMANCE_GUIDANCE["comprehensive"]

            # Extract key concepts from their answer for follow-up
            projects_mentioned = (
                ", ".join(mentioned_projects[:2])
                if mentioned_projects
                else "the projects discussed"
            )
            technologies_mentioned = (
                ", ".join(mentioned_technologies[:3])
                if mentioned_technologies
                else "the technologies mentioned"
            )
            
            previous_context = EXPERIENTIAL_ANSWER_CONTEXT.format(
                last_answer_preview=last_answer[:200],
                experiences_mentioned=projects_mentioned,
                technologies_mentioned=technologies_mentioned,
                score=score,
                performance_guidance=performance_guidance,
            )

        # Determine question type based on context
        question_flow = EXPERIENTIAL_QUESTION_FLOW.get(
            context.question_count, 
            {"type": "project_overview", "focus": "General project discussion"}
        )
        question_type = question_flow["type"]

        prompt = EXPERIENTIAL_QUESTION_PROMPT.format(
            cv_projects=cv_projects_str,
            experiences=cv_experiences_str,
            current_focus=context.current_project_focus,
            question_type=question_type,
            topics_covered=context.projects_covered,
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
                else self._fallback_experiential_question_with_context(
                    context, last_answer, score if "score" in locals() else 0.5
                )
            )

            # Update projects covered
            if context.current_project_focus not in context.projects_covered:
                context.projects_covered.append(context.current_project_focus)

            # Switch to next project if needed
            should_switch_project = self._should_switch_project(context, answer_evaluation)
            if should_switch_project:
                next_project = self._get_next_project(context)
                if next_project:
                    context.current_project_focus = next_project

            return question

        except Exception as e:
            print(f"Error generating experiential question: {e}")
            return self._fallback_experiential_question_with_context(
                context, last_answer, score if "score" in locals() else 0.5
            )
    

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

    def _extract_cv_keywords(self, cv_content: str) -> List[str]:
        """Extract technical keywords from CV content using LLM."""
        if not cv_content.strip():
            return ["General Programming"]

        prompt = CV_KEYWORDS_EXTRACTION_PROMPT.format(cv_content=cv_content)

        try:
            response = self.llm.complete(prompt)
            if response and hasattr(response, "text"):
                keywords_text = response.text.strip()
                # Parse the comma-separated response
                keywords = [kw.strip() for kw in keywords_text.split(",") if kw.strip()]
                # Clean and format keywords
                formatted_keywords = []
                for keyword in keywords[:12]:  # Limit to 12 keywords
                    cleaned = keyword.strip().strip('"').strip("'")
                    if cleaned and len(cleaned) > 1:
                        formatted_keywords.append(cleaned)

                return (
                    formatted_keywords
                    if formatted_keywords
                    else self._fallback_extract_cv_keywords(cv_content)
                )
            else:
                return "fallback keywords"
                # return self._fallback_extract_cv_keywords(cv_content)

        except Exception as e:
            print(f"Error extracting CV keywords with LLM: {e}")
            return self._fallback_extract_cv_keywords(cv_content)

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

    def _fallback_extract_cv_keywords(self, cv_content: str) -> List[str]:
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
            "dynamodb",
            "firebase",
            # Cloud & Infrastructure
            "aws",
            "azure",
            "gcp",
            "docker",
            "kubernetes",
            "terraform",
            "ansible",
            "jenkins",
            "gitlab ci",
            "github actions",
            "heroku",
            "digital ocean",
            # Data Science & ML
            "machine learning",
            "data science",
            "tensorflow",
            "pytorch",
            "pandas",
            "numpy",
            "scikit-learn",
            "jupyter",
            "tableau",
            "power bi",
            "spark",
            "hadoop",
            # DevOps & Tools
            "git",
            "linux",
            "bash",
            "powershell",
            "nginx",
            "apache",
            "microservices",
            "ci/cd",
            "monitoring",
            "logging",
            "prometheus",
            "grafana",
            # Testing & QA
            "unit testing",
            "selenium",
            "jest",
            "pytest",
            "cypress",
            "postman",
            # API & Protocols
            "rest",
            "graphql",
            "grpc",
            "websockets",
            "api",
            "json",
            "xml",
            # Security
            "cybersecurity",
            "oauth",
            "jwt",
            "encryption",
            "penetration testing",
            # Emerging Tech
            "blockchain",
            "iot",
            "ar/vr",
            "computer vision",
            "nlp",
            "chatbot",
        ]

        found_keywords = []
        cv_lower = cv_content.lower()

        for keyword in tech_keywords:
            if keyword in cv_lower:
                # Capitalize properly
                if keyword in [
                    "iot",
                    "ar/vr",
                    "nlp",
                    "jwt",
                    "api",
                    "html",
                    "css",
                    "sql",
                ]:
                    found_keywords.append(keyword.upper())
                elif "/" in keyword:
                    found_keywords.append(keyword.upper())
                else:
                    found_keywords.append(keyword.title())

        return found_keywords[:12] if found_keywords else ["General Programming"]

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

    def _fallback_structure_explanation(self, context: ConversationContext) -> str:
        cv_keywords_str = (
            ", ".join(context.cv_keywords[:2])
            if context.cv_keywords
            else "your technical background"
        )
        return FALLBACK_STRUCTURE_EXPLANATION.format(cv_keywords=cv_keywords_str)

    def _fallback_technical_question(self, context: ConversationContext) -> str:
        return FALLBACK_TECHNICAL_QUESTION.format(current_topic=context.current_topic)

    def _fallback_closing(self, context: ConversationContext) -> str:
        primary_technology = (
            context.cv_keywords[0] if context.cv_keywords else "technology"
        )
        return FALLBACK_CLOSING.format(
            candidate_name=context.candidate_name, primary_technology=primary_technology
        )

    # Experiential question helper methods

    def _extract_cv_projects(self, resume_sections: Dict[str, str]) -> List[Dict[str, str]]:
        """Extract projects from CV sections."""
        projects = []
        
        # Look for common project section names
        project_sections = ["projects", "project", "portfolio", "work", "experience"]
        
        for section_name, content in resume_sections.items():
            if any(keyword in section_name.lower() for keyword in project_sections):
                # Simple project extraction - look for bullet points or numbered items
                lines = content.split('\n')
                current_project = {}
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                        
                    # Look for project titles (usually start with bullet points or numbers)
                    if line.startswith(('•', '-', '*', '1.', '2.', '3.', '4.', '5.')):
                        # Save previous project if exists
                        if current_project and 'name' in current_project:
                            projects.append(current_project)
                        
                        # Start new project
                        project_name = line.lstrip('•-*123456789. ').strip()
                        current_project = {
                            'name': project_name,
                            'description': '',
                            'technologies': []
                        }
                    elif current_project and 'name' in current_project:
                        # Add description or technology to current project
                        if any(tech in line.lower() for tech in ['python', 'javascript', 'react', 'node', 'java', 'c++', 'sql', 'mongodb', 'aws', 'docker']):
                            current_project['technologies'].append(line)
                        else:
                            current_project['description'] += ' ' + line
                
                # Add last project
                if current_project and 'name' in current_project:
                    projects.append(current_project)
        
        # If no projects found in specific sections, try to extract from general content
        if not projects:
            projects = self._fallback_extract_projects(resume_sections)
        
        return projects[:5]  # Limit to 5 projects

    def _extract_cv_experiences(self, resume_sections: Dict[str, str]) -> List[Dict[str, str]]:
        """Extract work experiences from CV sections."""
        experiences = []
        
        # Look for experience-related sections
        experience_sections = ["experience", "work", "employment", "career", "professional"]
        
        for section_name, content in resume_sections.items():
            if any(keyword in section_name.lower() for keyword in experience_sections):
                lines = content.split('\n')
                current_experience = {}
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Look for company names or job titles
                    if any(indicator in line.lower() for indicator in ['inc', 'corp', 'ltd', 'llc', 'company', 'technologies', 'solutions']):
                        if current_experience and 'company' in current_experience:
                            experiences.append(current_experience)
                        current_experience = {
                            'company': line,
                            'position': '',
                            'duration': '',
                            'description': ''
                        }
                    elif current_experience and 'company' in current_experience:
                        # Check if it's a position or duration
                        if any(role in line.lower() for role in ['developer', 'engineer', 'analyst', 'intern', 'assistant', 'manager', 'lead']):
                            current_experience['position'] = line
                        elif any(month in line.lower() for month in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']):
                            current_experience['duration'] = line
                        else:
                            current_experience['description'] += ' ' + line
                
                # Add last experience
                if current_experience and 'company' in current_experience:
                    experiences.append(current_experience)
        
        return experiences[:3]  # Limit to 3 experiences

    def _format_cv_projects_for_prompt(self, projects: List[Dict[str, str]]) -> str:
        """Format CV projects for use in prompts."""
        if not projects:
            return "No specific projects mentioned in CV"
        
        formatted_projects = []
        for i, project in enumerate(projects, 1):
            project_str = f"{i}. {project['name']}"
            if project.get('description'):
                project_str += f" - {project['description'][:100]}..."
            if project.get('technologies'):
                techs = ', '.join(project['technologies'][:3])
                project_str += f" (Technologies: {techs})"
            formatted_projects.append(project_str)
        
        return '\n'.join(formatted_projects)

    def _format_cv_experiences_for_prompt(self, experiences: List[Dict[str, str]]) -> str:
        """Format CV experiences for use in prompts."""
        if not experiences:
            return "No work experience mentioned in CV"
        
        formatted_experiences = []
        for i, exp in enumerate(experiences, 1):
            exp_str = f"{i}. {exp.get('company', 'Unknown Company')}"
            if exp.get('position'):
                exp_str += f" - {exp['position']}"
            if exp.get('duration'):
                exp_str += f" ({exp['duration']})"
            if exp.get('description'):
                exp_str += f" - {exp['description'][:100]}..."
            formatted_experiences.append(exp_str)
        
        return '\n'.join(formatted_experiences)

    def _extract_projects_from_answer(self, answer: str) -> List[str]:
        """Extract project names mentioned in candidate's answer."""
        if not answer:
            return []
        
        # Look for project indicators
        project_indicators = [
            'project', 'application', 'system', 'platform', 'website', 'app',
            'tool', 'software', 'program', 'solution', 'product'
        ]
        
        mentioned_projects = []
        answer_lower = answer.lower()
        
        # Simple extraction - look for phrases that might be project names
        words = answer.split()
        for i, word in enumerate(words):
            if any(indicator in word.lower() for indicator in project_indicators):
                # Try to get the full project name (2-3 words around the indicator)
                start = max(0, i-1)
                end = min(len(words), i+3)
                project_name = ' '.join(words[start:end])
                mentioned_projects.append(project_name)
        
        return mentioned_projects[:3]  # Return top 3

    def _extract_technologies_from_answer(self, answer: str) -> List[str]:
        """Extract technologies mentioned in candidate's answer."""
        if not answer:
            return []
        
        # Common technology terms
        tech_terms = [
            'python', 'javascript', 'java', 'react', 'node', 'django', 'flask',
            'sql', 'mongodb', 'postgresql', 'aws', 'docker', 'kubernetes',
            'git', 'linux', 'api', 'rest', 'graphql', 'html', 'css'
        ]
        
        mentioned_techs = []
        answer_lower = answer.lower()
        
        for term in tech_terms:
            if term in answer_lower:
                mentioned_techs.append(term)
        
        return mentioned_techs[:5]  # Return top 5

    def _should_switch_project(self, context: ConversationContext, answer_evaluation: Optional[Dict]) -> bool:
        """Determine if we should switch to a new project."""
        # Don't switch too early
        if context.question_count < 3:
            return False
        
        # Switch every 2-3 questions in experiential phase
        base_switch_interval = 2
        
        if answer_evaluation:
            score = answer_evaluation.get("overall_score", 0.5)
            
            # If they're struggling, switch sooner
            if score < 0.4 and context.question_count % 2 == 0:
                return True
        
        # Check if it's time to switch based on interval
        questions_on_current_project = context.question_count % base_switch_interval
        return questions_on_current_project == 0 and len(context.cv_projects) > len(context.projects_covered)

    def _get_next_project(self, context: ConversationContext) -> Optional[str]:
        """Get the next project to discuss."""
        uncovered_projects = [
            project['name']
            for project in context.cv_projects
            if project['name'] not in context.projects_covered
        ]
        
        if uncovered_projects:
            return uncovered_projects[0]
        
        # If all projects covered, cycle back
        if context.projects_covered:
            return context.projects_covered[
                context.question_count % len(context.projects_covered)
            ]
        
        return None

    def _fallback_extract_projects(self, resume_sections: Dict[str, str]) -> List[Dict[str, str]]:
        """Fallback method to extract projects when specific sections not found."""
        projects = []
        
        # Look for any content that might be projects
        for section_name, content in resume_sections.items():
            if 'project' in section_name.lower() or 'work' in section_name.lower():
                lines = content.split('\n')
                for line in lines:
                    line = line.strip()
                    if len(line) > 10 and any(tech in line.lower() for tech in ['python', 'javascript', 'react', 'node', 'java']):
                        projects.append({
                            'name': line[:50] + '...' if len(line) > 50 else line,
                            'description': line,
                            'technologies': []
                        })
        
        return projects[:3]

    def _fallback_experiential_question_with_context(
        self, context: ConversationContext, last_answer: str = "", score: float = 0.5
    ) -> str:
        """Fallback method for experiential questions with contextual acknowledgment."""
        base_question = f"Can you tell me about your {context.current_project_focus} project and what you learned from it?"
        
        if last_answer:
            if score < 0.4:
                acknowledgment = "I appreciate you sharing that. Let me ask about something else - "
            elif score < 0.7:
                acknowledgment = "That's helpful context. Now, "
            else:
                acknowledgment = "Great insights! Building on that, "
            
            return f"{acknowledgment}{base_question.lower()}"
        
        return base_question
