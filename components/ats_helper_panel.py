from __future__ import annotations

from typing import Any, Dict, Optional, List

import streamlit as st

from utils import jd_optimizer
from utils.profiles import load_profile


def render_ats_helper_panel(cv: Dict[str, Any], key_prefix: str = "ats_help", profile: Optional[Dict[str, Any]] = None) -> None:
    """
    ATS Helper: shows verbs/templates/metrics/keywords from merged profile+libraries.
    Uses ONE shared JD text managed by jd_optimizer (cv["job_description"]).
    """
    jd_optimizer.ensure_jd_state(cv)

    # Load profile if not provided (keeps app.py simpler)
    if profile is None:
        pid = cv.get("ats_profile", "cyber_security")
        lang = cv.get("jd_lang", "en")
        try:
            profile = load_profile(pid, lang=lang)
        except Exception:
            profile = {"keywords": {}, "action_verbs": [], "metrics": [], "bullet_templates": []}

    st.subheader("ATS Helper (keywords • metrics • verbs • templates)")
    st.caption("Folosește Job Description-ul shared. Poți auto-aplica keywords lipsă în Skills.")

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
            if (cv.get("job_description") or "").strip():
                st.success("Nice — no missing keywords detected (top set).")
            else:
                st.info("Paste JD în 'Job Description (shared)'.")

        if st.button("Auto-apply missing → Modern keywords", key=f"{key_prefix}_apply_kw", use_container_width=True):
            jd_optimizer.apply_auto_to_modern_skills(cv, analysis)
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
