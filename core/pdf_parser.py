"""
Universal PDF Parser - Complete Version
"""

import fitz
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import hashlib
import logging
import re

from core.format_detector import FormatDetector
from core.parsing_strategies import get_all_strategies, ExtractedQuestion
from core.image_handler import ImageExtractor, SmartImageLinker, ExtractedImage, PageTracker

logger = logging.getLogger(__name__)


@dataclass
class ParsedQuestion:
    """Complete parsed question with all fields"""
    id: str
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_answer: Optional[str]
    explanation: Optional[str]
    source_file: str
    page_number: int
    question_number: str = ""
    images: List[str] = field(default_factory=list)
    subject: Optional[str] = None
    year: Optional[str] = None
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)
    has_image_reference: bool = False
    image_pattern_matched: str = ""
    needs_review: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "question_text": self.question_text,
            "option_a": self.option_a,
            "option_b": self.option_b,
            "option_c": self.option_c,
            "option_d": self.option_d,
            "correct_answer": self.correct_answer,
            "explanation": self.explanation,
            "source_file": self.source_file,
            "page_number": self.page_number,
            "question_number": self.question_number,
            "images": self.images,
            "subject": self.subject,
            "year": self.year,
            "is_valid": self.is_valid,
            "has_image_reference": self.has_image_reference,
            "image_pattern_matched": self.image_pattern_matched,
            "needs_review": self.needs_review,
        }


