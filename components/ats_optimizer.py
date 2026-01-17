import re
from collections import Counter
from typing import Dict, Any, Optional

import streamlit as st

# ------------------------------------------------------------
# V2: per-job persist + overlay auto-update (recommended)
# Requires: utils/jd_optimizer.py  (the file I gave you earlier)
# ------------------------------------------------------------
try:
    from utils.jd_optimizer import (
        analyze_job_description,
        ensure_jd_store,
        list_jobs,
        store_result,
        build_overlay_from_result,
        apply_overlay_to_cv,
    )
    _JD_OPT_AVAILABLE = True
except Exception:
    _JD_OPT_AVAILABLE = False


# ----------------------------
# Legacy helpers (simple ATS keyword match)
# ----------------------------
_STOPWORDS = set("""a about above after again against all am an and any are as at be because been before being below between both but by
can did do does doing down during each few for from further had has have having he her here hers herself him himself his how
i if in into is it its itself just me more most my myself no nor not of off on once only or other our ours ourselves out over
own same she should so some such than that the their theirs them themselves then there these they this those through to too
under until up very was we were what when where which while who whom why with you your yours yourself yourselves
""".split())

def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())

def _extract_keywords_simple(text: str, top_n: int = 30):
    """Simple keyword extraction (ATS-oriented): keeps tech tokens and longer words."""
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


# ----------------------------
# Legacy panel: render_ats_optimizer (keyword match)
# Kept for backward compatibility with older app usage
# ----------------------------
def render_ats_optimizer(cv: dict):
    st.subheader("ATS Optimizer (keyword match)")
    st.caption("Lipește job description-ul și vezi ce cuvinte cheie lipsesc din CV. (heuristic, offline)")

    cv["job_description"] = st.text_area(
        "Job description",
        value=cv.get("job_description", ""),
        height=220,
        key="ats_jd_legacy",
        placeholder="Paste aici anunțul de job..."
    )

    jd = (cv.get("job_description") or "").strip()
    if not jd:
        st.info("Adaugă un job description ca să vezi analiza.")
        return

    # Build a plain-text CV blob (Modern focus)
    cv_blob = "\n".join([
        cv.get("pozitie_vizata", ""),
        cv.get("rezumat", ""),
        "\n".join(cv.get("rezumat_bullets", []) or []),
        cv.get("modern_skills_headline", ""),
        cv.get("modern_tools", ""),
        cv.get("modern_certs", ""),
        cv.get("modern_keywords_extra", ""),
        "\n".join([f"{e.get('functie','')} {e.get('tehnologii','')} {e.get('activitati','')}"
                   for e in (cv.get("experienta") or []) if isinstance(e, dict)]),
        "\n".join([f"{e.get('titlu','') or e.get('calificare','')} {e.get('organizatie','') or e.get('institutie','')}"
                   for e in (cv.get("educatie") or []) if isinstance(e, dict)]),
    ])

    jd_kw = _extract_keywords_simple(jd, top_n=35)
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
    else:
        st.write(", ".join(missing))
        add = st.button("Adaugă missing keywords în 'Extra keywords'", type="primary", key="ats_add_missing_legacy")
        if add:
            existing = (cv.get("modern_keywords_extra") or "").strip()
            # keep newline style (your exporters expect newline sometimes)
            existing_lines = [x.strip() for x in existing.splitlines() if x.strip()]
            merged = existing_lines + missing[:25]
            # dedupe
            seen = set()
            out = []
            for x in merged:
                low = x.lower()
                if low in seen:
                    continue
                seen.add(low)
                out.append(x)
            cv["modern_keywords_extra"] = "\n".join(out).strip()
            st.success("Adăugat! Scroll la Skills ca să vezi câmpul actualizat.")
            st.rerun()

    st.divider()
    st.markdown(
        "**Recomandări rapide (ATS):**\n"
        "- 3–6 bullets per rol/proiect\n"
        "- verbe de acțiune + rezultate măsurabile\n"
        "- pune keywords relevante în Summary + Technical Skills\n"
        "- evită tabele/coloane în varianta Modern"
    )


