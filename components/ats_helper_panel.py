import re
import streamlit as st


def _flatten_text_from_cv(cv: dict) -> str:
    parts = []
    for k in ["rezumat_bullets", "modern_skills_headline", "modern_tools", "modern_certs", "modern_keywords_extra"]:
        v = cv.get(k)
        if isinstance(v, list):
            parts.extend([str(x) for x in v])
        else:
            parts.append(str(v or ""))

    exp = cv.get("experienta", [])
    if isinstance(exp, list):
        for e in exp:
            if isinstance(e, dict):
                parts.append(str(e.get("titlu", "")))
                parts.append(str(e.get("functie", "")))
                parts.append(str(e.get("angajator", "")))
                parts.append(str(e.get("activitati", "")))

    edu = cv.get("educatie", [])
    if isinstance(edu, list):
        for ed in edu:
            if isinstance(ed, dict):
                parts.append(str(ed.get("titlu", "")))
                parts.append(str(ed.get("organizatie", "")))

    return "\n".join([p for p in parts if p.strip()])


def _has_metric(s: str) -> bool:
    return bool(re.search(r"(\d+(\.\d+)?)\s*(%|x|hrs?|hours?|days?|weeks?|months?|ms|s|sec|min|USD|\$|€|RON|k|K|M|million|bn|B)", s, re.IGNORECASE))


def render_ats_helper_panel(cv: dict, key_prefix: str = "ats_help"):
    """
    ATS utilities:
    - Uses shared cv['job_description'] (no extra paste)
    - Detect missing metrics in bullets
    - Action verb variety check
    - Templates quick view
    """
    st.subheader("ATS Helper (keywords • metrics • verbs • templates)")
    st.caption("Folosește Job Description deja lipit în celelalte panouri (shared).")

    jd = str(cv.get("job_description", "") or "")
    if jd.strip():
        with st.expander("Show current Job Description (shared)", expanded=False):
            st.code(jd[:4000] + ("..." if len(jd) > 4000 else ""))
    else:
        st.info("Nu există Job Description încă. Lipeste-l în ATS Optimizer / JD Analyzer.")

    cv_text = _flatten_text_from_cv(cv).lower()

    # Keywords: naive extraction (words >= 4) + filter
    words = re.findall(r"[a-zA-Z][a-zA-Z\+\#\.\-]{3,}", jd.lower()) if jd else []
    stop = {"with", "that", "this", "from", "will", "have", "your", "work", "team", "years", "year", "role"}
    kws = sorted(set([w for w in words if w not in stop]))[:200]

    if jd:
        matched = [k for k in kws if k in cv_text]
        missing = [k for k in kws if k not in cv_text]

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Matched keywords (top)**")
            st.write(", ".join(matched[:40]) if matched else "—")
        with c2:
            st.markdown("**Missing keywords (top)**")
            st.write(", ".join(missing[:40]) if missing else "—")

        score = int(100 * len(matched) / max(1, len(kws))) if kws else 0
        st.progress(score / 100.0)
        st.caption(f"Keyword coverage (rough): {score}%")

    # Metrics check
    st.markdown("### Metrics detector (bullets)")
    flagged = []

    for b in cv.get("rezumat_bullets", []) if isinstance(cv.get("rezumat_bullets", []), list) else []:
        if b and not _has_metric(b):
            flagged.append(("Summary", b))

    exp = cv.get("experienta", [])
    if isinstance(exp, list):
        for i, e in enumerate(exp):
            if not isinstance(e, dict):
                continue
            bullets = str(e.get("activitati", "")).splitlines()
            for line in bullets:
                line = line.strip().lstrip("-•* ").strip()
                if line and not _has_metric(line):
                    flagged.append((f"Experience #{i+1}", line))

    if flagged:
        st.warning(f"{len(flagged)} bullets without obvious metrics. Consider adding numbers (scale, %, time, cost, SLA).")
        for sec, line in flagged[:12]:
            st.write(f"- [{sec}] {line}")
    else:
        st.success("Great — most bullets include measurable impact (or look like they do).")

    # Verb variety
    st.markdown("### Action verb variety (quick scan)")
    verbs = re.findall(r"^\s*[-•*]?\s*([A-Za-z]+)\b", _flatten_text_from_cv(cv), re.MULTILINE)
    verbs = [v.lower() for v in verbs if len(v) > 2]
    top = {}
    for v in verbs:
        top[v] = top.get(v, 0) + 1
    common = sorted(top.items(), key=lambda x: x[1], reverse=True)[:8]
    if common:
        st.write("Most common starters:", ", ".join([f"{v}({n})" for v, n in common]))
        if common[0][1] >= 4:
            st.info("Tip: avoid repeating the same starter verb; rotate verbs to look stronger.")
    else:
        st.caption("No bullets detected yet.")

    st.markdown("### Bullet templates (copy/paste)")
    templates = [
        "Reduced [incident/latency/cost] by [X%] by implementing [control/tool/process].",
        "Hardened [system/network] by deploying [MFA/EDR/SIEM rule], improving [metric] from [A] to [B].",
        "Performed vulnerability assessments on [N assets], remediating [Y critical/high] issues within [T days].",
        "Automated [task] using [Python/PowerShell], saving [X hours/week] and reducing errors by [Y%].",
        "Built/maintained [infrastructure] for [N users/sites], achieving [SLA/uptime] of [X%].",
    ]
    for t in templates:
        st.code(t)
