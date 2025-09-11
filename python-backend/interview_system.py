import warnings
import os
import random
import re
import string
import torch
from nltk import pos_tag, sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from pypdf import PdfReader
from transformers import AutoModel, AutoTokenizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from sentence_transformers import SentenceTransformer

# Llama Index & Groq imports (only what's necessary)
from llama_index.llms.groq import Groq
from llama_index.core import SimpleDirectoryReader

# Suppress specific warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# ----------------- Text Extraction & Processing Functions -----------------

def segregate_resume_text(text):
    """
    Segregates resume text into sections using rule-based keyword matching.
    """
    section_keywords = {
        'experience': ['professional experience', 'work experience', 'experience', 'employment history', 'career'],
        'education': ['education', 'academic background', 'academic qualifications'],
        'skills': ['skills', 'technical skills', 'proficiencies', 'expertise'],
        'projects': ['projects', 'personal projects', 'portfolio']
    }

    lines = text.lower().split('\n')
    resume_sections = {}
    current_section = 'header'  # Start with a default header section
    resume_sections[current_section] = ""

    for line in lines:
        if not line.strip():
            continue

        found_section = False
        for section, keywords in section_keywords.items():
            for keyword in keywords:
                if keyword in line:
                    current_section = section
                    if current_section not in resume_sections:
                        resume_sections[current_section] = ""
                    found_section = True
                    break
            if found_section:
                break

        resume_sections[current_section] += line + "\n"

    return resume_sections

def extract_text_from_pdf(file_path):
    reader = PdfReader(file_path)
    text = "".join(page.extract_text() for page in reader.pages if page.extract_text())
    return text

def preprocess_text(text):
    text = text.lower()
    text = re.sub('[^a-zA-Z]', ' ', text)
    sentences = sent_tokenize(text)
    features = ""
    stop_words = set(stopwords.words("english"))
    for sent in sentences:
        words = word_tokenize(sent)
        words = [word for word in words if word not in stop_words and word not in string.punctuation]
        tagged_words = pos_tag(words)
        filtered_words = [word for word, tag in tagged_words if tag not in ['DT', 'IN', 'TO', 'PRP', 'WP']]
        features += " ".join(filtered_words) + " "
    return features.strip()

def get_embeddings(text, model, tokenizer, device):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=512).to(device)
    outputs = model(**inputs)
    embeddings = outputs.last_hidden_state.mean(dim=1).detach().cpu().numpy()
    return embeddings

def compute_cosine_similarity(cv_pdf, jd_pdf):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model_name = "bert-base-uncased"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name).to(device)
    cv_text = extract_text_from_pdf(cv_pdf)
    jd_text = extract_text_from_pdf(jd_pdf)
    cv_features = preprocess_text(cv_text)
    jd_features = preprocess_text(jd_text)
    cv_embedding = get_embeddings(cv_features, model, tokenizer, device)
    jd_embedding = get_embeddings(jd_features, model, tokenizer, device)
    similarity_score = cosine_similarity(cv_embedding, jd_embedding)[0][0]
    return similarity_score

# ----------------- Core Interview Classes -----------------

class LLMEngine:
    def __init__(self, model_name, api_key):
        self.llm = Groq(model=model_name, api_key=api_key)

    def complete(self, prompt):
        response = self.llm.complete(prompt)
        return response.text if hasattr(response, 'text') else str(response)

class DocumentLoader:
    def __init__(self, cv_path, jd_path, reference_path):
        self.cv_text = extract_text_from_pdf(cv_path)
        self.jd_text = extract_text_from_pdf(jd_path)
        self.documents = SimpleDirectoryReader(input_files=[reference_path]).load_data()
        self.cv_path = cv_path
        self.jd_path = jd_path
        self.reference_path = reference_path

class InterviewQuestionGenerator:
    def __init__(self, llm, documents):
        self.llm = llm
        self.documents = documents
        self.sentence_transformer = SentenceTransformer("all-MiniLM-L6-v2")

    def retrieve_relevant_context_with_window(self, question, cv_text, reference_material, window_size=5):
        all_text = cv_text + "\n" + "\n".join([doc.text for doc in reference_material])
        sentences = all_text.split('.')
        if len(sentences) < window_size:
            return ' '.join(sentences)
        query_words = set(question.lower().split())
        best_chunk = ""
        max_overlap = 0
        for i in range(len(sentences) - window_size + 1):
            chunk = ' '.join(sentences[i:i+window_size])
            overlap = len(query_words.intersection(chunk.lower().split()))
            if overlap > max_overlap:
                max_overlap = overlap
                best_chunk = chunk
        return best_chunk if best_chunk else ' '.join(sentences[:window_size])

    def generate_questions_from_section(self, section_name, section_text, num_questions=2):
        """Generates targeted questions from a specific resume section."""
        prompt = f"""You are an expert technical interviewer. Based on the following "{section_name}" section from a candidate's resume, generate {num_questions} insightful interview questions that probe their skills and experience in this area.

Resume Section Content:
---
{section_text}
---

Return ONLY the questions as a numbered list.
"""
        response = self.llm.complete(prompt)
        questions = []
        for line in response.split('\n'):
            if re.match(r'^\s*\d+[\.\)]', line.strip()):
                question_text = re.sub(r'^\s*\d+[\.\)]\s*', '', line).strip()
                if question_text:
                    questions.append(question_text)
        return questions

