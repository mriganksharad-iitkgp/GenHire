"""
PDF Parser Service - Extract text from PDF files for CV and JD processing
Handles PDF text extraction with robust error handling and encoding support
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from PyPDF2 import PdfReader

logger = logging.getLogger(__name__)

class PDFParserService:
    """
    Service for extracting text from PDF files (CVs, JDs, etc.)
    Uses PyPDF2 for PDF parsing with fallback mechanisms
    """
    
    SUPPORTED_EXTENSIONS = ['.pdf', '.txt']
    MAX_FILE_SIZE_MB = 10  # Maximum file size in MB
    
    def __init__(self):
        """Initialize PDF parser service"""
        logger.info("PDFParserService initialized")
    
    def _extract_page_layout(self, page) -> tuple[str, str]:
        fragments = []

        def visitor(text, _cm, tm, _font_dict, _font_size):
            clean = str(text or "").strip()
            if clean:
                fragments.append((float(tm[4]), float(tm[5]), clean))

        page.extract_text(visitor_text=visitor)
        if not fragments:
            return page.extract_text() or "", "low"

        page_width = float(page.mediabox.width)
        left = [item for item in fragments if item[0] < page_width * 0.46]
        right = [item for item in fragments if item[0] > page_width * 0.54]
        center = [item for item in fragments if page_width * 0.46 <= item[0] <= page_width * 0.54]
        is_two_column = len(left) >= 8 and len(right) >= 8 and len(center) < (len(fragments) * 0.2)

        def ordered(items):
            return "\n".join(text for _x, _y, text in sorted(items, key=lambda item: (-round(item[1], 1), item[0])))

        if is_two_column:
            return f"{ordered(left)}\n{ordered(center)}\n{ordered(right)}".strip(), "medium"
        return ordered(fragments), "high"

    def _extract_pdf_with_metadata(self, file_path: str) -> tuple[str, Dict[str, str]]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        # Validate file size
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > self.MAX_FILE_SIZE_MB:
            raise ValueError(f"File size ({file_size_mb:.2f}MB) exceeds maximum allowed ({self.MAX_FILE_SIZE_MB}MB)")
        
        try:
            logger.info(f"Extracting text from PDF: {file_path}")
            reader = PdfReader(file_path)
            text_parts = []
            
            # Extract text from each page
            confidences = []
            for page_num, page in enumerate(reader.pages, 1):
                try:
                    page_text, confidence = self._extract_page_layout(page)
                    confidences.append(confidence)
                    if page_text and page_text.strip():
                        text_parts.append(page_text)
                        logger.debug(f"Extracted {len(page_text)} characters from page {page_num}")
                except Exception as e:
                    logger.warning(f"Failed to extract text from page {page_num}: {e}")
                    continue
            
            if not text_parts:
                logger.warning(f"No text extracted from PDF: {file_path}")
                return "", {
                    "parsing_confidence": "low",
                    "layout_detected": "unknown",
                    "parser": "coordinate_aware_pypdf",
                }
            
            full_text = "\n".join(text_parts)
            logger.info(f"Successfully extracted {len(full_text)} characters from {len(text_parts)} pages")
            confidence = "low" if "low" in confidences else "medium" if "medium" in confidences else "high"
            return full_text, {
                "parsing_confidence": confidence,
                "layout_detected": "two_column" if "medium" in confidences else "single_column",
                "parser": "coordinate_aware_pypdf",
            }
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF {file_path}: {e}")
            raise ValueError(f"Failed to parse PDF: {str(e)}")

    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from a PDF file using coordinate-aware ordering."""
        text, _metadata = self._extract_pdf_with_metadata(file_path)
        return text
    
    def extract_text_from_txt(self, file_path: str, encoding: str = 'utf-8') -> str:
        """
        Extract text from a plain text file
        
        Args:
            file_path: Path to the text file
            encoding: Text encoding (default: utf-8)
            
        Returns:
            File content as string
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Text file not found: {file_path}")
        
        try:
            logger.info(f"Reading text file: {file_path}")
            with open(file_path, 'r', encoding=encoding) as f:
                text = f.read()
            logger.info(f"Successfully read {len(text)} characters")
            return text
        except UnicodeDecodeError:
            # Try with different encoding
            logger.warning(f"UTF-8 decoding failed, trying latin-1 encoding")
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Failed to read text file with fallback encoding: {e}")
                raise ValueError(f"Failed to read text file: {str(e)}")
        except Exception as e:
            logger.error(f"Error reading text file {file_path}: {e}")
            raise ValueError(f"Failed to read text file: {str(e)}")
    
    def extract_text(self, file_path: str) -> str:
        """
        Extract text from a file (auto-detect PDF or TXT)
        
        Args:
            file_path: Path to the file
            
        Returns:
            Extracted text as string
            
        Raises:
            ValueError: If file format is not supported
        """
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == '.pdf':
            return self.extract_text_from_pdf(file_path)
        elif file_ext == '.txt':
            return self.extract_text_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_ext}. Supported formats: {self.SUPPORTED_EXTENSIONS}")
    
    def parse_cv_pdf(self, file_path: str) -> Dict[str, Any]:
        """
        Parse CV PDF and extract text with metadata
        
        Args:
            file_path: Path to CV PDF file
            
        Returns:
            Dictionary containing extracted text and metadata
        """
        file_ext = Path(file_path).suffix.lower()
        if file_ext == '.pdf':
            text, parse_metadata = self._extract_pdf_with_metadata(file_path)
        else:
            text = self.extract_text(file_path)
            parse_metadata = {
                'parsing_confidence': 'high',
                'layout_detected': 'plain_text',
                'parser': 'plain_text'
            }
        file_size = os.path.getsize(file_path)
        
        # Count pages for PDFs
        pages = 0
        if Path(file_path).suffix.lower() == '.pdf':
            try:
                reader = PdfReader(file_path)
                pages = len(reader.pages)
            except:
                pages = 0
        
        return {
            'text': text,
            'metadata': {
                'filename': os.path.basename(file_path),
                'file_path': file_path,
                'file_size': file_size,
                'pages': pages,
                'character_count': len(text),
                'word_count': len(text.split()),
                'file_type': Path(file_path).suffix.lower(),
                **parse_metadata
            }
        }
    
    def parse_jd_pdf(self, file_path: str) -> Dict[str, Any]:
        """
        Parse Job Description PDF and extract text with metadata
        
        Args:
            file_path: Path to JD PDF file
            
        Returns:
            Dictionary containing extracted text and metadata
        """
        # Same logic as CV parsing
        return self.parse_cv_pdf(file_path)
    
    def validate_pdf(self, file_path: str) -> bool:
        """
        Validate if a file is a valid PDF
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if valid PDF, False otherwise
        """
        try:
            if not os.path.exists(file_path):
                return False
            
            if Path(file_path).suffix.lower() != '.pdf':
                return False
            
            # Try to open and read the PDF
            reader = PdfReader(file_path)
            _ = len(reader.pages)
            return True
        except:
            return False
    
    def is_supported_file(self, file_path: str) -> bool:
        """
        Check if file format is supported
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if supported, False otherwise
        """
        file_ext = Path(file_path).suffix.lower()
        return file_ext in self.SUPPORTED_EXTENSIONS


# Singleton instance
_pdf_parser_instance = None

def get_pdf_parser() -> PDFParserService:
    """Get singleton instance of PDF parser service"""
    global _pdf_parser_instance
    if _pdf_parser_instance is None:
        _pdf_parser_instance = PDFParserService()
    return _pdf_parser_instance
