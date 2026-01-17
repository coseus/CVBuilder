from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, Any

import streamlit as st

from utils.ats_scoring import compute_score

_STOPWORDS = set("""a about above after again against all am an and any are as at be because been before being below between both but by
can did do does doing down during each few for from further had has have having he her here hers herself him himself his how
i if in into is it its itself just me more most my myself no nor not of off on once only or other our ours ourselves out over
own same she should so some such than that the their theirs them themselves then there these they this those through to too
under until up very was we were what when where which while who whom why with you your yours yourself yourselves
""".split())


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def extract_jd_keywords(text: str, top_n: int = 35) -> List[str]:
    text = _normalize_text(text)
    tokens = re.findall(r"[a-z0-9][a-z0-9\+\#\.\-/]{1,}", text)
    cleaned = []
    for t in tokens:
        t = t.strip(".-/")
        if len(t) < 3:
            continue
        if t in _STOPWORDS:
            continue
        cleaned.append(t)
    return [w for w, _ in Counter(cleaned).most_common(top_n)]


def render_ats_score_dashboard(cv: Dict[str, Any], profile: Dict[str, Any]):
    st.subheader("ATS Score Dashboard")
    st.caption("Pragmatic scoring to help you improve readability for recruiters and match for ATS.")

    jd = (cv.get('job_description') or '').strip()
    jd_keywords = extract_jd_keywords(jd, top_n=35) if jd else []

    score = compute_score(cv, profile, jd_keywords)

    cols = st.columns(5)
    cols[0].metric("Overall", f"{score.overall}%")
    cols[1].metric("Profile keywords", f"{score.keyword_coverage}%")
    cols[2].metric("JD match", f"{score.jd_match}%")
    cols[3].metric("Metrics", f"{score.metrics_coverage}%")
    cols[4].metric("Verb variety", f"{score.verb_variety}%")

    st.progress(min(100, max(0, score.overall)))

    with st.expander("What to fix first", expanded=True):
        if score.completeness < 80:
            st.warning("Complete the basics: Name, Email, Phone, Summary, Skills, at least 1 experience/project.")
        if score.metrics_coverage < 50:
            st.info("Add numbers where possible: scope (assets/hosts/users), severity counts, time saved, MTTR, % reduction.")
        if score.verb_variety < 50:
            st.info("Vary bullet starting verbs. Aim for 6–12 unique verbs across the CV.")
        if jd and score.jd_match < 60:
            st.info("Add missing JD keywords naturally into Skills + bullets (avoid keyword spam).")

    if score.repeated_starting_verbs:
        with st.expander("Repeated starting verbs (3+ times)", expanded=False):
            for v, c in score.repeated_starting_verbs:
                st.write(f"- {v.title()} — {c} times")

    if score.bullets_missing_metrics:
        with st.expander("Bullets missing metrics (examples)", expanded=False):
            for b in score.bullets_missing_metrics:
                st.write(f"- {b}")
            st.caption("Tip: add one of: count, %, time, size, severity breakdown.")

    if score.missing_profile_keywords:
        with st.expander("Missing profile keywords (top)", expanded=False):
            st.write(", ".join(score.missing_profile_keywords[:40]) if score.missing_profile_keywords else "—")

    if jd and score.missing_jd_keywords:
        with st.expander("Missing JD keywords (top)", expanded=False):
            st.write(", ".join(score.missing_jd_keywords[:40]))
