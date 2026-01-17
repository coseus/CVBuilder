import streamlit as st
from components.list_editor import render_bullet_list

DEFAULT_CATEGORIES = [
    ("Competențe sociale", "competente_sociale"),
    ("Competențe organizaționale", "competente_organizatorice"),
    ("Competențe tehnice", "competente_tehnice"),
    ("Competențe utilizare calculator", "competente_calculator"),
    ("Competențe artistice", "competente_artistice"),
    ("Alte competențe", "alte_competente"),
]

def _migrate_legacy(cv):
    # If legacy fields exist and new structure empty, migrate into sections
    if cv.get('aptitudini_sections'):
        return
    sections = []
    for title, key in DEFAULT_CATEGORIES:
        val = (cv.get(key) or "").strip()
        if not val:
            continue
        bullets = []
        for line in val.splitlines():
            s = line.strip().lstrip('-•* ').strip()
            if s:
                bullets.append(s)
        if bullets:
            sections.append({"category": title, "items": bullets})
    cv['aptitudini_sections'] = sections

def render_aptitudini_sections(cv, prefix=""):
    st.subheader("Aptitudini și competențe personale (editabile)")
    _migrate_legacy(cv)

    # Add new category
    with st.form(key=f"{prefix}add_skill_cat", clear_on_submit=True):
        cat = st.text_input("Categorie nouă", key=f"{prefix}new_cat", placeholder="Ex: Competențe de comunicare")
        add = st.form_submit_button("Adaugă categorie")
        if add and cat.strip():
            cv['aptitudini_sections'].append({"category": cat.strip(), "items": []})
            st.rerun()

    if not cv.get('aptitudini_sections'):
        st.info("Nu ai adăugat încă secțiuni.")
        return

    for i, sec in enumerate(list(cv['aptitudini_sections'])):
        title = sec.get("category") or f"Categorie {i+1}"
        with st.expander(title, expanded=False):
            cols = st.columns([1,1,1,4])
            with cols[0]:
                if st.button("⬆️ Sus", key=f"{prefix}apt_up_{i}", disabled=(i==0)):
                    cv['aptitudini_sections'][i-1], cv['aptitudini_sections'][i] = cv['aptitudini_sections'][i], cv['aptitudini_sections'][i-1]
                    st.rerun()
            with cols[1]:
                if st.button("⬇️ Jos", key=f"{prefix}apt_down_{i}", disabled=(i==len(cv['aptitudini_sections'])-1)):
                    cv['aptitudini_sections'][i+1], cv['aptitudini_sections'][i] = cv['aptitudini_sections'][i], cv['aptitudini_sections'][i+1]
                    st.rerun()
            with cols[2]:
                if st.button("🗑️ Șterge", key=f"{prefix}apt_del_{i}"):
                    cv['aptitudini_sections'].pop(i)
                    st.rerun()
            with cols[3]:
                cv['aptitudini_sections'][i]['category'] = st.text_input("Titlu categorie", value=title, key=f"{prefix}apt_title_{i}")

            bullets = cv['aptitudini_sections'][i].get("items", [])
            bullets = render_bullet_list(
                label="Bullets",
                bullets=bullets,
                key_prefix=f"{prefix}apt_bul_{i}",
                help_text="Recomandat: bullets scurte, cu impact/rezultate."
            )
            cv['aptitudini_sections'][i]["items"] = bullets

    # Keep legacy fields in sync (optional): write back joined text
    for title, key in DEFAULT_CATEGORIES:
        # find matching section
        match = next((s for s in cv['aptitudini_sections'] if s.get('category')==title), None)
        if match:
            cv[key] = "\n".join([f"- {b}" for b in match.get("items", [])])
