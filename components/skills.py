import streamlit as st
from components.aptitudini import render_aptitudini_sections

def render_skills(cv, prefix=""):
    # Backwards compatible wrapper
    render_aptitudini_sections(cv, prefix=prefix)

    st.markdown("### Permis conducere")
    cv['permis_conducere'] = st.text_input(
        "Permis conducere (categoria, opțional)",
        value=cv.get('permis_conducere', ''),
        key=f"{prefix}permis"
    )
