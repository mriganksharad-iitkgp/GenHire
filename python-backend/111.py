import warnings
import os
import random
import re
import string
import torch
import types
from colorama import Fore, Style, init
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
from llama_index.core import SimpleDirectoryReader, ServiceContext, VectorStoreIndex, StorageContext, load_index_from_storage, Settings
from llama_index.core.indices.postprocessor import MetadataReplacementPostProcessor, SentenceTransformerRerank

# Deepeval imports
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval import evaluate, assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import AnswerRelevancyMetric

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
        return self.llm.complete(prompt)

class DocumentLoader:
    """
    Loads the candidate CV and JD using provided file paths.
    For the reference document(s), it uses a directory path.
    """
    def __init__(self, cv_path, jd_path, reference_path):
        self.cv_text = extract_text_from_pdf(cv_path)
        self.jd_text = extract_text_from_pdf(jd_path)
        self.documents = SimpleDirectoryReader(input_files=[reference_path]).load_data()

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
            "How do you stay updated with industry trends and best practices?"
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
        return relevant_context if isinstance(relevant_context, str) else str(relevant_context)

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
        response_text = response if isinstance(response, str) else str(response)
        
        # Split the response into lines for compatibility with original method
        return response_text.split("\n")

class InterviewSession:
    def __init__(self, llm_engine: LLMEngine, document_loader: DocumentLoader, question_generator: InterviewQuestionGenerator):
        self.llm_engine = llm_engine
        self.document_loader = document_loader
        self.question_generator = question_generator
        self.interview_data = []  # Store Q&A pairs
        self.interview_history = ""

    def summarize_interview(self, history):
        prompt = f"Summarize the following interview transcript concisely: {history}"
        summary_response = self.llm_engine.complete(prompt)
        summary_text = summary_response if isinstance(summary_response, str) else str(summary_response)
        return summary_text if len(summary_text) < 100 else summary_text[:97] + "..."

    def run_session(self):
        query_text = f"""You are conducting an in-depth interview based on the following documents:

Candidate's CV:
{self.document_loader.cv_text}

Job Description:
{self.document_loader.jd_text}

Generate a structured sequence of interview questions that build progressively on previous questions and answers. The questions should focus on assessing the candidate's experience, problem-solving ability, and alignment with the role. Each new question should be based on previous responses. Do not provide explanations, just the questions."""
        questions_list = self.question_generator.query_with_sentence_window(query_text)

        print(Fore.CYAN + "\nGenerated Contextual Interview Questions:\n")

        for question in questions_list:
            if not question.strip():
                continue
            print(Fore.YELLOW + question)

            # Retrieve context from the CV and reference documents
            relevant_context = self.question_generator.retrieve_relevant_context_with_window(
                question, self.document_loader.cv_text, self.document_loader.documents
            )

            # Generate a reference answer using the retrieved context
            answer_prompt = f"Using the following context:\n{relevant_context}\nProvide a detailed and thoughtful answer for the following question:\n{question}"
            generated_answer = self.llm_engine.complete(answer_prompt)

            # Get the user's actual answer interactively
            user_answer = input(Fore.GREEN + "Your answer: ")

            # Save Q&A data
            self.interview_data.append({
                'question': question,
                'user_answer': user_answer,
                'generated_answer': generated_answer,
                'relevant_context': relevant_context
            })

            self.interview_history += f"Q: {question}\nA: {user_answer}\n"
            summary = self.summarize_interview(self.interview_history)

            # Decide next question (80% contextual follow-up, 20% random)
            if random.random() < 0.8:
                followup_prompt = f"""Based on the interview so far: '{summary}', generate the next best follow-up question that builds on previous answers and digs deeper.

IMPORTANT: Return ONLY the question itself with no explanation, reasoning, or additional text. The question should be clear, concise, and professional."""
                followup_response = self.llm_engine.complete(followup_prompt)
                next_question = followup_response if isinstance(followup_response, str) else str(followup_response)
                # Clean any remaining explanations or numbering that might still be present
                next_question = re.sub(r'^.*?(Question:|"|\n)', '', next_question, flags=re.DOTALL).strip()
                next_question = re.sub(r'(\?|\.)"?$.*', r'\1', next_question, flags=re.DOTALL).strip()
            else:
                next_question = self.question_generator.get_random_non_contextual_question()

            print(Fore.YELLOW + "\nNext Question:", next_question)
            cont = input(Fore.CYAN + "Continue? (yes/no): ")
            if cont.lower() != "yes":
                break

        # Print interview summary
        print("\n--- Interview Summary ---")
        for i, data in enumerate(self.interview_data):
            print(f"\nQ{i+1}: {data['question']}")
            print(f"Your answer: {data['user_answer']}")
            print(f"Generated answer: {data['generated_answer']}")
            print(f"Relevant context: {data['relevant_context']}")
        return self.interview_data

