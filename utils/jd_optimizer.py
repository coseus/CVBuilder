# utils/jd_optimizer.py
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

"""
CVBuilder — Job Description optimizer (offline)

Goals:
- ONE shared Job Description text (cv["job_description"]) used by:
  * ATS Optimizer (keyword match)
  * Job Description Analyzer (Offline)
  * ATS Helper Panel
  * ATS Score Dashboard

- Persist analyses per job (hash) in cv["jd_state"]["jobs"][job_id]
- Provide stable API used by components (no AttributeError surprises)
- EN/RO keyword extraction (lightweight, fully offline)
"""

# ---------------------------
# State management
# ---------------------------

CANONICAL_JD_KEY = "job_description"   # single source of truth
LEGACY_JD_KEYS = ("jd_text", "jd", "job_desc")


def ensure_jd_state(cv: dict) -> None:
    """Ensure JD keys exist in the CV dict (safe across reruns/imports)."""
    if not isinstance(cv, dict):
        return

    # Canonical JD
    if CANONICAL_JD_KEY not in cv:
        # back-compat: try to pull from older keys
        for k in LEGACY_JD_KEYS:
            if isinstance(cv.get(k), str) and cv.get(k).strip():
                cv[CANONICAL_JD_KEY] = cv.get(k, "")
                break
        else:
            cv[CANONICAL_JD_KEY] = ""

    # Persistent analyzer state
    st = cv.setdefault("jd_state", {})
    if not isinstance(st, dict):
        cv["jd_state"] = {}
        st = cv["jd_state"]

    st.setdefault("active_job_id", "")
    st.setdefault("jobs", {})  # job_id -> analysis dict
    st.setdefault("last_jd_hash", "")
    st.setdefault("current_role_hint", "")
    st.setdefault("last_updated_utc", "")


def get_current_jd(cv: dict) -> str:
    ensure_jd_state(cv)
    return str(cv.get(CANONICAL_JD_KEY) or "")


def set_current_jd(cv: dict, jd_text: str) -> None:
    ensure_jd_state(cv)
    cv[CANONICAL_JD_KEY] = jd_text or ""


def job_hash(jd_text: str) -> str:
    """Stable hash for a JD (used as job_id)."""
    s = (jd_text or "").strip().encode("utf-8")
    return hashlib.sha256(s).hexdigest()[:16]


def get_current_analysis(cv: dict) -> Dict[str, Any]:
    """
    Returns current analysis (for active job), or a default empty analysis dict.
    Components rely on keys: coverage, missing, present, keywords, hash, lang.
    """
    ensure_jd_state(cv)
    st = cv["jd_state"]
    jid = st.get("active_job_id") or ""
    jobs = st.get("jobs", {}) if isinstance(st.get("jobs", {}), dict) else {}
    if jid and jid in jobs and isinstance(jobs[jid], dict):
        return jobs[jid]
    # default
    return {
        "hash": "",
        "lang": "en",
        "keywords": [],
        "present": [],
        "missing": [],
        "coverage": 0.0,
        "role_hint": st.get("current_role_hint", "") or "",
        "created_utc": "",
        "profile_id": "",
        "domain": "",
    }


def get_active_analysis(cv: dict) -> Optional[Dict[str, Any]]:
    a = get_current_analysis(cv)
    return a if a.get("hash") else None


# ---------------------------
# Language + keyword extraction (offline)
# ---------------------------

_STOP_EN = {
    "and","or","the","a","an","to","of","in","on","for","with","as","at","by","from","is","are","be","will","you",
    "we","our","your","this","that","these","those","it","they","their","them","us","who","what","when","where",
    "job","role","work","team","years","year","experience","skills","skill","responsibilities","responsibility",
    "requirements","required","preferred","nice","plus",
}
_STOP_RO = {
    "si","și","sau","un","o","unei","ale","al","a","la","in","în","pe","pentru","cu","ca","din","este","sunt","fi",
    "vei","voi","tu","voi","noi","nostru","noastra","acest","aceasta","aceste","acestia",
    "job","rol","munca","echipa","ani","an","experienta","experiență","abilitati","abilități","competente","competențe",
    "responsabilitati","responsabilități","responsabilitate",
}

# Keep short tech tokens even if length <= 2
_TECH_HINTS = {
    "c#", "c++", "go", "aws", "gcp", "azure", "siem", "soar", "edr", "xdr", "vpn", "lan", "wan",
    "sso", "mfa", "iam", "soc", "dfir", "waf", "ids", "ips", "api", "sql", "ssh", "tls", "ssl",
}

