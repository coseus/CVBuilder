# utils/jd_optimizer.py
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------
# State keys (single source of truth)
# ---------------------------
JD_KEY = "job_description"          # canonical JD text
JD_LANG_KEY = "jd_lang"             # detected language: "en" / "ro"
JD_ROLE_HINT_KEY = "jd_role_hint"   # optional role hint
JD_STATE_KEY = "jd_state"           # dict with analyses per job hash


# ---------------------------
# Minimal stopwords
# ---------------------------
_STOP_EN = {
    "and", "or", "the", "a", "an", "to", "of", "in", "on", "for", "with", "as", "at", "by", "from",
    "is", "are", "be", "been", "being", "this", "that", "these", "those", "you", "we", "they",
    "our", "your", "their", "will", "can", "may", "must", "should",
    "responsible", "responsibilities", "requirements", "preferred", "nice", "plus",
    "minimum", "basic", "strong", "experience", "knowledge", "skills", "ability",
    "job", "role", "work", "team", "years", "year",
}
_STOP_RO = {
    "si", "și", "sau", "un", "o", "unei", "ale", "al", "a", "la", "în", "in", "pe", "pentru", "cu",
    "ca", "din", "este", "sunt", "fi", "vei", "voi", "tu", "voi", "noi", "nostru", "noastra",
    "acest", "aceasta", "aceste", "acestia",
    "job", "rol", "munca", "echipa", "ani", "an", "experienta", "experiență",
    "abilitati", "abilități", "competente", "competențe", "responsabilitati", "responsabilități",
}

_TECH_HINTS = {
    "c#", "c++", "go", "aws", "gcp", "azure", "siem", "soar", "edr", "xdr", "vpn", "lan", "wan",
    "sso", "mfa", "iam", "soc", "dfir", "waf", "ids", "ips", "api", "sql", "tls", "ssl",
}


# ---------------------------
# Public API expected by app/components
# ---------------------------
def ensure_jd_state(cv: dict) -> None:
    """Ensure all JD keys exist (safe across reruns)."""
    if not isinstance(cv, dict):
        return

    cv.setdefault(JD_KEY, "")
    cv.setdefault(JD_LANG_KEY, "en")
    cv.setdefault(JD_ROLE_HINT_KEY, "")

    cv.setdefault(JD_STATE_KEY, {})
    st = cv.get(JD_STATE_KEY)
    if not isinstance(st, dict):
        cv[JD_STATE_KEY] = {}
        st = cv[JD_STATE_KEY]

    st.setdefault("active_job_id", "")
    st.setdefault("jobs", {})  # job_id -> analysis dict


def get_current_jd(cv: dict) -> str:
    ensure_jd_state(cv)
    return str(cv.get(JD_KEY, "") or "")


def set_current_jd(cv: dict, jd_text: str) -> None:
    ensure_jd_state(cv)
    cv[JD_KEY] = str(jd_text or "")


def get_current_analysis(cv: dict) -> Dict[str, Any]:
    """Return active analysis if exists; else empty dict."""
    ensure_jd_state(cv)
    st = cv.get(JD_STATE_KEY, {})
    jid = str(st.get("active_job_id") or "")
    jobs = st.get("jobs", {})
    if isinstance(jobs, dict) and jid and jid in jobs and isinstance(jobs[jid], dict):
        return jobs[jid]
    return {}


def job_hash(jd_text: str) -> str:
    s = (jd_text or "").strip().encode("utf-8")
    return hashlib.sha256(s).hexdigest()[:16]