class UniversalPDFParser:
    """Universal parser with image support"""
    
    def __init__(self, extract_images: bool = True, save_images: bool = True):
        self.format_detector = FormatDetector()
        self.strategies = get_all_strategies()
        self.extract_images = extract_images
        self.save_images = save_images
        
        if extract_images:
            self.image_extractor = ImageExtractor()
            self.image_linker = SmartImageLinker()
            self.page_tracker = PageTracker()
        
        self.stats = {
            "total_pages": 0,
            "total_pdfs": 0,
            "total_questions": 0,
            "valid_questions": 0,
            "invalid_questions": 0,
            "questions_with_image_refs": 0,
            "questions_with_images_linked": 0,
            "images_extracted": 0,
            "parsing_errors": 0,
            "formats_detected": {}
        }
        
        self._current_images: Dict[int, List[ExtractedImage]] = {}
        self._current_page_map: Dict[str, int] = {}
    
    def parse_directory(self, directory: Path) -> List[ParsedQuestion]:
        all_questions = []
        pdf_files = list(directory.glob("*.pdf"))
        
        logger.info(f"Found {len(pdf_files)} PDF files to process")
        
        print("\n📊 Detecting PDF formats...")
        for pdf_path in pdf_files:
            sig = self.format_detector.detect_format(pdf_path)
            fmt = sig.format_type.value
            self.stats["formats_detected"][fmt] = self.stats["formats_detected"].get(fmt, 0) + 1
            print(f"  • {pdf_path.name}: {sig}")
        
        print("\n📝 Processing PDFs...")
        
        for pdf_path in pdf_files:
            try:
                questions = self.parse_pdf(pdf_path)
                all_questions.extend(questions)
                
                self.stats["total_pdfs"] += 1
                
                with_images = sum(1 for q in questions if q.images)
                print(f"  ✅ {pdf_path.name}: {len(questions)} questions ({with_images} with images)")
                
            except Exception as e:
                logger.error(f"Failed to parse {pdf_path.name}: {e}")
                print(f"  ❌ {pdf_path.name}: Error - {e}")
                self.stats["parsing_errors"] += 1
        
        return all_questions
    
    def parse_pdf(self, pdf_path: Path) -> List[ParsedQuestion]:
        """Parse a single PDF"""
        
        try:
            doc = fitz.open(pdf_path)
            self.stats["total_pages"] += len(doc)
            
            full_text = ""
            for page in doc:
                full_text += page.get_text("text") + "\n\n"
            
            doc.close()
            
        except Exception as e:
            logger.error(f"Error reading {pdf_path}: {e}")
            return []
        
        full_text = self._clean_text(full_text)
        
        # Track page numbers
        if self.extract_images:
            self._current_page_map = self.page_tracker.analyze_pdf(pdf_path)
            logger.info(f"Mapped {len(self._current_page_map)} questions to pages")
        
        # Extract images
        if self.extract_images:
            self._current_images = self.image_extractor.extract_from_pdf(pdf_path)
            total_images = sum(len(imgs) for imgs in self._current_images.values())
            self.stats["images_extracted"] += total_images
            logger.info(f"Extracted {total_images} images")
        
        # Parse questions
        extracted_questions = []
        
        for strategy in self.strategies:
            if strategy.can_parse(full_text):
                logger.debug(f"Trying strategy: {strategy.get_name()}")
                extracted = strategy.parse(full_text, pdf_path.name)
                
                if extracted:
                    logger.info(f"Strategy '{strategy.get_name()}' extracted {len(extracted)} questions")
                    extracted_questions = extracted
                    break
        
        if not extracted_questions:
            return []
        
        # Convert and link images
        parsed_questions = []
        
        for eq in extracted_questions:
            pq = self._convert_and_link(eq)
            
            self.stats["total_questions"] += 1
            
            if pq.is_valid:
                parsed_questions.append(pq)
                self.stats["valid_questions"] += 1
                
                if pq.has_image_reference:
                    self.stats["questions_with_image_refs"] += 1
                
                if pq.images:
                    self.stats["questions_with_images_linked"] += 1
            else:
                self.stats["invalid_questions"] += 1
        
        return parsed_questions
    
    def _clean_text(self, text: str) -> str:
        text = text.replace('\x00', '')
        text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)
        text = re.sub(r'[^\S\n]+', ' ', text)
        text = re.sub(r'\n{4,}', '\n\n\n', text)
        return text.strip()
    
    def _convert_and_link(self, eq: ExtractedQuestion) -> ParsedQuestion:
        """Convert and link images"""
        
        q_id = hashlib.md5(eq.question_text[:200].lower().encode()).hexdigest()[:12]
        
        actual_page = self._current_page_map.get(eq.question_number, eq.page_number)
        
        has_image_ref = False
        pattern_matched = ""
        
        if self.extract_images:
            has_image_ref, pattern_matched = self.image_linker.question_needs_image(eq.question_text)
        
        # Link images - SAVE ABSOLUTE PATHS
        image_paths = []
        
        if has_image_ref and self._current_images:
            matched_image = self.image_linker.get_image_for_question(
                eq.question_text,
                actual_page,
                self._current_images
            )
            
            if matched_image:
                if self.save_images:
                    # Save and store ABSOLUTE path
                    path = self.image_extractor.save_image(matched_image)
                    image_paths.append(str(path.absolute()))  # Use absolute path
                else:
                    image_paths.append(matched_image.get_data_uri())
        
        pq = ParsedQuestion(
            id=q_id,
            question_text=eq.question_text,
            option_a=eq.options.get('A', ''),
            option_b=eq.options.get('B', ''),
            option_c=eq.options.get('C', ''),
            option_d=eq.options.get('D', ''),
            correct_answer=eq.correct_answer,
            explanation=eq.explanation,
            source_file=eq.source_file,
            page_number=actual_page,
            question_number=eq.question_number,
            images=image_paths,
            has_image_reference=has_image_ref,
            image_pattern_matched=pattern_matched,
            needs_review=has_image_ref and not image_paths
        )
        
        pq = self._validate_question(pq)
        return pq
    
    def _validate_question(self, pq: ParsedQuestion) -> ParsedQuestion:
        errors = []
        
        if len(pq.question_text) < 15:
            errors.append("Question too short")
        
        if len(pq.question_text) > 3000:
            errors.append("Question too long")
        
        options = [pq.option_a, pq.option_b, pq.option_c, pq.option_d]
        
        empty_count = sum(1 for o in options if not o or len(o) < 1)
        if empty_count > 0:
            errors.append(f"{empty_count} empty options")
        
        non_empty = [o.lower().strip() for o in options if o]
        if len(set(non_empty)) != len(non_empty):
            errors.append("Duplicate options")
        
        if pq.correct_answer and pq.correct_answer not in 'ABCD':
            errors.append(f"Invalid answer: {pq.correct_answer}")
            pq.correct_answer = None
        
        pq.validation_errors = errors
        pq.is_valid = len(errors) == 0
        
        return pq
    
    def get_stats(self) -> Dict:
        return self.stats.copy()
    
    def print_stats(self):
        print("\n" + "="*60)
        print("📊 PARSING STATISTICS")
        print("="*60)
        
        print(f"\n📁 Files:")
        print(f"   Total PDFs processed: {self.stats['total_pdfs']}")
        print(f"   Total pages: {self.stats['total_pages']}")
        print(f"   Parsing errors: {self.stats['parsing_errors']}")
        
        print(f"\n📝 Questions:")
        print(f"   Total extracted: {self.stats['total_questions']}")
        print(f"   Valid: {self.stats['valid_questions']}")
        print(f"   Invalid: {self.stats['invalid_questions']}")
        
        print(f"\n🖼️ Images:")
        print(f"   Total extracted: {self.stats['images_extracted']}")
        print(f"   Questions with image references: {self.stats['questions_with_image_refs']}")
        print(f"   Questions with images linked: {self.stats['questions_with_images_linked']}")
        
        if self.stats['questions_with_image_refs'] > 0:
            link_rate = self.stats['questions_with_images_linked'] / self.stats['questions_with_image_refs'] * 100
            print(f"   Link success rate: {link_rate:.1f}%")
        
        print(f"\n📋 Formats detected:")
        for fmt, count in self.stats['formats_detected'].items():
            print(f"   {fmt}: {count} files")


# Aliases for backward compatibility
PDFParser = UniversalPDFParser
FMGEPDFParser = UniversalPDFParser
EnhancedPDFParser = UniversalPDFParser