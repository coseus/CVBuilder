import streamlit as st
from components.list_editor import render_string_list_editor


def render_ats_summary(cv: dict, key_prefix: str = "ats_sum"):
    cv.setdefault("rezumat_bullets", [])

    st.subheader("Professional Summary (bullets recomandat)")
    cv["rezumat_bullets"] = render_string_list_editor(
        label="Bullet",
        items=cv.get("rezumat_bullets", []),
        key_prefix=key_prefix,
        placeholder="ex: Reduced incident response time by 35% using X...",
        help_text="Tip: 3–5 bullets, fiecare cu impact + tool/tech + (ideal) metric.",
    )