# ----------------------------
# V2 panel: per-job persist + overlay auto-update (ML-ish heuristic)
# Exposed under the legacy name the app imports: render_jd_ml_offline_panel
# ----------------------------
def render_jd_ml_offline_panel(cv: dict, profile: Optional[Dict[str, Any]] = None):
    """
    Backward-compatible entry point (your app imports this).
    If utils/jd_optimizer.py exists -> uses V2.
    Else -> falls back to legacy render_ats_optimizer.
    """
    if not _JD_OPT_AVAILABLE:
        st.warning("JD Optimizer V2 indisponibil (utils/jd_optimizer.py missing/import error). Folosesc fallback legacy.")
        render_ats_optimizer(cv)
        return

    ensure_jd_store(cv)

    st.subheader("Job Description Analyzer (Offline) — per job + auto-update")

    if profile is None:
        # safe fallback (still works)
        profile = {"keywords": {}, "bullet_templates": []}

    # Saved jobs
    jobs = list_jobs(cv)
    active = cv.get("active_job_id", "")

    if jobs:
        labels = [j[0] for j in jobs]
        ids = [j[1] for j in jobs]
        idx = ids.index(active) if active in ids else 0

        pick = st.selectbox(
            "Saved Job Descriptions",
            options=list(range(len(jobs))),
            format_func=lambda i: labels[i],
            index=idx,
            key="jd_v2_pick_job",
        )
        cv["active_job_id"] = ids[pick]

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Load selected JD", use_container_width=True, key="jd_v2_load"):
                obj = cv.get("jd_store", {}).get(cv["active_job_id"], {})
                if isinstance(obj, dict):
                    cv["job_description"] = obj.get("jd_text", "")
                st.rerun()
        with c2:
            if st.button("Delete selected JD", use_container_width=True, key="jd_v2_delete"):
                cv.get("jd_store", {}).pop(cv["active_job_id"], None)
                cv["active_job_id"] = ""
                st.rerun()
    else:
        st.caption("No saved Job Descriptions yet.")

    st.markdown("---")

    cv.setdefault("job_description", "")
    lang_hint = st.selectbox(
        "Language hint",
        options=[("Auto", ""), ("English", "en"), ("Română", "ro")],
        format_func=lambda x: x[0],
        key="jd_v2_lang_hint",
    )[1]

    jd_text = st.text_area(
        "Paste Job Description (EN/RO)",
        value=cv.get("job_description", ""),
        height=240,
        key="jd_v2_text",
    )

    colA, colB, colC = st.columns([1, 1, 1.2])
    with colA:
        run = st.button("Analyze JD", type="primary", use_container_width=True, key="jd_v2_analyze")
    with colB:
        save = st.button("Save JD", use_container_width=True, key="jd_v2_save")
    with colC:
        apply_now = st.button("Apply overlay (auto-update)", use_container_width=True, key="jd_v2_apply")

    if run or save or apply_now:
        try:
            res = analyze_job_description(jd_text, profile=profile, lang_hint=(lang_hint or None))
            store_result(cv, res)
            cv["job_description"] = res.jd_text

            overlay = build_overlay_from_result(res)
            overlay["score"] = res.score

            # store overlay per job
            cv["jd_store"][res.job_id]["overlay"] = overlay

            if save:
                st.success(f"Saved JD: {res.job_id} | Lang: {res.lang} | Score: {res.score}/100")

            # Apply overlay:
            # 1) updates modern_keywords_extra
            # 2) makes templates available via cv['ats_job_overlay']
            if apply_now or run:
                apply_overlay_to_cv(cv, overlay)
                # also expose templates in a dedicated key used by rewrite UI
                cv["ats_rewrite_templates_active"] = overlay.get("templates_ranked", [])
                st.success(f"Overlay applied. Score: {res.score}/100. Keywords + templates updated.")

            st.rerun()

        except Exception as e:
            st.error(f"JD Analyzer error: {e}")

    # Show results for active job
    active_id = cv.get("active_job_id", "")
    obj = cv.get("jd_store", {}).get(active_id, {}) if active_id else {}
    if isinstance(obj, dict) and obj.get("result"):
        r = obj.get("result", {})
        score = int(r.get("score", 0) or 0)
        st.markdown("### Results")
        st.progress(score / 100.0)
        st.write(f"**ATS Match Score:** {score}/100")

        cov = r.get("coverage", {})
        if isinstance(cov, dict) and cov:
            st.markdown("**Coverage by bucket**")
            st.write({k: f"{int(float(v)*100)}%" for k, v in cov.items()})

        with st.expander("Suggested extra keywords", expanded=False):
            st.write(r.get("suggested_extra_keywords", []) or [])

        with st.expander("Suggested templates (ranked)", expanded=False):
            for t in (r.get("suggested_templates", []) or []):
                st.write(f"- {t}")


# Optional alias if you want to call explicitly
def render_jd_ml_offline_panel_v2(cv: dict, profile: Optional[Dict[str, Any]] = None):
    render_jd_ml_offline_panel(cv, profile=profile)
