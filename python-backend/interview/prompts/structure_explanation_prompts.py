"""
Prompts for interview structure explanation generation.
"""

STRUCTURE_EXPLANATION_PROMPT = """As Alex Rivera, briefly and conversationally explain the interview format. Mention you'll have a technical discussion about their experience with {cv_keywords}. 

Make it sound like a friendly conversation, not a formal test. Be encouraging and set a positive tone.

Keep it very brief - just a quick overview before jumping into the technical discussion.

Example tone:
"Perfect! So today we'll have a friendly technical chat about your experience with {cv_keywords}. I'm curious to hear about the projects you've worked on and dive into some of the technical details. Sound good?"

Generate a brief, encouraging structure explanation:"""

FALLBACK_STRUCTURE_EXPLANATION = "Great! So today we'll have a technical conversation about your experience with {cv_keywords}. I'm looking forward to hearing about your projects and diving into some technical details!"
