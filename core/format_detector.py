"""
Format Detector Module
Analyzes PDFs to determine their question format
"""

import re
import fitz
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PDFFormat(Enum):
    """Detected PDF formats"""
    FORMAT_QUESTION_COLON = "question_colon"      # "1. Question:" + "Option 1:"
    FORMAT_Q_DOT = "q_dot"                         # "Q1." or "Q.1"
    FORMAT_NUMBER_DOT = "number_dot"               # "1." + "A." or "a)"
    FORMAT_NUMBER_PAREN = "number_paren"           # "1)" + "(A)" or "A)"
    FORMAT_BRACKET = "bracket"                     # "[1]" + "[A]"
    FORMAT_TABLE = "table"                         # Questions in table format
    FORMAT_MIXED = "mixed"                         # Multiple formats detected
    FORMAT_UNKNOWN = "unknown"                     # Could not detect


@dataclass
class FormatSignature:
    """Signature of detected format"""
    format_type: PDFFormat
    confidence: float  # 0-1
    question_pattern: str
    option_pattern: str
    answer_pattern: str
    sample_matches: List[str]
    
    def __str__(self):
        return f"{self.format_type.value} (confidence: {self.confidence:.0%})"


class FormatDetector:
    """
    Detects the format of FMGE PDFs by analyzing patterns
    """
    
    # Question patterns to check (pattern, format_type, description)
    QUESTION_PATTERNS = [
        # Format 1: "1. Question :" or "1. Question:"
        (r'^\s*(\d{1,3})\s*\.\s*Question\s*:\s*', PDFFormat.FORMAT_QUESTION_COLON, "X. Question:"),
        
        # Format 2: "Q1." or "Q.1" or "Q 1."
        (r'^\s*Q\s*\.?\s*(\d{1,3})\s*[\.\):]', PDFFormat.FORMAT_Q_DOT, "Q1. or Q.1"),
        
        # Format 3: "1." at start of line (simple numbered)
        (r'^\s*(\d{1,3})\s*\.\s+[A-Z]', PDFFormat.FORMAT_NUMBER_DOT, "1. Text"),
        
        # Format 4: "1)" at start of line
        (r'^\s*(\d{1,3})\s*\)\s+', PDFFormat.FORMAT_NUMBER_PAREN, "1) Text"),
        
        # Format 5: "[1]" format
        (r'^\s*\[(\d{1,3})\]\s*', PDFFormat.FORMAT_BRACKET, "[1] Text"),
    ]
    
    # Option patterns to check
    OPTION_PATTERNS = [
        # "Option 1 :" format
        (r'Option\s*[1-4]\s*:', "Option X:"),
        
        # "A." or "A)" format
        (r'(?:^|\n)\s*[A-Da-d]\s*[\.\)]', "A. or A)"),
        
        # "(A)" format
        (r'(?:^|\n)\s*\([A-Da-d]\)', "(A)"),
        
        # "A -" or "A:" format
        (r'(?:^|\n)\s*[A-Da-d]\s*[-:]', "A- or A:"),
        
        # "1." "2." for options
        (r'(?:^|\n)\s*[1-4]\s*[\.\)]', "1. 2. 3. 4."),
    ]
    
    # Answer patterns to check
    ANSWER_PATTERNS = [
        (r'Correct\s*option\s*:\s*\d', "Correct option: X"),
        (r'Correct\s*Answer\s*:\s*[A-Da-d]', "Correct Answer: A"),
        (r'Ans(?:wer)?\s*[\.\:\-]\s*[A-Da-d]', "Ans: A"),
        (r'Answer\s*[A-Da-d]', "Answer A"),
        (r'\*\*?[A-Da-d]\*\*?', "**A**"),
        (r'Key\s*:\s*[A-Da-d]', "Key: A"),
    ]
    
    def __init__(self):
        self.cache = {}  # Cache detected formats
    
    def detect_format(self, pdf_path: Path, sample_pages: int = 5) -> FormatSignature:
        """
        Detect the format of a PDF by analyzing sample pages
        """
        
        # Check cache
        cache_key = str(pdf_path)
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            doc = fitz.open(pdf_path)
            
            # Extract text from sample pages
            sample_text = ""
            pages_to_check = min(sample_pages, len(doc))
            
            for i in range(pages_to_check):
                sample_text += doc[i].get_text("text") + "\n\n"
            
            doc.close()
            
            # Detect format
            signature = self._analyze_text(sample_text, pdf_path.name)
            
            # Cache result
            self.cache[cache_key] = signature
            
            logger.info(f"Detected format for {pdf_path.name}: {signature}")
            
            return signature
            
        except Exception as e:
            logger.error(f"Error detecting format for {pdf_path}: {e}")
            return FormatSignature(
                format_type=PDFFormat.FORMAT_UNKNOWN,
                confidence=0.0,
                question_pattern="",
                option_pattern="",
                answer_pattern="",
                sample_matches=[]
            )
    
    def _analyze_text(self, text: str, filename: str) -> FormatSignature:
        """Analyze text to determine format"""
        
        # Count matches for each question pattern
        question_scores = []
        
        for pattern, format_type, desc in self.QUESTION_PATTERNS:
            matches = re.findall(pattern, text, re.MULTILINE | re.IGNORECASE)
            if matches:
                question_scores.append({
                    'format': format_type,
                    'pattern': pattern,
                    'count': len(matches),
                    'desc': desc,
                    'samples': matches[:5]
                })
        
        # Sort by match count
        question_scores.sort(key=lambda x: x['count'], reverse=True)
        
        # Detect option format
        option_pattern = ""
        option_desc = ""
        for pattern, desc in self.OPTION_PATTERNS:
            if re.search(pattern, text, re.MULTILINE | re.IGNORECASE):
                option_pattern = pattern
                option_desc = desc
                break
        
        # Detect answer format
        answer_pattern = ""
        answer_desc = ""
        for pattern, desc in self.ANSWER_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                answer_pattern = pattern
                answer_desc = desc
                break
        
        # Determine best format
        if question_scores:
            best = question_scores[0]
            
            # Calculate confidence based on match count and consistency
            total_potential = text.count('\n') / 20  # Rough estimate of questions
            confidence = min(1.0, best['count'] / max(1, total_potential))
            
            # Boost confidence if we also found options and answers
            if option_pattern:
                confidence = min(1.0, confidence + 0.2)
            if answer_pattern:
                confidence = min(1.0, confidence + 0.1)
            
            return FormatSignature(
                format_type=best['format'],
                confidence=confidence,
                question_pattern=best['pattern'],
                option_pattern=option_pattern,
                answer_pattern=answer_pattern,
                sample_matches=[f"{best['desc']}: {s}" for s in best['samples'][:3]]
            )
        
        return FormatSignature(
            format_type=PDFFormat.FORMAT_UNKNOWN,
            confidence=0.0,
            question_pattern="",
            option_pattern=option_pattern,
            answer_pattern=answer_pattern,
            sample_matches=[]
        )
    
    def detect_all(self, directory: Path) -> Dict[str, FormatSignature]:
        """Detect formats for all PDFs in a directory"""
        
        results = {}
        pdf_files = list(directory.glob("*.pdf"))
        
        for pdf_path in pdf_files:
            results[pdf_path.name] = self.detect_format(pdf_path)
        
        return results
    
    def print_detection_report(self, directory: Path):
        """Print a report of detected formats"""
        
        results = self.detect_all(directory)
        
        print("\n" + "="*70)
        print("PDF FORMAT DETECTION REPORT")
        print("="*70)
        
        # Group by format type
        by_format = {}
        for filename, sig in results.items():
            fmt = sig.format_type.value
            if fmt not in by_format:
                by_format[fmt] = []
            by_format[fmt].append((filename, sig))
        
        for fmt, files in by_format.items():
            print(f"\n📁 {fmt.upper()} ({len(files)} files)")
            print("-" * 50)
            for filename, sig in files:
                print(f"  • {filename}")
                print(f"    Confidence: {sig.confidence:.0%}")
                if sig.sample_matches:
                    print(f"    Samples: {sig.sample_matches[0]}")
        
        print("\n" + "="*70)