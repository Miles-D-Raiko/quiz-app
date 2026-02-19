import streamlit as st
import json
from pathlib import Path
from datetime import datetime
import time
import random

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
    'shuffled_questions': None,
    'option_shuffles': {},
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ───────────────────────────────────────────────
# Admin helpers
# ───────────────────────────────────────────────
ADMIN_PASSWORD = "quizmaster2025"  # ← CHANGE THIS or better: use st.secrets

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
        cat = quiz.get("category", None)
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
    all_categories = get_all_categories() or ["Uncategorized"]
    all_categories = sorted(set(all_categories + ["Uncategorized"]))

    with tab1:
        quiz_json = st.text_area("Quiz JSON", height=240, placeholder="Paste valid quiz JSON here...")
        quiz_title = st.text_input("Quiz title (optional)", key="new_quiz_title")
        category = st.selectbox(
            "Category / Department",
            options=all_categories + ["New category..."],
            key="new_quiz_category_select"
        )
        new_category = ""
        if category == "New category...":
            new_category = st.text_input("Enter new category name", key="new_category_input").strip()
        final_category = new_category or category

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
                        st.info("Keeping existing version.")
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
                if not data.get("category"):
                    data["category"] = "Uncategorized"
                if title in st.session_state.quizzes:
                    if st.checkbox("Overwrite existing?", key="ow_file"):
                        save_quiz(title, data)
                        st.success(f"Quiz **{title}** updated!")
                    else:
                        st.info("Skipped — quiz already exists.")
                else:
                    save_quiz(title, data)
                    st.success(f"Quiz **{title}** added!")
            except Exception as e:
                st.error(f"Error: {e}")

