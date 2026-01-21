# components/ats_optimizer.py
from __future__ import annotations

from typing import Any, Dict, Optional, List

import streamlit as st

from utils import jd_optimizer


def _role_options_from_profile(profile: Optional[Dict[str, Any]]) -> List[str]:
    """
    Prefer profile job_titles, fallback to a sensible generic list.
    Works for IT + Non-IT.
    """
    default = ["general", "specialist", "analyst", "manager"]

    if not isinstance(profile, dict):
        return default

    jt = profile.get("job_titles", [])
    if isinstance(jt, list) and jt:
        out: List[str] = []
        for x in jt:
            s = str(x).strip()
            if not s:
                continue
            low = s.lower()
            if low not in [z.lower() for z in out]:
                out.append(s)
        return out[:12] if out else default

    # if profile has a title, use it as first option
    title = profile.get("title")
    if isinstance(title, str) and title.strip():
        return [title.strip()] + default

    return default


def render_ats_optimizer(cv: Dict[str, Any], profile: Optional[Dict[str, Any]] = None) -> None:
    """
    ATS Optimizer (keyword match) — reads shared cv["job_description"].
    """
    st.subheader("ATS Optimizer (keyword match)")
    st.caption("Folosește Job Description-ul shared. Offline, rapid, ATS-friendly.")

    jd_optimizer.ensure_jd_state(cv)
    analysis = jd_optimizer.auto_update_on_change(cv, profile=profile)

    jd = (cv.get("job_description") or "").strip()
    if not jd:
        st.info("Pune Job Description în panoul shared (dreapta) ca să vezi analiza.")
        return

    cov = float(analysis.get("coverage", 0.0) or 0.0)
    present = analysis.get("present", []) or []
    missing = analysis.get("missing", []) or []

    cols = st.columns(3)
    cols[0].metric("JD keywords (top)", min(45, len(analysis.get("keywords", []) or [])))
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
    Job Description Analyzer (Offline) — persists per job hash and can update templates.
    Reads shared cv["job_description"].
    """
    st.subheader("Job Description Analyzer (Offline)")
    st.caption("Extrage keywords + coverage, salvează analiza per job (hash) și poate aplica automat în Skills / rewrite templates.")

    jd_optimizer.ensure_jd_state(cv)

    role_options = _role_options_from_profile(profile)
    current = (cv.get("jd_role_hint") or "").strip()
    if not current:
        current = role_options[0]
    # keep current if present; otherwise fallback
    if current.lower() not in [x.lower() for x in role_options]:
        current = role_options[0]

    cv["jd_role_hint"] = st.selectbox(
        "Role hint",
        role_options,
        index=[x.lower() for x in role_options].index(current.lower()),
        key="jd_role_hint_select",
        help="Derivat din profile job_titles (dacă există).",
    )

    jd = (cv.get("job_description") or "").strip()
    if not jd:
        st.info("Pune Job Description în panoul shared (dreapta) ca să rulezi analiza.")
        return

    c1, c2, c3 = st.columns([1, 1, 1])
    run = c1.button("Re-analyze now", use_container_width=True, key="jd_run_now")
    apply_missing = c2.button("Apply missing → Extra keywords", use_container_width=True, key="jd_apply_missing_btn")
    apply_templates = c3.button("Update rewrite templates", use_container_width=True, key="jd_apply_templates_btn")

    if run:
        analysis = jd_optimizer.analyze_jd(cv, profile=profile, role_hint=cv.get("jd_role_hint") or "")
        st.success(f"JD analyzed. Coverage: {float(analysis.get('coverage',0.0))*100:.0f}%")
        st.rerun()
    else:
        analysis = jd_optimizer.auto_update_on_change(cv, profile=profile)

    st.markdown(
        f"**Job hash:** `{analysis.get('hash','')}` • **Lang:** `{analysis.get('lang','en')}` • "
        f"**Coverage:** **{float(analysis.get('coverage',0.0))*100:.0f}%**"
    )

    missing = analysis.get("missing", []) or []
    if missing:
        st.markdown("**Missing keywords (top)**")
        st.write(", ".join(missing[:40]))
    else:
        st.success("No missing keywords detected in top set.")

    if apply_missing:
        jd_optimizer.apply_missing_to_extra_keywords(cv, limit=25)
        st.success("Applied into Modern → Extra keywords.")
        st.rerun()

    if apply_templates:
        jd_optimizer.update_rewrite_templates_from_jd(cv, profile=profile)
        st.success("Rewrite templates updated for this job.")
        st.rerun()

    with st.expander("Saved analyses (history)", expanded=False):
        jobs = cv.get("jd_state", {}).get("jobs", {})
        if not isinstance(jobs, dict) or not jobs:
            st.caption("No saved jobs yet.")
        else:
            # show most recent-ish (dict order is insertion order)
            items = list(jobs.items())[-10:]
            for h, a in reversed(items):
                covp = float((a or {}).get("coverage", 0.0) or 0.0) * 100.0
                rh = (a or {}).get("role_hint", "")
                st.write(f"- `{h}` • {covp:.0f}% • {rh}")
