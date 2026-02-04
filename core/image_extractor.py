"""
Image Extractor Module
Extracts images from PDFs and links them to questions
FIXED: Stores RELATIVE image paths (portable, UI-safe)
"""

import fitz
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import hashlib
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExtractedImage:
    """Extracted image with metadata"""
    id: str
    data: bytes
    width: int
    height: int
    page_number: int
    position: Tuple[float, float, float, float]
    format: str
    source_file: str

    @property
    def area(self) -> int:
        return self.width * self.height


class ImageExtractor:
    """
    Extracts images from PDFs and links them to questions
    """

    MIN_WIDTH = 80
    MIN_HEIGHT = 80
    MIN_AREA = 10000

    SKIP_SIZES = [
        (32, 32), (48, 48), (64, 64),
        (100, 30), (150, 40), (200, 50),
    ]

    def __init__(self, output_dir: Path = None):
        # ABSOLUTE disk location
        self.output_dir = output_dir or Path("data/processed/images")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._seen_hashes = set()

    # ---------------------------
    # Utility helpers
    # ---------------------------

    def _safe_filename(self, name: str) -> str:
        """Make filename safe across OS"""
        return (
            name.replace(" ", "_")
                .replace(".pdf", "")
                .replace("/", "_")
                .replace("\\", "_")
        )

    # ---------------------------
    # Extraction
    # ---------------------------

    def extract_from_pdf(self, pdf_path: Path) -> Dict[int, List[ExtractedImage]]:
        """
        Extract images from PDF, grouped by page number
        Returns: {page_number: [ExtractedImage]}
        """

        images_by_page: Dict[int, List[ExtractedImage]] = {}

        try:
            doc = fitz.open(pdf_path)

            for page_index in range(len(doc)):
                page = doc[page_index]
                page_num = page_index + 1

                images = self._extract_page_images(
                    page=page,
                    page_num=page_num,
                    filename=pdf_path.name
                )

                if images:
                    images_by_page[page_num] = images

            doc.close()

        except Exception as e:
            logger.error(f"Image extraction failed for {pdf_path}: {e}")

        return images_by_page

    def _extract_page_images(
        self,
        page: fitz.Page,
        page_num: int,
        filename: str
    ) -> List[ExtractedImage]:

        extracted_images: List[ExtractedImage] = []
        image_list = page.get_images(full=True)

        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]

            try:
                base_image = page.parent.extract_image(xref)
                if not base_image:
                    continue

                img_bytes = base_image["image"]
                width = base_image.get("width", 0)
                height = base_image.get("height", 0)

                if not self._is_valid_image(width, height, img_bytes):
                    continue

                position = self._get_image_position(page)

                img_id = f"{filename}_{page_num}_{img_index}"

                extracted_images.append(
                    ExtractedImage(
                        id=img_id,
                        data=img_bytes,
                        width=width,
                        height=height,
                        page_number=page_num,
                        position=position,
                        format=base_image.get("ext", "png"),
                        source_file=filename
                    )
                )

            except Exception as e:
                logger.debug(f"Failed extracting image xref={xref}: {e}")

        return extracted_images

    def _is_valid_image(self, width: int, height: int, data: bytes) -> bool:
        if width < self.MIN_WIDTH or height < self.MIN_HEIGHT:
            return False

        if width * height < self.MIN_AREA:
            return False

        for w, h in self.SKIP_SIZES:
            if abs(width - w) < 10 and abs(height - h) < 10:
                return False

        aspect = width / height if height else 0
        if aspect > 8 or aspect < 0.125:
            return False

        img_hash = hashlib.md5(data).hexdigest()
        if img_hash in self._seen_hashes:
            return False

        self._seen_hashes.add(img_hash)
        return True

    def _get_image_position(
        self,
        page: fitz.Page
    ) -> Tuple[float, float, float, float]:
        try:
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") == 1:
                    return tuple(block.get("bbox", (0, 0, 0, 0)))
        except Exception:
            pass

        return (0, 0, 0, 0)

    # ---------------------------
    # Saving & linking
    # ---------------------------

    def save_image(self, image: ExtractedImage) -> str:
        """
        Save image to disk and return RELATIVE path (to DATA_DIR)
        """

        safe_source = self._safe_filename(image.source_file)
        filename = f"{safe_source}_{image.page_number}_{image.id.split('_')[-1]}.{image.format}"

        absolute_path = self.output_dir / filename
        absolute_path.parent.mkdir(parents=True, exist_ok=True)

        with open(absolute_path, "wb") as f:
            f.write(image.data)

        # 🔥 CRITICAL: return RELATIVE path
        return f"processed/images/{filename}"

    def link_images_to_questions(
        self,
        images_by_page: Dict[int, List[ExtractedImage]],
        question_pages: Dict[str, int]
    ) -> Dict[str, List[str]]:
        """
        Link images to questions based on page proximity
        Returns: {question_id: [relative_image_paths]}
        """

        links: Dict[str, List[str]] = {}

        for q_id, q_page in question_pages.items():
            candidates: List[ExtractedImage] = []

            for offset in (0, -1, 1):
                page = q_page + offset
                if page in images_by_page:
                    candidates.extend(images_by_page[page])

            if not candidates:
                continue

            image_paths: List[str] = []
            for img in candidates:
                relative_path = self.save_image(img)
                image_paths.append(relative_path)

            links[q_id] = image_paths

        return links


class ImageQuestionMatcher:
    """
    Heuristic matcher to detect whether a question needs an image
    """

    def __init__(self):
        self.image_keywords = [
            "image", "figure", "diagram", "picture", "shown", "given",
            "above", "below", "following", "radiograph", "x-ray",
            "ct", "mri", "ecg", "graph", "chart", "table"
        ]

    def needs_image(self, question_text: str) -> bool:
        text = question_text.lower()
        return any(k in text for k in self.image_keywords)

    def match_image_to_question(
        self,
        question_text: str,
        question_page: int,
        images_by_page: Dict[int, List[ExtractedImage]]
    ) -> Optional[ExtractedImage]:

        if not self.needs_image(question_text):
            return None

        candidates: List[ExtractedImage] = []

        for offset in (0, -1, 1):
            page = question_page + offset
            if page in images_by_page:
                candidates.extend(images_by_page[page])

        if not candidates:
            return None

        candidates.sort(key=lambda img: img.area, reverse=True)
        return candidates[0]
