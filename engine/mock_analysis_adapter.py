from typing import List, Dict
from datetime import timedelta
from engine.analysis_engine import (
    QuestionResult,
    SessionAnalysis
)
from core.pdf_parser import ParsedQuestion


def analyze_mock_attempt(
    *,
    user_id: str,
    mock_id: str,
    questions: List[ParsedQuestion],
    answers: Dict[int, str],
    start_time: float,
    end_time: float
) -> SessionAnalysis:
    """
    Converts a mock exam attempt into a SessionAnalysis object
    WITHOUT using ExamSession / ExamQuestion.
    """

    question_results: List[QuestionResult] = []

    for idx, q in enumerate(questions):
        selected = answers.get(idx)
        is_attempted = selected is not None
        is_correct = is_attempted and selected == q.correct_answer

        question_results.append(
            QuestionResult(
                question_id=q.id,
                question_text=q.question_text,
                selected_answer=selected,
                correct_answer=q.correct_answer,
                is_correct=is_correct,
                is_attempted=is_attempted,
                subject=q.subject,
                explanation=q.explanation,
                time_spent=0  # optional future enhancement
            )
        )

    total = len(question_results)
    attempted = sum(r.is_attempted for r in question_results)
    correct = sum(r.is_correct for r in question_results)
    incorrect = attempted - correct
    unattempted = total - attempted

    accuracy = (correct / attempted * 100) if attempted else 0
    attempt_rate = (attempted / total * 100) if total else 0

    total_time = timedelta(seconds=(end_time - start_time))
    avg_time = total_time.total_seconds() / total if total else 0

    # Subject-wise breakdown
    subject_breakdown = {}
    for r in question_results:
        subject = r.subject or "Untagged"
        subject_breakdown.setdefault(subject, {
            "total": 0,
            "attempted": 0,
            "correct": 0,
            "incorrect": 0,
            "accuracy": 0.0
        })

        subject_breakdown[subject]["total"] += 1
        if r.is_attempted:
            subject_breakdown[subject]["attempted"] += 1
            if r.is_correct:
                subject_breakdown[subject]["correct"] += 1
            else:
                subject_breakdown[subject]["incorrect"] += 1

    for s in subject_breakdown.values():
        if s["attempted"]:
            s["accuracy"] = round(s["correct"] / s["attempted"] * 100, 1)

    return SessionAnalysis(
        session_id=f"{user_id}_{mock_id}",
        mode="mock",
        total_questions=total,
        attempted=attempted,
        correct=correct,
        incorrect=incorrect,
        unattempted=unattempted,
        score=correct,
        accuracy=round(accuracy, 1),
        attempt_rate=round(attempt_rate, 1),
        total_time=total_time,
        average_time_per_question=avg_time,
        question_results=question_results,
        subject_breakdown=subject_breakdown,
        mistakes_by_type={}
    )
