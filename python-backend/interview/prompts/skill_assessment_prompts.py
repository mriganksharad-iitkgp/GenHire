"""
Prompts for skill level assessment using LLM analysis.
"""

SKILL_LEVEL_ASSESSMENT_PROMPT = """Analyze the following CV/Resume content to assess the candidate's technical skill level. Consider these key factors:

**EXPERIENCE TIMELINE ANALYSIS:**
1. **Graduation Year vs Current Year (2025)**: Calculate years since graduation
2. **Work Experience Duration**: Total years of professional experience
3. **Company Progression**: Number of companies worked at and career progression
4. **Role/Title Evolution**: Progression from junior to senior positions

**SKILL LEVEL INDICATORS:**
- **Beginner (0-2 years)**: Recent graduate, entry-level positions, basic projects
- **Intermediate (2-5 years)**: Mid-level roles, multiple technologies, team collaboration
- **Advanced (5+ years)**: Senior roles, leadership, architecture, mentoring, complex projects

**ASSESSMENT CRITERIA:**
1. **Time-based**: Years since graduation and total work experience
2. **Role-based**: Job titles (Junior, Mid, Senior, Lead, Architect, Principal)
3. **Responsibility-based**: Team leadership, project ownership, technical decisions
4. **Technology-based**: Breadth and depth of technical skills
5. **Achievement-based**: Notable projects, awards, certifications

CV Content:
{cv_content}

Based on the above analysis, classify the candidate's skill level as one of:
- "beginner" (0-2 years experience, entry-level roles)
- "intermediate" (2-5 years experience, mid-level roles) 
- "advanced" (5+ years experience, senior roles with leadership)

Consider the candidate's career progression, technical responsibilities, and years of experience.

Skill Level Assessment:"""
