# components/ats_optimizer.py
from __future__ import annotations

from typing import Any, Dict, Optional, List

import streamlit as st

from utils import jd_optimizer


def _role_options_from_profile(profile: Optional[Dict[str, Any]]) -> List[str]:
    """
    Prefer profile job_titles, fallback to a small sensible list.
    """
    default = ["general", "security engineer", "soc analyst", "penetration tester"]
    if not isinstance(profile, dict):
        return default

    jt = profile.get("job_titles", [])
    if isinstance(jt, list) and jt:
        # normalize a bit
        out = []
        for x in jt:
            s = str(x).strip().lower()
            if s and s not in out:
                out.append(s)
        return out[:12] if out else default

    return default


def render_ats_optimizer(cv: Dict[str, Any], profile: Optional[Dict[str, Any]] = None) -> None:
    """
    ATS Optimizer (keyword match) - now reads shared cv['job_description']
    (NO text_area here; JD is entered once in app.py).
    """
    st.subheader("ATS Optimizer (keyword match)")
    st.caption("Folosește Job Description-ul shared de mai sus. Offline, rapid, ATS-friendly.")

    jd_optimizer.ensure_jd_state(cv)

    # Auto-update analysis if JD changed
    jd_optimizer.auto_update_on_change(cv, profile=profile)

    jd = (cv.get("job_description") or "").strip()
    if not jd:
        st.info("Pune Job Description în panoul shared (deasupra) ca să vezi analiza.")
        return

    cov = float(cv.get("jd_coverage", 0.0) or 0.0)
    present = cv.get("jd_present", []) or []
    missing = cv.get("jd_missing", []) or []

    cols = st.columns(3)
    cols[0].metric("JD keywords (top)", min(45, len(cv.get("jd_keywords", []) or [])))
    cols[1].metric("Matched", len(present))
    cols[2].metric("Match %", f"{int(round(cov * 100))}%")

    with st.expander("Matched keywords", expanded=False):
        st.write(", ".join(present) if present else "—")

    st.markdown("**Missing (candidates to add):**")
    if not missing:
        st.success("Arată bine — nu am găsit keywords lipsă în top listă.")
        return

    st.write(", ".join(missing[:60]))

    if st.button("Apply missing → Modern: Extra keywords", type="primary", use_container_width=True, key="btn_apply_missing_kw"):
        jd_optimizer.apply_missing_to_extra_keywords(cv, limit=25)
        st.success("Aplicat în Modern → Extra keywords.")
        st.rerun()


def render_jd_ml_offline_panel(cv: Dict[str, Any], profile: Optional[Dict[str, Any]] = None) -> None:
    """
    Job Description Analyzer (Offline) - persist per job hash + templates update.
    (NO text_area here; shared JD is entered once in app.py).
    """
    st.subheader("Job Description Analyzer (Offline)")
    st.caption("Extrage keywords + coverage, salvează analiza per job (hash) și poate aplica automat în Skills / rewrite templates.")

    jd_optimizer.ensure_jd_state(cv)

    role_options = _role_options_from_profile(profile)
    current = (cv.get("jd_role_hint") or "").strip().lower()
    if current not in role_options:
        current = role_options[0]
    cv["jd_role_hint"] = st.selectbox(
        "Role hint",
        role_options,
        index=role_options.index(current),
        key="jd_role_hint_select",
    )

    # Auto-update analysis if JD changed
    analysis = jd_optimizer.auto_update_on_change(cv, profile=profile)

    jd = (cv.get("job_description") or "").strip()
    if not jd:
        st.info("Pune Job Description în panoul shared (deasupra) ca să rulezi analiza.")
        return

    colA, colB, colC, colD = st.columns([1, 1, 1, 1])
    with colA:
        run = st.button("Re-analyze now", use_container_width=True, key="jd_run_now")
    with colB:
        apply_missing = st.button("Apply missing → Extra keywords", use_container_width=True, key="jd_apply_missing_btn")
    with colC:
        apply_templates = st.button("Update rewrite templates", use_container_width=True, key="jd_apply_templates_btn")
    with colD:
        reset_jd = st.button("Reset doar ATS/JD", use_container_width=True, key="jd_reset_only_btn")

    if reset_jd:
        jd_optimizer.reset_ats_jd_only(cv, keep_history=True)
        st.success("Reset ATS/JD (experience/education NU au fost șterse).")
        st.rerun()

    if run:
        analysis = jd_optimizer.analyze_jd(cv, profile=profile)
        st.success(f"JD analyzed. Coverage: {float(analysis.get('coverage',0.0))*100:.0f}% (hash: {analysis.get('hash')})")
        st.rerun()

    # Display analysis
    cov = float(cv.get("jd_coverage", 0.0) or 0.0)
    st.markdown(f"**Coverage:** {cov*100:.0f}%")
    missing = cv.get("jd_missing", []) or []

    if missing:
        st.warning("Missing keywords (top): " + ", ".join(missing[:20]))
    else:
        st.success("No missing keywords detected in top set.")

    with st.expander("Top extracted keywords", expanded=False):
        st.write((cv.get("jd_keywords") or [])[:60])

    # Apply actions
    if apply_missing:
        if not missing:
            st.info("No missing keywords to apply.")
        else:
            jd_optimizer.apply_missing_to_extra_keywords(cv, limit=25)
            st.success("Applied missing keywords into Modern → Extra keywords.")
            st.rerun()

    if apply_templates:
        jd_optimizer.update_rewrite_templates_from_jd(cv, profile=profile)
        st.success("Rewrite templates updated for this job (cv['ats_rewrite_templates_active']).")
        st.rerun()
