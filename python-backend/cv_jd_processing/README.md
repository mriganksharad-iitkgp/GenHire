# CV-JD Scoring API

This project is an **AI-powered Resume–Job Description (CV–JD) Scoring API**.
It supports both PDF parsing and **text-based CV-JD matching** for automated candidate screening.

## **NEW: Text-Based CV Scoring Integration**

The system now includes a **CVScoringService** that works directly with structured CV data and job descriptions in text format, eliminating the need for PDF processing in the main HR application.

### Features:
* **Automated CV-JD matching** during job applications
* **10-category scoring rubric** with detailed breakdown
* **Fallback scoring** for error handling
* **API endpoint** for recalculating existing application scores
* **Migration utility** for updating legacy applications

The output is returned in **JSON format**, including:

* A **score breakdown** (per rubric category)
* A **total alignment score (out of 100)**
* **Detailed reasoning** for each category score

This can be integrated into any website or platform for **automated candidate screening**.

---

## Tech Stack

* **[FastAPI](https://fastapi.tiangolo.com/)** → for building the REST API.
* **[llama-parse](https://llama.cloud/)** → to parse and extract text from PDF files.
* **[Google Generative AI](https://ai.google.dev/)** → Gemini model for evaluation & scoring.
* **[LangChain](https://www.langchain.com/)** (`langchain-google-genai`) → wrapper to interact with Google LLMs.
* **[python-dotenv](https://pypi.org/project/python-dotenv/)** → to load environment variables securely.
* **[Uvicorn](https://www.uvicorn.org/)** → ASGI server for running FastAPI apps.

---

## ⚙️ Environment Setup

### 1. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate   # On Mac/Linux
venv\Scripts\activate      # On Windows
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Variables

Create a `.env` file in the project root with the following variables:

```env
parser_api_key=YOUR_LLAMA_PARSE_API_KEY
GOOGLE_API_KEY=YOUR_GOOGLE_GENAI_API_KEY
```

* `parser_api_key` → API key for **LlamaParse** service (to parse PDF).
* `GOOGLE_API_KEY` → API key for **Google Generative AI** (Gemini).

---

## ▶️ Running the API

Start the FastAPI server:

```bash
uvicorn cv_jd_matching:app --reload
```

* Here, `cv_jd_matching` is the Python filename (`cv_jd_matching.py`).
* `--reload` enables hot reloading during development.

---

## 📡 API Usage

### Endpoint: `/score/` (PDF-based)

**Method**: `POST`
**Parameters**:

* `cv`: Resume file (PDF)
* `jd`: Job description file (PDF)

### Endpoint: `/score-text/` (Text-based)

**Method**: `POST`
**Content-Type**: `application/json`
**Body**:

```json
{
  "cv_text": "Formatted CV text content",
  "jd_text": "Formatted job description text"
}
```

**Example with cURL**:

```bash
curl -X POST "http://127.0.0.1:8000/score-text/" \
  -H "Content-Type: application/json" \
  -d '{
    "cv_text": "John Doe\nSoftware Engineer\nSkills: Python, JavaScript...",
    "jd_text": "Job Title: Senior Developer\nRequirements: Python, React..."
  }'
```

**Response (JSON Example)**:

```json
{
  "score_breakdown": {
    "Core Technical Skills": { "score": 8, "reasoning": "Candidate knows Python and TensorFlow, matching JD." },
    "Domain Knowledge": { "score": 7, "reasoning": "Relevant coursework in AI/ML." },
    "Educational Background": { "score": 8, "reasoning": "Computer Science degree aligns with requirements." }
  },
  "total_score": 76
}
```

## 🔧 Integration with HR Application

The CV scoring service is now integrated into the main HR application:

### New Features:
* **Automatic CV scoring** during job applications
* **Score breakdown storage** in application records
* **Recalculate scores** API endpoint: `POST /api/applications/{id}/recalculate-score`
* **Migration utility** for existing applications

### Scoring Rubrics (10 points each):
1. **Core Technical Skills** - Programming languages, frameworks, tools
2. **Domain Knowledge** - Industry/domain relevance
3. **Educational Background** - Degree alignment with requirements
4. **Work Experience Relevance** - Years and role alignment
5. **Project/Research Experience** - Academic/industrial projects
6. **Tools & Platforms** - Databases, cloud services, ML libraries
7. **Certifications & Training** - Professional certifications
8. **Publications/Competitions/Achievements** - Technical recognition
9. **Problem-Solving & Analytical Skills** - Evidence from projects
10. **Overall Fit for Role** - Aggregate technical alignment

---

## 🌐 Deployment Notes

* Can be hosted on **AWS / GCP / Azure** with Docker or serverless options.
* Requires **valid API keys** for `LlamaParse` and `Google Generative AI`.
* Secure `.env` file and never commit it to GitHub.
