# components/ats_optimizer.py
from __future__ import annotations

from typing import Any, Dict

import streamlit as st

from utils import jd_optimizer


def render_ats_optimizer(cv: Dict[str, Any], profile: Dict[str, Any] | None = None):
    """
    ATS Optimizer (keyword match) — OFFLINE.

    IMPORTANT: No extra JD textbox here.
    It uses the shared Job Description field managed by jd_optimizer.
    """
    jd_optimizer.ensure_jd_state(cv)

    st.subheader("ATS Optimizer (keyword match)")
    st.caption("Folosește Job Description-ul shared de mai sus. Offline, rapid, ATS-friendly.")

    analysis = jd_optimizer.get_current_analysis(cv)

    col1, col2 = st.columns([1, 1], gap="large")
    with col1:
        st.metric("Coverage", f"{analysis.get('coverage', 0):.1f}%")
        present = analysis.get("present", [])
        if present:
            st.markdown("**Present keywords (top)**")
            st.write(", ".join(present[:30]))
        else:
            st.info("Paste a JD in the shared box above.")

    with col2:
        missing = analysis.get("missing", [])
        if missing:
            st.markdown("**Missing keywords (top)**")
            st.write(", ".join(missing[:35]))
        else:
            st.success("Great — top keywords are already covered.")

    c3, c4 = st.columns(2, gap="large")
    with c3:
        if st.button("Auto-apply missing → Extra keywords", use_container_width=True, key="ats_optimizer_apply"):
            jd_optimizer.apply_missing_to_extra_keywords(cv, limit=25)
            st.success("Applied into Modern → Extra keywords.")
            st.rerun()

    with c4:
        if st.button("Re-analyze", use_container_width=True, key="ats_optimizer_reanalyze"):
            jd_optimizer.analyze_jd(cv, profile=profile)
            st.rerun()


def render_jd_ml_offline_panel(cv: Dict[str, Any], profile: Dict[str, Any] | None = None):
    """
    Job Description Analyzer (Offline) — uses shared JD (no extra textbox).
    Persists analysis per job hash.
    """
    jd_optimizer.ensure_jd_state(cv)

    st.subheader("Job Description Analyzer (Offline)")
    st.caption("Folosește Job Description-ul shared. Salvează analiza per job (hash) automat.")

    # Role hint (optional)
    role_hint = st.text_input(
        "Role hint (optional)",
        value=(cv.get("jd_state", {}).get("current_role_hint") or ""),
        key="jd_ml_offline_role",
        help="Ex: 'security engineer', 'system administrator', 'accountant' etc.",
    )

    # Suggestions from profile (if provided)
    if isinstance(profile, dict):
        hints = profile.get("job_titles") or []
        if isinstance(hints, list) and hints:
            st.caption("Sugestii din profile")
            st.write(", ".join([str(x) for x in hints[:8]]))

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

    c1, c2 = st.columns(2, gap="large")
    with c1:
        if st.button("Auto-apply missing → Extra keywords", key="jd_ml_apply", use_container_width=True):
            jd_optimizer.apply_missing_to_extra_keywords(cv, limit=25)
            st.success("Applied into Modern → Extra keywords.")
            st.rerun()

    with c2:
        if st.button("Show saved analyses", key="jd_ml_show_saved", use_container_width=True):
            jobs = cv.get("jd_state", {}).get("jobs", {})
            if not jobs:
                st.info("No saved jobs yet.")
            else:
                for h, a in list(jobs.items())[:12]:
                    st.write(f"- {h} • {a.get('coverage',0):.1f}% • {a.get('role_hint','')}")
