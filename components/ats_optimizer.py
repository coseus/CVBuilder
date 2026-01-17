import re
from collections import Counter

import streamlit as st
from utils.jd_ml_offline import (
    extract_keywords,
    categorize_keywords,
    compute_coverage,
    build_technical_skills_lines_from_buckets,
    suggested_bullet_templates,
)

def render_jd_ml_offline_panel(cv: dict):
    st.subheader("Job Description Analyzer (Offline)")

    cv.setdefault("job_description", "")
    cv.setdefault("jd_role_hint", "security engineer")
    cv.setdefault("jd_keywords", [])
    cv.setdefault("jd_buckets", {})
    cv.setdefault("jd_missing", [])
    cv.setdefault("jd_coverage", 0.0)
    cv.setdefault("jd_templates", [])

    cv["jd_role_hint"] = st.selectbox(
        "Role hint",
        ["security engineer", "soc analyst", "penetration tester", "general cyber security"],
        index=["security engineer", "soc analyst", "penetration tester", "general cyber security"].index(cv.get("jd_role_hint","security engineer")),
        key="jd_role_hint"
    )

    cv["job_description"] = st.text_area(
        "Paste job description here",
        value=cv.get("job_description",""),
        height=220,
        key="jd_text"
    )

    colA, colB, colC = st.columns(3)
    with colA:
        run = st.button("Analyze JD", use_container_width=True)
    with colB:
        apply_skills = st.button("Apply → TECHNICAL SKILLS", use_container_width=True)
    with colC:
        apply_templates = st.button("Update rewrite templates", use_container_width=True)

    if run:
        kws = extract_keywords(cv["job_description"], max_keywords=60)
        kw_list = [k for k, _ in kws]

        buckets = categorize_keywords(kw_list)

        # Build a CV text blob to compare (simple but effective)
        cv_blob = []
        cv_blob.append(cv.get("rezumat",""))
        cv_blob.extend(cv.get("rezumat_bullets", []) if isinstance(cv.get("rezumat_bullets", []), list) else [])
        cv_blob.append(cv.get("modern_tools",""))
        cv_blob.append(cv.get("modern_keywords_extra",""))
        for e in cv.get("experienta", []) if isinstance(cv.get("experienta", []), list) else []:
            if isinstance(e, dict):
                cv_blob.append(e.get("functie",""))
                cv_blob.append(e.get("angajator",""))
                cv_blob.append(e.get("titlu",""))
                cv_blob.append(e.get("activitati",""))
                cv_blob.append(e.get("tehnologii",""))
        cv_text = "\n".join([str(x) for x in cv_blob if x])

        coverage, missing = compute_coverage(cv_text, kw_list[:40])  # focus on top 40

        cv["jd_keywords"] = kw_list
        cv["jd_buckets"] = buckets
        cv["jd_missing"] = missing
        cv["jd_coverage"] = coverage

        cv["jd_templates"] = suggested_bullet_templates(cv["jd_role_hint"], buckets)

        st.success(f"JD analyzed. Coverage: {coverage*100:.0f}%")

    # Display results if available
    if cv.get("jd_keywords"):
        st.markdown(f"**Coverage:** {cv.get('jd_coverage',0.0)*100:.0f}%")
        missing = cv.get("jd_missing", [])
        if missing:
            st.warning("Missing keywords (top): " + ", ".join(missing[:20]))
        else:
            st.success("No missing keywords detected in top set (great).")

        with st.expander("Top extracted keywords (preview)"):
            st.write(cv["jd_keywords"][:50])

        with st.expander("Categorized skills (preview)"):
            for cat, items in (cv.get("jd_buckets") or {}).items():
                if items:
                    st.write(f"**{cat}**: {', '.join(items[:15])}")

        with st.expander("Suggested rewrite templates (for this job)"):
            for t in cv.get("jd_templates", []):
                st.write("• " + t)

    # Apply buttons
    if apply_skills and cv.get("jd_buckets"):
        lines = build_technical_skills_lines_from_buckets(cv["jd_buckets"], cap_per_group=12)
        # Store as a dedicated field used by exporter for TECHNICAL SKILLS
        cv["technical_skills_lines"] = lines
        st.success("Applied → TECHNICAL SKILLS (temporary lines set).")

    if apply_templates and cv.get("jd_templates"):
        cv["ats_rewrite_templates_active"] = cv["jd_templates"]
        st.success("Updated rewrite templates for this job.")


