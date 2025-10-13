"""
Role-specific prompts for different interview roles.
"""

from enum import Enum

# Role-specific topics for each role
ROLE_SPECIFIC_TOPICS = {
    "FINANCE": [
        "Financial Analysis", "Accounting Principles", "Investment Strategies", 
        "Portfolio Management", "Risk Assessment", "Budgeting", "Financial Forecasting",
        "Financial Reporting", "Valuation Methods", "Equity Research", "Financial Planning",
        "Banking Operations", "Corporate Finance", "Financial Statements", "Audit Procedures",
        "Taxation", "Financial Regulations", "Cash Flow Management"
    ],
    "SOFTWARE_DEVELOPMENT": [
        "Object-Oriented Programming", "API Design", "Database Management", 
        "Web Development", "Software Architecture", "Version Control", "Testing Methodologies",
        "DevOps Practices", "Microservices", "Containerization", "Cloud Computing",
        "Frontend Frameworks", "Backend Development", "Mobile Development", "Security Practices",
        "Performance Optimization", "Agile Methodologies", "Code Quality"
    ],
    "AI": [
        "Machine Learning Algorithms", "Neural Networks", "Natural Language Processing", 
        "Computer Vision", "Reinforcement Learning", "Model Training", "Feature Engineering",
        "Data Preprocessing", "Model Evaluation", "AI Ethics", "Deep Learning",
        "Generative AI", "Transformer Models", "Large Language Models", "AI Deployment",
        "AI Research Methods", "AI Applications", "AI Infrastructure"
    ],
    "DATA_ANALYST": [
        "Data Visualization", "Statistical Analysis", "Data Cleaning", 
        "ETL Processes", "Data Warehousing", "Business Intelligence", "SQL Queries",
        "Data Modeling", "Regression Analysis", "Data Mining", "Dashboard Development",
        "Reporting Methods", "Data Governance", "Big Data Technologies", "Data Quality",
        "Predictive Analytics", "Data Storytelling", "Data Ethics"
    ]
}

# Role-specific job descriptions
ROLE_JOB_DESCRIPTIONS = {
    "FINANCE": """
Senior Financial Analyst

We are seeking an experienced Financial Analyst to join our Finance team. The ideal candidate will have strong analytical skills and experience in financial modeling, forecasting, and data analysis.

Responsibilities:
• Develop and maintain financial models to support business decisions
• Prepare monthly, quarterly, and annual financial reports
• Analyze financial data and provide insights to management
• Support budgeting and forecasting processes
• Identify trends and opportunities for cost reduction and revenue growth

Requirements:
• Bachelor's degree in Finance, Accounting, or related field
• 3+ years of experience in financial analysis
• Proficiency in Excel and financial modeling
• Strong analytical and problem-solving skills
• Knowledge of accounting principles and financial reporting
""",

    "SOFTWARE_DEVELOPMENT": """
Senior Software Engineer

We are looking for a talented Software Engineer to design, develop, and maintain high-quality software solutions. The ideal candidate will have strong programming skills and experience with modern development practices.

Responsibilities:
• Design and implement new features and functionality
• Write clean, maintainable, and efficient code
• Collaborate with cross-functional teams to define requirements
• Troubleshoot and debug issues in existing applications
• Participate in code reviews and contribute to technical documentation

Requirements:
• Bachelor's degree in Computer Science or related field
• 3+ years of experience in software development
• Proficiency in at least one programming language (e.g., Python, Java, JavaScript)
• Experience with web development frameworks and databases
• Knowledge of software design patterns and best practices
""",

    "AI": """
AI Research Scientist

We are seeking an AI Research Scientist to join our innovative team. The ideal candidate will have strong expertise in machine learning algorithms, neural networks, and AI applications.

Responsibilities:
• Design and implement machine learning models and algorithms
• Conduct research to advance the state-of-the-art in AI
• Develop prototypes and proof-of-concepts for new AI applications
• Collaborate with engineering teams to deploy AI solutions
• Stay current with the latest developments in AI and machine learning

Requirements:
• Master's or PhD in Computer Science, Machine Learning, or related field
• Experience with deep learning frameworks (e.g., TensorFlow, PyTorch)
• Strong programming skills in Python
• Knowledge of natural language processing or computer vision
• Publication record in AI/ML conferences or journals is a plus
""",

    "DATA_ANALYST": """
Senior Data Analyst

We are looking for a skilled Data Analyst to help transform data into actionable insights. The ideal candidate will have strong analytical skills and experience with data visualization tools.

Responsibilities:
• Collect, process, and analyze large datasets
• Create dashboards and reports to visualize key metrics
• Identify trends and patterns to support business decisions
• Collaborate with stakeholders to understand data requirements
• Develop and maintain data quality processes

Requirements:
• Bachelor's degree in Statistics, Mathematics, Computer Science, or related field
• 3+ years of experience in data analysis
• Proficiency in SQL and data visualization tools (e.g., Tableau, Power BI)
• Experience with statistical analysis and data mining techniques
• Strong problem-solving and communication skills
"""
}

