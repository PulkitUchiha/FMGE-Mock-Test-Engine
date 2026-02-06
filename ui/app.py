"""
FMGE Practice Engine - Streamlit UI
Complete interface with image display
"""

import streamlit as st
from pathlib import Path
import sys
import base64
import random
from datetime import datetime
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.json_storage import QuestionStorage
from config.settings import DATA_DIR, EXAM_CONFIG

# ===== MOCK EXAM IMPORTS =====
from engine.mock_exam_engine import (
    init_mock_session,
    start_exam_if_needed,
    remaining_time
)
from storage.json_storage import MockExamStorage
from engine.mock_analysis_adapter import analyze_mock_attempt
from storage.mock_users import validate_user


def get_current_mock_id():
    """Returns the official mock ID for today."""
    return f"mock_fmge_{datetime.now().strftime('%Y_%m_%d')}"


# Page config
st.set_page_config(
    page_title="FMGE Practice Engine",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f77b4;
        text-align: center;
        padding: 1rem;
    }
    .question-box {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
        margin: 1rem 0;
    }
    .question-image {
        text-align: center;
        margin: 1rem 0;
        padding: 1rem;
        background: #fff;
        border: 1px solid #ddd;
        border-radius: 8px;
    }
    .question-image img {
        max-width: 100%;
        max-height: 400px;
        border-radius: 4px;
    }
    .option-correct {
        background: #d4edda !important;
        border-left: 4px solid #28a745 !important;
        padding: 10px;
        border-radius: 4px;
        margin: 5px 0;
    }
    .option-incorrect {
        background: #f8d7da !important;
        border-left: 4px solid #dc3545 !important;
        padding: 10px;
        border-radius: 4px;
        margin: 5px 0;
    }
    .option-normal {
        background: #f8f9fa;
        border-left: 4px solid #6c757d;
        padding: 10px;
        border-radius: 4px;
        margin: 5px 0;
    }
    .stat-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 1rem;
        color: white;
        text-align: center;
        margin: 0.5rem 0;
    }
    .stat-card h2 {
        margin: 0;
        font-size: 2rem;
    }
    .stat-card p {
        margin: 0.5rem 0 0 0;
        opacity: 0.9;
    }
    .explanation-box {
        background: #e7f3ff;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-top: 1rem;
        border-left: 4px solid #0066cc;
    }
    .image-missing {
        background: #fff3cd;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
        color: #856404;
    }
</style>
""", unsafe_allow_html=True)


def load_image_as_base64(image_path: str) -> str:
    """Robust image loader for Streamlit Cloud + Windows."""
    try:
        image_path = image_path.replace("\\", "/")
        path = Path(image_path)

        if not path.is_absolute():
            path = DATA_DIR / path

        if not path.exists():
            return None

        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")

        ext = path.suffix.lower().replace(".", "")
        if ext == "jpg":
            ext = "jpeg"

        return f"data:image/{ext};base64,{data}"

    except Exception as e:
        st.error(f"Error loading image: {e}")
        return None


def display_question_image(question):
    """Display image for a question if available"""
    if question.images:
        for img_path in question.images:
            if img_path.startswith('data:'):
                st.markdown(f'''
                    <div class="question-image">
                        <img src="{img_path}" alt="Question Image">
                    </div>
                ''', unsafe_allow_html=True)
            else:
                img_data = load_image_as_base64(img_path)
                if img_data:
                    st.markdown(f'''
                        <div class="question-image">
                            <img src="{img_data}" alt="Question Image">
                        </div>
                    ''', unsafe_allow_html=True)
                else:
                    st.warning(f"⚠️ Image file not found: {img_path}")

    elif question.has_image_reference:
        st.markdown('''
            <div class="image-missing">
                ⚠️ This question references an image that could not be extracted.
            </div>
        ''', unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables"""
    if 'questions' not in st.session_state:
        storage = QuestionStorage()
        st.session_state.questions = storage.load_questions()

    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'home'

    if 'exam_active' not in st.session_state:
        st.session_state.exam_active = False

    if 'exam_questions' not in st.session_state:
        st.session_state.exam_questions = []

    if 'exam_answers' not in st.session_state:
        st.session_state.exam_answers = {}

    if 'exam_submitted' not in st.session_state:
        st.session_state.exam_submitted = False

    if 'current_q_index' not in st.session_state:
        st.session_state.current_q_index = 0

    if 'exam_start_time' not in st.session_state:
        st.session_state.exam_start_time = None

    # ===== MOCK EXAM STATE =====
    if 'exam_mode' not in st.session_state:
        st.session_state.exam_mode = 'practice'

    if 'user_id' not in st.session_state:
        st.session_state.user_id = None


