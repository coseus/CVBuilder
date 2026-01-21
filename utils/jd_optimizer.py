# utils/jd_optimizer.py
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Tuple


# =========================
# State (single source of truth)
# =========================

def ensure_jd_state(cv: Dict[str, Any]) -> None:
    """
    Ensures canonical keys exist in cv for JD handling.
    Canonical JD text key: cv["job_description"].
    Persistent analysis store: cv["jd_state"].
    Mirror quick fields: cv["jd_keywords"], cv["jd_present"], cv["jd_missing"], cv["jd_coverage"], cv["jd_lang"].
    """
    if not isinstance(cv, dict):
        return

    cv.setdefault("job_description", "")

    cv.setdefault("jd_state", {})
    if not isinstance(cv["jd_state"], dict):
        cv["jd_state"] = {}
    st = cv["jd_state"]

    st.setdefault("active_job_id", "")
    st.setdefault("jobs", {})  # job_id -> analysis dict
    if not isinstance(st["jobs"], dict):
        st["jobs"] = {}

    # user-selected hint (optional)
    cv.setdefault("jd_role_hint", "")

    # quick mirrors for UI
    cv.setdefault("jd_keywords", [])
    cv.setdefault("jd_present", [])
    cv.setdefault("jd_missing", [])
    cv.setdefault("jd_coverage", 0.0)
    cv.setdefault("jd_lang", "en")

    # templates for rewrite
    cv.setdefault("ats_rewrite_templates_active", [])


def get_current_jd(cv: Dict[str, Any]) -> str:
    ensure_jd_state(cv)
    return str(cv.get("job_description") or "")


def set_current_jd(cv: Dict[str, Any], text: str) -> None:
    ensure_jd_state(cv)
    cv["job_description"] = str(text or "")


