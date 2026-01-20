# utils/jd_optimizer.py
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional


# ---------------------------
# State (persist in cv dict)
# ---------------------------
def ensure_jd_state(cv: dict) -> None:
    """
    Ensures CV dict contains the JD analyzer persistent state.
    Prevents AttributeError / KeyError across Streamlit reruns.
    """
    if not isinstance(cv, dict):
        return

    # Canonical JD text used everywhere
    cv.setdefault("job_description", "")

    # Persistent per-job analysis
    cv.setdefault("jd_state", {})
    st = cv["jd_state"]
    if not isinstance(st, dict):
        cv["jd_state"] = {}
        st = cv["jd_state"]

    st.setdefault("active_job_id", "")
    st.setdefault("jobs", {})  # job_id -> analysis dict
    st.setdefault("current_role_hint", "")


def job_hash(jd_text: str) -> str:
    s = (jd_text or "").strip().encode("utf-8")
    return hashlib.sha256(s).hexdigest()[:16]


def get_current_jd(cv: dict) -> str:
    ensure_jd_state(cv)
    return (cv.get("job_description") or "").strip()


def set_current_jd(cv: dict, text: str) -> None:
    ensure_jd_state(cv)
    cv["job_description"] = (text or "")


def set_current_role_hint(cv: dict, role_hint: str) -> None:
    ensure_jd_state(cv)
    cv["jd_state"]["current_role_hint"] = (role_hint or "").strip()


def get_current_analysis(cv: dict) -> Dict[str, Any]:
    """
    Returns analysis for active job (or empty analysis).
    Auto-runs analysis if JD exists but not analyzed yet.
    """
    ensure_jd_state(cv)
    jd = get_current_jd(cv)
    st = cv["jd_state"]

    if not jd.strip():
        return _empty_analysis()

    jid = job_hash(jd)
    jobs = st.get("jobs", {})
    if not isinstance(jobs, dict):
        st["jobs"] = {}
        jobs = st["jobs"]

    # if missing, analyze now
    if jid not in jobs:
        role_hint = st.get("current_role_hint", "") or ""
        jobs[jid] = analyze_jd(cv, role_hint=role_hint)
        st["active_job_id"] = jid

    # keep active aligned
    st["active_job_id"] = jid
    return jobs.get(jid) or _empty_analysis()


def auto_update_on_change(cv: dict, profile: Optional[dict] = None) -> None:
    """
    Safe to call on every rerun.
    If JD text changed => compute new hash => analyze/persist per job.
    """
    ensure_jd_state(cv)
    jd = get_current_jd(cv)
    if not jd:
        return

    jid = job_hash(jd)
    st = cv["jd_state"]
    jobs = st.get("jobs", {})
    if not isinstance(jobs, dict):
        st["jobs"] = {}
        jobs = st["jobs"]

    prev = st.get("active_job_id", "")

    # If already analyzed and active, nothing to do
    if prev == jid and jid in jobs:
        return

    role_hint = st.get("current_role_hint", "") or ""
    analysis = analyze_jd(cv, role_hint=role_hint, profile=profile)
    jobs[jid] = analysis
    st["active_job_id"] = jid


# ---------------------------
# Offline keyword extraction
# ---------------------------
_STOP_EN = {
    "and", "or", "the", "a", "an", "to", "of", "in", "on", "for", "with", "as", "at", "by", "from",
    "is", "are", "be", "will", "you", "we", "our", "your", "this", "that", "these", "those", "it",
    "they", "their", "them", "us", "who", "what", "when", "where",
    "job", "role", "work", "team", "years", "year", "experience", "skills", "skill",
    "responsibilities", "responsibility", "requirements", "required", "preferred",
}
_STOP_RO = {
    "si", "sau", "un", "o", "unei", "ale", "al", "a", "la", "in", "pe", "pentru", "cu", "ca", "din",
    "este", "sunt", "fi", "vei", "voi", "tu", "voi", "noi", "nostru", "noastra",
    "acest", "aceasta", "aceste", "acestia",
    "job", "rol", "munca", "echipa", "ani", "an", "experienta", "abilitati", "competente",
    "responsabilitati", "responsabilitate", "cerinte", "necesar", "preferabil",
}

