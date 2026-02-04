"""
Parsing Strategies Module
Different strategies for different PDF formats
"""

import re
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import hashlib
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExtractedQuestion:
    """Raw extracted question before validation"""
    question_number: str
    question_text: str
    options: Dict[str, str]  # {'A': '...', 'B': '...', ...}
    correct_answer: Optional[str]
    explanation: Optional[str]
    raw_block: str  # Original text block
    source_file: str
    page_number: int
    has_image: bool = False
    image_refs: List[str] = field(default_factory=list)


class ParsingStrategy(ABC):
    """Abstract base class for parsing strategies"""
    
    @abstractmethod
    def can_parse(self, text: str) -> bool:
        """Check if this strategy can parse the given text"""
        pass
    
    @abstractmethod
    def parse(self, text: str, filename: str) -> List[ExtractedQuestion]:
        """Parse text and extract questions"""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Return strategy name"""
        pass


class QuestionColonStrategy(ParsingStrategy):
    """
    Strategy for "X. Question:" + "Option X:" format
    
    Example:
    1. Question :
    What is the capital of France?
    
    Option 1 :
    London
    Option 2 :
    Paris
    Option 3 :
    Berlin
    Option 4 :
    Madrid
    
    Correct option : 2
    """
    
    def get_name(self) -> str:
        return "Question Colon Format"
    
    def can_parse(self, text: str) -> bool:
        # Check for characteristic patterns
        has_question = bool(re.search(r'\d+\s*\.\s*Question\s*:', text, re.IGNORECASE))
        has_options = bool(re.search(r'Option\s*[1-4]\s*:', text, re.IGNORECASE))
        return has_question and has_options
    
    def parse(self, text: str, filename: str) -> List[ExtractedQuestion]:
        questions = []
        
        # Split by question pattern
        pattern = r'(?:^|\n)\s*(\d{1,3})\s*\.\s*Question\s*:\s*\n?'
        parts = re.split(pattern, text, flags=re.IGNORECASE)
        
        # Parts will be: [before, num1, content1, num2, content2, ...]
        i = 1
        while i < len(parts) - 1:
            q_num = parts[i]
            content = parts[i + 1]
            
            extracted = self._parse_block(q_num, content, filename)
            if extracted:
                questions.append(extracted)
            
            i += 2
        
        return questions
    
    def _parse_block(self, q_num: str, content: str, filename: str) -> Optional[ExtractedQuestion]:
        """Parse a single question block"""
        
        # Extract question text (before Option 1)
        match = re.search(r'Option\s*1\s*:', content, re.IGNORECASE)
        if not match:
            return None
        
        question_text = content[:match.start()].strip()
        
        # Extract options
        options = {}
        option_pattern = r'Option\s*([1-4])\s*:\s*\n?(.*?)(?=Option\s*[1-4]\s*:|Correct\s*option|Solutions|Reference|$)'
        option_matches = re.findall(option_pattern, content, re.IGNORECASE | re.DOTALL)
        
        option_map = {'1': 'A', '2': 'B', '3': 'C', '4': 'D'}
        for num, text in option_matches:
            letter = option_map.get(num, num)
            options[letter] = self._clean_text(text)
        
        if len(options) < 4:
            return None
        
        # Extract answer
        correct_answer = None
        ans_match = re.search(r'Correct\s*option\s*:\s*(\d)', content, re.IGNORECASE)
        if ans_match:
            correct_answer = option_map.get(ans_match.group(1))
        else:
            # Try alternative pattern
            ans_match = re.search(r'Correct\s*Answer\s*:\s*([A-Da-d])', content, re.IGNORECASE)
            if ans_match:
                correct_answer = ans_match.group(1).upper()
        
        # Extract explanation
        explanation = None
        exp_match = re.search(r'Explanation\s*:\s*(.*?)(?=Reference|Incorrect|Learning|$)', 
                              content, re.IGNORECASE | re.DOTALL)
        if exp_match:
            explanation = self._clean_text(exp_match.group(1))
        
        # Check for image references
        has_image = bool(re.search(r'(?:image|figure|diagram|picture|shown|given below)', 
                                   question_text, re.IGNORECASE))
        
        return ExtractedQuestion(
            question_number=q_num,
            question_text=self._clean_text(question_text),
            options=options,
            correct_answer=correct_answer,
            explanation=explanation,
            raw_block=content[:500],
            source_file=filename,
            page_number=int(q_num) // 3 + 1,
            has_image=has_image
        )
    
    def _clean_text(self, text: str) -> str:
        """Clean text by normalizing whitespace"""
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


class QDotStrategy(ParsingStrategy):
    """
    Strategy for "Q1." or "Q.1" format with A/B/C/D options
    
    Example:
    Q1. What is the capital of France?
    A. London
    B. Paris
    C. Berlin
    D. Madrid
    
    Ans: B
    """
    
    def get_name(self) -> str:
        return "Q-Dot Format"
    
    def can_parse(self, text: str) -> bool:
        has_q = bool(re.search(r'Q\s*\.?\s*\d+', text, re.IGNORECASE))
        has_opts = bool(re.search(r'(?:^|\n)\s*[A-D]\s*[\.\)]', text, re.MULTILINE))
        return has_q and has_opts
    
    def parse(self, text: str, filename: str) -> List[ExtractedQuestion]:
        questions = []
        
        # Split by Q pattern
        pattern = r'(?:^|\n)\s*Q\s*\.?\s*(\d{1,3})\s*[\.\)\:]?\s*'
        parts = re.split(pattern, text, flags=re.IGNORECASE)
        
        i = 1
        while i < len(parts) - 1:
            q_num = parts[i]
            content = parts[i + 1]
            
            extracted = self._parse_block(q_num, content, filename)
            if extracted:
                questions.append(extracted)
            
            i += 2
        
        return questions
    
    def _parse_block(self, q_num: str, content: str, filename: str) -> Optional[ExtractedQuestion]:
        """Parse a single question block"""
        
        # Find where options start
        opt_match = re.search(r'(?:^|\n)\s*[Aa]\s*[\.\)\:]', content)
        if not opt_match:
            return None
        
        question_text = content[:opt_match.start()].strip()
        options_text = content[opt_match.start():]
        
        # Extract options A, B, C, D
        options = {}
        opt_pattern = r'(?:^|\n)\s*([A-Da-d])\s*[\.\)\:]\s*(.*?)(?=(?:\n\s*[A-Da-d]\s*[\.\)\:])|(?:\n\s*(?:Ans|Answer|Correct|Explanation))|$)'
        opt_matches = re.findall(opt_pattern, options_text, re.IGNORECASE | re.DOTALL)
        
        for letter, text in opt_matches:
            options[letter.upper()] = self._clean_text(text)
        
        if len(options) < 4:
            return None
        
        # Extract answer
        correct_answer = None
        ans_patterns = [
            r'Ans(?:wer)?\s*[\.\:\-]?\s*([A-Da-d])',
            r'Correct\s*(?:Answer|Option)?\s*[\.\:\-]?\s*([A-Da-d])',
            r'Answer\s*[\.\:\-]?\s*([A-Da-d])',
        ]
        
        for pattern in ans_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                correct_answer = match.group(1).upper()
                break
        
        # Extract explanation
        explanation = None
        exp_match = re.search(r'(?:Explanation|Solution)\s*[\.\:\-]?\s*(.*?)(?=Q\s*\.?\s*\d|$)', 
                              content, re.IGNORECASE | re.DOTALL)
        if exp_match:
            explanation = self._clean_text(exp_match.group(1))
        
        has_image = bool(re.search(r'(?:image|figure|diagram|picture|shown|given)', 
                                   question_text, re.IGNORECASE))
        
        return ExtractedQuestion(
            question_number=q_num,
            question_text=self._clean_text(question_text),
            options=options,
            correct_answer=correct_answer,
            explanation=explanation,
            raw_block=content[:500],
            source_file=filename,
            page_number=int(q_num) // 3 + 1,
            has_image=has_image
        )
    
    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


class NumberDotStrategy(ParsingStrategy):
    """
    Strategy for simple numbered format: "1." + "A." options
    
    Example:
    1. What is the capital of France?
    A. London
    B. Paris
    C. Berlin
    D. Madrid
    
    Answer: B
    """
    
    def get_name(self) -> str:
        return "Number-Dot Format"
    
    def can_parse(self, text: str) -> bool:
        # Look for numbered questions followed by lettered options
        has_nums = bool(re.search(r'^\s*\d{1,3}\s*\.\s*[A-Z]', text, re.MULTILINE))
        has_opts = bool(re.search(r'(?:^|\n)\s*[A-D]\s*[\.\)]', text, re.MULTILINE))
        return has_nums and has_opts
    
    def parse(self, text: str, filename: str) -> List[ExtractedQuestion]:
        questions = []
        
        # Split by number pattern at start of line
        pattern = r'(?:^|\n)\s*(\d{1,3})\s*\.\s+(?=[A-Z])'
        parts = re.split(pattern, text, flags=re.MULTILINE)
        
        i = 1
        while i < len(parts) - 1:
            q_num = parts[i]
            content = parts[i + 1]
            
            # Skip if this looks like a list item within explanation
            if len(content) < 50:
                i += 2
                continue
            
            extracted = self._parse_block(q_num, content, filename)
            if extracted:
                questions.append(extracted)
            
            i += 2
        
        return questions
    
    def _parse_block(self, q_num: str, content: str, filename: str) -> Optional[ExtractedQuestion]:
        """Parse a single question block"""
        
        # Find where options start
        opt_match = re.search(r'(?:^|\n)\s*[Aa]\s*[\.\)\:]', content)
        if not opt_match:
            return None
        
        question_text = content[:opt_match.start()].strip()
        
        if len(question_text) < 15:
            return None
        
        # Extract options
        options = {}
        opt_pattern = r'(?:^|\n)\s*([A-Da-d])\s*[\.\)\:]\s*(.*?)(?=(?:\n\s*[A-Da-d]\s*[\.\)\:])|(?:\n\s*(?:Ans|Answer|Correct|Explanation|\d+\s*\.))|$)'
        opt_matches = re.findall(opt_pattern, content, re.IGNORECASE | re.DOTALL)
        
        for letter, text in opt_matches:
            text = self._clean_text(text)
            if text:
                options[letter.upper()] = text
        
        if len(options) < 4:
            return None
        
        # Extract answer
        correct_answer = None
        ans_patterns = [
            r'Ans(?:wer)?\s*[\.\:\-]?\s*\(?([A-Da-d])\)?',
            r'Correct\s*(?:Answer|Option)?\s*[\.\:\-]?\s*\(?([A-Da-d])\)?',
            r'\*\*?([A-Da-d])\*\*?',
        ]
        
        for pattern in ans_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                correct_answer = match.group(1).upper()
                break
        
        # Extract explanation
        explanation = None
        exp_match = re.search(r'(?:Explanation|Solution|Rationale)\s*[\.\:\-]?\s*(.*?)(?=\d+\s*\.|$)', 
                              content, re.IGNORECASE | re.DOTALL)
        if exp_match:
            explanation = self._clean_text(exp_match.group(1))
        
        has_image = bool(re.search(r'(?:image|figure|diagram|picture|shown|given)', 
                                   question_text, re.IGNORECASE))
        
        return ExtractedQuestion(
            question_number=q_num,
            question_text=self._clean_text(question_text),
            options=options,
            correct_answer=correct_answer,
            explanation=explanation,
            raw_block=content[:500],
            source_file=filename,
            page_number=int(q_num) // 3 + 1,
            has_image=has_image
        )
    
    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


class NumberParenStrategy(ParsingStrategy):
    """
    Strategy for "1)" format with (A) or A) options
    
    Example:
    1) What is the capital of France?
    (A) London
    (B) Paris
    (C) Berlin
    (D) Madrid
    """
    
    def get_name(self) -> str:
        return "Number-Paren Format"
    
    def can_parse(self, text: str) -> bool:
        has_nums = bool(re.search(r'^\s*\d{1,3}\s*\)', text, re.MULTILINE))
        has_opts = bool(re.search(r'(?:^|\n)\s*\(?[A-D]\)', text, re.MULTILINE))
        return has_nums and has_opts
    
    def parse(self, text: str, filename: str) -> List[ExtractedQuestion]:
        questions = []
        
        # Split by number-paren pattern
        pattern = r'(?:^|\n)\s*(\d{1,3})\s*\)\s*'
        parts = re.split(pattern, text, flags=re.MULTILINE)
        
        i = 1
        while i < len(parts) - 1:
            q_num = parts[i]
            content = parts[i + 1]
            
            if len(content) < 50:
                i += 2
                continue
            
            extracted = self._parse_block(q_num, content, filename)
            if extracted:
                questions.append(extracted)
            
            i += 2
        
        return questions
    
    def _parse_block(self, q_num: str, content: str, filename: str) -> Optional[ExtractedQuestion]:
        """Parse question block"""
        
        # Find options
        opt_match = re.search(r'(?:^|\n)\s*\(?[Aa]\)?[\.\)\:]?', content)
        if not opt_match:
            return None
        
        question_text = content[:opt_match.start()].strip()
        
        if len(question_text) < 15:
            return None
        
        # Extract options - handle both (A) and A) formats
        options = {}
        opt_pattern = r'(?:^|\n)\s*\(?([A-Da-d])\)?[\.\)\:]?\s*(.*?)(?=(?:\n\s*\(?[A-Da-d]\))|(?:\n\s*(?:Ans|Answer|Correct|\d+\s*\)))|$)'
        opt_matches = re.findall(opt_pattern, content, re.IGNORECASE | re.DOTALL)
        
        for letter, text in opt_matches:
            text = self._clean_text(text)
            if text:
                options[letter.upper()] = text
        
        if len(options) < 4:
            return None
        
        # Extract answer
        correct_answer = None
        ans_match = re.search(r'(?:Ans(?:wer)?|Correct)\s*[\.\:\-]?\s*\(?([A-Da-d])\)?', 
                              content, re.IGNORECASE)
        if ans_match:
            correct_answer = ans_match.group(1).upper()
        
        # Explanation
        explanation = None
        exp_match = re.search(r'(?:Explanation|Solution)\s*[\.\:\-]?\s*(.*?)(?=\d+\s*\)|$)', 
                              content, re.IGNORECASE | re.DOTALL)
        if exp_match:
            explanation = self._clean_text(exp_match.group(1))
        
        has_image = bool(re.search(r'(?:image|figure|diagram|picture|shown|given)', 
                                   question_text, re.IGNORECASE))
        
        return ExtractedQuestion(
            question_number=q_num,
            question_text=self._clean_text(question_text),
            options=options,
            correct_answer=correct_answer,
            explanation=explanation,
            raw_block=content[:500],
            source_file=filename,
            page_number=int(q_num) // 3 + 1,
            has_image=has_image
        )
    
    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


class GenericStrategy(ParsingStrategy):
    """
    Fallback strategy that tries multiple approaches
    """
    
    def get_name(self) -> str:
        return "Generic Fallback"
    
    def can_parse(self, text: str) -> bool:
        # Always returns True as fallback
        return True
    
    def parse(self, text: str, filename: str) -> List[ExtractedQuestion]:
        questions = []
        
        # Try to find any numbered items with options
        # Very flexible pattern
        pattern = r'(?:^|\n)\s*(?:Q\.?\s*)?(\d{1,3})\s*[\.\)\:]'
        matches = list(re.finditer(pattern, text, re.MULTILINE))
        
        for i, match in enumerate(matches):
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            
            content = text[start:end].strip()
            
            if len(content) < 100:
                continue
            
            # Try to find 4 options anywhere in the content
            options = self._find_options(content)
            
            if len(options) >= 4:
                q_num = match.group(1)
                
                # Question text is everything before first option
                q_text = self._extract_question(content, options)
                
                if q_text and len(q_text) >= 15:
                    answer = self._find_answer(content)
                    explanation = self._find_explanation(content)
                    
                    has_image = bool(re.search(r'(?:image|figure|diagram|picture|shown|given)', 
                                               q_text, re.IGNORECASE))
                    
                    questions.append(ExtractedQuestion(
                        question_number=q_num,
                        question_text=q_text,
                        options=options,
                        correct_answer=answer,
                        explanation=explanation,
                        raw_block=content[:500],
                        source_file=filename,
                        page_number=int(q_num) // 3 + 1,
                        has_image=has_image
                    ))
        
        return questions
    
    def _find_options(self, content: str) -> Dict[str, str]:
        """Try multiple patterns to find options"""
        
        options = {}
        
        # Pattern list to try
        patterns = [
            r'(?:^|\n)\s*([A-Da-d])\s*[\.\)\:]\s*(.*?)(?=\n\s*[A-Da-d]\s*[\.\)\:]|\n\s*(?:Ans|Correct)|$)',
            r'(?:^|\n)\s*\(([A-Da-d])\)\s*(.*?)(?=\n\s*\([A-Da-d]\)|\n\s*(?:Ans|Correct)|$)',
            r'Option\s*([1-4A-Da-d])\s*:\s*(.*?)(?=Option\s*[1-4A-Da-d]|Correct|$)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            
            for letter, text in matches:
                letter = letter.upper()
                if letter in '1234':
                    letter = {'1': 'A', '2': 'B', '3': 'C', '4': 'D'}[letter]
                
                text = re.sub(r'\s+', ' ', text).strip()
                if text and letter in 'ABCD':
                    options[letter] = text
            
            if len(options) >= 4:
                break
        
        return options
    
    def _extract_question(self, content: str, options: Dict[str, str]) -> str:
        """Extract question text"""
        
        # Find where first option appears
        first_opt = None
        for opt_text in options.values():
            idx = content.find(opt_text[:20])
            if idx != -1:
                if first_opt is None or idx < first_opt:
                    first_opt = idx
        
        if first_opt:
            q_text = content[:first_opt]
            # Remove option marker if present
            q_text = re.sub(r'[A-Da-d]\s*[\.\)\:]?\s*$', '', q_text)
            return re.sub(r'\s+', ' ', q_text).strip()
        
        # Fallback: first paragraph
        parts = content.split('\n\n')
        return re.sub(r'\s+', ' ', parts[0]).strip() if parts else ""
    
    def _find_answer(self, content: str) -> Optional[str]:
        """Find answer using multiple patterns"""
        
        patterns = [
            r'Correct\s*option\s*:\s*(\d)',
            r'Correct\s*Answer\s*:\s*([A-Da-d])',
            r'Ans(?:wer)?\s*[\.\:\-]?\s*\(?([A-Da-d1-4])\)?',
            r'Answer\s*[\.\:\-]?\s*([A-Da-d])',
            r'\*\*?([A-Da-d])\*\*?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                ans = match.group(1).upper()
                if ans in '1234':
                    ans = {'1': 'A', '2': 'B', '3': 'C', '4': 'D'}[ans]
                if ans in 'ABCD':
                    return ans
        
        return None
    
    def _find_explanation(self, content: str) -> Optional[str]:
        """Find explanation"""
        
        patterns = [
            r'Explanation\s*:\s*(.*?)(?=Reference|Learning|$)',
            r'Solution\s*:\s*(.*?)(?=Reference|Learning|$)',
            r'Rationale\s*:\s*(.*?)(?=Reference|Learning|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                exp = match.group(1)
                exp = re.sub(r'\s+', ' ', exp).strip()
                if len(exp) > 20:
                    return exp[:2000]
        
        return None


# Factory function to get all strategies
def get_all_strategies() -> List[ParsingStrategy]:
    """Return all available parsing strategies in order of preference"""
    return [
        QuestionColonStrategy(),
        QDotStrategy(),
        NumberDotStrategy(),
        NumberParenStrategy(),
        GenericStrategy(),  # Fallback
    ]