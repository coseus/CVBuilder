# components/ats_optimizer.py
from __future__ import annotations

import streamlit as st
from typing import Any, Dict, Optional

from utils import jd_optimizer


def _ensure_analysis(cv: Dict[str, Any], profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    jd_optimizer.ensure_jd_state(cv)
    # prefer cached analysis; if none but JD exists => analyze
    a = jd_optimizer.get_current_analysis(cv)
    if a:
        return a
    if (cv.get("job_description") or "").strip():
        return jd_optimizer.analyze_jd(cv, profile=profile, role_hint=cv.get("jd_role_hint", ""))
    return {}


def render_ats_optimizer(cv: Dict[str, Any], profile: Dict[str, Any] | None = None):
    """
    ATS Optimizer (keyword match) — OFFLINE.
    Uses shared JD: cv["job_description"] (set in app.py expander).
    """
    jd_optimizer.ensure_jd_state(cv)

    st.subheader("ATS Optimizer (keyword match)")
    st.caption("Folosește Job Description-ul din zona 'Job Description (shared)' (nu mai trebuie paste aici).")

    jd = jd_optimizer.get_current_jd(cv).strip()
    if not jd:
        st.info("Pastează un Job Description în 'Job Description (shared)' ca să vezi coverage/missing.")
        return

    analysis = _ensure_analysis(cv, profile=profile)

    col1, col2 = st.columns([1, 1], gap="large")
    with col1:
        st.metric("Coverage", f"{analysis.get('coverage', 0):.1f}%")
        present = analysis.get("present", [])
        if isinstance(present, list) and present:
            st.markdown("**Present keywords (top)**")
            st.write(", ".join(present[:30]))
        else:
            st.info("Încă nu sunt matches — apasă Re-analyze.")

    with col2:
        missing = analysis.get("missing", [])
        if isinstance(missing, list) and missing:
            st.markdown("**Missing keywords (top)**")
            st.write(", ".join(missing[:35]))
        else:
            st.success("Top keywords par acoperite.")

    c3, c4 = st.columns(2, gap="large")
    with c3:
        if st.button("Auto-apply missing → Modern keywords", use_container_width=True, key="ats_optimizer_apply"):
            jd_optimizer.apply_missing_to_extra_keywords(cv, limit=25)
            st.success("Applied into Modern → Extra keywords.")
            st.rerun()

    with c4:
        if st.button("Re-analyze", use_container_width=True, key="ats_optimizer_reanalyze"):
            jd_optimizer.analyze_jd(cv, profile=profile, role_hint=cv.get("jd_role_hint", ""))
            st.success("Re-analyzed.")
            st.rerun()


def render_jd_ml_offline_panel(cv: Dict[str, Any], profile: Dict[str, Any] | None = None):
    """
    Job Description Analyzer (Offline)
    Uses shared JD. Shows hash/lang/coverage + saved analyses.
    """
    jd_optimizer.ensure_jd_state(cv)

    st.subheader("Job Description Analyzer (Offline)")
    st.caption("Folosește Job Description-ul shared. Salvează analiza per job (hash) automat.")

    jd = jd_optimizer.get_current_jd(cv).strip()
    if not jd:
        st.info("Pastează un Job Description în 'Job Description (shared)'.")
        return

    # Role hint: keep 1 field in session
    default_hint = (cv.get("jd_role_hint") or "").strip()
    hints = []
    if isinstance(profile, dict):
        jts = profile.get("job_titles")
        if isinstance(jts, list):
            hints = [str(x).strip().lower() for x in jts if str(x).strip()][:12]

    colh1, colh2 = st.columns([2, 3], gap="large")
    with colh1:
        cv["jd_role_hint"] = st.text_input(
            "Role hint (optional)",
            value=default_hint,
            key="jd_ml_role_hint",
            help="Ex: security engineer / soc analyst / project manager etc.",
        )
    with colh2:
        if hints:
            st.caption("Sugestii din profile")
            st.write(", ".join(hints[:10]))

    analysis = jd_optimizer.analyze_jd(cv, profile=profile, role_hint=cv.get("jd_role_hint", ""))

    st.markdown(
        f"**Job hash:** `{analysis.get('hash','')}` • "
        f"**Lang:** `{analysis.get('lang','en')}` • "
        f"**Coverage:** **{analysis.get('coverage',0):.1f}%**"
    )

    missing = analysis.get("missing", [])
    if isinstance(missing, list) and missing:
        st.markdown("**Missing keywords (top)**")
        st.write(", ".join(missing[:40]))
    else:
        st.success("No missing keywords detected in top set.")

    c1, c2, c3 = st.columns(3, gap="large")
    with c1:
        if st.button("Auto-apply missing → Modern keywords", key="jd_ml_apply", use_container_width=True):
            jd_optimizer.apply_missing_to_extra_keywords(cv, limit=25)
            st.success("Applied.")
            st.rerun()

    with c2:
        if st.button("Update rewrite templates", key="jd_ml_update_templates", use_container_width=True):
            jd_optimizer.update_rewrite_templates_from_jd(cv, profile=profile)
            st.success("Updated rewrite hints.")
            st.rerun()

    with c3:
        if st.button("Show saved analyses", key="jd_ml_show_saved", use_container_width=True):
            stt = cv.get("jd_state", {})
            jobs = stt.get("jobs", {})
            if not isinstance(jobs, dict) or not jobs:
                st.info("No saved jobs yet.")
            else:
                for h, a in list(jobs.items())[:15]:
                    cov = (a.get("coverage", 0) if isinstance(a, dict) else 0)
                    rh = (a.get("role_hint", "") if isinstance(a, dict) else "")
                    st.write(f"- `{h}` • {cov:.1f}% • {rh}")
