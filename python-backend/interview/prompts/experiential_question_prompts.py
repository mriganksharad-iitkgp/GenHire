"""

Prompts for experiential question generation during interview.
Focus on CV projects, previous experiences, and practical implementation details.

"""

EXPERIENTIAL_QUESTION_PROMPT = """You are Alex Rivera, an experienced technical interviewer. You're having a natural conversation with a candidate about their project experiences and practical work.

CANDIDATE'S CV PROJECTS: {cv_projects}

CANDIDATE'S EXPERIENCES: {experiences}

CURRENT FOCUS PROJECT/EXPERIENCE: {current_focus}

QUESTION TYPE NEEDED: {question_type}

PROJECTS/EXPERIENCES ALREADY DISCUSSED: {topics_covered}

{previous_context}

INSTRUCTIONS:

1. FIRST: Create a natural acknowledgment of their previous answer based on what they actually said

2. THEN: Ask a {question_type} question about {current_focus}

3. Make the acknowledgment specific to their response content, not generic

4. Reference specific projects, technologies, or challenges they mentioned when possible

5. Keep it conversational and encouraging

6. Follow the performance guidance: {performance_guidance}

QUESTION TYPES BY STAGE:

- Project Overview (Questions 1-3): "Tell me about...", "What was your role in...", "How did you approach..."

- Technical Implementation (Questions 4-7): "How did you implement...", "What technologies did you use...", "Walk me through the architecture..."

- Challenges & Problem Solving (Questions 8-10): "What challenges did you face...", "How did you overcome...", "What would you do differently..."

- Impact & Learnings (Questions 11+): "What was the impact...", "What did you learn...", "How has this experience influenced..."

EXAMPLES OF NATURAL, CONTEXTUAL ACKNOWLEDGMENTS:

- "That sounds like a really interesting project with [specific technology/approach]. Tell me more about..."

- "I can see you put a lot of thought into [specific aspect they mentioned]. When you were implementing..."

- "It's impressive that you handled [specific challenge]. In that project, how did you..."

- "That's a great example of [specific skill/concept]. Building on that experience..."

EXPERIENTIAL QUESTION FOCUS AREAS:

1. **Project Scope & Planning**: Understanding project requirements, planning, timeline management

2. **Technical Decision Making**: Why certain technologies/approaches were chosen

3. **Implementation Details**: How specific features were built, code architecture

4. **Collaboration & Teamwork**: Working with others, communication, code reviews

5. **Problem Solving**: Debugging, performance issues, unexpected challenges

6. **Learning & Growth**: What was learned, skills developed, areas of improvement

7. **Impact & Results**: Measurable outcomes, user feedback, business impact

Generate a natural, conversational response with contextual acknowledgment:"""

FALLBACK_EXPERIENTIAL_QUESTION = "Can you walk me through your {current_focus} project and tell me about your specific contributions to it?"

# Performance guidance templates for experiential questions
EXPERIENTIAL_PERFORMANCE_GUIDANCE = {
    "vague": "The candidate gave a vague or high-level answer. Acknowledge their response positively, then ask for more specific details about implementation, challenges, or their personal contributions.",

    "surface": "The candidate provided surface-level details. Acknowledge what they shared, then drill deeper into technical implementation, decision-making process, or specific challenges they faced.",

    "detailed": "The candidate provided good details about their experience. Acknowledge their thorough explanation, then explore a different aspect of the project or ask about lessons learned.",

    "comprehensive": "The candidate gave a comprehensive and insightful answer. Show enthusiasm for their detailed response, then ask about advanced topics like scalability, optimization, or how they'd approach similar problems now."
}

# Context templates for previous experiential answers
EXPERIENTIAL_ANSWER_CONTEXT = """
Previous answer context: The candidate just described: "{last_answer_preview}..."

Key projects/experiences mentioned: {experiences_mentioned}

Specific technologies/tools discussed: {technologies_mentioned}

Score: {score}/1.0

Performance guidance: {performance_guidance}
"""

