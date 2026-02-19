import streamlit as st
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
import time

# ───────────────────────────────────────────────
# Paths & Session State
# ───────────────────────────────────────────────
QUIZZES_DIR = Path("quizzes")
QUIZZES_DIR.mkdir(exist_ok=True)

defaults = {
    'quizzes': {},
    'selected_quiz': None,
    'user_answers': {},
    'show_answers': False,
    'score': None,
    'quiz_start_time': None,
    'time_limit_minutes': None,
    'timer_expired': False,
    'reveal_correct_answers': False,
    'selected_categories': [],
    'admin_logged_in': False,
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ───────────────────────────────────────────────
# Admin helpers
# ───────────────────────────────────────────────

ADMIN_PASSWORD = "quizmaster2025"  # ← CHANGE THIS or use st.secrets!

def is_admin():
    return st.session_state.get("admin_logged_in", False)

def delete_quiz(title):
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
    path = QUIZZES_DIR / f"{safe_title}.json"
    if path.exists():
        path.unlink()
        st.session_state.quizzes.pop(title, None)
        st.success(f"Quiz **{title}** deleted.")
        if st.session_state.selected_quiz == title:
            st.session_state.selected_quiz = None
        st.rerun()
    else:
        st.error("Quiz file not found.")

# ───────────────────────────────────────────────
# Load / Save / Categories
# ───────────────────────────────────────────────
def load_quizzes():
    st.session_state.quizzes.clear()
    for file in QUIZZES_DIR.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                title = data.get("quiz_title", file.stem)
                st.session_state.quizzes[title] = data
        except Exception as e:
            st.warning(f"Could not load {file.name}: {e}")

load_quizzes()

def get_all_categories():
    cats = set()
    for quiz in st.session_state.quizzes.values():
        cat = quiz.get("category", "Uncategorized")
        if cat:
            cats.add(cat)
    return sorted(cats)

def save_quiz(title, data):
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
    path = QUIZZES_DIR / f"{safe_title}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    load_quizzes()

# ───────────────────────────────────────────────
# Add new quiz (admin only)
# ───────────────────────────────────────────────
def submit_quiz_section():
    st.header("Add New Quiz (JSON)")
    tab1, tab2 = st.tabs(["Paste JSON", "Upload file"])

    all_categories = get_all_categories() + ["Uncategorized"] if get_all_categories() else ["Uncategorized"]

    with tab1:
        quiz_json = st.text_area("Quiz JSON", height=240, placeholder="Paste valid quiz JSON here...")
        quiz_title = st.text_input("Quiz title (optional)", key="new_quiz_title")
        category = st.selectbox(
            "Category / Department",
            options=all_categories + ["New category..."],
            key="new_quiz_category_select"
        )

        new_category = None
        if category == "New category...":
            new_category = st.text_input("Enter new category name", key="new_category_input")

        final_category = new_category.strip() if new_category else category

        if st.button("Submit JSON", type="primary", key="submit_json"):
            if not quiz_json.strip():
                st.error("Please paste some JSON.")
                return
            try:
                data = json.loads(quiz_json)
                title = quiz_title.strip() or data.get("quiz_title") or f"Quiz_{len(st.session_state.quizzes)+1}"
                if final_category and final_category != "Uncategorized":
                    data["category"] = final_category

                if title in st.session_state.quizzes:
                    if st.checkbox("Overwrite existing quiz?", key="overwrite_confirm"):
                        save_quiz(title, data)
                        st.success(f"Quiz **{title}** updated!")
                    else:
                        st.info("Keeping existing version — choose a different title.")
                else:
                    save_quiz(title, data)
                    st.success(f"Quiz **{title}** saved!")
            except json.JSONDecodeError:
                st.error("Invalid JSON format.")

    with tab2:
        uploaded = st.file_uploader("Upload .json file", type=["json"])
        if uploaded and st.button("Process file", key="submit_file"):
            try:
                data = json.load(uploaded)
                title = data.get("quiz_title", uploaded.name.replace(".json", ""))
                if "category" not in data or not data["category"]:
                    data["category"] = "Uncategorized"

                if title in st.session_state.quizzes:
                    if st.checkbox("Overwrite existing?", key="ow_file"):
                        save_quiz(title, data)
                        st.success(f"Quiz **{title}** updated from file!")
                    else:
                        st.info("Skipped — quiz already exists.")
                else:
                    save_quiz(title, data)
                    st.success(f"Quiz **{title}** added!")
            except Exception as e:
                st.error(f"Error: {e}")

# ───────────────────────────────────────────────
# Take quiz – stable widgets + smoother timer
# ───────────────────────────────────────────────
def take_quiz_section():
    quiz = st.session_state.quizzes[st.session_state.selected_quiz]
    title = quiz.get('quiz_title', st.session_state.selected_quiz)
    category = quiz.get('category', 'Uncategorized')
    questions = quiz.get("questions", [])

    st.header(f"Quiz: {title}")
    st.caption(f"Category / Department: **{category}**")

    timer_placeholder = st.empty()

    if st.session_state.quiz_start_time is None and not st.session_state.show_answers:
        st.info("Optional: set a time limit")
        time_choice = st.select_slider(
            "Time limit",
            options=["No timer", "10 min", "15 min", "20 min", "25 min", "30 min", "35 min", "40 min"],
            value="No timer"
        )

        if st.button("Start Quiz", type="primary"):
            if time_choice != "No timer":
                minutes = int(time_choice.split()[0])
                st.session_state.time_limit_minutes = minutes
                st.session_state.quiz_start_time = datetime.now()
            st.rerun()

    timer_running = False
    if st.session_state.quiz_start_time is not None and not st.session_state.show_answers:
        elapsed = datetime.now() - st.session_state.quiz_start_time
        remaining_sec = max(0, int(st.session_state.time_limit_minutes * 60 - elapsed.total_seconds())) \
            if st.session_state.time_limit_minutes else 999999999

        if remaining_sec <= 0:
            st.session_state.timer_expired = True
            st.session_state.show_answers = True
            timer_placeholder.error("⏰ Time's up! Quiz auto-submitted.")
            st.rerun()
        else:
            mins, secs = divmod(remaining_sec, 60)
            timer_placeholder.caption(f"⏳ **Time remaining: {mins:02d}:{secs:02d}**")
            timer_running = True

    for i, q in enumerate(questions):
        st.subheader(f"Q{i+1}. {q.get('question', '—')}")

        opts = q.get("options", [])
        correct = q.get("correct")
        explanation = q.get("explanation", "")

        if not opts:
            st.error(f"Q{i+1}: Missing or empty 'options' list")
            continue
        if correct is None:
            st.error(f"Q{i+1}: Missing 'correct' key")
            continue
        if correct not in opts:
            st.error(f"Q{i+1}: 'correct' value '{correct}' does not match any option → options are: {opts}")
            continue

        key = f"answer_q_{i}"

        if not st.session_state.show_answers and not st.session_state.timer_expired:
            choice = st.radio(
                "Your answer:",
                opts,
                index=st.session_state.user_answers.get(i, None),
                key=key,
                horizontal=False
            )
            if choice is not None:
                st.session_state.user_answers[i] = opts.index(choice)
        else:
            user_idx = st.session_state.user_answers.get(i, None)
            correct_idx = opts.index(correct) if correct in opts else -1

            st.radio(
                "Your selection (review)",
                opts,
                index=user_idx if user_idx is not None else 0,
                key=f"review_{key}",
                disabled=True,
                horizontal=True
            )

            if st.session_state.reveal_correct_answers:
                if user_idx is None:
                    st.warning("Skipped")
                    st.markdown(f"**Correct:** {correct}")
                elif user_idx == correct_idx:
                    st.success("Correct ✓")
                else:
                    st.error("Incorrect ✗")
                    st.markdown(f"**Correct:** {correct}")

                if explanation:
                    with st.expander("Explanation"):
                        st.write(explanation)

        st.markdown("---")

    quiz_ended = st.session_state.show_answers or st.session_state.timer_expired

    if not quiz_ended:
        if st.button("Submit Quiz", type="primary"):
            correct_count = sum(
                1 for i, q in enumerate(questions)
                if st.session_state.user_answers.get(i) is not None
                and q["options"][st.session_state.user_answers[i]] == q["correct"]
            )
            st.session_state.score = (correct_count, len(questions))
            st.session_state.show_answers = True
            st.rerun()
    else:
        if st.session_state.score:
            correct, total = st.session_state.score
            pct = correct / total * 100 if total > 0 else 0
            st.success(f"**Score: {correct}/{total}**  ({pct:.0f}%)")

        if not st.session_state.reveal_correct_answers:
            if st.button("🔍 Show Correct Answers & Explanations"):
                st.session_state.reveal_correct_answers = True
                st.rerun()
        else:
            st.info("Correct answers are visible above ↑")
            if st.button("Hide Correct Answers"):
                st.session_state.reveal_correct_answers = False
                st.rerun()

    if quiz_ended:
        if st.button("Restart this quiz"):
            for k in ['user_answers', 'show_answers', 'score', 'quiz_start_time',
                      'time_limit_minutes', 'timer_expired', 'reveal_correct_answers']:
                if k in st.session_state:
                    if isinstance(st.session_state[k], dict):
                        st.session_state[k].clear()
                    else:
                        st.session_state[k] = None if k != 'reveal_correct_answers' else False
            st.rerun()

    if timer_running:
        time.sleep(0.98)
        st.rerun()

# ───────────────────────────────────────────────
# Main Layout
# ───────────────────────────────────────────────
st.title("📝 Quiz App – Categories & Departments")

with st.sidebar:
    if not is_admin():
        with st.expander("Admin Zone", expanded=False):
            pwd = st.text_input("Admin password", type="password", key="admin_pwd_input")
            if st.button("Login as Admin", key="admin_login_btn"):
                if pwd.strip() == ADMIN_PASSWORD:
                    st.session_state.admin_logged_in = True
                    st.success("Admin access granted")
                    st.rerun()
                else:
                    st.error("Incorrect password")
    else:
        st.success("🔐 Admin mode active")
        if st.button("Logout Admin", key="admin_logout"):
            st.session_state.admin_logged_in = False
            st.rerun()

    st.divider()

    st.header("Filter by Department")
    categories = get_all_categories()
    if categories:
        st.session_state.selected_categories = st.multiselect(
            "Select departments",
            options=categories,
            default=st.session_state.selected_categories,
            help="Choose one or more categories to filter quizzes"
        )
    else:
        st.info("No categories yet — add quizzes with categories!")

    st.header("Available Quizzes")

    filtered_quizzes = {}
    for title, quiz in st.session_state.quizzes.items():
        cat = quiz.get("category", "Uncategorized")
        if not st.session_state.selected_categories or cat in st.session_state.selected_categories:
            display_label = f"{title} ({cat})"
            filtered_quizzes[display_label] = title

    if filtered_quizzes:
        for display_label, real_title in filtered_quizzes.items():
            cols = st.columns([5, 1])
            with cols[0]:
                btn_type = "primary" if real_title == st.session_state.selected_quiz else "secondary"
                if st.button(display_label, key=f"select_{real_title}", type=btn_type, use_container_width=True):
                    if real_title != st.session_state.selected_quiz:
                        st.session_state.selected_quiz = real_title
                        for k in ['user_answers', 'show_answers', 'score', 'quiz_start_time',
                                  'time_limit_minutes', 'timer_expired', 'reveal_correct_answers']:
                            if k in st.session_state:
                                if isinstance(st.session_state[k], dict):
                                    st.session_state[k].clear()
                                else:
                                    st.session_state[k] = None if k != 'reveal_correct_answers' else False
                        st.rerun()

            with cols[1]:
                if is_admin():
                    if st.button("🗑", key=f"del_{real_title}", help="Delete this quiz"):
                        delete_quiz(real_title)

    else:
        st.info("No quizzes match the selected departments (or no quizzes yet).")

    st.divider()

    if is_admin():
        submit_quiz_section()
    else:
        st.caption("Quiz creation is restricted to administrators.")

if st.session_state.selected_quiz:
    take_quiz_section()
else:
    st.info("Select a quiz from the sidebar (filter by department if needed).")