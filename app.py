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
NOTES_DIR   = Path("notes")
QUIZZES_DIR.mkdir(exist_ok=True)
NOTES_DIR.mkdir(exist_ok=True)

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
    'selected_departments': [],
    'selected_subcategories': [],
    'admin_logged_in': False,
    'shuffled_questions': None,
    'option_shuffles': {},
    # Edit quiz
    'edit_quiz_title': None,
    'edit_quiz_data': None,
    # Notes
    'notes': {},
    'edit_note_id': None,
    'edit_note_data': None,
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

def delete_note(note_id):
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in note_id)
    path = NOTES_DIR / f"{safe}.json"
    if path.exists():
        path.unlink()
        st.session_state.notes.pop(note_id, None)
        st.success(f"Note **{note_id}** deleted.")
        st.rerun()

# ───────────────────────────────────────────────
# Load / Save
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

def load_notes():
    st.session_state.notes.clear()
    for file in NOTES_DIR.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                note_id = data.get("id", file.stem)
                st.session_state.notes[note_id] = data
        except Exception as e:
            st.warning(f"Could not load note {file.name}: {e}")

load_quizzes()
load_notes()

def save_quiz(title, data):
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
    path = QUIZZES_DIR / f"{safe_title}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    load_quizzes()

def save_note(note_id, data):
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in note_id)
    path = NOTES_DIR / f"{safe}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    load_notes()

# ───────────────────────────────────────────────
# Category & Subcategory helpers
# ───────────────────────────────────────────────
def get_all_departments():
    depts = set()
    for quiz in st.session_state.quizzes.values():
        dept = quiz.get("department") or quiz.get("category")
        if dept:
            depts.add(dept)
    return sorted(depts)

def get_subcategories_for_depts(selected_depts):
    subs = set()
    for quiz in st.session_state.quizzes.values():
        dept = quiz.get("department") or quiz.get("category")
        sub = quiz.get("subcategory") or quiz.get("topic")
        if dept in selected_depts and sub:
            subs.add(sub)
    return sorted(subs)

