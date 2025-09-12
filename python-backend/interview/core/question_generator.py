"""
Advanced question generation system for natural interview conversations.
"""

import re
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from ..llm.base import BaseLLM
from ..config.settings import QuestionType


class ConversationDepth(Enum):
    """Levels of conversation depth."""

    SURFACE = "surface"  # Initial topic introduction
    MODERATE = "moderate"  # Basic understanding exploration
    DEEP = "deep"  # Advanced concepts and edge cases
    EXPERT = "expert"  # Industry expertise and experience


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
    candidate_skill_level: str  # beginner, intermediate, advanced, expert
    answer_quality_trend: List[float]  # Last few answer scores
    follow_up_count: int
    needs_topic_change: bool
    conversation_energy: str  # engaging, declining, neutral


@dataclass
class QuestionMetadata:
    """Metadata for generated questions."""

    question_type: QuestionType
    intent: QuestionIntent
    difficulty_level: str
    expected_depth: ConversationDepth
    topic_area: str
    prerequisites: List[str]


class QuestionGenerator:
    """Advanced question generator for natural interview conversations."""

    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self.conversation_context = None
        self.available_topics = []  # Dynamic topics from CV/JD

    def initialize_conversation(
        self, resume_sections: Dict[str, str], job_description: str = ""
    ) -> ConversationContext:
        """Initialize conversation context based on resume and job description."""
        # Extract dynamic topics from CV and JD
        cv_content = " ".join(resume_sections.values())
        self.available_topics = self._extract_dynamic_topics(
            cv_content, job_description
        )

        # Assess initial skill level from resume
        skill_level = self._assess_initial_skill_level(resume_sections)

        # Select starting topic from extracted topics
        starting_topic = (
            self.available_topics[0]
            if self.available_topics
            else "technical background"
        )

        return ConversationContext(
            current_topic=starting_topic,
            depth_level=ConversationDepth.SURFACE,
            topics_covered=[],
            candidate_skill_level=skill_level,
            answer_quality_trend=[],
            follow_up_count=0,
            needs_topic_change=False,
            conversation_energy="neutral",
        )

    def get_next_question(
        self,
        context: ConversationContext,
        last_answer: Optional[str] = None,
        answer_evaluation: Optional[Dict] = None,
    ) -> Tuple[str, QuestionMetadata]:
        """
        Generate the next question based on conversation flow and context.
        This is the main method that decides question strategy.
        """
        # Update context based on last answer
        if last_answer and answer_evaluation:
            context = self._update_conversation_context(
                context, last_answer, answer_evaluation
            )

        # Decide on question strategy
        intent = self._determine_question_intent(context)

        # Generate question based on intent
        if intent == QuestionIntent.EXPLORE_NEW_TOPIC:
            return self._generate_new_topic_question(context)
        elif intent == QuestionIntent.PROBE_DEEPER:
            return self._generate_follow_up_question(context, last_answer)
        elif intent == QuestionIntent.CLARIFY_UNDERSTANDING:
            return self._generate_clarification_question(context, last_answer)
        elif intent == QuestionIntent.ASSESS_EXPERIENCE:
            return self._generate_experience_question(context)
        elif intent == QuestionIntent.TRANSITION_TOPIC:
            return self._generate_transition_question(context)
        else:
            return self._generate_verification_question(context, last_answer)

    def _determine_question_intent(
        self, context: ConversationContext
    ) -> QuestionIntent:
        """Determine what kind of question to ask next based on conversation state."""

        # If just started, explore new topic
        if not context.topics_covered:
            return QuestionIntent.EXPLORE_NEW_TOPIC

        # If we've been on same topic too long, transition
        if context.follow_up_count >= 3:
            return QuestionIntent.TRANSITION_TOPIC

        # If answer quality is declining, clarify or transition
        if len(context.answer_quality_trend) >= 2:
            recent_avg = sum(context.answer_quality_trend[-2:]) / 2
            if recent_avg < 0.6:
                return (
                    QuestionIntent.CLARIFY_UNDERSTANDING
                    if context.follow_up_count < 2
                    else QuestionIntent.TRANSITION_TOPIC
                )

        # If answer quality is high and we're not too deep, probe deeper
        if len(context.answer_quality_trend) >= 1:
            last_score = context.answer_quality_trend[-1]
            if last_score > 0.7 and context.depth_level != ConversationDepth.EXPERT:
                return QuestionIntent.PROBE_DEEPER

        # If we need topic change flag is set
        if context.needs_topic_change:
            return QuestionIntent.TRANSITION_TOPIC

        # If candidate shows expertise, assess experience
        if context.candidate_skill_level in ["advanced", "expert"]:
            return QuestionIntent.ASSESS_EXPERIENCE

        # Default to exploring deeper
        return QuestionIntent.PROBE_DEEPER

    def _generate_new_topic_question(
        self, context: ConversationContext
    ) -> Tuple[str, QuestionMetadata]:
        """Generate a question to explore a new technical topic."""

        # Get unexplored topics
        unexplored_topics = [
            topic
            for topic in self._get_available_topics()
            if topic not in context.topics_covered
        ]

        if not unexplored_topics:
            unexplored_topics = [
                "software architecture",
                "system design",
                "problem solving",
            ]

        topic = unexplored_topics[0]

        # Adjust question based on skill level
        if context.candidate_skill_level in ["beginner", "intermediate"]:
            prompt = f"""
            Generate an opening question about {topic} that is appropriate for someone with 
            {context.candidate_skill_level} level experience. The question should:
            - Be welcoming and not intimidating
            - Test fundamental understanding
            - Allow for different levels of depth in answers
            - Be conversational and natural
            
            Generate ONE clear, engaging question about {topic}:
            """
        else:
            prompt = f"""
            Generate an opening question about {topic} for an experienced professional.
            The question should:
            - Test deeper understanding and practical application
            - Be challenging but fair
            - Allow demonstration of real-world experience
            - Be conversational and professional
            
            Generate ONE thoughtful question about {topic}:
            """

        question = self._generate_question_from_prompt(prompt)

        metadata = QuestionMetadata(
            question_type=QuestionType.TECHNICAL,
            intent=QuestionIntent.EXPLORE_NEW_TOPIC,
            difficulty_level=context.candidate_skill_level,
            expected_depth=ConversationDepth.SURFACE,
            topic_area=topic,
            prerequisites=[],
        )

        # Update context
        context.current_topic = topic
        context.topics_covered.append(topic)
        context.depth_level = ConversationDepth.SURFACE
        context.follow_up_count = 0

        return question, metadata

    def _generate_follow_up_question(
        self, context: ConversationContext, last_answer: str
    ) -> Tuple[str, QuestionMetadata]:
        """Generate a follow-up question that goes deeper into the current topic."""

        # Determine next depth level
        next_depth = self._get_next_depth_level(context.depth_level)

        prompt = f"""
        Based on this answer about {context.current_topic}, generate a follow-up question 
        that digs deeper into the concept. Current depth level: {context.depth_level.value}.
        Target depth: {next_depth.value}.
        
        Previous Answer: {last_answer}
        
        The follow-up should:
        - Build naturally on what they just said
        - Go deeper into technical details or practical applications
        - Test {next_depth.value} level understanding
        - Feel like a natural conversation progression
        - Not repeat what was already covered
        
        Generate ONE insightful follow-up question:
        """

        question = self._generate_question_from_prompt(prompt)

        metadata = QuestionMetadata(
            question_type=QuestionType.TECHNICAL,
            intent=QuestionIntent.PROBE_DEEPER,
            difficulty_level=self._depth_to_difficulty(next_depth),
            expected_depth=next_depth,
            topic_area=context.current_topic,
            prerequisites=[context.current_topic],
        )

        # Update context
        context.depth_level = next_depth
        context.follow_up_count += 1

        return question, metadata

    def _generate_clarification_question(
        self, context: ConversationContext, last_answer: str
    ) -> Tuple[str, QuestionMetadata]:
        """Generate a question to clarify understanding when the previous answer was unclear."""

        prompt = f"""
        The candidate's previous answer about {context.current_topic} was unclear or incomplete.
        Generate a clarifying question that:
        - Helps them elaborate on unclear points
        - Is supportive and encouraging, not confrontational
        - Guides them toward a better explanation
        - Feels natural and helpful
        
        Previous Answer: {last_answer}
        
        Generate ONE supportive clarification question:
        """

        question = self._generate_question_from_prompt(prompt)

        metadata = QuestionMetadata(
            question_type=QuestionType.TECHNICAL,
            intent=QuestionIntent.CLARIFY_UNDERSTANDING,
            difficulty_level="intermediate",
            expected_depth=context.depth_level,
            topic_area=context.current_topic,
            prerequisites=[],
        )

        return question, metadata

    def _generate_experience_question(
        self, context: ConversationContext
    ) -> Tuple[str, QuestionMetadata]:
        """Generate a question to assess real-world experience."""

        prompt = f"""
        Generate a question that assesses practical experience with {context.current_topic}.
        The question should:
        - Ask about real-world scenarios and challenges
        - Test practical application of knowledge
        - Allow discussion of specific experiences
        - Be conversational and engaging
        
        Generate ONE experience-focused question about {context.current_topic}:
        """

        question = self._generate_question_from_prompt(prompt)

        metadata = QuestionMetadata(
            question_type=QuestionType.EXPERIENCE,
            intent=QuestionIntent.ASSESS_EXPERIENCE,
            difficulty_level="advanced",
            expected_depth=ConversationDepth.MODERATE,
            topic_area=context.current_topic,
            prerequisites=[context.current_topic],
        )

        return question, metadata

    def _generate_transition_question(
        self, context: ConversationContext
    ) -> Tuple[str, QuestionMetadata]:
        """Generate a question that smoothly transitions to a new topic."""

        # Get next topic
        unexplored_topics = [
            topic
            for topic in self._get_available_topics()
            if topic not in context.topics_covered
        ]

        if not unexplored_topics:
            # If all topics covered, go to behavioral/situational
            return self._generate_behavioral_question(context)

        next_topic = unexplored_topics[0]

        prompt = f"""
        Create a smooth transition from discussing {context.current_topic} to {next_topic}.
        The question should:
        - Acknowledge what we've discussed about {context.current_topic}
        - Naturally bridge to {next_topic}
        - Feel conversational and professional
        - Not be abrupt or jarring
        
        Generate ONE smooth transition question to {next_topic}:
        """

        question = self._generate_question_from_prompt(prompt)

        metadata = QuestionMetadata(
            question_type=QuestionType.TECHNICAL,
            intent=QuestionIntent.TRANSITION_TOPIC,
            difficulty_level=context.candidate_skill_level,
            expected_depth=ConversationDepth.SURFACE,
            topic_area=next_topic,
            prerequisites=[],
        )

        # Update context for new topic
        context.current_topic = next_topic
        context.topics_covered.append(next_topic)
        context.depth_level = ConversationDepth.SURFACE
        context.follow_up_count = 0
        context.needs_topic_change = False

        return question, metadata

    def _generate_verification_question(
        self, context: ConversationContext, last_answer: str
    ) -> Tuple[str, QuestionMetadata]:
        """Generate a question to verify understanding of a concept."""

        prompt = f"""
        Based on their answer about {context.current_topic}, generate a verification question 
        that tests if they truly understand the concept or just memorized it.
        
        Previous Answer: {last_answer}
        
        The verification question should:
        - Test deeper understanding, not just recall
        - Ask for examples or applications
        - Be respectful and professional
        - Probe for genuine comprehension
        
        Generate ONE verification question:
        """

        question = self._generate_question_from_prompt(prompt)

        metadata = QuestionMetadata(
            question_type=QuestionType.TECHNICAL,
            intent=QuestionIntent.VERIFY_KNOWLEDGE,
            difficulty_level="intermediate",
            expected_depth=context.depth_level,
            topic_area=context.current_topic,
            prerequisites=[context.current_topic],
        )

        return question, metadata

    def _generate_behavioral_question(
        self, context: ConversationContext
    ) -> Tuple[str, QuestionMetadata]:
        """Generate a behavioral question when technical topics are exhausted."""

        behavioral_areas = [
            "problem-solving approach",
            "team collaboration",
            "handling pressure",
            "learning new technologies",
            "dealing with difficult technical challenges",
        ]

        area = behavioral_areas[len(context.topics_covered) % len(behavioral_areas)]

        prompt = f"""
        Generate a behavioral interview question about {area}.
        The question should:
        - Start with "Tell me about a time when..." or "How do you handle..."
        - Be relevant to a technical role
        - Allow for storytelling and specific examples
        - Be professional and engaging
        
        Generate ONE behavioral question about {area}:
        """

        question = self._generate_question_from_prompt(prompt)

        metadata = QuestionMetadata(
            question_type=QuestionType.BEHAVIORAL,
            intent=QuestionIntent.ASSESS_EXPERIENCE,
            difficulty_level="intermediate",
            expected_depth=ConversationDepth.MODERATE,
            topic_area=area,
            prerequisites=[],
        )

        return question, metadata

    def _update_conversation_context(
        self, context: ConversationContext, last_answer: str, evaluation: Dict
    ) -> ConversationContext:
        """Update conversation context based on the last interaction."""

        # Update answer quality trend
        overall_score = evaluation.get("overall_score", 0.5)
        context.answer_quality_trend.append(overall_score)

        # Keep only last 5 scores
        if len(context.answer_quality_trend) > 5:
            context.answer_quality_trend = context.answer_quality_trend[-5:]

        # Update skill level assessment based on performance
        if len(context.answer_quality_trend) >= 3:
            recent_avg = sum(context.answer_quality_trend[-3:]) / 3
            if recent_avg > 0.8 and context.candidate_skill_level in [
                "beginner",
                "intermediate",
            ]:
                context.candidate_skill_level = "advanced"
            elif recent_avg < 0.4 and context.candidate_skill_level in [
                "advanced",
                "expert",
            ]:
                context.candidate_skill_level = "intermediate"

        # Assess conversation energy
        if overall_score > 0.7:
            context.conversation_energy = "engaging"
        elif overall_score < 0.4:
            context.conversation_energy = "declining"
        else:
            context.conversation_energy = "neutral"

        # Determine if topic change is needed
        if context.follow_up_count >= 2 and context.conversation_energy == "declining":
            context.needs_topic_change = True

        return context

    def _assess_initial_skill_level(self, resume_sections: Dict[str, str]) -> str:
        """Assess initial skill level from resume."""

        experience_text = resume_sections.get("experience", "")
        skills_text = resume_sections.get("skills", "")
        education_text = resume_sections.get("education", "")

        combined_text = f"{experience_text} {skills_text} {education_text}"

        # Simple heuristic-based assessment
        years_indicators = re.findall(r"(\d+)\s*(?:years?|yrs?)", combined_text.lower())
        senior_indicators = ["senior", "lead", "principal", "architect", "manager"]
        advanced_skills = [
            "system design",
            "architecture",
            "scalability",
            "performance",
        ]

        max_years = max([int(y) for y in years_indicators], default=0)
        has_senior_role = any(
            indicator in combined_text.lower() for indicator in senior_indicators
        )
        has_advanced_skills = any(
            skill in combined_text.lower() for skill in advanced_skills
        )

        if max_years >= 7 or has_senior_role:
            return "expert"
        elif max_years >= 4 or has_advanced_skills:
            return "advanced"
        elif max_years >= 1:
            return "intermediate"
        else:
            return "beginner"

    def _extract_dynamic_topics(
        self, cv_content: str, job_description: str
    ) -> List[str]:
        """
        Extract relevant interview topics from CV and Job Description.

        Args:
            cv_content: Candidate's CV content
            job_description: Job posting content

        Returns:
            List of relevant topics for the interview
        """
        try:
            extraction_prompt = f"""
Analyze the following CV and Job Description to extract relevant technical topics and skills for an interview.

=== JOB DESCRIPTION ===
{job_description}

=== CANDIDATE CV ===
{cv_content}

Extract a focused list of 8-12 interview topics that are:
1. Mentioned in the job description (required/preferred skills)
2. Present in the candidate's CV (their experience areas)
3. Relevant for technical assessment
4. Suitable for interview questions

Focus on:
- Programming languages and frameworks
- Technical skills and tools
- Domain expertise areas
- Project experience areas
- System design concepts
- Problem-solving areas

Return ONLY a simple list of topics, one per line, no numbering or formatting.
Example format:
Python Programming
REST API Development
Database Design
Machine Learning
System Architecture
"""

            # Get LLM response for topic extraction
            response = self.llm.complete(extraction_prompt)

            # Parse the response to extract topics
            topics = []
            if response and hasattr(response, "text"):
                content = response.text.strip()
                # Split by lines and clean up
                raw_topics = [
                    line.strip() for line in content.split("\n") if line.strip()
                ]

                # Filter and validate topics
                for topic in raw_topics:
                    # Remove numbering, bullets, or extra formatting
                    cleaned_topic = topic.strip("- •*123456789. ")
                    if cleaned_topic and len(cleaned_topic) > 3:
                        topics.append(cleaned_topic.lower())

            # Fallback topics if extraction fails
            if not topics:
                topics = [
                    "technical problem solving",
                    "programming fundamentals",
                    "system design",
                    "project experience",
                    "technical communication",
                ]

            # Limit to reasonable number of topics
            return topics[:12]

        except Exception as e:
            print(f"Error extracting topics: {e}")
            # Return default fallback topics
            return [
                "technical problem solving",
                "programming experience",
                "system design basics",
                "project management",
                "technical communication",
                "learning approach",
            ]

    def _get_available_topics(self) -> List[str]:
        """Get list of available technical topics to explore."""
        # Return the dynamically extracted topics if available, otherwise fallback
        if self.available_topics:
            return self.available_topics

        # Fallback topics if dynamic extraction hasn't been done
        return [
            "data structures and algorithms",
            "system design",
            "database design",
            "software architecture",
            "performance optimization",
            "security principles",
            "testing strategies",
            "version control",
            "deployment and DevOps",
            "code quality and best practices",
        ]

    def _get_next_depth_level(
        self, current_depth: ConversationDepth
    ) -> ConversationDepth:
        """Get the next depth level for follow-up questions."""
        depth_progression = {
            ConversationDepth.SURFACE: ConversationDepth.MODERATE,
            ConversationDepth.MODERATE: ConversationDepth.DEEP,
            ConversationDepth.DEEP: ConversationDepth.EXPERT,
            ConversationDepth.EXPERT: ConversationDepth.EXPERT,  # Stay at expert level
        }
        return depth_progression.get(current_depth, ConversationDepth.MODERATE)

    def _depth_to_difficulty(self, depth: ConversationDepth) -> str:
        """Convert depth level to difficulty string."""
        mapping = {
            ConversationDepth.SURFACE: "beginner",
            ConversationDepth.MODERATE: "intermediate",
            ConversationDepth.DEEP: "advanced",
            ConversationDepth.EXPERT: "expert",
        }
        return mapping.get(depth, "intermediate")

    def _generate_question_from_prompt(self, prompt: str) -> str:
        """Generate a question using the LLM from a given prompt."""
        try:
            response = self.llm.complete(prompt)
            question = response.text.strip()

            # Clean up the question
            question = re.sub(r"^\d+[\.\)]\s*", "", question)
            question = question.strip("\"'")

            # Ensure it's a proper question
            if not question.endswith("?") and not question.endswith("."):
                question += "?"

            return (
                question if question else "Can you tell me more about your experience?"
            )

        except Exception as e:
            print(f"Error generating question: {e}")
            return "Can you tell me more about your experience?"