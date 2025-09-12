"""
Domain-agnostic fundamental question generation system for technical interviews.
This generator dynamically extracts technical concepts from any domain based on CV and JD,
generating academic/theoretical questions with direct answers.
"""

import re
import random
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from ..llm.base import BaseLLM
from ..config.settings import QuestionType


class DifficultyLevel(Enum):
    """Difficulty levels for fundamental questions."""

    BASIC = "basic"  # Entry level concepts
    INTERMEDIATE = "intermediate"  # Mid-level concepts
    ADVANCED = "advanced"  # Senior level concepts
    EXPERT = "expert"  # Expert level concepts


@dataclass
class FundamentalQuestion:
    """A dynamically generated fundamental question with its metadata."""

    question: str
    topic: str  # Specific topic from CV/JD
    domain: str  # Technical domain (e.g., "Machine Learning", "Web Development", "Data Analysis")
    difficulty: DifficultyLevel
    context: str  # CV/JD context that inspired this question
    expected_concepts: List[str]  # Key concepts that should be covered
    follow_up_prompts: List[str]  # Prompts for generating follow-ups


@dataclass
class InterviewState:
    """Current state of the fundamental interview."""

    current_topic: str  # Current topic being discussed
    current_domain: str  # Current technical domain
    difficulty_level: DifficultyLevel
    cv_topics: List[str]  # Topics extracted from CV
    jd_topics: List[str]  # Topics extracted from JD
    relevant_topics: List[str]  # Topics common to both CV and JD
    technical_domains: List[str]  # Identified technical domains
    topics_covered: List[str]
    questions_asked: List[FundamentalQuestion]
    correct_answers_count: int
    total_questions_count: int
    candidate_skill_level: str  # Assessed from CV and answers
    candidate_confidence_level: str  # low, medium, high
    needs_easier_questions: bool
    needs_harder_questions: bool