# ───────────────────────────────────────────────
# Add new quiz (admin only) — unchanged
# ───────────────────────────────────────────────
def submit_quiz_section():
    st.header("Add New Quiz (JSON)")
    tab1, tab2 = st.tabs(["Paste JSON", "Upload file"])
    all_depts = get_all_departments() or ["Uncategorized"]
    all_depts = sorted(set(all_depts + ["Uncategorized"]))

    with tab1:
        quiz_json = st.text_area("Quiz JSON", height=240, placeholder="Paste valid quiz JSON here...")
        quiz_title = st.text_input("Quiz title (optional)", key="new_quiz_title")
        department = st.selectbox(
            "Department / Category",
            options=all_depts + ["New department..."],
            key="new_quiz_dept_select"
        )
        new_dept = ""
        if department == "New department...":
            new_dept = st.text_input("Enter new department name", key="new_dept_input").strip()
        subcategory = st.text_input("Sub-category / Topic (optional)", key="new_quiz_subcat").strip()
        final_dept = new_dept or department

        if st.button("Submit JSON", type="primary", key="submit_json"):
            if not quiz_json.strip():
                st.error("Please paste some JSON.")
                return
            try:
                data = json.loads(quiz_json)
                title = quiz_title.strip() or data.get("quiz_title") or f"Quiz_{len(st.session_state.quizzes)+1}"
                if final_dept and final_dept != "Uncategorized":
                    data["department"] = final_dept
                if subcategory:
                    data["subcategory"] = subcategory
                if title in st.session_state.quizzes:
                    if st.checkbox("Overwrite existing quiz?", key="ow_confirm"):
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
        if uploaded and st.button("Process uploaded file", key="submit_file"):
            try:
                data = json.load(uploaded)
                title = data.get("quiz_title", uploaded.name.replace(".json", ""))
                if not data.get("department"):
                    data["department"] = "Uncategorized"
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
# Edit quiz form (admin only) — unchanged
# ───────────────────────────────────────────────
def edit_quiz_form():
    if not st.session_state.get('edit_quiz_title'):
        return

    title = st.session_state.edit_quiz_title
    data = st.session_state.edit_quiz_data

    st.subheader(f"Editing Quiz: {title}")

    edited_title = st.text_input("Quiz Title", value=data.get("quiz_title", title), key="edit_title_input")

    all_depts = get_all_departments() or ["Uncategorized"]
    all_depts = sorted(set(all_depts + ["Uncategorized"]))
    current_dept = data.get("department") or data.get("category", "Uncategorized")
    dept_index = all_depts.index(current_dept) if current_dept in all_depts else 0

    department = st.selectbox(
        "Department / Category",
        options=all_depts + ["New department..."],
        index=dept_index,
        key="edit_dept_select"
    )

    new_dept = ""
    if department == "New department...":
        new_dept = st.text_input("New department name", key="edit_new_dept_input").strip()

    final_dept = new_dept or department

    current_subcat = data.get("subcategory", "")
    subcategory = st.text_input("Sub-category / Topic (optional)", value=current_subcat, key="edit_subcat_input")

    current_json = json.dumps(data, indent=2, ensure_ascii=False)
    edited_json = st.text_area("Quiz JSON (edit carefully)", value=current_json, height=400, key="edit_json_area")

    col_save, col_cancel = st.columns(2)
    with col_save:
        if st.button("💾 Save Changes", type="primary"):
            try:
                new_data = json.loads(edited_json)
                new_data["quiz_title"] = edited_title.strip() or title
                if final_dept and final_dept != "Uncategorized":
                    new_data["department"] = final_dept
                else:
                    new_data.pop("department", None)
                if subcategory.strip():
                    new_data["subcategory"] = subcategory.strip()
                else:
                    new_data.pop("subcategory", None)

                save_quiz(edited_title.strip() or title, new_data)

                if edited_title.strip() != title:
                    old_safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
                    old_path = QUIZZES_DIR / f"{old_safe}.json"
                    if old_path.exists():
                        old_path.unlink()

                st.success(f"Quiz **{edited_title or title}** updated successfully!")
                st.session_state.edit_quiz_title = None
                st.session_state.edit_quiz_data = None
                st.rerun()

            except json.JSONDecodeError:
                st.error("Invalid JSON format — please fix the syntax.")
            except Exception as e:
                st.error(f"Could not save changes: {e}")

    with col_cancel:
        if st.button("Cancel / Close editor"):
            st.session_state.edit_quiz_title = None
            st.session_state.edit_quiz_data = None
            st.rerun()

