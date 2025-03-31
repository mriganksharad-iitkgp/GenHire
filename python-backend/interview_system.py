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

# Llama Index & Groq imports
from llama_index.core.node_parser import SentenceWindowNodeParser
from llama_index.llms.groq import Groq
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex

# Deepeval imports
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval import evaluate
from deepeval.test_case import LLMTestCase
from deepeval.metrics import AnswerRelevancyMetric

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# ----------------- Text Extraction Functions -----------------

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
    """
    Computes cosine similarity between a CV and JD document.
    """
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

# ----------------- Refactored Classes -----------------

class LLMEngine:
    def __init__(self, model_name, api_key):
        self.llm = Groq(model=model_name, api_key=api_key)

    def complete(self, prompt):
        response = self.llm.complete(prompt)
        return response.text if hasattr(response, 'text') else str(response)

class DocumentLoader:
    """
    Loads the candidate CV and JD using provided file paths.
    For the reference document(s), it uses a directory path.
    """
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
        # Initialize a sentence transformer model for embeddings
        self.sentence_transformer = SentenceTransformer("all-MiniLM-L6-v2")

    def get_random_non_contextual_question(self):
        questions = [
            "Can you discuss a recent project where you overcame significant challenges?",
            "What are your core strengths and weaknesses in a professional setting?",
            "How do you stay updated with industry trends and best practices?",
            "Tell me about a time when you had to learn a new technology quickly.",
            "How do you approach working in a team with diverse perspectives?",
            "What's your process for solving complex problems?",
            "How do you handle feedback and criticism?",
            "What motivates you professionally?",
            "Describe a situation where you had to adapt to changing requirements.",
            "How do you prioritize tasks when facing multiple deadlines?"
        ]
        return random.choice(questions)

    def retrieve_relevant_context_with_window(self, question, cv_text, reference_material, window_size=5):
        context_windows = []
        cv_sentences = cv_text.split('.')
        reference_sentences = "\n".join([doc.text for doc in reference_material]).split('.')
        all_sentences = cv_sentences + reference_sentences

        # Create windows of text using SentenceWindowNodeParser
        node_parser = SentenceWindowNodeParser.from_defaults(window_size=window_size)
        for i in range(0, len(all_sentences), window_size):
            context_windows.append(' '.join(all_sentences[i:i+window_size]))

        query_prompt = f"Given the following question: '{question}', which windows of text are most relevant?"
        relevant_context = self.llm.complete(query_prompt)
        return relevant_context

    def query_with_sentence_window(self, query_text, sentence_window_size=5, similarity_top_k=6, rerank_top_n=2):
        # Generate question embeddings using the sentence transformer
        query_embedding = self.sentence_transformer.encode(query_text)
        
        # Create text chunks from documents with window_size
        document_chunks = []
        for doc in self.documents:
            sentences = doc.text.split('.')
            for i in range(0, len(sentences), sentence_window_size):
                chunk = ' '.join(sentences[i:i+sentence_window_size])
                if len(chunk) > 20:  # Avoid too small chunks
                    document_chunks.append(chunk)
        
        # Generate embeddings for all document chunks
        document_embeddings = self.sentence_transformer.encode(document_chunks)
        
        # Calculate cosine similarities
        similarities = cosine_similarity([query_embedding], document_embeddings)[0]
        
        # Get the most similar chunks
        top_indices = np.argsort(similarities)[-similarity_top_k:]
        top_chunks = [document_chunks[i] for i in top_indices]
        
        # Generate a response based on the top chunks
        context = "\n".join(top_chunks) 
        response_prompt = f"""Based on the following context, answer this question: {query_text}
        
Context:
{context}

Answer:"""
        response = self.llm.complete(response_prompt)
        
        # Return response as a list for API compatibility
        return response.split("\n") if isinstance(response, str) else [str(response)]

    def generate_initial_questions(self, cv_text, jd_text):
        """Generate initial interview questions based on CV and JD"""
        query_text = f"""You are conducting an in-depth interview based on the following documents:

Candidate's CV:
{cv_text}

Job Description:
{jd_text}

Generate 5 structured interview questions that assess the candidate's experience, problem-solving ability, and alignment with the role. Return ONLY the questions as a numbered list.
"""
        response = self.llm.complete(query_text)
        
        # Parse questions into a list
        questions = []
        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            # Skip empty lines and lines without question content
            if not line or not any(c.isalpha() for c in line):
                continue
            # Clean up numbering and formatting
            cleaned_line = re.sub(r'^\d+[\.\)]\s*', '', line).strip()
            if cleaned_line:
                questions.append(cleaned_line)
        
        return questions

