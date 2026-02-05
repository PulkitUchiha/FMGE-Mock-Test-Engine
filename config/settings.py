"""
Configuration settings for FMGE Practice Engine
All constants and configurable parameters in one place
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict
import os

# Base paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_PDF_DIR = DATA_DIR / "raw_pdfs"
PROCESSED_DIR = DATA_DIR / "processed"
SESSIONS_DIR = DATA_DIR / "sessions"
QUESTIONS_FILE = DATA_DIR / "questions.json"

# Ensure directories exist
for dir_path in [DATA_DIR, RAW_PDF_DIR, PROCESSED_DIR, SESSIONS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)


@dataclass
class ParserConfig:
    """Configuration for PDF parsing"""
    
    # Minimum requirements for valid question
    min_question_length: int = 20
    min_option_length: int = 1
    required_options: int = 4
    
    # Patterns to identify question starts
    question_patterns: List[str] = field(default_factory=lambda: [
        r'^\d{1,4}[\.\)\:]',           # 1. or 1) or 1:
        r'^Q\s*\d{1,4}[\.\)\:]?',      # Q1. or Q 1 or Q1)
        r'^Question\s*\d{1,4}',        # Question 1
        r'^\[\d{1,4}\]',               # [1]
    ])
    
    # Option patterns
    option_patterns: List[str] = field(default_factory=lambda: [
        r'^[A-Da-d][\.\)\:]',          # A. or a) or A:
        r'^\([A-Da-d]\)',              # (A) or (a)
        r'^[A-Da-d]\s*[-–]',           # A - or a –
        r'^Option\s*[A-Da-d]',         # Option A
    ])
    
    # Answer patterns
    answer_patterns: List[str] = field(default_factory=lambda: [
        r'Ans(?:wer)?[\s\.:]*[A-Da-d]',
        r'Correct[\s\.:]*[A-Da-d]',
        r'Key[\s\.:]*[A-Da-d]',
        r'\*[A-Da-d]\*',               # *A*
    ])
    
    # Noise patterns to remove
    noise_patterns: List[str] = field(default_factory=lambda: [
        r'PrepLadder',
        r'DAMS',
        r'Marrow',
        r'Page\s*\d+',
        r'www\.',
        r'Copyright',
        r'All Rights Reserved',
    ])


@dataclass
class ImageConfig:
    """Configuration for image handling"""
    
    min_width: int = 50
    min_height: int = 50
    max_aspect_ratio: float = 10.0
    min_aspect_ratio: float = 0.1
    
    # Skip images smaller than this (logos/icons)
    min_area: int = 5000
    
    # Similarity threshold for deduplication
    similarity_threshold: float = 0.95
    
    # Common watermark dimensions to filter
    watermark_sizes: List[tuple] = field(default_factory=lambda: [
        (100, 30),   # Typical text watermark
        (50, 50),    # Square logos
        (32, 32),    # Icons
    ])


@dataclass
class ExamConfig:
    """Configuration for exam modes"""
    
    daily_practice_count: int = 50
    full_mock_count: int = 150
    
    # Time limits in minutes
    daily_time_limit: int = 60
    mock_time_limit: int = 180
    
    # Marking scheme
    correct_marks: float = 1.0
    incorrect_marks: float = 0.0  # No negative marking in FMGE
    unattempted_marks: float = 0.0


@dataclass
class SubjectConfig:
    """FMGE subject categories and keywords"""
    
    subjects: Dict[str, List[str]] = field(default_factory=lambda: {
        "Anatomy": ["nerve", "muscle", "bone", "artery", "vein", "ligament"],
        "Physiology": ["hormone", "reflex", "cardiac output", "GFR"],
        "Biochemistry": ["enzyme", "metabolism", "vitamin", "protein", "amino acid"],
        "Pathology": ["tumor", "carcinoma", "necrosis", "inflammation"],
        "Pharmacology": ["drug", "dose", "mechanism", "receptor"],
        "Microbiology": ["bacteria", "virus", "fungus", "parasite", "infection"],
        "Forensic Medicine": ["poison", "injury", "death", "autopsy"],
        "Community Medicine": ["epidemiology", "vaccine", "sanitation", "statistics"],
        "Ophthalmology": ["eye", "retina", "cornea", "vision", "glaucoma"],
        "ENT": ["ear", "nose", "throat", "hearing", "vertigo"],
        "Medicine": ["diabetes", "hypertension", "fever", "anemia", "jaundice"],
        "Surgery": ["incision", "hernia", "appendix"],
        "Pediatrics": ["child", "infant", "neonate", "vaccination"],
        "Obstetrics & Gynecology": ["pregnancy", "delivery", "uterus", "ovary", "menstrual"],
        "Psychiatry": ["depression", "schizophrenia", "anxiety"],
        "Dermatology": ["skin", "rash", "lesion", "eczema"],
        "Radiology": ["x-ray", "ct", "mri", "ultrasound", "radiograph"],
        "Anaesthesia": ["sedation", "intubation", "ventilation"],
        "Orthopedics": ["fracture", "joint", "dislocation"],
    })



# Global config instances
PARSER_CONFIG = ParserConfig()
IMAGE_CONFIG = ImageConfig()
EXAM_CONFIG = ExamConfig()
SUBJECT_CONFIG = SubjectConfig()