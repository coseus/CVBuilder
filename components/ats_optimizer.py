import re
import hashlib
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st


# -------------------------
# Small utilities
# -------------------------
_STOPWORDS_EN = set("""
a about above after again against all am an and any are as at be because been before being below between both but by
can did do does doing down during each few for from further had has have having he her here hers herself him himself his how
i if in into is it its itself just me more most my myself no nor not of off on once only or other our ours ourselves out over
own same she should so some such than that the their theirs them themselves then there these they this those through to too
under until up very was we were what when where which while who whom why with you your yours yourself yourselves
""".split())

_STOPWORDS_RO = set("""
și si sau ori in în la pe cu din de a al ai ale alea unei unui un una unui unei care ce că ca pentru prin peste sub sus jos
este sunt era au avea aveați avem aveam voi tu el ea ei ele noi voi lor
""".split())

_TECH_KEEP = set([
    "c#", "c++", ".net", "node.js", "node", "aws", "azure", "gcp", "m365", "o365",
    "siem", "soc", "edr", "xdr", "iam", "sso", "mfa", "vpn", "vlan", "ad", "entra",
    "tcp", "udp", "dns", "dhcp", "http", "https", "ssh", "rdp", "sql", "linux", "windows",
])

def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())

def _job_hash(text: str) -> str:
    t = (text or "").strip().encode("utf-8", errors="ignore")
    return hashlib.sha256(t).hexdigest()[:12] if t else "nojd"

def _extract_keywords(text: str, top_n: int = 45) -> List[str]:
    """
    ATS-ish keyword extraction: keeps tech tokens and longer words.
    Works offline, fast, no ML deps.
    """
    text = _normalize_text(text)
    # keep words + tech-ish tokens (c#, c++, .net, node.js, aws, etc.)
    tokens = re.findall(r"[a-z0-9][a-z0-9\+\#\.\-/]{1,}", text)

    cleaned: List[str] = []
    for t in tokens:
        t = t.strip(".-/")
        if t in _TECH_KEEP:
            cleaned.append(t)
            continue
        if len(t) < 3:
            continue
        if t in _STOPWORDS_EN or t in _STOPWORDS_RO:
            continue
        cleaned.append(t)

    # frequency
    return [w for w, _ in Counter(cleaned).most_common(top_n)]

def _compute_coverage(cv_text: str, keywords: List[str]) -> Tuple[float, List[str], List[str]]:
    """
    Returns coverage, present, missing
    """
    cv_t = _normalize_text(cv_text)
    present = [k for k in keywords if k and k in cv_t]
    missing = [k for k in keywords if k and k not in cv_t]
    cov = len(present) / max(1, len(keywords))
    return cov, present, missing

def _build_cv_blob(cv: dict) -> str:
    """
    Build text blob from CV content (Modern focus).
    """
    parts: List[str] = []
    parts.append(str(cv.get("pozitie_vizata", "") or ""))
    parts.append(str(cv.get("profile_line", "") or ""))
    parts.append(str(cv.get("rezumat", "") or ""))

    bullets = cv.get("rezumat_bullets", [])
    if isinstance(bullets, list):
        parts.extend([str(x) for x in bullets if x])

    # Skills
    parts.append(str(cv.get("modern_skills_headline", "") or ""))
    parts.append(str(cv.get("modern_tools", "") or ""))
    parts.append(str(cv.get("modern_certs", "") or ""))
    parts.append(str(cv.get("modern_keywords_extra", "") or ""))

    # New structured technical skills lines (if you use them)
    tlines = cv.get("technical_skills_lines", [])
    if isinstance(tlines, list):
        parts.extend([str(x) for x in tlines if x])

    # Experience
    exp = cv.get("experienta", [])
    if isinstance(exp, list):
        for e in exp:
            if not isinstance(e, dict):
                continue
            parts.append(str(e.get("functie", "") or ""))
            parts.append(str(e.get("angajator", "") or ""))
            parts.append(str(e.get("titlu", "") or ""))
            parts.append(str(e.get("activitati", "") or ""))
            parts.append(str(e.get("tehnologii", "") or ""))

    # Education (your schema uses titlu/organizatie)
    edu = cv.get("educatie", [])
    if isinstance(edu, list):
        for ed in edu:
            if not isinstance(ed, dict):
                continue
            parts.append(str(ed.get("titlu", "") or ""))
            parts.append(str(ed.get("organizatie", "") or ""))

    return "\n".join([p for p in parts if p and str(p).strip()])


