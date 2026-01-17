import streamlit as st

def render_modern_skills(cv, prefix: str = "modern_"):
    st.subheader("Skills (ATS-friendly)")

    cv['modern_skills_headline'] = st.text_input(
        "Headline skills (separate cu • sau ,)",
        value=cv.get('modern_skills_headline', ''),
        key=f"{prefix}skills_headline",
        help="Ex: Python • Pentesting • Web Security • Linux • Networking"
    )

    col1, col2 = st.columns(2)
    with col1:
        cv['modern_tools'] = st.text_area(
            "Tools / Tech (comma-separated)",
            value=cv.get('modern_tools', ''),
            height=110,
            key=f"{prefix}tools",
            help="Ex: Nmap, Burp Suite, Metasploit, Wireshark, Git, Docker"
        )
    with col2:
        cv['modern_certs'] = st.text_area(
            "Certifications (comma-separated)",
            value=cv.get('modern_certs', ''),
            height=110,
            key=f"{prefix}certs",
            help="Ex: eJPT, Security+, PNPT"
        )

    cv['modern_keywords_extra'] = st.text_area(
        "Extra keywords (optional, pentru ATS match)",
        value=cv.get('modern_keywords_extra', ''),
        height=90,
        key=f"{prefix}keywords_extra",
        help="Cuvinte cheie din job description pe care vrei să apară explicit în CV."
    )