def auto_update_on_change(cv: dict, profile: Optional[dict] = None) -> None:
    """
    Call on rerun after JD text area updates.
    If JD changed, analyze and persist per-hash.
    """
    ensure_jd_state(cv)
    jd = (cv.get(JD_KEY) or "").strip()
    if not jd:
        return

    jid = job_hash(jd)
    st = cv.get(JD_STATE_KEY, {})
    prev = str(st.get("active_job_id") or "")
    jobs = st.get("jobs", {})
    if not isinstance(jobs, dict):
        jobs = {}
        st["jobs"] = jobs

    # if same job already analyzed, no-op
    if prev == jid and jid in jobs:
        return

    analysis = analyze_jd(cv=cv, profile=profile, role_hint=cv.get(JD_ROLE_HINT_KEY, ""))
    jobs[jid] = analysis
    st["active_job_id"] = jid

    # keep a cached detected language for UI/export
    if isinstance(analysis, dict) and analysis.get("lang"):
        cv[JD_LANG_KEY] = analysis["lang"]


# ---------------------------
# Language / tokenize / extract
# ---------------------------
def detect_lang(text: str) -> str:
    t = (text or "").lower()
    ro_hits = sum(1 for w in ["și", "să", "între", "cunoaștere", "responsabilități", "experiență", "competențe"] if w in t)
    en_hits = sum(1 for w in ["responsibilities", "requirements", "experience", "skills", "ability"] if w in t)
    return "ro" if ro_hits > en_hits else "en"


_WORD_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9\+\#\.\-]{1,}")


def _tokenize(text: str) -> List[str]:
    return _WORD_RE.findall((text or "").lower())


def _ngrams(tokens: List[str], n: int) -> List[str]:
    if n <= 1:
        return tokens[:]
    return [" ".join(tokens[i:i + n]) for i in range(0, max(0, len(tokens) - n + 1))]


def _dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
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


def extract_keywords(text: str, lang: str = "en", max_keywords: int = 80) -> List[str]:
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


# ---------------------------
# Coverage + CV text build
# ---------------------------
def _cv_text_for_coverage(cv: dict) -> str:
    """Make a big text blob from CV fields for simple ATS coverage matching."""
    if not isinstance(cv, dict):
        return ""

    parts: List[str] = []

    # summary
    rb = cv.get("rezumat_bullets")
    if isinstance(rb, list):
        parts.extend([str(x) for x in rb if str(x).strip()])
    if cv.get("rezumat"):
        parts.append(str(cv.get("rezumat")))

    # modern skills fields you already use in export
    for k in ("modern_skills_headline", "modern_tools", "modern_certs", "modern_keywords_extra"):
        v = cv.get(k)
        if v:
            parts.append(str(v))

    # personal / headline bits
    for k in ("pozitie_vizata", "titlu", "headline", "summary"):
        v = cv.get(k)
        if v:
            parts.append(str(v))

    # experience bullets
    exp = cv.get("experienta")
    if isinstance(exp, list):
        for e in exp:
            if not isinstance(e, dict):
                continue
            for kk in ("functie", "angajator", "tehnologii", "activitati", "descriere", "realizari"):
                vv = e.get(kk)
                if vv:
                    parts.append(str(vv))

    # education
    edu = cv.get("educatie")
    if isinstance(edu, list):
        for ed in edu:
            if not isinstance(ed, dict):
                continue
            for kk in ("titlu", "organizatie", "descriere"):
                vv = ed.get(kk)
                if vv:
                    parts.append(str(vv))

    return "\n".join(parts).lower()


def _compute_coverage(cv_text: str, jd_keywords: List[str]) -> Tuple[float, List[str], List[str]]:
    hay = (cv_text or "").lower()
    present: List[str] = []
    missing: List[str] = []
    for kw in jd_keywords:
        k = (kw or "").strip().lower()
        if not k:
            continue
        if k in hay:
            present.append(k)
        else:
            missing.append(k)

    total = max(1, len(present) + len(missing))
    coverage = (len(present) / total) * 100.0
    return coverage, _dedupe_keep_order(present), _dedupe_keep_order(missing)


