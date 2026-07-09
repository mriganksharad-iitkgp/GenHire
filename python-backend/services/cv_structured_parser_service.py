import json
import logging
import os
import re
from typing import Any, Dict, Optional

from services.llm_fallback_service import get_llm_fallback_service

logger = logging.getLogger(__name__)


class CVStructuredParserService:
    """Convert extracted CV text into the schema consumed by CVDetailsForm.

    Runs on the app-wide LLM chain (LLM_PROVIDER_PRIORITY order); the legacy
    CV_PARSER_MODEL env still pins the Gemini model for this task."""

    def parse(self, text: str) -> Optional[Dict[str, Any]]:
        if not str(text or "").strip():
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
            overrides = {}
            if os.getenv("CV_PARSER_MODEL"):
                overrides["google"] = os.getenv("CV_PARSER_MODEL")
            result = get_llm_fallback_service().invoke(
                prompt, json_mode=True, model_overrides=overrides or None
            )
            content = str(result["content"] or "").strip()
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
