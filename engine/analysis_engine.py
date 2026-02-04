"""
Analysis Engine Module
Provides deep post-test analysis and performance insights
Goes beyond simple scoring to identify patterns and weaknesses
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime, timedelta
import json
from pathlib import Path

from core.pdf_parser import ParsedQuestion
from engine.exam_engine import ExamSession, ExamQuestion, QuestionStatus


@dataclass
class QuestionResult:
    """Result for a single question"""
    question_id: str
    question_text: str
    selected_answer: Optional[str]
    correct_answer: Optional[str]
    is_correct: bool
    is_attempted: bool
    subject: Optional[str]
    explanation: Optional[str]
    time_spent: int = 0
    
    @property
    def status(self) -> str:
        if not self.is_attempted:
            return "unattempted"
        return "correct" if self.is_correct else "incorrect"


@dataclass
class SessionAnalysis:
    """Complete analysis of an exam session"""
    session_id: str
    mode: str
    
    # Basic metrics
    total_questions: int
    attempted: int
    correct: int
    incorrect: int
    unattempted: int
    
    # Calculated metrics
    score: float
    accuracy: float  # correct / attempted
    attempt_rate: float  # attempted / total
    
    # Time metrics
    total_time: timedelta
    average_time_per_question: float
    
    # Detailed results
    question_results: List[QuestionResult]
    
    # Subject-wise breakdown
    subject_breakdown: Dict[str, Dict]
    
    # Patterns
    mistakes_by_type: Dict[str, int]
    
    # Timestamp
    analyzed_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "mode": self.mode,
            "total_questions": self.total_questions,
            "attempted": self.attempted,
            "correct": self.correct,
            "incorrect": self.incorrect,
            "unattempted": self.unattempted,
            "score": self.score,
            "accuracy": self.accuracy,
            "attempt_rate": self.attempt_rate,
            "total_time_seconds": self.total_time.total_seconds(),
            "average_time_per_question": self.average_time_per_question,
            "subject_breakdown": self.subject_breakdown,
            "analyzed_at": self.analyzed_at.isoformat(),
        }


class AnalysisEngine:
    """
    Analyzes exam sessions to provide actionable insights
    Focuses on identifying weaknesses and tracking improvement
    """
    
    def __init__(self, question_bank: List[ParsedQuestion]):
        # Create lookup for correct answers
        self.answer_lookup = {q.id: q for q in question_bank}
    
    def analyze_session(self, session: ExamSession) -> SessionAnalysis:
        """Perform complete analysis of an exam session"""
        
        if not session.is_submitted:
            raise ValueError("Cannot analyze unsubmitted session")
        
        # Analyze each question
        question_results = self._analyze_questions(session.questions)
        
        # Calculate basic metrics
        total = len(question_results)
        attempted = sum(1 for r in question_results if r.is_attempted)
        correct = sum(1 for r in question_results if r.is_correct)
        incorrect = attempted - correct
        unattempted = total - attempted
        
        # Calculate percentages
        score = correct  # Each correct = 1 mark (FMGE has no negative)
        accuracy = (correct / attempted * 100) if attempted > 0 else 0
        attempt_rate = (attempted / total * 100) if total > 0 else 0
        
        # Time analysis
        total_time = session.elapsed_time
        avg_time = total_time.total_seconds() / total if total > 0 else 0
        
        # Subject breakdown
        subject_breakdown = self._analyze_by_subject(question_results)
        
        # Pattern analysis
        mistake_patterns = self._analyze_mistakes(question_results)
        
        return SessionAnalysis(
            session_id=session.session_id,
            mode=session.mode.value,
            total_questions=total,
            attempted=attempted,
            correct=correct,
            incorrect=incorrect,
            unattempted=unattempted,
            score=score,
            accuracy=accuracy,
            attempt_rate=attempt_rate,
            total_time=total_time,
            average_time_per_question=avg_time,
            question_results=question_results,
            subject_breakdown=subject_breakdown,
            mistakes_by_type=mistake_patterns,
        )
    
    def _analyze_questions(
        self, 
        exam_questions: List[ExamQuestion]
    ) -> List[QuestionResult]:
        """Analyze individual questions"""
        results = []
        
        for eq in exam_questions:
            # Get original question from bank
            original = self.answer_lookup.get(eq.question_id)
            
            correct_answer = original.correct_answer if original else None
            is_attempted = eq.selected_answer is not None
            is_correct = is_attempted and eq.selected_answer == correct_answer
            
            result = QuestionResult(
                question_id=eq.question_id,
                question_text=eq.question_text,
                selected_answer=eq.selected_answer,
                correct_answer=correct_answer,
                is_correct=is_correct,
                is_attempted=is_attempted,
                subject=original.subject if original else None,
                explanation=original.explanation if original else None,
                time_spent=eq.time_spent,
            )
            results.append(result)
        
        return results
    
    def _analyze_by_subject(
        self, 
        results: List[QuestionResult]
    ) -> Dict[str, Dict]:
        """Break down performance by subject"""
        subject_data = defaultdict(lambda: {
            "total": 0,
            "attempted": 0,
            "correct": 0,
            "incorrect": 0,
            "accuracy": 0.0,
        })
        
        for r in results:
            subject = r.subject or "Untagged"
            subject_data[subject]["total"] += 1
            
            if r.is_attempted:
                subject_data[subject]["attempted"] += 1
                if r.is_correct:
                    subject_data[subject]["correct"] += 1
                else:
                    subject_data[subject]["incorrect"] += 1
        
        # Calculate accuracies
        for subject, data in subject_data.items():
            if data["attempted"] > 0:
                data["accuracy"] = round(
                    data["correct"] / data["attempted"] * 100, 1
                )
        
        # Sort by weakness (lowest accuracy first)
        sorted_subjects = dict(
            sorted(subject_data.items(), key=lambda x: x[1]["accuracy"])
        )
        
        return sorted_subjects
    
    def _analyze_mistakes(
        self, 
        results: List[QuestionResult]
    ) -> Dict[str, int]:
        """Analyze patterns in mistakes"""
        patterns = defaultdict(int)
        
        incorrect = [r for r in results if r.is_attempted and not r.is_correct]
        
        for r in incorrect:
            # Categorize mistake type
            if r.subject:
                patterns[f"subject:{r.subject}"] += 1
            
            # Option tendency
            if r.selected_answer:
                patterns[f"selected_option:{r.selected_answer}"] += 1
        
        return dict(patterns)
    
    def get_weak_subjects(
        self, 
        analysis: SessionAnalysis,
        threshold: float = 50.0
    ) -> List[Tuple[str, float]]:
        """Get subjects with accuracy below threshold"""
        weak = []
        
        for subject, data in analysis.subject_breakdown.items():
            if data["attempted"] >= 3 and data["accuracy"] < threshold:
                weak.append((subject, data["accuracy"]))
        
        return sorted(weak, key=lambda x: x[1])
    
    def get_strong_subjects(
        self, 
        analysis: SessionAnalysis,
        threshold: float = 70.0
    ) -> List[Tuple[str, float]]:
        """Get subjects with accuracy above threshold"""
        strong = []
        
        for subject, data in analysis.subject_breakdown.items():
            if data["attempted"] >= 3 and data["accuracy"] >= threshold:
                strong.append((subject, data["accuracy"]))
        
        return sorted(strong, key=lambda x: -x[1])
    
    def get_incorrect_questions(
        self, 
        analysis: SessionAnalysis
    ) -> List[QuestionResult]:
        """Get all incorrectly answered questions"""
        return [r for r in analysis.question_results 
                if r.is_attempted and not r.is_correct]
    
    def get_unattempted_questions(
        self, 
        analysis: SessionAnalysis
    ) -> List[QuestionResult]:
        """Get all unattempted questions"""
        return [r for r in analysis.question_results if not r.is_attempted]
    
    def compare_sessions(
        self, 
        analyses: List[SessionAnalysis]
    ) -> Dict:
        """Compare multiple sessions for trend analysis"""
        if len(analyses) < 2:
            return {"message": "Need at least 2 sessions for comparison"}
        
        # Sort by date
        sorted_analyses = sorted(analyses, key=lambda x: x.analyzed_at)
        
        trends = {
            "sessions": len(analyses),
            "score_trend": [],
            "accuracy_trend": [],
            "attempt_rate_trend": [],
            "subject_trends": defaultdict(list),
        }
        
        for a in sorted_analyses:
            trends["score_trend"].append({
                "session": a.session_id,
                "score": a.score,
                "date": a.analyzed_at.isoformat(),
            })
            trends["accuracy_trend"].append({
                "session": a.session_id,
                "accuracy": a.accuracy,
            })
            trends["attempt_rate_trend"].append({
                "session": a.session_id,
                "attempt_rate": a.attempt_rate,
            })
            
            for subject, data in a.subject_breakdown.items():
                trends["subject_trends"][subject].append(data["accuracy"])
        
        # Calculate improvement
        first = sorted_analyses[0]
        last = sorted_analyses[-1]
        
        trends["improvement"] = {
            "score": last.score - first.score,
            "accuracy": last.accuracy - first.accuracy,
            "attempt_rate": last.attempt_rate - first.attempt_rate,
        }
        
        return trends


class ProgressTracker:
    """
    Tracks long-term progress across multiple sessions
    Identifies improvement areas and persistent weaknesses
    """
    
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.history: List[SessionAnalysis] = []
        self._load_history()
    
    def _load_history(self):
        """Load historical analysis data"""
        if self.storage_path.exists():
            with open(self.storage_path) as f:
                data = json.load(f)
                # Reconstruct analyses (simplified)
                self.history = data.get("analyses", [])
    
    def _save_history(self):
        """Save analysis history"""
        with open(self.storage_path, 'w') as f:
            json.dump({"analyses": [a.to_dict() for a in self.history]}, f)
    
    def add_analysis(self, analysis: SessionAnalysis):
        """Add a new analysis to history"""
        self.history.append(analysis)
        self._save_history()
    
    def get_overall_stats(self) -> Dict:
        """Get aggregate statistics across all sessions"""
        if not self.history:
            return {"message": "No history available"}
        
        total_questions = sum(a.total_questions for a in self.history)
        total_correct = sum(a.correct for a in self.history)
        total_attempted = sum(a.attempted for a in self.history)
        
        return {
            "total_sessions": len(self.history),
            "total_questions_practiced": total_questions,
            "overall_accuracy": round(total_correct / total_attempted * 100, 1) if total_attempted > 0 else 0,
            "average_score_per_session": round(sum(a.score for a in self.history) / len(self.history), 1),
        }
    
    def identify_persistent_weaknesses(
        self, 
        min_occurrences: int = 3,
        max_accuracy: float = 50.0
    ) -> List[str]:
        """Identify subjects that are consistently weak"""
        subject_performance = defaultdict(list)
        
        for analysis in self.history:
            for subject, data in analysis.subject_breakdown.items():
                if data["attempted"] > 0:
                    subject_performance[subject].append(data["accuracy"])
        
        persistent_weak = []
        for subject, accuracies in subject_performance.items():
            if len(accuracies) >= min_occurrences:
                avg_accuracy = sum(accuracies) / len(accuracies)
                if avg_accuracy < max_accuracy:
                    persistent_weak.append(subject)
        
        return persistent_weak