# ---------------------------
# Main analysis
# ---------------------------
def analyze_jd(
    cv: dict,
    profile: Optional[dict] = None,
    role_hint: str = "",
) -> Dict[str, Any]:
    """
    Analyze current cv[JD_KEY], compute keywords + coverage against CV.
    Stores active job hash in returned dict.
    """
    ensure_jd_state(cv)
    jd_text = (cv.get(JD_KEY) or "").strip()
    lang = detect_lang(jd_text) if jd_text else (cv.get(JD_LANG_KEY) or "en")
    cv[JD_LANG_KEY] = lang

    jid = job_hash(jd_text) if jd_text else ""

    kws = extract_keywords(jd_text, lang=lang, max_keywords=80) if jd_text else []

    cv_text = _cv_text_for_coverage(cv)
    coverage, present, missing = _compute_coverage(cv_text, kws)

    # role hints from profile
    role_hints: List[str] = []
    if isinstance(profile, dict):
        jts = profile.get("job_titles")
        if isinstance(jts, list):
            role_hints = [str(x).strip().lower() for x in jts if str(x).strip()][:12]

    # fallback heuristics
    jd_l = jd_text.lower()
    if not role_hints:
        if any(x in jd_l for x in ["soc", "siem", "splunk", "sentinel", "qradar"]):
            role_hints = ["soc analyst", "security analyst"]
        elif any(x in jd_l for x in ["pentest", "penetration", "burp", "oscp"]):
            role_hints = ["penetration tester", "application security"]
        elif any(x in jd_l for x in ["cloud", "aws", "azure", "gcp"]):
            role_hints = ["cloud engineer", "cloud security"]
        else:
            role_hints = ["general"]

    out = {
        "hash": jid,
        "lang": lang,
        "role_hint": (role_hint or cv.get(JD_ROLE_HINT_KEY) or "").strip(),
        "role_hints": role_hints,
        "keywords": kws,
        "coverage": float(coverage),
        "present": present,
        "missing": missing,
        "profile_id": (profile.get("id") if isinstance(profile, dict) else "") or "",
    }

    # persist to state as "active"
    st = cv.get(JD_STATE_KEY, {})
    jobs = st.get("jobs", {})
    if isinstance(jobs, dict) and jid:
        jobs[jid] = out
        st["active_job_id"] = jid

    return out


# ---------------------------
# Auto-apply helpers used by UI
# ---------------------------
def apply_auto_to_modern_skills(cv: dict, analysis: Dict[str, Any]) -> None:
    """Append missing keywords into modern_keywords_extra (newline list)."""
    if not isinstance(cv, dict) or not isinstance(analysis, dict):
        return
    missing = analysis.get("missing", [])
    if not isinstance(missing, list) or not missing:
        return

    existing = (cv.get("modern_keywords_extra") or "").strip()
    existing_list = [x.strip() for x in existing.splitlines() if x.strip()]
    merged = _dedupe_keep_order(existing_list + [str(x).strip() for x in missing if str(x).strip()])
    cv["modern_keywords_extra"] = "\n".join(merged[:80])


def apply_missing_to_extra_keywords(cv: dict, limit: int = 25) -> None:
    """Convenience wrapper: uses active analysis."""
    analysis = get_current_analysis(cv)
    missing = analysis.get("missing", [])
    if isinstance(missing, list):
        analysis2 = dict(analysis)
        analysis2["missing"] = missing[: max(0, int(limit))]
        apply_auto_to_modern_skills(cv, analysis2)


def update_rewrite_templates_from_jd(cv: dict, profile: Optional[dict] = None) -> None:
    """
    Minimal offline helper:
    - put a few missing keywords as "hints" for rewrite component
    You can wire this into your ats_rewrite later.
    """
    ensure_jd_state(cv)
    analysis = get_current_analysis(cv) or analyze_jd(cv=cv, profile=profile, role_hint=cv.get(JD_ROLE_HINT_KEY, ""))
    missing = analysis.get("missing", [])
    if not isinstance(missing, list):
        missing = []

    # store for other components (if you want to consume it)
    cv.setdefault("rewrite_hints", {})
    cv["rewrite_hints"]["missing_keywords_top"] = missing[:20]
