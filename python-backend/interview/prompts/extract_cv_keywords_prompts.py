"""
Prompts for CV keyword extraction using LLM analysis.
"""

CV_KEYWORDS_EXTRACTION_PROMPT = """Analyze the following CV/Resume content and extract the most relevant technical skills, technologies, frameworks, and tools mentioned. Focus on ALL technical domains:

**CORE TECHNICAL AREAS:**
1. Programming Languages (Python, JavaScript, Java, C++, C#, Go, Rust, Swift, Kotlin, etc.)
2. Web Technologies (HTML, CSS, React, Angular, Vue, Node.js, Django, Flask, Spring, etc.)
3. Mobile Development (iOS, Android, React Native, Flutter, Xamarin, etc.)
4. Databases & Data Storage (SQL, MySQL, PostgreSQL, MongoDB, Redis, Elasticsearch, etc.)

**INFRASTRUCTURE & OPERATIONS:**
5. Cloud Platforms (AWS, Azure, GCP, Digital Ocean, Heroku, etc.)
6. DevOps & CI/CD (Docker, Kubernetes, Jenkins, GitLab CI, GitHub Actions, Terraform, etc.)
7. System Administration (Linux, Windows Server, Networking, Security, etc.)
8. Monitoring & Logging (Prometheus, Grafana, ELK Stack, Splunk, etc.)

**SPECIALIZED DOMAINS:**
9. Data Science & Analytics (Pandas, NumPy, R, Tableau, Power BI, Jupyter, etc.)
10. Machine Learning & AI (TensorFlow, PyTorch, Scikit-learn, OpenAI, Computer Vision, NLP, etc.)
11. Cybersecurity (Penetration Testing, OWASP, Cryptography, Network Security, etc.)
12. Game Development (Unity, Unreal Engine, Godot, etc.)
13. Blockchain & Crypto (Ethereum, Solidity, Web3, Smart Contracts, etc.)

**DEVELOPMENT PRACTICES:**
14. Software Architecture (Microservices, SOA, Design Patterns, Clean Code, etc.)
15. Testing & QA (Unit Testing, Integration Testing, Selenium, Jest, Pytest, etc.)
16. Version Control & Collaboration (Git, GitHub, GitLab, SVN, Agile, Scrum, etc.)
17. API Development (REST, GraphQL, gRPC, WebSockets, etc.)

**EMERGING TECHNOLOGIES:**
18. IoT & Embedded Systems (Arduino, Raspberry Pi, Sensors, etc.)
19. AR/VR Development (ARKit, ARCore, Oculus, etc.)
20. Big Data Technologies (Hadoop, Spark, Kafka, Storm, etc.)

CV Content:
{cv_content}

Extract 10-15 technical keywords that would be most relevant for a comprehensive technical interview. Return them as a comma-separated list, formatted properly (e.g., "Python, React, Machine Learning, AWS, Docker").

Prioritize:
- Technologies with demonstrated experience (projects, years of experience)
- Skills mentioned multiple times or described in detail
- Technologies that appear in work experience vs. just "familiar with"
- Core competencies vs. peripheral mentions

Technical Keywords:"""
