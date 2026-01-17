# components/ats_optimizer.py
from __future__ import annotations

import streamlit as st
from typing import Any, Dict, List, Optional

from utils.jd_optimizer import (
    analyze_job_description,
    detect_lang,
    derive_role_hint_from_profile,
    job_hash,
    load_analysis,
)

# (păstrează restul importurilor tale existente pentru scoring etc.)


def _ensure_jd_defaults(cv: dict) -> None:
    cv.setdefault("job_description", "")
    cv.setdefault("jd_last_job_id", "")
    cv.setdefault("jd_last_profile_id", "")
    cv.setdefault("jd_last_lang", "")
    cv.setdefault("jd_last_role_hint", "")
    cv.setdefault("jd_store", {})  # persisted analyses


def render_jd_input_shared(cv: dict, profile: dict) -> Dict[str, Any]:
    """
    SINGLE source of truth for JD text. Everyone uses cv['job_description'].
    Also triggers analysis persistence per (profile, role_hint, jd_hash).
    """
    _ensure_jd_defaults(cv)

    st.subheader("ATS Optimizer (keyword match)")
    st.caption("Lipește job description-ul o singură dată. Restul panourilor îl folosesc automat (offline).")

    jd = st.text_area(
        "Job description (paste here)",
        value=cv.get("job_description", ""),
        height=220,
        key="jd_shared_textarea",
        placeholder="Paste job description here (EN/RO).",
    )

    # Keep in cv
    cv["job_description"] = jd

    lang = detect_lang(jd) if jd.strip() else (cv.get("jd_last_lang") or "en")
    role_hint = derive_role_hint_from_profile(profile)
    pid = (profile.get("id") or "").strip()
    jid = job_hash(jd, profile_id=pid, role_hint=role_hint) if jd.strip() else ""

    # If profile changed, we want analyzer to follow
    profile_changed = (cv.get("jd_last_profile_id") != pid)
    job_changed = (cv.get("jd_last_job_id") != jid)

    cv["jd_last_profile_id"] = pid
    cv["jd_last_lang"] = lang
    cv["jd_last_role_hint"] = role_hint

    analysis: Dict[str, Any] = {}
    if jd.strip():
        # Load cached if exists, else compute and persist
        cached = load_analysis(cv, jid) if jid else {}
        if cached and not profile_changed and not job_changed:
            analysis = cached
        else:
            analysis = analyze_job_description(cv, jd, profile, lang=lang, role_hint=role_hint)

        cv["jd_last_job_id"] = analysis.get("job_id", jid)

    # Small status line
    cols = st.columns(3)
    cols[0].markdown(f"**Detected language:** `{lang}`")
    cols[1].markdown(f"**Profile:** `{pid}`")
    cols[2].markdown(f"**Role hint:** `{role_hint}`")

    return analysis


def render_jd_ml_offline_panel(cv: dict, profile: dict) -> None:
    """
    Offline analyzer panel that reads from shared JD and shared analysis.
    """
    _ensure_jd_defaults(cv)

    st.subheader("Job Description Analyzer (Offline)")
    st.caption("Extrage keywords + coverage, salvează analiza per job (hash) și poate aplica automat în Skills / rewrite templates.")

    jd = cv.get("job_description", "").strip()
    if not jd:
        st.info("Paste a Job Description above (ATS Optimizer).")
        return

    pid = (profile.get("id") or "").strip()
    role_hint = derive_role_hint_from_profile(profile)
    jid = job_hash(jd, profile_id=pid, role_hint=role_hint)

    analysis = load_analysis(cv, jid) or analyze_job_description(cv, jd, profile)

    kws = analysis.get("keywords", [])
    st.markdown(f"**Extracted keywords:** {len(kws)}")
    if kws:
        st.write(", ".join(kws[:40]) + (" ..." if len(kws) > 40 else ""))

    # OPTIONAL: auto-apply buttons (safe, non-destructive)
    st.markdown("### Apply (optional)")
    c1, c2 = st.columns(2)

    with c1:
        if st.button("Append keywords to Modern → Keywords (extra)", use_container_width=True, key="jd_apply_keywords_extra"):
            existing = (cv.get("modern_keywords_extra") or "").strip()
            add = "\n".join(kws[:60])
            merged = "\n".join([x for x in [existing, add] if x]).strip()
            cv["modern_keywords_extra"] = merged
            st.success("Applied to modern_keywords_extra.")

    with c2:
        if st.button("Save as last JD analysis (persist)", use_container_width=True, key="jd_persist_ok"):
            cv["jd_last_job_id"] = analysis.get("job_id", jid)
            st.success("Saved. (Already persisted by default.)")


def render_ats_helper_panel(cv: dict, profile: dict) -> None:
    """
    Helper panel uses shared JD too. No extra textareas.
    """
    _ensure_jd_defaults(cv)

    st.subheader("ATS Helper (keywords • metrics • verbs • templates)")
    st.caption("Folosește automat Job Description-ul de mai sus + ATS Profile libraries.")

    jd = cv.get("job_description", "").strip()
    if not jd:
        st.info("Paste a Job Description above (ATS Optimizer).")
        return

    pid = (profile.get("id") or "").strip()
    role_hint = derive_role_hint_from_profile(profile)
    jid = job_hash(jd, profile_id=pid, role_hint=role_hint)
    analysis = load_analysis(cv, jid)

    # Fallback if missing
    if not analysis:
        analysis = analyze_job_description(cv, jd, profile)

    # Show suggestions from profile + analysis
    kws = analysis.get("keywords", [])
    verbs = profile.get("action_verbs", []) or []
    metrics = profile.get("metrics", []) or []
    tmpls = profile.get("bullet_templates", []) or []

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Keywords (top)**")
        st.write(", ".join(kws[:25]) if kws else "—")
    with c2:
        st.markdown("**Action verbs**")
        st.write(", ".join(verbs[:25]) if verbs else "—")
    with c3:
        st.markdown("**Metrics ideas**")
        st.write("\n".join([f"- {m}" for m in metrics[:8]]) if metrics else "—")

    with st.expander("Bullet templates", expanded=False):
        for t in tmpls[:10]:
            st.write(f"- {t}")


def render_ats_optimizer(cv: dict, profile: dict) -> None:
    """
    Your main entry from app.py.
    This now orchestrates: shared JD input -> analyzer -> helper.
    """
    analysis = render_jd_input_shared(cv, profile=profile)
    st.markdown("---")
    render_jd_ml_offline_panel(cv, profile=profile)
    st.markdown("---")
    render_ats_helper_panel(cv, profile=profile)
