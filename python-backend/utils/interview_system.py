import os
import random
import re
import string
import uuid
import warnings
import torch
import numpy as np

from nltk import pos_tag, sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from pypdf import PdfReader
from transformers import AutoModel, AutoTokenizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

from llama_index.core import SimpleDirectoryReader
from llama_index.llms.groq import Groq

# Suppress specific warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# ----------------- Text Extraction and Similarity Functions -----------------
def extract_text_from_pdf(file_path):
    """Extracts text from a PDF file."""
    if not os.path.exists(file_path):
        print(f"Warning: PDF file not found at {file_path}")
        return ""
    reader = PdfReader(file_path)
    text = "".join(page.extract_text() for page in reader.pages if page.extract_text())
    return text

def preprocess_text(text):
    """Preprocesses text for embedding by cleaning and filtering words."""
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
    """Generates embeddings for a given text using a transformer model."""
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=512).to(device)
    with torch.no_grad():
        outputs = model(**inputs)
    embeddings = outputs.last_hidden_state.mean(dim=1).cpu().numpy()
    return embeddings

def compute_cosine_similarity(cv_pdf, jd_pdf, model, tokenizer):
    """Computes cosine similarity between a CV and a Job Description."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device) # Ensure model is on the correct device
    try:
        cv_text = extract_text_from_pdf(cv_pdf)
        jd_text = extract_text_from_pdf(jd_pdf)
        if not cv_text or not jd_text:
            return 0.0
        cv_features = preprocess_text(cv_text)
        jd_features = preprocess_text(jd_text)
        cv_embedding = get_embeddings(cv_features, model, tokenizer, device)
        jd_embedding = get_embeddings(jd_features, model, tokenizer, device)
        similarity_score = cosine_similarity(cv_embedding, jd_embedding)[0][0]
        return float(similarity_score)
    except Exception as e:
        print(f"Error computing similarity: {e}")
        return 0.0

def segregate_resume_text(text):
    """Segregates resume text into standard sections."""
    section_keywords = {
        'experience': ['professional experience', 'work experience', 'experience', 'employment history', 'career'],
        'education': ['education', 'academic background', 'academic qualifications'],
        'skills': ['skills', 'technical skills', 'proficiencies', 'expertise'],
        'projects': ['projects', 'personal projects', 'portfolio']
    }
    lines = text.lower().split('\n')
    resume_sections = {}
    current_section = 'header'
    resume_sections[current_section] = ""
    for line in lines:
        if not line.strip(): continue
        found_section = False
        for section, keywords in section_keywords.items():
            for keyword in keywords:
                if keyword in line:
                    current_section = section
                    if current_section not in resume_sections:
                        resume_sections[current_section] = ""
                    found_section = True
                    break
            if found_section: break
        resume_sections[current_section] += line + "\n"
    return resume_sections

# ----------------- Core Interview Classes -----------------

class LLMEngine:
    """Wrapper for the Groq LLM."""
    def __init__(self, model_name, api_key):
        self.llm = Groq(model=model_name, api_key=api_key)

    def complete(self, prompt):
        response = self.llm.complete(prompt)
        return response.text if hasattr(response, 'text') else str(response)

class DocumentLoader:
    """Loads and holds text from CV, JD, and reference documents."""
    def __init__(self, cv_path, jd_path, reference_paths): # <-- FIX IS HERE
        self.cv_text = extract_text_from_pdf(cv_path)
        self.jd_text = extract_text_from_pdf(jd_path)
        # Handle single or multiple reference paths
        paths = [reference_paths] if isinstance(reference_paths, str) else reference_paths
        self.documents = SimpleDirectoryReader(input_files=paths).load_data()
        self.cv_path = cv_path
        self.jd_path = jd_path
        self.reference_paths = reference_paths

class InterviewQuestionGenerator:
    """Generates technical questions based on resume content and reference material."""
    def __init__(self, llm, documents):
        self.llm = llm
        self.documents = documents
        self.sentence_transformer = SentenceTransformer("all-MiniLM-L6-v2")

    def _extract_keywords_from_text(self, text):
        """Uses the LLM to extract key technical terms from text."""
        prompt = f"""From the following text, extract a list of the most important technical skills, frameworks, and concepts. Return them as a simple comma-separated list.
        Text: --- {text} --- Keywords:"""
        response = self.llm.complete(prompt)
        return [keyword.strip() for keyword in response.split(',') if keyword.strip()]

    def retrieve_relevant_context_with_window(self, question, cv_text, reference_material, window_size=5):
        """Retrieves a relevant chunk of text to help answer a question."""
        all_text = cv_text + "\n" + "\n".join([doc.text for doc in reference_material])
        sentences = all_text.split('.')
        if len(sentences) < window_size: return ' '.join(sentences)
        query_words = set(question.lower().split())
        best_chunk, max_overlap = "", 0
        for i in range(len(sentences) - window_size + 1):
            chunk = ' '.join(sentences[i:i+window_size])
            overlap = len(query_words.intersection(chunk.lower().split()))
            if overlap > max_overlap:
                max_overlap, best_chunk = overlap, chunk
        return best_chunk if best_chunk else ' '.join(sentences[:window_size])

    def generate_initial_questions(self, resume_sections, sections_to_probe, total_questions=4):
        """Generates a batch of initial technical questions from multiple resume sections in one go."""
        
        combined_text = ""
        for section_key in sections_to_probe:
            if section_key in resume_sections:
                combined_text += f"--- From {section_key.upper()} Section ---\n"
                combined_text += resume_sections[section_key] + "\n\n"

        if not combined_text:
            return []

        prompt = f"""You are an expert technical interviewer reviewing a candidate's resume.
        Based on the following combined text from their 'experience' and 'skills' sections, generate {total_questions} diverse, theoretical, or definition-based technical questions.

        *IMPORTANT INSTRUCTIONS:*
        - DO NOT ask about personal experience (e.g., "Tell me about a project...").
        - DO ask for definitions, comparisons, or explanations of core concepts (e.g., "What is the difference between L1 and L2 regularization?").
        - Ensure the questions cover a range of topics mentioned in the text.
        - Return ONLY the questions as a numbered list.

        Resume Text:
        {combined_text}
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
    """Manages the state and flow of an entire interview session."""
    def __init__(self, groq_api_key, similarity_model, similarity_tokenizer):
        self.sessions = {}
        self.groq_api_key = groq_api_key
        self.max_questions = 8
        self.similarity_model = similarity_model
        self.similarity_tokenizer = similarity_tokenizer
        os.environ["GROQ_API_KEY"] = groq_api_key

    def create_session(self, cv_path, jd_path, reference_paths): # <-- FIX IS HERE
        session_id = str(uuid.uuid4())
        llm_engine = LLMEngine(model_name="llama-3.1-70b-versatile", api_key=self.groq_api_key)
        document_loader = DocumentLoader(cv_path=cv_path, jd_path=jd_path, reference_paths=reference_paths) # <-- FIX IS HERE
        resume_sections = segregate_resume_text(document_loader.cv_text)
        question_generator = InterviewQuestionGenerator(llm=llm_engine, documents=document_loader.documents)
        
        # --- OPTIMIZED QUESTION GENERATION ---
        sections_to_probe = ['experience', 'skills']
        initial_questions = question_generator.generate_initial_questions(resume_sections, sections_to_probe, total_questions=4)
        
        if not initial_questions:
            initial_questions.append("Tell me about your background and experience.")

        self.sessions[session_id] = {
            "llm_engine": llm_engine, "document_loader": document_loader,
            "question_generator": question_generator, "interview_history": "",
            "current_questions": initial_questions, "questions_asked": 0,
            "is_complete": False, "interview_data": []
        }
        # --- OPTIMIZED SIMILARITY CALCULATION ---
        similarity = compute_cosine_similarity(cv_path, jd_path, self.similarity_model, self.similarity_tokenizer)
        return {"session_id": session_id, "initial_questions": initial_questions, "similarity_score": similarity}

    def _calculate_relevance(self, user_answer, reference_answer):
        model = SentenceTransformer("all-MiniLM-L6-v2")
        user_embedding = model.encode([user_answer])
        ref_embedding = model.encode([reference_answer])
        return float(cosine_similarity(user_embedding, ref_embedding)[0][0])

    def submit_answer(self, session_id, question, answer):
        session = self.sessions.get(session_id)
        if not session or session.get("is_complete"):
            return {"error": "Session not found or is complete."}

        llm = session["llm_engine"]
        docs = session["document_loader"]
        q_gen = session["question_generator"]

        context = q_gen.retrieve_relevant_context_with_window(question, docs.cv_text, docs.documents)
        expected_answer = llm.complete(f"Based on this context: {context}\nAnswer the question: {question}")
        relevance_score = self._calculate_relevance(answer, expected_answer)
        
        session["interview_history"] += f"Q: {question}\nA: {answer}\n"
        session["questions_asked"] += 1
        session["interview_data"].append({"question": question, "answer": answer, "relevance_score": relevance_score})

        if session["questions_asked"] >= self.max_questions:
            session["is_complete"] = True
            final_eval = self._generate_final_evaluation(session)
            return {"interview_complete": True, "evaluation": final_eval}

        summary = llm.complete(f"Summarize this interview transcript concisely: {session['interview_history']}")
        next_question = llm.complete(f"Based on the summary: '{summary}', generate the next best follow-up question. Return ONLY the question.").strip()
        
        session["current_questions"] = [next_question]
        return {"next_question": next_question, "interview_complete": False}

    def _generate_final_evaluation(self, session):
        avg_score = np.mean([item['relevance_score'] for item in session['interview_data']])
        qualitative_prompt = f"""As an expert HR analyst, review this interview transcript and provide a structured evaluation.
        Transcript:\n{session["interview_history"]}
        Provide a concise qualitative assessment covering overall impression, key strengths, and areas for improvement.
        Do not include a numeric score. Format the output as a single block of text with paragraphs."""
        qualitative_assessment = session["llm_engine"].complete(qualitative_prompt)
        
        return {
            "quantitative": {
                "average_relevance_score": avg_score,
                "number_of_questions": session["questions_asked"]
            },
            "qualitative_assessment": qualitative_assessment
        }