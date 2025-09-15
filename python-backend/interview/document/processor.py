"""
Document processing utilities for the interview system.
"""

import os
import re
import string
from typing import Dict, List, Optional, Tuple
from pathlib import Path

import nltk
from nltk import pos_tag, sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from pypdf import PdfReader

# # Download required NLTK data with updated names
# try:
#     nltk.data.find("tokenizers/punkt_tab")
# except LookupError:
#     print("Downloading punkt_tab...")
#     nltk.download("punkt_tab")

# try:
#     nltk.data.find("corpora/stopwords")
# except LookupError:
#     print("Downloading stopwords...")
#     nltk.download("stopwords")

# try:
#     nltk.data.find("taggers/averaged_perceptron_tagger_eng")
# except LookupError:
#     print("Downloading averaged_perceptron_tagger_eng...")
#     nltk.download("averaged_perceptron_tagger_eng")


class DocumentProcessor:
    """Handles document loading, text extraction, and preprocessing."""

    def __init__(self, max_file_size_mb: int = 10):
        self.max_file_size_mb = max_file_size_mb
        self.supported_formats = {".pdf", ".txt", ".docx"}

    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from a PDF file."""
        if not self._validate_file(file_path):
            return ""

        try:
            reader = PdfReader(file_path)
            text_parts = []

            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

            return "\n".join(text_parts)

        except Exception as e:
            print(f"Error extracting text from PDF {file_path}: {e}")
            return ""

    def extract_text_from_txt(self, file_path: str) -> str:
        """Extract text from a TXT file."""
        if not self._validate_file(file_path):
            return ""

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                return file.read()
        except Exception as e:
            print(f"Error reading text file {file_path}: {e}")
            return ""

    def extract_text(self, file_path: str) -> str:
        """Extract text from supported file formats."""
        file_ext = Path(file_path).suffix.lower()

        if file_ext == ".pdf":
            return self.extract_text_from_pdf(file_path)
        elif file_ext == ".txt":
            return self.extract_text_from_txt(file_path)
        else:
            print(f"Unsupported file format: {file_ext}")
            return ""

    def preprocess_text(self, text: str) -> str:
        """Preprocess text for embedding by cleaning and filtering."""
        if not text:
            return ""

        try:
            # Convert to lowercase and remove non-alphabetic characters
            text = text.lower()
            text = re.sub(r"[^a-zA-Z\s]", " ", text)

            # Tokenize into sentences
            sentences = sent_tokenize(text)
            processed_words = []

            # Get stopwords
            stop_words = set(stopwords.words("english"))

            for sentence in sentences:
                # Tokenize words
                words = word_tokenize(sentence)

                # Remove stopwords and punctuation
                words = [
                    word
                    for word in words
                    if word not in stop_words and word not in string.punctuation
                ]

                # POS tagging to filter meaningful words
                tagged_words = pos_tag(words)

                # Keep nouns, verbs, adjectives, and adverbs
                meaningful_words = [
                    word
                    for word, tag in tagged_words
                    if tag not in ["DT", "IN", "TO", "PRP", "WP", "CC", "UH"]
                ]

                processed_words.extend(meaningful_words)

            return " ".join(processed_words)

        except Exception as e:
            print(f"Error preprocessing text: {e}")
            return text

    def segregate_resume_text(self, text: str) -> Dict[str, str]:
        """Segregate resume text into standard sections."""
        section_keywords = {
            "personal_info": ["personal information", "contact", "profile"],
            "summary": ["summary", "objective", "profile summary"],
            "experience": [
                "professional experience",
                "work experience",
                "experience",
                "employment history",
                "career",
                "work history",
                "internships",
            ],
            "education": [
                "education",
                "academic background",
                "academic qualifications",
                "qualifications",
                "degrees",
            ],
            "skills": [
                "skills",
                "technical skills",
                "proficiencies",
                "expertise",
                "competencies",
                "technologies",
            ],
            "projects": ["projects", "personal projects", "portfolio", "work samples"],
            "certifications": [
                "certifications",
                "certificates",
                "credentials",
                "licenses",
            ],
            "achievements": ["achievements", "awards", "honors", "accomplishments"],
        }

        lines = text.lower().split("\n")
        resume_sections = {"header": ""}
        current_section = "header"

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if line matches any section keyword
            section_found = False
            for section, keywords in section_keywords.items():
                for keyword in keywords:
                    if keyword in line:
                        current_section = section
                        if current_section not in resume_sections:
                            resume_sections[current_section] = ""
                        section_found = True
                        break
                if section_found:
                    break

            # Add line to current section
            resume_sections[current_section] += line + "\n"

        return resume_sections

    def extract_keywords(self, text: str) -> List[str]:
        """Extract key technical terms and skills from text."""
        if not text:
            return []

        try:
            # Preprocess text
            processed_text = self.preprocess_text(text)
            words = processed_text.split()

            # POS tagging to find nouns and proper nouns
            tagged_words = pos_tag(words)
            keywords = [
                word
                for word, tag in tagged_words
                if tag in ["NN", "NNS", "NNP", "NNPS"] and len(word) > 2
            ]

            # Remove duplicates while preserving order
            return list(dict.fromkeys(keywords))

        except Exception as e:
            print(f"Error extracting keywords: {e}")
            return []

    def _validate_file(self, file_path: str) -> bool:
        """Validate file existence, size, and format."""
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return False

        # Check file size
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > self.max_file_size_mb:
            print(f"File too large: {file_size_mb:.2f}MB > {self.max_file_size_mb}MB")
            return False

        # Check file format
        file_ext = Path(file_path).suffix.lower()
        if file_ext not in self.supported_formats:
            print(f"Unsupported file format: {file_ext}")
            return False

        return True