class InterviewSessionManager:
    """Manages interview sessions through API interactions"""
    def __init__(self):
        self.active_sessions = {}
        self.llama_api_key = "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"
        self.eval_api_key = "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"
        self.max_questions = 8  # Maximum number of questions before auto-ending
    
    def create_session(self, cv_path, jd_path, reference_path):
        """Create a new interview session"""
        session_id = str(random.randint(10000, 99999))
        
        # Initialize LLM engine
        llm_engine = LLMEngine(model_name="llama-3.3-70b-versatile", api_key=self.llama_api_key)
        
        # Load documents
        document_loader = DocumentLoader(cv_path=cv_path, jd_path=jd_path, reference_path=reference_path)
        
        # Initialize question generator
        question_generator = InterviewQuestionGenerator(llm=llm_engine, documents=document_loader.documents)
        
        # Generate initial questions
        initial_questions = question_generator.generate_initial_questions(
            document_loader.cv_text, 
            document_loader.jd_text
        )
        
        # Create session data
        self.active_sessions[session_id] = {
            "llm_engine": llm_engine,
            "document_loader": document_loader,
            "question_generator": question_generator,
            "interview_data": [],
            "interview_history": "",
            "current_questions": initial_questions,
            "cv_path": cv_path,
            "jd_path": jd_path,
            "reference_path": reference_path,
            "questions_asked": 0,  # Track number of questions asked
            "is_complete": False  # Flag to track if interview is complete
        }
        
        # Calculate similarity score
        similarity = compute_cosine_similarity(cv_path, jd_path)
        
        return {
            "session_id": session_id,
            "initial_questions": initial_questions,
            "similarity_score": float(similarity)
        }
    
    def get_session(self, session_id):
        """Get session data by ID"""
        session = self.active_sessions.get(session_id)
        if not session:
            return None
        
        return {
            "session_id": session_id,
            "current_questions": session["current_questions"],
            "interview_data_count": len(session["interview_data"]),
            "cv_path": session["cv_path"],
            "jd_path": session["jd_path"]
        }
    
    def submit_answer(self, session_id, question, answer):
        """Process a candidate's answer and generate follow-up questions"""
        session = self.active_sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}
        
        if session.get("is_complete", False):
            return {"error": "Interview is already complete", "should_end": True}
        
        # Get components from session
        llm_engine = session["llm_engine"]
        document_loader = session["document_loader"]
        question_generator = session["question_generator"]
        
        # Retrieve context for evaluation
        relevant_context = question_generator.retrieve_relevant_context_with_window(
            question, 
            document_loader.cv_text, 
            document_loader.documents
        )
        
        # Generate reference answer
        answer_prompt = f"Using the following context:\n{relevant_context}\nProvide a detailed and thoughtful answer for the following question:\n{question}"
        generated_answer = llm_engine.complete(answer_prompt)
        
        # Save Q&A data
        qa_data = {
            'question': question,
            'user_answer': answer,
            'generated_answer': generated_answer,
            'relevant_context': relevant_context,
            'timestamp': str(np.datetime64('now'))
        }
        
        session["interview_data"].append(qa_data)
        session["interview_history"] += f"Q: {question}\nA: {answer}\n"
        
        # Increment question counter
        session["questions_asked"] = session.get("questions_asked", 0) + 1
        
        # Check if we've reached the maximum number of questions
        if session["questions_asked"] >= self.max_questions:
            session["is_complete"] = True
            evaluation_results = self._generate_final_evaluation(session)
            return {
                "next_question": "Thank you for completing all the interview questions. The interview is now finished.",
                "evaluation": {
                    "relevance_score": self._calculate_basic_relevance(answer, generated_answer),
                    "depth": len(answer.split()) / max(1, len(generated_answer.split())),
                    "feedback": self._generate_quick_feedback(answer, generated_answer)
                },
                "interview_complete": True,
                "final_evaluation": evaluation_results
            }
        
        # Summarize the interview so far
        summary_prompt = f"Summarize the following interview transcript concisely: {session['interview_history']}"
        summary = llm_engine.complete(summary_prompt)
        
        # Decide on follow-up question
        if random.random() < 0.8:  # 80% chance of contextual follow-up
            followup_prompt = f"""Based on the interview so far: '{summary}', generate the next best follow-up question that builds on previous answers and digs deeper.

IMPORTANT: Return ONLY the question itself with no explanation, reasoning, or additional text. The question should be clear, concise, and professional."""
            next_question = llm_engine.complete(followup_prompt)
            # Clean any remaining explanations or numbering that might still be present
            next_question = re.sub(r'^.*?(Question:|"|\n)', '', next_question, flags=re.DOTALL).strip()
            next_question = re.sub(r'(\?|\.)"?$.*', r'\1', next_question, flags=re.DOTALL).strip()
        else:  # 20% chance of non-contextual question
            next_question = question_generator.get_random_non_contextual_question()
        
        # Update session with new question
        session["current_questions"] = [next_question]
        
        # Add countdown message as we approach the end
        remaining_questions = self.max_questions - session["questions_asked"]
        countdown_message = ""
        if remaining_questions <= 3:
            countdown_message = f" ({remaining_questions} question{'s' if remaining_questions != 1 else ''} remaining)"
        
        return {
            "next_question": next_question + countdown_message,
            "evaluation": {
                "relevance_score": self._calculate_basic_relevance(answer, generated_answer),
                "depth": len(answer.split()) / max(1, len(generated_answer.split())),
                "feedback": self._generate_quick_feedback(answer, generated_answer)
            },
            "questions_remaining": remaining_questions
        }
    
    def _calculate_basic_relevance(self, user_answer, reference_answer):
        """Calculate basic relevance score between user answer and reference answer"""
        # Use sentence transformer for semantic similarity
        model = SentenceTransformer("all-MiniLM-L6-v2")
        user_embedding = model.encode([user_answer])
        ref_embedding = model.encode([reference_answer])
        
        # Calculate cosine similarity
        similarity = cosine_similarity(user_embedding, ref_embedding)[0][0]
        return float(similarity)
    
    def _generate_quick_feedback(self, user_answer, reference_answer):
        """Generate quick feedback on user's answer"""
        prompt = f"""Compare the candidate's answer with the reference answer and provide brief feedback:
        
Candidate Answer: {user_answer}
Reference Answer: {reference_answer}

Provide a one-sentence assessment of the candidate's answer in terms of relevance and completeness:"""
        
        feedback_llm = LLMEngine(model_name="llama-3.3-70b-versatile", api_key=self.llama_api_key)
        feedback = feedback_llm.complete(prompt)
        return feedback

    def end_session(self, session_id):
        """End interview session and generate final evaluation"""
        session = self.active_sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}
        
        # Generate overall evaluation
        evaluation_results = self._generate_final_evaluation(session)
        
        # Clean up session (optionally keep for history)
        # del self.active_sessions[session_id]
        
        return {
            "session_id": session_id,
            "evaluation": evaluation_results,
            "interview_data_count": len(session["interview_data"])
        }
    
    def _generate_final_evaluation(self, session):
        """Generate final evaluation of the interview"""
        interview_data = session["interview_data"]
        if not interview_data:
            return {"error": "No interview data available"}
        
        # Basic evaluation
        total_answers = len(interview_data)
        total_score = 0
        answer_scores = []
        
        for qa in interview_data:
            relevance = self._calculate_basic_relevance(qa['user_answer'], qa['generated_answer'])
            total_score += relevance
            answer_scores.append(relevance)
        
        avg_score = total_score / total_answers if total_answers > 0 else 0
        
        # Full evaluation with LLM
        prompt = f"""You are an expert HR interviewer. Review this interview and provide an assessment:

Interview Transcript:
{session["interview_history"]}

Provide a structured evaluation with:
1. Overall impression (1-2 sentences)
2. Key strengths demonstrated (bullet points)
3. Areas for improvement (bullet points)
4. Fit for role (good/moderate/needs work)
"""
        
        feedback_llm = LLMEngine(model_name="llama-3.3-70b-versatile", api_key=self.llama_api_key)
        qualitative_assessment = feedback_llm.complete(prompt)
        
        return {
            "quantitative": {
                "average_relevance_score": float(avg_score),
                "number_of_questions": total_answers,
                "question_scores": answer_scores
            },
            "qualitative_assessment": qualitative_assessment
        }

# Singleton instance of the session manager
session_manager = InterviewSessionManager() 