def render_sidebar():
    """Render navigation sidebar"""
    st.sidebar.markdown("## 🩺 FMGE Practice")
    st.sidebar.markdown("---")

    # 🔒 Lock sidebar during mock exam
    if st.session_state.get('exam_mode') == 'mock':
        st.sidebar.info("📝 Mock Exam in Progress")
        st.sidebar.markdown("Navigation locked")
        return

    if st.sidebar.button("🏠 Home", use_container_width=True):
        st.session_state.current_page = 'home'
        st.session_state.exam_active = False
        st.rerun()

    if st.sidebar.button("📝 Practice", use_container_width=True):
        st.session_state.current_page = 'practice'
        st.rerun()

    if st.sidebar.button("🎯 Real Mock Test", use_container_width=True):
        st.session_state.current_page = 'mock_login'
        st.rerun()

    if st.sidebar.button("📖 Browse Questions", use_container_width=True):
        st.session_state.current_page = 'browse'
        st.rerun()

    if st.sidebar.button("🖼️ Image Questions", use_container_width=True):
        st.session_state.current_page = 'images'
        st.rerun()

    if st.sidebar.button("📊 Statistics", use_container_width=True):
        st.session_state.current_page = 'stats'
        st.rerun()

    st.sidebar.markdown("---")

    total = len(st.session_state.questions)
    with_images = sum(1 for q in st.session_state.questions if q.images)

    st.sidebar.metric("Total Questions", total)
    st.sidebar.metric("With Images", with_images)


def render_home():
    """Render home page"""
    st.markdown(
        '<h1 class="main-header">🩺 FMGE Practice Engine</h1>',
        unsafe_allow_html=True,
    )

    st.markdown("""
    ### Welcome to your FMGE preparation platform!
    
    Practice with real FMGE questions including **image-based questions**.
    """)

    questions = st.session_state.questions

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f'''
            <div class="stat-card">
                <h2>{len(questions)}</h2>
                <p>Total Questions</p>
            </div>
        ''', unsafe_allow_html=True)

    with col2:
        with_ans = sum(1 for q in questions if q.correct_answer)
        st.markdown(f'''
            <div class="stat-card">
                <h2>{with_ans}</h2>
                <p>With Answers</p>
            </div>
        ''', unsafe_allow_html=True)

    with col3:
        with_img = sum(1 for q in questions if q.images)
        st.markdown(f'''
            <div class="stat-card">
                <h2>{with_img}</h2>
                <p>With Images</p>
            </div>
        ''', unsafe_allow_html=True)

    with col4:
        subjects = len(set(q.subject for q in questions if q.subject))
        st.markdown(f'''
            <div class="stat-card">
                <h2>{subjects}</h2>
                <p>Subjects</p>
            </div>
        ''', unsafe_allow_html=True)

    st.markdown("---")

    st.subheader("🚀 Quick Start")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📝 Start Practice (50 Qs)", use_container_width=True, type="primary"):
            start_practice_exam(50)

    with col2:
        if st.button("📋 Practice Exam (150 Qs)", use_container_width=True):
            start_practice_exam(150)

    with col3:
        if st.button("🖼️ Image Questions Only", use_container_width=True):
            start_practice_exam(50, images_only=True)

    st.markdown("---")

    # Real Mock Test section on home page
    st.subheader("🎯 Real Mock Test")
    st.markdown("""
    Take a **timed mock exam** that simulates the real FMGE experience:
    - 🔒 **150 questions** with countdown timer
    - 📊 **Detailed analysis** after submission
    - 🚫 **One attempt per day** — just like the real exam
    """)

    if st.button("🎯 Start Real Mock Test", use_container_width=True, type="primary"):
        st.session_state.current_page = 'mock_login'
        st.rerun()


