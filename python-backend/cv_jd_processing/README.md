# 📄 CV-JD Scoring API

This project is an **AI-powered Resume–Job Description (CV–JD) Scoring API**.
It parses PDF documents (resumes and job descriptions), extracts their content, and then uses **Google’s Gemini LLM** to evaluate how well the candidate’s CV aligns with the given JD.

The output is returned in **JSON format**, including:

* A **score breakdown** (per rubric category)
* A **total alignment score (out of 100)**

This can be integrated into any website or platform for **automated candidate screening**.

---

## 🚀 Tech Stack

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

### Endpoint: `/score/`

**Method**: `POST`
**Parameters**:

* `cv`: Resume file (PDF)
* `jd`: Job description file (PDF)

**Example with cURL**:

```bash
curl -X POST "http://127.0.0.1:8000/score/" \
  -F "cv=@resume.pdf" \
  -F "jd=@job_description.pdf"
```

**Response (JSON Example)**:

```json
{
  "score_breakdown": {
    "Core Technical Skills": { "score": 8, "reasoning": "Candidate knows Python and TensorFlow, matching JD." },
    "Domain Knowledge": { "score": 7, "reasoning": "Relevant coursework in AI/ML." }
  },
  "total_score": 76
}
```

---

## 🌐 Deployment Notes

* Can be hosted on **AWS / GCP / Azure** with Docker or serverless options.
* Requires **valid API keys** for `LlamaParse` and `Google Generative AI`.
* Secure `.env` file and never commit it to GitHub.
