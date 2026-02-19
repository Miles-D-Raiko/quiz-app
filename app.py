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
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
    path = QUIZZES_DIR / f"{safe}.json"
    if path.exists():
        path.unlink()
        st.session_state.quizzes.pop(title, None)
        st.success(f"Quiz **{title}** deleted.")
        if st.session_state.selected_quiz == title:
            st.session_state.selected_quiz = None
        st.rerun()

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
            st.warning(f"Could not load quiz {file.name}: {e}")

def load_notes():
    st.session_state.notes.clear()
    for file in NOTES_DIR.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                nid = data.get("id", file.stem)
                st.session_state.notes[nid] = data
        except Exception as e:
            st.warning(f"Could not load note {file.name}: {e}")

load_quizzes()
load_notes()

def save_quiz(title, data):
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
    path = QUIZZES_DIR / f"{safe}.json"
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
# Category helpers
# ───────────────────────────────────────────────
def get_all_departments():
    depts = set()
    for quiz in st.session_state.quizzes.values():
        d = quiz.get("department") or quiz.get("category")
        if d:
            depts.add(d)
    return sorted(depts)

def get_subcategories_for_depts(selected_depts):
    subs = set()
    for quiz in st.session_state.quizzes.values():
        d = quiz.get("department") or quiz.get("category")
        s = quiz.get("subcategory")
        if d in selected_depts and s:
            subs.add(s)
    return sorted(subs)

# ───────────────────────────────────────────────
# Add / Edit Quiz (admin)
# ───────────────────────────────────────────────
def submit_quiz_section():
    st.header("Add New Quiz")
    tab1, tab2 = st.tabs(["Paste JSON", "Upload file"])
    all_depts = sorted(set(get_all_departments() + ["Uncategorized"]))

    with tab1:
        quiz_json   = st.text_area("Quiz JSON", height=220)
        quiz_title  = st.text_input("Title (optional)")
        department  = st.selectbox("Department", options=all_depts + ["New department..."])
        new_dept    = st.text_input("New department name") if department == "New department..." else ""
        subcategory = st.text_input("Sub-category / Topic (optional)")
        final_dept  = new_dept.strip() or department

        if st.button("Save Quiz", type="primary"):
            if not quiz_json.strip():
                st.error("Paste JSON content")
                return
            try:
                data = json.loads(quiz_json)
                title = quiz_title.strip() or data.get("quiz_title") or f"Quiz_{len(st.session_state.quizzes)+1}"
                if final_dept != "Uncategorized":
                    data["department"] = final_dept
                if subcategory.strip():
                    data["subcategory"] = subcategory.strip()
                save_quiz(title, data)
                st.success(f"Saved: **{title}**")
            except json.JSONDecodeError:
                st.error("Invalid JSON")

    with tab2:
        uploaded = st.file_uploader("Upload JSON", type="json")
        if uploaded and st.button("Process file"):
            try:
                data = json.load(uploaded)
                title = data.get("quiz_title", uploaded.name.replace(".json",""))
                if not data.get("department"):
                    data["department"] = "Uncategorized"
                save_quiz(title, data)
                st.success(f"Added: **{title}**")
            except Exception as e:
                st.error(str(e))

def edit_quiz_form():
    if not st.session_state.get('edit_quiz_title'):
        return

    title = st.session_state.edit_quiz_title
    data  = st.session_state.edit_quiz_data

    st.subheader(f"Edit Quiz: {title}")

    edited_title = st.text_input("Title", value=data.get("quiz_title", title))
    current_dept = data.get("department") or data.get("category", "Uncategorized")
    all_depts = sorted(set(get_all_departments() + ["Uncategorized"]))
    dept_idx = all_depts.index(current_dept) if current_dept in all_depts else 0
    department = st.selectbox("Department", options=all_depts + ["New department..."], index=dept_idx)

    new_dept = st.text_input("New department name") if department == "New department..." else ""
    final_dept = new_dept.strip() or department

    subcategory = st.text_input("Sub-category / Topic (optional)", value=data.get("subcategory", ""))

    edited_json = st.text_area("JSON content", value=json.dumps(data, indent=2), height=400)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Save Changes", type="primary"):
            try:
                new_data = json.loads(edited_json)
                new_data["quiz_title"] = edited_title.strip() or title
                if final_dept != "Uncategorized":
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
                    (QUIZZES_DIR / f"{old_safe}.json").unlink(missing_ok=True)

                st.success("Quiz updated")
                st.session_state.edit_quiz_title = None
                st.session_state.edit_quiz_data = None
                st.rerun()
            except json.JSONDecodeError:
                st.error("Invalid JSON")
            except Exception as e:
                st.error(str(e))

    with c2:
        if st.button("Cancel"):
            st.session_state.edit_quiz_title = None
            st.session_state.edit_quiz_data = None
            st.rerun()

# ───────────────────────────────────────────────
# Keypoint Notes (Admin)
# ───────────────────────────────────────────────
def edit_note_form():
    if not st.session_state.get('edit_note_id'):
        return

    nid  = st.session_state.edit_note_id
    data = st.session_state.edit_note_data

    st.subheader(f"Edit Note: {data.get('title')}")

    title   = st.text_input("Title", value=data.get("title",""))
    dept    = st.selectbox("Department", options=[""] + get_all_departments(), index=0)
    subcat  = st.text_input("Sub-category (optional)", value=data.get("subcategory",""))
    content = st.text_area("Content (markdown ok)", value=data.get("content",""), height=300)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Save Changes", type="primary"):
            if not title.strip() or not content.strip():
                st.error("Title & content required")
                return
            new_data = {
                "id": title.strip(),
                "title": title.strip(),
                "department": dept if dept else None,
                "subcategory": subcat.strip() or None,
                "content": content.strip(),
                "created": data.get("created"),
                "last_updated": datetime.now().isoformat(),
            }
            save_note(title.strip(), new_data)
            if title.strip() != nid:
                delete_note(nid)
            st.success("Note updated")
            st.session_state.edit_note_id = None
            st.session_state.edit_note_data = None
            st.rerun()

    with c2:
        if st.button("Cancel"):
            st.session_state.edit_note_id = None
            st.session_state.edit_note_data = None
            st.rerun()

