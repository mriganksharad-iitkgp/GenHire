import os
import random
import re
from nltk import pos_tag, sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from pypdf import PdfReader
from transformers import AutoModel, AutoTokenizer
from sklearn.metrics.pairwise import cosine_similarity
import torch
from sentence_transformers import SentenceTransformer
from llama_index.core import SimpleDirectoryReader
from llama_index.llms.groq import Groq

# Text processing functions
def extract_text_from_pdf(file_path):
    reader = PdfReader(file_path)
    text = "".join(page.extract_text() for page in reader.pages if page.extract_text())
    return text

def segregate_resume_text(text):
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

# Core classes
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
    
    def generate_questions_from_section(self, section_name, section_text, num_questions=2):
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
    def __init__(self, groq_api_key):
        self.active_sessions = {}
        self.llama_api_key = groq_api_key
        self.max_questions = 8
        os.environ["GROQ_API_KEY"] = groq_api_key
    
    # ... rest of the InterviewSessionManager implementation ...
    # (Copy the methods from your provided code)