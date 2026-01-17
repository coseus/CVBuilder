import streamlit as st


def render_personal_info_shared(cv: dict, key_prefix: str = "pi"):
    """
    Shared Personal Info editor for BOTH Modern and Europass.
    Writes directly into cv[...] keys used by exporters.
    Includes edit/add/delete for extra fields.
    """
    if not isinstance(cv, dict):
        st.error("CV is not a dict.")
        return

    cv.setdefault("nume_prenume", "")
    cv.setdefault("pozitie_vizata", "")
    cv.setdefault("telefon", "")
    cv.setdefault("email", "")
    cv.setdefault("adresa", "")
    cv.setdefault("linkedin", "")
    cv.setdefault("github", "")
    cv.setdefault("website", "")

    cv.setdefault("personal_info_extra", [])  # list of {"label": str, "value": str}

    st.subheader("Informații personale")

    cv["nume_prenume"] = st.text_input("Nume complet", value=cv.get("nume_prenume", ""), key=f"{key_prefix}_name")
    cv["pozitie_vizata"] = st.text_input("Titlu / Rol țintă", value=cv.get("pozitie_vizata", ""), key=f"{key_prefix}_headline")

    c1, c2 = st.columns(2)
    with c1:
        cv["email"] = st.text_input("Email", value=cv.get("email", ""), key=f"{key_prefix}_email")
        cv["linkedin"] = st.text_input("LinkedIn", value=cv.get("linkedin", ""), key=f"{key_prefix}_linkedin")
        cv["website"] = st.text_input("Website/Portfolio", value=cv.get("website", ""), key=f"{key_prefix}_website")
    with c2:
        cv["telefon"] = st.text_input("Telefon", value=cv.get("telefon", ""), key=f"{key_prefix}_phone")
        cv["adresa"] = st.text_input("Locație", value=cv.get("adresa", ""), key=f"{key_prefix}_location")
        cv["github"] = st.text_input("GitHub", value=cv.get("github", ""), key=f"{key_prefix}_github")

    st.markdown("### Câmpuri extra (edit/add/delete)")
    extras = cv.get("personal_info_extra", [])
    if not isinstance(extras, list):
        extras = []
        cv["personal_info_extra"] = extras

    # Existing extras (editable)
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

    # Add new extra
    with st.expander("➕ Adaugă câmp extra", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            new_label = st.text_input("Label (ex: City, Clearance, Telegram)", key=f"{key_prefix}_extra_new_label")
        with col2:
            new_value = st.text_input("Value", key=f"{key_prefix}_extra_new_value")
        if st.button("Add extra field", key=f"{key_prefix}_extra_add"):
            if new_label.strip() and new_value.strip():
                cv["personal_info_extra"].append({"label": new_label.strip(), "value": new_value.strip()})
                st.rerun()
            else:
                st.warning("Completează și label și value.")
