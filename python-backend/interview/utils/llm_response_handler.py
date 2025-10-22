"""
Centralized LLM response handler for consistent processing across the interview system.
"""

import json
import re
from typing import Dict, Any, Union


class LLMResponseHandler:
    """Centralized handler for cleaning and processing LLM responses."""

    @staticmethod
    def extract_text(response: Any) -> str:
        """Extract text from LLM response object."""
        if hasattr(response, "text"):
            return response.text
        return str(response)

    @staticmethod
    def clean_markdown(text: str) -> str:
        """Remove markdown code blocks and formatting from text."""
        text = text.strip()

        # Handle ```json ... ``` blocks
        json_pattern = r"```json\s*(.*?)\s*```"
        json_match = re.search(json_pattern, text, re.DOTALL)
        if json_match:
            return json_match.group(1).strip()

        # Handle generic ``` blocks
        generic_pattern = r"```\s*(.*?)\s*```"
        generic_match = re.search(generic_pattern, text, re.DOTALL)
        if generic_match:
            return generic_match.group(1).strip()

        return text

    @staticmethod
    def parse_json_response(response: Any) -> Dict[str, Any]:
        """Extract text from LLM response and parse as JSON."""
        try:
            text = LLMResponseHandler.extract_text(response)
            cleaned_text = LLMResponseHandler.clean_markdown(text)
            return json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in LLM response: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to process LLM response: {str(e)}")

    @staticmethod
    def extract_clean_text(response: Any) -> str:
        """Extract and clean text from LLM response."""
        text = LLMResponseHandler.extract_text(response)
        cleaned = LLMResponseHandler.clean_markdown(text)

        if not cleaned:
            raise ValueError("Empty response from LLM")

        return cleaned