def start_practice_exam(num_questions: int, images_only: bool = False):
    """Start a new practice exam session"""
    questions = st.session_state.questions

    available = [q for q in questions if q.is_valid and q.correct_answer]

    if images_only:
        available = [q for q in available if q.images]

    if len(available) < num_questions:
        num_questions = len(available)

    if num_questions == 0:
        st.error("No questions available!")
        return

    selected = random.sample(available, num_questions)

    st.session_state.exam_questions = selected
    st.session_state.exam_answers = {}
    st.session_state.exam_submitted = False
    st.session_state.exam_active = True
    st.session_state.current_q_index = 0
    st.session_state.exam_start_time = datetime.now()
    st.session_state.current_page = 'exam'
    st.rerun()


def render_exam():
    """Render active practice exam"""
    if not st.session_state.exam_active:
        st.warning("No active exam. Start a new practice session.")
        if st.button("Go to Practice"):
            st.session_state.current_page = 'practice'
            st.rerun()
        return

    if st.session_state.exam_submitted:
        render_exam_results()
        return

    questions = st.session_state.exam_questions
    current_idx = st.session_state.current_q_index

    # Header
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        elapsed = datetime.now() - st.session_state.exam_start_time
        mins = int(elapsed.total_seconds() // 60)
        secs = int(elapsed.total_seconds() % 60)
        st.markdown(f"### ⏱️ Time: {mins:02d}:{secs:02d}")

    with col2:
        st.markdown(f"### Question {current_idx + 1}/{len(questions)}")

    with col3:
        answered = len(st.session_state.exam_answers)
        st.markdown(f"### ✅ {answered}/{len(questions)}")

    st.markdown("---")

    # Current question
    question = questions[current_idx]

    st.markdown(f'''
        <div class="question-box">
            <strong>Q{current_idx + 1}.</strong> {question.question_text}
        </div>
    ''', unsafe_allow_html=True)

    display_question_image(question)

    # Options
    options = {
        'A': question.option_a,
        'B': question.option_b,
        'C': question.option_c,
        'D': question.option_d,
    }

    current_answer = st.session_state.exam_answers.get(question.id)

    # Save answer immediately via on_change callback
    def save_practice_answer():
        picked = st.session_state[f"q_{question.id}"]
        if picked:
            st.session_state.exam_answers[question.id] = picked

    st.radio(
        "Select your answer:",
        options=['A', 'B', 'C', 'D'],
        format_func=lambda x: f"{x}. {options[x]}",
        index=['A', 'B', 'C', 'D'].index(current_answer) if current_answer else None,
        key=f"q_{question.id}",
        on_change=save_practice_answer
    )

    st.markdown("---")

    # Navigation buttons
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        if st.button("⬅️ Previous", disabled=current_idx == 0):
            st.session_state.current_q_index = current_idx - 1
            st.rerun()

    with col2:
        if st.button("➡️ Next", disabled=current_idx >= len(questions) - 1):
            st.session_state.current_q_index = current_idx + 1
            st.rerun()

    with col3:
        if st.button("🔀 Random"):
            st.session_state.current_q_index = random.randint(0, len(questions) - 1)
            st.rerun()

    with col4:
        if st.button("❌ Clear"):
            if question.id in st.session_state.exam_answers:
                del st.session_state.exam_answers[question.id]
            st.rerun()

    with col5:
        if st.button("📤 Submit", type="primary"):
            st.session_state.exam_submitted = True
            st.rerun()

    # ── Question Navigator Grid ──
    st.markdown("---")
    st.markdown("### 📋 Question Navigator")

    answered_count = len(st.session_state.exam_answers)
    unanswered_count = len(questions) - answered_count
    st.caption(f"✅ Answered: {answered_count}  |  ⬜ Unanswered: {unanswered_count}")

    buttons_per_row = 10
    total_questions = len(questions)

    for row_start in range(0, total_questions, buttons_per_row):
        row_end = min(row_start + buttons_per_row, total_questions)
        num_in_row = row_end - row_start
        cols = st.columns(num_in_row)

        for col_idx in range(num_in_row):
            i = row_start + col_idx
            q = questions[i]
            is_answered = q.id in st.session_state.exam_answers
            is_current = (i == current_idx)

            if is_current:
                label = f"👉 {i + 1}"
            elif is_answered:
                label = f"✅ {i + 1}"
            else:
                label = f"⬜ {i + 1}"

            with cols[col_idx]:
                if st.button(label, key=f"nav_{i}"):
                    st.session_state.current_q_index = i
                    st.rerun()


def render_exam_results():
    """Render exam results with images"""
    questions = st.session_state.exam_questions
    answers = st.session_state.exam_answers

    correct = 0
    incorrect = 0
    unattempted = 0

    for q in questions:
        user_ans = answers.get(q.id)
        if user_ans is None:
            unattempted += 1
        elif user_ans == q.correct_answer:
            correct += 1
        else:
            incorrect += 1

    # Show total time taken
    if st.session_state.exam_start_time:
        total_elapsed = int((datetime.now() - st.session_state.exam_start_time).total_seconds())
        hrs = total_elapsed // 3600
        mins = (total_elapsed % 3600) // 60
        secs = total_elapsed % 60
        if hrs > 0:
            st.info(f"⏱ Total Time: {hrs:02d}:{mins:02d}:{secs:02d}")
        else:
            st.info(f"⏱ Total Time: {mins:02d}:{secs:02d}")

    st.markdown("## 📊 Exam Results")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Score", f"{correct}/{len(questions)}")

    with col2:
        accuracy = (correct / (correct + incorrect) * 100) if (correct + incorrect) > 0 else 0
        st.metric("Accuracy", f"{accuracy:.1f}%")

    with col3:
        st.metric("Correct", correct)

    with col4:
        st.metric("Incorrect", incorrect)

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 New Exam", type="primary"):
            st.session_state.exam_active = False
            st.session_state.current_page = 'practice'
            st.rerun()

    with col2:
        show_review = st.checkbox("📖 Show Detailed Review", value=True)

    if show_review:
        st.markdown("---")
        st.markdown("## 📖 Question Review")

        filter_opt = st.radio(
            "Show:",
            ["All", "Incorrect Only", "Correct Only", "Unattempted"],
            horizontal=True,
        )

        for i, q in enumerate(questions):
            user_ans = answers.get(q.id)
            is_correct = user_ans == q.correct_answer
            is_attempted = user_ans is not None

            if filter_opt == "Incorrect Only" and (is_correct or not is_attempted):
                continue
            if filter_opt == "Correct Only" and not is_correct:
                continue
            if filter_opt == "Unattempted" and is_attempted:
                continue

            with st.expander(
                f"{'✅' if is_correct else '❌' if is_attempted else '⬜'} "
                f"Q{i+1}. {q.question_text[:80]}...",
                expanded=not is_correct and is_attempted,
            ):
                st.markdown(f"**Question:** {q.question_text}")
                display_question_image(q)
                st.markdown("---")

                for opt in ['A', 'B', 'C', 'D']:
                    opt_text = getattr(q, f'option_{opt.lower()}')

                    if opt == q.correct_answer and opt == user_ans:
                        st.markdown(f'''
                            <div class="option-correct">
                                ✅ <strong>{opt}.</strong> {opt_text} (Your answer - Correct!)
                            </div>
                        ''', unsafe_allow_html=True)
                    elif opt == q.correct_answer:
                        st.markdown(f'''
                            <div class="option-correct">
                                ✅ <strong>{opt}.</strong> {opt_text} (Correct Answer)
                            </div>
                        ''', unsafe_allow_html=True)
                    elif opt == user_ans:
                        st.markdown(f'''
                            <div class="option-incorrect">
                                ❌ <strong>{opt}.</strong> {opt_text} (Your answer)
                            </div>
                        ''', unsafe_allow_html=True)
                    else:
                        st.markdown(f'''
                            <div class="option-normal">
                                ⚪ <strong>{opt}.</strong> {opt_text}
                            </div>
                        ''', unsafe_allow_html=True)

                if q.explanation:
                    st.markdown(f'''
                        <div class="explanation-box">
                            <strong>📚 Explanation:</strong><br>
                            {q.explanation}
                        </div>
                    ''', unsafe_allow_html=True)

                st.caption(f"Source: {q.source_file} | Subject: {q.subject or 'Untagged'}")


def render_mock_login():
    """Mock exam login page"""
    st.header("🎯 Real Mock Test - Login")

    st.markdown("""
    **Rules:**
    - ⏱ Timed exam — same duration as real FMGE
    - 📝 150 questions, no going back after submission
    - 🚫 One attempt per day
    - 🔒 Navigation locked during exam
    """)

    st.markdown("---")

    user_id = st.text_input("Registration ID")
    password = st.text_input("Password / DOB", type="password")

    if st.button("🎯 Enter Mock Exam", type="primary"):
        if not validate_user(user_id, password):
            st.error("Invalid credentials")
            return

        st.session_state.user_id = user_id
        st.session_state.exam_mode = "mock"
        st.session_state.current_page = "mock_exam"
        st.rerun()

    st.markdown("---")
    if st.button("⬅️ Back to Home"):
        st.session_state.current_page = 'home'
        st.rerun()


def render_mock_exam():
    """Render the real mock exam with timer and navigator"""
    mock_store = MockExamStorage()
    mock_id = get_current_mock_id()
    user_id = st.session_state.user_id

    # 🚫 Prevent re-attempt
    if mock_store.mock_attempt_exists(user_id, mock_id):
        st.error("❌ You have already attempted today's mock exam.")
        st.markdown("Come back tomorrow for a new mock test!")
        if st.button("🏠 Go Home"):
            st.session_state.exam_mode = "practice"
            st.session_state.current_page = "home"
            st.rerun()
        st.stop()

    # Init mock session once
    init_mock_session(st.session_state.questions)

    time_left = remaining_time()

    # ⏱ Auto submit when time runs out
    if time_left <= 0:
        submit_mock_exam()
        return

    # ── Timer display ──
    t_mins = time_left // 60
    t_secs = time_left % 60

    if time_left <= 300:
        st.error(f"⏰ LAST 5 MINUTES — {t_mins:02d}:{t_secs:02d}")
    elif time_left <= 900:
        st.warning(f"⏱ Time Left: {t_mins:02d}:{t_secs:02d}")
    else:
        st.info(f"⏱ Time Left: {t_mins:02d}:{t_secs:02d}")

    idx = st.session_state.mock_current_q
    questions = st.session_state.mock_questions
    question = questions[idx]

    # ── Header info ──
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"### Question {idx + 1}/150")
    with col2:
        answered_count = sum(1 for a in st.session_state.mock_answers if a is not None)
        st.markdown(f"### ✅ {answered_count}/150")

    st.markdown("---")

    # ── Question ──
    st.markdown(f"""
        <div class="question-box">
            <strong>Q{idx+1}.</strong> {question.question_text}
        </div>
    """, unsafe_allow_html=True)

    display_question_image(question)

    # ── Options ──
    options = {
        'A': question.option_a,
        'B': question.option_b,
        'C': question.option_c,
        'D': question.option_d,
    }

    current_answer = st.session_state.mock_answers[idx]

    # Save answer immediately via on_change callback
    def save_mock_answer():
        picked = st.session_state[f"mock_q_{idx}"]
        if picked:
            start_exam_if_needed()
            st.session_state.mock_answers[idx] = picked

    st.radio(
        "Select your answer:",
        options=['A', 'B', 'C', 'D'],
        format_func=lambda x: f"{x}. {options[x]}",
        index=['A', 'B', 'C', 'D'].index(current_answer) if current_answer else None,
        key=f"mock_q_{idx}",
        on_change=save_mock_answer
    )

    st.markdown("---")

    # ── Navigation buttons ──
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("⬅️ Previous", disabled=idx == 0):
            st.session_state.mock_current_q -= 1
            st.rerun()

    with col2:
        if st.button("➡️ Next", disabled=idx >= 149):
            st.session_state.mock_current_q += 1
            st.rerun()

    with col3:
        if st.button("❌ Clear"):
            st.session_state.mock_answers[idx] = None
            st.rerun()

    with col4:
        if st.button("📤 Submit Exam", type="primary"):
            unanswered = sum(1 for a in st.session_state.mock_answers if a is None)
            if unanswered > 0:
                st.warning(f"⚠️ You have {unanswered} unanswered questions!")
                st.session_state['confirm_submit'] = True
            else:
                submit_mock_exam()

    # Confirm submit if unanswered questions
    if st.session_state.get('confirm_submit'):
        st.markdown("---")
        st.error("Are you sure you want to submit with unanswered questions?")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Yes, Submit Now", type="primary"):
                st.session_state['confirm_submit'] = False
                submit_mock_exam()
        with c2:
            if st.button("❌ No, Continue Exam"):
                st.session_state['confirm_submit'] = False
                st.rerun()

    # ══════════════════════════════════════════════
    # QUESTION NAVIGATOR GRID
    # ══════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 📋 Question Navigator")

    answered_total = sum(1 for a in st.session_state.mock_answers if a is not None)
    unanswered_total = 150 - answered_total
    st.caption(f"✅ Answered: {answered_total}  |  ⬜ Unanswered: {unanswered_total}")

    buttons_per_row = 10
    total_questions = len(questions)

    for row_start in range(0, total_questions, buttons_per_row):
        row_end = min(row_start + buttons_per_row, total_questions)
        num_in_row = row_end - row_start
        cols = st.columns(num_in_row)

        for col_idx in range(num_in_row):
            i = row_start + col_idx
            is_answered = st.session_state.mock_answers[i] is not None
            is_current = (i == idx)

            if is_current:
                label = f"👉 {i + 1}"
            elif is_answered:
                label = f"✅ {i + 1}"
            else:
                label = f"⬜ {i + 1}"

            with cols[col_idx]:
                if st.button(label, key=f"mock_nav_{i}"):
                    st.session_state.mock_current_q = i
                    st.rerun()