_RE_WORD = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9\+\#\.\-]{1,}")


def detect_lang(text: str) -> str:
    """Tiny offline heuristic: returns 'ro' or 'en'."""
    t = (text or "").lower()
    ro_hits = sum(1 for w in [" și ", " să ", "între", "cunoaștere", "responsabilită", "experiență", "competențe"] if w in t)
    en_hits = sum(1 for w in ["responsibilities", "requirements", "experience", "skills", "ability"] if w in t)
    return "ro" if ro_hits > en_hits else "en"


def _tokenize(text: str) -> List[str]:
    return [m.group(0).lower() for m in _RE_WORD.finditer(text or "")]


def _ngrams(tokens: List[str], n: int) -> List[str]:
    if n <= 1:
        return tokens
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
    """
    Offline keyword extraction:
    - keep single tokens + 2/3-grams
    - frequency-based ranking
    - basic stopword filtering
    """
    tokens = _tokenize(text)
    stop = _STOP_RO if lang == "ro" else _STOP_EN

    singles: List[str] = []
    for t in tokens:
        if t in stop:
            continue
        if len(t) <= 2 and t not in _TECH_HINTS:
            continue
        if re.fullmatch(r"\d+", t):
            continue
        singles.append(t)

    bigrams = [g for g in _ngrams(tokens, 2) if not any(w in stop for w in g.split())]
    trigrams = [g for g in _ngrams(tokens, 3) if not any(w in stop for w in g.split())]

    # score by frequency + prefer longer phrases for ties
    freq: Dict[str, int] = {}
    for cand in singles + bigrams + trigrams:
        freq[cand] = freq.get(cand, 0) + 1

    ranked = sorted(freq.items(), key=lambda kv: (kv[1], len(kv[0])), reverse=True)
    kws = [k for k, _ in ranked]

    cleaned: List[str] = []
    for k in kws:
        if len(k) > 44:
            continue
        if k.count(" ") >= 4:
            continue
        cleaned.append(k)

    return _dedupe_keep_order(cleaned)[:max_keywords]


# ---------------------------
# CV text for matching (ATS)
# ---------------------------

def _cv_text_for_matching(cv: dict) -> str:
    """Build a plain text representation of CV for keyword matching (ATS-friendly)."""
    parts: List[str] = []
    for k in ("nume_prenume","pozitie_vizata","rezumat","modern_skills_headline","modern_tools","modern_certs","modern_keywords_extra"):
        v = cv.get(k)
        if isinstance(v, str) and v.strip():
            parts.append(v)

    bullets = cv.get("rezumat_bullets", [])
    if isinstance(bullets, list):
        for b in bullets:
            s = str(b).strip()
            if s:
                parts.append(s)

    exp = cv.get("experienta", [])
    if isinstance(exp, list):
        for e in exp:
            if not isinstance(e, dict):
                continue
            for kk in ("functie","angajator","titlu","perioada","tehnologii","activitati"):
                v = e.get(kk)
                if isinstance(v, str) and v.strip():
                    parts.append(v)

    edu = cv.get("educatie", [])
    if isinstance(edu, list):
        for e in edu:
            if not isinstance(e, dict):
                continue
            for kk in ("titlu","organizatie","perioada","descriere","calificare","institutie"):
                v = e.get(kk)
                if isinstance(v, str) and v.strip():
                    parts.append(v)

    return "\n".join(parts).lower()


def _keyword_present(keyword: str, cv_text: str) -> bool:
    k = (keyword or "").strip().lower()
    if not k:
        return False
    # exact phrase match for multi-word; word-boundary for single tokens (best effort)
    if " " in k:
        return k in cv_text
    return re.search(rf"\b{re.escape(k)}\b", cv_text) is not None


# ---------------------------
# Main analysis API (used by components)
# ---------------------------