# -------------------------
# JD Analyzer (Offline) with per-job persistence
# -------------------------
def _init_jd_state(cv: dict) -> None:
    cv.setdefault("job_description", "")
    cv.setdefault("jd_role_hint", "security engineer")
    cv.setdefault("jd_store", {})  # {job_hash: {...analysis...}}
    cv.setdefault("jd_active_hash", "nojd")

def _persist_analysis(cv: dict, h: str, analysis: dict) -> None:
    store = cv.get("jd_store")
    if not isinstance(store, dict):
        store = {}
        cv["jd_store"] = store
    store[h] = analysis
    cv["jd_active_hash"] = h

def _load_analysis(cv: dict, h: str) -> Optional[dict]:
    store = cv.get("jd_store")
    if isinstance(store, dict):
        return store.get(h)
    return None

def render_jd_ml_offline_panel(cv: dict, profile: Optional[dict] = None) -> None:
    """
    Offline "ML-like" panel: extract keywords -> compute coverage -> persist per job hash.
    """
    _init_jd_state(cv)

    st.subheader("Job Description Analyzer (Offline)")
    st.caption("Extrage keywords + coverage, salvează analiza per job (hash) și poate aplica automat în Skills / rewrite templates.")

    # Role hint (affects templates, optional)
    role_options = ["security engineer", "soc analyst", "penetration tester", "general cyber security"]
    current = cv.get("jd_role_hint", role_options[0])
    if current not in role_options:
        current = role_options[0]
    cv["jd_role_hint"] = st.selectbox("Role hint", role_options, index=role_options.index(current), key="jd_role_hint")

    # JD text
    cv["job_description"] = st.text_area(
        "Paste job description here",
        value=cv.get("job_description", ""),
        height=220,
        key="jd_text",
        placeholder="Paste job description (EN/RO)..."
    )

    jd = (cv.get("job_description") or "").strip()
    h = _job_hash(jd)
    cv["jd_active_hash"] = h

    colA, colB, colC, colD = st.columns([1,1,1,1])
    with colA:
        run = st.button("Analyze JD", use_container_width=True, key="jd_run")
    with colB:
        apply_missing = st.button("Apply missing → Extra keywords", use_container_width=True, key="jd_apply_missing")
    with colC:
        apply_templates = st.button("Update rewrite templates", use_container_width=True, key="jd_apply_templates")
    with colD:
        reset_jd = st.button("Reset only JD/ATS", use_container_width=True, key="jd_reset_only")

    if reset_jd:
        # do NOT delete exp/edu; only JD/ATS runtime + per-job store if you want
        cv["job_description"] = ""
        cv["jd_active_hash"] = "nojd"
        # Keep store (history) by default; if you want wipe store too, uncomment:
        # cv["jd_store"] = {}
        # Clear fields used by optimizer
        for k in ["jd_keywords", "jd_missing", "jd_present", "jd_coverage"]:
            cv.pop(k, None)
        st.success("Reset JD/ATS fields (experience/education NOT touched).")
        st.rerun()

    if not jd and not run:
        st.info("Pune un job description și apasă Analyze.")
        # show last analysis if exists for active hash
        return

    if run:
        keywords = _extract_keywords(jd, top_n=60)
        cv_blob = _build_cv_blob(cv)
        coverage, present, missing = _compute_coverage(cv_blob, keywords[:45])

        analysis = {
            "hash": h,
            "keywords": keywords,
            "present": present,
            "missing": missing,
            "coverage": coverage,
            "role_hint": cv.get("jd_role_hint", ""),
        }
        _persist_analysis(cv, h, analysis)

        # mirror some fields for quick UI
        cv["jd_keywords"] = keywords
        cv["jd_present"] = present
        cv["jd_missing"] = missing
        cv["jd_coverage"] = coverage

        st.success(f"JD analyzed. Coverage: {coverage*100:.0f}% (job hash: {h})")

    # Load existing analysis (if already analyzed)
    analysis = _load_analysis(cv, h)
    if analysis and not cv.get("jd_keywords"):
        # hydrate
        cv["jd_keywords"] = analysis.get("keywords", [])
        cv["jd_present"] = analysis.get("present", [])
        cv["jd_missing"] = analysis.get("missing", [])
        cv["jd_coverage"] = analysis.get("coverage", 0.0)

    if cv.get("jd_keywords"):
        st.markdown(f"**Coverage:** {float(cv.get('jd_coverage',0.0))*100:.0f}%")
        missing = cv.get("jd_missing", []) or []
        if missing:
            st.warning("Missing keywords (top): " + ", ".join(missing[:20]))
        else:
            st.success("No missing keywords detected in top set (nice).")

        with st.expander("Top extracted keywords"):
            st.write((cv.get("jd_keywords") or [])[:60])

        with st.expander("Matched keywords"):
            st.write((cv.get("jd_present") or [])[:60] or "—")

    if apply_missing:
        missing = cv.get("jd_missing", []) or []
        if not missing:
            st.info("No missing keywords to apply.")
        else:
            existing = (cv.get("modern_keywords_extra") or "").strip()
            # keep it tidy
            add = ", ".join(missing[:25])
            cv["modern_keywords_extra"] = (existing + (", " if existing and add else "") + add).strip()
            st.success("Applied missing keywords into Modern → Extra keywords.")
            st.rerun()

    if apply_templates:
        # basic role-based templates; you can later replace with your jd_optimizer templates
        role = (cv.get("jd_role_hint") or "").lower()
        base = [
            "Implemented {control_or_feature} across {environment}; improved security posture and documented SOPs.",
            "Automated {process} using {tool_or_tech}; reduced {metric} by {value}.",
            "Investigated {incident_type} using {tool}; contained impact and produced post-incident report.",
        ]
        if "penetration" in role:
            base.insert(0, "Performed penetration testing on {scope}; identified {vuln_type} and delivered remediation guidance.")
        if "soc" in role:
            base.insert(0, "Monitored alerts in {siem}; triaged incidents and escalated per playbooks.")
        cv["ats_rewrite_templates_active"] = base
        st.success("Rewrite templates updated for this job (stored in cv['ats_rewrite_templates_active']).")
        st.rerun()