class FundamentalQuestionGenerator:
    """Domain-agnostic generator for fundamental technical questions based on CV and JD."""

    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self.interview_state = None

    def initialize_interview(
        self, resume_sections: Dict[str, str], job_description: str = ""
    ) -> InterviewState:
        """Initialize interview based on CV and JD analysis."""

        # Extract topics from CV and JD
        cv_content = " ".join(resume_sections.values())
        cv_topics = self._extract_technical_topics(cv_content, "CV")
        jd_topics = self._extract_technical_topics(job_description, "Job Description")

        # Find relevant topics and domains
        relevant_topics = self._find_relevant_topics(cv_topics, jd_topics)
        technical_domains = self._identify_technical_domains(cv_topics + jd_topics)

        # Assess candidate skill level from CV
        skill_level = self._assess_skill_level_from_cv(resume_sections)

        # Initialize interview state
        self.interview_state = InterviewState(
            current_topic="",
            current_domain="",
            difficulty_level=self._skill_to_difficulty(skill_level),
            cv_topics=cv_topics,
            jd_topics=jd_topics,
            relevant_topics=relevant_topics,
            technical_domains=technical_domains,
            topics_covered=[],
            questions_asked=[],
            correct_answers_count=0,
            total_questions_count=0,
            candidate_skill_level=skill_level,
            candidate_confidence_level="medium",
            needs_easier_questions=False,
            needs_harder_questions=False,
        )

        return self.interview_state

    def get_opening_question(self) -> Tuple[FundamentalQuestion, str]:
        """Generate the opening fundamental question."""

        # Select the most relevant topic and domain to start with
        starting_topic, starting_domain = self._select_starting_topic_and_domain()

        self.interview_state.current_topic = starting_topic
        self.interview_state.current_domain = starting_domain

        # Generate opening question
        question = self._generate_fundamental_question(
            starting_topic,
            starting_domain,
            self.interview_state.difficulty_level,
            is_opening=True,
        )

        # Update state
        self.interview_state.questions_asked.append(question)
        self.interview_state.total_questions_count += 1

        return question, self._format_natural_question(
            question.question, is_opening=True
        )

    def get_next_question(
        self,
        last_answer: Optional[str] = None,
        answer_evaluation: Optional[Dict] = None,
    ) -> Tuple[FundamentalQuestion, str]:
        """Get the next fundamental question based on conversation flow."""

        if last_answer and answer_evaluation:
            self._update_interview_state(last_answer, answer_evaluation)

        # Decide next question strategy
        if self._should_continue_current_topic():
            question = self._generate_follow_up_question(last_answer)
        elif self._should_adjust_difficulty():
            question = self._generate_difficulty_adjusted_question()
        else:
            question = self._transition_to_new_topic()

        # Update state
        self.interview_state.questions_asked.append(question)
        self.interview_state.total_questions_count += 1

        return question, self._format_natural_question(question.question)

    def _extract_technical_topics(self, text: str, source_type: str) -> List[str]:
        """Extract technical topics from any domain text."""

        if not text:
            return []

        extraction_prompt = f"""
Analyze the following {source_type} text and extract ALL technical topics, skills, technologies, 
tools, methodologies, and domain-specific concepts mentioned. Be comprehensive and include any 
technical terms regardless of the domain (software, data science, finance, healthcare, engineering, etc.).

Text: {text}

Extract technical topics including but not limited to:
- Programming languages and frameworks
- Technical tools and software
- Domain-specific methodologies and concepts
- Industry-specific technologies
- Technical skills and competencies
- Research areas and specializations
- Technical processes and workflows
- Standards and protocols
- Scientific/technical concepts

Return ONLY a clean list of technical topics, one per line, no formatting or numbering:
"""

        try:
            response = self.llm.complete(extraction_prompt)
            if response and hasattr(response, "text"):
                topics = []
                for line in response.text.strip().split("\n"):
                    topic = line.strip().lower()
                    # Remove common prefixes and clean up
                    topic = re.sub(r"^[-•*\d+\.\)]\s*", "", topic)
                    if (
                        topic
                        and len(topic) > 2
                        and not topic.startswith(("the ", "and ", "or "))
                    ):
                        topics.append(topic)
                return topics[:20]  # Limit to reasonable number
        except Exception as e:
            print(f"Error extracting topics: {e}")

        return ["technical knowledge", "problem solving"]

    def _identify_technical_domains(self, all_topics: List[str]) -> List[str]:
        """Identify the main technical domains from extracted topics."""

        topics_text = ", ".join(all_topics)

        domain_prompt = f"""
Based on these technical topics: {topics_text}

Identify the main technical domains/fields represented. Consider domains like:
- Software Development, Web Development, Mobile Development
- Data Science, Machine Learning, Artificial Intelligence
- DevOps, Cloud Computing, System Administration  
- Cybersecurity, Network Engineering
- Database Administration, Data Engineering
- UI/UX Design, Product Management
- Quality Assurance, Testing
- Research and Development
- Finance Technology, HealthTech, EdTech
- Hardware Engineering, Embedded Systems
- Any other technical domain

Return the 3-5 most relevant technical domains, one per line:
"""

        try:
            response = self.llm.complete(domain_prompt)
            if response and hasattr(response, "text"):
                domains = []
                for line in response.text.strip().split("\n"):
                    domain = line.strip()
                    domain = re.sub(r"^[-•*\d+\.\)]\s*", "", domain)
                    if domain and len(domain) > 3:
                        domains.append(domain)
                return domains[:5]
        except Exception as e:
            print(f"Error identifying domains: {e}")

        return ["Technical Development"]

    def _find_relevant_topics(
        self, cv_topics: List[str], jd_topics: List[str]
    ) -> List[str]:
        """Find topics that appear in both CV and JD for maximum relevance."""

        relevant = []
        for cv_topic in cv_topics:
            for jd_topic in jd_topics:
                # Check for exact match or partial match
                if (
                    cv_topic.lower() in jd_topic.lower()
                    or jd_topic.lower() in cv_topic.lower()
                    or self._topics_are_related(cv_topic, jd_topic)
                ):
                    if cv_topic not in relevant:
                        relevant.append(cv_topic)
                    break

        # If no overlapping topics found, prioritize JD topics then CV topics
        if not relevant:
            relevant = jd_topics[:8] if jd_topics else cv_topics[:8]

        return relevant

    def _topics_are_related(self, topic1: str, topic2: str) -> bool:
        """Check if two topics are semantically related."""

        # Simple heuristic - check for common words (can be enhanced with semantic similarity)
        words1 = set(topic1.lower().split())
        words2 = set(topic2.lower().split())

        # Remove common stop words
        stop_words = {
            "and",
            "or",
            "the",
            "a",
            "an",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
        }
        words1 = words1 - stop_words
        words2 = words2 - stop_words

        # Check if they share significant words
        intersection = words1.intersection(words2)
        return (
            len(intersection) > 0
            and len(intersection) / min(len(words1), len(words2)) > 0.3
        )

    def _select_starting_topic_and_domain(self) -> Tuple[str, str]:
        """Select the best topic and domain to start the interview with."""

        # Prioritize topics that appear in both CV and JD
        if self.interview_state.relevant_topics:
            starting_topic = self.interview_state.relevant_topics[0]
        elif self.interview_state.jd_topics:
            starting_topic = self.interview_state.jd_topics[0]
        elif self.interview_state.cv_topics:
            starting_topic = self.interview_state.cv_topics[0]
        else:
            starting_topic = "technical problem solving"

        # Select the most relevant domain
        if self.interview_state.technical_domains:
            starting_domain = self.interview_state.technical_domains[0]
        else:
            starting_domain = "Technical Development"

        return starting_topic, starting_domain

    def _generate_fundamental_question(
        self,
        topic: str,
        domain: str,
        difficulty: DifficultyLevel,
        is_opening: bool = False,
    ) -> FundamentalQuestion:
        """Generate a fundamental question related to the topic and domain."""

        # Build context information
        context_info = ""
        if (
            topic in self.interview_state.cv_topics
            and topic in self.interview_state.jd_topics
        ):
            context_info = (
                f"Since you have {topic} experience and it's required for this role, "
            )
        elif topic in self.interview_state.cv_topics:
            context_info = f"I see you have experience with {topic}, "
        elif topic in self.interview_state.jd_topics:
            context_info = f"This role requires {topic} knowledge, "

        question_prompt = f"""
Generate a fundamental theoretical question about {topic} in the context of {domain}.

Context: {context_info}
Difficulty Level: {difficulty.value}
Domain: {domain}
Topic: {topic}

The question should:
1. Test fundamental theoretical knowledge and concepts, not just practical experience
2. Have clear, academic answers with specific principles/concepts
3. Be appropriate for {difficulty.value} level understanding
4. Focus on underlying principles, theory, and foundational concepts
5. Be conversational and natural for an interview setting
6. Be answerable with direct knowledge rather than storytelling

Difficulty Guidelines:
- Basic: Entry-level concepts, definitions, basic principles
- Intermediate: Mid-level understanding, comparisons, trade-offs
- Advanced: Senior-level concepts, complex scenarios, deep understanding
- Expert: Expert-level concepts, cutting-edge knowledge, research-level understanding

Generate ONE clear, focused fundamental question:
"""

        try:
            response = self.llm.complete(question_prompt)
            question_text = response.text.strip()

            # Clean up the question
            question_text = re.sub(r"^\d+[\.\)]\s*", "", question_text)
            question_text = question_text.strip("\"'")
            if not question_text.endswith("?"):
                question_text += "?"

        except Exception as e:
            print(f"Error generating question: {e}")
            question_text = f"Can you explain the fundamental concepts and principles behind {topic}?"

        # Generate expected concepts
        expected_concepts = self._generate_expected_concepts(
            question_text, topic, domain, difficulty
        )

        return FundamentalQuestion(
            question=question_text,
            topic=topic,
            domain=domain,
            difficulty=difficulty,
            context=context_info,
            expected_concepts=expected_concepts,
            follow_up_prompts=[],
        )

    def _generate_expected_concepts(
        self, question: str, topic: str, domain: str, difficulty: DifficultyLevel
    ) -> List[str]:
        """Generate expected concepts that should be covered in the answer."""

        concepts_prompt = f"""
For this fundamental question about {topic} in {domain}:
"{question}"

List the key concepts, principles, and theoretical points that a {difficulty.value} level candidate should cover in their answer.
Focus on:
- Core theoretical concepts
- Fundamental principles
- Key definitions
- Important relationships/connections
- Critical understanding points

Return a simple list of key concepts, one per line, no formatting:
"""

        try:
            response = self.llm.complete(concepts_prompt)
            concepts = []
            for line in response.text.strip().split("\n"):
                concept = line.strip().strip("-•* ")
                if concept and len(concept) > 5:
                    concepts.append(concept)
            return concepts[:6]  # Limit to reasonable number
        except Exception as e:
            print(f"Error generating expected concepts: {e}")
            return [
                f"Basic understanding of {topic}",
                "Clear explanation of key concepts",
                "Relevant theoretical knowledge",
            ]

    def _should_continue_current_topic(self) -> bool:
        """Determine if we should continue with current topic."""

        current_topic_questions = [
            q
            for q in self.interview_state.questions_asked
            if q.topic == self.interview_state.current_topic
        ]

        # Continue if we've asked less than 3 questions on current topic
        # and candidate is performing adequately
        return (
            len(current_topic_questions) < 3
            and not self.interview_state.needs_easier_questions
            and not self.interview_state.needs_harder_questions
        )

    def _should_adjust_difficulty(self) -> bool:
        """Check if we should adjust difficulty level."""

        return (
            self.interview_state.needs_easier_questions
            or self.interview_state.needs_harder_questions
        )

    def _generate_follow_up_question(self, last_answer: str) -> FundamentalQuestion:
        """Generate a follow-up question that goes deeper into the current topic."""

        current_topic = self.interview_state.current_topic
        current_domain = self.interview_state.current_domain

        follow_up_prompt = f"""
Based on this answer about {current_topic} in {current_domain}:
"{last_answer}"

Generate a follow-up fundamental question that:
1. Goes deeper into the theoretical concepts mentioned
2. Tests more advanced understanding of the same topic area
3. Builds naturally on their previous answer
4. Remains academic and theoretical (not experiential)
5. Is appropriate for {self.interview_state.difficulty_level.value} level
6. Explores related concepts or principles

Generate ONE insightful follow-up question:
"""

        try:
            response = self.llm.complete(follow_up_prompt)
            question_text = response.text.strip().strip("\"'")
            if not question_text.endswith("?"):
                question_text += "?"
        except Exception as e:
            print(f"Error generating follow-up: {e}")
            question_text = (
                f"Can you elaborate on the theoretical aspects of {current_topic}?"
            )

        expected_concepts = self._generate_expected_concepts(
            question_text,
            current_topic,
            current_domain,
            self.interview_state.difficulty_level,
        )

        return FundamentalQuestion(
            question=question_text,
            topic=current_topic,
            domain=current_domain,
            difficulty=self.interview_state.difficulty_level,
            context="Follow-up question",
            expected_concepts=expected_concepts,
            follow_up_prompts=[],
        )

    def _generate_difficulty_adjusted_question(self) -> FundamentalQuestion:
        """Generate a question with adjusted difficulty level."""

        if self.interview_state.needs_harder_questions:
            new_difficulty = self._increase_difficulty(
                self.interview_state.difficulty_level
            )
            transition_context = "Moving to more advanced concepts"
        else:
            new_difficulty = self._decrease_difficulty(
                self.interview_state.difficulty_level
            )
            transition_context = "Let's focus on fundamental concepts"

        self.interview_state.difficulty_level = new_difficulty
        self.interview_state.needs_harder_questions = False
        self.interview_state.needs_easier_questions = False

        question = self._generate_fundamental_question(
            self.interview_state.current_topic,
            self.interview_state.current_domain,
            new_difficulty,
        )
        question.context = transition_context

        return question

    def _transition_to_new_topic(self) -> FundamentalQuestion:
        """Transition to a new topic from CV/JD."""

        # Mark current topic as covered
        if (
            self.interview_state.current_topic
            not in self.interview_state.topics_covered
        ):
            self.interview_state.topics_covered.append(
                self.interview_state.current_topic
            )

        # Find next topic
        uncovered_relevant = [
            topic
            for topic in self.interview_state.relevant_topics
            if topic not in self.interview_state.topics_covered
        ]

        if uncovered_relevant:
            next_topic = uncovered_relevant[0]
        else:
            # Fall back to any uncovered topic from CV or JD
            all_topics = list(
                set(self.interview_state.cv_topics + self.interview_state.jd_topics)
            )
            uncovered_topics = [
                topic
                for topic in all_topics
                if topic not in self.interview_state.topics_covered
            ]
            next_topic = (
                uncovered_topics[0]
                if uncovered_topics
                else "advanced technical concepts"
            )

        # Select appropriate domain for the new topic
        next_domain = self._select_domain_for_topic(next_topic)

        # Update current topic and domain
        self.interview_state.current_topic = next_topic
        self.interview_state.current_domain = next_domain

        # Adjust difficulty based on performance
        if self.interview_state.total_questions_count > 0:
            success_rate = (
                self.interview_state.correct_answers_count
                / self.interview_state.total_questions_count
            )
            if success_rate > 0.75:
                self.interview_state.difficulty_level = self._increase_difficulty(
                    self.interview_state.difficulty_level
                )
            elif success_rate < 0.4:
                self.interview_state.difficulty_level = self._decrease_difficulty(
                    self.interview_state.difficulty_level
                )

        return self._generate_fundamental_question(
            next_topic, next_domain, self.interview_state.difficulty_level
        )

    def _select_domain_for_topic(self, topic: str) -> str:
        """Select the most appropriate domain for a given topic."""

        # Use LLM to intelligently match topic to domain
        if self.interview_state.technical_domains:
            domain_selection_prompt = f"""
Given the topic "{topic}" and these available technical domains:
{', '.join(self.interview_state.technical_domains)}

Which domain is most appropriate for discussing {topic}? 
Return only the domain name:
"""

            try:
                response = self.llm.complete(domain_selection_prompt)
                selected_domain = response.text.strip()
                if selected_domain in self.interview_state.technical_domains:
                    return selected_domain
            except Exception:
                pass

        # Fallback to first available domain
        return (
            self.interview_state.technical_domains[0]
            if self.interview_state.technical_domains
            else "Technical Development"
        )

    def _format_natural_question(self, question: str, is_opening: bool = False) -> str:
        """Format question with natural conversation elements."""

        if is_opening:
            opening_phrases = [
                "Let's start by exploring some fundamental concepts. ",
                "I'd like to begin with some theoretical questions related to your background. ",
                "Let's dive into some core concepts that are relevant to this role. ",
            ]
            return random.choice(opening_phrases) + question

        # Add natural transitions for non-opening questions
        transition_phrases = [
            "Great. ",
            "Interesting. ",
            "I see. ",
            "Good. ",
            "Alright. ",
            "Thanks. ",
        ]

        if random.random() < 0.4:  # 40% chance of transition
            return random.choice(transition_phrases) + question

        return question

    def _update_interview_state(self, last_answer: str, evaluation: Dict):
        """Update interview state based on answer evaluation."""

        overall_score = evaluation.get("overall_score", 0.5)

        # Update correct answers count
        if overall_score >= 0.7:
            self.interview_state.correct_answers_count += 1

        # Update confidence level
        if overall_score >= 0.8:
            self.interview_state.candidate_confidence_level = "high"
        elif overall_score >= 0.5:
            self.interview_state.candidate_confidence_level = "medium"
        else:
            self.interview_state.candidate_confidence_level = "low"

        # Determine difficulty adjustments
        if overall_score < 0.4:
            self.interview_state.needs_easier_questions = True
        elif overall_score > 0.8:
            self.interview_state.needs_harder_questions = True

    def _assess_skill_level_from_cv(self, resume_sections: Dict[str, str]) -> str:
        """Assess candidate skill level from CV content."""

        experience_text = resume_sections.get("experience", "")
        skills_text = resume_sections.get("skills", "")
        education_text = resume_sections.get("education", "")

        combined_text = f"{experience_text} {skills_text} {education_text}".lower()

        # Look for experience indicators
        years_match = re.findall(r"(\d+)\s*(?:years?|yrs?)", combined_text)
        max_years = max([int(y) for y in years_match], default=0)

        # Look for seniority indicators
        senior_terms = [
            "senior",
            "lead",
            "principal",
            "architect",
            "manager",
            "head",
            "director",
            "expert",
            "specialist",
        ]
        has_senior_role = any(term in combined_text for term in senior_terms)

        # Look for advanced concepts (domain-agnostic)
        advanced_terms = [
            "research",
            "optimization",
            "architecture",
            "design",
            "analysis",
            "strategy",
            "methodology",
        ]
        has_advanced_concepts = any(term in combined_text for term in advanced_terms)

        # Determine skill level
        if max_years >= 7 or has_senior_role:
            return "expert"
        elif max_years >= 4 or has_advanced_concepts:
            return "advanced"
        elif max_years >= 1:
            return "intermediate"
        else:
            return "beginner"

    def _skill_to_difficulty(self, skill_level: str) -> DifficultyLevel:
        """Convert skill level to difficulty level."""

        mapping = {
            "beginner": DifficultyLevel.BASIC,
            "intermediate": DifficultyLevel.INTERMEDIATE,
            "advanced": DifficultyLevel.ADVANCED,
            "expert": DifficultyLevel.EXPERT,
        }
        return mapping.get(skill_level, DifficultyLevel.INTERMEDIATE)

    def _increase_difficulty(self, current: DifficultyLevel) -> DifficultyLevel:
        """Increase difficulty level."""

        progression = {
            DifficultyLevel.BASIC: DifficultyLevel.INTERMEDIATE,
            DifficultyLevel.INTERMEDIATE: DifficultyLevel.ADVANCED,
            DifficultyLevel.ADVANCED: DifficultyLevel.EXPERT,
            DifficultyLevel.EXPERT: DifficultyLevel.EXPERT,
        }
        return progression.get(current, DifficultyLevel.INTERMEDIATE)

    def _decrease_difficulty(self, current: DifficultyLevel) -> DifficultyLevel:
        """Decrease difficulty level."""

        regression = {
            DifficultyLevel.EXPERT: DifficultyLevel.ADVANCED,
            DifficultyLevel.ADVANCED: DifficultyLevel.INTERMEDIATE,
            DifficultyLevel.INTERMEDIATE: DifficultyLevel.BASIC,
            DifficultyLevel.BASIC: DifficultyLevel.BASIC,
        }
        return regression.get(current, DifficultyLevel.BASIC)

    def get_interview_summary(self) -> Dict[str, Any]:
        """Get a summary of the fundamental interview session."""

        success_rate = 0
        if self.interview_state.total_questions_count > 0:
            success_rate = (
                self.interview_state.correct_answers_count
                / self.interview_state.total_questions_count
            )

        return {
            "total_questions": self.interview_state.total_questions_count,
            "correct_answers": self.interview_state.correct_answers_count,
            "success_rate": success_rate,
            "topics_covered": self.interview_state.topics_covered,
            "cv_topics_extracted": self.interview_state.cv_topics,
            "jd_topics_extracted": self.interview_state.jd_topics,
            "relevant_topics": self.interview_state.relevant_topics,
            "technical_domains": self.interview_state.technical_domains,
            "final_difficulty_level": self.interview_state.difficulty_level.value,
            "candidate_skill_level": self.interview_state.candidate_skill_level,
            "candidate_confidence": self.interview_state.candidate_confidence_level,
        }

    def evaluate_answer(
        self, question: FundamentalQuestion, answer: str
    ) -> Dict[str, Any]:
        """Evaluate a fundamental answer for academic correctness."""

        evaluation_prompt = f"""
Evaluate this answer to a fundamental technical question about {question.topic} in {question.domain}.

Question: {question.question}
Expected Level: {question.difficulty.value}
Answer: {answer}

Expected Key Concepts: {', '.join(question.expected_concepts)}

Rate the answer on these criteria (0.0 to 1.0):
1. Conceptual Accuracy: How technically correct are the concepts mentioned?
2. Completeness: How well does it cover the expected concepts?
3. Depth: How deep is the understanding demonstrated?
4. Clarity: How clearly are concepts explained?

Also provide:
- Overall Score (0.0 to 1.0)
- Missing Concepts (what important concepts were not mentioned)
- Strengths (what the candidate did well)
- Areas for Improvement

Format your response as:
Conceptual Accuracy: [score]
Completeness: [score]
Depth: [score]
Clarity: [score]
Overall Score: [score]
Missing Concepts: [list]
Strengths: [list]
Areas for Improvement: [list]
"""

        try:
            response = self.llm.complete(evaluation_prompt)
            evaluation_text = response.text.strip()

            # Parse the evaluation (simplified parsing)
            evaluation = self._parse_evaluation_response(evaluation_text)
            return evaluation

        except Exception as e:
            print(f"Error evaluating answer: {e}")
            return {
                "overall_score": 0.5,
                "conceptual_accuracy": 0.5,
                "completeness": 0.5,
                "depth": 0.5,
                "clarity": 0.5,
                "missing_concepts": [],
                "strengths": [],
                "areas_for_improvement": [],
            }

    def _parse_evaluation_response(self, evaluation_text: str) -> Dict[str, Any]:
        """Parse the LLM evaluation response into structured data."""

        evaluation = {
            "overall_score": 0.5,
            "conceptual_accuracy": 0.5,
            "completeness": 0.5,
            "depth": 0.5,
            "clarity": 0.5,
            "missing_concepts": [],
            "strengths": [],
            "areas_for_improvement": [],
        }

        try:
            lines = evaluation_text.split("\n")
            for line in lines:
                line = line.strip()
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip().lower().replace(" ", "_")
                    value = value.strip()

                    if key in [
                        "conceptual_accuracy",
                        "completeness",
                        "depth",
                        "clarity",
                        "overall_score",
                    ]:
                        # Extract numeric value
                        score_match = re.search(r"([0-9]*\.?[0-9]+)", value)
                        if score_match:
                            evaluation[key] = float(score_match.group(1))
                    elif key in [
                        "missing_concepts",
                        "strengths",
                        "areas_for_improvement",
                    ]:
                        # Extract list items
                        items = [
                            item.strip() for item in value.split(",") if item.strip()
                        ]
                        evaluation[key] = items
        except Exception as e:
            print(f"Error parsing evaluation: {e}")

        return evaluation
