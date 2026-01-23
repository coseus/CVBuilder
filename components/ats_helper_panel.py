# components/ats_helper_panel.py
from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from utils import jd_optimizer
from utils.profiles import load_profile


def render_ats_helper_panel(
    cv: Dict[str, Any],
    key_prefix: str = "ats_help",
    profile: Dict[str, Any] | None = None,
):
    """
    ATS Helper: keywords / metrics / verbs / templates (merged from profile + libraries).
    Uses ONE shared JD text managed by utils.jd_optimizer (cv["job_description"]).
    """
    jd_optimizer.ensure_jd_state(cv)

    # Load profile if not provided
    if profile is None:
        pid = cv.get("ats_profile", "cyber_security")
        lang = cv.get("jd_lang") or "en"
        try:
            profile = load_profile(pid, lang=lang)
        except Exception:
            profile = {"keywords": {}, "action_verbs": [], "metrics": [], "bullet_templates": []}

    st.subheader("ATS Helper (keywords • metrics • verbs • templates)")

    # ONE shared JD input
    jd_text = jd_optimizer.get_current_jd(cv)
    new_text = st.text_area(
        "Job Description (paste here) — used for keyword match + offline analyzer",
        value=jd_text,
        height=160,
        key=f"{key_prefix}_jd",
    )
    if new_text != jd_text:
        jd_optimizer.set_current_jd(cv, new_text)

    # ensure analysis up to date
    jd_optimizer.auto_update_on_change(cv, profile=profile)
    analysis = jd_optimizer.get_current_analysis(cv)

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown("**Coverage**")
        st.write(f"{analysis.get('coverage', 0):.1f}% keywords found in CV")

        missing = analysis.get("missing", [])[:25]
        if missing:
            st.markdown("**Missing keywords (top)**")
            st.write(", ".join(missing))
        else:
            st.success("Nice — no missing keywords detected (top set).")

        if st.button("Auto-apply missing → Modern keywords", key=f"{key_prefix}_apply_kw", use_container_width=True):
            jd_optimizer.apply_auto_to_modern_skills(cv, analysis, limit=80)
            st.success("Applied into Modern → Keywords (extra).")
            st.rerun()

    with col2:
        kw = (profile or {}).get("keywords", {}) or {}
        st.markdown("**Profile keywords (merged libraries)**")
        for bucket in ["core", "technologies", "tools", "certifications", "frameworks", "soft_skills"]:
            vals = kw.get(bucket, [])
            if isinstance(vals, list) and vals:
                st.caption(bucket.replace("_", " ").title())
                st.write(", ".join(vals[:30]))

    st.markdown("---")

    verbs = (profile or {}).get("action_verbs", []) or []
    metrics = (profile or {}).get("metrics", []) or []
    templates = (profile or {}).get("bullet_templates", []) or []

    c3, c4, c5 = st.columns(3, gap="large")
    with c3:
        st.markdown("**Action verbs**")
        st.write(", ".join(list(verbs)[:50]) if verbs else "—")

    with c4:
        st.markdown("**Metrics ideas**")
        if metrics:
            for m in list(metrics)[:10]:
                st.write(f"• {m}")
        else:
            st.write("—")

    with c5:
        st.markdown("**Bullet templates**")
        if templates:
            for t in list(templates)[:6]:
                st.write(f"• {t}")
        else:
            st.write("—")
