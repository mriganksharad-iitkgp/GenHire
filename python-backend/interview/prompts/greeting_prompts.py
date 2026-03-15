"""
Prompts for interview greeting generation.
"""

GREETING_PROMPT = """Give a brief, friendly greeting for the technical interview and ask the candidate to introduce themselves briefly.

Keep it very short (10 seconds max). Be warm and welcoming.

Example:
"Hi {candidate_name}! I'm Alex. Great to meet you! Could you please give me a brief introduction about yourself and your background?"

Generate a short greeting that asks for a brief self-introduction:"""

FALLBACK_GREETING = "Hi {candidate_name}! I'm Alex. Great to meet you! Could you please give me a brief introduction about yourself and your background?"
