# components/ats_helper_panel.py
from __future__ import annotations

from typing import Any, Dict, Optional, List
import streamlit as st

from utils import jd_optimizer


def render_ats_helper_panel(
    cv: Dict[str, Any],
    key_prefix: str = "ats_help",
    profile: Optional[Dict[str, Any]] = None,
) -> None:
    """
    ATS Helper: verbs/templates/metrics/keywords + quick actions.
    Uses shared JD via jd_optimizer.
    """
    jd_optimizer.ensure_jd_state(cv)
    jd_optimizer.auto_update_on_change(cv, profile=profile)

    st.subheader("ATS Helper (keywords • metrics • verbs • templates)")
    st.caption("Folosește Job Description-ul shared. Aici vezi resursele din profil + ce a extras analyzer-ul.")

    jd = (cv.get("job_description") or "").strip()
    if not jd:
        st.info("Pune Job Description în panoul shared (dreapta) pentru a popula automat keywords/templates.")
        return

    a = jd_optimizer.get_current_analysis_or_blank(cv)
    cov = float(a.get("coverage", 0.0) or 0.0) * 100
    st.markdown(f"**JD coverage (top keywords):** {cov:.1f}%")

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("**Missing keywords (top 30)**")
        missing = (a.get("missing") or [])[:30]
        st.write(", ".join(missing) if missing else "—")

        if st.button(
            "Apply missing → Modern: Extra keywords",
            use_container_width=True,
            key=f"{key_prefix}__apply_missing",
        ):
            jd_optimizer.apply_missing_to_extra_keywords(cv, limit=25)
            st.success("Applied into Modern → Extra keywords.")
            st.rerun()

    with col2:
        st.markdown("**Active rewrite templates (for this job)**")
        templates = cv.get("ats_rewrite_templates_active", []) or []
        if not templates:
            st.caption("No active templates yet. Use JD Analyzer → Update rewrite templates.")
        else:
            for t in templates[:12]:
                st.write("• " + str(t))

        if st.button(
            "Generate templates now (from JD + profile)",
            use_container_width=True,
            key=f"{key_prefix}__gen_templates",
        ):
            jd_optimizer.update_rewrite_templates_from_jd(cv, profile=profile)
            st.success("Templates updated.")
            st.rerun()

    # Optional: show profile resources if provided
    if isinstance(profile, dict) and profile:
        st.markdown("---")
        c3, c4, c5 = st.columns(3, gap="large")

        verbs = profile.get("action_verbs", []) or []
        metrics = profile.get("metrics", []) or []
        bullets = profile.get("bullet_templates", []) or []

        with c3:
            st.markdown("**Action verbs**")
            st.write(", ".join([str(x) for x in verbs[:50]]) if verbs else "—")

        with c4:
            st.markdown("**Metrics ideas**")
            if metrics:
                for m in metrics[:10]:
                    st.write("• " + str(m))
            else:
                st.write("—")

        with c5:
            st.markdown("**Bullet templates**")
            if bullets:
                for b in bullets[:6]:
                    st.write("• " + str(b))
            else:
                st.write("—")
