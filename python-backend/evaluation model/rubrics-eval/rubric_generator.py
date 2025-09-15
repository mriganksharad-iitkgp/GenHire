"""Rubric generation module."""

import json
import re
from typing import List
from langchain_openai import ChatOpenAI
from .config import Config


class RubricGenerator:
    """Handles the generation of grading rubrics for questions."""

    def __init__(self):
        """Initialize the rubric generator.

        Uses API key from config/environment variables.
        """
        # Ensure config is loaded
        Config.load_from_environment()
        self.llm = ChatOpenAI(
            model=Config.RUBRIC_GENERATION_MODEL,
            api_key=Config.OPENAI_API_KEY,
            temperature=Config.RUBRIC_GENERATION_TEMPERATURE,
        )

    def generate_rubrics(self, question: str) -> List[str]:
        """Generate grading rubrics for a given question.

        Args:
            question: The question to generate rubrics for.

        Returns:
            List of rubric strings.
        """
        prompt = self._create_rubric_prompt(question)

        try:
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            return self._parse_rubrics_response(content)
        except Exception as e:
            print(f"An error occurred during rubric generation: {e}")
            return []

    def _create_rubric_prompt(self, question: str) -> str:
        """Create the prompt for rubric generation.

        Args:
            question: The question to create prompt for.

        Returns:
            The formatted prompt string.
        """
        return f"""
        You are an expert educator and curriculum designer specializing in creating precise, atomic, and objective grading rubrics.

        Your task is to generate a set of grading criteria (rubrics) for the following question.

        **Question:**
        "{question}"

        **Instructions for Rubric Creation:**
        1.  **Atomicity:** Each rubric item must be a distinct, single, verifiable point.
        2.  **Precision:** Rubrics must be based *only* on the information explicitly asked for in the question. Don't be creative in generating rubrics
        3.  **Format:** Respond with only a JSON-formatted list of strings. Do not include any other text, explanations, or markdown formatting.
        4. **IMP:** We assume that question is precise so that student doesn't need to imagine if he has to say anything extra like to give example or not etc.

        **Example:**
        - If the question is "Explain the difference between supervised and unsupervised learning.", your response must be:
        ["Defines supervised learning.", "Defines unsupervised learning.", "Establishes a clear difference between them."]
        """

    def _parse_rubrics_response(self, content: str) -> List[str]:
        """Parse the LLM response to extract rubrics.

        Args:
            content: Raw response content from LLM.

        Returns:
            List of rubric strings.
        """
        try:
            # Try direct JSON parsing first
            rubrics = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            match = re.search(r"\[.*\]", content, re.DOTALL)
            if match:
                json_string = match.group(0)
                try:
                    rubrics = json.loads(json_string)
                except json.JSONDecodeError:
                    raise ValueError("Could not parse JSON from the model's response.")
            else:
                raise ValueError(
                    "Could not find a valid JSON array in the model's response."
                )

        # Validate that we got a list of strings
        if isinstance(rubrics, list) and all(isinstance(item, str) for item in rubrics):
            return rubrics
        else:
            return []

    def generate_rubrics_batch(self, questions: List[str]) -> List[List[str]]:
        """Generate rubrics for multiple questions.

        Args:
            questions: List of questions to generate rubrics for.

        Returns:
            List of rubric lists, one for each question.
        """
        all_rubrics = []
        for question in questions:
            rubrics = self.generate_rubrics(question)
            all_rubrics.append(rubrics)
        return all_rubrics
