import streamlit as st
from components.ats_rewrite import render_auto_rewrite_box


def render_work_experience(
    cv: dict,
    profile=None,
    prefix: str = "",
    title: str = "",
    item_label: str = "Proiect",
    list_key: str = "experienta",
    show_employer_fields: bool = True,
    show_sector_field: bool = False,
    show_tech_and_link: bool = False,
):
    if not isinstance(cv, dict):
        st.error("CV data is missing or invalid.")
        return

    cv.setdefault(list_key, [])

    if title:
        st.subheader(title)

    # Add new
    with st.expander(f"➕ Add {item_label}", expanded=False):
        titlu = st.text_input("Nume proiect", key=f"{prefix}add_{list_key}_titlu")
        perioada = st.text_input("Perioadă", key=f"{prefix}add_{list_key}_perioada")
        functie = st.text_input("Rol / Funcție", key=f"{prefix}add_{list_key}_functie")

        angajator = ""
        locatie = ""
        if show_employer_fields:
            colA, colB = st.columns(2)
            with colA:
                angajator = st.text_input("Angajator / Client", key=f"{prefix}add_{list_key}_angajator")
            with colB:
                locatie = st.text_input("Locație", key=f"{prefix}add_{list_key}_locatie")

        activitati = st.text_area(
            "Activități / Realizări (bullets recomandat)",
            height=120,
            key=f"{prefix}add_{list_key}_activitati",
        )

        tehnologii = ""
        link = ""
        if show_tech_and_link:
            tehnologii = st.text_input("Tehnologii / Tools", key=f"{prefix}add_{list_key}_tehnologii")
            link = st.text_input("Link (repo / report / demo)", key=f"{prefix}add_{list_key}_link")

        if st.button(f"Add {item_label}", key=f"{prefix}btn_add_{list_key}"):
            cv[list_key].append({
                "titlu": titlu,
                "perioada": perioada,
                "functie": functie,
                "angajator": angajator,
                "locatie": locatie,
                "activitati": activitati,
                "sector": "",
                "tehnologii": tehnologii,
                "link": link,
            })
            st.success(f"{item_label} added.")
            st.rerun()

    # Existing
    for idx, item in enumerate(cv[list_key]):
        shown_title = item.get("titlu") or item.get("functie") or f"{item_label} #{idx+1}"

        with st.expander(f"{item_label} #{idx + 1}: {shown_title}", expanded=False):
            item["titlu"] = st.text_input("Nume proiect", value=item.get("titlu", ""), key=f"{prefix}{list_key}_{idx}_titlu")
            item["perioada"] = st.text_input("Perioadă", value=item.get("perioada", ""), key=f"{prefix}{list_key}_{idx}_perioada")
            item["functie"] = st.text_input("Rol / Funcție", value=item.get("functie", ""), key=f"{prefix}{list_key}_{idx}_functie")

            if show_employer_fields:
                col1, col2 = st.columns(2)
                with col1:
                    item["angajator"] = st.text_input("Angajator / Client", value=item.get("angajator", ""), key=f"{prefix}{list_key}_{idx}_angajator")
                with col2:
                    item["locatie"] = st.text_input("Locație", value=item.get("locatie", ""), key=f"{prefix}{list_key}_{idx}_locatie")

            item["activitati"] = st.text_area(
                "Activități / Realizări",
                value=item.get("activitati", ""),
                height=140,
                key=f"{prefix}{list_key}_{idx}_activitati",
            )

            if show_tech_and_link:
                item["tehnologii"] = st.text_input("Tehnologii / Tools", value=item.get("tehnologii", ""), key=f"{prefix}{list_key}_{idx}_tehnologii")
                item["link"] = st.text_input("Link", value=item.get("link", ""), key=f"{prefix}{list_key}_{idx}_link")

            # optional rewrite
            if profile:
                render_auto_rewrite_box(
                    cv=cv,
                    profile=profile,
                    field_path=f"{list_key}[{idx}].activitati",
                    item_key=f"{list_key}_{idx}",
                    label="Rewrite suggestion",
                )

            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("⬆ Move up", key=f"{prefix}{list_key}_{idx}_up") and idx > 0:
                    cv[list_key][idx - 1], cv[list_key][idx] = cv[list_key][idx], cv[list_key][idx - 1]
                    st.rerun()
            with c2:
                if st.button("⬇ Move down", key=f"{prefix}{list_key}_{idx}_down") and idx < len(cv[list_key]) - 1:
                    cv[list_key][idx + 1], cv[list_key][idx] = cv[list_key][idx], cv[list_key][idx + 1]
                    st.rerun()
            with c3:
                if st.button("🗑 Delete", key=f"{prefix}{list_key}_{idx}_del"):
                    cv[list_key].pop(idx)
                    st.rerun()