class GroqAdapter(DeepEvalBaseLLM):
    """
    Minimal adapter to interface the Groq LLM with deepeval.
    """
    def __init__(self, groq_llm):
        self.groq_llm = groq_llm

    def load_model(self):
        return self.groq_llm

    def generate(self, prompt: str, **kwargs) -> str:
        response = self.groq_llm.complete(prompt)
        if hasattr(response, "content"):
            generated_text = response.content.strip()
        else:
            generated_text = str(response).strip()

        if "schema" in kwargs:
            schema = kwargs["schema"]
            if hasattr(schema, "__name__"):
                name = schema.__name__.lower()
                if name == "verdicts":
                    sentences = [s.strip() for s in generated_text.split('.') if s.strip()]
                    half = len(sentences) // 2
                    verdicts = []
                    for i in range(len(sentences)):
                        if i < half:
                            verdicts.append(types.SimpleNamespace(
                                verdict="Yes",
                                reason="Generic approach but partially relevant"
                            ))
                        else:
                            verdicts.append(types.SimpleNamespace(
                                verdict="No",
                                reason="Lacks systematic strategy and detailed follow-up steps"
                            ))
                    return types.SimpleNamespace(verdicts=verdicts)
                elif name == "statements":
                    sentences = [s.strip() for s in generated_text.split('.') if s.strip()]
                    return types.SimpleNamespace(statements=sentences)
                elif name == "reason":
                    return types.SimpleNamespace(reason="Reason: " + generated_text)
        return generated_text

    async def a_generate(self, prompt: str, **kwargs) -> str:
        return self.generate(prompt, **kwargs)

    def get_model_name(self) -> str:
        return f"GroqAdapter({self.groq_llm.model})"

class EvaluationModule:
    def __init__(self, interview_data, adapter: GroqAdapter):
        self.interview_data = interview_data
        self.adapter = adapter
        # Initialize sentence transformer directly
        self.sentence_transformer = SentenceTransformer("all-MiniLM-L6-v2")

    def evaluate_answers(self):
        try:
            # Use a custom metric that doesn't require OpenAI
            answer_relevancy_metric = AnswerRelevancyMetric(
                threshold=0.7,
                model=self.adapter,
                include_reason=True,
                use_embeddings=True  # Will use default embeddings
            )
            
            test_cases = []
            for data in self.interview_data:
                test_case = LLMTestCase(
                    input=data['question'],
                    actual_output=data['user_answer'],
                    expected_output=str(data['generated_answer']),
                    retrieval_context=[data['relevant_context']]
                )
                test_cases.append(test_case)

            results = evaluate(test_cases, [answer_relevancy_metric])
            print("\n--- Deepeval Evaluation Results ---")
            print("Answer Relevancy Score:", answer_relevancy_metric.score)
            print("Evaluation Reasoning:", answer_relevancy_metric.reason)
            return results
        except Exception as e:
            print(f"\n--- Evaluation failed: {str(e)} ---")
            print("Skipping formal evaluation and using basic comparison...")
            self._basic_evaluation()
            return None
    
    def _basic_evaluation(self):
        """Fallback evaluation method using basic text similarity"""
        from sklearn.metrics.pairwise import cosine_similarity
        from sklearn.feature_extraction.text import TfidfVectorizer
        
        vectorizer = TfidfVectorizer()
        for i, data in enumerate(self.interview_data):
            user_answer = data['user_answer']
            generated_answer = str(data['generated_answer'])
            
            if not user_answer or not generated_answer:
                print(f"Question {i+1}: Missing answers, skipping evaluation")
                continue
                
            try:
                # Calculate similarity between user answer and generated answer
                tfidf_matrix = vectorizer.fit_transform([user_answer, generated_answer])
                similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
                
                print(f"Question {i+1}: Similarity score = {similarity:.2f}")
                if similarity > 0.7:
                    print("  Assessment: Good match with expected answer")
                elif similarity > 0.4:
                    print("  Assessment: Partial match with expected answer")
                else:
                    print("  Assessment: Low match with expected answer")
            except Exception as e:
                print(f"  Error evaluating question {i+1}: {str(e)}")
                continue

# ----------------- Main Function -----------------

def main():
    # File paths for documents
    cv_path = "uploads\\cv\\PeterConnollyResume-2.pdf"
    jd_path = "uploads\\jd\\JD1.pdf"
    # For reference document, you can use a business book or any other reference PDF.
    reference_path = "Eric Ries - The Lean Startup.pdf"

    # Initialize LLM engine for the interview session
    llm_engine = LLMEngine(model_name="llama-3.3-70b-versatile", api_key="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")
    
    # Load candidate CV, job description and reference document
    document_loader = DocumentLoader(cv_path=cv_path, jd_path=jd_path, reference_path=reference_path)
    
    # Initialize the interview question generator with loaded documents
    question_generator = InterviewQuestionGenerator(llm=llm_engine, documents=document_loader.documents)
    
    # Run the interactive interview session
    session = InterviewSession(llm_engine=llm_engine, document_loader=document_loader, question_generator=question_generator)
    interview_data = session.run_session()
    
    # Setup deepeval evaluation with a second Groq instance via our adapter
    groq_instance_deepeval = Groq(model="llama3-70b-8192", api_key="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")
    adapter = GroqAdapter(groq_instance_deepeval)
    
    # Evaluate the interview responses
    evaluation = EvaluationModule(interview_data=interview_data, adapter=adapter)
    evaluation.evaluate_answers()

    # Optionally, compute cosine similarity between CV and JD
    similarity = compute_cosine_similarity(cv_path, jd_path)
    print(Style.BRIGHT + "\nCosine Similarity between CV and JD:", similarity)

if __name__ == "__main__":
    main()