# Specific question templates for different experiential areas
EXPERIENTIAL_QUESTION_TEMPLATES = {
    "project_overview": [
        "Can you walk me through the {project_name} project from start to finish?",
        "What was your specific role and contribution in the {project_name} project?",
        "How did you approach the planning and design phase of {project_name}?",
        "What motivated you to work on {project_name}? What problem were you trying to solve?"
    ],

    "technical_implementation": [
        "How did you architect the solution for {project_name}?",
        "What technologies did you choose for {project_name} and why?",
        "Can you explain the data flow in your {project_name} system?",
        "How did you handle {specific_feature} in your {project_name} project?",
        "What was the most complex part of implementing {project_name}?"
    ],

    "challenges_problem_solving": [
        "What was the biggest challenge you faced while working on {project_name}?",
        "Tell me about a time when something went wrong in {project_name}. How did you debug it?",
        "How did you handle performance issues in {project_name}?",
        "What would you do differently if you were to rebuild {project_name} today?",
        "How did you ensure code quality and reliability in {project_name}?"
    ],

    "collaboration_teamwork": [
        "How did you collaborate with others during the {project_name} project?",
        "How did you handle code reviews and feedback in {project_name}?",
        "Tell me about any disagreements or conflicts during {project_name} and how you resolved them.",
        "How did you communicate technical concepts to non-technical stakeholders in {project_name}?"
    ],

    "impact_learnings": [
        "What was the impact or outcome of your {project_name} project?",
        "What did you learn from working on {project_name}?",
        "How has the {project_name} project influenced your approach to subsequent projects?",
        "What feedback did you receive on {project_name}?",
        "How do you measure the success of {project_name}?"
    ],

    "internship_experience": [
        "Tell me about your experience at {company_name}. What did you work on?",
        "What was the most valuable thing you learned during your internship at {company_name}?",
        "How did you adapt to the team's workflow and coding standards at {company_name}?",
        "What project are you most proud of from your time at {company_name}?"
    ],

    "research_experience": [
        "Can you explain your research in {research_area} in simple terms?",
        "What methodology did you use for your research in {research_area}?",
        "What were the key findings from your {research_area} research?",
        "How did you validate your results in {research_area}?",
        "What tools and technologies did you use for your research?"
    ]
}

# Follow-up question generators
EXPERIENTIAL_FOLLOW_UPS = {
    "dive_deeper": [
        "That's interesting. Can you elaborate on {specific_aspect}?",
        "You mentioned {specific_detail}. How exactly did you implement that?",
        "Tell me more about the {specific_technology} part of your solution.",
        "What was your thought process when you decided to {specific_decision}?"
    ],

    "alternative_approaches": [
        "What other approaches did you consider for {specific_problem}?",
        "How would you solve {specific_problem} differently with the knowledge you have now?",
        "What are the trade-offs of the approach you chose for {specific_feature}?",
        "If you had unlimited time and resources, how would you improve {specific_aspect}?"
    ],

    "lessons_learned": [
        "What would you do differently if you started {project_name} again?",
        "What was the most valuable lesson you learned from {project_name}?",
        "How has working on {project_name} changed your development practices?",
        "What advice would you give to someone starting a similar project?"
    ]
}

# Question progression logic for experiential interviews
EXPERIENTIAL_QUESTION_FLOW = {
    1: {"type": "project_overview", "focus": "Get high-level understanding of the project"},
    2: {"type": "project_overview", "focus": "Understand candidate's specific role and contributions"},
    3: {"type": "technical_implementation", "focus": "Dive into technical details and architecture"},
    4: {"type": "technical_implementation", "focus": "Explore technology choices and implementation"},
    5: {"type": "challenges_problem_solving", "focus": "Understand problem-solving approach"},
    6: {"type": "challenges_problem_solving", "focus": "Explore debugging and troubleshooting skills"},
    7: {"type": "collaboration_teamwork", "focus": "Assess teamwork and communication skills"},
    8: {"type": "impact_learnings", "focus": "Understand project outcomes and personal growth"},
    9: {"type": "follow_up", "focus": "Dive deeper into most interesting aspects"},
    10: {"type": "alternative_approaches", "focus": "Assess critical thinking and adaptability"}
}