def analyze_jd(
    cv_or_text: Any,
    role_hint: str = "",
    profile: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Backward-compatible entrypoint.

    Supported calls:
      - analyze_jd(cv, role_hint="...", profile=profile)   # used by Streamlit components
      - analyze_jd(jd_text="...", lang="en", profile=...)  # internal (not used by UI)

    Returns analysis dict (also persisted into cv["jd_state"] if cv passed).
    """
    if isinstance(cv_or_text, dict):
        cv = cv_or_text
        ensure_jd_state(cv)
        jd = get_current_jd(cv).strip()
        if not jd:
            # persist empty analysis
            st = cv["jd_state"]
            st["active_job_id"] = ""
            st["last_jd_hash"] = ""
            return get_current_analysis(cv)

        lang = detect_lang(jd)
        jid = job_hash(jd)
        st = cv["jd_state"]
        st["current_role_hint"] = role_hint or st.get("current_role_hint", "") or ""
        analysis = _analyze(jd, lang=lang, cv=cv, role_hint=st["current_role_hint"], profile=profile)
        st["jobs"][jid] = analysis
        st["active_job_id"] = jid
        st["last_jd_hash"] = jid
        st["last_updated_utc"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        return analysis

    # text mode (rare)
    jd = str(cv_or_text or "").strip()
    lang = detect_lang(jd)
    return _analyze(jd, lang=lang, cv=None, role_hint=role_hint, profile=profile)


def _analyze(jd_text: str, lang: str, cv: Optional[dict], role_hint: str, profile: Optional[dict]) -> Dict[str, Any]:
    kws = extract_keywords(jd_text, lang=lang, max_keywords=80)

    cv_text = _cv_text_for_matching(cv or {})
    present = [k for k in kws if _keyword_present(k, cv_text)]
    missing = [k for k in kws if k not in present]

    coverage = 0.0
    if kws:
        coverage = (len(present) / max(1, len(kws))) * 100.0

    prof_id = (profile.get("id") if isinstance(profile, dict) else "") or ""
    domain = (profile.get("domain") if isinstance(profile, dict) else "") or ""

    return {
        "hash": job_hash(jd_text),
        "lang": lang,
        "role_hint": role_hint or "",
        "profile_id": prof_id,
        "domain": domain,
        "keywords": kws,
        "present": present,
        "missing": missing,
        "coverage": float(round(coverage, 2)),
        "created_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


def auto_update_on_change(cv: dict, profile: Optional[dict] = None) -> None:
    """
    Call this on rerun. Re-analyzes only when JD text changed (hash differs).
    """
    ensure_jd_state(cv)
    jd = get_current_jd(cv).strip()
    if not jd:
        return

    jid = job_hash(jd)
    st = cv["jd_state"]
    if st.get("last_jd_hash") == jid and jid in (st.get("jobs") or {}):
        # already analyzed this exact JD in this session state
        st["active_job_id"] = jid
        return

    analyze_jd(cv, role_hint=st.get("current_role_hint", "") or "", profile=profile)


# ---------------------------
# Auto-apply helpers (used by UI buttons)
# ---------------------------

def apply_auto_to_modern_skills(cv: dict, analysis: Dict[str, Any], limit: int = 35) -> None:
    """
    Append missing keywords into cv["modern_keywords_extra"] (newline separated).
    """
    if not isinstance(cv, dict) or not isinstance(analysis, dict):
        return

    missing = analysis.get("missing", [])
    if not isinstance(missing, list) or not missing:
        return

    existing = (cv.get("modern_keywords_extra") or "").strip()
    existing_list = [x.strip() for x in existing.splitlines() if x.strip()]

    add = [str(x).strip() for x in missing if str(x).strip()]
    merged = _dedupe_keep_order(existing_list + add)
    cv["modern_keywords_extra"] = "\n".join(merged[: max(1, int(limit))])


def apply_missing_to_extra_keywords(cv: dict, limit: int = 25) -> None:
    """
    Convenience wrapper: apply current analysis missing keywords.
    """
    analysis = get_current_analysis(cv)
    apply_auto_to_modern_skills(cv, analysis, limit=limit)


def update_rewrite_templates_from_jd(cv: dict, profile: Optional[dict] = None, limit: int = 12) -> None:
    """
    Optional: generate job-specific rewrite templates from JD keywords.
    Stores into cv["jd_state"]["jobs"][job_id]["rewrite_templates"] and cv["rewrite_templates"] (if you want).
    """
    ensure_jd_state(cv)
    analysis = get_active_analysis(cv)
    if not analysis:
        return

    kws = analysis.get("keywords", [])
    if not isinstance(kws, list):
        kws = []

    # pick a handful of meaningful phrases (prefer 2-3 grams)
    picked = [k for k in kws if " " in k][: max(3, min(10, len(kws)))]
    if len(picked) < 4:
        picked += [k for k in kws if " " not in k][:4]

    templates: List[str] = []
    for k in picked[:limit]:
        templates.append(f"Implemented {k} across {{environment}}; improved {{metric}} by {{value}}.")
    templates = _dedupe_keep_order(templates)[:limit]

    analysis["rewrite_templates"] = templates
    # optional: also expose at root CV (some components use rewrite_templates)
    cv["rewrite_templates"] = templates


# ---------------------------
# Import / Export helpers (optional)
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
