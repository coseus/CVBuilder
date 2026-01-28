from __future__ import annotations

from typing import Any, Dict, Optional, List

import streamlit as st

from utils import jd_optimizer


def render_ats_optimizer(cv: Dict[str, Any], profile: Optional[Dict[str, Any]] = None) -> None:
    """
    ATS Optimizer (keyword match) — OFFLINE.

    Uses ONE shared JD stored in cv["job_description"] managed by utils.jd_optimizer.
    No extra copy-paste fields here.
    """
    jd_optimizer.ensure_jd_state(cv)

    st.subheader("ATS Optimizer (keyword match)")
    st.caption("Folosește Job Description-ul din panel-ul 'Job Description (shared)'. Offline, rapid, ATS-friendly.")

    analysis = jd_optimizer.get_current_analysis(cv)

    col1, col2 = st.columns([1, 1], gap="large")
    with col1:
        st.metric("Coverage", f"{analysis.get('coverage', 0):.1f}%")
        present = analysis.get("present", [])
        if present:
            st.markdown("**Present keywords (top)**")
            st.write(", ".join(present[:30]))
        else:
            st.info("Paste JD în 'Job Description (shared)' ca să apară match-ul.")

    with col2:
        missing = analysis.get("missing", [])
        if missing:
            st.markdown("**Missing keywords (top)**")
            st.write(", ".join(missing[:35]))
        else:
            if (cv.get("job_description") or "").strip():
                st.success("Top keywords sunt deja acoperite (în setul analizat).")
            else:
                st.info("Nu există JD încă.")

    c3, c4 = st.columns(2, gap="large")
    with c3:
        if st.button("Auto-apply missing → Modern keywords", use_container_width=True, key="ats_optimizer_apply"):
            jd_optimizer.apply_auto_to_modern_skills(cv, analysis)
            st.success("Applied into Modern → Keywords (extra).")
            st.rerun()

    with c4:
        if st.button("Re-analyze", use_container_width=True, key="ats_optimizer_reanalyze"):
            jd_optimizer.analyze_current(cv, profile=profile)
            st.rerun()


def render_jd_ml_offline_panel(cv: Dict[str, Any], profile: Optional[Dict[str, Any]] = None) -> None:
    """
    Job Description Analyzer (Offline)

    Uses the SAME shared JD (cv["job_description"]) and persists per job hash automatically.
    """
    jd_optimizer.ensure_jd_state(cv)

    st.subheader("Job Description Analyzer (Offline)")
    st.caption("Folosește Job Description-ul shared. Salvează analiza per job (hash) automat.")

    # role hint suggestions from profile (optional)
    role_hint_default = (cv.get("jd_state", {}) or {}).get("current_role_hint") or ""
    role_hint = st.text_input(
        "Role hint (optional)",
        value=str(role_hint_default),
        key="jd_ml_offline_role_hint",
        help="Ex: 'security engineer', 'system administrator', 'accountant' etc.",
    )
    if role_hint != role_hint_default:
        cv.setdefault("jd_state", {})["current_role_hint"] = role_hint

    # show suggestions
    if isinstance(profile, dict):
        jts = profile.get("job_titles") or []
        if isinstance(jts, list) and jts:
            st.caption("Sugestii din profile")
            st.write(", ".join([str(x) for x in jts[:8]]))

    # analyze current JD (no extra paste)
    analysis = jd_optimizer.analyze_current(cv, profile=profile, role_hint=role_hint)

    st.markdown(
        f"**Job hash:** `{analysis.get('hash','')}` • **Lang:** `{analysis.get('lang','en')}` • "
        f"**Coverage:** **{analysis.get('coverage',0):.1f}%**"
    )

    missing = analysis.get("missing", [])
    if missing:
        st.markdown("**Missing keywords (top)**")
        st.write(", ".join(missing[:40]))
    else:
        if (cv.get("job_description") or "").strip():
            st.success("No missing keywords detected in top set.")
        else:
            st.info("Nu există JD încă.")

    c1, c2, c3 = st.columns(3, gap="large")
    with c1:
        if st.button("Auto-apply missing → Modern keywords", key="jd_ml_apply", use_container_width=True):
            jd_optimizer.apply_auto_to_modern_skills(cv, analysis)
            st.success("Applied into Modern → Keywords (extra).")
            st.rerun()

    with c2:
        if st.button("Show saved analyses", key="jd_ml_show_saved", use_container_width=True):
            jobs = (cv.get("jd_state", {}) or {}).get("jobs", {})
            if not isinstance(jobs, dict) or not jobs:
                st.info("No saved jobs yet.")
            else:
                for h, a in list(jobs.items())[:12]:
                    st.write(f"- {h} • {a.get('coverage',0):.1f}% • {a.get('role_hint','')}")

    with c3:
        if st.button("Clear saved JD analyses", key="jd_ml_clear", use_container_width=True):
            cv.setdefault("jd_state", {})["jobs"] = {}
            cv.setdefault("jd_state", {})["active_job_id"] = ""
            st.success("Cleared.")
            st.rerun()