_STOPWORDS = set("""a about above after again against all am an and any are as at be because been before being below between both but by
can did do does doing down during each few for from further had has have having he her here hers herself him himself his how
i if in into is it its itself just me more most my myself no nor not of off on once only or other our ours ourselves out over
own same she should so some such than that the their theirs them themselves then there these they this those through to too
under until up very was we were what when where which while who whom why with you your yours yourself yourselves
""".split())

def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())

def _extract_keywords(text: str, top_n: int = 30):
    """Simple keyword extraction (ATS-oriented): keeps tech tokens and longer words."""
    text = _normalize_text(text)
    # keep words + tech-ish tokens (c#, c++, .net, node.js, aws, etc.)
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

def render_ats_optimizer(cv):
    st.subheader("ATS Optimizer (keyword match)")
    st.caption("Lipește job description-ul și vezi ce cuvinte cheie lipsesc din CV. Nu e NLP 'magic'—e un ajutor practic pentru ATS.")

    cv['job_description'] = st.text_area(
        "Job description",
        value=cv.get('job_description', ''),
        height=220,
        key="ats_jd",
        placeholder="Paste aici anunțul de job..."
    )

    jd = (cv.get('job_description') or "").strip()
    if not jd:
        st.info("Adaugă un job description ca să vezi analiza.")
        return

    # Build a plain-text CV blob (Modern focus)
    cv_blob = "\n".join([
        cv.get('pozitie_vizata', ''),
        cv.get('rezumat', ''),
        cv.get('modern_skills_headline', ''),
        cv.get('modern_tools', ''),
        cv.get('modern_certs', ''),
        cv.get('modern_keywords_extra', ''),
        # experience/projects
        "\n".join([f"{e.get('functie','')} {e.get('tehnologii','')} {e.get('activitati','')}" for e in (cv.get('experienta') or [])]),
        # education (names help ATS)
        "\n".join([f"{e.get('calificare','')} {e.get('institutie','')}" for e in (cv.get('educatie') or [])]),
    ])

    jd_kw = _extract_keywords(jd, top_n=35)
    cv_text = _normalize_text(cv_blob)

    present = [k for k in jd_kw if k in cv_text]
    missing = [k for k in jd_kw if k not in cv_text]

    score = int(round(100 * (len(present) / max(1, len(jd_kw)))))
    cols = st.columns(3)
    cols[0].metric("JD keywords", len(jd_kw))
    cols[1].metric("Matched", len(present))
    cols[2].metric("Match %", f"{score}%")

    with st.expander("Matched keywords", expanded=False):
        st.write(", ".join(present) if present else "—")

    st.markdown("**Missing (candidates to add):**")
    if not missing:
        st.success("Arată bine — nu am găsit keywords lipsă (în top listă).")

    # Let user add missing keywords to 'modern_keywords_extra' with one click
    if missing:
        st.write(", ".join(missing))
        add = st.button("Adaugă missing keywords în 'Extra keywords'", type="primary")
        if add:
            existing = (cv.get('modern_keywords_extra') or "").strip()
            extra = ", ".join(missing[:25])
            cv['modern_keywords_extra'] = (existing + (", " if existing and extra else "") + extra).strip()
            st.success("Adăugat! Scroll la Skills ca să vezi câmpul actualizat.")
            st.rerun()

    st.divider()
    st.markdown("**Recomandări rapide (ATS):**\n- Țintește 3–6 bullets per proiect/rol\n- Folosește verbe de acțiune + rezultate măsurabile\n- Pune cele mai relevante keywords în Summary + Tools\n- Evită tabele/coloane în varianta Modern PDF/DOCX")
