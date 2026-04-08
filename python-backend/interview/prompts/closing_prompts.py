"""
Prompts for interview closing generation.
"""

CLOSING_PROMPT = """close warmly: "Thank you, {candidate_name}, for sharing your expertise—your {positive_aspect} knowledge was impressive." Outline next steps: "We'll review and follow up within 3 business days via email." End positively.

Generate the closing:"""

FALLBACK_CLOSING = "Thank you {candidate_name} for such an engaging technical discussion! Your insights about {primary_technology} were really impressive. We'll review everything and follow up within 3 business days with next steps."
