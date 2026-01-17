import streamlit as st
from components.list_editor import render_kv_list_editor

CONTACT_TYPES = ["email", "phone", "location", "linkedin", "github", "website"]


def _normalize_contact_type(t: str) -> str:
    t = (t or "").strip().lower()
    return t if t in CONTACT_TYPES else "email"


def _sync_primary_fields_from_contacts(cv: dict):
    cv.setdefault("email", "")
    cv.setdefault("telefon", "")
    cv.setdefault("adresa", "")
    cv.setdefault("linkedin", "")
    cv.setdefault("github", "")
    cv.setdefault("website", "")

    contacts = cv.get("contact_items", [])
    if not isinstance(contacts, list):
        return

    def first_val(tp: str) -> str:
        for it in contacts:
            if isinstance(it, dict) and (it.get("type") == tp) and str(it.get("value", "")).strip():
                return str(it.get("value", "")).strip()
        return ""

    cv["email"] = first_val("email") or cv.get("email", "")
    cv["telefon"] = first_val("phone") or cv.get("telefon", "")
    cv["adresa"] = first_val("location") or cv.get("adresa", "")
    cv["linkedin"] = first_val("linkedin") or cv.get("linkedin", "")
    cv["github"] = first_val("github") or cv.get("github", "")
    cv["website"] = first_val("website") or cv.get("website", "")


def render_ats_personal_info(cv: dict, key_prefix: str = "ats_pi"):
    if not isinstance(cv, dict):
        st.error("CV invalid.")
        return

    cv.setdefault("nume_prenume", "")
    cv.setdefault("pozitie_vizata", "")
    cv.setdefault("profile_line", "")  # ✅ NEW

    cv.setdefault("contact_items", [])
    if not isinstance(cv["contact_items"], list) or not cv["contact_items"]:
        seed = []
        if str(cv.get("email", "")).strip():
            seed.append({"type": "email", "value": str(cv.get("email", "")).strip()})
        if str(cv.get("telefon", "")).strip():
            seed.append({"type": "phone", "value": str(cv.get("telefon", "")).strip()})
        if str(cv.get("adresa", "")).strip():
            seed.append({"type": "location", "value": str(cv.get("adresa", "")).strip()})
        if str(cv.get("linkedin", "")).strip():
            seed.append({"type": "linkedin", "value": str(cv.get("linkedin", "")).strip()})
        if str(cv.get("github", "")).strip():
            seed.append({"type": "github", "value": str(cv.get("github", "")).strip()})
        if str(cv.get("website", "")).strip():
            seed.append({"type": "website", "value": str(cv.get("website", "")).strip()})
        cv["contact_items"] = seed

    cv.setdefault("personal_info_extra", [])

    st.subheader("Personal Information (ATS) — add/edit/delete")

    cv["nume_prenume"] = st.text_input("Full name", value=cv.get("nume_prenume", ""), key=f"{key_prefix}_name")
    cv["profile_line"] = st.text_input(  # ✅ NEW
        "Profile line (short)",
        value=cv.get("profile_line", ""),
        key=f"{key_prefix}_profile_line",
        placeholder="e.g., Senior System Administrator | Cloud & Security Specialist | 17+ years",
        help="A short recruiter-friendly line under your name. Great for ATS + readability.",
    )
    cv["pozitie_vizata"] = st.text_input(
        "Target title / headline",
        value=cv.get("pozitie_vizata", ""),
        key=f"{key_prefix}_headline",
    )

    st.markdown("### Contact items (add/edit/delete)")
    contacts = cv.get("contact_items", [])
    if not isinstance(contacts, list):
        contacts = []
        cv["contact_items"] = contacts

    for i in range(len(contacts)):
        row = contacts[i] if isinstance(contacts[i], dict) else {"type": "email", "value": ""}
        row.setdefault("type", "email")
        row.setdefault("value", "")

        c1, c2, c3 = st.columns([2, 6, 1])
        with c1:
            row["type"] = st.selectbox(
                "Type",
                CONTACT_TYPES,
                index=CONTACT_TYPES.index(_normalize_contact_type(row.get("type"))),
                key=f"{key_prefix}_ct_{i}_type",
                label_visibility="collapsed",
            )
        with c2:
            row["value"] = st.text_input(
                "Value",
                value=str(row.get("value", "")),
                key=f"{key_prefix}_ct_{i}_value",
                label_visibility="collapsed",
                placeholder="e.g., name@email.com / +40... / Cluj-Napoca / linkedin.com/in/...",
            )
        with c3:
            if st.button("🗑", key=f"{key_prefix}_ct_{i}_del"):
                cv["contact_items"].pop(i)
                _sync_primary_fields_from_contacts(cv)
                st.rerun()

        cv["contact_items"][i] = row

    with st.expander("➕ Add contact item", expanded=False):
        c1, c2 = st.columns([2, 6])
        with c1:
            new_type = st.selectbox("Type", CONTACT_TYPES, key=f"{key_prefix}_ct_new_type")
        with c2:
            new_value = st.text_input("Value", key=f"{key_prefix}_ct_new_value")
        if st.button("Add", key=f"{key_prefix}_ct_add_btn"):
            if str(new_value).strip():
                cv["contact_items"].append({"type": new_type, "value": str(new_value).strip()})
                _sync_primary_fields_from_contacts(cv)
                st.rerun()
            else:
                st.warning("Enter a value first.")

    _sync_primary_fields_from_contacts(cv)

    st.markdown("### Extra fields (add/edit/delete)")
    cv["personal_info_extra"] = render_kv_list_editor(
        label="Extra fields",
        items=cv.get("personal_info_extra", []),
        key_prefix=f"{key_prefix}_extra",
        label_name="Label",
        value_name="Value",
        help_text="Examples: City, Clearance, Telegram, Availability, Citizenship etc.",
    )
