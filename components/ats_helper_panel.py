# components/ats_helper_panel.py
from __future__ import annotations

from typing import Any, Dict, Optional

import streamlit as st

from utils import jd_optimizer
from utils.profiles import load_profile


def render_ats_helper_panel(
    cv: Dict[str, Any],
    key_prefix: str = "ats_help",
    profile: Optional[Dict[str, Any]] = None,
) -> None:
    """
    ATS Helper: verbs/templates/metrics/keywords from merged profile+libraries,
    and shows current JD analysis (coverage/missing) using the shared JD.
    """
    jd_optimizer.ensure_jd_state(cv)

    # Load profile if not provided
    if profile is None:
        pid = cv.get("ats_profile", "cyber_security")
        lang = cv.get("jd_lang", "en")
        try:
            profile = load_profile(pid, lang=lang)
        except Exception:
            profile = {"keywords": {}, "action_verbs": [], "metrics": [], "bullet_templates": []}

    st.subheader("ATS Helper (keywords • metrics • verbs • templates)")
    st.caption("Folosește Job Description-ul shared (dreapta). Aici vezi ce ai în profil + ce lipsește din CV.")

    # ensure analysis is up to date
    analysis = jd_optimizer.auto_update_on_change(cv, profile=profile)
    jd = jd_optimizer.get_current_jd(cv).strip()
    if not jd:
        st.info("Pune Job Description în panoul shared (dreapta) ca să apară analiza.")
        return

    coverage = float(analysis.get("coverage", 0.0) or 0.0) * 100.0
    st.markdown(f"**Coverage (top keywords):** **{coverage:.0f}%** • **Lang:** `{analysis.get('lang','en')}` • **Hash:** `{analysis.get('hash','')}`")

    col1, col2 = st.columns(2, gap="large")

    with col1:
        missing = (analysis.get("missing") or [])[:30]
        st.markdown("**Missing keywords (top):**")
        st.write(", ".join(missing) if missing else "—")

        cA, cB = st.columns(2)
        with cA:
            if st.button("Apply missing → Extra keywords", use_container_width=True, key=f"{key_prefix}_apply_missing"):
                jd_optimizer.apply_missing_to_extra_keywords(cv, limit=25)
                st.success("Applied into Modern → Extra keywords.")
                st.rerun()
        with cB:
            if st.button("Update rewrite templates", use_container_width=True, key=f"{key_prefix}_upd_templates"):
                jd_optimizer.update_rewrite_templates_from_jd(cv, profile=profile)
                st.success("Templates updated for this job.")
                st.rerun()

        st.markdown("---")
        st.markdown("**Active rewrite templates (for this job):**")
        templates = cv.get("ats_rewrite_templates_active", []) or []
        if templates:
            for t in templates[:12]:
                st.write("• " + str(t))
        else:
            st.caption("Nu există încă templates active. Apasă „Update rewrite templates”.")

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
        st.markdown("**Action verbs**")
        st.write(", ".join(list(verbs)[:40]) if verbs else "—")

        st.markdown("**Metrics ideas**")
        if metrics:
            for m in list(metrics)[:10]:
                st.write(f"• {m}")
        else:
            st.write("—")
