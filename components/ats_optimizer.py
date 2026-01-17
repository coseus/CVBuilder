from __future__ import annotations

import streamlit as st
from typing import Any, Dict, Optional

from utils.jd_optimizer import (
    analyze_job_description,
    ensure_jd_store,
    list_jobs,
    store_result,
    build_overlay_from_result,
    apply_overlay_to_cv,
)


def _safe_profile_title(profile: Dict[str, Any]) -> str:
    t = profile.get("title")
    if isinstance(t, dict):
        return t.get("en") or t.get("ro") or "ATS Profile"
    return str(t or "ATS Profile")


def render_ats_optimizer(cv: Dict[str, Any], profile: Optional[Dict[str, Any]] = None) -> None:
    """
    ATS Optimizer / JD Analyzer (offline).
    - Persist per job description (hash)
    - Auto-apply overlay to CV (keywords/templates per job)
    - EN/RO language auto-detect + optional override
    """
    ensure_jd_store(cv)

    st.subheader("ATS Optimizer (Offline) — Job Description Analyzer")

    if profile is None:
        st.info("Selectează un ATS profile ca să ai keyword bank relevant.")
        profile = {"keywords": {}, "bullet_templates": []}

    st.caption(f"Profile: {_safe_profile_title(profile)}")

    # Job selector
    jobs = list_jobs(cv)
    active = cv.get("active_job_id", "")

    if jobs:
        labels = [j[0] for j in jobs]
        ids = [j[1] for j in jobs]
        try:
            idx = ids.index(active) if active in ids else 0
        except Exception:
            idx = 0

        pick = st.selectbox("Saved Job Descriptions", options=list(range(len(jobs))), format_func=lambda i: labels[i], index=idx, key="ats_job_pick")
        cv["active_job_id"] = ids[pick]

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Load selected JD into editor", use_container_width=True, key="ats_load_jd"):
                obj = cv["jd_store"].get(cv["active_job_id"], {})
                if isinstance(obj, dict):
                    cv["job_description"] = obj.get("jd_text", "")
                st.rerun()

        with col_b:
            if st.button("Delete selected JD", use_container_width=True, key="ats_delete_jd"):
                cv["jd_store"].pop(cv["active_job_id"], None)
                cv["active_job_id"] = ""
                st.rerun()
    else:
        st.caption("No saved Job Descriptions yet.")

    st.markdown("---")

    # Editor
    cv.setdefault("job_description", "")
    lang_hint = st.selectbox(
        "Language hint (auto recommended)",
        options=[("Auto", ""), ("English", "en"), ("Română", "ro")],
        format_func=lambda x: x[0],
        key="ats_jd_lang_hint",
    )[1]

    jd_text = st.text_area(
        "Paste Job Description (EN/RO)",
        value=cv.get("job_description", ""),
        height=240,
        key="ats_jd_text",
        help="Offline analyzer: extrage keywords, calculează match score și creează overlay per job.",
    )

    col1, col2, col3 = st.columns([1, 1, 1.1], gap="small")

    with col1:
        run = st.button("Analyze JD", type="primary", use_container_width=True, key="ats_analyze_jd")
    with col2:
        save = st.button("Save JD", use_container_width=True, key="ats_save_jd")
    with col3:
        apply_now = st.button("Apply overlay to CV (auto-update)", use_container_width=True, key="ats_apply_overlay")

    if run or save or apply_now:
        try:
            res = analyze_job_description(jd_text, profile=profile, lang_hint=(lang_hint or None))
            store_result(cv, res)
            # persist the editor text
            cv["job_description"] = res.jd_text

            # build overlay and store
            overlay = build_overlay_from_result(res)
            overlay["score"] = res.score  # keep handy
            cv["jd_store"][res.job_id]["overlay"] = overlay

            if save:
                st.success(f"Saved JD: {res.job_id}  |  Lang: {res.lang}  |  Score: {res.score}/100")

            if apply_now or run:
                apply_overlay_to_cv(cv, overlay)
                st.success(f"Overlay applied. Score: {res.score}/100. Keywords updated for Modern ATS export.")

            st.rerun()

        except Exception as e:
            st.error(f"JD Analyzer error: {e}")

    # Show active job results
    active_id = cv.get("active_job_id", "")
    obj = cv.get("jd_store", {}).get(active_id, {}) if active_id else {}
    if isinstance(obj, dict) and obj.get("result"):
        r = obj.get("result", {})
        overlay = obj.get("overlay", {})

        st.markdown("### Results")
        score = int(r.get("score", 0) or 0)
        st.progress(score / 100.0)
        st.write(f"**ATS Match Score:** {score}/100")

        cov = r.get("coverage", {}) if isinstance(r.get("coverage", {}), dict) else {}
        if cov:
            st.markdown("**Coverage by bucket**")
            st.write({k: f"{int(v*100)}%" for k, v in cov.items()})

        matched = r.get("matched", {}) if isinstance(r.get("matched", {}), dict) else {}
        if matched:
            with st.expander("Matched keywords (by bucket)", expanded=False):
                for b, items in matched.items():
                    if items:
                        st.markdown(f"**{b}**")
                        st.write(items)

        extra = r.get("suggested_extra_keywords", [])
        if isinstance(extra, list) and extra:
            with st.expander("Suggested extra keywords (for ATS)", expanded=False):
                st.write(extra)

        tpls = r.get("suggested_templates", [])
        if isinstance(tpls, list) and tpls:
            with st.expander("Top templates (ranked)", expanded=False):
                for t in tpls:
                    st.write(f"- {t}")

        st.markdown("---")
        st.caption("Overlay is stored per job and applied into CV as `cv['ats_job_overlay']` + updates `modern_keywords_extra`.")
