from __future__ import annotations

import streamlit as st
from typing import Any, Dict, List
from utils.profiles import load_domains_index

from utils.jd_optimizer import (
    analyze_jd,
    apply_jd_to_cv,
    jd_hash,
    load_analysis,
    role_hints_from_profile,
    save_analysis,
)


def _shared_jd_box(cv: Dict[str, Any], key: str = "shared_jd") -> str:
    """
    Single source of truth for JD across ALL ATS panels:
    cv['job_description']
    """
    cv.setdefault("job_description", "")
    jd = st.text_area(
        "Job Description (paste once) — shared across ATS panels",
        value=cv.get("job_description", ""),
        height=180,
        key=key,
        help="Lipeste JD o singura data. Este folosit de Keyword Match + JD Analyzer + ATS Helper.",
    )
    cv["job_description"] = jd
    return jd


def _cv_text_for_match(cv: Dict[str, Any]) -> str:
    parts: List[str] = []
    for k in ["rezumat_bullets", "modern_skills_headline", "modern_tools", "modern_certs", "modern_keywords_extra"]:
        v = cv.get(k)
        if isinstance(v, list):
            parts.extend([str(x) for x in v])
        else:
            parts.append(str(v or ""))

    exp = cv.get("experienta", [])
    if isinstance(exp, list):
        for e in exp:
            if isinstance(e, dict):
                parts.append(str(e.get("titlu", "")))
                parts.append(str(e.get("functie", "")))
                parts.append(str(e.get("angajator", "")))
                parts.append(str(e.get("activitati", "")))
                parts.append(str(e.get("tehnologii", "")))

    edu = cv.get("educatie", [])
    if isinstance(edu, list):
        for ed in edu:
            if isinstance(ed, dict):
                parts.append(str(ed.get("titlu", "")))
                parts.append(str(ed.get("organizatie", "")))
                parts.append(str(ed.get("descriere", "")))

    return "\n".join([p for p in parts if p and p.strip()]).lower()


def render_ats_optimizer(cv: Dict[str, Any], profile: Dict[str, Any] | None = None) -> None:
    """
    Panel 1: ATS Optimizer (keyword match) - uses shared JD.
    """
    st.subheader("ATS Optimizer (keyword match)")
    st.caption("Lipește job description-ul o singură dată. Vezi keywords lipsă rapid, offline.")

    jd = _shared_jd_box(cv, key="ats_shared_jd")

    if not jd.strip():
        st.info("Paste Job Description ca să vezi keyword coverage.")
        return

    lang_hint = st.selectbox(
        "Language",
        [("Auto", "auto"), ("English", "en"), ("Română", "ro")],
        format_func=lambda x: x[0],
        index=0,
        key="ats_lang_hint_match",
    )[1]

    role_hint = ""
    if profile:
        hints = role_hints_from_profile(profile)
        role_hint = st.selectbox("Role hint", hints, index=0, key="ats_role_hint_match")

    analysis = analyze_jd(cv, jd, lang_hint=lang_hint, role_hint=role_hint)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Matched keywords (top)**")
        st.write(", ".join(analysis.matched[:50]) if analysis.matched else "—")
    with c2:
        st.markdown("**Missing keywords (top)**")
        st.write(", ".join(analysis.missing[:50]) if analysis.missing else "—")

    st.progress(analysis.coverage / 100.0)
    st.caption(f"Keyword coverage (rough): {analysis.coverage}%")

    st.markdown("---")
    st.markdown("### Apply missing keywords to Modern → Keywords")
    colA, colB = st.columns(2)
    with colA:
        if st.button("Append missing → Keywords", use_container_width=True, key="btn_apply_missing_append"):
            apply_jd_to_cv(cv, analysis, mode="append")
            st.success("Applied (append) to modern_keywords_extra.")
            st.rerun()
    with colB:
        if st.button("Replace Keywords with missing", use_container_width=True, key="btn_apply_missing_replace"):
            apply_jd_to_cv(cv, analysis, mode="replace")
            st.success("Applied (replace) to modern_keywords_extra.")
            st.rerun()


def render_jd_ml_offline_panel(cv: Dict[str, Any], profile: Dict[str, Any] | None = None) -> None:
    """
    Panel 2: Job Description Analyzer (Offline)
    - Extract keywords + coverage
    - Persist per job hash
    - Apply automatically into Skills / rewrite (for now: keywords extra)
    """
    st.subheader("Job Description Analyzer (Offline)")
    st.caption("Extrage keywords + coverage, salvează analiza per job (hash) și poate aplica automat în Skills.")

    jd = _shared_jd_box(cv, key="jd_shared_analyzer")

    lang_hint = st.selectbox(
        "Language",
        [("Auto", "auto"), ("English", "en"), ("Română", "ro")],
        format_func=lambda x: x[0],
        index=0,
        key="jd_lang_hint_analyzer",
    )[1]

    role_hint = ""
    if profile:
        hints = role_hints_from_profile(profile)
        role_hint = st.selectbox(
            "Role hint (din ATS profile)",
            hints,
            index=0,
            key="jd_role_hint_analyzer",
            help="Se actualizează automat când schimbi ATS Profile.",
        )
    else:
        role_hint = st.text_input("Role hint (optional)", value="", key="jd_role_hint_free")

    if not jd.strip():
        st.info("Paste Job Description ca să rulezi analiza.")
        return

    job_id = jd_hash(jd)
    st.caption(f"Job hash: `{job_id}`")

    analysis = analyze_jd(cv, jd, lang_hint=lang_hint, role_hint=role_hint)

    st.write(f"Coverage: **{analysis.coverage}%** | Keywords: **{len(analysis.keywords)}** | Missing: **{len(analysis.missing)}**")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Save analysis", use_container_width=True, key="btn_save_analysis"):
            save_analysis(job_id, jd, analysis)
            st.success("Saved.")
    with col2:
        if st.button("Load saved", use_container_width=True, key="btn_load_analysis"):
            saved = load_analysis(job_id)
            if saved:
                st.success("Loaded saved analysis.")
                st.session_state["jd_loaded_preview"] = saved
            else:
                st.warning("No saved analysis for this hash.")
    with col3:
        if st.button("Apply missing → Keywords", use_container_width=True, key="btn_apply_from_analyzer"):
            apply_jd_to_cv(cv, analysis, mode="append")
            st.success("Applied to Modern keywords.")
            st.rerun()

    with st.expander("Show missing keywords (copy)", expanded=False):
        st.code("\n".join(analysis.missing[:120]) if analysis.missing else "—")

    # Show loaded snapshot if any
    snap = st.session_state.get("jd_loaded_preview")
    if isinstance(snap, dict):
        with st.expander("Loaded snapshot (debug)", expanded=False):
            st.json(snap)
