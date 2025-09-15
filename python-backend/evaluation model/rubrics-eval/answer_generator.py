"""Answer generation module for creating test answer spectrums."""

from typing import List, Tuple
from langchain_openai import ChatOpenAI
from .config import Config


class AnswerGenerator:
    """Handles the generation of answer spectrums for testing purposes."""

    def __init__(self):
        """Initialize the answer generator.

        Uses API key from config/environment variables.
        """
        # Ensure config is loaded
        Config.load_from_environment()
        self.llm = ChatOpenAI(
            model=Config.ANSWER_GENERATION_MODEL,
            api_key=Config.OPENAI_API_KEY,
            temperature=Config.ANSWER_GENERATION_TEMPERATURE,
        )

    def generate_balanced_spectrum(self, question: str) -> Tuple[List[str], List[str]]:
        """Generate a balanced spectrum of 6 answers with smooth quality degradation.

        Args:
            question: The question to generate answers for.

        Returns:
            Tuple of (titles, generated_answers).
        """
        print("=" * 80)
        print("Starting Balanced Answer Spectrum Generation")
        print(f'Question: "{question}"')
        print("=" * 80)

        generated_answers = []
        titles = []

        # Generate the perfect answer first
        initial_answer = self._generate_perfect_answer(question)
        if not initial_answer:
            return [], []

        generated_answers.append(initial_answer)
        titles.append("1. Perfect Answer (Target Score: 95-100)")

        # Generate degraded versions
        degradation_tasks = self._get_degradation_tasks()

        for task in degradation_tasks:
            print(f"Generating: {task['title']}")
            try:
                previous_answer = generated_answers[-1]
                degraded_answer = self._generate_degraded_answer(
                    question, previous_answer, task["instruction"]
                )
                generated_answers.append(degraded_answer)
                titles.append(task["title"])
            except Exception as e:
                error_message = (
                    f"ERROR: Could not generate answer for {task['title']}. Reason: {e}"
                )
                generated_answers.append(error_message)
                titles.append(task["title"])

        print("...Generation complete.")
        return titles, generated_answers

    def generate_sequential_relevance_spectrum(
        self, question: str
    ) -> Tuple[List[str], List[str]]:
        """Generate a sequential relevance spectrum where each answer is worse than the previous.

        Args:
            question: The question to generate answers for.

        Returns:
            Tuple of (titles, generated_answers).
        """
        print("=" * 80)
        print("Starting Sequential Answer Relevance Spectrum Generation")
        print(f'Question: "{question}"')
        print("=" * 80)

        generated_answers = []
        titles = []

        # Generate the perfectly relevant answer first
        initial_answer = self._generate_perfectly_relevant_answer(question)
        if not initial_answer:
            return [], []

        generated_answers.append(initial_answer)
        titles.append("1. Perfectly Relevant (The Expert)")

        # Generate sequentially degraded versions
        relevance_degradation_tasks = self._get_relevance_degradation_tasks()

        for task in relevance_degradation_tasks:
            print(f"Generating: {task['title']}")
            try:
                previous_answer = generated_answers[-1]
                degraded_answer = self._generate_degraded_answer(
                    question, previous_answer, task["instruction"]
                )
                generated_answers.append(degraded_answer)
                titles.append(task["title"])
            except Exception as e:
                error_message = (
                    f"ERROR: Could not generate answer for {task['title']}. Reason: {e}"
                )
                generated_answers.append(error_message)
                titles.append(task["title"])

        print("...Generation complete.")
        return titles, generated_answers

    def _generate_perfect_answer(self, question: str) -> str:
        """Generate a perfect answer for the given question."""
        prompt = f"""
        You are an expert job candidate in an interview. Provide a direct, correct, and concise answer to the following question. This is your best attempt. The answer should be a single, focused paragraph.

        Question: "{question}"
        """
        try:
            response = self.llm.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            print(f"Failed to generate the initial answer. Error: {e}")
            return ""

    def _generate_perfectly_relevant_answer(self, question: str) -> str:
        """Generate a perfectly relevant answer for the given question."""
        prompt = f"""
        You are an expert job candidate in an interview. Your task is to provide a direct, correct, and concise answer to the following question. This will be your first and best attempt. The answer should be a single, focused paragraph.

        Question: "{question}"
        """
        try:
            response = self.llm.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            print(f"Failed to generate the initial answer. Error: {e}")
            return ""

    def _generate_degraded_answer(
        self, question: str, previous_answer: str, instruction: str
    ) -> str:
        """Generate a degraded version of the previous answer."""
        revision_prompt = f"""
        You are an interview candidate revising your answers. Your goal is to make your previous answer worse according to a specific instruction to create a spectrum of quality.

        Original Question: "{question}"

        Your Previous Answer Was:
        "{previous_answer}"

        Your Revision Instruction: "{instruction}"

        Now, provide the revised answer as a single, spoken-style paragraph.
        """

        response = self.llm.invoke(revision_prompt)
        return response.content.strip()

    def _get_degradation_tasks(self) -> List[dict]:
        """Get the list of degradation tasks for balanced spectrum generation."""
        return [
            {
                "title": "2. Correct but Verbose (Target Score: 80-90)",
                "instruction": "Revise your previous answer. Keep the core explanation correct, but make it less concise by adding tangential, though still related, information. The answer should feel slightly unfocused.",
            },
            {
                "title": "3. Correct but Superficial (Target Score: 60-75)",
                "instruction": "Revise your previous answer to be much less detailed. Strip away the explanatory depth and nuance, leaving only a technically correct but superficial definition. It should sound like you memorized a single sentence without understanding the 'why'.",
            },
            {
                "title": "4. Relevant with a Key Factual Error (Target Score: 40-55)",
                "instruction": "Revise your previous answer to be on-topic but factually incorrect on a key point. For example, correctly define one term but misrepresent the purpose or function of the other. This demonstrates a specific misunderstanding.",
            },
            {
                "title": "5. Relevant but Confuses Core Concepts (Target Score: 20-35)",
                "instruction": "Revise your previous answer to demonstrate a fundamental confusion. The answer should still be about the right topic, but it must explicitly swap the core definitions or roles of the main concepts. For instance, define 'validation set' as the 'test set' and vice versa.",
            },
            {
                "title": "6. Irrelevant Question Dodge (Target Score: 5-15)",
                "instruction": "For your final revision, completely pivot away from answering the question. Acknowledge the keywords from the original question, but then confidently answer a different, higher-level question. Do not attempt to answer the original question anymore.",
            },
        ]

    def _get_relevance_degradation_tasks(self) -> List[dict]:
        """Get the list of relevance degradation tasks for sequential spectrum generation."""
        return [
            {
                "title": "2. Mostly Relevant (The Rambler)",
                "instruction": "Revise your previous answer to make it less relevant. First, repeat the core correct answer, but then add a significant amount of tangential, unasked-for information about a related topic. This should make the answer less focused.",
            },
            {
                "title": "3. Partially Relevant (The Sub-Part Answerer)",
                "instruction": "Revise your previous answer to make it even less relevant. Remove the rambling parts and the main point, and instead focus only on a specific, minor sub-part of the original question. Your answer should be correct for that small part, but very incomplete overall.",
            },
            {
                "title": "4. Low Relevance (The Question Dodger)",
                "instruction": "Revise your previous answer to be much less relevant. Acknowledge the keywords from the original question, but skillfully pivot to answering a different, related, higher-level question you are more comfortable with. Do not answer the original question at all.",
            },
            {
                "title": "5. Very Low Relevance (The Keyword Recognizer)",
                "instruction": "Revise your previous answer to be almost completely irrelevant. It should use one or two keywords from the original question but be about an entirely different concept within the same general field. The answer should be factually correct for the wrong topic it discusses.",
            },
            {
                "title": "6. Irrelevant (The Buzzword Bluffer)",
                "instruction": "For your final revision, make the previous answer completely irrelevant and nonsensical. It should use technical-sounding buzzwords related to the original question but be logically incoherent and convey no real information.",
            },
        ]
