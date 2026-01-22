# components/ats_optimizer.py
from __future__ import annotations

from typing import Any, Dict, Optional, List
import streamlit as st

from utils import jd_optimizer


def _role_options_from_profile(profile: Optional[Dict[str, Any]]) -> List[str]:
    default = ["general", "security engineer", "soc analyst", "penetration tester"]
    if not isinstance(profile, dict):
        return default
    jt = profile.get("job_titles", [])
    if isinstance(jt, list) and jt:
        out = []
        for x in jt:
            s = str(x).strip()
            if not s:
                continue
            low = s.lower()
            if low not in [z.lower() for z in out]:
                out.append(s)
        return out[:12] if out else default
    return default


def render_ats_optimizer(cv: Dict[str, Any], profile: Optional[Dict[str, Any]] = None) -> None:
    """
    ATS Optimizer (keyword match) — uses shared JD.
    """
    jd_optimizer.ensure_jd_state(cv)
    jd_optimizer.auto_update_on_change(cv, profile=profile)

    st.subheader("ATS Optimizer (keyword match)")
    st.caption("Folosește Job Description-ul shared (din dreapta). Offline, rapid, ATS-friendly.")

    jd = (cv.get("job_description") or "").strip()
    if not jd:
        st.info("Pune Job Description în panoul shared ca să vezi analiza.")
        return

    a = jd_optimizer.get_current_analysis_or_blank(cv)

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.metric("Coverage", f"{float(a.get('coverage', 0.0))*100:.1f}%")
        present = a.get("present", []) or []
        st.markdown("**Present keywords (top)**")
        st.write(", ".join(present[:30]) if present else "—")

    with col2:
        missing = a.get("missing", []) or []
        st.markdown("**Missing keywords (top)**")
        st.write(", ".join(missing[:35]) if missing else "—")

    c3, c4 = st.columns(2, gap="large")
    with c3:
        if st.button("Auto-apply missing → Modern keywords", use_container_width=True, key="ats_optimizer_apply"):
            jd_optimizer.apply_missing_to_extra_keywords(cv, limit=25)
            st.success("Applied into Modern → Extra keywords.")
            st.rerun()

    with c4:
        if st.button("Re-analyze", use_container_width=True, key="ats_optimizer_reanalyze"):
            jd_optimizer.analyze_jd(cv, profile=profile, role_hint=cv.get("jd_role_hint", ""))
            st.rerun()


def render_jd_ml_offline_panel(cv: Dict[str, Any], profile: Optional[Dict[str, Any]] = None) -> None:
    """
    Job Description Analyzer (Offline) — uses shared JD.
    """
    jd_optimizer.ensure_jd_state(cv)

    st.subheader("Job Description Analyzer (Offline)")
    st.caption("Extrage keywords + coverage, salvează analiza per job (hash) și poate aplica automat în Skills / rewrite templates.")

    jd = (cv.get("job_description") or "").strip()
    if not jd:
        st.info("Pune Job Description în panoul shared ca să ruleze analyzer-ul.")
        return

    role_opts = _role_options_from_profile(profile)
    current = (cv.get("jd_role_hint") or "").strip()
    if not current:
        current = role_opts[0]

    role_hint = st.selectbox(
        "Role hint",
        role_opts,
        index=role_opts.index(current) if current in role_opts else 0,
        key="jd_ml_role_hint_select",
        help="Folosit pentru template suggestions & heuristici (offline).",
    )
    cv["jd_role_hint"] = role_hint

    analysis = jd_optimizer.analyze_jd(cv, profile=profile, role_hint=role_hint)

    st.markdown(
        f"**Job hash:** `{analysis.get('hash','')}` • "
        f"**Lang:** `{analysis.get('lang','en')}` • "
        f"**Coverage:** **{float(analysis.get('coverage',0.0))*100:.1f}%**"
    )

    missing = analysis.get("missing", []) or []
    if missing:
        st.markdown("**Missing keywords (top)**")
        st.write(", ".join(missing[:40]))
    else:
        st.success("No missing keywords detected in top set.")

    c1, c2, c3 = st.columns(3, gap="large")
    with c1:
        if st.button("Apply missing → Extra keywords", key="jd_ml_apply", use_container_width=True):
            jd_optimizer.apply_missing_to_extra_keywords(cv, limit=25)
            st.success("Applied into Modern → Extra keywords.")
            st.rerun()

    with c2:
        if st.button("Update rewrite templates", key="jd_ml_update_templates", use_container_width=True):
            jd_optimizer.update_rewrite_templates_from_jd(cv, profile=profile)
            st.success("Updated rewrite templates for this job.")
            st.rerun()

    with c3:
        if st.button("Show saved analyses", key="jd_ml_show_saved", use_container_width=True):
            store = cv.get("jd_store", {})
            if not isinstance(store, dict) or not store:
                st.info("No saved jobs yet.")
            else:
                for h, a in list(store.items())[:12]:
                    cov = float((a or {}).get("coverage", 0.0) or 0.0) * 100
                    rh = (a or {}).get("role_hint", "")
                    st.write(f"- `{h}` • {cov:.1f}% • {rh}")