# ───────────────────────────────────────────────
# Take quiz – with dropdown time selection
# ───────────────────────────────────────────────
def take_quiz_section():
    quiz = st.session_state.quizzes[st.session_state.selected_quiz]
    title = quiz.get('quiz_title', st.session_state.selected_quiz)
    category = quiz.get('category', 'Uncategorized')
    original_questions = quiz.get("questions", [])

    st.header(f"Quiz: {title}")
    st.caption(f"Department: **{category}**")

    if st.session_state.quiz_start_time is None and not st.session_state.show_answers:
        st.session_state.shuffled_questions = None
        st.session_state.option_shuffles = {}

    if st.session_state.shuffled_questions is None and original_questions:
        shuffled_idx = list(range(len(original_questions)))
        random.shuffle(shuffled_idx)
        st.session_state.shuffled_questions = [original_questions[i] for i in shuffled_idx]

        st.session_state.option_shuffles = {}
        for orig_i, q in enumerate(original_questions):
            opts = q.get("options", [])
            if not opts:
                continue
            opt_idx = list(range(len(opts)))
            random.shuffle(opt_idx)
            st.session_state.option_shuffles[orig_i] = opt_idx

    shuffled_questions = st.session_state.shuffled_questions or original_questions

    timer_placeholder = st.empty()

    # ── Time limit selection (dropdown) ────────────────────────────────
    if st.session_state.quiz_start_time is None and not st.session_state.show_answers:
        st.info("Optional: choose a time limit for this attempt")

        time_options = [
            "No timer",
            "5 minutes", "10 minutes", "15 minutes", "20 minutes",
            "25 minutes", "30 minutes", "40 minutes", "50 minutes", "60 minutes"
        ]

        selected_time = st.selectbox(
            "Select Practice Duration:",
            options=time_options,
            index=0,
            key="time_limit_selectbox",
            help="Quiz will auto-submit when time expires (if a limit is chosen)."
        )

        if st.button("Start Quiz", type="primary"):
            if selected_time != "No timer":
                try:
                    minutes = int(selected_time.split()[0])
                    st.session_state.time_limit_minutes = minutes
                    st.session_state.quiz_start_time = datetime.now()
                except:
                    st.session_state.time_limit_minutes = None
                    st.session_state.quiz_start_time = datetime.now()
            else:
                st.session_state.time_limit_minutes = None
                st.session_state.quiz_start_time = datetime.now()
            st.rerun()

    # ── Timer logic ────────────────────────────────────────────────────
    timer_running = False
    if st.session_state.quiz_start_time is not None and not st.session_state.show_answers:
        elapsed = datetime.now() - st.session_state.quiz_start_time
        remaining_sec = 999_999_999

        if st.session_state.get('time_limit_minutes'):
            remaining_sec = max(0, int(st.session_state.time_limit_minutes * 60 - elapsed.total_seconds()))

        if remaining_sec <= 0 and st.session_state.get('time_limit_minutes'):
            st.session_state.timer_expired = True
            st.session_state.show_answers = True
            timer_placeholder.error("⏰ Time's up! Quiz auto-submitted.")
            st.rerun()
        else:
            if st.session_state.get('time_limit_minutes'):
                mins, secs = divmod(remaining_sec, 60)
                timer_placeholder.caption(f"⏳ **Time remaining: {mins:02d}:{secs:02d}**")
            else:
                timer_placeholder.caption("⏳ No time limit active")
            timer_running = True

    # ── Questions ──────────────────────────────────────────────────────
    for display_i, q in enumerate(shuffled_questions):
        st.subheader(f"Q{display_i+1}. {q.get('question', '—')}")
        orig_index = original_questions.index(q)
        opts_orig = q.get("options", [])
        correct_orig = q.get("correct")

        if not opts_orig or correct_orig not in opts_orig:
            st.error(f"Q{display_i+1}: Invalid question data")
            continue

        shuffle_map = st.session_state.option_shuffles.get(orig_index, list(range(len(opts_orig))))
        opts_display = [opts_orig[j] for j in shuffle_map]

        key = f"answer_{display_i}"

        if not st.session_state.show_answers and not st.session_state.timer_expired:
            choice = st.radio(
                "Your answer:",
                opts_display,
                index=st.session_state.user_answers.get(display_i, None),
                key=key,
                horizontal=False
            )
            if choice is not None:
                st.session_state.user_answers[display_i] = opts_display.index(choice)
        else:
            user_idx = st.session_state.user_answers.get(display_i, None)
            correct_display_idx = shuffle_map.index(opts_orig.index(correct_orig))

            st.radio(
                "Your selection",
                opts_display,
                index=user_idx if user_idx is not None else 0,
                key=f"review_{key}",
                disabled=True,
                horizontal=True
            )

            if st.session_state.reveal_correct_answers:
                if user_idx is None:
                    st.warning("Skipped")
                    st.markdown(f"**Correct:** {correct_orig}")
                elif user_idx == correct_display_idx:
                    st.success("Correct ✓")
                else:
                    st.error("Incorrect ✗")
                    st.markdown(f"**Correct:** {correct_orig}")

                if expl := q.get("explanation", ""):
                    with st.expander("Explanation"):
                        st.write(expl)

        st.markdown("---")

    quiz_ended = st.session_state.show_answers or st.session_state.timer_expired

    if not quiz_ended:
        if st.button("Submit Quiz", type="primary"):
            correct_count = 0
            for display_i, q in enumerate(shuffled_questions):
                orig_i = original_questions.index(q)
                user_idx = st.session_state.user_answers.get(display_i)
                if user_idx is None:
                    continue
                shuffle_map = st.session_state.option_shuffles.get(orig_i, [])
                user_orig_idx = shuffle_map[user_idx]
                if q["options"][user_orig_idx] == q["correct"]:
                    correct_count += 1
            st.session_state.score = (correct_count, len(shuffled_questions))
            st.session_state.show_answers = True
            st.rerun()
    else:
        if st.session_state.score:
            correct, total = st.session_state.score
            pct = correct / total * 100 if total > 0 else 0
            st.success(f"**Score: {correct}/{total}** ({pct:.0f}%)")

        if not st.session_state.reveal_correct_answers:
            if st.button("🔍 Show Correct Answers & Explanations"):
                st.session_state.reveal_correct_answers = True
                st.rerun()
        else:
            if st.button("Hide Correct Answers"):
                st.session_state.reveal_correct_answers = False
                st.rerun()

    if quiz_ended:
        if st.button("Restart this quiz"):
            keys_to_reset = [
                'user_answers', 'show_answers', 'score', 'quiz_start_time',
                'time_limit_minutes', 'timer_expired', 'reveal_correct_answers',
                'shuffled_questions', 'option_shuffles'
            ]
            for k in keys_to_reset:
                if k in st.session_state:
                    if isinstance(st.session_state[k], dict):
                        st.session_state[k].clear()
                    else:
                        st.session_state[k] = None
            st.rerun()

    if timer_running:
        time.sleep(1)
        st.rerun()