def submit_mock_exam():
    """Submit mock exam and save results"""
    mock_store = MockExamStorage()
    mock_id = get_current_mock_id()

    analysis = analyze_mock_attempt(
        user_id=st.session_state.user_id,
        mock_id=mock_id,
        questions=st.session_state.mock_questions,
        answers=st.session_state.mock_answers,
        start_time=st.session_state.mock_start_time,
        end_time=time.time(),
    )

    mock_store.save_mock_attempt({
        "user_id": st.session_state.user_id,
        "mock_id": mock_id,
        "mode": "mock",
        "raw": {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "start_time": st.session_state.mock_start_time,
            "end_time": time.time(),
            "answers": st.session_state.mock_answers,
        },
        "analysis": analysis.to_dict(),
    })

    st.success("✅ Mock Exam Submitted Successfully!")
    st.info(
        f"📊 You answered **{analysis.correct} out of "
        f"{analysis.total_questions}** questions correctly."
    )

    # Exit mock mode
    st.session_state.exam_mode = "practice"
    st.session_state.current_page = "home"
    st.session_state['confirm_submit'] = False
    st.stop()


def render_practice():
    """Render practice setup page"""
    st.header("📝 Start Practice Session")

    questions = st.session_state.questions

    col1, col2 = st.columns(2)

    with col1:
        num_questions = st.slider("Number of Questions", 10, min(200, len(questions)), 50)

    with col2:
        mode = st.selectbox("Mode", ["All Questions", "Image Questions Only", "Non-Image Questions"])

    subjects = sorted(set(q.subject for q in questions if q.subject))
    subjects = ["All Subjects"] + subjects

    selected_subject = st.selectbox("Filter by Subject", subjects)

    available = [q for q in questions if q.is_valid and q.correct_answer]

    if mode == "Image Questions Only":
        available = [q for q in available if q.images]
    elif mode == "Non-Image Questions":
        available = [q for q in available if not q.images and not q.has_image_reference]

    if selected_subject != "All Subjects":
        available = [q for q in available if q.subject == selected_subject]

    st.info(f"📊 {len(available)} questions available with current filters")

    if st.button("🚀 Start Practice", type="primary", use_container_width=True):
        if len(available) >= num_questions:
            selected = random.sample(available, num_questions)
        else:
            selected = available

        if selected:
            start_practice_exam_with_questions(selected)
        else:
            st.error("No questions match your filters!")


