"""
Document loader for handling CV, JD, and reference documents.
"""

from typing import List, Dict, Optional
from pathlib import Path
from .processor import DocumentProcessor

try:
    from llama_index.core import SimpleDirectoryReader

    LLAMA_INDEX_AVAILABLE = True
except ImportError:
    LLAMA_INDEX_AVAILABLE = False


class DocumentLoader:
    """Loads and manages CV, JD, and reference documents."""

    def __init__(self, cv_path: str, jd_path: str, reference_paths: List[str]):
        self.processor = DocumentProcessor()
        self.cv_path = cv_path
        self.jd_path = jd_path
        self.reference_paths = (
            reference_paths if isinstance(reference_paths, list) else [reference_paths]
        )

        # Load documents
        self.cv_text = self._load_document(cv_path)
        self.jd_text = self._load_document(jd_path)
        self.reference_texts = [
            self._load_document(path) for path in self.reference_paths
        ]

        # Load with llama-index if available
        if LLAMA_INDEX_AVAILABLE:
            try:
                self.documents = SimpleDirectoryReader(
                    input_files=self.reference_paths
                ).load_data()
            except Exception as e:
                print(f"Warning: Could not load documents with llama-index: {e}")
                self.documents = []
        else:
            self.documents = []

    def _load_document(self, file_path: str) -> str:
        """Load a single document."""
        try:
            return self.processor.extract_text(file_path)
        except Exception as e:
            print(f"Error loading document {file_path}: {e}")
            return ""

    def get_cv_sections(self) -> Dict[str, str]:
        """Get segregated CV sections."""
        return self.processor.segregate_resume_text(self.cv_text)

    def get_jd_text(self) -> str:
        """Get job description text."""
        return self.jd_text

    def get_jd_keywords(self) -> List[str]:
        """Extract keywords from job description."""
        return self.processor.extract_keywords(self.jd_text)

    def get_cv_keywords(self) -> List[str]:
        """Extract keywords from CV."""
        return self.processor.extract_keywords(self.cv_text)

    def get_combined_reference_text(self) -> str:
        """Get all reference texts combined."""
        return "\n\n".join(self.reference_texts)

    def validate_documents(self) -> Dict[str, bool]:
        """Validate all loaded documents."""
        return {
            "cv_valid": bool(self.cv_text.strip()),
            "jd_valid": bool(self.jd_text.strip()),
            "references_valid": all(
                bool(text.strip()) for text in self.reference_texts
            ),
        }
