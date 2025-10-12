"""
Role-based question generator that uses question banks for specific roles.
Falls back to LLM-generated questions when no question bank is available.
Uses role-specific prompts for more relevant questions and greetings.
"""

import os
import pandas as pd
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
import random

from .prompt_based_question_generator import (
    PromptBasedQuestionGenerator,
    ConversationContext,
    InterviewPhase,
    QuestionMetadata,
    QuestionIntent
)
from ..config.settings import QuestionType
from ..prompts.role_specific_prompts import (
    ROLE_GREETING_PROMPTS,
    ROLE_FALLBACK_GREETINGS,
    ROLE_TECHNICAL_QUESTION_PROMPTS,
    ROLE_FALLBACK_TECHNICAL_QUESTIONS,
    ROLE_KEYWORDS,
    ROLE_SPECIFIC_TOPICS
)


class Role(Enum):
    """Available roles for interviews."""
    FINANCE = "Finance"
    SOFTWARE_DEVELOPMENT = "Software Development"
    AI = "AI"
    DATA_ANALYST = "Data Analyst"


class RoleBasedQuestionGenerator(PromptBasedQuestionGenerator):
    """
    Question generator that uses role-specific question banks when available.
    Falls back to prompt-based generation when no question bank is available.
    """

    def __init__(self, llm, question_bank_dir=None):
        super().__init__(llm)
        self.role = None
        self.question_bank = None
        self.question_bank_dir = question_bank_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "question_bank"
        )
        self.available_roles = self._get_available_roles()
        self.using_question_bank = False
        
    def _get_next_topic(self, context: ConversationContext) -> Optional[str]:
        """
        Get the next topic to explore based on role-specific topics if available,
        otherwise fall back to CV keywords.
        """
        # If we have a role, use role-specific topics
        if self.role:
            role_topics = ROLE_SPECIFIC_TOPICS.get(self.role.name, [])
            
            if role_topics:
                # Filter out topics already covered
                uncovered_topics = [
                    topic for topic in role_topics if topic not in context.topics_covered
                ]
                
                # If we have uncovered role-specific topics, use one
                if uncovered_topics:
                    return uncovered_topics[0]
                
                # If all role topics covered, cycle back through them
                if role_topics:
                    return role_topics[context.question_count % len(role_topics)]
        
        # Fall back to parent class implementation if no role-specific topics
        uncovered_topics = [
            topic for topic in context.cv_keywords if topic not in context.topics_covered
        ]

        if uncovered_topics:
            return uncovered_topics[0]

        # If all CV topics covered, cycle back to previous topics for deeper exploration
        if context.topics_covered:
            return context.topics_covered[
                context.question_count % len(context.topics_covered)
            ]

        return None

    def _get_available_roles(self) -> Dict[Role, bool]:
        """
        Check which roles have question banks available.
        Returns a dictionary mapping roles to availability.
        """
        available_roles = {}
        
        for role in Role:
            file_path = self._get_question_bank_path(role)
            available_roles[role] = os.path.exists(file_path)
            
        return available_roles

    def _get_question_bank_path(self, role: Role) -> str:
        """Get the file path for a role's question bank."""
        role_file_mapping = {
            Role.FINANCE: "FinanceConsulting_QuestionBank.csv",
            Role.SOFTWARE_DEVELOPMENT: "SoftwareDevelopment_QuestionBank.csv",
            Role.AI: "AI_QuestionBank.csv",
            Role.DATA_ANALYST: "DataAnalyst_QuestionBank.csv",
        }
        
        filename = role_file_mapping.get(role)
        if not filename:
            return None
            
        return os.path.join(self.question_bank_dir, filename)

    def _load_question_bank(self, role: Role) -> Optional[pd.DataFrame]:
        """Load the question bank for a specific role if available."""
        file_path = self._get_question_bank_path(role)
        
        if not file_path or not os.path.exists(file_path):
            return None
            
        try:
            return pd.read_csv(file_path)
        except Exception as e:
            print(f"Error loading question bank for {role.value}: {e}")
            return None

    def set_role(self, role: Role) -> bool:
        """
        Set the role for the interview and load the appropriate question bank.
        Returns True if a question bank was loaded, False otherwise.
        """
        self.role = role
        self.question_bank = self._load_question_bank(role)
        self.using_question_bank = self.question_bank is not None
        return self.using_question_bank

    def initialize_conversation(
        self, resume_sections: Dict[str, str], job_description: str = "", role: Role = None
    ) -> ConversationContext:
        """Initialize conversation context based on resume, job description, and role."""
        # Initialize with parent method
        context = super().initialize_conversation(resume_sections, job_description)
        
        # Set role if provided
        if role:
            self.set_role(role)
            
        # Update CV keywords to be role-specific if role is set
        if self.role and hasattr(context, 'cv_keywords'):
            role_keywords = ROLE_KEYWORDS.get(self.role.name, [])
            
            # Extract role-specific keywords from resume
            extracted_keywords = []
            for section in resume_sections.values():
                extracted_keywords.extend([kw for kw in role_keywords if kw.lower() in section.lower()])
            
            # Remove duplicates
            extracted_keywords = list(set(extracted_keywords))
            
            # If no role-specific keywords found, use some default ones for the role
            if not extracted_keywords and role_keywords:
                extracted_keywords = role_keywords[:3]  # Use first 3 default keywords
                
            # Update the context with role-specific keywords if we found any
            if extracted_keywords:
                context.cv_keywords = extracted_keywords
            
            # Set initial topic from role-specific topics
            role_topics = ROLE_SPECIFIC_TOPICS.get(self.role.name, [])
            if role_topics and hasattr(context, 'current_topic'):
                context.current_topic = role_topics[0]
        
        return context

    def _generate_greeting(self, context: ConversationContext) -> str:
        """Generate a role-specific greeting."""
        if self.role:
            # Get role-specific greeting prompt
            greeting_prompt = ROLE_GREETING_PROMPTS.get(self.role.name)
            fallback_greeting = ROLE_FALLBACK_GREETINGS.get(self.role.name)
            
            if greeting_prompt:
                # Format the greeting prompt with context variables
                formatted_prompt = greeting_prompt.format(
                    job_title=context.job_title,
                    candidate_name=context.candidate_name,
                    primary_technology=context.primary_technology if hasattr(context, 'primary_technology') else "",
                    cv_keywords=", ".join(context.cv_keywords[:3]) if context.cv_keywords else ""
                )
                
                try:
                    # Generate greeting using the role-specific prompt
                    greeting = self.llm.generate_text(formatted_prompt)
                    return greeting
                except Exception as e:
                    print(f"Error generating greeting: {e}")
                    
                    # Use fallback greeting if available
                    if fallback_greeting:
                        tech_mention = f" with {context.primary_technology}" if hasattr(context, 'primary_technology') and context.primary_technology else ""
                        return fallback_greeting.format(
                            candidate_name=context.candidate_name,
                            tech_mention=tech_mention
                        )
        
        # Fall back to parent method if no role-specific greeting is available
        return super()._generate_greeting(context)

    def _generate_technical_question(
        self,
        context: ConversationContext,
        last_answer: Optional[str] = None,
        answer_evaluation: Optional[Dict] = None,
    ) -> str:
        """
        Generate technical questions using the question bank if available,
        otherwise use role-specific prompts for generation.
        """
        # If we have a question bank and are using it, select a question from it
        if self.using_question_bank and self.question_bank is not None:
            # Get a random question from the question bank
            # Skip the first 20 questions which are typically general/behavioral questions
            technical_questions = self.question_bank.iloc[20:]
            
            if not technical_questions.empty:
                # Select a random question
                random_index = random.randint(0, len(technical_questions) - 1)
                question = technical_questions.iloc[random_index]["Interview Question"]
                
                # Update topics covered - but don't switch topics too frequently
                if context.current_topic not in context.topics_covered:
                    context.topics_covered.append(context.current_topic)
                    
                return question
        
        # If no question bank or it's empty, use role-specific prompts
        if self.role:
            # Get role-specific technical question prompt
            tech_prompt = ROLE_TECHNICAL_QUESTION_PROMPTS.get(self.role.name)
            fallback_question = ROLE_FALLBACK_TECHNICAL_QUESTIONS.get(self.role.name)
            
            if tech_prompt:
                # Save original prompts
                original_tech_prompt = self.technical_question_prompt
                original_fallback = self.fallback_technical_question
                
                # Set role-specific prompts
                self.technical_question_prompt = tech_prompt
                if fallback_question:
                    self.fallback_technical_question = fallback_question
                
                # Generate question using role-specific prompt
                question = super()._generate_technical_question(context, last_answer, answer_evaluation)
                
                # Restore original prompts
                self.technical_question_prompt = original_tech_prompt
                self.fallback_technical_question = original_fallback
                
                return question
        
        # Fall back to parent class's generation method if no role-specific prompt
        return super()._generate_technical_question(context, last_answer, answer_evaluation)

    def get_available_roles(self) -> List[str]:
        """Return a list of available role names."""
        return [role.value for role in Role]