def start_practice_exam_with_questions(selected_questions):
    """Start practice exam with pre-selected questions"""
    st.session_state.exam_questions = selected_questions
    st.session_state.exam_answers = {}
    st.session_state.exam_submitted = False
    st.session_state.exam_active = True
    st.session_state.current_q_index = 0
    st.session_state.exam_start_time = datetime.now()
    st.session_state.current_page = 'exam'
    st.rerun()


def render_browse():
    """Browse all questions"""
    st.header("📖 Browse Questions")

    questions = st.session_state.questions

    col1, col2, col3 = st.columns(3)

    with col1:
        search = st.text_input("🔍 Search", "")

    with col2:
        subjects = ["All"] + sorted(set(q.subject for q in questions if q.subject))
        subject = st.selectbox("Subject", subjects)

    with col3:
        image_filter = st.selectbox("Images", ["All", "With Images", "Without Images"])

    filtered = questions

    if search:
        filtered = [q for q in filtered if search.lower() in q.question_text.lower()]

    if subject != "All":
        filtered = [q for q in filtered if q.subject == subject]

    if image_filter == "With Images":
        filtered = [q for q in filtered if q.images]
    elif image_filter == "Without Images":
        filtered = [q for q in filtered if not q.images]

    st.info(f"Showing {len(filtered)} questions")

    per_page = 10
    total_pages = (len(filtered) - 1) // per_page + 1 if filtered else 1

    page = st.number_input("Page", 1, total_pages, 1)

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

    for i, q in enumerate(filtered[start_idx:end_idx]):
        with st.expander(f"Q{start_idx + i + 1}. {q.question_text[:100]}..."):
            st.markdown(f"**Question:** {q.question_text}")
            display_question_image(q)
            st.markdown("---")

            col1, col2 = st.columns(2)

            with col1:
                st.markdown(f"**A.** {q.option_a}")
                st.markdown(f"**B.** {q.option_b}")

            with col2:
                st.markdown(f"**C.** {q.option_c}")
                st.markdown(f"**D.** {q.option_d}")

            if q.correct_answer:
                st.success(f"✅ Correct Answer: **{q.correct_answer}**")

            if q.explanation:
                st.info(f"📚 {q.explanation[:500]}...")

            st.caption(f"Source: {q.source_file} | Subject: {q.subject or 'Untagged'}")


