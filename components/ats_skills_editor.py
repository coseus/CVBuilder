import streamlit as st


def _list_from_multiline(text: str):
    out = []
    for line in (text or "").splitlines():
        s = line.strip().lstrip("-•* ").strip()
        if s:
            out.append(s)
    return out


def render_ats_skills_editor(cv: dict, key_prefix: str = "ats_sk"):
    """
    ATS-friendly skills editor (Modern).
    Stores into:
      modern_skills_headline, modern_tools, modern_certs, modern_keywords_extra
    with add/edit/delete UI.
    """
    if not isinstance(cv, dict):
        st.error("CV invalid.")
        return

    cv.setdefault("modern_skills_headline", "")
    cv.setdefault("modern_tools", "")
    cv.setdefault("modern_certs", "")
    cv.setdefault("modern_keywords_extra", "")

    st.subheader("Skills (ATS-friendly)")

    cv["modern_skills_headline"] = st.text_input(
        "Skills headline (1 linie, keyword-dense)",
        value=cv.get("modern_skills_headline", ""),
        key=f"{key_prefix}_headline",
        placeholder="ex: Security • Windows/Linux • AD/Azure AD • O365 • Networking",
    )

    st.caption("Recomandat: 1 skill pe linie (tools/certs/keywords).")
    cv["modern_tools"] = st.text_area("Tools / Technologies", value=cv.get("modern_tools", ""), height=120, key=f"{key_prefix}_tools")
    cv["modern_certs"] = st.text_area("Certifications", value=cv.get("modern_certs", ""), height=120, key=f"{key_prefix}_certs")
    cv["modern_keywords_extra"] = st.text_area("Extra keywords", value=cv.get("modern_keywords_extra", ""), height=120, key=f"{key_prefix}_kw")

    # Quick previews (helps user see export format)
    with st.expander("Preview (as bullets)", expanded=False):
        tools = _list_from_multiline(cv.get("modern_tools", ""))
        certs = _list_from_multiline(cv.get("modern_certs", ""))
        kws = _list_from_multiline(cv.get("modern_keywords_extra", ""))

        if tools:
            st.markdown("**Tools:**")
            for t in tools:
                st.write(f"- {t}")
        if certs:
            st.markdown("**Certifications:**")
            for c in certs:
                st.write(f"- {c}")
        if kws:
            st.markdown("**Keywords:**")
            for k in kws:
                st.write(f"- {k}")
