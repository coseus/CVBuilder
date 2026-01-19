# components/ats_helper_panel.py
from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from utils import jd_optimizer


def render_ats_helper_panel(cv: Dict[str, Any], key_prefix: str = "ats_help") -> None:
    st.subheader("ATS Helper (keywords • metrics • verbs • templates)")
    st.caption("Folosește Job Description-ul shared. Aici vezi resursele din profil + ce a extras analyzer-ul.")

    jd_optimizer.ensure_jd_state(cv)
    jd_optimizer.auto_update_on_change(cv)

    lang = (cv.get("jd_lang") or "en").lower()
    jd = (cv.get("job_description") or "").strip()

    if not jd:
        st.info("Pune Job Description în panoul shared pentru a popula automat keywords/templates.")
        return

    cov = float(cv.get("jd_coverage", 0.0) or 0.0)
    st.markdown(f"**JD coverage (top keywords):** {cov*100:.0f}%")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Missing keywords (top 30):**")
        missing = (cv.get("jd_missing") or [])[:30]
        st.write(", ".join(missing) if missing else "—")

        if st.button("Apply missing → Modern: Extra keywords", use_container_width=True, key=f"{key_prefix}__apply_missing"):
            jd_optimizer.apply_missing_to_extra_keywords(cv, limit=25)
            st.success("Applied into Modern → Extra keywords.")
            st.rerun()

    with col2:
        st.markdown("**Active rewrite templates (for this job):**")
        templates = cv.get("ats_rewrite_templates_active", []) or []
        if not templates:
            st.caption("No active templates yet. Use JD Analyzer → Update rewrite templates.")
        else:
            for t in templates[:12]:
                st.write("• " + str(t))

        if st.button("Generate templates now (from JD + profile)", use_container_width=True, key=f"{key_prefix}__gen_templates"):
            jd_optimizer.update_rewrite_templates_from_jd(cv)
            st.success("Templates updated.")
            st.rerun()