# ───────────────────────────────────────────────
# Take quiz section — unchanged
# ───────────────────────────────────────────────
def take_quiz_section():
    quiz = st.session_state.quizzes[st.session_state.selected_quiz]
    title = quiz.get('quiz_title', st.session_state.selected_quiz)
    dept = quiz.get('department', quiz.get('category', 'Uncategorized'))
    subcat = quiz.get('subcategory', '')
    original_questions = quiz.get("questions", [])

    st.header(f"Quiz: {title}")
    st.caption(f"Department: **{dept}**" + (f" • Topic: **{subcat}**" if subcat else ""))

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
            if not opts: continue
            opt_idx = list(range(len(opts)))
            random.shuffle(opt_idx)
            st.session_state.option_shuffles[orig_i] = opt_idx

    shuffled_questions = st.session_state.shuffled_questions or original_questions

    timer_placeholder = st.empty()

    if st.session_state.quiz_start_time is None and not st.session_state.show_answers:
        st.info("Optional: choose a time limit for this attempt")
        time_options = [
            "No timer",
            "5 minutes", "10 minutes", "15 minutes", "20 minutes",
            "25 minutes", "30 minutes", "40 minutes", "50 minutes", "60 minutes"
        ]
        selected_time = st.selectbox(
            "Time limit",
            options=time_options,
            index=0,
            key="time_limit_select"
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
                timer_placeholder.caption("⏳ No time limit")
            timer_running = True

    for i, q in enumerate(shuffled_questions):
        st.subheader(f"Q{i+1}. {q.get('question', '—')}")
        orig_idx = original_questions.index(q)
        opts_orig = q.get("options", [])
        correct = q.get("correct")

        if not opts_orig or correct not in opts_orig:
            st.error(f"Q{i+1}: Invalid question data")
            continue

        shuffle_map = st.session_state.option_shuffles.get(orig_idx, list(range(len(opts_orig))))
        opts_shuffled = [opts_orig[j] for j in shuffle_map]

        key = f"ans_{i}"

        if not st.session_state.show_answers and not st.session_state.timer_expired:
            choice = st.radio("Your answer:", opts_shuffled,
                              index=st.session_state.user_answers.get(i, None),
                              key=key, horizontal=False)
            if choice is not None:
                st.session_state.user_answers[i] = opts_shuffled.index(choice)
        else:
            user_idx = st.session_state.user_answers.get(i, None)
            correct_shuf_idx = shuffle_map.index(opts_orig.index(correct))

            st.radio("Your selection:", opts_shuffled,
                     index=user_idx if user_idx is not None else 0,
                     key=f"rev_{key}", disabled=True, horizontal=True)

            if st.session_state.reveal_correct_answers:
                if user_idx is None:
                    st.warning("Skipped")
                    st.markdown(f"**Correct:** {correct}")
                elif user_idx == correct_shuf_idx:
                    st.success("Correct ✓")
                else:
                    st.error("Incorrect ✗")
                    st.markdown(f"**Correct:** {correct}")
                if expl := q.get("explanation", ""):
                    with st.expander("Explanation"):
                        st.write(expl)

        st.markdown("---")

    quiz_ended = st.session_state.show_answers or st.session_state.timer_expired

    if not quiz_ended:
        if st.button("Submit Quiz", type="primary"):
            correct_count = 0
            for i, q in enumerate(shuffled_questions):
                orig_i = original_questions.index(q)
                u_idx = st.session_state.user_answers.get(i)
                if u_idx is None: continue
                map_ = st.session_state.option_shuffles.get(orig_i, [])
                orig_choice_idx = map_[u_idx]
                if q["options"][orig_choice_idx] == q["correct"]:
                    correct_count += 1
            st.session_state.score = (correct_count, len(shuffled_questions))
            st.session_state.show_answers = True
            st.rerun()
    else:
        if st.session_state.score:
            c, t = st.session_state.score
            pct = c / t * 100 if t > 0 else 0
            st.success(f"**Score: {c}/{t}** ({pct:.0f}%)")

        if not st.session_state.reveal_correct_answers:
            if st.button("Show correct answers & explanations"):
                st.session_state.reveal_correct_answers = True
                st.rerun()
        else:
            if st.button("Hide correct answers"):
                st.session_state.reveal_correct_answers = False
                st.rerun()

    if quiz_ended:
        if st.button("Restart this quiz"):
            for k in ['user_answers','show_answers','score','quiz_start_time',
                      'time_limit_minutes','timer_expired','reveal_correct_answers',
                      'shuffled_questions','option_shuffles']:
                if k in st.session_state:
                    v = st.session_state[k]
                    if isinstance(v, dict):
                        v.clear()
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
    if not is_admin():
        with st.expander("Admin Zone"):
            pwd = st.text_input("Admin password", type="password")
            if st.button("Login as Admin"):
                if pwd.strip() == ADMIN_PASSWORD:
                    st.session_state.admin_logged_in = True
                    st.rerun()
                else:
                    st.error("Wrong password")
    else:
        st.success("Admin mode active")
        if st.button("Logout"):
            st.session_state.admin_logged_in = False
            st.rerun()

    st.divider()

    st.header("Filter Quizzes")

    depts = get_all_departments()

    selected_depts = st.multiselect(
        "Department",
        options=depts,
        default=[],
        placeholder="Select department(s)",
        key="dept_multi"
    )

    selected_subcats = []
    if selected_depts:
        possible_subs = get_subcategories_for_depts(selected_depts)
        if possible_subs:
            selected_subcats = st.multiselect(
                "Topic / Sub-category",
                options=possible_subs,
                default=[],
                placeholder="All topics (optional)",
                key="subcat_multi"
            )
        else:
            st.caption("No sub-categories defined for selected department(s)")

    st.session_state.selected_departments = selected_depts
    st.session_state.selected_subcategories = selected_subcats

    # ── New section: Key Notes (Admin only) ────────────────────────
    if is_admin():
        st.divider()
        st.header("Key Notes")
        with st.expander("➕ Add / Edit Key Note", expanded=False):
            note_title = st.text_input("Note Title", key="new_note_title")
            note_dept = st.selectbox(
                "Department",
                options=[""] + get_all_departments(),
                key="new_note_dept"
            )
            note_subcat = st.text_input("Sub-category (optional)", key="new_note_subcat")
            note_content = st.text_area(
                "Content (paste formatted text, markdown works)",
                height=160,
                key="new_note_content"
            )

            if st.button("Save Note", type="primary"):
                if not note_title.strip() or not note_content.strip():
                    st.error("Title and content are required.")
                else:
                    note_id = note_title.strip()
                    data = {
                        "id": note_id,
                        "title": note_title.strip(),
                        "department": note_dept if note_dept else None,
                        "subcategory": note_subcat.strip() or None,
                        "content": note_content.strip(),
                        "created": datetime.now().isoformat(),
                        "last_updated": datetime.now().isoformat(),
                    }
                    save_note(note_id, data)
                    st.success("Note saved!")
                    st.rerun()

    st.header("Available Quizzes")
    # ... (your existing quiz listing code remains unchanged) ...

    st.divider()

    if is_admin():
        submit_quiz_section()
    else:
        st.caption("Quiz creation restricted to admin.")

# ── Main content ────────────────────────────────────────
if not st.session_state.selected_departments:
    st.info("Select at least one department from the sidebar to view available quizzes.")
elif st.session_state.selected_quiz:
    take_quiz_section()
else:
    st.subheader("Key Notes & Summaries")

    filtered_notes = []
    for note in st.session_state.notes.values():
        dept_match = not st.session_state.selected_departments or \
                     (note.get("department") in st.session_state.selected_departments)
        sub_match = not st.session_state.selected_subcategories or \
                    (note.get("subcategory") and note.get("subcategory") in st.session_state.selected_subcategories)

        if dept_match and sub_match:
            filtered_notes.append(note)

    if not filtered_notes:
        st.info("No key notes available for the current department / topic selection.")
    else:
        for note in sorted(filtered_notes, key=lambda x: x.get("title", "")):
            with st.expander(note["title"]):
                if note.get("department"):
                    st.caption(f"Department: **{note['department']}**" +
                               (f" • Topic: **{note['subcategory']}**" if note.get("subcategory") else ""))
                # Preserve formatting (bold, lists, code, etc.)
                st.markdown(note["content"], unsafe_allow_html=True)
                st.caption(f"Last updated: {note.get('last_updated', '—')[:19]}")

                if is_admin():
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✏️ Edit", key=f"edit_note_{note['id']}"):
                            st.session_state.edit_note_id = note['id']
                            st.session_state.edit_note_data = note.copy()
                            st.rerun()
                    with col2:
                        if st.button("🗑 Delete", key=f"del_note_{note['id']}"):
                            delete_note(note['id'])
                            st.rerun()

# ── Edit quiz form ──────────────────────────────────────
if is_admin() and st.session_state.get('edit_quiz_title'):
    edit_quiz_form()

# ── Edit note form (simple version) ─────────────────────
if is_admin() and st.session_state.get('edit_note_id'):
    nid = st.session_state.edit_note_id
    data = st.session_state.edit_note_data

    st.subheader(f"Edit Note: {data.get('title')}")

    edited_title = st.text_input("Title", value=data.get("title", ""))
    edited_dept = st.selectbox("Department", options=[""] + get_all_departments(),
                               index=0)
    edited_subcat = st.text_input("Sub-category (optional)", value=data.get("subcategory", ""))
    edited_content = st.text_area("Content", value=data.get("content", ""), height=300)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Save Changes", type="primary"):
            if not edited_title.strip() or not edited_content.strip():
                st.error("Title and content required.")
            else:
                new_data = {
                    "id": edited_title.strip(),
                    "title": edited_title.strip(),
                    "department": edited_dept if edited_dept else None,
                    "subcategory": edited_subcat.strip() or None,
                    "content": edited_content.strip(),
                    "created": data.get("created"),
                    "last_updated": datetime.now().isoformat(),
                }
                save_note(edited_title.strip(), new_data)
                if edited_title.strip() != nid:
                    delete_note(nid)
                st.success("Note updated!")
                st.session_state.edit_note_id = None
                st.session_state.edit_note_data = None
                st.rerun()
    with c2:
        if st.button("Cancel"):
            st.session_state.edit_note_id = None
            st.session_state.edit_note_data = None
            st.rerun()