_TECH_HINTS = {
    "c#", "c++", "go", "aws", "gcp", "azure", "siem", "soar", "edr", "xdr", "vpn", "lan", "wan",
    "sso", "mfa", "iam", "soc", "dfir", "waf", "ids", "ips", "api", "sql",
    "okta", "entra", "intune", "splunk", "sentinel", "crowdstrike",
}


def detect_lang(text: str) -> str:
    t = (text or "").lower()
    ro_hits = sum(1 for w in ["și", "să", "între", "cunoaștere", "responsabilități", "experiență", "competențe"] if w in t)
    en_hits = sum(1 for w in ["responsibilities", "requirements", "experience", "skills", "ability"] if w in t)
    return "ro" if ro_hits > en_hits else "en"


def _tokenize(text: str) -> List[str]:
    # tokens that keep +/#/./- for tech strings
    return re.findall(r"[a-zA-Z0-9][a-zA-Z0-9\+\#\.\-]{1,}", (text or "").lower())


def _ngrams(tokens: List[str], n: int) -> List[str]:
    out: List[str] = []
    for i in range(0, max(0, len(tokens) - n + 1)):
        out.append(" ".join(tokens[i:i + n]))
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


def _cv_text_blob(cv: dict) -> str:
    """
    Build a searchable text blob from CV fields (ATS-friendly).
    """
    parts: List[str] = []
    for key in [
        "nume_prenume", "pozitie_vizata", "profile_line",
        "modern_skills_headline", "modern_tools", "modern_certs", "modern_keywords_extra",
        "rezumat",  # legacy
    ]:
        v = cv.get(key)
        if isinstance(v, str) and v.strip():
            parts.append(v.strip())

    # summary bullets
    rb = cv.get("rezumat_bullets")
    if isinstance(rb, list):
        parts.extend([str(x).strip() for x in rb if str(x).strip()])

    # experience bullets
    exp = cv.get("experienta")
    if isinstance(exp, list):
        for it in exp:
            if not isinstance(it, dict):
                continue
            for k in ["titlu", "functie", "angajator", "tehnologii", "activitati", "locatie"]:
                vv = it.get(k)
                if isinstance(vv, str) and vv.strip():
                    parts.append(vv.strip())

    # education
    edu = cv.get("educatie")
    if isinstance(edu, list):
        for it in edu:
            if not isinstance(it, dict):
                continue
            for k in ["titlu", "organizatie", "descriere", "locatie"]:
                vv = it.get(k)
                if isinstance(vv, str) and vv.strip():
                    parts.append(vv.strip())

    return "\n".join(parts).lower()