# ───────────────────────────────────────────────
# Take Quiz (unchanged – abbreviated for brevity)
# ───────────────────────────────────────────────
def take_quiz_section():
    # ... your existing take_quiz_section code here ...
    # (keeping it out of this snippet to save space – copy from your previous version)
    st.info("Quiz section (paste your existing take_quiz_section code here)")
    pass

# ───────────────────────────────────────────────
# Main App
# ───────────────────────────────────────────────
st.title("NextGen Dev")

with st.sidebar:
    if not is_admin():
        with st.expander("Admin Zone"):
            pwd = st.text_input("Password", type="password")
            if st.button("Login"):
                if pwd == ADMIN_PASSWORD:
                    st.session_state.admin_logged_in = True
                    st.rerun()
                else:
                    st.error("Wrong password")
    else:
        st.success("Admin mode")
        if st.button("Logout"):
            st.session_state.admin_logged_in = False
            st.rerun()

    st.divider()

    st.header("Filter")
    depts = get_all_departments()
    selected_depts = st.multiselect("Department", depts, [], key="depts")
    selected_subcats = []
    if selected_depts:
        subs = get_subcategories_for_depts(selected_depts)
        if subs:
            selected_subcats = st.multiselect("Topic", subs, [], key="subs")

    st.session_state.selected_departments   = selected_depts
    st.session_state.selected_subcategories = selected_subcats

    st.header("Quizzes")
    if not selected_depts:
        st.info("Select department(s)")
    else:
        filtered_quizzes = {}
        for t, q in st.session_state.quizzes.items():
            d = q.get("department") or q.get("category", "Uncategorized")
            s = q.get("subcategory", "")
            if d in selected_depts and (not selected_subcats or s in selected_subcats):
                label = t
                if s: label += f" ({s})"
                elif d != "Uncategorized": label += f" ({d})"
                filtered_quizzes[label] = t

        if not filtered_quizzes:
            st.info("No matching quizzes")
        else:
            for label, t in sorted(filtered_quizzes.items()):
                cols = st.columns([5,1,1])
                cols[0].button(label, key=f"sel_quiz_{t}",
                               type="primary" if t == st.session_state.selected_quiz else "secondary",
                               use_container_width=True,
                               on_click=lambda x=t: st.session_state.update(selected_quiz=x))
                if is_admin():
                    cols[1].button("✏️", key=f"editq_{t}", help="Edit", on_click=lambda x=t: [
                        st.session_state.update(edit_quiz_title=x, edit_quiz_data=st.session_state.quizzes[x].copy())
                    ])
                    cols[2].button("🗑", key=f"delq_{t}", help="Delete", on_click=lambda x=t: delete_quiz(x))

    if is_admin():
        st.divider()
        with st.expander("Manage Notes"):
            st.subheader("New Note")
            n_title   = st.text_input("Title")
            n_dept    = st.selectbox("Department", [""] + get_all_departments())
            n_subcat  = st.text_input("Sub-category (opt)")
            n_content = st.text_area("Content", height=140)

            if st.button("Save Note"):
                if n_title.strip() and n_content.strip():
                    nid = n_title.strip()
                    data = {
                        "id": nid,
                        "title": nid,
                        "department": n_dept if n_dept else None,
                        "subcategory": n_subcat.strip() or None,
                        "content": n_content.strip(),
                        "created": datetime.now().isoformat(),
                        "last_updated": datetime.now().isoformat(),
                    }
                    save_note(nid, data)
                    st.success("Note saved")
                    st.rerun()
                else:
                    st.error("Title & content required")

# ── Main content ────────────────────────────────────────
if not st.session_state.selected_departments:
    st.info("Select department(s) in sidebar")
elif st.session_state.selected_quiz:
    take_quiz_section()
else:
    st.subheader("Keypoint Notes")

    notes_shown = []
    for n in st.session_state.notes.values():
        d_match = not selected_depts or n.get("department") in selected_depts
        s_match = not selected_subcats or (n.get("subcategory") and n.get("subcategory") in selected_subcats)
        if d_match and s_match:
            notes_shown.append(n)

    if not notes_shown:
        st.info("No notes for current selection")
    else:
        for note in sorted(notes_shown, key=lambda x: x["title"]):
            with st.expander(note["title"]):
                if note.get("department"):
                    st.caption(f"**{note['department']}**" + (f" • {note['subcategory']}" if note.get("subcategory") else ""))
                st.markdown(note["content"])
                st.caption(f"Updated: {note.get('last_updated','—')[:19]}")

                if is_admin():
                    c1, c2 = st.columns(2)
                    c1.button("✏️ Edit", key=f"edn_{note['id']}", on_click=lambda x=note["id"]: st.session_state.update(
                        edit_note_id=x, edit_note_data=st.session_state.notes[x].copy()))
                    c2.button("🗑 Delete", key=f"dln_{note['id']}", on_click=lambda x=note["id"]: delete_note(x))

# ── Edit forms ──────────────────────────────────────────
if is_admin():
    if st.session_state.get('edit_quiz_title'):
        edit_quiz_form()
    if st.session_state.get('edit_note_id'):
        edit_note_form()
