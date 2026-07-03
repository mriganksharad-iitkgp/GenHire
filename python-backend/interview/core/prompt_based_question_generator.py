"""
Simple prompt-based question generator using the technical interview prompts.
This is designed to work with the existing session manager without modifications.
"""

import os
import re
import json
import logging
import hashlib
import random
import time
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

from ..llm.base import BaseLLM
from .cost_tracker import CostTracker
from ..config.settings import QuestionType, InterviewConfig
from ..prompts import (
    CV_KEYWORDS_EXTRACTION_PROMPT,
    JD_KEYWORDS_EXTRACTION_PROMPT,
    JD_DIFFICULTY_DISTRIBUTION_PROMPT,
    SKILL_LEVEL_ASSESSMENT_PROMPT,
    GREETING_PROMPT,
    FALLBACK_GREETING,
    STRUCTURE_EXPLANATION_PROMPT,
    FALLBACK_STRUCTURE_EXPLANATION,
    EXPERIENTIAL_QUESTION_PROMPT,
    FALLBACK_EXPERIENTIAL_QUESTION,
    TECHNICAL_QUESTION_PROMPT,
    REPHRASE_BANK_QUESTION_PROMPT,
    FALLBACK_TECHNICAL_QUESTION,
    PERFORMANCE_GUIDANCE,
    PREVIOUS_ANSWER_CONTEXT,
    CLOSING_PROMPT,
    FALLBACK_CLOSING,
    HR_QUESTION_PROMPT,
    FALLBACK_HR_QUESTION,
    HR_PREVIOUS_ANSWER_CONTEXT,
)

logger = logging.getLogger(__name__)

# In-memory cache for the 4 LLM calls made during initialize_conversation().
# Keyed on MD5(cv_text[:3000] + jd_text[:3000]) — same candidate+JD reuses results.
_INIT_CACHE: Dict[str, Any] = {}
_INIT_CACHE_MAX = 50