class InterviewSessionManager:
    """Manages interview sessions with targeted questions and dynamic follow-ups."""
    def __init__(self):
        self.active_sessions = {}
        # It's better to get the API key from environment variables in a real app
        self.llama_api_key = os.getenv("GROQ_API_KEY", "YOUR_FALLBACK_GROQ_API_KEY")
        self.max_questions = 8
        os.environ["GROQ_API_KEY"] = self.llama_api_key

    def create_session(self, cv_path, jd_path, reference_path):
        session_id = str(random.randint(10000, 99999))
        llm_engine = LLMEngine(model_name="llama3-70b-8192", api_key=self.llama_api_key)
        document_loader = DocumentLoader(cv_path=cv_path, jd_path=jd_path, reference_path=reference_path)
        resume_sections = segregate_resume_text(document_loader.cv_text)
        
        question_generator = InterviewQuestionGenerator(llm=llm_engine, documents=document_loader.documents)
        
        initial_questions = []
        if 'experience' in resume_sections and resume_sections['experience'].strip():
            initial_questions = question_generator.generate_questions_from_section(
                'Work Experience', resume_sections['experience'], num_questions=3
            )
        else:
            # Fallback for resumes without a clear 'experience' section
            prompt = f"Generate 3 general technical interview questions based on this job description: {document_loader.jd_text}"
            response = llm_engine.complete(prompt)
            initial_questions = [line.strip() for line in response.split('\n') if line.strip()]

        self.active_sessions[session_id] = {
            "llm_engine": llm_engine,
            "document_loader": document_loader,
            "question_generator": question_generator,
            "resume_sections": resume_sections,
            "interview_data": [],
            "interview_history": "",
            "current_questions": initial_questions,
            "questions_asked": 0,
            "is_complete": False
        }
        similarity = compute_cosine_similarity(cv_path, jd_path)
        return {"session_id": session_id, "initial_questions": initial_questions, "similarity_score": float(similarity)}

    def _calculate_basic_relevance(self, user_answer, reference_answer):
        model = SentenceTransformer("all-MiniLM-L6-v2")
        user_embedding = model.encode([user_answer])
        ref_embedding = model.encode([reference_answer])
        similarity = cosine_similarity(user_embedding, ref_embedding)[0][0]
        return float(similarity)

    def _generate_quick_feedback(self, llm_engine, question, answer):
        prompt = f"""You are an expert interview coach. The question was "{question}" and the candidate answered "{answer}". Provide one sentence of constructive feedback."""
        feedback = llm_engine.complete(prompt)
        return feedback

    def submit_answer(self, session_id, question, answer):
        session = self.active_sessions.get(session_id)
        if not session or session.get("is_complete"):
            return {"error": "Session not found or is complete."}

        llm_engine = session["llm_engine"]
        document_loader = session["document_loader"]

        retrieval_context = session["question_generator"].retrieve_relevant_context_with_window(
            question, document_loader.cv_text, document_loader.documents
        )
        expected_output = llm_engine.complete(f"Context: {retrieval_context}\nQuestion: {question}\nAnswer:")

        relevance_score = self._calculate_basic_relevance(answer, expected_output)
        qualitative_feedback = self._generate_quick_feedback(llm_engine, question, answer)

        session["interview_history"] += f"Q: {question}\nA: {answer}\n"
        session["questions_asked"] += 1

        turn_output = {
            "input": question, "actual_output": answer, "expected_output": expected_output,
            "retrieval_context": retrieval_context,
            "evaluation": {
                "metric": "Cosine Similarity",
                "relevance_score": relevance_score,
                "feedback": qualitative_feedback
            }
        }

        if session["questions_asked"] >= self.max_questions:
            session["is_complete"] = True
            turn_output["interview_complete"] = True
            turn_output["final_evaluation"] = self._generate_final_evaluation(session)
            return turn_output

        summary_prompt = f"Summarize this interview transcript concisely: {session['interview_history']}"
        summary = llm_engine.complete(summary_prompt)
        followup_prompt = f"Based on the interview summary: '{summary}', generate the next best follow-up question. Return ONLY the question."
        next_question = llm_engine.complete(followup_prompt).strip()

        session["current_questions"] = [next_question]
        turn_output["next_question"] = next_question
        return turn_output

    def _generate_final_evaluation(self, session):
        prompt = f"""You are an expert HR interviewer. Review this interview transcript and provide a structured evaluation:
        Transcript:\n{session["interview_history"]}
        Provide:
        1. Overall impression
        2. Key strengths
        3. Areas for improvement
        4. Role fit"""
        return session["llm_engine"].complete(prompt)

# Singleton instance of the session manager
session_manager = InterviewSessionManager()