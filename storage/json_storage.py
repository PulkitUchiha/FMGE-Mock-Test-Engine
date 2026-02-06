"""JSON Storage Module with Image Support"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import shutil
import logging
import base64

from core.pdf_parser import ParsedQuestion
from config.settings import DATA_DIR, QUESTIONS_FILE

logger = logging.getLogger(__name__)


class QuestionStorage:
    
    def __init__(self, filepath: Path = QUESTIONS_FILE):
        self.filepath = filepath
        self.backup_dir = DATA_DIR / "backups"
        self.backup_dir.mkdir(exist_ok=True)
    
    def save_questions(self, questions: List[ParsedQuestion], create_backup: bool = True) -> bool:
        try:
            if create_backup and self.filepath.exists():
                self._create_backup()
            
            # Convert questions to dict, handling images
            questions_data = []
            for q in questions:
                q_dict = q.to_dict()
                
                # Convert image paths to relative paths
                if q_dict.get('images'):
                    q_dict['images'] = [
                        str(Path(p).relative_to(DATA_DIR)) if Path(p).exists() else p
                        for p in q_dict['images']
                    ]
                
                questions_data.append(q_dict)
            
            data = {
                "version": "1.1",
                "created_at": datetime.now().isoformat(),
                "total_count": len(questions),
                "with_images": sum(1 for q in questions if q.images),
                "questions": questions_data,
            }
            
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved {len(questions)} questions to {self.filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save questions: {e}")
            return False
    
    def load_questions(self) -> List[ParsedQuestion]:
        if not self.filepath.exists():
            logger.warning(f"Question file not found: {self.filepath}")
            return []
        
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            questions = []
            for q_data in data.get("questions", []):
                # Convert relative image paths back to absolute
                images = q_data.get("images", [])
                absolute_images = []
                for img_path in images:
                    if img_path.startswith("data:"):
                        # Base64 data URI
                        absolute_images.append(img_path)
                    else:
                        # File path
                        abs_path = DATA_DIR / img_path
                        if abs_path.exists():
                            absolute_images.append(str(abs_path))
                        else:
                            absolute_images.append(img_path)
                
                question = ParsedQuestion(
                    id=q_data["id"],
                    question_text=q_data["question_text"],
                    option_a=q_data["option_a"],
                    option_b=q_data["option_b"],
                    option_c=q_data["option_c"],
                    option_d=q_data["option_d"],
                    correct_answer=q_data.get("correct_answer"),
                    explanation=q_data.get("explanation"),
                    source_file=q_data.get("source_file", "unknown"),
                    page_number=q_data.get("page_number", 0),
                    images=absolute_images,
                    subject=q_data.get("subject"),
                    year=q_data.get("year"),
                    is_valid=q_data.get("is_valid", True),
                    has_image_reference=q_data.get("has_image_reference", False),
                    needs_review=q_data.get("needs_review", False),
                )
                questions.append(question)
            
            logger.info(f"Loaded {len(questions)} questions")
            return questions
            
        except Exception as e:
            logger.error(f"Failed to load questions: {e}")
            return []
    
    def _create_backup(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"questions_backup_{timestamp}.json"
        shutil.copy(self.filepath, backup_path)
        logger.info(f"Created backup: {backup_path}")
    
    def get_stats(self) -> Dict:
        questions = self.load_questions()
        
        if not questions:
            return {"total": 0}
        
        subject_counts = {}
        for q in questions:
            subject = q.subject or "Untagged"
            subject_counts[subject] = subject_counts.get(subject, 0) + 1
        
        with_answers = sum(1 for q in questions if q.correct_answer)
        with_explanations = sum(1 for q in questions if q.explanation)
        with_images = sum(1 for q in questions if q.images)
        needs_review = sum(1 for q in questions if q.needs_review)
        
        return {
            "total": len(questions),
            "with_answers": with_answers,
            "with_explanations": with_explanations,
            "with_images": with_images,
            "needs_review": needs_review,
            "by_subject": subject_counts,
            "answer_coverage": f"{with_answers/len(questions)*100:.1f}%",
        }
    
    def add_questions(self, new_questions: List[ParsedQuestion], deduplicate: bool = True) -> int:
        existing = self.load_questions()
        existing_ids = {q.id for q in existing}
        
        added = 0
        for q in new_questions:
            if deduplicate and q.id in existing_ids:
                continue
            existing.append(q)
            added += 1
        
        self.save_questions(existing)
        return added
    
    def get_questions_needing_images(self) -> List[ParsedQuestion]:
        """Get questions that reference images but don't have them"""
        questions = self.load_questions()
        return [q for q in questions if q.has_image_reference and not q.images]
    
    def export_with_images_html(self, output_path: Path, limit: int = 100):
        """Export questions with images to an HTML file for viewing"""
        
        questions = self.load_questions()
        
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>FMGE Questions with Images</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; }
        .question { border: 1px solid #ddd; padding: 20px; margin: 20px 0; border-radius: 8px; }
        .question-text { font-size: 16px; font-weight: bold; margin-bottom: 15px; }
        .image-container { text-align: center; margin: 15px 0; }
        .image-container img { max-width: 100%; max-height: 400px; border: 1px solid #ccc; }
        .options { margin: 15px 0; }
        .option { padding: 8px; margin: 5px 0; background: #f5f5f5; border-radius: 4px; }
        .option.correct { background: #d4edda; border-left: 4px solid #28a745; }
        .answer { color: #28a745; font-weight: bold; margin-top: 10px; }
        .explanation { background: #e7f3ff; padding: 10px; border-radius: 4px; margin-top: 10px; }
        .meta { color: #666; font-size: 12px; margin-top: 10px; }
        .no-image { color: #dc3545; font-style: italic; }
    </style>
</head>
<body>
    <h1>FMGE Questions with Images</h1>
"""
        
        count = 0
        for q in questions:
            if count >= limit:
                break
            
            # Only show questions with images or that need images
            if not q.has_image_reference:
                continue
            
            count += 1
            
            html += f'<div class="question">\n'
            html += f'<div class="question-text">Q{count}. {q.question_text}</div>\n'
            
            # Display image
            if q.images:
                for img_path in q.images:
                    if img_path.startswith("data:"):
                        html += f'<div class="image-container"><img src="{img_path}" alt="Question Image"></div>\n'
                    elif Path(img_path).exists():
                        # Read and embed as base64
                        with open(img_path, 'rb') as f:
                            img_data = base64.b64encode(f.read()).decode()
                        ext = Path(img_path).suffix[1:]
                        html += f'<div class="image-container"><img src="data:image/{ext};base64,{img_data}" alt="Question Image"></div>\n'
            else:
                html += '<div class="no-image">⚠️ Image referenced but not found</div>\n'
            
            # Options
            html += '<div class="options">\n'
            for opt, text in [('A', q.option_a), ('B', q.option_b), ('C', q.option_c), ('D', q.option_d)]:
                is_correct = q.correct_answer == opt
                css_class = "option correct" if is_correct else "option"
                prefix = "✓ " if is_correct else ""
                html += f'<div class="{css_class}">{prefix}{opt}. {text}</div>\n'
            html += '</div>\n'
            
            if q.correct_answer:
                html += f'<div class="answer">Answer: {q.correct_answer}</div>\n'
            
            if q.explanation:
                html += f'<div class="explanation"><strong>Explanation:</strong> {q.explanation[:500]}...</div>\n'
            
            html += f'<div class="meta">Source: {q.source_file} | Page: {q.page_number} | Subject: {q.subject or "Untagged"}</div>\n'
            html += '</div>\n'
        
        html += "</body></html>"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        logger.info(f"Exported {count} questions to {output_path}")
        return count
    
# ===========================
# Mock Exam Attempt Storage
# ===========================

class MockExamStorage:
    """
    Handles persistence of mock exam attempts.
    Separate from QuestionStorage by design.
    """

    BASE_DIR = Path("data/sessions/mock_exams")

    def __init__(self):
        self.BASE_DIR.mkdir(parents=True, exist_ok=True)

    def mock_attempt_exists(self, user_id: str, mock_id: str) -> bool:
        path = self.BASE_DIR / user_id / f"{mock_id}.json"
        return path.exists()

    def save_mock_attempt(self, data: Dict) -> None:
        """
        Persist a completed mock exam attempt.
        """
        user_dir = self.BASE_DIR / data["user_id"]
        user_dir.mkdir(parents=True, exist_ok=True)

        path = user_dir / f"{data['mock_id']}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(
            f"Saved mock exam attempt for user={data['user_id']} mock={data['mock_id']}"
        )

    def load_mock_attempt(self, user_id: str, mock_id: str) -> Optional[Dict]:
        path = self.BASE_DIR / user_id / f"{mock_id}.json"
        if not path.exists():
            return None

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_user_attempts(self, user_id: str) -> List[str]:
        """
        List all mock IDs attempted by a user.
        """
        user_dir = self.BASE_DIR / user_id
        if not user_dir.exists():
            return []

        return [p.stem for p in user_dir.glob("*.json")]
