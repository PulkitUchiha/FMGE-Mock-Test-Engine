"""
Image Handler Module - Improved Version
Better image detection and linking
"""

import fitz
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import hashlib
import base64
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class ExtractedImage:
    """Represents an extracted image"""
    id: str
    data: bytes
    width: int
    height: int
    page_number: int
    y_position: float
    source_file: str
    format: str = "png"
    
    @property
    def area(self) -> int:
        return self.width * self.height
    
    def to_base64(self) -> str:
        return base64.b64encode(self.data).decode('utf-8')
    
    def get_data_uri(self) -> str:
        b64 = self.to_base64()
        return f"data:image/{self.format};base64,{b64}"


class ImageExtractor:
    """Extracts images from PDFs"""
    
    MIN_WIDTH = 80
    MIN_HEIGHT = 80
    MIN_AREA = 8000
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path("data/processed/images")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._seen_hashes = set()
        
        self.stats = {
            "total_extracted": 0,
            "filtered_small": 0,
            "filtered_duplicate": 0,
            "filtered_watermark": 0,
            "valid_images": 0,
        }
    
    def extract_from_pdf(self, pdf_path: Path) -> Dict[int, List[ExtractedImage]]:
        """Extract all valid images from a PDF, organized by page number"""
        images_by_page = {}
        
        try:
            doc = fitz.open(pdf_path)
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_images = self._extract_page_images(page, page_num + 1, pdf_path.name)
                
                if page_images:
                    images_by_page[page_num + 1] = page_images
            
            doc.close()
            
            total = sum(len(imgs) for imgs in images_by_page.values())
            logger.info(f"Extracted {total} images from {pdf_path.name}")
            
        except Exception as e:
            logger.error(f"Error extracting images from {pdf_path}: {e}")
        
        return images_by_page
    
    def _extract_page_images(
        self, 
        page: fitz.Page, 
        page_num: int, 
        filename: str
    ) -> List[ExtractedImage]:
        """Extract valid images from a single page"""
        
        images = []
        image_list = page.get_images(full=True)
        
        for img_index, img in enumerate(image_list):
            xref = img[0]
            self.stats["total_extracted"] += 1
            
            try:
                base_image = page.parent.extract_image(xref)
                
                if not base_image:
                    continue
                
                img_bytes = base_image["image"]
                width = base_image.get("width", 0)
                height = base_image.get("height", 0)
                img_format = base_image.get("ext", "png")
                
                # Get Y position
                y_pos = self._get_image_y_position(page, img_index)
                
                if not self._is_valid_image(width, height, img_bytes):
                    continue
                
                img_id = f"{Path(filename).stem}_p{page_num}_i{img_index}"
                
                extracted = ExtractedImage(
                    id=img_id,
                    data=img_bytes,
                    width=width,
                    height=height,
                    page_number=page_num,
                    y_position=y_pos,
                    source_file=filename,
                    format=img_format
                )
                
                images.append(extracted)
                self.stats["valid_images"] += 1
                
            except Exception as e:
                logger.debug(f"Error extracting image {xref}: {e}")
        
        images.sort(key=lambda x: x.y_position)
        return images
    
    def _get_image_y_position(self, page: fitz.Page, img_index: int) -> float:
        """Get Y position of image on page"""
        try:
            image_info = page.get_image_info()
            if img_index < len(image_info):
                bbox = image_info[img_index].get("bbox", [0, 0, 0, 0])
                return bbox[1] if len(bbox) > 1 else 0
        except:
            pass
        return 0
    
    def _is_valid_image(self, width: int, height: int, data: bytes) -> bool:
        """Check if image should be included"""
        
        if width < self.MIN_WIDTH or height < self.MIN_HEIGHT:
            self.stats["filtered_small"] += 1
            return False
        
        if width * height < self.MIN_AREA:
            self.stats["filtered_small"] += 1
            return False
        
        # Skip full-width banners
        if width > 800 and height < 60:
            self.stats["filtered_watermark"] += 1
            return False
        
        # Skip tall thin strips
        if height > 500 and width < 50:
            self.stats["filtered_watermark"] += 1
            return False
        
        # Duplicate check
        img_hash = hashlib.md5(data).hexdigest()
        if img_hash in self._seen_hashes:
            self.stats["filtered_duplicate"] += 1
            return False
        
        self._seen_hashes.add(img_hash)
        return True
    
    def save_image(self, image: ExtractedImage) -> Path:
        """Save an image to disk"""
        filepath = self.output_dir / f"{image.id}.{image.format}"
        with open(filepath, 'wb') as f:
            f.write(image.data)
        return filepath
    
    def get_stats(self) -> Dict:
        return self.stats.copy()


