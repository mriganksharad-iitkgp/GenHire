"""
Prompts for CV and JD keyword extraction using LLM analysis.
"""

CV_KEYWORDS_EXTRACTION_PROMPT = """Analyze BOTH the CV/Resume and the Job Description to extract the most relevant technical skills and topic areas for interview questions.

Weight JD relevance higher when ranking topics (prioritize JD ~60%, CV evidence ~40%). Prefer items explicitly required in the JD and demonstrated in the CV.

CORE DOMAINS TO CONSIDER:
1. Programming Languages (Python, JavaScript, Java, C++, C#, Go, Rust, Swift, Kotlin, etc.)
2. Web Technologies (HTML, CSS, React, Angular, Vue, Node.js, Django, Flask, Spring)
3. Mobile (iOS, Android, React Native, Flutter)
4. Databases (SQL, MySQL, PostgreSQL, MongoDB, Redis, Elasticsearch)
5. Cloud & DevOps (AWS, Azure, GCP, Docker, Kubernetes, Terraform, CI/CD)
6. Data/ML (Pandas, NumPy, TensorFlow, PyTorch, Scikit-learn, Spark, Hadoop)
7. Architecture & APIs (Microservices, Design Patterns, REST, GraphQL, gRPC)
8. Security & Reliability (Auth, JWT, OAuth, Testing, Monitoring, Logging)

CV Content:
{cv_content}

Job Description (JD) Content:
{jd_content}

TASK:
- Extract 12–15 concise keywords and technical topic areas.
- Sort by JD relevance first, then by CV evidence depth (projects, years, achievements).
- Include both concrete technologies (e.g., "Python", "React") and topic areas (e.g., "System Design", "CI/CD").
- Return a single comma-separated list only.

Examples of good outputs:
- "Python, System Design, REST APIs, React, Docker, AWS, CI/CD, PostgreSQL, Unit Testing, Kubernetes, Microservices, Logging, OAuth, GraphQL, Caching"

Technical Keywords and Areas:"""
