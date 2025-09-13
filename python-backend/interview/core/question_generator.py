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
    has_been_greeted: bool = False  # Track if initial greeting was given
    previous_answers: List[str] = None  # Store previous answers for context
    question_count: int = 0  # Track total questions asked

    def __post_init__(self):
        if self.previous_answers is None:
            self.previous_answers = []


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
    """
    Advanced question generator for natural interview conversations with academic focus.

    This class generates fundamental, technical questions that test theoretical knowledge
    and academic understanding rather than situational scenarios. It provides:

    - Warm interview greetings and initialization
    - Interactive responses to candidate answers
    - Academic-focused question generation
    - Natural conversation flow management
    - Progressive difficulty based on performance
    """

    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self.conversation_context = None
        self.available_topics = []  # Dynamic topics from CV/JD
        self.cv_content = ""  # Store CV content for reference
        self.resume_sections = {}  # Store resume sections

    def initialize_conversation(
        self, resume_sections: Dict[str, str], job_description: str = ""
    ) -> ConversationContext:
        """Initialize conversation context based on resume and job description."""
        # Store CV content for reference in questions
        self.resume_sections = resume_sections
        self.cv_content = " ".join(resume_sections.values())

        # Extract dynamic topics from CV and JD
        self.available_topics = self._extract_dynamic_topics(
            self.cv_content, job_description
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
            has_been_greeted=False,
            question_count=0,
        )

    def generate_interview_greeting(
        self,
        candidate_name: Optional[str] = None,
        context: Optional[ConversationContext] = None,
    ) -> str:
        """Generate a warm, professional greeting to start the interview."""

        # Get some CV context for the greeting
        cv_reference = ""
        if context and self.cv_content:
            cv_reference = f"I've had a chance to review your resume and I can see you have experience with {context.current_topic}."

        greeting_prompts = [
            f"Generate a warm, natural greeting to start a technical interview conversation. Make it sound like a real human interviewer speaking:",
            f"",
            f"The candidate's name is: {candidate_name or 'the candidate'}",
            f"CV context: {cv_reference}",
            f"First topic area from their CV: {context.current_topic if context else 'technical background'}",
            f"",
            f"The greeting should:",
            f"- Sound completely natural and conversational (like a real person speaking)",
            f"- Welcome them warmly and make them feel comfortable",
            f"- Mention that you've reviewed their resume",
            f"- Set a collaborative, discussion-like tone",
            f"- Let them know the questions will be based on their CV/experience",
            f"- End naturally by transitioning to the first topic from their background",
            f"",
            f"Make it sound like a real interviewer having a natural conversation, not robotic or scripted:",
        ]

        prompt = "\n".join(greeting_prompts)

        try:
            response = self.llm.complete(prompt)
            greeting = (
                response.text.strip() if response and hasattr(response, "text") else ""
            )

            if not greeting:
                # Fallback greeting
                name_part = f"Hi {candidate_name}! " if candidate_name else "Hello! "
                cv_part = "I've had a chance to review your resume and "
                topic_part = (
                    f"I'd like to start by discussing your experience with {context.current_topic}"
                    if context
                    else "I'd like to discuss your technical background"
                )
                greeting = f"{name_part}{cv_part}{topic_part}. The questions will be based on what you've mentioned in your CV, so feel free to draw from your actual experience. Ready to begin?"

            return greeting

        except Exception as e:
            print(f"Error generating greeting: {e}")
            # Fallback greeting
            name_part = f"Hi {candidate_name}! " if candidate_name else "Hello! "
            return f"{name_part}Welcome to the technical interview. I've reviewed your resume and I'll be asking questions based on your experience and background. Feel free to ask for clarification if needed. Let's get started!"

    def generate_answer_response(
        self,
        candidate_answer: str,
        context: ConversationContext,
        evaluation: Optional[Dict] = None,
    ) -> str:
        """Generate an interactive response to the candidate's answer before asking the next question."""

        try:
            # Determine the type of response based on answer quality
            if evaluation:
                overall_score = evaluation.get("overall_score", 0.5)
                accuracy = evaluation.get("technical_accuracy", 0.5)
                completeness = evaluation.get("completeness", 0.5)
            else:
                overall_score = 0.5
                accuracy = 0.5
                completeness = 0.5

            # Create response based on performance
            if overall_score >= 0.8:
                response_type = "excellent"
            elif overall_score >= 0.6:
                response_type = "good"
            elif overall_score >= 0.4:
                response_type = "partial"
            else:
                response_type = "needs_improvement"

            prompt = f"""
You are a professional interviewer having a natural conversation with a candidate about {context.current_topic}.

The candidate just answered your question. Generate a natural, human-like response that an experienced interviewer would give.

Candidate's Answer: {candidate_answer}

Answer Quality: {response_type} (score: {overall_score:.2f})

Your response should:
- Sound completely natural and conversational
- Acknowledge what they said in a human way
- Show you were listening and engaged
- Be encouraging and professional
- Set up naturally for the next question
- Sound like a real person having a conversation

{self._get_response_guidelines(response_type)}

Generate a natural interviewer response (like a real person would say):
"""

            response = self.llm.complete(prompt)
            interviewer_response = (
                response.text.strip() if response and hasattr(response, "text") else ""
            )

            if not interviewer_response:
                # Fallback responses based on performance
                fallback_responses = {
                    "excellent": "That's a really solid explanation! I can see you have good understanding of this area.",
                    "good": "Good, you've covered the key points well. That makes sense.",
                    "partial": "I see what you're getting at. That's a good starting point.",
                    "needs_improvement": "Okay, I understand your perspective. Let me ask you about this in a different way.",
                }
                interviewer_response = fallback_responses.get(
                    response_type, "I see, thank you for explaining that."
                )

            return interviewer_response

        except Exception as e:
            print(f"Error generating answer response: {e}")
            return "I see, thank you for that explanation."

    def _get_response_guidelines(self, response_type: str) -> str:
        """Get guidelines for different types of responses."""
        guidelines = {
            "excellent": """
- Sound genuinely impressed and encouraging
- Use natural phrases like "That's really good", "I can see you know this well"
- Be specific about what they did well
- Show genuine interest in their answer
""",
            "good": """
- Acknowledge their solid understanding
- Use affirming language like "That's right", "Good point", "Exactly"
- Sound satisfied with their response
- Be naturally encouraging
""",
            "partial": """
- Acknowledge what they got right positively
- Sound understanding and supportive
- Use phrases like "I see what you mean", "That's a good start"
- Avoid any negative language
""",
            "needs_improvement": """
- Stay completely supportive and encouraging
- Never sound disappointed or critical
- Use phrases like "Let me try asking this differently", "How about we approach it this way"
- Make it sound like you're helping them succeed
""",
        }
        return guidelines.get(response_type, "Be professional, natural and supportive.")

    def get_next_question_with_response(
        self,
        context: ConversationContext,
        last_answer: Optional[str] = None,
        answer_evaluation: Optional[Dict] = None,
    ) -> Tuple[str, str, QuestionMetadata]:
        """
        Generate both an interactive response to the previous answer and the next question.
        Returns: (interviewer_response, next_question, metadata)
        """

        interviewer_response = ""

        # Generate response to previous answer if provided
        if last_answer:
            interviewer_response = self.generate_answer_response(
                last_answer, context, answer_evaluation
            )

        # Get the next question
        next_question, metadata = self.get_next_question(
            context, last_answer, answer_evaluation
        )

        return interviewer_response, next_question, metadata

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
        # Store previous answer for conversation memory
        if last_answer:
            context.previous_answers.append(last_answer)
            # Keep only last 3 answers for context
            if len(context.previous_answers) > 3:
                context.previous_answers = context.previous_answers[-3:]

        # Increment question count
        context.question_count += 1

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
        """
        Determine what kind of question to ask next based on conversation state.
        Handles multiple simultaneous intents with proper prioritization.
        """

        # Collect all applicable intents with their priority scores
        intent_scores = {}

        # PRIORITY 1: Critical conversation flow issues (highest priority)
        # Only explore new topic if we haven't covered any OR current topic is truly exhausted
        if not context.topics_covered and context.question_count == 1:
            intent_scores[QuestionIntent.EXPLORE_NEW_TOPIC] = (
                100  # Must start somewhere (first question only)
            )

        if context.follow_up_count >= 4:  # Stuck too long on one topic
            intent_scores[QuestionIntent.TRANSITION_TOPIC] = 95

        # PRIORITY 2: Poor answer quality - needs immediate attention
        if len(context.answer_quality_trend) >= 2:
            recent_avg = sum(context.answer_quality_trend[-2:]) / 2
            if recent_avg < 0.4:  # Very poor performance
                if context.follow_up_count < 2:
                    intent_scores[QuestionIntent.CLARIFY_UNDERSTANDING] = 90
                else:
                    intent_scores[QuestionIntent.TRANSITION_TOPIC] = 85

        # PRIORITY 3: Explicit topic change flag
        if context.needs_topic_change:
            intent_scores[QuestionIntent.TRANSITION_TOPIC] = 80

        # PRIORITY 4: Quality-based decisions (good performance)
        if len(context.answer_quality_trend) >= 1:
            last_score = context.answer_quality_trend[-1]

            # High quality answers - probe deeper (but respect other priorities)
            if last_score > 0.7 and context.depth_level != ConversationDepth.EXPERT:
                intent_scores[QuestionIntent.PROBE_DEEPER] = 70

            # Moderate quality - might need clarification
            elif 0.5 <= last_score <= 0.7 and context.follow_up_count < 3:
                intent_scores[QuestionIntent.CLARIFY_UNDERSTANDING] = 60

        # PRIORITY 5: Skill-level based decisions
        if context.candidate_skill_level in ["advanced", "expert"]:
            # Expert candidates should get experience questions, but not if we need to change topics
            if QuestionIntent.TRANSITION_TOPIC not in intent_scores:
                intent_scores[QuestionIntent.ASSESS_EXPERIENCE] = 65

        # PRIORITY 6: Moderate follow-up scenarios
        if 2 <= context.follow_up_count <= 3:
            intent_scores[QuestionIntent.TRANSITION_TOPIC] = 50

        # PRIORITY 7: Default probing (lowest priority)
        if not intent_scores:  # No other intent determined
            intent_scores[QuestionIntent.PROBE_DEEPER] = 30

        # CONFLICT RESOLUTION: Handle specific combinations
        selected_intent = self._resolve_intent_conflicts(intent_scores, context)

        return selected_intent

    def _resolve_intent_conflicts(
        self, intent_scores: Dict[QuestionIntent, int], context: ConversationContext
    ) -> QuestionIntent:
        """
        Resolve conflicts when multiple intents have similar priorities.
        Apply business logic for specific combinations.
        """

        # If no intents, default to exploring
        if not intent_scores:
            return QuestionIntent.PROBE_DEEPER

        # Special case: Expert + Topic Change
        if (
            QuestionIntent.TRANSITION_TOPIC in intent_scores
            and context.candidate_skill_level == "expert"
            and intent_scores.get(QuestionIntent.ASSESS_EXPERIENCE, 0) > 0
        ):

            # If we've been on topic for a while, prioritize transition
            if context.follow_up_count >= 3:
                return QuestionIntent.TRANSITION_TOPIC
            # Otherwise, get one experience question before transitioning
            else:
                return QuestionIntent.ASSESS_EXPERIENCE

        # Special case: Clarification vs Transition (poor performance)
        if (
            QuestionIntent.CLARIFY_UNDERSTANDING in intent_scores
            and QuestionIntent.TRANSITION_TOPIC in intent_scores
        ):

            # If we've tried clarification before, transition
            if context.follow_up_count >= 2:
                return QuestionIntent.TRANSITION_TOPIC
            # Otherwise, give one more chance to clarify
            else:
                return QuestionIntent.CLARIFY_UNDERSTANDING

        # Special case: Probe Deeper vs Assess Experience (high performers)
        if (
            QuestionIntent.PROBE_DEEPER in intent_scores
            and QuestionIntent.ASSESS_EXPERIENCE in intent_scores
            and context.candidate_skill_level in ["advanced", "expert"]
        ):

            # Alternate between probing and experience based on depth
            if context.depth_level in [
                ConversationDepth.SURFACE,
                ConversationDepth.MODERATE,
            ]:
                return QuestionIntent.PROBE_DEEPER
            else:
                return QuestionIntent.ASSESS_EXPERIENCE

        # Default: Return highest scoring intent
        return max(intent_scores.items(), key=lambda x: x[1])[0]

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

        # Adjust question based on conversation stage and context
        cv_reference = self._get_cv_context_for_topic(topic)

        # Check if this is first question or continuation of conversation
        is_first_question = context.question_count <= 1 and not context.has_been_greeted

        if is_first_question:
            # This is the very first question - include greeting
            context.has_been_greeted = True

            if context.candidate_skill_level in ["beginner", "intermediate"]:
                prompt = f"""
                You are starting an interview conversation. Generate a warm greeting followed by a natural first question about {topic}.
                
                CV Context: {cv_reference}
                
                Create a natural response that:
                - Starts with a warm, professional greeting
                - References their CV/resume experience with {topic}
                - Makes them feel comfortable by showing it's based on their background
                - Asks about basic concepts they should know from their experience
                - Flows naturally as the opening of an interview
                
                Example approach:
                "Hi! Thanks for coming in today. I've had a chance to review your resume and I can see you have experience with {topic}. Since you've worked with this, could you tell me..."
                
                Generate a natural greeting and opening question:
                """
            else:
                prompt = f"""
                You are starting an interview conversation. Generate a warm greeting followed by a natural first question about {topic}.
                
                CV Context: {cv_reference}
                
                Create a natural response that:
                - Starts with a warm, professional greeting
                - References their CV/resume experience with {topic}
                - Makes them comfortable by showing it's based on their background
                - Asks about concepts they claim to know from their CV
                - Flows naturally as the opening of an interview
                
                Example approach:
                "Hello! Welcome, and thank you for taking the time to meet with me today. Looking at your background, I can see you have {topic} experience. Given your work in this area, I'd like to understand..."
                
                Generate a natural greeting and opening question:
                """
        else:
            # This is a continuation - transition to new topic naturally
            previous_topic = (
                context.current_topic
                if context.topics_covered
                else "your previous answer"
            )

            if context.candidate_skill_level in ["beginner", "intermediate"]:
                prompt = f"""
                You are continuing an interview conversation. The candidate has been discussing {previous_topic}. 
                Now transition naturally to {topic} based on their CV.
                
                CV Context: {cv_reference}
                Previous conversation context: They just finished discussing {previous_topic}
                
                Create a natural transition that:
                - Acknowledges the previous discussion
                - Smoothly introduces {topic} from their CV/resume
                - Shows continuity in the conversation
                - Asks about basic concepts they should know from their experience
                - Flows naturally from the previous topic
                
                Example approach:
                "That's helpful, thank you. Now I'd like to shift to another area from your resume - {topic}. I see you have experience with this as well, so could you tell me..."
                
                Generate a natural topic transition and question:
                """
            else:
                prompt = f"""
                You are continuing an interview conversation. The candidate has been discussing {previous_topic}. 
                Now transition naturally to {topic} based on their CV.
                
                CV Context: {cv_reference}
                Previous conversation context: They just finished discussing {previous_topic}
                
                Create a natural transition that:
                - Acknowledges the previous discussion  
                - Smoothly introduces {topic} from their CV/resume
                - Shows continuity in the conversation
                - Asks about concepts they claim to know from their CV
                - Flows naturally from the previous topic
                
                Example approach:
                "Thanks for that explanation. Looking at another part of your background, I notice you've worked with {topic}. Given your experience in this area, I'd like to understand..."
                
                Generate a natural topic transition and question:
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

    def _get_cv_context_for_topic(self, topic: str) -> str:
        """Get relevant CV context for a specific topic."""
        if not self.cv_content:
            return f"The candidate mentioned {topic} in their background"

        # Look for the topic in CV content
        cv_lower = self.cv_content.lower()
        topic_lower = topic.lower()

        # Find sentences containing the topic
        sentences = self.cv_content.split(".")
        relevant_sentences = [s.strip() for s in sentences if topic_lower in s.lower()]

        if relevant_sentences:
            # Return first relevant sentence, truncated if too long
            context = (
                relevant_sentences[0][:100] + "..."
                if len(relevant_sentences[0]) > 100
                else relevant_sentences[0]
            )
            return f"From CV: {context}"
        else:
            return f"The candidate has {topic} in their background"

    def _generate_follow_up_question(
        self, context: ConversationContext, last_answer: str
    ) -> Tuple[str, QuestionMetadata]:
        """Generate a follow-up question that goes deeper into the current topic."""

        # Determine next depth level
        next_depth = self._get_next_depth_level(context.depth_level)

        prompt = f"""
        You are an interviewer having a natural conversation. The candidate just answered about {context.current_topic} from their CV experience. 
        Generate a natural follow-up response that shows you were listening and want to dig deeper.
        
        Current Topic: {context.current_topic}
        Previous Answer: {last_answer}
        Conversation History: {len(context.previous_answers)} previous exchanges
        
        Create a natural response that:
        - Shows you heard and understood their specific answer
        - References details from what they just said
        - Asks for more specific details naturally about their actual experience
        - Sounds like a real person having a conversation
        - Builds on the conversation flow so far
        - Avoids generic phrases - be specific to their answer
        
        Example approaches:
        "That's really interesting - you mentioned [specific detail from their answer]. In that situation, how did you..."
        "I can see that worked well for you. When you were implementing that, what challenges did you face with..."
        "That makes a lot of sense. You said [reference to their answer] - I'm curious about the technical details of..."
        
        Generate a natural, conversational follow-up that references their specific answer:
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
        You are an interviewer having a natural conversation. The candidate's answer about {context.current_topic} (from their CV) needs some clarification.
        Generate a supportive, natural response that helps them clarify.
        
        Previous Answer: {last_answer}
        
        Create a natural response that:
        - Sounds understanding and supportive (not critical)
        - Shows you want to help them explain better
        - References their CV experience to make them comfortable
        - Asks for clarification in a friendly way
        - Sounds like a real person helping them succeed
        
        Example approaches:
        "I can see you have experience with this from your background. Could you help me understand..."
        "That's interesting. Since this is something you've worked with, could you clarify..."
        "I want to make sure I understand your experience with this correctly. When you say..."
        
        Generate a natural, supportive clarification request:
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
        You are an interviewer having a natural conversation with a candidate about their {context.current_topic} experience from their CV.
        
        Generate a conversational response that asks about their real-world experience.
        
        Create a natural response that:
        - References specific experience from their CV with {context.current_topic}
        - Sounds like a real interviewer interested in their background
        - Asks about practical, hands-on experience naturally
        - Makes them comfortable by showing it's based on their resume
        - Flows naturally in conversation
        
        Example approaches:
        "I noticed you have {context.current_topic} experience on your resume. Tell me about how you actually used this in your work..."
        "Your background shows you've worked with {context.current_topic}. Walk me through a specific example of..."
        "Looking at your experience with {context.current_topic}, I'm curious about..."
        
        Generate a natural, conversational question about their practical experience:
        """

        question = self._generate_question_from_prompt(prompt)

        metadata = QuestionMetadata(
            question_type=QuestionType.TECHNICAL,
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

        # Create varied transition approaches to avoid repetition
        transition_styles = [
            "acknowledgment_shift",
            "natural_pivot",
            "topic_bridge",
            "simple_transition",
        ]

        # Choose style based on question count to ensure variety
        style = transition_styles[context.question_count % len(transition_styles)]

        prompt = f"""
        You are an interviewer having a natural conversation. You want to smoothly transition from discussing {context.current_topic} to {next_topic}.
        
        Current conversation context:
        - Just finished discussing {context.current_topic}
        - Moving to {next_topic} (also from their background)
        - This is question #{context.question_count + 1} in the conversation
        - Use transition style: {style}
        
        Create a natural transition using the "{style}" approach:
        
        For "acknowledgment_shift": Thank them for the previous answer, then shift focus
        For "natural_pivot": Connect the topics naturally if possible
        For "topic_bridge": Find a connection between topics
        For "simple_transition": Direct but smooth topic change
        
        The transition should:
        - Sound conversational and natural
        - Acknowledge they've covered {context.current_topic} 
        - Introduce {next_topic} without repeating "resume/CV" phrases
        - Flow smoothly in the ongoing conversation
        - Include a question about {next_topic}
        
        Example approaches for {style}:
        - "That gives me good insight into your {context.current_topic} work. Let's talk about {next_topic} now - tell me about..."
        - "Perfect, thank you. Shifting gears a bit to {next_topic} - how would you..."
        - "Great explanation. Now I'm curious about {next_topic} from your background..."
        
        Generate a natural transition with question about {next_topic}:
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
        You are an interviewer having a natural conversation. Based on their answer about {context.current_topic} (from their CV), generate a natural follow-up to verify their understanding.
        
        Previous Answer: {last_answer}
        
        Create a natural response that:
        - Shows you're interested in verifying their knowledge
        - References their CV experience with {context.current_topic}
        - Sounds like a real interviewer naturally probing
        - Makes them comfortable by relating to their background
        - Flows naturally in conversation
        
        Example approaches:
        "That's interesting. Since you've worked with this, can you give me a specific example of..."
        "I see. Given your experience with this, help me understand..."
        "That makes sense. In your work with {context.current_topic}, how exactly..."
        
        Generate a natural verification question:
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
        """Generate a fundamental technical question when specific topics are exhausted."""

        fundamental_areas = [
            "algorithm complexity analysis",
            "data structure selection and trade-offs",
            "memory management concepts",
            "concurrency and synchronization",
            "software design principles",
            "performance optimization techniques",
        ]

        area = fundamental_areas[len(context.topics_covered) % len(fundamental_areas)]

        prompt = f"""
        You are an interviewer having a natural conversation. You want to explore {area} as a fundamental technical concept.
        
        Create a conversational question that:
        - Introduces {area} naturally in conversation
        - Tests fundamental understanding
        - Sounds like a real interviewer asking
        - Is approachable and not intimidating
        - Flows naturally in the interview
        
        Example approaches:
        "Let's talk about {area} for a moment. This is a fundamental concept in technical work..."
        "I'd like to explore {area} with you. From your perspective..."
        "Moving to some fundamentals, let's discuss {area}..."
        
        Generate a natural, conversational question about {area}:
        """

        question = self._generate_question_from_prompt(prompt)

        metadata = QuestionMetadata(
            question_type=QuestionType.TECHNICAL,
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