# ───────────────────────────────────────────────
# Main Layout
# ───────────────────────────────────────────────
st.title("NextGen Dev")

with st.sidebar:
    # Admin login
    if not is_admin():
        with st.expander("Admin Zone"):
            pwd = st.text_input("Admin password", type="password", key="admin_pwd")
            if st.button("Login as Admin"):
                if pwd.strip() == ADMIN_PASSWORD:
                    st.session_state.admin_logged_in = True
                    st.rerun()
                else:
                    st.error("Incorrect password")
    else:
        st.success("🔐 Admin mode")
        if st.button("Logout"):
            st.session_state.admin_logged_in = False
            st.rerun()

    st.divider()

    st.header("Filter by Department")
    categories = get_all_categories()

    selected = st.multiselect(
        "Select department(s)",
        options=categories,
        default=[],
        placeholder="Choose department to see quizzes",
        help="Quizzes appear only after selecting at least one department.",
        key="dept_filter"
    )

    st.session_state.selected_categories = selected

    st.header("Available Quizzes")

    if len(selected) == 0:
        st.info("Select at least one department above to view quizzes.")
    else:
        filtered = {
            f"{title} ({quiz.get('category', 'Uncategorized')})": title
            for title, quiz in st.session_state.quizzes.items()
            if quiz.get("category") in selected
        }

        if not filtered:
            st.info(f"No quizzes found for selected department{'s' if len(selected) > 1 else ''}.")
        else:
            st.caption(f"Found {len(filtered)} quiz{'zes' if len(filtered) != 1 else ''}")
            for label, real_title in sorted(filtered.items()):
                cols = st.columns([5, 1])
                with cols[0]:
                    is_active = real_title == st.session_state.selected_quiz
                    if st.button(label, key=f"sel_{real_title}",
                                 type="primary" if is_active else "secondary",
                                 use_container_width=True):
                        if not is_active:
                            st.session_state.selected_quiz = real_title
                            # Reset quiz state
                            for k in ['user_answers', 'show_answers', 'score',
                                      'quiz_start_time', 'time_limit_minutes',
                                      'timer_expired', 'reveal_correct_answers',
                                      'shuffled_questions', 'option_shuffles']:
                                if k in st.session_state:
                                    val = st.session_state[k]
                                    if isinstance(val, dict):
                                        val.clear()
                                    else:
                                        st.session_state[k] = None
                            st.rerun()
                with cols[1]:
                    if is_admin():
                        if st.button("🗑", key=f"del_{real_title}", help="Delete quiz"):
                            delete_quiz(real_title)
                            st.rerun()

    st.divider()

    if is_admin():
        submit_quiz_section()
    else:
        st.caption("Quiz creation is admin-only.")

# ── Main content ─────────────────────────────────────
if len(st.session_state.selected_categories) == 0:
    st.info("Please select at least one department in the sidebar to view available quizzes.")
elif st.session_state.selected_quiz:
    take_quiz_section()
else:
    st.info("Select a quiz from the filtered list in the sidebar.")