def enrich_with_coverage(cv: dict, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Adds coverage/present/missing computed against current CV content.
    """
    if not isinstance(cv, dict) or not isinstance(analysis, dict):
        return analysis

    kws = analysis.get("keywords", [])
    if not isinstance(kws, list) or not kws:
        analysis["coverage"] = 0.0
        analysis["present"] = []
        analysis["missing"] = []
        return analysis

    blob = _cv_text_blob(cv)

    present: List[str] = []
    missing: List[str] = []
    for kw in kws:
        s = str(kw).strip()
        if not s:
            continue
        # simple contains; for multiword: contains phrase
        if s.lower() in blob:
            present.append(s)
        else:
            missing.append(s)

    present = _dedupe_keep_order(present)
    missing = _dedupe_keep_order(missing)

    total = max(1, len(present) + len(missing))
    analysis["present"] = present
    analysis["missing"] = missing
    analysis["coverage"] = (len(present) / total) * 100.0
    return analysis


def _empty_analysis() -> Dict[str, Any]:
    return {
        "hash": "",
        "job_id": "",
        "lang": "en",
        "keywords": [],
        "role_hint": "",
        "role_hints": [],
        "coverage": 0.0,
        "present": [],
        "missing": [],
        "profile_id": "",
    }


def _analyze_jd_text(jd_text: str, lang: str = "en", profile: Optional[dict] = None) -> Dict[str, Any]:
    kws = extract_keywords(jd_text, lang=lang, max_keywords=80)

    role_hints: List[str] = []
    if isinstance(profile, dict):
        jts = profile.get("job_titles")
        if isinstance(jts, list):
            role_hints = [str(x).strip() for x in jts if str(x).strip()][:12]

    if not role_hints:
        low = (jd_text or "").lower()
        if any(x in low for x in ["soc", "siem", "splunk", "sentinel"]):
            role_hints = ["soc analyst", "security analyst"]
        elif any(x in low for x in ["pentest", "penetration", "burp", "oscp"]):
            role_hints = ["penetration tester", "application security"]
        elif any(x in low for x in ["cloud", "aws", "azure", "gcp"]):
            role_hints = ["cloud engineer", "cloud security"]
        else:
            role_hints = ["general"]

    h = job_hash(jd_text)

    return {
        "hash": h,
        "job_id": h,
        "lang": lang,
        "keywords": kws,
        "role_hint": "",
        "role_hints": role_hints,
        "coverage": 0.0,
        "present": [],
        "missing": [],
        "profile_id": (profile.get("id") if isinstance(profile, dict) else "") or "",
    }


def analyze_jd(
    cv_or_text: Any,
    lang: str = "en",
    profile: Optional[dict] = None,
    role_hint: Optional[str] = None,
    jd_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Backward-compatible analyzer.

    Supports BOTH:
      A) analyze_jd(jd_text: str, lang="en", profile=profile, role_hint="...")
      B) analyze_jd(cv: dict, role_hint="...", profile=profile)   # legacy panels

    Returns dict including:
      hash, lang, keywords, coverage, present, missing, role_hint
    """
    # Case B: called with cv dict (legacy)
    if isinstance(cv_or_text, dict):
        cv = cv_or_text
        ensure_jd_state(cv)

        text = (jd_text if isinstance(jd_text, str) else get_current_jd(cv)).strip()
        if not text:
            return _empty_analysis()

        auto_lang = detect_lang(text)
        base = _analyze_jd_text(text, lang=auto_lang, profile=profile)

        rh = (role_hint or cv.get("jd_state", {}).get("current_role_hint") or "").strip()
        base["role_hint"] = rh
        if rh:
            # keep role_hints but prioritize selected one
            hints = [rh]
            for x in base.get("role_hints", []) or []:
                xs = str(x).strip()
                if xs and xs.lower() != rh.lower():
                    hints.append(xs)
            base["role_hints"] = hints[:12]

        # persist
        st = cv["jd_state"]
        jobs = st.get("jobs", {})
        if not isinstance(jobs, dict):
            st["jobs"] = {}
            jobs = st["jobs"]

        jobs[base["hash"]] = enrich_with_coverage(cv, base)
        st["active_job_id"] = base["hash"]
        if rh:
            st["current_role_hint"] = rh

        return jobs[base["hash"]]

    # Case A: called with raw text
    text = ""
    if isinstance(cv_or_text, str):
        text = cv_or_text
    elif isinstance(jd_text, str):
        text = jd_text
    text = (text or "").strip()
    if not text:
        return _empty_analysis()

    use_lang = lang if lang in ("en", "ro") else detect_lang(text)
    base = _analyze_jd_text(text, lang=use_lang, profile=profile)
    base["role_hint"] = (role_hint or "").strip()
    return base


# ---------------------------
# CV integration helpers
# ---------------------------
def apply_auto_to_modern_skills(cv: dict, analysis: dict) -> None:
    """
    Auto-apply missing keywords into modern_keywords_extra (newline separated).
    Keeps existing text; appends only new items; caps length.
    """
    if not isinstance(cv, dict) or not isinstance(analysis, dict):
        return

    missing = analysis.get("missing", [])
    if not isinstance(missing, list) or not missing:
        # fallback: use all keywords
        missing = analysis.get("keywords", [])
        if not isinstance(missing, list):
            return

    existing = (cv.get("modern_keywords_extra") or "").strip()
    existing_list = [x.strip() for x in existing.splitlines() if x.strip()]
    merged = _dedupe_keep_order(existing_list + [str(x).strip() for x in missing if str(x).strip()])

    cv["modern_keywords_extra"] = "\n".join(merged[:80])


# ---------------------------
# Optional: export/import state (debug)
# ---------------------------
def export_jd_state(cv: dict) -> str:
    ensure_jd_state(cv)
    return json.dumps(cv.get("jd_state", {}), ensure_ascii=False, indent=2)


def import_jd_state(cv: dict, jd_state_json: str) -> None:
    ensure_jd_state(cv)
    try:
        obj = json.loads(jd_state_json or "{}")
        if isinstance(obj, dict):
            cv["jd_state"] = obj
    except Exception:
        pass
