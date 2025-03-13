import warnings
import os
import random
 
# Llama Index & Groq imports
from llama_index.core.node_parser import SentenceWindowNodeParser
from llama_index.llms.groq import Groq
from llama_index.core import SimpleDirectoryReader, ServiceContext, VectorStoreIndex, StorageContext, load_index_from_storage, Settings
from llama_index.core.indices.postprocessor import MetadataReplacementPostProcessor, SentenceTransformerRerank
 
from colorama import Fore, Style, init
 
# NLP and ML libraries for cosine similarity
import pandas as pd
from pypdf import PdfReader
from nltk import pos_tag, sent_tokenize, word_tokenize
from nltk.corpus import stopwords
import string
import re
import torch
from transformers import AutoModel, AutoTokenizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
 
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
init(autoreset=True)
 
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
    The JD document can be in PDF format.
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

# Predefined new question templates (for completely new questions)
new_question_templates = [
    "Can you share an example of a challenge you overcame in a similar role?",
    "What innovative approaches have you used to solve problems in your previous projects?",
    "How do you see your skills evolving in the coming years?",
    "What motivates you to continuously learn and adapt in your career?"
]
 
def summarize_previous(llm,questions):
    prompt = f"Summarize the following interview questions into a concise thematic summary: {questions}"
    summary_response = llm.complete(prompt)
    summary_text = summary_response if isinstance(summary_response, str) else str(summary_response)
    return summary_text if len(summary_text) < 100 else summary_text[:97] + "..."
 
def generate_contextual_questions(llm,initial_questions):
    contextual_questions = []
    all_previous_questions = []
    for i, question in enumerate(initial_questions):
        contextual_questions.append(f"{i+1}. {question}")
        all_previous_questions.append(question)
        if i > 0 and random.random() < 0.5:
            prev_summary = summarize_previous(llm,all_previous_questions[:-1])
            followup_prompt = (
                f"Based on the previous discussion: '{prev_summary}', create a specific follow-up question that references key details from the candidate’s response and encourages deeper insights into '{question}'."
            )
            followup_response = llm.complete(followup_prompt)
            followup_question = followup_response if isinstance(followup_response, str) else str(followup_response)
            contextual_questions.append(f"   ➔ Follow-up: {followup_question}")
        if random.random() < 0.3:
            new_q = random.choice(new_question_templates)
            contextual_questions.append(f"   ➔ New Question: {new_q}")
    return contextual_questions

def build_sentence_window_index(documents, save_dir):
    if not os.path.exists(save_dir):
        sentence_index = VectorStoreIndex.from_documents(documents)
        sentence_index.storage_context.persist(persist_dir=save_dir)
    else:
        sentence_index = load_index_from_storage(StorageContext.from_defaults(persist_dir=save_dir))
    return sentence_index

def get_sentence_window_query_engine(sentence_index, similarity_top_k, rerank_top_n):
    postproc = MetadataReplacementPostProcessor(target_metadata_key="window")
    rerank = SentenceTransformerRerank(top_n=rerank_top_n, model="BAAI/bge-reranker-base")
    sentence_window_engine = sentence_index.as_query_engine(
        similarity_top_k=similarity_top_k,
        node_postprocessors=[postproc, rerank]
    )
    return sentence_window_engine

class PDFProcessor:
    def __init__(self, document_pdf_path, groq_api_key):
        self.document_pdf_path = document_pdf_path
        self.llm = Groq(model="mixtral-8x7b-32768", api_key=groq_api_key)
        self.documents = self.load_documents()
    
    def load_documents(self):
        return SimpleDirectoryReader(input_files=[self.document_pdf_path]).load_data()
    
    def query_with_sentence_window(self, sentence_window_size, query_text,
                                   embed_model="local:BAAI/bge-small-en-v1.5", save_dir="sentence_index",
                                   similarity_top_k=6, rerank_top_n=2):
        Settings.llm = self.llm
        Settings.embed_model = embed_model
        Settings.node_parser = SentenceWindowNodeParser.from_defaults(
            window_size=sentence_window_size,
            window_metadata_key="window",
            original_text_metadata_key="original_text"
        )

        index = build_sentence_window_index(self.documents, save_dir=save_dir)
        query_engine = get_sentence_window_query_engine(index, similarity_top_k, rerank_top_n)
        response = query_engine.query(query_text)
        response_text = response.response if hasattr(response, 'response') else str(response)
        questions = response_text.split("\n")
        contextual_questions = generate_contextual_questions(self.llm,questions)
        return "\n".join(contextual_questions)
    
    def get_similarity(self, cv_pdf, jd_pdf):
        similarity = compute_cosine_similarity(cv_pdf, jd_pdf)
        return similarity
    
    def generate_initial_questions(self, jd_path, cv_path):
        jd_text = extract_text_from_pdf(jd_path)
        cv_text = extract_text_from_pdf(cv_path)

        # --- Generate Contextual Interview Questions ---
        query_text = f"""You are an expert interviewer with deep insights into both technical and behavioral interviewing.
            Based on the following two documents:
            
            Candidate's CV:
            {cv_text}
            
            Job Description:
            {jd_text}
            
            Generate a comprehensive set of interview questions that build on previous responses and ensure a logical follow-up.
            """
        interview_questions = self.query_with_sentence_window(
            sentence_window_size=5,
            query_text=query_text,
            embed_model="local:BAAI/bge-small-en-v1.5",
            save_dir="sentence_index",
            similarity_top_k=6,
            rerank_top_n=2
        )
        return interview_questions


# ----------------- Main Function -----------------
 
def main():
    document_pdf_path = "Eric Ries - The Lean Startup.pdf"  # Path to the document for querying
    groq_api_key = "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"  # Replace with actual API key

    processor = PDFProcessor(document_pdf_path, groq_api_key)
    # query_text = input("Please enter your query: ").strip()
    # response = processor.query_document(query_text)
    # print(Fore.GREEN + "Query Response:\n" + str(response))

    jd_path = "uploads\\jd\\JD1.pdf"  # Replace with actual path
    cv_path = "uploads\\cv\\PeterConnollyResume-2.pdf"  # Replace with actual path

    # --- Compute Cosine Similarity between CV and JD ---
    # similarity = compute_cosine_similarity(cv_path, jd_path)
    # print(Style.BRIGHT + "\nCosine Similarity between CV and JD:", similarity)

    interview_questions = processor.generate_initial_questions(cv_path, jd_path)
    print(Fore.CYAN + "\nGenerated Contextual Interview Questions:\n")
    print(Fore.YELLOW + interview_questions)
 
if __name__ == "__main__":
    main()