import warnings
import os
from colorama import Fore, Style, init
from llama_index.llms.groq import Groq
from llama_index.core import SimpleDirectoryReader, ServiceContext, VectorStoreIndex, StorageContext, load_index_from_storage
from llama_index.core.node_parser import SentenceWindowNodeParser
from llama_index.core.indices.postprocessor import MetadataReplacementPostProcessor, SentenceTransformerRerank
from llama_index.core import QueryBundle, Settings
#from copy import deepcopy

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
init(autoreset=True)

class PDFProcessor:
    def __init__(self, document_pdf_path, groq_api_key):
        self.document_pdf_path = document_pdf_path
        self.llm = Groq(model="mixtral-8x7b-32768", api_key=groq_api_key)
        self.documents = self.load_documents()
    
    def load_documents(self):
        """Loads the document for querying."""
        return SimpleDirectoryReader(input_files=[self.document_pdf_path]).load_data()
    
    def query_document(self, query_text, sentence_window_size=5, embed_model="local:BAAI/bge-small-en-v1.5", save_dir="sentence_index", similarity_top_k=6, rerank_top_n=2):
        """Queries the document using a sentence window approach."""
        Settings.llm = self.llm
        Settings.embed_model = embed_model
        Settings.node_parser = SentenceWindowNodeParser.from_defaults(
            window_size=sentence_window_size,
            window_metadata_key="window",
            original_text_metadata_key="original_text"
        )
        
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
        
        index = build_sentence_window_index(self.documents, save_dir=save_dir)
        query_engine = get_sentence_window_query_engine(index, similarity_top_k, rerank_top_n)
        response = query_engine.query(query_text)
        return response

def main():
    document_pdf_path = "Eric Ries - The Lean Startup.pdf"  # Path to the document for querying
    groq_api_key = "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"  # Replace with actual API key
    
    processor = PDFProcessor(document_pdf_path, groq_api_key)
    query_text = input("Please enter your query: ").strip()
    response = processor.query_document(query_text)
    print(Fore.GREEN + "Query Response:\n" + str(response))

if __name__ == "__main__":
    main()
