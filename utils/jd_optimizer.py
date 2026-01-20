# utils/jd_optimizer.py
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional


# ---------------------------
# Public API expected by app/components
# ---------------------------
def ensure_jd_state(cv: dict) -> None:
    """
    Ensures CV dict contains the JD analyzer persistent state.
    Prevents AttributeError / KeyError across reruns.
    """
    if not isinstance(cv, dict):
        return

    # One canonical JD text used everywhere
    cv.setdefault("job_description", "")

    # Persistent per-job analysis state
    cv.setdefault("jd_state", {})
    st = cv["jd_state"]
    if not isinstance(st, dict):
        cv["jd_state"] = {}
        st = cv["jd_state"]

    st.setdefault("active_job_id", "")
    st.setdefault("jobs", {})  # job_id -> analysis payload
    st.setdefault("last_jd_hash", "")  # convenience


def job_hash(jd_text: str) -> str:
    """
    Stable hash for a job description (used as job_id).
    """
    s = (jd_text or "").strip().encode("utf-8")
    return hashlib.sha256(s).hexdigest()[:16]


def get_current_jd(cv: dict) -> str:
    """
    Canonical JD getter used by multiple components.
    """
    ensure_jd_state(cv)
    return (cv.get("job_description") or "").strip()


def set_current_jd(cv: dict, jd_text: str) -> None:
    """
    Canonical JD setter used by multiple components.
    Also resets active job id if content cleared.
    """
    ensure_jd_state(cv)
    cv["job_description"] = (jd_text or "")
    if not (cv["job_description"] or "").strip():
        st = cv["jd_state"]
        st["active_job_id"] = ""
        st["last_jd_hash"] = ""


def get_active_analysis(cv: dict) -> Optional[dict]:
    """
    Returns analysis for active job id (if any).
    """
    ensure_jd_state(cv)
    st = cv["jd_state"]
    jid = st.get("active_job_id") or ""
    if not jid:
        return None
    jobs = st.get("jobs", {})
    if not isinstance(jobs, dict):
        return None
    return jobs.get(jid)


def get_current_analysis(cv: dict) -> Dict[str, Any]:
    """
    Compatibility alias used by UI panels.
    Always returns a dict.
    """
    a = get_active_analysis(cv)
    return a if isinstance(a, dict) else {
        "lang": detect_lang(get_current_jd(cv)),
        "keywords": [],
        "coverage": 0.0,
        "missing": [],
        "role_hints": [],
        "profile_id": "",
        "job_id": "",
    }


def auto_update_on_change(cv: dict, profile: Optional[dict] = None) -> None:
    """
    Auto-analyze when JD changes; persist results per job hash.
    Safe no-op if JD empty.

    Expected by app.py:
      jd_optimizer.auto_update_on_change(cv, profile=profile)
    """
    ensure_jd_state(cv)
    jd = (cv.get("job_description") or "").strip()
    if not jd:
        return

    st = cv["jd_state"]
    jid = job_hash(jd)

    # If same job already active & stored, no-op
    if st.get("active_job_id") == jid and jid in st.get("jobs", {}):
        return

    # Analyze & compute coverage vs current CV
    lang = detect_lang(jd)
    analysis = analyze_jd(jd_text=jd, lang=lang, profile=profile)
    analysis = enrich_with_coverage(cv, analysis)

    # Persist
    jobs = st.get("jobs")
    if not isinstance(jobs, dict):
        jobs = {}
        st["jobs"] = jobs
    jobs[jid] = analysis
    st["active_job_id"] = jid
    st["last_jd_hash"] = jid

    # Optional auto-apply extracted keywords into CV fields
    apply_keywords_to_cv(cv, analysis)


# ---------------------------
# JD analysis (offline)
# ---------------------------
_STOP_EN = {
    "and","or","the","a","an","to","of","in","on","for","with","as","at","by","from","is","are","be","will","you",
    "we","our","your","this","that","these","those","it","they","their","them","us","who","what","when","where",
    "job","role","work","team","years","year","experience","skills","skill","responsibilities","responsibility",
}
_STOP_RO = {
    "si","sau","un","o","unei","ale","al","a","la","in","pe","pentru","cu","ca","din","este","sunt","fi","vei","voi",
    "tu","voi","noi","nostru","noastra","acest","aceasta","aceste","acestia","job","rol","munca","echipa","ani","an",
    "experienta","abilitati","competente","responsabilitati","responsabilitate",
}

_TECH_HINTS = {
    # common ATS tokens we want to keep even if short
    "c#", "c++", "go", "aws", "gcp", "azure", "siem", "soar", "edr", "vpn", "lan", "wan", "sso", "mfa", "iam",
    "soc", "dfir", "xdr", "waf", "ids", "ips", "api", "sql",
}


