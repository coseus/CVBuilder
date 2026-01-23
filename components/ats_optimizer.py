# components/ats_optimizer.py
from __future__ import annotations

from typing import Any, Dict

import streamlit as st

from utils import jd_optimizer


def render_ats_optimizer(cv: Dict[str, Any], profile: Dict[str, Any] | None = None):
    """
    ATS Optimizer (keyword match) — OFFLINE.
    Uses ONE shared JD field (cv["job_description"]) managed by jd_optimizer.
    """
    jd_optimizer.ensure_jd_state(cv)

    st.subheader("ATS Optimizer (keyword match)")
    st.caption("Lipește job description-ul și vezi ce keywords lipsesc din CV. Offline, rapid, ATS-friendly.")

    jd_text = jd_optimizer.get_current_jd(cv)
    new_text = st.text_area("Job description", value=jd_text, height=160, key="ats_optimizer_jd")
    if new_text != jd_text:
        jd_optimizer.set_current_jd(cv, new_text)

    # re-run analysis if needed
    jd_optimizer.auto_update_on_change(cv, profile=profile)
    analysis = jd_optimizer.get_current_analysis(cv)

    col1, col2 = st.columns([1, 1], gap="large")
    with col1:
        st.metric("Coverage", f"{analysis.get('coverage', 0):.1f}%")
        present = analysis.get("present", [])
        if present:
            st.markdown("**Present keywords (top)**")
            st.write(", ".join(present[:30]))
        else:
            st.info("No matches detected yet — paste a JD.")

    with col2:
        missing = analysis.get("missing", [])
        if missing:
            st.markdown("**Missing keywords (top)**")
            st.write(", ".join(missing[:35]))
        else:
            st.success("Great — top keywords are already covered.")

    c3, c4 = st.columns(2, gap="large")
    with c3:
        if st.button("Auto-apply missing → Modern keywords", use_container_width=True, key="ats_optimizer_apply"):
            jd_optimizer.apply_missing_to_extra_keywords(cv, limit=80)
            st.success("Applied into Modern → Keywords (extra).")
            st.rerun()

    with c4:
        if st.button("Re-analyze", use_container_width=True, key="ats_optimizer_reanalyze"):
            jd_optimizer.analyze_jd(cv, role_hint=cv.get("jd_state", {}).get("current_role_hint", ""), profile=profile)
            st.rerun()


def render_jd_ml_offline_panel(cv: Dict[str, Any], profile: Dict[str, Any] | None = None):
    """
    Job Description Analyzer (Offline)
    Saves analysis per job hash in cv["jd_state"]["jobs"].
    """
    jd_optimizer.ensure_jd_state(cv)

    st.subheader("Job Description Analyzer (Offline)")
    st.caption("Extrage keywords + coverage, salvează analiza per job (hash) și poate aplica automat în Skills / rewrite templates.")

    jd_text = jd_optimizer.get_current_jd(cv)
    new_text = st.text_area("Job Description", value=jd_text, height=160, key="jd_ml_offline_jd")
    if new_text != jd_text:
        jd_optimizer.set_current_jd(cv, new_text)

    role_hint = st.text_input(
        "Role hint (optional)",
        value=(cv.get("jd_state", {}).get("current_role_hint") or ""),
        key="jd_ml_offline_role",
        help="Ex: 'security engineer', 'soc analyst', 'project manager', etc.",
    )
    cv["jd_state"]["current_role_hint"] = role_hint

    analysis = jd_optimizer.analyze_jd(cv, role_hint=role_hint, profile=profile)

    st.markdown(
        f"**Job hash:** `{analysis.get('hash','')}` • **Lang:** `{analysis.get('lang','en')}` • "
        f"**Coverage:** **{analysis.get('coverage',0):.1f}%**"
    )

    missing = analysis.get("missing", [])
    if missing:
        st.markdown("**Missing keywords (top)**")
        st.write(", ".join(missing[:40]))
    else:
        st.success("No missing keywords detected in top set.")

    c1, c2, c3 = st.columns(3, gap="large")
    with c1:
        if st.button("Auto-apply missing → Modern keywords", key="jd_ml_apply", use_container_width=True):
            jd_optimizer.apply_auto_to_modern_skills(cv, analysis, limit=80)
            st.success("Applied into Modern → Keywords (extra).")
            st.rerun()

    with c2:
        if st.button("Update rewrite templates", key="jd_ml_update_templates", use_container_width=True):
            jd_optimizer.update_rewrite_templates_from_jd(cv, profile=profile)
            st.success("Updated rewrite templates for this job.")
            st.rerun()

    with c3:
        if st.button("Show saved analyses", key="jd_ml_show_saved", use_container_width=True):
            jobs = cv.get("jd_state", {}).get("jobs", {})
            if not jobs:
                st.info("No saved jobs yet.")
            else:
                for h, a in list(jobs.items())[:12]:
                    st.write(f"- {h} • {a.get('coverage',0):.1f}% • {a.get('role_hint','')}")