def get_current_analysis(cv: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns active analysis if exists, else a safe empty analysis object.
    """
    ensure_jd_state(cv)
    st = cv["jd_state"]
    jid = st.get("active_job_id") or ""
    jobs = st.get("jobs") or {}
    if isinstance(jobs, dict) and jid and jid in jobs and isinstance(jobs[jid], dict):
        return jobs[jid]
    return {
        "hash": "",
        "lang": (cv.get("jd_lang") or "en"),
        "keywords": [],
        "present": [],
        "missing": [],
        "coverage": 0.0,
        "role_hint": (cv.get("jd_role_hint") or ""),
        "profile_id": "",
    }


# =========================
# Hash / persistence
# =========================

def job_hash(jd_text: str) -> str:
    s = (jd_text or "").strip().encode("utf-8")
    return hashlib.sha256(s).hexdigest()[:16]


def _persist_analysis(cv: Dict[str, Any], jid: str, analysis: Dict[str, Any]) -> None:
    ensure_jd_state(cv)
    st = cv["jd_state"]
    st["jobs"][jid] = analysis
    st["active_job_id"] = jid

    # mirror for fast UI
    cv["jd_keywords"] = analysis.get("keywords", [])
    cv["jd_present"] = analysis.get("present", [])
    cv["jd_missing"] = analysis.get("missing", [])
    cv["jd_coverage"] = float(analysis.get("coverage", 0.0) or 0.0)
    cv["jd_lang"] = analysis.get("lang", cv.get("jd_lang", "en"))


def _load_analysis(cv: Dict[str, Any], jid: str) -> Optional[Dict[str, Any]]:
    ensure_jd_state(cv)
    jobs = cv["jd_state"].get("jobs", {})
    if isinstance(jobs, dict):
        a = jobs.get(jid)
        return a if isinstance(a, dict) else None
    return None


# =========================
# Language detect + keyword extraction (offline)
# =========================

_STOP_EN = {
    "and","or","the","a","an","to","of","in","on","for","with","as","at","by","from","is","are","be","will","you",
    "we","our","your","this","that","these","those","it","they","their","them","us","who","what","when","where",
    "job","role","work","team","years","year","experience","skills","skill","responsibilities","responsibility",
    "requirements","preferred","nice","plus","must","should","able","ability",
}
_STOP_RO = {
    "si","sau","un","o","unei","ale","al","a","la","in","pe","pentru","cu","ca","din","este","sunt","fi","vei","voi",
    "tu","voi","noi","nostru","noastra","acest","aceasta","aceste","acestia",
    "job","rol","munca","echipa","ani","an","experienta","abilitati","competente","responsabilitati","responsabilitate",
    "cerinte","preferabil","obligatoriu","trebuie","capabil","abilitate",
}

_TECH_HINTS = {
    "c#", "c++", "go", "aws", "gcp", "azure", "siem", "soar", "edr", "xdr", "vpn", "lan", "wan", "sso", "mfa", "iam",
    "soc", "dfir", "waf", "ids", "ips", "api", "sql", "tcp", "udp",
}


def detect_lang(text: str) -> str:
    t = (text or "").lower()
    ro_hits = sum(1 for w in [" și ", " să ", "între", "cunoaștere", "responsabilită", "experiență", "competen"] if w in t)
    en_hits = sum(1 for w in ["responsibilities", "requirements", "experience", "skills", "ability"] if w in t)
    return "ro" if ro_hits > en_hits else "en"


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9][a-zA-Z0-9\+\#\.\-]{1,}", (text or "").lower())


def _ngrams(tokens: List[str], n: int) -> List[str]:
    out: List[str] = []
    for i in range(0, max(0, len(tokens) - n + 1)):
        out.append(" ".join(tokens[i:i+n]))
    return out


def _dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for it in items:
        s = (it or "").strip()
        if not s:
            continue
        k = s.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(s)
    return out


def extract_keywords(text: str, lang: str = "en", max_keywords: int = 70) -> List[str]:
    tokens = _tokenize(text)
    stop = _STOP_RO if lang == "ro" else _STOP_EN

    singles: List[str] = []
    for t in tokens:
        if t in stop:
            continue
        if re.fullmatch(r"\d+", t):
            continue
        if len(t) <= 2 and t not in _TECH_HINTS:
            continue
        singles.append(t)

    bigrams = [g for g in _ngrams(tokens, 2) if not any(w in stop for w in g.split())]
    trigrams = [g for g in _ngrams(tokens, 3) if not any(w in stop for w in g.split())]

    freq: Dict[str, int] = {}
    for cand in singles + bigrams + trigrams:
        freq[cand] = freq.get(cand, 0) + 1

    ranked = sorted(freq.items(), key=lambda kv: (kv[1], len(kv[0])), reverse=True)
    kws = [k for k, _ in ranked]

    cleaned: List[str] = []
    for k in kws:
        if len(k) > 42:
            continue
        if k.count(" ") >= 4:
            continue
        cleaned.append(k)

    return _dedupe_keep_order(cleaned)[:max_keywords]


# =========================
# CV blob + coverage
# =========================

def _build_cv_blob(cv: Dict[str, Any]) -> str:
    """
    Build a lowercase text blob from CV fields (ATS-friendly matching).
    Keep it fast + robust.
    """
    parts: List[str] = []

    def add(x: Any) -> None:
        if x is None:
            return
        if isinstance(x, str):
            if x.strip():
                parts.append(x)
            return
        if isinstance(x, list):
            for it in x:
                add(it)
            return
        if isinstance(x, dict):
            for _, v in x.items():
                add(v)
            return
        s = str(x).strip()
        if s:
            parts.append(s)

    # main fields
    add(cv.get("rezumat"))
    add(cv.get("rezumat_bullets"))
    add(cv.get("modern_skills_headline"))
    add(cv.get("modern_tools"))
    add(cv.get("modern_certs"))
    add(cv.get("modern_keywords_extra"))

    # experiences
    exps = cv.get("experienta", [])
    if isinstance(exps, list):
        for e in exps:
            if isinstance(e, dict):
                add(e.get("functie"))
                add(e.get("angajator"))
                add(e.get("activitati"))
                add(e.get("tehnologii"))
                add(e.get("link"))

    # education
    edu = cv.get("educatie", [])
    if isinstance(edu, list):
        for ed in edu:
            if isinstance(ed, dict):
                add(ed.get("titlu"))
                add(ed.get("organizatie"))
                add(ed.get("descriere"))

    return " \n ".join(parts).lower()


def _compute_coverage(cv_blob: str, keywords: List[str], top_n: int = 45) -> Tuple[float, List[str], List[str]]:
    """
    Coverage computed against top_n keywords (ATS-ish).
    Matching is substring-based (good enough offline).
    """
    kws = [k.strip() for k in keywords if str(k).strip()]
    kws = kws[:top_n]

    present: List[str] = []
    missing: List[str] = []

    for kw in kws:
        if kw.lower() in cv_blob:
            present.append(kw)
        else:
            missing.append(kw)

    coverage = (len(present) / max(1, len(kws))) if kws else 0.0
    return coverage, present, missing


# =========================
# Main analyze API (what components call)
# =========================

def analyze_jd(cv: Dict[str, Any], profile: Optional[Dict[str, Any]] = None, role_hint: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyze current JD in cv["job_description"], persist in cv["jd_state"] per hash.
    Returns analysis dict.
    """
    ensure_jd_state(cv)
    jd = (cv.get("job_description") or "").strip()
    if not jd:
        # reset mirrors but keep history
        cv["jd_keywords"] = []
        cv["jd_present"] = []
        cv["jd_missing"] = []
        cv["jd_coverage"] = 0.0
        return get_current_analysis(cv)

    lang = detect_lang(jd)
    cv["jd_lang"] = lang

    jid = job_hash(jd)

    # role hint
    rh = (role_hint if role_hint is not None else cv.get("jd_role_hint") or "").strip()
    cv["jd_role_hint"] = rh

    keywords = extract_keywords(jd, lang=lang, max_keywords=80)
    cv_blob = _build_cv_blob(cv)
    coverage, present, missing = _compute_coverage(cv_blob, keywords, top_n=45)

    analysis = {
        "hash": jid,
        "lang": lang,
        "keywords": keywords,
        "present": present,
        "missing": missing,
        "coverage": float(coverage),
        "role_hint": rh,
        "profile_id": (profile.get("id") if isinstance(profile, dict) else "") or "",
    }

    _persist_analysis(cv, jid, analysis)
    return analysis


def auto_update_on_change(cv: Dict[str, Any], profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    If JD changed, re-analyze automatically (persist by hash).
    If unchanged, hydrate mirrors from cached analysis.
    """
    ensure_jd_state(cv)
    jd = (cv.get("job_description") or "").strip()
    if not jd:
        return get_current_analysis(cv)

    jid = job_hash(jd)
    active = cv["jd_state"].get("active_job_id") or ""

    if active != jid:
        return analyze_jd(cv, profile=profile, role_hint=cv.get("jd_role_hint") or "")

    cached = _load_analysis(cv, jid)
    if cached:
        # hydrate mirrors (in case they got cleared)
        cv["jd_keywords"] = cached.get("keywords", [])
        cv["jd_present"] = cached.get("present", [])
        cv["jd_missing"] = cached.get("missing", [])
        cv["jd_coverage"] = float(cached.get("coverage", 0.0) or 0.0)
        cv["jd_lang"] = cached.get("lang", cv.get("jd_lang", "en"))
        return cached

    return analyze_jd(cv, profile=profile, role_hint=cv.get("jd_role_hint") or "")


# =========================
# Apply actions used by UI buttons
# =========================

def apply_missing_to_extra_keywords(cv: Dict[str, Any], limit: int = 25) -> None:
    ensure_jd_state(cv)
    missing = cv.get("jd_missing", []) or []
    if not missing:
        return

    existing = (cv.get("modern_keywords_extra") or "").strip()
    existing_items = [x.strip() for x in re.split(r"[\n,]+", existing) if x.strip()]

    add_items = [str(m).strip() for m in missing[:limit] if str(m).strip()]
    merged = _dedupe_keep_order(existing_items + add_items)

    # store nicely (comma separated)
    cv["modern_keywords_extra"] = ", ".join(merged)


def apply_auto_to_modern_skills(cv: Dict[str, Any], analysis: Dict[str, Any]) -> None:
    """
    Back-compat name used by some panels: apply extracted/missing into modern_keywords_extra.
    """
    if not isinstance(analysis, dict):
        analysis = get_current_analysis(cv)
    # default: apply missing
    missing = analysis.get("missing", []) or []
    cv.setdefault("jd_missing", missing)
    apply_missing_to_extra_keywords(cv, limit=25)


def update_rewrite_templates_from_jd(cv: Dict[str, Any], profile: Optional[Dict[str, Any]] = None) -> List[str]:
    """
    Create job-specific rewrite templates:
    - profile bullet_templates first (already merged by libraries in load_profile)
    - add a few JD-aware generic templates (EN/RO)
    Stored in cv["ats_rewrite_templates_active"].
    """
    ensure_jd_state(cv)
    lang = (cv.get("jd_lang") or "en").lower()
    role = (cv.get("jd_role_hint") or "").strip().lower()

    base: List[str] = []
    if isinstance(profile, dict):
        bt = profile.get("bullet_templates", [])
        if isinstance(bt, list):
            base.extend([str(x).strip() for x in bt if str(x).strip()])

    if lang == "ro":
        extra = [
            "Am implementat {control_or_feature} în {environment}; am îmbunătățit {metric} cu {value}.",
            "Am automatizat {process} folosind {tool_or_tech}; am redus efortul manual cu {value}.",
            "Am diagnosticat și remediat {issue}; am redus {metric} cu {value}.",
        ]
        if "soc" in role:
            extra.insert(0, "Am monitorizat alertele în {siem}; am triat incidentele și am escaladat conform playbook-urilor.")
        if "penetration" in role or "pentest" in role:
            extra.insert(0, "Am efectuat testare de penetrare pe {scope}; am identificat {vuln_type} și am livrat recomandări de remediere.")
    else:
        extra = [
            "Implemented {control_or_feature} across {environment}; improved {metric} by {value}.",
            "Automated {process} using {tool_or_tech}; reduced manual effort by {value}.",
            "Diagnosed and remediated {issue}; reduced {metric} by {value}.",
        ]
        if "soc" in role:
            extra.insert(0, "Monitored alerts in {siem}; triaged incidents and escalated per playbooks.")
        if "penetration" in role or "pentest" in role:
            extra.insert(0, "Performed penetration testing on {scope}; identified {vuln_type} and delivered remediation guidance.")

    out = _dedupe_keep_order(base + extra)[:25]
    cv["ats_rewrite_templates_active"] = out
    return out


def reset_ats_jd_only(cv: Dict[str, Any], keep_history: bool = True) -> None:
    """
    Reset only JD/ATS runtime fields. Does NOT touch experience/education.
    """
    ensure_jd_state(cv)
    cv["job_description"] = ""
    cv["jd_role_hint"] = ""
    cv["jd_keywords"] = []
    cv["jd_present"] = []
    cv["jd_missing"] = []
    cv["jd_coverage"] = 0.0
    cv["ats_rewrite_templates_active"] = []

    if not keep_history:
        cv["jd_state"] = {"active_job_id": "", "jobs": {}}


# =========================
# Optional export/import of jd_state
# =========================

def export_jd_state(cv: Dict[str, Any]) -> str:
    ensure_jd_state(cv)
    return json.dumps(cv.get("jd_state", {}), ensure_ascii=False, indent=2)


def import_jd_state(cv: Dict[str, Any], jd_state_json: str) -> None:
    ensure_jd_state(cv)
    try:
        obj = json.loads(jd_state_json or "{}")
        if isinstance(obj, dict):
            cv["jd_state"] = obj
    except Exception:
        pass
