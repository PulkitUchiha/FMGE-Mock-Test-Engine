"""
Exam Engine Module
Handles exam session creation, question delivery, and answer collection
Provides exam-like experience without spoilers
"""

import random
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path

from core.pdf_parser import ParsedQuestion
from config.settings import EXAM_CONFIG, SESSIONS_DIR


class ExamMode(Enum):
    DAILY_PRACTICE = "daily_practice"
    FULL_MOCK = "full_mock"
    CUSTOM = "custom"
    SUBJECT_WISE = "subject_wise"


class QuestionStatus(Enum):
    UNANSWERED = "unanswered"
    ANSWERED = "answered"
    MARKED_FOR_REVIEW = "marked_for_review"
    ANSWERED_AND_MARKED = "answered_and_marked"


@dataclass
class ExamQuestion:
    """Question as presented in exam (no correct answer visible)"""
    index: int  # 1-based index in exam
    question_id: str
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    images: List[str] = field(default_factory=list)
    
    # Runtime state
    selected_answer: Optional[str] = None
    status: QuestionStatus = QuestionStatus.UNANSWERED
    time_spent: int = 0  # seconds
    
    def to_dict(self) -> Dict:
        return {
            "index": self.index,
            "question_id": self.question_id,
            "question_text": self.question_text,
            "option_a": self.option_a,
            "option_b": self.option_b,
            "option_c": self.option_c,
            "option_d": self.option_d,
            "images": self.images,
            "selected_answer": self.selected_answer,
            "status": self.status.value,
            "time_spent": self.time_spent,
        }


@dataclass
class ExamSession:
    """Represents a complete exam session"""
    session_id: str
    mode: ExamMode
    questions: List[ExamQuestion]
    
    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    time_limit_minutes: int = 60
    
    # State
    current_index: int = 0
    is_submitted: bool = False
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    subject_filter: Optional[str] = None
    
    @property
    def total_questions(self) -> int:
        return len(self.questions)
    
    @property
    def answered_count(self) -> int:
        return sum(1 for q in self.questions if q.selected_answer is not None)
    
    @property
    def marked_count(self) -> int:
        return sum(1 for q in self.questions 
                   if q.status in [QuestionStatus.MARKED_FOR_REVIEW, 
                                   QuestionStatus.ANSWERED_AND_MARKED])
    
    @property
    def elapsed_time(self) -> timedelta:
        if self.start_time:
            end = self.end_time or datetime.now()
            return end - self.start_time
        return timedelta(0)
    
    @property
    def remaining_time(self) -> timedelta:
        if not self.start_time:
            return timedelta(minutes=self.time_limit_minutes)
        
        elapsed = self.elapsed_time
        limit = timedelta(minutes=self.time_limit_minutes)
        remaining = limit - elapsed
        
        return max(remaining, timedelta(0))
    
    @property
    def is_time_up(self) -> bool:
        return self.remaining_time.total_seconds() <= 0
    
    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "mode": self.mode.value,
            "questions": [q.to_dict() for q in self.questions],
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "time_limit_minutes": self.time_limit_minutes,
            "current_index": self.current_index,
            "is_submitted": self.is_submitted,
            "created_at": self.created_at.isoformat(),
            "subject_filter": self.subject_filter,
        }