def render_image_questions():
    """View only image-based questions"""
    st.header("🖼️ Image-Based Questions")

    questions = st.session_state.questions

    image_questions = [q for q in questions if q.images]
    needs_images = [q for q in questions if q.has_image_reference and not q.images]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("With Images", len(image_questions))

    with col2:
        st.metric("Missing Images", len(needs_images))

    with col3:
        st.metric("Total Image Refs", len(image_questions) + len(needs_images))

    st.markdown("---")

    tab1, tab2 = st.tabs(["✅ With Images", "⚠️ Missing Images"])

    with tab1:
        if not image_questions:
            st.info("No questions with linked images found.")
        else:
            for i, q in enumerate(image_questions[:20]):
                with st.expander(f"Q{i+1}. {q.question_text[:80]}...", expanded=(i < 3)):
                    st.markdown(f"**Question:** {q.question_text}")
                    display_question_image(q)

                    cols = st.columns(2)
                    with cols[0]:
                        st.markdown(f"**A.** {q.option_a}")
                        st.markdown(f"**B.** {q.option_b}")
                    with cols[1]:
                        st.markdown(f"**C.** {q.option_c}")
                        st.markdown(f"**D.** {q.option_d}")

                    if q.correct_answer:
                        st.success(f"Answer: {q.correct_answer}")

    with tab2:
        if not needs_images:
            st.success("All image references have linked images!")
        else:
            st.warning(f"{len(needs_images)} questions reference images but couldn't be linked.")

            for i, q in enumerate(needs_images[:20]):
                with st.expander(f"Q{i+1}. {q.question_text[:80]}..."):
                    st.markdown(f"**Question:** {q.question_text}")
                    st.markdown(f"**Pattern matched:** `{q.image_pattern_matched}`")
                    st.markdown(f"**Page:** {q.page_number}")
                    st.markdown(f"**Source:** {q.source_file}")


