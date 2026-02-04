"""
FMGE Practice Engine - Streamlit UI
Complete interface with image display
"""

import streamlit as st
from pathlib import Path
import sys
import base64
import random
from datetime import datetime, timedelta
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.json_storage import QuestionStorage
from config.settings import DATA_DIR, EXAM_CONFIG

# Page config
st.set_page_config(
    page_title="FMGE Practice Engine",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better image display
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
    """Load an image file and convert to base64 for display"""
    try:
        path = Path(image_path)
        
        # Handle relative paths
        if not path.is_absolute():
            path = DATA_DIR / image_path
        
        if path.exists():
            with open(path, 'rb') as f:
                data = base64.b64encode(f.read()).decode()
            
            # Determine format from extension
            ext = path.suffix.lower().replace('.', '')
            if ext == 'jpg':
                ext = 'jpeg'
            
            return f"data:image/{ext};base64,{data}"
        else:
            return None
    except Exception as e:
        st.error(f"Error loading image: {e}")
        return None


def display_question_image(question):
    """Display image for a question if available"""
    if question.images:
        for img_path in question.images:
            # Check if it's already a data URI
            if img_path.startswith('data:'):
                st.markdown(f'''
                    <div class="question-image">
                        <img src="{img_path}" alt="Question Image">
                    </div>
                ''', unsafe_allow_html=True)
            else:
                # Load from file
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


def render_sidebar():
    """Render navigation sidebar"""
    st.sidebar.markdown("## 🩺 FMGE Practice")
    st.sidebar.markdown("---")
    
    # Navigation buttons
    if st.sidebar.button("🏠 Home", use_container_width=True):
        st.session_state.current_page = 'home'
        st.session_state.exam_active = False
        st.rerun()
    
    if st.sidebar.button("📝 Practice", use_container_width=True):
        st.session_state.current_page = 'practice'
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
    
    # Quick stats
    total = len(st.session_state.questions)
    with_images = sum(1 for q in st.session_state.questions if q.images)
    
    st.sidebar.metric("Total Questions", total)
    st.sidebar.metric("With Images", with_images)


def render_home():
    """Render home page"""
    st.markdown('<h1 class="main-header">🩺 FMGE Practice Engine</h1>', unsafe_allow_html=True)
    
    st.markdown("""
    ### Welcome to your FMGE preparation platform!
    
    Practice with real FMGE questions including **image-based questions**.
    """)
    
    # Stats cards
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
    
    # Quick actions
    st.subheader("🚀 Quick Start")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📝 Start Practice (50 Qs)", use_container_width=True, type="primary"):
            start_exam(50)
    
    with col2:
        if st.button("📋 Full Mock (150 Qs)", use_container_width=True):
            start_exam(150)
    
    with col3:
        if st.button("🖼️ Image Questions Only", use_container_width=True):
            start_exam(50, images_only=True)


def start_exam(num_questions: int, images_only: bool = False):
    """Start a new exam session"""
    questions = st.session_state.questions
    
    # Filter questions
    available = [q for q in questions if q.is_valid and q.correct_answer]
    
    if images_only:
        available = [q for q in available if q.images]
    
    if len(available) < num_questions:
        num_questions = len(available)
    
    if num_questions == 0:
        st.error("No questions available!")
        return
    
    # Select random questions
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
    """Render active exam"""
    if not st.session_state.exam_active:
        st.warning("No active exam. Start a new practice session.")
        if st.button("Go to Practice"):
            st.session_state.current_page = 'practice'
            st.rerun()
        return
    
    questions = st.session_state.exam_questions
    current_idx = st.session_state.current_q_index
    
    if st.session_state.exam_submitted:
        render_exam_results()
        return
    
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
    
    # Question text
    st.markdown(f'''
        <div class="question-box">
            <strong>Q{current_idx + 1}.</strong> {question.question_text}
        </div>
    ''', unsafe_allow_html=True)
    
    # Display image if available
    display_question_image(question)
    
    # Options
    options = {
        'A': question.option_a,
        'B': question.option_b,
        'C': question.option_c,
        'D': question.option_d,
    }
    
    current_answer = st.session_state.exam_answers.get(question.id)
    
    selected = st.radio(
        "Select your answer:",
        options=['A', 'B', 'C', 'D'],
        format_func=lambda x: f"{x}. {options[x]}",
        index=['A', 'B', 'C', 'D'].index(current_answer) if current_answer else None,
        key=f"q_{question.id}"
    )
    
    # Save answer
    if selected:
        st.session_state.exam_answers[question.id] = selected
    
    st.markdown("---")
    
    # Navigation
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
    
    # Question palette
    st.markdown("---")
    st.markdown("### Question Navigator")
    
    cols = st.columns(10)
    for i, q in enumerate(questions):
        col_idx = i % 10
        with cols[col_idx]:
            answered = q.id in st.session_state.exam_answers
            btn_label = f"{'✅' if answered else '⬜'} {i+1}"
            if st.button(btn_label, key=f"nav_{i}"):
                st.session_state.current_q_index = i
                st.rerun()


def render_exam_results():
    """Render exam results with images"""
    questions = st.session_state.exam_questions
    answers = st.session_state.exam_answers
    
    # Calculate score
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
    
    # Summary
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
    
    # Buttons
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
        
        # Filter options
        filter_opt = st.radio(
            "Show:",
            ["All", "Incorrect Only", "Correct Only", "Unattempted"],
            horizontal=True
        )
        
        for i, q in enumerate(questions):
            user_ans = answers.get(q.id)
            is_correct = user_ans == q.correct_answer
            is_attempted = user_ans is not None
            
            # Apply filter
            if filter_opt == "Incorrect Only" and (is_correct or not is_attempted):
                continue
            if filter_opt == "Correct Only" and not is_correct:
                continue
            if filter_opt == "Unattempted" and is_attempted:
                continue
            
            # Question card
            with st.expander(
                f"{'✅' if is_correct else '❌' if is_attempted else '⬜'} Q{i+1}. {q.question_text[:80]}...",
                expanded=not is_correct and is_attempted
            ):
                # Question text
                st.markdown(f"**Question:** {q.question_text}")
                
                # Display image
                display_question_image(q)
                
                st.markdown("---")
                
                # Options with highlighting
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
                
                # Explanation
                if q.explanation:
                    st.markdown(f'''
                        <div class="explanation-box">
                            <strong>📚 Explanation:</strong><br>
                            {q.explanation}
                        </div>
                    ''', unsafe_allow_html=True)
                
                st.caption(f"Source: {q.source_file} | Subject: {q.subject or 'Untagged'}")


def render_practice():
    """Render practice setup page"""
    st.header("📝 Start Practice Session")
    
    questions = st.session_state.questions
    
    # Options
    col1, col2 = st.columns(2)
    
    with col1:
        num_questions = st.slider("Number of Questions", 10, min(200, len(questions)), 50)
    
    with col2:
        mode = st.selectbox("Mode", ["All Questions", "Image Questions Only", "Non-Image Questions"])
    
    # Subject filter
    subjects = sorted(set(q.subject for q in questions if q.subject))
    subjects = ["All Subjects"] + subjects
    
    selected_subject = st.selectbox("Filter by Subject", subjects)
    
    # Filter questions
    available = [q for q in questions if q.is_valid and q.correct_answer]
    
    if mode == "Image Questions Only":
        available = [q for q in available if q.images]
    elif mode == "Non-Image Questions":
        available = [q for q in available if not q.images and not q.has_image_reference]
    
    if selected_subject != "All Subjects":
        available = [q for q in available if q.subject == selected_subject]
    
    st.info(f"📊 {len(available)} questions available with current filters")
    
    # Start button
    if st.button("🚀 Start Practice", type="primary", use_container_width=True):
        if len(available) >= num_questions:
            selected = random.sample(available, num_questions)
        else:
            selected = available
        
        if selected:
            st.session_state.exam_questions = selected
            st.session_state.exam_answers = {}
            st.session_state.exam_submitted = False
            st.session_state.exam_active = True
            st.session_state.current_q_index = 0
            st.session_state.exam_start_time = datetime.now()
            st.session_state.current_page = 'exam'
            st.rerun()
        else:
            st.error("No questions match your filters!")


def render_browse():
    """Browse all questions"""
    st.header("📖 Browse Questions")
    
    questions = st.session_state.questions
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        search = st.text_input("🔍 Search", "")
    
    with col2:
        subjects = ["All"] + sorted(set(q.subject for q in questions if q.subject))
        subject = st.selectbox("Subject", subjects)
    
    with col3:
        image_filter = st.selectbox("Images", ["All", "With Images", "Without Images"])
    
    # Apply filters
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
    
    # Pagination
    per_page = 10
    total_pages = (len(filtered) - 1) // per_page + 1 if filtered else 1
    
    page = st.number_input("Page", 1, total_pages, 1)
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    # Display questions
    for i, q in enumerate(filtered[start_idx:end_idx]):
        with st.expander(f"Q{start_idx + i + 1}. {q.question_text[:100]}..."):
            st.markdown(f"**Question:** {q.question_text}")
            
            # Display image
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
    
    # Filter to image questions
    image_questions = [q for q in questions if q.images]
    needs_images = [q for q in questions if q.has_image_reference and not q.images]
    
    # Stats
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("With Images", len(image_questions))
    
    with col2:
        st.metric("Missing Images", len(needs_images))
    
    with col3:
        st.metric("Total Image Refs", len(image_questions) + len(needs_images))
    
    st.markdown("---")
    
    # Tabs
    tab1, tab2 = st.tabs(["✅ With Images", "⚠️ Missing Images"])
    
    with tab1:
        if not image_questions:
            st.info("No questions with linked images found.")
        else:
            for i, q in enumerate(image_questions[:20]):  # Show first 20
                with st.expander(f"Q{i+1}. {q.question_text[:80]}...", expanded=(i < 3)):
                    st.markdown(f"**Question:** {q.question_text}")
                    
                    # Display image prominently
                    display_question_image(q)
                    
                    # Options
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
    
    # Overall stats
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
    
    # Subject distribution
    st.subheader("📚 Subject Distribution")
    
    subject_counts = {}
    for q in questions:
        subj = q.subject or "Untagged"
        subject_counts[subj] = subject_counts.get(subj, 0) + 1
    
    # Sort by count
    sorted_subjects = sorted(subject_counts.items(), key=lambda x: -x[1])
    
    for subj, count in sorted_subjects[:15]:
        pct = count / len(questions) * 100
        st.progress(pct / 100, f"{subj}: {count} ({pct:.1f}%)")
    
    st.markdown("---")
    
    # Source distribution
    st.subheader("📁 Source Files")
    
    source_counts = {}
    for q in questions:
        source_counts[q.source_file] = source_counts.get(q.source_file, 0) + 1
    
    for source, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        st.text(f"{source}: {count} questions")


def main():
    """Main application entry point"""
    init_session_state()
    render_sidebar()
    
    # Route to current page
    page = st.session_state.current_page
    
    if page == 'home':
        render_home()
    elif page == 'practice':
        render_practice()
    elif page == 'exam':
        render_exam()
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