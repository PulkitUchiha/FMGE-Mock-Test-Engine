"""
Manual Review Module
Handles questions that need human review
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class ReviewItem:
    """Item needing manual review"""
    question_id: str
    question_text: str
    options: Dict[str, str]
    current_answer: Optional[str]
    source_file: str
    page_number: int
    reason: str  # Why it needs review
    raw_block: str
    created_at: str = ""
    reviewed: bool = False
    corrected_answer: Optional[str] = None
    reviewer_notes: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class ManualReviewQueue:
    """
    Manages questions that need manual review
    """
    
    def __init__(self, storage_path: Path = None):
        self.storage_path = storage_path or Path("data/review_queue.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.items: List[ReviewItem] = []
        self._load()
    
    def _load(self):
        """Load existing review items"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path) as f:
                    data = json.load(f)
                self.items = [ReviewItem(**item) for item in data.get("items", [])]
            except Exception as e:
                logger.error(f"Error loading review queue: {e}")
                self.items = []
    
    def _save(self):
        """Save review items"""
        data = {
            "items": [asdict(item) for item in self.items],
            "updated_at": datetime.now().isoformat()
        }
        
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def add(self, item: ReviewItem):
        """Add item to review queue"""
        # Check for duplicates
        if not any(i.question_id == item.question_id for i in self.items):
            self.items.append(item)
            self._save()
    
    def add_from_parsed_question(self, pq, reason: str, raw_block: str = ""):
        """Add a parsed question to review queue"""
        
        item = ReviewItem(
            question_id=pq.id,
            question_text=pq.question_text,
            options={
                'A': pq.option_a,
                'B': pq.option_b,
                'C': pq.option_c,
                'D': pq.option_d
            },
            current_answer=pq.correct_answer,
            source_file=pq.source_file,
            page_number=pq.page_number,
            reason=reason,
            raw_block=raw_block
        )
        
        self.add(item)
    
    def get_pending(self) -> List[ReviewItem]:
        """Get items pending review"""
        return [item for item in self.items if not item.reviewed]
    
    def get_reviewed(self) -> List[ReviewItem]:
        """Get items that have been reviewed"""
        return [item for item in self.items if item.reviewed]
    
    def mark_reviewed(
        self, 
        question_id: str, 
        corrected_answer: Optional[str] = None,
        notes: str = ""
    ):
        """Mark an item as reviewed"""
        for item in self.items:
            if item.question_id == question_id:
                item.reviewed = True
                item.corrected_answer = corrected_answer
                item.reviewer_notes = notes
                break
        
        self._save()
    
    def get_stats(self) -> Dict:
        """Get review queue statistics"""
        pending = len(self.get_pending())
        reviewed = len(self.get_reviewed())
        
        # Group by reason
        by_reason = {}
        for item in self.items:
            reason = item.reason
            by_reason[reason] = by_reason.get(reason, 0) + 1
        
        return {
            "total": len(self.items),
            "pending": pending,
            "reviewed": reviewed,
            "by_reason": by_reason
        }
    
    def export_for_review(self, output_path: Path):
        """Export pending items to a readable format for review"""
        
        pending = self.get_pending()
        
        output = ["# Questions Needing Review\n"]
        output.append(f"Generated: {datetime.now().isoformat()}\n")
        output.append(f"Total pending: {len(pending)}\n")
        output.append("="*60 + "\n\n")
        
        for i, item in enumerate(pending, 1):
            output.append(f"## [{i}] {item.question_id}\n")
            output.append(f"**Source:** {item.source_file}, Page {item.page_number}\n")
            output.append(f"**Reason:** {item.reason}\n\n")
            output.append(f"**Question:** {item.question_text}\n\n")
            output.append("**Options:**\n")
            for letter, text in item.options.items():
                output.append(f"- {letter}: {text}\n")
            output.append(f"\n**Current Answer:** {item.current_answer or 'None'}\n")
            output.append(f"\n**Raw Text:**\n```\n{item.raw_block[:500]}\n```\n")
            output.append("\n---\n\n")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(output)
        
        logger.info(f"Exported {len(pending)} items to {output_path}")