def render_stats():
    """Render statistics page"""
    st.header("📊 Question Bank Statistics")

    questions = st.session_state.questions

    if not questions:
        st.warning("No questions loaded.")
        return

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Questions", len(questions))

    with col2:
        with_ans = sum(1 for q in questions if q.correct_answer)
        st.metric("With Answers", with_ans)

    with col3:
        with_exp = sum(1 for q in questions if q.explanation)
        st.metric("With Explanations", with_exp)

    with col4:
        with_img = sum(1 for q in questions if q.images)
        st.metric("With Images", with_img)

    st.markdown("---")

    st.subheader("📚 Subject Distribution")

    subject_counts = {}
    for q in questions:
        subj = q.subject or "Untagged"
        subject_counts[subj] = subject_counts.get(subj, 0) + 1

    sorted_subjects = sorted(subject_counts.items(), key=lambda x: -x[1])

    for subj, count in sorted_subjects[:15]:
        pct = count / len(questions) * 100
        st.progress(pct / 100, f"{subj}: {count} ({pct:.1f}%)")

    st.markdown("---")

    st.subheader("📁 Source Files")

    source_counts = {}
    for q in questions:
        source_counts[q.source_file] = source_counts.get(q.source_file, 0) + 1

    for source, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        st.text(f"{source}: {count} questions")


def main():
    init_session_state()

    # Sidebar only if NOT in mock mode
    if st.session_state.exam_mode != 'mock':
        render_sidebar()

    page = st.session_state.current_page

    if page == 'home':
        render_home()
    elif page == 'practice':
        render_practice()
    elif page == 'exam':
        render_exam()
    elif page == 'mock_login':
        render_mock_login()
    elif page == 'mock_exam':
        render_mock_exam()
    elif page == 'browse':
        render_browse()
    elif page == 'images':
        render_image_questions()
    elif page == 'stats':
        render_stats()
    else:
        render_home()


if __name__ == "__main__":
    main()