import json
import logging
import os
import re
from typing import Any, Dict, Optional

from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)


class CVStructuredParserService:
    """Convert extracted CV text into the schema consumed by CVDetailsForm."""

    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        self.llm = (
            ChatGoogleGenerativeAI(
                model=os.getenv("CV_PARSER_MODEL", "gemini-flash-latest"),
                temperature=0,
                google_api_key=api_key,
            )
            if api_key
            else None
        )

    def parse(self, text: str) -> Optional[Dict[str, Any]]:
        if not self.llm or not str(text or "").strip():
            return None

        prompt = f"""
Extract the resume below into strict JSON. Preserve the difference between paid/work
experience, internships, and projects. Never move a project into experience merely
because it mentions technologies or dates. Do not invent missing values.

Return one JSON object with these keys:
personalInfo: {{fullName, email, phone, location, linkedin, github}}
professionalSummary: string
education: [{{degree, institution, year, grade, field}}]
experience: [{{company, position, duration, description, location}}]
skills: {{technical: [string], soft: [string]}}
projects: [{{title, description, technologies, duration, link}}]
achievements: [{{title, description, date, organization, level}}]
competitions: [{{name, position, date, organizer, description}}]
certifications: [{{name, issuer, date, credentialId, validUntil}}]
internships: [{{company, position, duration, description, location}}]
coursework: [{{course, institution, duration, certification}}]
languages: [{{language, proficiency, certification}}]
extracurricular: [{{activity, role, duration, description}}]

Use empty strings and empty arrays for missing data. Return JSON only.

Resume:
{text[:30000]}
"""
        try:
            response = self.llm.invoke(prompt)
            content = str(response.content or "").strip()
            content = content.replace("```json", "").replace("```", "").strip()
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if not match:
                return None
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except Exception as exc:
            logger.warning("Structured CV parsing failed: %s", exc)
            return None


_structured_parser = None


def get_cv_structured_parser() -> CVStructuredParserService:
    global _structured_parser
    if _structured_parser is None:
        _structured_parser = CVStructuredParserService()
    return _structured_parser
