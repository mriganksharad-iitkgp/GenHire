JD_KEYWORDS_EXTRACTION_PROMPT = """Analyze the Job Description (JD) to extract the most critical technical skills, technologies, and methodologies required for the role.

INSTRUCTIONS:
1. Extract 10-15 specific technical keywords (e.g., Python, Docker, System Design, React).
2. Focus ONLY on what the role REQUIRES.
3. Ignore generic soft skills (e.g., "Team player", "Leadership").
4. List the most important technologies mentioned in the JD first.
5. Return ONLY a comma-separated list of keywords.

JD CONTENT:
{jd_content}

Comma-separated keywords:"""

JD_DIFFICULTY_DISTRIBUTION_PROMPT = """Analyze the following Job Description (JD) and determine the ideal difficulty distribution for a technical interview.
Based on the seniority, required skills, and responsibilities, provide the percentage of questions that should be Easy, Medium, and Hard.

INSTRUCTIONS:
1. The total percentage must sum to 100%.
2. Return ONLY a JSON object in the following format:
   {{"easy": X, "medium": Y, "hard": Z}}
3. Consider:
   - Junior/Entry-level roles: Higher percentage of Easy/Medium questions.
   - Mid-level roles: Balanced distribution, focused on Medium.
   - Senior/Architect roles: Higher percentage of Hard/Medium questions.

JD CONTENT:
{jd_content}

JSON Response:"""

CV_KEYWORDS_EXTRACTION_PROMPT = """Analyze BOTH the CV/Resume and the Job Description to extract the most relevant technical skills and topic areas for interview questions.

Weight JD relevance as the HIGHEST priority (prioritize JD requirements ~80%, CV evidence ~20%). Focus on what the JOB REQUIRES. 
1. If a skill is in the JD, it MUST be included in the list, even if it's not prominent in the CV.
2. If a skill is in the CV but NOT in the JD, only include it if it's highly relevant to the role's domain.
3. The resulting list should serve as a roadmap for testing if the candidate meets the JOB'S requirements.
4. Extract only technical skills, tools, and methodologies (e.g., Python, AWS, System Design, Agile).
5. Avoid generic terms like "Communication" or "Teamwork".
6. Return ONLY a comma-separated list of keywords.

CV CONTENT:
{cv_content}

JD CONTENT:
{jd_content}

Comma-separated keywords:"""