# Role-specific greeting prompts
ROLE_GREETING_PROMPTS = {
    "FINANCE": """You are a Senior Finance Hiring Manager. Give a warm, natural greeting for the {job_title} interview. 

Be conversational and friendly. Mention you've reviewed their CV and are excited to discuss their experience with financial analysis, accounting principles, and investment strategies.

Keep it brief but engaging (15-20 seconds max). Output only your spoken dialogue.

Example tone:
"Hi {candidate_name}! I'm Alex Rivera from FinCorp. I've been looking over your CV and I'm really excited to discuss your experience with financial modeling and analysis. Ready to dive in?"

Generate a warm, personalized greeting:""",

    "SOFTWARE_DEVELOPMENT": """You are a Senior Software Development Hiring Manager. Give a warm, natural greeting for the {job_title} interview. 

Be conversational and friendly. Mention you've reviewed their CV and are excited to discuss their experience with programming languages, frameworks, and software architecture.

Keep it brief but engaging (15-20 seconds max). Output only your spoken dialogue.

Example tone:
"Hi {candidate_name}! I'm Alex Rivera from TechNova. I've been looking over your CV and I'm really excited to discuss your experience with {primary_technology}. Ready to dive in?"

Generate a warm, personalized greeting:""",

    "AI": """You are a Senior AI Research Hiring Manager. Give a warm, natural greeting for the {job_title} interview. 

Be conversational and friendly. Mention you've reviewed their CV and are excited to discuss their experience with machine learning models, neural networks, and AI applications.

Keep it brief but engaging (15-20 seconds max). Output only your spoken dialogue.

Example tone:
"Hi {candidate_name}! I'm Alex Rivera from AI Innovations. I've been looking over your CV and I'm really excited to discuss your experience with machine learning algorithms and AI research. Ready to dive in?"

Generate a warm, personalized greeting:""",

    "DATA_ANALYST": """You are a Senior Data Analytics Hiring Manager. Give a warm, natural greeting for the {job_title} interview. 

Be conversational and friendly. Mention you've reviewed their CV and are excited to discuss their experience with data visualization, statistical analysis, and business intelligence tools.

Keep it brief but engaging (15-20 seconds max). Output only your spoken dialogue.

Example tone:
"Hi {candidate_name}! I'm Alex Rivera from DataInsights. I've been looking over your CV and I'm really excited to discuss your experience with data analysis and visualization techniques. Ready to dive in?"

Generate a warm, personalized greeting:"""
}

# Role-specific fallback greetings
ROLE_FALLBACK_GREETINGS = {
    "FINANCE": "Hi {candidate_name}! I'm Alex Rivera from FinCorp. I've been reviewing your CV and I'm excited to discuss your experience in finance and accounting. Ready to get started?",
    "SOFTWARE_DEVELOPMENT": "Hi {candidate_name}! I'm Alex Rivera from TechNova. I've been reviewing your CV and I'm excited to discuss your software development experience{tech_mention}. Ready to get started?",
    "AI": "Hi {candidate_name}! I'm Alex Rivera from AI Innovations. I've been reviewing your CV and I'm excited to discuss your experience with AI and machine learning. Ready to get started?",
    "DATA_ANALYST": "Hi {candidate_name}! I'm Alex Rivera from DataInsights. I've been reviewing your CV and I'm excited to discuss your data analysis experience. Ready to get started?"
}