class ExamEngine:
    """
    Main exam engine that manages exam sessions
    Provides exam-like experience without exposing answers
    """
    
    def __init__(
        self, 
        question_bank: List[ParsedQuestion],
        config: EXAM_CONFIG = None,
        sessions_dir: Path = SESSIONS_DIR
    ):
        self.question_bank = question_bank
        self.config = config or EXAM_CONFIG
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        
        # Index questions by subject for filtered exams
        self._subject_index = self._build_subject_index()
        
        # Active session
        self.current_session: Optional[ExamSession] = None
    
    def _build_subject_index(self) -> Dict[str, List[ParsedQuestion]]:
        """Build index of questions by subject"""
        index = {}
        for q in self.question_bank:
            subject = q.subject or "General"
            if subject not in index:
                index[subject] = []
            index[subject].append(q)
        return index
    
    def create_session(
        self,
        mode: ExamMode = ExamMode.DAILY_PRACTICE,
        subject: Optional[str] = None,
        question_count: Optional[int] = None,
    ) -> ExamSession:
        """Create a new exam session"""
        
        # Determine question count
        if question_count is None:
            if mode == ExamMode.DAILY_PRACTICE:
                question_count = self.config.daily_practice_count
            elif mode == ExamMode.FULL_MOCK:
                question_count = self.config.full_mock_count
            else:
                question_count = 50
        
        # Determine time limit
        if mode == ExamMode.DAILY_PRACTICE:
            time_limit = self.config.daily_time_limit
        elif mode == ExamMode.FULL_MOCK:
            time_limit = self.config.mock_time_limit
        else:
            time_limit = question_count * 1.2  # 1.2 min per question
        
        # Select questions
        available_questions = self._get_available_questions(subject)
        
        if len(available_questions) < question_count:
            question_count = len(available_questions)
        
        selected = random.sample(available_questions, question_count)
        
        # Create exam questions (without answers)
        exam_questions = [
            ExamQuestion(
                index=i + 1,
                question_id=q.id,
                question_text=q.question_text,
                option_a=q.option_a,
                option_b=q.option_b,
                option_c=q.option_c,
                option_d=q.option_d,
                images=q.images,
            )
            for i, q in enumerate(selected)
        ]
        
        # Create session
        session = ExamSession(
            session_id=self._generate_session_id(),
            mode=mode,
            questions=exam_questions,
            time_limit_minutes=int(time_limit),
            subject_filter=subject,
        )
        
        self.current_session = session
        return session
    
    def _get_available_questions(
        self, 
        subject: Optional[str] = None
    ) -> List[ParsedQuestion]:
        """Get questions available for selection"""
        if subject and subject in self._subject_index:
            return self._subject_index[subject]
        return self.question_bank
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = random.randint(1000, 9999)
        return f"session_{timestamp}_{random_suffix}"
    
    def start_exam(self) -> bool:
        """Start the current exam session"""
        if not self.current_session:
            return False
        
        self.current_session.start_time = datetime.now()
        return True
    
    def get_question(self, index: int) -> Optional[ExamQuestion]:
        """Get a question by index (1-based)"""
        if not self.current_session:
            return None
        
        if 1 <= index <= self.current_session.total_questions:
            return self.current_session.questions[index - 1]
        return None
    
    def answer_question(
        self, 
        index: int, 
        answer: Optional[str],
        mark_for_review: bool = False
    ) -> bool:
        """Record an answer for a question"""
        question = self.get_question(index)
        if not question:
            return False
        
        # Validate answer
        if answer is not None and answer not in 'ABCD':
            return False
        
        question.selected_answer = answer
        
        # Update status
        if answer and mark_for_review:
            question.status = QuestionStatus.ANSWERED_AND_MARKED
        elif answer:
            question.status = QuestionStatus.ANSWERED
        elif mark_for_review:
            question.status = QuestionStatus.MARKED_FOR_REVIEW
        else:
            question.status = QuestionStatus.UNANSWERED
        
        return True
    
    def navigate_to(self, index: int) -> bool:
        """Navigate to a specific question"""
        if not self.current_session:
            return False
        
        if 1 <= index <= self.current_session.total_questions:
            self.current_session.current_index = index - 1
            return True
        return False
    
    def next_question(self) -> Optional[ExamQuestion]:
        """Move to next question"""
        if not self.current_session:
            return None
        
        current = self.current_session.current_index
        if current < self.current_session.total_questions - 1:
            self.current_session.current_index = current + 1
            return self.current_session.questions[self.current_session.current_index]
        return None
    
    def previous_question(self) -> Optional[ExamQuestion]:
        """Move to previous question"""
        if not self.current_session:
            return None
        
        current = self.current_session.current_index
        if current > 0:
            self.current_session.current_index = current - 1
            return self.current_session.questions[self.current_session.current_index]
        return None
    
    def get_navigation_status(self) -> List[Dict]:
        """Get status of all questions for navigation panel"""
        if not self.current_session:
            return []
        
        return [
            {
                "index": q.index,
                "status": q.status.value,
                "answered": q.selected_answer is not None,
            }
            for q in self.current_session.questions
        ]
    
    def submit_exam(self) -> ExamSession:
        """Submit the exam and finalize"""
        if not self.current_session:
            raise ValueError("No active session")
        
        self.current_session.end_time = datetime.now()
        self.current_session.is_submitted = True
        
        # Save session
        self._save_session(self.current_session)
        
        return self.current_session
    
    def _save_session(self, session: ExamSession):
        """Save session to disk"""
        filepath = self.sessions_dir / f"{session.session_id}.json"
        
        with open(filepath, 'w') as f:
            json.dump(session.to_dict(), f, indent=2)
    
    def load_session(self, session_id: str) -> Optional[ExamSession]:
        """Load a previous session"""
        filepath = self.sessions_dir / f"{session_id}.json"
        
        if not filepath.exists():
            return None
        
        with open(filepath) as f:
            data = json.load(f)
        
        # Reconstruct session
        questions = [
            ExamQuestion(
                index=q["index"],
                question_id=q["question_id"],
                question_text=q["question_text"],
                option_a=q["option_a"],
                option_b=q["option_b"],
                option_c=q["option_c"],
                option_d=q["option_d"],
                images=q.get("images", []),
                selected_answer=q.get("selected_answer"),
                status=QuestionStatus(q.get("status", "unanswered")),
                time_spent=q.get("time_spent", 0),
            )
            for q in data["questions"]
        ]
        
        session = ExamSession(
            session_id=data["session_id"],
            mode=ExamMode(data["mode"]),
            questions=questions,
            start_time=datetime.fromisoformat(data["start_time"]) if data.get("start_time") else None,
            end_time=datetime.fromisoformat(data["end_time"]) if data.get("end_time") else None,
            time_limit_minutes=data.get("time_limit_minutes", 60),
            current_index=data.get("current_index", 0),
            is_submitted=data.get("is_submitted", False),
            created_at=datetime.fromisoformat(data["created_at"]),
            subject_filter=data.get("subject_filter"),
        )
        
        return session
    
    def get_all_sessions(self) -> List[Dict]:
        """Get list of all saved sessions"""
        sessions = []
        
        for filepath in self.sessions_dir.glob("*.json"):
            try:
                with open(filepath) as f:
                    data = json.load(f)
                sessions.append({
                    "session_id": data["session_id"],
                    "mode": data["mode"],
                    "created_at": data["created_at"],
                    "is_submitted": data.get("is_submitted", False),
                    "total_questions": len(data["questions"]),
                })
            except Exception:
                continue
        
        return sorted(sessions, key=lambda x: x["created_at"], reverse=True)