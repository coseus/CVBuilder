import streamlit as st
from components.list_editor import render_bullet_list

def render_professional_summary(cv, prefix=""):
    # Ensure bullets list exists
    cv.setdefault('rezumat_bullets', [])
    st.subheader("Professional Summary (bullets)")
    bullets = cv.get('rezumat_bullets', [])
    bullets = render_bullet_list(
        label="Summary bullets",
        bullets=bullets,
        key_prefix=f"{prefix}sum",
        help_text="3–5 bullets. Include keywords + rezultate măsurabile (%, #, timp)."
    )
    cv['rezumat_bullets'] = bullets
