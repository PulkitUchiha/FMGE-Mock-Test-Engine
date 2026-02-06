# engine/mock_exam_engine.py

import time
import random
import streamlit as st

TOTAL_QUESTIONS = 150
TOTAL_TIME_SEC = 180 * 60  # 180 minutes


def init_mock_session(all_questions):
    """
    Initialize mock exam session exactly once.
    Safe against reruns and partial session resets.
    """

    # If already initialized properly, do nothing
    if (
        "mock_questions" in st.session_state
        and "mock_answers" in st.session_state
        and "mock_start_time" in st.session_state
    ):
        return

    if len(all_questions) < TOTAL_QUESTIONS:
        raise ValueError(
            f"Not enough questions for mock exam. "
            f"Required={TOTAL_QUESTIONS}, Available={len(all_questions)}"
        )

    st.session_state.mock_questions = random.sample(
        all_questions, TOTAL_QUESTIONS
    )

    # index → selected option (A/B/C/D or None)
    st.session_state.mock_answers = {
        i: None for i in range(TOTAL_QUESTIONS)
    }

    st.session_state.mock_current_q = 0

    # Timer state
    st.session_state.mock_exam_started = False
    st.session_state.mock_start_time = None

    # Submission lock
    st.session_state.mock_submitted = False


def start_exam_if_needed():
    """
    Starts timer ONLY on first answer selection.
    """
    if not st.session_state.mock_exam_started:
        st.session_state.mock_exam_started = True
        st.session_state.mock_start_time = time.time()


def remaining_time():
    """
    Returns remaining time in seconds.
    Timer is frozen until exam starts.
    """
    if not st.session_state.mock_exam_started:
        return TOTAL_TIME_SEC

    elapsed = int(time.time() - st.session_state.mock_start_time)
    return max(0, TOTAL_TIME_SEC - elapsed)
