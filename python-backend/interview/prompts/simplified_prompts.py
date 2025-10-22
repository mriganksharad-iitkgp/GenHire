"""
Simplified prompts for natural interview flow with minimal acknowledgments.
"""

# CV and JD Analysis Prompt
CV_JD_ANALYSIS_PROMPT = """
Analyze the following CV and Job Description to extract key information for conducting a modern first-round interview.

CV:
{cv_text}

Job Description:
{jd_text}

Extract and return in JSON format:
1. job_role: The main job title/role from JD
2. experience_level: junior/mid/senior based on CV experience and JD requirements  
3. key_skills: Top 5 relevant skills mentioned in both CV and JD (technical, analytical, business, etc.)
4. primary_domain: The main domain area (technical, finance, product, marketing, operations, etc.)
5. candidate_expertise: Key areas of expertise mentioned in CV relevant to JD
6. years_experience: Approximate years of experience from CV

Return only valid JSON without any explanation.
"""

# First Question Generation
FIRST_QUESTION_PROMPT = """
You are conducting a first-round interview for the role: {job_role}

Candidate profile:
- Experience level: {experience_level}
- Key skills: {key_skills}
- Years of experience: {years_experience}
- Domain: {primary_domain}

Generate a natural, theoretical opening question that:
1. Is commonly asked in today's first-round interviews for this role
2. Focuses on fundamental concepts relevant to the role and domain
3. Is theoretical rather than experience/scenario-based
4. Is conversational and appropriate for their experience level
5. Doesn't ask for personal information or "tell me about yourself"

Examples for different roles and levels:
- Software Developer (Junior): "What is the difference between REST and GraphQL APIs?"
- Software Developer (Senior): "How would you explain the CAP theorem and its implications?"
- Product Manager (Mid): "What is the difference between a feature and a product?"
- Finance Analyst (Senior): "Explain the difference between NPV and IRR in investment analysis"
- Data Scientist (Mid): "What is the bias-variance tradeoff in machine learning?"

Return only the question, no explanation.
"""

# Next Question with Intelligent Follow-up Logic
NEXT_QUESTION_PROMPT = """
You are conducting a first-round interview for: {job_role}

Interview history so far:
{interview_history}
Last answer: {last_answer}
Question #{question_number} of {max_questions}
Experience level: {experience_level}
Domain: {primary_domain}

IMPORTANT: Review the interview history carefully and DO NOT repeat questions that have already been asked or are very similar to previous questions.

Analyze the interview history to determine the best next question approach:

1. FOLLOW-UP NEEDED: If the candidate's last answer was:
   - Incomplete or vague
   - Showed uncertainty or confusion
   - Mentioned an interesting concept that needs deeper exploration
   - Had technical inaccuracies that need clarification
   
2. NEW CONCEPT: If the candidate's last answer was:
   - Complete and accurate
   - Showed good understanding
   - Covered the topic sufficiently
   - Ready to move to different fundamental concepts

Generate a response that:
1. Starts with 1-2 word acknowledgment (like "Good.", "Great!", "Okay.", "Nice.")
2. Either asks a follow-up question OR moves to a new concept
3. Focuses on theoretical/conceptual knowledge commonly asked in first-round interviews
4. Ensures variety across different conceptual areas of the domain
5. Matches the experience level appropriately
6. AVOIDS repeating or asking similar questions to those already covered in the interview history
7. Explores new fundamental concepts that haven't been discussed yet

Ensure questions test fundamental knowledge appropriate for {experience_level} level in {primary_domain} domain while maintaining variety and avoiding repetition.

Return the complete response (acknowledgment + question).
"""
