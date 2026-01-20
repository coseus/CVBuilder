# components/ats_helper_panel.py
from __future__ import annotations

from typing import Any, Dict

import streamlit as st

from utils import jd_optimizer
from utils.profiles import load_profile


def render_ats_helper_panel(
    cv: Dict[str, Any],
    key_prefix: str = "ats_help",
    profile: Dict[str, Any] | None = None,
) -> None:
    """
    ATS Helper: shows verbs/templates/metrics/keywords from merged profile+libraries.
    Uses ONE shared JD text managed by jd_optimizer (cv["job_description"] / jd state).
    """

    # ✅ MUST be inside function (cv exists only at runtime)
    jd_optimizer.ensure_jd_state(cv)

    # Optional: auto-refresh analysis when JD changes (if implemented in jd_optimizer)
    # Safe-call: if function doesn't exist, it won't break.
    if hasattr(jd_optimizer, "auto_update_on_change"):
        try:
            jd_optimizer.auto_update_on_change(cv, profile=profile)
        except Exception:
            pass

    # Load profile if not provided (keeps app.py simpler)
    if profile is None:
        pid = (cv.get("ats_profile") or "cyber_security").strip() or "cyber_security"
        try:
            # Prefer current UI/export lang if you keep it in cv; fallback en
            lang = (cv.get("ui_lang") or cv.get("lang") or "en").strip().lower()
            if lang not in ("en", "ro"):
                lang = "en"
            profile = load_profile(pid, lang=lang)
        except Exception:
            profile = {"keywords": {}, "action_verbs": [], "metrics": [], "bullet_templates": []}

    st.subheader("ATS Helper (keywords • metrics • verbs • templates)")

    # -------- Shared JD input (single source of truth) --------
    # Uses jd_optimizer API if present; fallback to cv["job_description"]
    if hasattr(jd_optimizer, "get_current_jd"):
        jd_text = jd_optimizer.get_current_jd(cv) or ""
    else:
        jd_text = (cv.get("job_description") or "").strip()

    new_text = st.text_area(
        "Job Description (paste here) — used for keyword match + offline analyzer",
        value=jd_text,
        height=160,
        key=f"{key_prefix}_jd",
    )

    if new_text != jd_text:
        if hasattr(jd_optimizer, "set_current_jd"):
            jd_optimizer.set_current_jd(cv, new_text)
        else:
            cv["job_description"] = new_text

        # If analyzer supports update on set
        if hasattr(jd_optimizer, "auto_update_on_change"):
            try:
                jd_optimizer.auto_update_on_change(cv, profile=profile)
            except Exception:
                pass

    # -------- Analysis (coverage / missing keywords) --------
    if hasattr(jd_optimizer, "get_current_analysis"):
        analysis = jd_optimizer.get_current_analysis(cv) or {}
    else:
        analysis = {}

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown("**Coverage**")
        cov = analysis.get("coverage", 0)
        try:
            cov_val = float(cov)
        except Exception:
            cov_val = 0.0

        # Accept both 0..1 and 0..100
        if cov_val <= 1.0:
            cov_percent = cov_val * 100.0
        else:
            cov_percent = cov_val

        st.write(f"{cov_percent:.1f}% keywords found in CV")

        missing = (analysis.get("missing") or [])[:25]
        if missing:
            st.markdown("**Missing keywords (top)**")
            st.write(", ".join([str(x) for x in missing if str(x).strip()]))
        else:
            st.success("Nice — no missing keywords detected (top set).")

        if st.button(
            "Auto-apply missing → Modern keywords",
            key=f"{key_prefix}_apply_kw",
            use_container_width=True,
        ):
            if hasattr(jd_optimizer, "apply_auto_to_modern_skills"):
                jd_optimizer.apply_auto_to_modern_skills(cv, analysis)
            elif hasattr(jd_optimizer, "apply_missing_to_extra_keywords"):
                jd_optimizer.apply_missing_to_extra_keywords(cv, limit=25)
            else:
                # last-resort fallback
                cur = (cv.get("modern_keywords_extra") or "").strip()
                add = "\n".join([str(x) for x in missing if str(x).strip()])
                cv["modern_keywords_extra"] = (cur + ("\n" if cur and add else "") + add).strip()

            st.success("Applied into Modern → Keywords (extra).")
            st.rerun()

    with col2:
        kw = (profile or {}).get("keywords", {}) or {}
        st.markdown("**Profile keywords (merged libraries)**")
        for bucket in ["core", "technologies", "tools", "certifications", "frameworks", "soft_skills"]:
            vals = kw.get(bucket, [])
            if isinstance(vals, list) and vals:
                st.caption(bucket.replace("_", " ").title())
                st.write(", ".join([str(x) for x in vals[:30] if str(x).strip()]))

    st.markdown("---")

    # -------- verbs / metrics / templates --------
    verbs = (profile or {}).get("action_verbs", []) or []
    metrics = (profile or {}).get("metrics", []) or []
    templates = (profile or {}).get("bullet_templates", []) or []

    c3, c4, c5 = st.columns(3, gap="large")

    with c3:
        st.markdown("**Action verbs**")
        if verbs:
            st.write(", ".join([str(x) for x in list(verbs)[:50] if str(x).strip()]))
        else:
            st.info("No verbs available in this profile.")

    with c4:
        st.markdown("**Metrics ideas**")
        if metrics:
            for m in list(metrics)[:10]:
                m = str(m).strip()
                if m:
                    st.write(f"• {m}")
        else:
            st.info("No metrics available in this profile.")

    with c5:
        st.markdown("**Bullet templates**")
        if templates:
            for t in list(templates)[:6]:
                t = str(t).strip()
                if t:
                    st.write(f"• {t}")
        else:
            st.info("No templates available in this profile.")