class SmartImageLinker:
    """
    Improved image linking with better detection and matching
    """
    
    # More specific patterns that MUST indicate an image is referenced
    # These are phrases, not just words
    IMAGE_PHRASES = [
        r'(?:shown|given|seen|depicted|illustrated)\s+(?:in\s+)?(?:the\s+)?(?:image|figure|picture|photograph|diagram)',
        r'(?:image|figure|picture|photograph|diagram)\s+(?:shown|given|below|above)',
        r'identify\s+(?:the\s+)?(?:structure|finding|lesion|abnormality)',
        r'what\s+(?:is|does)\s+(?:the\s+)?(?:image|figure|arrow|structure)',
        r'(?:x-ray|xray|radiograph|ct\s*scan|mri|ecg|ekg|ultrasound|usg)\s+(?:shows|showing|revealed|image)',
        r'(?:clinical|gross)\s+photograph',
        r'histology\s+(?:slide|image|section)',
        r'(?:blood\s+)?smear\s+(?:shows|showing|image)',
        r'culture\s+(?:shown|image|plate)',
        r'fundus\s+(?:image|photograph|picture)',
        r'(?:the\s+)?(?:given|following)\s+(?:image|figure|picture)',
        r'(?:arrow|arrowhead)\s+(?:points|shows|indicates|marks)',
        r'marked\s+(?:structure|area|region|finding)',
        r'what\s+is\s+(?:the\s+)?(?:diagnosis|finding|abnormality)\s+(?:in|from)',
        r'biopsy\s+(?:shows|image|specimen)',
        r'specimen\s+(?:shown|image)',
        r'lesion\s+(?:shown|seen|image)',
        r'rash\s+(?:shown|seen|image)',
        r'(?:ct|mri|pet)\s+(?:scan)?\s+(?:image|finding|shows)',
        r'electrocardiogram\s+(?:shows|showing|image)',
        r'angiography\s+(?:shows|image)',
    ]
    
    # Compile patterns for efficiency
    def __init__(self):
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) 
            for pattern in self.IMAGE_PHRASES
        ]
    
    def question_needs_image(self, question_text: str) -> Tuple[bool, str]:
        """
        Check if a question references an image
        Returns: (needs_image: bool, matched_pattern: str)
        """
        for pattern in self._compiled_patterns:
            match = pattern.search(question_text)
            if match:
                return True, match.group(0)
        
        return False, ""
    
    def link_images_to_questions(
        self,
        questions: List[Dict],
        images_by_page: Dict[int, List[ExtractedImage]],
        text_positions: Dict[str, int] = None  # question_id -> page_number from parsing
    ) -> Dict[str, List[ExtractedImage]]:
        """
        Link images to questions using multiple strategies
        """
        links = {}
        
        for q in questions:
            q_id = q.get('id', '')
            q_text = q.get('question_text', '')
            q_page = q.get('page_number', 0)
            
            needs_image, pattern = self.question_needs_image(q_text)
            
            if not needs_image:
                continue
            
            # Try to find matching images
            matched = self._find_best_images(q_page, images_by_page)
            
            if matched:
                links[q_id] = matched
        
        return links
    
    def _find_best_images(
        self,
        question_page: int,
        images_by_page: Dict[int, List[ExtractedImage]]
    ) -> List[ExtractedImage]:
        """Find the best matching images for a question"""
        
        candidates = []
        
        # Priority order: same page, previous page, next page
        for offset in [0, -1, 1, -2, 2]:
            page = question_page + offset
            if page in images_by_page:
                candidates.extend(images_by_page[page])
        
        if not candidates:
            return []
        
        # Sort by size (larger = more likely to be content, not decoration)
        candidates.sort(key=lambda x: x.area, reverse=True)
        
        # Return top 1-2 images
        return candidates[:2]
    
    def get_image_for_question(
        self,
        question_text: str,
        question_page: int,
        images_by_page: Dict[int, List[ExtractedImage]]
    ) -> Optional[ExtractedImage]:
        """Get the most likely image for a specific question"""
        
        needs_image, _ = self.question_needs_image(question_text)
        
        if not needs_image:
            return None
        
        images = self._find_best_images(question_page, images_by_page)
        return images[0] if images else None


class PageTracker:
    """
    Tracks which page each question is actually on
    by analyzing the text positions in the PDF
    """
    
    def __init__(self):
        self.question_pages = {}  # question_number -> actual_page
    
    def analyze_pdf(self, pdf_path: Path) -> Dict[str, int]:
        """
        Analyze PDF to find actual page numbers for questions
        """
        self.question_pages = {}
        
        try:
            doc = fitz.open(pdf_path)
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                
                # Find question markers on this page
                # Pattern: "X. Question" at start of line
                patterns = [
                    r'^\s*(\d{1,3})\s*\.\s*Question\s*:',
                    r'^\s*Q\s*\.?\s*(\d{1,3})',
                    r'^\s*(\d{1,3})\s*\.\s+[A-Z]',
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, text, re.MULTILINE | re.IGNORECASE)
                    for match in matches:
                        q_num = match if isinstance(match, str) else match[0]
                        self.question_pages[q_num] = page_num + 1
            
            doc.close()
            
        except Exception as e:
            logger.error(f"Error analyzing PDF pages: {e}")
        
        return self.question_pages
    
    def get_page_for_question(self, question_number: str) -> Optional[int]:
        return self.question_pages.get(question_number)