def detect_lang(text: str) -> str:
    """
    Very small offline heuristic: returns 'ro' or 'en'
    """
    t = (text or "").lower()
    ro_hits = sum(1 for w in ["și", "să", "între", "cunoaștere", "responsabilități", "experiență", "competențe"] if w in t)
    en_hits = sum(1 for w in ["responsibilities", "requirements", "experience", "skills", "ability"] if w in t)
    return "ro" if ro_hits > en_hits else "en"


def _tokenize(text: str) -> List[str]:
    # keep things like "azure ad", "active directory", "incident response" later via ngrams
    return re.findall(r"[a-zA-Z0-9][a-zA-Z0-9\+\#\.\-]{1,}", (text or "").lower())


def _ngrams(tokens: List[str], n: int) -> List[str]:
    out = []
    for i in range(0, max(0, len(tokens) - n + 1)):
        out.append(" ".join(tokens[i:i+n]))
    return out


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


def extract_keywords(text: str, lang: str = "en", max_keywords: int = 70) -> List[str]:
    tokens = _tokenize(text)
    stop = _STOP_RO if lang == "ro" else _STOP_EN

    singles = []
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

    freq: Dict[str, int] = {}
    for cand in singles + bigrams + trigrams:
        freq[cand] = freq.get(cand, 0) + 1

    ranked = sorted(freq.items(), key=lambda kv: (kv[1], len(kv[0])), reverse=True)
    kws = [k for k, _ in ranked]

    cleaned = []
    for k in kws:
        if len(k) > 42:
            continue
        if k.count(" ") >= 4:
            continue
        cleaned.append(k)

    return _dedupe_keep_order(cleaned)[:max_keywords]


def _analyze_jd_text(jd_text: str, lang: str = "en", profile: Optional[dict] = None) -> Dict[str, Any]:
    """
    Internal: analyze raw JD text (offline).
    """
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

    return {
        "job_id": job_hash(jd_text),
        "lang": lang,
        "keywords": kws,
        "profile_id": (profile.get("id") if isinstance(profile, dict) else "") or "",
        "role_hints": role_hints,
        "coverage": 0.0,
        "missing": [],
        "matched": [],
    }


