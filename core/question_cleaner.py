"""
Question Cleaner Module
Filters, deduplicates, and enhances parsed questions
Ensures only high-quality MCQs enter the question bank
"""

import re
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import hashlib

from core.pdf_parser import ParsedQuestion
from config.settings import SUBJECT_CONFIG


@dataclass
class CleaningStats:
    """Statistics from cleaning process"""
    total_input: int = 0
    duplicates_removed: int = 0
    invalid_removed: int = 0
    enhanced: int = 0
    final_output: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "total_input": self.total_input,
            "duplicates_removed": self.duplicates_removed,
            "invalid_removed": self.invalid_removed,
            "enhanced": self.enhanced,
            "final_output": self.final_output,
            "duplicate_rate": f"{(self.duplicates_removed/self.total_input*100):.1f}%" if self.total_input > 0 else "0%",
            "retention_rate": f"{(self.final_output/self.total_input*100):.1f}%" if self.total_input > 0 else "0%",
        }


class QuestionCleaner:
    """
    Cleans and validates questions for the question bank
    Focuses on quality over quantity
    """
    
    def __init__(self, subject_config: SUBJECT_CONFIG = None):
        self.subject_config = subject_config or SUBJECT_CONFIG
        self.stats = CleaningStats()
        self._seen_hashes: Set[str] = set()
        self._seen_questions: Dict[str, ParsedQuestion] = {}
    
    def clean_questions(self, questions: List[ParsedQuestion]) -> List[ParsedQuestion]:
        """Main cleaning pipeline"""
        self.stats.total_input = len(questions)
        
        # Step 1: Remove invalid questions
        valid_questions = self._filter_invalid(questions)
        
        # Step 2: Deduplicate
        unique_questions = self._deduplicate(valid_questions)
        
        # Step 3: Enhance with subject tags
        enhanced_questions = self._enhance_questions(unique_questions)
        
        # Step 4: Final validation
        final_questions = self._final_validation(enhanced_questions)
        
        self.stats.final_output = len(final_questions)
        
        return final_questions
    
    def _filter_invalid(self, questions: List[ParsedQuestion]) -> List[ParsedQuestion]:
        """Remove questions that don't meet quality standards"""
        valid = []
        
        for q in questions:
            if self._is_valid_question(q):
                valid.append(q)
            else:
                self.stats.invalid_removed += 1
        
        return valid
    
    def _is_valid_question(self, q: ParsedQuestion) -> bool:
        """Check if question meets all quality criteria"""
        
        # Already marked invalid by parser
        if not q.is_valid:
            return False
        
        # Question text checks
        if len(q.question_text) < 20:
            return False
        
        if len(q.question_text) > 2000:  # Suspiciously long
            return False
        
        # Must have all 4 options
        options = [q.option_a, q.option_b, q.option_c, q.option_d]
        if not all(len(opt) >= 1 for opt in options):
            return False
        
        # Options should be distinct
        if len(set(options)) != 4:
            return False
        
        # Check for garbage/noise patterns
        garbage_patterns = [
            r'^[\d\s\.\-]+$',  # Only numbers and punctuation
            r'^[A-Z]{20,}$',   # All caps gibberish
            r'lorem ipsum',     # Placeholder text
        ]
        
        combined_text = q.question_text + ' '.join(options)
        for pattern in garbage_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                return False
        
        return True
    
    def _deduplicate(self, questions: List[ParsedQuestion]) -> List[ParsedQuestion]:
        """Remove duplicate questions using multiple strategies"""
        unique = []
        
        for q in questions:
            # Generate multiple hashes for comparison
            hashes = self._generate_hashes(q)
            
            # Check if any hash has been seen
            is_duplicate = any(h in self._seen_hashes for h in hashes)
            
            if not is_duplicate:
                # Add all hashes to seen set
                self._seen_hashes.update(hashes)
                self._seen_questions[q.id] = q
                unique.append(q)
            else:
                self.stats.duplicates_removed += 1
        
        return unique
    
    def _generate_hashes(self, q: ParsedQuestion) -> List[str]:
        """Generate multiple hash signatures for duplicate detection"""
        hashes = []
        
        # Hash 1: Full question text
        h1 = hashlib.md5(q.question_text.lower().encode()).hexdigest()
        hashes.append(f"full_{h1}")
        
        # Hash 2: Normalized question (remove numbers, special chars)
        normalized = re.sub(r'[^a-zA-Z\s]', '', q.question_text.lower())
        normalized = ' '.join(normalized.split())
        h2 = hashlib.md5(normalized.encode()).hexdigest()
        hashes.append(f"norm_{h2}")
        
        # Hash 3: First 100 chars (catches questions with different endings)
        h3 = hashlib.md5(q.question_text[:100].lower().encode()).hexdigest()
        hashes.append(f"prefix_{h3}")
        
        # Hash 4: Question + first option (catches exact copies)
        combined = f"{q.question_text}{q.option_a}".lower()
        h4 = hashlib.md5(combined.encode()).hexdigest()
        hashes.append(f"combo_{h4}")
        
        return hashes
    
    def _enhance_questions(self, questions: List[ParsedQuestion]) -> List[ParsedQuestion]:
        """Add metadata enhancements to questions"""
        enhanced = []
        
        for q in questions:
            # Auto-tag subject
            q.subject = self._detect_subject(q)
            
            # Extract year if possible
            q.year = self._extract_year(q)
            
            # Clean up text formatting
            q = self._clean_formatting(q)
            
            self.stats.enhanced += 1
            enhanced.append(q)
        
        return enhanced
    
    def _detect_subject(self, q: ParsedQuestion) -> Optional[str]:
        """Detect subject based on keyword matching"""
        combined_text = f"{q.question_text} {q.option_a} {q.option_b} {q.option_c} {q.option_d}"
        combined_text = combined_text.lower()
        
        subject_scores = defaultdict(int)
        
        for subject, keywords in self.subject_config.subjects.items():
            for keyword in keywords:
                if keyword.lower() in combined_text:
                    subject_scores[subject] += 1
        
        if subject_scores:
            # Return subject with highest score
            return max(subject_scores, key=subject_scores.get)
        
        return None
    
    def _extract_year(self, q: ParsedQuestion) -> Optional[str]:
        """Extract exam year from source file or question text"""
        # Try source file name first
        year_match = re.search(r'20[12]\d', q.source_file)
        if year_match:
            return year_match.group(0)
        
        # Try question text
        year_match = re.search(r'FMGE\s*(20[12]\d)', q.question_text, re.IGNORECASE)
        if year_match:
            return year_match.group(1)
        
        return None
    
    def _clean_formatting(self, q: ParsedQuestion) -> ParsedQuestion:
        """Clean up text formatting issues"""
        
        def clean_text(text: str) -> str:
            # Normalize whitespace
            text = re.sub(r'\s+', ' ', text)
            # Fix spacing around punctuation
            text = re.sub(r'\s+([.,;:!?])', r'\1', text)
            # Capitalize first letter
            if text and text[0].islower():
                text = text[0].upper() + text[1:]
            return text.strip()
        
        q.question_text = clean_text(q.question_text)
        q.option_a = clean_text(q.option_a)
        q.option_b = clean_text(q.option_b)
        q.option_c = clean_text(q.option_c)
        q.option_d = clean_text(q.option_d)
        
        if q.explanation:
            q.explanation = clean_text(q.explanation)
        
        return q
    
    def _final_validation(self, questions: List[ParsedQuestion]) -> List[ParsedQuestion]:
        """Final quality check before output"""
        final = []
        
        for q in questions:
            # Ensure question ends with proper punctuation
            if q.question_text and q.question_text[-1] not in '.?:':
                q.question_text += '?'
            
            # Validate answer is one of A, B, C, D
            if q.correct_answer and q.correct_answer not in 'ABCD':
                q.correct_answer = None
            
            final.append(q)
        
        return final
    
    def get_stats(self) -> Dict:
        """Return cleaning statistics"""
        return self.stats.to_dict()
    
    def get_subject_distribution(self, questions: List[ParsedQuestion]) -> Dict[str, int]:
        """Get distribution of questions by subject"""
        distribution = defaultdict(int)
        
        for q in questions:
            subject = q.subject or "Untagged"
            distribution[subject] += 1
        
        return dict(sorted(distribution.items(), key=lambda x: -x[1]))


class DuplicateAnalyzer:
    """
    Analyzes potential duplicates for manual review
    Helpful for quality assurance
    """
    
    def __init__(self, similarity_threshold: float = 0.8):
        self.similarity_threshold = similarity_threshold
    
    def find_similar_pairs(
        self, 
        questions: List[ParsedQuestion]
    ) -> List[Tuple[ParsedQuestion, ParsedQuestion, float]]:
        """Find pairs of similar questions"""
        similar_pairs = []
        
        for i, q1 in enumerate(questions):
            for q2 in questions[i+1:]:
                similarity = self._calculate_similarity(q1.question_text, q2.question_text)
                
                if similarity >= self.similarity_threshold:
                    similar_pairs.append((q1, q2, similarity))
        
        return sorted(similar_pairs, key=lambda x: -x[2])
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate Jaccard similarity between two texts"""
        # Tokenize
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0