class InterviewPhase(Enum):
    """Different phases of the interview."""

    GREETING = "greeting"
    STRUCTURE_EXPLANATION = "structure_explanation"
    EXPERIENTIAL_QUESTIONS = "experiential_questions"
    TECHNICAL_QUESTIONS = "technical_questions"
    HR_QUESTIONS = "hr_questions"
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
    candidate_skill_level: str  # extracted from CV
    jd_required_skill_level: str  # extracted from JD
    answer_quality_trend: List[float]
    follow_up_count: int
    needs_topic_change: bool
    conversation_energy: str
    has_been_greeted: bool = False
    previous_answers: List[str] = field(default_factory=list)
    question_count: int = 0
    interview_phase: InterviewPhase = InterviewPhase.GREETING
    candidate_name: str = "candidate"
    cv_keywords: List[str] = field(default_factory=list)
    jd_keywords: List[str] = field(default_factory=list)
    job_title: str = "Software Developer"
    cv_experiences: List[str] = field(default_factory=list)
    cv_projects: List[str] = field(default_factory=list)
    experiential_questions_asked: int = 0
    questions_on_current_topic: int = 0
    last_mentioned_concepts: List[str] = field(default_factory=list)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    role_difficulty: str = "medium"  # easy|medium|hard derived from JD
    difficulty_distribution: Dict[str, float] = field(default_factory=lambda: {"easy": 0.3, "medium": 0.4, "hard": 0.3})
    hr_questions_asked: int = 0
    hr_question_types_asked: List[str] = field(default_factory=list)
    asked_questions: List[str] = field(default_factory=list)
    fallback_usage_by_topic: Dict[str, int] = field(default_factory=dict)
    job_role: str = "software_engineer"

    def __post_init__(self):
        # No initialization needed since we're using field(default_factory)
        pass


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
    source: str = "unknown"


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
        # Use relative path from the current file location
        current_dir = os.path.dirname(os.path.abspath(__file__))
        question_bank_dir = os.path.join(current_dir, "..", "..", "question_bank", "technical_question_bank")
        self.question_bank_path = os.path.join(question_bank_dir, "ai_ml_interview_questions.json")
        self.question_bank_dir = question_bank_dir
        self.question_bank_paths = []
        self.question_bank = None
        self.question_embeddings = None
        # HR question banks
        self.hr_question_banks: Dict[str, List[Dict[str, Any]]] = {"fresher": [], "intermediate": [], "senior": []}
        self.hr_question_embeddings: Dict[str, List[Dict[str, Any]]] = {"fresher": [], "intermediate": [], "senior": []}
        self._load_hr_question_banks()
        self.last_question_source = "unknown"
        # Fallback variant pools
        self.exp_fallback_variants: List[str] = [
            "Could you share details about another project from your CV—goals, your responsibilities, tech stack, challenges, and measurable outcomes?",
            "Pick a different project and briefly explain the goals, your role, tools used, blockers you faced, and the final impact.",
            "Tell me about one more project from your CV. Focus on objectives, your contributions, technologies, key challenges, and results.",
        ]
        self.hr_fallback_variants: List[str] = [
            "What motivates you about this role, and how do your strengths match what we need?",
            "Which parts of this role resonate most with you, and how does your experience prepare you for them?",
            "What aspects of the opportunity excite you, and where do your skills best align?",
        ]
        self.tech_fallback_variants: List[str] = [
            "Can you discuss a different aspect of {topic} you've worked on and how you applied it?",
            "Share a practical example where you used {topic}. What was the problem, approach, and outcome?",
            "What trade-offs have you considered when working with {topic}, and how did you decide?",
        ]
        
    # Transient error keywords that are safe to retry (rate limits, network blips).
    _RETRYABLE_ERRORS = ("rate", "429", "503", "502", "500", "timeout", "connection",
                         "reset", "unavailable", "overloaded", "try again")

    def _complete_llm(self, prompt: str, max_retries: int = 3) -> Any:
        """LLM completion with cost tracking and exponential-backoff retry.

        Retries up to max_retries times on transient errors (rate limits, timeouts,
        temporary server errors). Non-retriable errors are re-raised immediately so
        FallbackLLM can switch providers.
        """
        last_exc: Exception = RuntimeError("No attempts made")
        for attempt in range(max_retries):
            try:
                response = self.llm.complete(prompt)

                # Track cost with robust usage extraction
                prompt_tokens = 0
                completion_tokens = 0
                model_name = getattr(response, "model", None) or self.config.default_model

                if hasattr(response, "usage"):
                    if isinstance(response.usage, dict):
                        prompt_tokens = response.usage.get("prompt_tokens", 0)
                        completion_tokens = response.usage.get("completion_tokens", 0)
                    else:
                        prompt_tokens = getattr(response.usage, "prompt_tokens", 0)
                        completion_tokens = getattr(response.usage, "completion_tokens", 0)

                if prompt_tokens == 0 and hasattr(response, "raw"):
                    raw = response.raw
                    if hasattr(raw, "usage_metadata"):
                        prompt_tokens = getattr(raw.usage_metadata, "prompt_token_count", 0)
                        completion_tokens = getattr(raw.usage_metadata, "candidates_token_count", 0)

                CostTracker().add_usage(
                    source="question_generation",
                    model=model_name,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    prompt_text=prompt,
                    completion_text=getattr(response, "text", "") if response else "",
                    usage=getattr(response, "usage", None),
                )
                return response

            except Exception as exc:
                err_lower = str(exc).lower()
                is_transient = any(kw in err_lower for kw in self._RETRYABLE_ERRORS)
                if is_transient and attempt < max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s … + ±0.5s jitter
                    wait = (2 ** attempt) + random.uniform(-0.5, 0.5)
                    wait = max(0.5, wait)
                    logger.warning(
                        "LLM transient error (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1, max_retries, wait, exc,
                    )
                    time.sleep(wait)
                    last_exc = exc
                else:
                    raise
        raise last_exc

    def _get_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for text using a simple method.
        
        In a production environment, you would use a proper embedding model.
        This is a simplified version for demonstration purposes.
        """
        # Simple character-based embedding (for demonstration only)
        # In production, use a proper embedding model like:
        # - self.llm.get_embedding(text) if your LLM supports it
        # - sentence-transformers, OpenAI embeddings API, etc.
        
        # Simple character frequency vector (26 lowercase letters + space)
        vec = np.zeros(27)
        text = text.lower()
        for char in text:
            if 'a' <= char <= 'z':
                vec[ord(char) - ord('a')] += 1
            elif char == ' ':
                vec[26] += 1
        
        # Normalize the vector
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    @staticmethod
    def _init_cache_key(cv_content: str, jd_content: str) -> str:
        combined = (cv_content[:3000] + "|" + jd_content[:3000]).encode("utf-8", errors="ignore")
        return hashlib.md5(combined).hexdigest()

    def initialize_conversation(
        self, resume_sections: Dict[str, str], job_description: str = ""
    ) -> ConversationContext:
        """Initialize conversation context based on resume and job description."""
        self.resume_sections = resume_sections
        self.cv_content = " ".join(resume_sections.values())

        cache_key = self._init_cache_key(self.cv_content, job_description)
        if cache_key in _INIT_CACHE:
            logger.info("init_cache HIT — reusing CV/JD keyword and skill extractions")
            cv_keywords, jd_keywords, skill_level, difficulty_dist = _INIT_CACHE[cache_key]
        else:
            # Run the four LLM-based extractions in parallel so the background
            # init thread finishes in ~2-3 s instead of the 6-10 s it took when
            # these four calls ran sequentially.
            with ThreadPoolExecutor(max_workers=4) as pool:
                cv_kw_future   = pool.submit(self._extract_cv_keywords, self.cv_content, job_description)
                jd_kw_future   = pool.submit(self._extract_jd_keywords, job_description)
                skill_future   = pool.submit(self._assess_initial_skill_level, resume_sections)
                diff_future    = pool.submit(self._analyze_jd_difficulty_distribution, job_description)

                cv_keywords    = cv_kw_future.result()
                jd_keywords    = jd_kw_future.result()
                skill_level    = skill_future.result()
                difficulty_dist = diff_future.result()

            # Evict oldest entry when the cache is full (simple FIFO)
            if len(_INIT_CACHE) >= _INIT_CACHE_MAX:
                _INIT_CACHE.pop(next(iter(_INIT_CACHE)))
            _INIT_CACHE[cache_key] = (cv_keywords, jd_keywords, skill_level, difficulty_dist)

        # Extract job title from job description
        job_title = self._extract_job_title(job_description)
        # Determine canonical job role and filter topics accordingly
        job_role = self._extract_job_role(job_title, jd_keywords)
        cv_keywords = self._filter_keywords_by_role(cv_keywords, job_role)
        jd_keywords = self._filter_keywords_by_role(jd_keywords, job_role)
        self._load_question_banks_for_role(job_role)

        # Classify role difficulty from JD (heuristic — no LLM needed)
        role_diff = self._classify_role_difficulty(job_description)
        skill_level_map = {"easy": "beginner", "medium": "intermediate", "hard": "expert"}
        jd_required_skill = skill_level_map.get(role_diff, "intermediate")
        
        candidate_name = self._extract_candidate_name(resume_sections)

        # Select starting topic: PRIORITIZE JD keywords to make interview role-focused
        starting_topic = "role fundamentals"
        if jd_keywords:
            # ONLY use JD keywords for technical topics
            starting_topic = jd_keywords[0]
        elif cv_keywords:
            # Very last fallback if JD extraction fails completely
            starting_topic = cv_keywords[0]

        # Extract experiences and projects
        experiences = self._extract_experiences(resume_sections)
        projects = self._extract_projects(resume_sections)

        context = ConversationContext(
            current_topic=starting_topic,
            depth_level=ConversationDepth.SURFACE,
            topics_covered=[],
            candidate_skill_level=skill_level,
            jd_required_skill_level=jd_required_skill,
            answer_quality_trend=[],
            follow_up_count=0,
            needs_topic_change=False,
            conversation_energy="neutral",
            has_been_greeted=False,
            question_count=0,
            interview_phase=InterviewPhase.GREETING,
            candidate_name=candidate_name,
            cv_keywords=cv_keywords,
            jd_keywords=jd_keywords,
            job_title=job_title,
            cv_experiences=experiences,
            cv_projects=projects,
            role_difficulty=role_diff,
            difficulty_distribution=difficulty_dist,
            job_role=job_role,
        )

        self.conversation_context = context
        return context

    def _generate_greeting(self, context: ConversationContext) -> str:
        """Generate interview greeting for the candidate."""
        try:
            prompt = GREETING_PROMPT.format(
                candidate_name=context.candidate_name
            )
            response = self._complete_llm(prompt)
            if response and hasattr(response, 'text'):
                self.last_question_source = "prompt"
                return response.text.strip()
            self.last_question_source = "fallback"
            return self._fallback_greeting(context)
        except Exception:
            self.last_question_source = "fallback"
            return self._fallback_greeting(context)

    def _refine_with_jd(self, bank_question: str, topic: str, difficulty: str, context: ConversationContext) -> str:
        """Return the bank question directly — no LLM call needed.

        The bank questions are already topic-matched and well-written.  The
        previous LLM-based rephrasing added 1-2 s of latency per question with
        minimal quality benefit, because the question bank is already curated for
        the role and the input JD summary (job title + 5 keywords) provided too
        little signal to produce meaningfully better questions.
        """
        return bank_question

    def _generate_technical_question(
        self,
        context: ConversationContext,
        last_answer: Optional[str] = None,
        answer_evaluation: Optional[Dict] = None,
    ) -> str:
        """Generate a technical question strictly based on JD requirements, using bank as primary source."""
        # Select difficulty based on JD-derived distribution
        selected_diff = self._select_question_difficulty(context)

        # If candidate says it's a repeat, rotate topic proactively
        if self._user_indicates_repetition(last_answer):
            next_topic = self._get_next_topic(context)
            if next_topic:
                context.current_topic = next_topic
                context.fallback_usage_by_topic[next_topic] = 0

        # Build context about previous answers
        jd_keywords_str = ", ".join(context.jd_keywords or []) if context.jd_keywords else "N/A"
        
        previous_context = ""
        score = 0.5  # Default score
        
        performance_guidance = PERFORMANCE_GUIDANCE["good"]
        if last_answer and answer_evaluation:
            score = answer_evaluation.get("relevance_score", 0.5)
            mentioned_concepts = self._extract_concepts_from_answer(last_answer)
            context.last_mentioned_concepts = mentioned_concepts
            
            if context.conversation_history:
                last_question = context.conversation_history[-1].get("question", "")
                context.conversation_history.append({
                    "question": last_question,
                    "answer": last_answer[:200] + "..." if len(last_answer) > 200 else last_answer,
                    "score": score,
                })
            
            if score < 0.3:
                performance_guidance = PERFORMANCE_GUIDANCE["struggled"]
            elif score < 0.6:
                performance_guidance = PERFORMANCE_GUIDANCE["partial"]
            elif score < 0.8:
                performance_guidance = PERFORMANCE_GUIDANCE["good"]
            else:
                performance_guidance = PERFORMANCE_GUIDANCE["excellent"]

            concepts_mentioned = ", ".join(mentioned_concepts[:3]) if mentioned_concepts else "the topics discussed"
            previous_context = PREVIOUS_ANSWER_CONTEXT.format(
                last_answer_preview=last_answer[:200],
                concepts_mentioned=concepts_mentioned,
                score=score,
                performance_guidance=performance_guidance,
            )

        # Determine question type based on question count
        if context.question_count <= 3:
            question_type = "foundational"
        elif context.question_count <= 6:
            question_type = "practical application"
        else:
            question_type = "advanced scenario-based"

        topics_covered_str = ", ".join(context.topics_covered) if context.topics_covered else "none yet"

        # STEP 1: Try to get a question from the bank matching the selected difficulty (JD-driven)
        bank_q = self._get_question_from_bank(context, context.current_topic, selected_diff)
        if bank_q:
            logger.info(f"Question bank HIT for topic '{context.current_topic}' and difficulty '{selected_diff}'")
            
            # REFINE the bank question using the JD (Ignore CV)
            refined_q = self._refine_with_jd(bank_q, context.current_topic, selected_diff, context)
            
            if context.current_topic not in context.topics_covered:
                context.topics_covered.append(context.current_topic)
            
            context.questions_on_current_topic += 1
            
            # Check if should switch topic
            should_switch = self._should_switch_topic(context, answer_evaluation)
            if should_switch:
                next_topic = self._get_next_topic(context)
                if next_topic:
                    context.current_topic = next_topic
                    context.questions_on_current_topic = 0
            
            self.last_question_source = "bank_refined"
            return refined_q

        # STEP 2: If no bank question, generate one using LLM (STRICTLY JD-primary)
        try:
            prompt = TECHNICAL_QUESTION_PROMPT.format(
                role_jd_keywords=jd_keywords_str,
                current_topic=context.current_topic,
                question_type=question_type,
                topics_covered=topics_covered_str,
                previous_context=previous_context,
                performance_guidance=performance_guidance,
                job_title=context.job_title,
                role_difficulty=selected_diff,
            )
            response = self._complete_llm(prompt)
            if response and hasattr(response, 'text'):
                question = response.text.strip()
                if question and len(question) > 10 and not self._is_near_duplicate(context, question):
                    if self._is_on_role_question(question, context.job_role, context.jd_keywords):
                        self.last_question_source = "prompt"
                        if context.current_topic not in context.topics_covered:
                            context.topics_covered.append(context.current_topic)
                        
                        context.questions_on_current_topic += 1
                        
                        should_switch = self._should_switch_topic(context, answer_evaluation)
                        if should_switch:
                            next_topic = self._get_next_topic(context)
                            if next_topic:
                                context.current_topic = next_topic
                                context.questions_on_current_topic = 0
                        
                        return question
        except Exception as e:
            logger.error(f"Error generating JD-driven technical question: {e}")
        
        # STEP 3: Fallback
        return self._fallback_technical_question_with_context(context, last_answer or "", score)

    def _select_question_difficulty(self, context: ConversationContext) -> str:
        """Select question difficulty based on JD-derived difficulty distribution."""
        dist = getattr(context, "difficulty_distribution", {"easy": 0.3, "medium": 0.4, "hard": 0.3})
        
        # Simple weighted random choice
        r = np.random.random()
        cumulative = 0.0
        for diff in ["easy", "medium", "hard"]:
            cumulative += dist.get(diff, 0.0)
            if r <= cumulative:
                return diff
        return "medium"

    def _load_question_bank(self) -> None:
        if not getattr(self, "question_bank_dir", None):
            self.question_bank = None
            self.question_embeddings = None
            return
        aggregated: List[Dict[str, Any]] = []
        paths: List[str] = []
        try:
            for fname in os.listdir(self.question_bank_dir):
                if fname.lower().endswith(".json"):
                    paths.append(os.path.join(self.question_bank_dir, fname))
        except Exception:
            if self.question_bank_path:
                paths = [self.question_bank_path]
        self.question_bank_paths = paths
        for p in paths:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        aggregated.extend(data)
                    elif isinstance(data, dict):
                        aggregated.extend(data.get("questions", []))
            except Exception:
                continue
        self.question_bank = aggregated if aggregated else None
        self.question_embeddings = [] if aggregated else None
        if not aggregated:
            return
        for idx, item in enumerate(aggregated):
            try:
                topic = item.get("topic", "").lower()
                question = item.get("question", "")
                difficulty = item.get("difficulty", "").lower()
                role = item.get("role", "").lower()
                combined_text = f"{topic} {question} {difficulty} {role}"
                embedding = self._get_embedding(combined_text)
                self.question_embeddings.append({
                    "question": question,
                    "topic": topic,
                    "difficulty": difficulty,
                    "embedding": embedding,
                    "index": idx
                })
            except Exception:
                continue

    def _select_bank_files_for_role(self, job_role: str) -> List[str]:
        role = (job_role or "software_engineer").lower()
        files: List[str] = []
        try:
            for fname in os.listdir(self.question_bank_dir):
                if fname.lower().endswith(".json"):
                    files.append(os.path.join(self.question_bank_dir, fname))
        except Exception:
            return [self.question_bank_path] if self.question_bank_path else []
        patterns_map = {
            "data_scientist": ["ai_ml", "ai_interview", "ai-ml", "ml"],
            "data_analyst": ["data_analytics", "analytics", "analyst"],
            "software_engineer": ["software_development", "software"],
            "full_stack_developer": ["software_development", "software"],
            "devops_engineer": ["devops"],
            "business_analyst": ["business", "analyst", "finance", "data_analytics"],
            "product_engineer": ["software_development", "software"],
        }
        pats = patterns_map.get(role, [])
        if not pats:
            return files
        chosen = [p for p in files if any(pt in os.path.basename(p).lower() for pt in pats)]
        return chosen or files

    def _load_question_banks_for_role(self, job_role: str) -> None:
        paths = self._select_bank_files_for_role(job_role)
        self.question_bank_paths = paths  # Store for display/tracking
        aggregated: List[Dict[str, Any]] = []
        for p in paths:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        aggregated.extend(data)
                    elif isinstance(data, dict):
                        aggregated.extend(data.get("questions", []))
            except Exception:
                continue
        self.question_bank = aggregated if aggregated else None
        self.question_embeddings = [] if aggregated else None
        if not aggregated:
            return
        self.question_embeddings.clear()
        for idx, item in enumerate(aggregated):
            try:
                topic = item.get("topic", "").lower()
                question = item.get("question", "")
                difficulty = item.get("difficulty", "").lower()
                role = item.get("role", "").lower()
                combined_text = f"{topic} {question} {difficulty} {role}"
                embedding = self._get_embedding(combined_text)
                self.question_embeddings.append({
                    "question": question,
                    "topic": topic,
                    "difficulty": difficulty,
                    "embedding": embedding,
                    "index": idx
                })
            except Exception:
                continue

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
        """Determine if we should switch to a new topic based on conversation flow.
        
        Forces very frequent topic changes for technical questions.
        """
        # FORCED SWITCH: After at most 2 questions, always switch.
        if context.questions_on_current_topic >= 2:
            return True
            
        # PREFERRED SWITCH: Switch after 1 question if there are many topics remaining
        covered_lowered = [c.lower() for c in context.topics_covered]
        uncovered_jd_count = len([t for t in context.jd_keywords if t.lower() not in covered_lowered])
        if context.questions_on_current_topic >= 1 and uncovered_jd_count > 2:
            return True
            
        # Performance-based early switch
        if answer_evaluation and context.questions_on_current_topic >= 1:
            score = answer_evaluation.get("relevance_score", 0.5)
            if score < 0.4: # Struggle detected, move to new topic immediately
                return True
                
        return False

    def _get_next_topic(self, context: ConversationContext) -> Optional[str]:
        """Get the next topic to explore - ONLY consider JD keywords for technical rounds."""
        # Clean and prioritize keywords from JD
        jd_keywords = [t.lower() for t in (context.jd_keywords or []) if t]
        covered = [t.lower() for t in (context.topics_covered or []) if t]
        
        # Ensure current topic is added to covered to avoid repeats
        if context.current_topic.lower() not in covered:
            covered.append(context.current_topic.lower())

        # Priority 1: Uncovered JD keywords that are on-role
        jd_allowed = [t for t in jd_keywords if t not in covered and self._is_topic_on_role(t, context.job_role)]
        if jd_allowed:
            return jd_allowed[0]

        # Priority 2: Any uncovered JD technical keywords
        all_uncovered_jd = [t for t in jd_keywords if t not in covered]
        if all_uncovered_jd:
            return all_uncovered_jd[0]

        # Priority 3: Cycle back to covered topics for deeper exploration
        if covered:
            # Pick a topic from covered that is NOT the current topic
            other_topics = [t for t in covered if t != context.current_topic.lower()]
            if other_topics:
                return other_topics[0]
            return covered[0]

        return None

    # --- Role taxonomy and guards ---
    def _extract_job_role(self, job_title: str, jd_keywords: List[str]) -> str:
        title = (job_title or "").lower()
        blob = " ".join(jd_keywords or []).lower()
        def has(*words):
            return any(w in title or w in blob for w in words)
        if has("data analyst", "data analysis"):
            return "data_analyst"
        if has("business analyst", "business analysis", "ba"):
            return "business_analyst"
        if has("devops", "site reliability", "sre", "platform engineer"):
            return "devops_engineer"
        if has("full stack", "fullstack"):
            return "full_stack_developer"
        if has("data scientist", "machine learning", "ml engineer", "ai engineer", "ai/ml"):
            return "data_scientist"
        if has("product engineer"):
            return "product_engineer"
        return "software_engineer"

    def _role_topic_whitelist(self, job_role: str) -> List[str]:
        role = (job_role or "software_engineer").lower()
        mapping = {
            "data_analyst": [
                "sql", "excel", "power bi", "tableau", "dashboard", "kpi", "report", "metric", "analysis", "data", "python", "pandas",
                "visualization", "statistics", "cleaning", "modeling", "etl"
            ],
            "business_analyst": [
                "requirement", "sql", "excel", "power bi", "tableau", "dashboard", "kpi",
                "stakeholder", "user story", "process", "metric", "report", "visualization", "business", "analysis",
                "documentation", "agile", "workflow", "modeling"
            ],
            "devops_engineer": [
                "ci", "cd", "pipeline", "docker", "kubernetes", "helm", "terraform", "ansible",
                "aws", "gcp", "azure", "monitor", "logging", "prometheus", "grafana", "deployment", "scaling", "load balancer",
                "linux", "bash", "security", "infrastructure", "yaml", "git"
            ],
            "full_stack_developer": [
                "react", "angular", "vue", "node", "express", "django", "flask", "rest", "graphql",
                "authentication", "authorization", "jwt", "database", "sql", "mongodb", "postgres", "redis",
                "state", "redux", "routing", "css", "html", "javascript", "typescript", "api", "testing"
            ],
            "data_scientist": [
                "python", "pandas", "numpy", "stat", "model", "training", "evaluation", "regression", "classification",
                "clustering", "nlp", "vision", "feature", "machine learning", "deep", "time series", "recommend",
                "scikit-learn", "tensorflow", "pytorch", "keras", "sql", "jupyter"
            ],
            "product_manager": [
                "product strategy", "roadmap", "user research", "stakeholder", "prioritization", "metrics", "kpi",
                "user story", "feature", "mvp", "agile", "scrum", "backlog", "sprint", "user experience", "ux",
                "market research", "competitive analysis", "data-driven", "a/b test", "analytics", "product launch",
                "go-to-market", "gtm", "user feedback", "customer", "business case", "roi", "okr", "requirement",
                "product vision", "product-market fit", "customer journey", "persona", "wireframe", "prototype"
            ],
            "product_engineer": [
                "feature", "requirements", "api", "performance", "scalability", "product", "ab test", "metric", "user",
                "system design", "frontend", "backend", "full stack"
            ],
            "software_engineer": [
                "algorithm", "data structure", "system design", "api", "database", "cache", "concurrency", "testing",
                "oop", "solid", "design patterns", "architecture", "refactoring", "performance", "scalability"
            ],
        }
        return mapping.get(role, mapping["software_engineer"])  # default generic

    def _filter_keywords_by_role(self, keywords: List[str], job_role: str) -> List[str]:
        if not keywords:
            return keywords
        allow = self._role_topic_whitelist(job_role)
        filtered = [kw for kw in keywords if self._is_topic_on_role(kw, job_role)]
        return filtered or keywords  # don't empty out; fall back to original if filtering removes all

    def _is_topic_on_role(self, topic: str, job_role: str) -> bool:
        t = (topic or "").lower()
        allow = self._role_topic_whitelist(job_role)
        return any(a in t for a in allow)

    def _role_matches(self, item_role: str, job_role: str) -> bool:
        r = (item_role or "").lower()
        jr = (job_role or "").lower()
        # Map common bank role labels to canonical roles
        if r in {"", "general"}:
            return True
        if "product manager" in r or "product owner" in r or "product lead" in r or "pm" in r:
            return jr == "product_manager"
        if "ai/ml" in r or "ml" in r or "ai" in r:
            return jr in {"data_scientist", "software_engineer"}  # allow DS or general SE
        if "devops" in r or "sre" in r or "platform" in r:
            return jr == "devops_engineer"
        if "full stack" in r or "fullstack" in r:
            return jr == "full_stack_developer"
        if "business analyst" in r:
            return jr == "business_analyst"
        if "product" in r and "engineer" in r:
            return jr == "product_engineer"
        if "software" in r and "engineer" in r:
            return jr in {"software_engineer", "full_stack_developer"}
        return True

    def _is_on_role_question(self, question: str, job_role: str, jd_keywords: List[str]) -> bool:
        q = (question or "").lower()
        # Signal if the question mentions any JD terms (strong positive)
        if any((kw or "").lower() in q for kw in (jd_keywords or []) if kw):
            return True
        # Positive: any allowlist term present
        if self._is_topic_on_role(q, job_role):
            return True
        # Negative signals by role (high-confidence off-role triggers)
        banned = {
            "business_analyst": ["q-learning", "gnn", "cnn", "transformer", "stripe", "api rate limiting", "distributed system"],
            "devops_engineer": [
                "q-learning", "gnn", "cnn", "bert", "quantization", "distillation",
                "model size", "model compression", "pruning", "tensor", "neural network"
            ],
            "full_stack_developer": ["q-learning", "gnn", "cnn", "bert", "quantization"],
            "data_scientist": ["stripe", "jwt auth", "dockerfile best practices"],
            "product_manager": [
                "api rate limiting", "distributed system", "authentication", "sql query", "database optimization",
                "go language", "r programming", "kubernetes", "docker", "microservices", "rest api implementation",
                "graphql implementation", "jwt token", "oauth", "redis cache", "mongodb schema", "nosql optimization",
                "algorithm complexity", "data structure implementation", "binary tree", "linked list", "heap",
                "q-learning", "gnn", "cnn", "bert", "transformer", "neural network", "deep learning", "nlp model",
                "stripe integration", "payment gateway", "webhook", "cipher", "encryption algorithm"
            ],
            "product_engineer": ["q-learning", "gnn", "cnn", "compensation package", "api rate limiting", "distributed system"],
            "software_engineer": [],
        }
        for term in banned.get((job_role or "software_engineer").lower(), []):
            if term in q:
                return False
        # Default: no positive signal and no banned-term hit — accept rather than
        # reject, since rejecting here silently discards a perfectly valid LLM
        # question in favor of a canned fallback (see _generate_technical_question).
        return True

    def _fallback_technical_question_with_context(
        self, context: ConversationContext, last_answer: str = "", score: float = 0.5
    ) -> str:
        """Fallback method that includes contextual acknowledgment and variant selection."""
        # Record fallback usage and possibly switch topic for variety
        self._record_fallback_and_maybe_switch_topic(context)
        # Choose a non-repeated variant for the (possibly updated) topic
        variants = [v.format(topic=context.current_topic) for v in self.tech_fallback_variants]
        base_question = self._choose_non_repeated_variant(variants, context) or (
            f"Can you tell me about your experience with {context.current_topic} and how you've applied it in your projects?"
        )

        if last_answer:
            if score < 0.4:
                acknowledgment = "I appreciate you working through that. Let me ask about something else - "
            elif score < 0.7:
                acknowledgment = "That's helpful context. Now, "
            else:
                acknowledgment = "Great insights! Building on that, "
            self.last_question_source = "fallback"
            return f"{acknowledgment}{base_question[0].lower() + base_question[1:]}"
        self.last_question_source = "fallback"
        return base_question

    def _get_question_from_bank(self, context: ConversationContext, topic: str, difficulty: str) -> Optional[str]:
        bank = self.question_bank
        if not bank or not self.question_embeddings:
            return None
        
        # Technical questions are STRICTLY JD-driven. Ignore CV keywords for bank matching.
        jd = ", ".join(context.jd_keywords or [])
        base_ctx = f"{topic} {difficulty} {context.job_title or ''} {context.job_role or ''}"
        
        if jd:
            query_embedding = self._get_embedding(f"{base_ctx} {jd}")
        else:
            query_embedding = self._get_embedding(base_ctx)
            
        norm = float(np.linalg.norm(query_embedding))
        if norm > 0.0:
            query_embedding = query_embedding / norm
            
        similarities: List[Tuple[float, int]] = []
        # Strictly use JD keywords for allowed topics in technical round
        allowed_topics = [t.lower() for t in (context.jd_keywords or []) if t]
        
        for i, emb_data in enumerate(self.question_embeddings):
            similarity = float(np.dot(query_embedding, emb_data["embedding"]))
            similarities.append((similarity, i))
            
        similarities.sort(reverse=True)
        
        primary: List[Tuple[float, Dict[str, Any]]] = []
        for sim, idx in similarities[:15]:
            item_idx = self.question_embeddings[idx].get("index", idx)
            item = bank[item_idx] if isinstance(bank, list) else bank.get("questions", [])[item_idx]
            
            if (item.get("difficulty", "") or "").lower() != (difficulty or "").lower():
                continue
                
            qtext = item.get("question", "")
            itopic = (item.get("topic", "") or "").lower()
            irole = (item.get("role", "") or "").lower()
            
            # Check if topic is relevant to JD or the identified role
            topic_match = False
            if allowed_topics:
                if any(at in itopic or itopic in at for at in allowed_topics):
                    topic_match = True
            
            if topic_match and not self._is_near_duplicate(context, qtext) and self._role_matches(irole, context.job_role) and self._is_topic_on_role(itopic, context.job_role):
                primary.append((sim, item))
                
        if primary:
            primary.sort(reverse=True, key=lambda x: x[0])
            return primary[0][1].get("question")
            
        return None

    def user_requested_repeat(self, last_answer: Optional[str]) -> bool:
        """Public entry point for session_manager to check repeat-intent
        *before* treating the candidate's message as a scored answer."""
        return self._user_indicates_repetition(last_answer)

    def _user_indicates_repetition(self, last_answer: Optional[str]) -> bool:
        if not last_answer:
            return False
        la = (last_answer or "").lower()
        # Heuristics: look for 'already' OR 'again/same/repeat' with any verb about answering
        core_flags = ["same question", "asked before", "repeat", "repeated", "again"]
        if any(flag in la for flag in core_flags):
            return True
        if "already" in la:
            verbs = [
                "answer", "answ", "ask", "asked", "said", "told", "explain", "explained", "mention", "mentioned",
                "cover", "covered", "discuss", "discussed", "insert"  # handle typo: "insert" seen in transcripts
            ]
            if any(v in la for v in verbs):
                return True
        return False

    def _normalize_question(self, q: str) -> str:
        return re.sub(r"\s+", " ", (q or "").strip().lower())

    def _tokenize_for_similarity(self, q: str) -> List[str]:
        text = self._normalize_question(q)
        # Basic stopwords to reduce false positives
        stop = {
            "the","a","an","and","or","of","to","in","on","for","with","about","your","you",
            "can","could","would","please","tell","me","walk","through","how","do","does","did",
            "this","that","it","is","are","was","were","be","being","been","as","at","from"
        }
        tokens = re.findall(r"[a-z0-9]+", text)
        return [t for t in tokens if t not in stop and len(t) > 2]

    def _jaccard_similarity(self, a: List[str], b: List[str]) -> float:
        sa, sb = set(a), set(b)
        if not sa or not sb:
            return 0.0
        inter = len(sa & sb)
        union = len(sa | sb)
        return inter / union if union else 0.0

    def _is_near_duplicate(self, context: ConversationContext, question: str, threshold: float = 0.35) -> bool:
        """Check if question is too similar to previously asked questions.
        
        Args:
            context: Conversation context with asked questions
            question: New question to check
            threshold: Jaccard similarity threshold (further lowered to 0.35 for stricter detection)
            
        Returns:
            True if question is a near-duplicate, False otherwise
        """
        cand_tokens = self._tokenize_for_similarity(question)
        if not cand_tokens:
            return False
            
        for prev in (context.asked_questions or []):
            prev_tokens = self._tokenize_for_similarity(prev)
            similarity = self._jaccard_similarity(cand_tokens, prev_tokens)
            if similarity >= threshold:
                # Log duplicate detection for debugging
                try:
                    logger.debug(f"Duplicate detected: similarity={similarity:.2f}, new='{question[:50]}...', prev='{prev[:50]}...'")
                except Exception:
                    pass
                return True
        return False

    def _max_prev_similarity(self, context: ConversationContext, question: str) -> float:
        cand_tokens = self._tokenize_for_similarity(question)
        best = 0.0
        for prev in (context.asked_questions or []):
            prev_tokens = self._tokenize_for_similarity(prev)
            sim = self._jaccard_similarity(cand_tokens, prev_tokens)
            if sim > best:
                best = sim
        return best

    def _make_alternative_if_duplicate(self, context: ConversationContext, question: str) -> str:
        norm = self._normalize_question(question)
        if norm not in (context.asked_questions or []) and not self._is_near_duplicate(context, question):
            return question
        # Treat duplicates like fallbacks so we encourage variety and topic rotation
        try:
            logger.info("dedup_triggered phase=%s topic=%s sim=%.2f q='%s'", context.interview_phase.value, context.current_topic, self._max_prev_similarity(context, question), question)
        except Exception:
            pass
        self._record_fallback_and_maybe_switch_topic(context)
        self.last_question_source = "fallback"
        if context.interview_phase == InterviewPhase.EXPERIENTIAL_QUESTIONS:
            return self._choose_non_repeated_variant(self.exp_fallback_variants, context) or (
                "Thanks. Could you walk me through a different project from your CV, focusing on goals, your responsibilities, tech stack, challenges, and outcomes?"
            )
        if context.interview_phase == InterviewPhase.HR_QUESTIONS:
            return self._choose_non_repeated_variant(self.hr_fallback_variants, context) or (
                "What other aspects of this role excite you, and how do your skills align with them?"
            )
        # Technical or other phases
        tech_variants = [v.format(topic=context.current_topic) for v in self.tech_fallback_variants]
        return self._choose_non_repeated_variant(tech_variants, context) or (
            f"Can you discuss another area of {context.current_topic} you've worked on and how you applied it in your projects?"
        )

    def _choose_non_repeated_variant(self, variants: List[str], context: ConversationContext) -> str:
        for v in variants:
            if (
                self._normalize_question(v) not in (context.asked_questions or [])
                and not self._is_near_duplicate(context, v)
            ):
                return v
        return variants[0] if variants else ""

    def _record_fallback_and_maybe_switch_topic(self, context: ConversationContext) -> None:
        """Force a topic switch if LLM fails or generates a duplicate twice."""
        topic = context.current_topic
        count = (context.fallback_usage_by_topic.get(topic, 0) or 0) + 1
        context.fallback_usage_by_topic[topic] = count
        
        # Aggressive switch: if we hit fallback even once, try rotating topic 
        # to keep the conversation fresh and avoid sounding repeated
        if count >= 1:
            next_topic = self._get_next_topic(context)
            if next_topic:
                context.current_topic = next_topic
                context.fallback_usage_by_topic[next_topic] = 0
                context.questions_on_current_topic = 0

    def _load_hr_question_banks(self) -> None:
        """Load HR question banks by seniority and create embeddings."""
        try:
            # Use relative path from the current file location
            current_dir = os.path.dirname(os.path.abspath(__file__))
            base_dir = os.path.join(current_dir, "..", "..", "question_bank", "hr_question_banks")
            file_map = {
                "fresher": "hr_interview_questions_fresher.json",
                "intermediate": "hr_interview_questions_intermediate.json",
                "senior": "hr_interview_questions_senior.json",
            }
            for level, fname in file_map.items():
                path = os.path.join(base_dir, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        # Expect a list of {question, seniority_level, question_type}
                        self.hr_question_banks[level] = data if isinstance(data, list) else []
                        # Build embeddings
                        emb_list: List[Dict[str, Any]] = []
                        for idx, item in enumerate(self.hr_question_banks[level]):
                            qtype = item.get("question_type", "").lower()
                            qtext = item.get("question", "")
                            combined = f"{qtype} {qtext}"
                            emb_list.append({
                                "embedding": self._get_embedding(combined),
                                "index": idx,
                                "type": qtype,
                            })
                        self.hr_question_embeddings[level] = emb_list
                except Exception:
                    self.hr_question_banks[level] = []
                    self.hr_question_embeddings[level] = []
        except Exception:
            # If loading fails globally, ensure empty structures
            self.hr_question_banks = {"fresher": [], "intermediate": [], "senior": []}
            self.hr_question_embeddings = {"fresher": [], "intermediate": [], "senior": []}

    def _is_hr_question_applicable(self, item: Dict[str, Any], context: ConversationContext) -> bool:
        """Basic applicability check using CV/job context and question content."""
        qtype = item.get("question_type", "").lower()
        qtext = item.get("question", "").lower()
        cv_blob = " ".join([
            context.job_title or "",
            " ".join(context.cv_keywords or []),
            " ".join(context.cv_experiences or []),
            " ".join(context.cv_projects or []),
        ]).lower()

        # Avoid compensation/executive package questions for junior candidates
        if (context.candidate_skill_level or "").lower() in {"beginner", "intermediate"}:
            banned_terms = ["executive", "compensation", "package", "salary history"]
            if any(bt in qtext for bt in banned_terms):
                return False

        # Always-applicable types
        always_ok = {"communication", "culture", "culture_fit", "career", "motivation", "strengths", "weaknesses"}
        if qtype in always_ok:
            return True

        # Trigger heuristics for applicability
        triggers: Dict[str, List[str]] = {
            "leadership": ["lead", "led", "managed", "team", "mentor"],
            "teamwork": ["team", "collaborat", "scrum", "agile", "pair"],
            "conflict": ["stakeholder", "client", "team", "conflict", "disagree"],
            "deadline": ["deadline", "deliver", "timeline", "sprint", "release"],
            "remote": ["remote", "distributed", "timezone"],
            "adaptability": ["learn", "new", "change", "pivot", "adap"],
            "problem_solving": ["problem", "issue", "debug", "fix", "root cause"],
        }
        # If type has specific triggers, check presence in CV blob or question text keywords
        for key, words in triggers.items():
            if qtype.startswith(key):
                if any(w in cv_blob for w in words) or any(w in qtext for w in words):
                    return True
                return False

        # Default to semantic similarity gate; if high enough, allow
        query_embedding = self._get_embedding(cv_blob)
        item_embedding = self._get_embedding(qtext)
        sim = float(np.dot(query_embedding, item_embedding))
        return sim >= 0.1

    def _get_hr_question_from_bank(self, context: ConversationContext) -> Optional[str]:
        """Pick an applicable HR question deterministically via semantic match (no random)."""
        level_map = {
            "beginner": "fresher",
            "intermediate": "intermediate",
            "expert": "senior",
        }
        level = level_map.get((context.candidate_skill_level or "intermediate").lower(), "intermediate")
        bank = self.hr_question_banks.get(level, [])
        emb_list = self.hr_question_embeddings.get(level, [])
        if not bank or not emb_list:
            return None

        # Build query from CV/job and last concepts
        context_text = " ".join([
            context.job_title or "",
            ", ".join(context.cv_keywords or []),
            " ".join(context.cv_experiences or []),
            " ".join(context.cv_projects or []),
            ", ".join(context.last_mentioned_concepts or []),
        ])
        q_emb = self._get_embedding(context_text)

        # Score by cosine similarity
        scored: List[Tuple[float, int]] = []
        for i, ed in enumerate(emb_list):
            sim = float(np.dot(q_emb, ed["embedding"]))
            scored.append((sim, i))
        scored.sort(reverse=True)

        # Iterate best to worst and choose first applicable and non-repeated type
        for sim, i in scored:
            item = bank[emb_list[i]["index"]]
            qtype = (item.get("question_type", "") or "").lower()
            if qtype in (context.hr_question_types_asked or []):
                continue
            if sim < 0.1:
                # Too low similarity, likely not applicable
                continue
            if not self._is_hr_question_applicable(item, context):
                continue
            # Mark type asked to avoid repetition and return question
            context.hr_question_types_asked.append(qtype)
            return item.get("question", None)
        return None

    def _generate_hr_question(
        self,
        context: ConversationContext,
        last_answer: Optional[str] = None,
        answer_evaluation: Optional[Dict] = None,
    ) -> str:
        """Generate HR question using LLM first, then bank as fallback."""
        # Build previous-answer context for HR prompt
        prev_ctx = ""
        if last_answer and answer_evaluation:
            score = answer_evaluation.get("relevance_score", 0.5)
            concepts_mentioned = self._extract_concepts_from_answer(last_answer)
            prev_ctx = HR_PREVIOUS_ANSWER_CONTEXT.format(
                last_answer_preview=last_answer[:200],
                concepts_mentioned=", ".join(concepts_mentioned[:3]) if concepts_mentioned else "the topics discussed",
                score=score,
            )

        # Map skill to human-readable experience level for prompt
        skill = (context.candidate_skill_level or "intermediate").lower()
        exp_map = {"beginner": "Fresher", "intermediate": "Intermediate", "expert": "Senior"}
        exp_level = exp_map.get(skill, "Intermediate")
        topics_covered_str = ", ".join(context.topics_covered or []) or "—"

        # STEP 1: Try to generate HR question using LLM FIRST (primary method)
        prompt = HR_QUESTION_PROMPT.format(
            job_title=context.job_title,
            jd_keywords=", ".join(context.jd_keywords or []) if context.jd_keywords else "N/A",
            candidate_name=context.candidate_name,
            experience_level=exp_level,
            topics_covered=topics_covered_str,
        )
        try:
            response = self._complete_llm(prompt)
            if response and hasattr(response, "text"):
                candidate = response.text.strip()
                # Validate: check if question is appropriate and not duplicate
                if candidate and len(candidate) > 10:
                    # Gate: avoid compensation/executive questions for junior candidates
                    banned_terms = ["executive", "compensation", "package", "salary history"]
                    is_junior = (context.candidate_skill_level or "").lower() in {"beginner", "intermediate"}
                    if not (is_junior and any(bt in candidate.lower() for bt in banned_terms)) and not self._is_near_duplicate(context, candidate):
                        self.last_question_source = "prompt"
                        return candidate
        except Exception:
            # LLM generation failed, continue to fallback
            pass
        
        # STEP 2: If LLM fails or generates invalid question, try question bank as fallback
        bank_q = self._get_hr_question_from_bank(context)
        if bank_q:
            self.last_question_source = "bank"
            return bank_q
        
        # STEP 3: If both LLM and bank fail, use hardcoded fallback
        self._record_fallback_and_maybe_switch_topic(context)
        self.last_question_source = "fallback"
        return self._choose_non_repeated_variant(self.hr_fallback_variants, context) or FALLBACK_HR_QUESTION

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
            # Switch to HR/behavioural questions for the last 2 slots of a 10-question interview.
            # context.question_count == 7 at start of Q9 generation (0-indexed from first dynamic Q).
            if context.question_count >= 7:
                context.interview_phase = InterviewPhase.HR_QUESTIONS
                question = self._generate_hr_question(
                    context, last_answer, answer_evaluation
                )
            else:
                question = self._generate_technical_question(
                    context, last_answer, answer_evaluation
                )

        elif context.interview_phase == InterviewPhase.HR_QUESTIONS:
            question = self._generate_hr_question(
                context, last_answer, answer_evaluation
            )
            context.hr_questions_asked += 1
            # In a 10-question interview only 2 HR slots are available; keep limit high
            # so the session manager (max_questions) terminates naturally.
            if context.hr_questions_asked >= 5:
                context.interview_phase = InterviewPhase.CLOSING

        elif context.interview_phase == InterviewPhase.CLOSING:
            question = "Thank you for your time. The interview is now complete."

        else:
            question = self._generate_technical_question(
                context, last_answer, answer_evaluation
            )

        # Avoid repeating previously asked questions
        question = self._make_alternative_if_duplicate(context, question)

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
        elif context.interview_phase == InterviewPhase.HR_QUESTIONS:
            question_type = QuestionType.BEHAVIORAL
            intent = QuestionIntent.ASSESS_EXPERIENCE
        else:
            question_type = QuestionType.TECHNICAL
            intent = QuestionIntent.PROBE_DEEPER
        
        difficulty_for_metadata = (
            self._select_question_difficulty(context)
            if context.interview_phase == InterviewPhase.TECHNICAL_QUESTIONS
            else context.candidate_skill_level
        )


        metadata = QuestionMetadata(
            question_type=question_type,
            intent=intent,
            difficulty_level=difficulty_for_metadata,
            expected_depth=context.depth_level,
            topic_area=context.current_topic,
            prerequisites=[],
            interview_phase=context.interview_phase,
            source=self.last_question_source,
        )

        # Track asked question to prevent repeats
        try:
            context.asked_questions.append(self._normalize_question(question))
        except Exception:
            pass
        context.question_count += 1
        try:
            logger.info(
                "question_source=%s phase=%s topic=%s",
                self.last_question_source,
                context.interview_phase.value,
                context.current_topic,
            )
        except Exception:
            pass
        return question, metadata

    def _generate_closing(self, context: ConversationContext) -> str:
        """Generate closing using the prompt template."""
        positive_aspect = (
            context.cv_keywords[0] if context.cv_keywords else "technical knowledge"
        )

        prompt = CLOSING_PROMPT.format(
            candidate_name=context.candidate_name, positive_aspect=positive_aspect
        )

        try:
            response = self._complete_llm(prompt)
            if response and hasattr(response, "text"):
                self.last_question_source = "prompt"
                return response.text.strip()
            self.last_question_source = "fallback"
            return self._fallback_closing(context)
        except Exception:
            self.last_question_source = "fallback"
            return self._fallback_closing(context)

    # Helper methods for extraction and fallbacks

    def _extract_cv_keywords(self, cv_content: str, jd_content: str) -> List[str]:
        """Extract technical keywords from CV and JD content using LLM (JD-weighted)."""
        if not (cv_content.strip() or jd_content.strip()):
            return ["General Programming"]

        prompt = CV_KEYWORDS_EXTRACTION_PROMPT.format(cv_content=cv_content, jd_content=jd_content)

        try:
            response = self._complete_llm(prompt)
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
            response = self._complete_llm(prompt)
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
        return FALLBACK_GREETING.format(
            candidate_name=context.candidate_name
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

    def _extract_jd_keywords(self, jd_content: str) -> List[str]:
        """Extract technical keywords from JD content using LLM."""
        if not jd_content.strip():
            return ["General Programming"]

        prompt = JD_KEYWORDS_EXTRACTION_PROMPT.format(jd_content=jd_content)

        try:
            response = self._complete_llm(prompt)
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
                    else self._fallback_extract_cv_keywords("", jd_content)
                )
            else:
                return self._fallback_extract_cv_keywords("", jd_content)

        except Exception as e:
            print(f"Error extracting JD keywords with LLM: {e}")
            return self._fallback_extract_cv_keywords("", jd_content)

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
            response = self._complete_llm(STRUCTURE_EXPLANATION_PROMPT)
            if response and hasattr(response, "text"):
                self.last_question_source = "prompt"
                return response.text.strip()
            self.last_question_source = "fallback"
            return FALLBACK_STRUCTURE_EXPLANATION
        except Exception:
            self.last_question_source = "fallback"
            return FALLBACK_STRUCTURE_EXPLANATION

    def _generate_experiential_question(
        self,
        context: ConversationContext,
        last_answer: Optional[str] = None,
        answer_evaluation: Optional[Dict] = None,
    ) -> str:
        """Generate an experiential question based on CV experiences and projects using LLM first."""
        
        # Track asked experiences to avoid repetition
        asked_items = set()
        for prev in context.asked_questions:
            for item in (context.cv_experiences or []) + (context.cv_projects or []):
                # Basic fuzzy check to see if an experience was already discussed
                if item.lower()[:30] in prev.lower():
                    asked_items.add(item)
        
        # Filter down to unasked experiences/projects for the prompt to force variety
        unasked_exp = [e for e in (context.cv_experiences or []) if e not in asked_items]
        unasked_proj = [p for p in (context.cv_projects or []) if p not in asked_items]
        
        # If we've run out of unasked items, recycle but prefer least recently used
        display_exp = unasked_exp if unasked_exp else context.cv_experiences
        display_proj = unasked_proj if unasked_proj else context.cv_projects

        experiences_str = "\n".join(display_exp[:5]) # Show subset to force focus
        projects_str = "\n".join(display_proj[:5])
        topics_covered_str = ", ".join(context.topics_covered or []) or "none"

        # STEP 1: Try to generate experiential question using LLM FIRST (primary method)
        prompt = EXPERIENTIAL_QUESTION_PROMPT.format(
            candidate_name=context.candidate_name,
            job_title=context.job_title,
            jd_keywords=", ".join(context.jd_keywords or []) if context.jd_keywords else "N/A",
            cv_experiences=experiences_str,
            cv_projects=projects_str,
            topics_covered=topics_covered_str,
        )

        try:
            response = self._complete_llm(prompt)
            if response and hasattr(response, "text"):
                question = response.text.strip()
                # Validate: check if question is not duplicate and has sufficient content
                if question and len(question) > 10 and not self._is_near_duplicate(context, question):
                    self.last_question_source = "prompt"
                    return question
        except Exception:
            # LLM generation failed, continue to fallback
            pass
        
        # STEP 2: If LLM fails or generates invalid question, use hardcoded fallback
        self._record_fallback_and_maybe_switch_topic(context)
        self.last_question_source = "fallback"
        return self._choose_non_repeated_variant(self.exp_fallback_variants, context) or FALLBACK_EXPERIENTIAL_QUESTION

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

    def _classify_role_difficulty(self, job_description: str) -> str:
        """Classify role difficulty from JD content: easy|medium|hard."""
        jd = (job_description or "").lower()
        # Heuristics for difficulty classification
        easy_markers = ["junior", "entry-level", "intern", "0-1 years", "1+ years"]
        hard_markers = [
            "senior", "principal", "staff", "architect", "lead",
            "distributed systems", "scalability", "kubernetes", "microservices",
            "system design", "aws", "azure", "gcp", "security", "performance",
            "10+ years", "8+ years"
        ]
        medium_markers = ["mid-level", "3+ years", "4+ years", "5+ years", "ownership", "mentorship"]

        score_easy = sum(1 for m in easy_markers if m in jd)
        score_hard = sum(1 for m in hard_markers if m in jd)
        score_medium = sum(1 for m in medium_markers if m in jd)

        if score_hard >= max(score_medium, score_easy) and score_hard > 0:
            return "hard"
        if score_easy > score_medium:
            return "easy"
        return "medium"

    def _analyze_jd_difficulty_distribution(self, job_description: str) -> Dict[str, float]:
        """Analyze JD and return difficulty distribution using LLM."""
        if not job_description.strip():
            return {"easy": 0.3, "medium": 0.4, "hard": 0.3}

        prompt = JD_DIFFICULTY_DISTRIBUTION_PROMPT.format(jd_content=job_description)

        try:
            response = self._complete_llm(prompt)
            if response and hasattr(response, "text"):
                res_text = response.text.strip()
                # Find JSON block
                match = re.search(r"\{.*\}", res_text, re.DOTALL)
                if match:
                    dist = json.loads(match.group(0))
                    # Validate distribution
                    easy = float(dist.get("easy", 0))
                    medium = float(dist.get("medium", 0))
                    hard = float(dist.get("hard", 0))
                    total = easy + medium + hard
                    if total > 0:
                        return {
                            "easy": easy / total,
                            "medium": medium / total,
                            "hard": hard / total
                        }
            
            # Fallback based on role_difficulty if LLM fails
            role_diff = self._classify_role_difficulty(job_description)
            if role_diff == "easy":
                return {"easy": 0.6, "medium": 0.3, "hard": 0.1}
            elif role_diff == "hard":
                return {"easy": 0.1, "medium": 0.3, "hard": 0.6}
            else:
                return {"easy": 0.3, "medium": 0.4, "hard": 0.3}
                
        except Exception as e:
            logger.error(f"Error analyzing JD difficulty distribution: {e}")
            return {"easy": 0.3, "medium": 0.4, "hard": 0.3}