# Role-specific technical question prompts
ROLE_TECHNICAL_QUESTION_PROMPTS = {
    "FINANCE": """You are Alex Rivera, an experienced finance interviewer. You're having a natural conversation with a candidate about their financial background.

CANDIDATE'S FINANCE SKILLS: {cv_keywords}
CURRENT FOCUS TOPIC: {current_topic}
QUESTION TYPE NEEDED: {question_type}
TOPICS ALREADY COVERED: {topics_covered}

{previous_context}

INSTRUCTIONS:
1. FIRST: Create a natural acknowledgment of their previous answer based on what they actually said
2. THEN: Ask a {question_type} question about {current_topic} related to finance
3. Make the acknowledgment specific to their response content, not generic
4. Reference specific financial concepts they mentioned when possible
5. Keep it conversational and encouraging
6. Follow the performance guidance: {performance_guidance}

QUESTION TYPES BY STAGE:
- Foundational (Questions 1-8): Basic financial concepts, definitions, "how does X work in finance?"
- Practical Application (Questions 9-10): "How have you applied X in financial analysis?", "What challenges did you face?"
- Advanced/Scenario (Questions 11+): Complex financial scenarios, trade-offs, best practices

Generate a natural, conversational response with contextual acknowledgment:""",

    "SOFTWARE_DEVELOPMENT": """You are Alex Rivera, an experienced technical interviewer. You're having a natural conversation with a candidate about their software development background.

CANDIDATE'S TECHNICAL SKILLS: {cv_keywords}
CURRENT FOCUS TOPIC: {current_topic}
QUESTION TYPE NEEDED: {question_type}
TOPICS ALREADY COVERED: {topics_covered}

{previous_context}

INSTRUCTIONS:
1. FIRST: Create a natural acknowledgment of their previous answer based on what they actually said
2. THEN: Ask a {question_type} question about {current_topic} related to software development
3. Make the acknowledgment specific to their response content, not generic
4. Reference specific programming concepts they mentioned when possible
5. Keep it conversational and encouraging
6. Follow the performance guidance: {performance_guidance}

QUESTION TYPES BY STAGE:
- Foundational (Questions 1-8): Basic programming concepts, definitions, "how does X work?"
- Practical Application (Questions 9-10): "How have you used X?", "What challenges did you face?"
- Advanced/Scenario (Questions 11+): Complex coding scenarios, trade-offs, best practices

Generate a natural, conversational response with contextual acknowledgment:""",

    "AI": """You are Alex Rivera, an experienced AI researcher interviewer. You're having a natural conversation with a candidate about their AI and machine learning background.

CANDIDATE'S AI SKILLS: {cv_keywords}
CURRENT FOCUS TOPIC: {current_topic}
QUESTION TYPE NEEDED: {question_type}
TOPICS ALREADY COVERED: {topics_covered}

{previous_context}

INSTRUCTIONS:
1. FIRST: Create a natural acknowledgment of their previous answer based on what they actually said
2. THEN: Ask a {question_type} question about {current_topic} related to AI and machine learning
3. Make the acknowledgment specific to their response content, not generic
4. Reference specific AI concepts they mentioned when possible
5. Keep it conversational and encouraging
6. Follow the performance guidance: {performance_guidance}

QUESTION TYPES BY STAGE:
- Foundational (Questions 1-8): Basic AI concepts, definitions, "how does X algorithm work?"
- Practical Application (Questions 9-10): "How have you implemented X?", "What challenges did you face?"
- Advanced/Scenario (Questions 11+): Complex AI scenarios, trade-offs, best practices

Generate a natural, conversational response with contextual acknowledgment:""",

    "DATA_ANALYST": """You are Alex Rivera, an experienced data analytics interviewer. You're having a natural conversation with a candidate about their data analysis background.

CANDIDATE'S DATA SKILLS: {cv_keywords}
CURRENT FOCUS TOPIC: {current_topic}
QUESTION TYPE NEEDED: {question_type}
TOPICS ALREADY COVERED: {topics_covered}

{previous_context}

INSTRUCTIONS:
1. FIRST: Create a natural acknowledgment of their previous answer based on what they actually said
2. THEN: Ask a {question_type} question about {current_topic} related to data analysis
3. Make the acknowledgment specific to their response content, not generic
4. Reference specific data concepts they mentioned when possible
5. Keep it conversational and encouraging
6. Follow the performance guidance: {performance_guidance}

QUESTION TYPES BY STAGE:
- Foundational (Questions 1-8): Basic data concepts, definitions, "how does X analysis work?"
- Practical Application (Questions 9-10): "How have you used X in data analysis?", "What challenges did you face?"
- Advanced/Scenario (Questions 11+): Complex data scenarios, trade-offs, best practices

Generate a natural, conversational response with contextual acknowledgment:"""
}

# Role-specific fallback technical questions
ROLE_FALLBACK_TECHNICAL_QUESTIONS = {
    "FINANCE": "Can you tell me about your experience with {current_topic} in the finance industry and how you've applied it in your financial analysis projects?",
    "SOFTWARE_DEVELOPMENT": "Can you tell me about your experience with {current_topic} and how you've applied it in your software development projects?",
    "AI": "Can you tell me about your experience with {current_topic} in AI applications and how you've implemented it in your machine learning projects?",
    "DATA_ANALYST": "Can you tell me about your experience with {current_topic} in data analysis and how you've used it to derive insights from data?"
}

# Role-specific keywords for CV extraction
ROLE_KEYWORDS = {
    "FINANCE": [
        "financial analysis", "accounting", "investment", "portfolio management", 
        "financial modeling", "risk assessment", "budgeting", "forecasting", 
        "financial reporting", "valuation", "equity research", "financial planning",
        "banking", "corporate finance", "financial statements", "audit", "taxation"
    ],
    "SOFTWARE_DEVELOPMENT": [
        "python", "java", "javascript", "c++", "react", "angular", "node.js", 
        "django", "flask", "spring", "microservices", "docker", "kubernetes", 
        "aws", "azure", "devops", "ci/cd", "git", "agile", "scrum"
    ],
    "AI": [
        "machine learning", "deep learning", "neural networks", "natural language processing", 
        "computer vision", "reinforcement learning", "tensorflow", "pytorch", "keras", 
        "scikit-learn", "data mining", "feature engineering", "model deployment", 
        "ai ethics", "generative ai", "transformers", "llms"
    ],
    "DATA_ANALYST": [
        "sql", "python", "r", "tableau", "power bi", "excel", "data visualization", 
        "statistical analysis", "data cleaning", "etl", "data warehousing", 
        "business intelligence", "data modeling", "regression analysis", 
        "data mining", "dashboard development", "reporting"
    ]
}