# -------------------------
# Classic ATS Optimizer (keyword match)
# -------------------------
def render_ats_optimizer(cv: dict, profile: Optional[dict] = None) -> None:
    """
    Backward/forward compatible.
    - accepts profile=... even if not used
    - shows simple keyword match and allows one-click apply
    """
    st.subheader("ATS Optimizer (keyword match)")
    st.caption("Lipește job description-ul și vezi ce keywords lipsesc din CV. Offline, rapid, ATS-friendly.")

    cv.setdefault("job_description", "")
    cv["job_description"] = st.text_area(
        "Job description",
        value=cv.get("job_description", ""),
        height=220,
        key="ats_jd",
        placeholder="Paste aici anunțul de job..."
    )

    jd = (cv.get("job_description") or "").strip()
    if not jd:
        st.info("Adaugă un job description ca să vezi analiza.")
        return

    jd_kw = _extract_keywords(jd, top_n=45)
    cv_blob = _build_cv_blob(cv)
    coverage, present, missing = _compute_coverage(cv_blob, jd_kw)

    score = int(round(coverage * 100))
    cols = st.columns(3)
    cols[0].metric("JD keywords", len(jd_kw))
    cols[1].metric("Matched", len(present))
    cols[2].metric("Match %", f"{score}%")

    with st.expander("Matched keywords", expanded=False):
        st.write(", ".join(present) if present else "—")

    st.markdown("**Missing (candidates to add):**")
    if not missing:
        st.success("Arată bine — nu am găsit keywords lipsă (în top listă).")
        return

    st.write(", ".join(missing))

    add = st.button("Adaugă missing keywords în 'Extra keywords'", type="primary", key="ats_add_missing")
    if add:
        existing = (cv.get("modern_keywords_extra") or "").strip()
        extra = ", ".join(missing[:25])
        cv["modern_keywords_extra"] = (existing + (", " if existing and extra else "") + extra).strip()
        st.success("Adăugat! Scroll la Skills ca să vezi câmpul actualizat.")
        st.rerun()