def analyze_jd(
    cv_or_text: Any,
    lang: str = "en",
    profile: Optional[dict] = None,
    role_hint: Optional[str] = None,
    jd_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Backward-compatible analyzer used by multiple panels.

    Supports BOTH:
      A) analyze_jd(jd_text: str, lang="en", profile=profile)
      B) analyze_jd(cv: dict, role_hint="...", profile=profile)   # legacy panel call

    If cv dict is provided:
      - reads JD from cv["job_description"]
      - detects lang automatically
      - enriches with coverage vs CV
      - applies role_hint override if provided
    """
    # --- Case B: called with cv dict (legacy) ---
    if isinstance(cv_or_text, dict):
        cv = cv_or_text
        ensure_jd_state(cv)

        text = (jd_text if isinstance(jd_text, str) else (cv.get("job_description") or "")).strip()
        if not text:
            return {
                "job_id": "",
                "lang": detect_lang(""),
                "keywords": [],
                "profile_id": (profile.get("id") if isinstance(profile, dict) else "") or "",
                "role_hints": [role_hint] if role_hint else [],
                "coverage": 0.0,
                "missing": [],
                "matched": [],
            }

        auto_lang = detect_lang(text)
        base = _analyze_jd_text(text, lang=auto_lang, profile=profile)

        # If panel provides explicit role_hint, force it first
        if isinstance(role_hint, str) and role_hint.strip():
            # keep existing hints, but put selected first
            rh = [role_hint.strip()]
            for x in base.get("role_hints", []) or []:
                xs = str(x).strip()
                if xs and xs.lower() != rh[0].lower():
                    rh.append(xs)
            base["role_hints"] = rh[:12]

        # Add coverage/missing/matched based on current CV
        base = enrich_with_coverage(cv, base)
        return base

    # --- Case A: called with JD text string (new style) ---
    text = ""
    if isinstance(cv_or_text, str):
        text = cv_or_text
    elif isinstance(jd_text, str):
        text = jd_text

    text = (text or "").strip()
    if not text:
        return {
            "job_id": "",
            "lang": lang,
            "keywords": [],
            "profile_id": (profile.get("id") if isinstance(profile, dict) else "") or "",
            "role_hints": [role_hint] if role_hint else [],
            "coverage": 0.0,
            "missing": [],
            "matched": [],
        }

    # use provided lang, but auto-detect if nonsense
    use_lang = lang if lang in ("en", "ro") else detect_lang(text)
    base = _analyze_jd_text(text, lang=use_lang, profile=profile)

    # If role_hint given, prioritize it
    if isinstance(role_hint, str) and role_hint.strip():
        rh = [role_hint.strip()]
        for x in base.get("role_hints", []) or []:
            xs = str(x).strip()
            if xs and xs.lower() != rh[0].lower():
                rh.append(xs)
        base["role_hints"] = rh[:12]

    return base

# ---------------------------
# Coverage / match vs CV
# ---------------------------
def _cv_text_blob(cv: dict) -> str:
    """
    Build a big normalized text blob from CV fields for keyword matching.
    """
    parts: List[str] = []
    for k in [
        "nume_prenume","pozitie_vizata","profile_line",
        "rezumat","modern_skills_headline","modern_tools","modern_certs","modern_keywords_extra",
        "competente_tehnice","competente_calculator","competente_sociale","competente_organizatorice",
        "competente_artistice","alte_competente",
        "email","telefon","adresa","linkedin","github","website",
    ]:
        v = cv.get(k)
        if isinstance(v, str) and v.strip():
            parts.append(v.strip())

    # summary bullets
    rb = cv.get("rezumat_bullets")
    if isinstance(rb, list):
        parts.extend([str(x).strip() for x in rb if str(x).strip()])

    # experience bullets
    exp = cv.get("experienta")
    if isinstance(exp, list):
        for e in exp:
            if not isinstance(e, dict):
                continue
            for kk in ["titlu","functie","angajator","locatie","tehnologii","link","activitati","perioada"]:
                vv = e.get(kk)
                if isinstance(vv, str) and vv.strip():
                    parts.append(vv.strip())

    # education
    edu = cv.get("educatie")
    if isinstance(edu, list):
        for ed in edu:
            if not isinstance(ed, dict):
                continue
            for kk in ["titlu","organizatie","locatie","descriere","perioada"]:
                vv = ed.get(kk)
                if isinstance(vv, str) and vv.strip():
                    parts.append(vv.strip())

    blob = " \n ".join(parts)
    blob = re.sub(r"\s+", " ", blob).lower()
    return blob


def enrich_with_coverage(cv: dict, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Adds:
      - coverage (%)
      - matched keywords
      - missing keywords
    """
    if not isinstance(analysis, dict):
        return analysis

    kws = analysis.get("keywords", [])
    if not isinstance(kws, list) or not kws:
        analysis["coverage"] = 0.0
        analysis["matched"] = []
        analysis["missing"] = []
        return analysis

    blob = _cv_text_blob(cv)

    matched: List[str] = []
    missing: List[str] = []
    for kw in kws:
        k = str(kw).strip()
        if not k:
            continue
        # word-boundary-ish match for single token; substring for multiword
        if " " in k:
            ok = (k.lower() in blob)
        else:
            ok = re.search(rf"\b{re.escape(k.lower())}\b", blob) is not None
        if ok:
            matched.append(k)
        else:
            missing.append(k)

    total = max(1, len(matched) + len(missing))
    analysis["matched"] = matched
    analysis["missing"] = missing
    analysis["coverage"] = (len(matched) / total) * 100.0
    return analysis


# ---------------------------
# CV integration
# ---------------------------
def apply_keywords_to_cv(cv: dict, analysis: dict) -> None:
    """
    Push JD keywords into Modern keywords (extra).
    Keeps existing user text; appends missing items.
    """
    if not isinstance(cv, dict) or not isinstance(analysis, dict):
        return

    kws = analysis.get("keywords", [])
    if not isinstance(kws, list) or not kws:
        return

    existing = (cv.get("modern_keywords_extra") or "").strip()
    existing_list = [x.strip() for x in existing.splitlines() if x.strip()]
    merged = _dedupe_keep_order(existing_list + [str(x).strip() for x in kws if str(x).strip()])

    # Keep it reasonable
    cv["modern_keywords_extra"] = "\n".join(merged[:80])


def apply_auto_to_modern_skills(cv: dict, analysis: Optional[dict] = None) -> None:
    """
    Used by ATS Helper button: apply missing keywords to modern_keywords_extra.
    """
    ensure_jd_state(cv)
    if analysis is None:
        analysis = get_active_analysis(cv) or {}
    if not isinstance(analysis, dict):
        return

    missing = analysis.get("missing", [])
    if not isinstance(missing, list) or not missing:
        return

    cur = (cv.get("modern_keywords_extra") or "").strip()
    cur_list = [x.strip() for x in cur.splitlines() if x.strip()]
    merged = _dedupe_keep_order(cur_list + [str(x).strip() for x in missing if str(x).strip()])
    cv["modern_keywords_extra"] = "\n".join(merged[:90])


# ---------------------------
# Optional: export/import analysis state
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
