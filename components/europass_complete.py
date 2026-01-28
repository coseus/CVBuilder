import streamlit as st


def render_europass_complete(cv: dict, key_prefix: str = "ep"):
    """
    Full Europass editor:
    - Personal info (shared keys)
    - Extra fields add/edit/delete
    - Education add/edit/delete
    - Languages (full Europass keys) add/edit/delete
    - Aptitudini sections add/edit/delete
    - Driving license
    """
    if not isinstance(cv, dict):
        st.error("CV invalid.")
        return

    # Defaults
    cv.setdefault("personal_info_extra", [])
    cv.setdefault("educatie", [])
    cv.setdefault("limba_materna", "")
    cv.setdefault("limbi_straine", [])
    cv.setdefault("aptitudini_sections", [])
    cv.setdefault("permis_conducere", "")

    # --- Personal info ---
    st.subheader("Personal information (Europass)")
    c1, c2 = st.columns(2)
    with c1:
        cv["nume_prenume"] = st.text_input("Full name", value=cv.get("nume_prenume", ""), key=f"{key_prefix}_name")
        cv["email"] = st.text_input("Email", value=cv.get("email", ""), key=f"{key_prefix}_email")
        cv["linkedin"] = st.text_input("LinkedIn", value=cv.get("linkedin", ""), key=f"{key_prefix}_linkedin")
    with c2:
        cv["telefon"] = st.text_input("Phone", value=cv.get("telefon", ""), key=f"{key_prefix}_phone")
        cv["adresa"] = st.text_input("Address / Location", value=cv.get("adresa", ""), key=f"{key_prefix}_addr")
        cv["website"] = st.text_input("Website", value=cv.get("website", ""), key=f"{key_prefix}_website")

    # Extra fields
    st.markdown("### Extra fields (edit/add/delete)")
    extras = cv["personal_info_extra"]
    if not isinstance(extras, list):
        extras = []
        cv["personal_info_extra"] = extras

    for i in range(len(extras)):
        row = extras[i] if isinstance(extras[i], dict) else {"label": "", "value": ""}
        row.setdefault("label", "")
        row.setdefault("value", "")

        colA, colB, colC = st.columns([1.1, 1.6, 0.4])
        with colA:
            row["label"] = st.text_input("Label", value=row.get("label", ""), key=f"{key_prefix}_extra_{i}_label")
        with colB:
            row["value"] = st.text_input("Value", value=row.get("value", ""), key=f"{key_prefix}_extra_{i}_value")
        with colC:
            if st.button("🗑", key=f"{key_prefix}_extra_{i}_del"):
                cv["personal_info_extra"].pop(i)
                st.rerun()
        cv["personal_info_extra"][i] = row

    with st.expander("➕ Add extra field", expanded=False):
        nl = st.text_input("Label", key=f"{key_prefix}_extra_new_label")
        nv = st.text_input("Value", key=f"{key_prefix}_extra_new_value")
        if st.button("Add", key=f"{key_prefix}_extra_add"):
            if nl.strip() and nv.strip():
                cv["personal_info_extra"].append({"label": nl.strip(), "value": nv.strip()})
                st.rerun()
            else:
                st.warning("Fill in the label and value.")

    st.markdown("---")

    # --- Education ---
    st.subheader("Education and training (edit/add/delete)")
    with st.expander("➕ Add education", expanded=False):
        perioada = st.text_input("Period", key=f"{key_prefix}_edu_add_perioada")
        titlu = st.text_input("Title (diploma/specialization)", key=f"{key_prefix}_edu_add_titlu")
        org = st.text_input("Institution", key=f"{key_prefix}_edu_add_org")
        loc = st.text_input("Location", key=f"{key_prefix}_edu_add_loc")
        desc = st.text_area("Description (optional)", key=f"{key_prefix}_edu_add_desc", height=90)
        if st.button("Add education", key=f"{key_prefix}_edu_add_btn"):
            cv["educatie"].append({"perioada": perioada, "titlu": titlu, "organizatie": org, "locatie": loc, "descriere": desc})
            st.rerun()

    for i in range(len(cv["educatie"])):
        ed = cv["educatie"][i]
        ed.setdefault("perioada", "")
        ed.setdefault("titlu", "")
        ed.setdefault("organizatie", "")
        ed.setdefault("locatie", "")
        ed.setdefault("descriere", "")

        with st.expander(f"Education #{i+1}: {ed.get('titlu') or '(fără titlu)'}", expanded=False):
            ed["perioada"] = st.text_input("Period", value=ed.get("perioada", ""), key=f"{key_prefix}_edu_{i}_per")
            ed["titlu"] = st.text_input("Title", value=ed.get("titlu", ""), key=f"{key_prefix}_edu_{i}_titlu")
            ed["organizatie"] = st.text_input("Institution", value=ed.get("organizatie", ""), key=f"{key_prefix}_edu_{i}_org")
            ed["locatie"] = st.text_input("Location", value=ed.get("locatie", ""), key=f"{key_prefix}_edu_{i}_loc")
            ed["descriere"] = st.text_area("Description", value=ed.get("descriere", ""), key=f"{key_prefix}_edu_{i}_desc", height=90)

            if st.button("Delete", key=f"{key_prefix}_edu_{i}_del"):
                cv["educatie"].pop(i)
                st.rerun()

    st.markdown("---")

    # --- Languages ---
    st.subheader("Language skills (Europass)")
    cv["limba_materna"] = st.text_input("Native language", value=cv.get("limba_materna", ""), key=f"{key_prefix}_mother")

    with st.expander("➕ Add language", expanded=False):
        limba = st.text_input("Language", key=f"{key_prefix}_lang_add_name")
        nivel = st.text_input("Level (ex: B1/B2/Intermediate)", key=f"{key_prefix}_lang_add_level")
        if st.button("Add language", key=f"{key_prefix}_lang_add_btn"):
            item = {
                "limba": limba.strip(),
                "nivel": nivel.strip(),
                "ascultare": nivel.strip(),
                "citire": nivel.strip(),
                "interactiune": nivel.strip(),
                "exprimare": nivel.strip(),
                "scriere": nivel.strip(),
            }
            cv["limbi_straine"].append(item)
            st.rerun()

    for i in range(len(cv["limbi_straine"])):
        l = cv["limbi_straine"][i]
        for k in ["limba", "nivel", "ascultare", "citire", "interactiune", "exprimare", "scriere"]:
            l.setdefault(k, "")

        with st.expander(f"{l.get('limba') or '(fără nume)'}", expanded=False):
            l["limba"] = st.text_input("Language", value=l.get("limba", ""), key=f"{key_prefix}_lang_{i}_name")
            l["nivel"] = st.text_input("Nivel (rapid)", value=l.get("nivel", ""), key=f"{key_prefix}_lang_{i}_lvl")

            c1, c2, c3 = st.columns(3)
            with c1:
                l["ascultare"] = st.text_input("Listening", value=l.get("ascultare", ""), key=f"{key_prefix}_lang_{i}_asc")
                l["citire"] = st.text_input("Reading", value=l.get("citire", ""), key=f"{key_prefix}_lang_{i}_cit")
            with c2:
                l["interactiune"] = st.text_input("Interaction", value=l.get("interactiune", ""), key=f"{key_prefix}_lang_{i}_int")
                l["exprimare"] = st.text_input("Expression", value=l.get("exprimare", ""), key=f"{key_prefix}_lang_{i}_exp")
            with c3:
                l["scriere"] = st.text_input("Writing", value=l.get("scriere", ""), key=f"{key_prefix}_lang_{i}_scr")
                if st.button("Aplică nivel rapid la toate", key=f"{key_prefix}_lang_{i}_apply"):
                    for kk in ["ascultare", "citire", "interactiune", "exprimare", "scriere"]:
                        l[kk] = l.get("nivel", "")
                    st.rerun()

            if st.button("Delete", key=f"{key_prefix}_lang_{i}_del"):
                cv["limbi_straine"].pop(i)
                st.rerun()

    st.markdown("---")

    # --- Aptitudini / competențe personale ---
    st.subheader("Personal skills and competencies (edit/add/delete)")
    secs = cv["aptitudini_sections"]
    if not isinstance(secs, list):
        secs = []
        cv["aptitudini_sections"] = secs

    with st.expander("➕ Add skills section", expanded=False):
        cat = st.text_input("Category", key=f"{key_prefix}_apt_add_cat")
        items = st.text_area("Items (1 pe linie)", key=f"{key_prefix}_apt_add_items", height=120)
        if st.button("Add section", key=f"{key_prefix}_apt_add_btn"):
            li = [x.strip().lstrip("-•* ").strip() for x in items.splitlines() if x.strip()]
            cv["aptitudini_sections"].append({"category": cat.strip(), "items": li})
            st.rerun()

    for i in range(len(cv["aptitudini_sections"])):
        sec = cv["aptitudini_sections"][i]
        sec.setdefault("category", "")
        sec.setdefault("items", [])

        with st.expander(f"Section #{i+1}: {sec.get('category') or '(fără categorie)'}", expanded=False):
            sec["category"] = st.text_input("Category", value=sec.get("category", ""), key=f"{key_prefix}_apt_{i}_cat")
            items_text = "\n".join(sec.get("items", []) if isinstance(sec.get("items", []), list) else [])
            items_text = st.text_area("Items (1 pe linie)", value=items_text, key=f"{key_prefix}_apt_{i}_items", height=120)
            sec["items"] = [x.strip().lstrip("-•* ").strip() for x in items_text.splitlines() if x.strip()]

            if st.button("Delete section", key=f"{key_prefix}_apt_{i}_del"):
                cv["aptitudini_sections"].pop(i)
                st.rerun()

    st.markdown("---")

    # --- Driving license ---
    st.subheader("Driving license")
    cv["permis_conducere"] = st.text_input("Categories (ex: A, B, C)", value=cv.get("permis_conducere", ""), key=f"{key_prefix}_dl")
