# utils/jd_optimizer.py
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------
# Public API expected by app/components
# ---------------------------
def ensure_jd_state(cv: dict) -> None:
    """
    Ensures CV dict contains the JD analyzer persistent state.
    This prevents AttributeError / KeyError across app reruns.
    """
    if not isinstance(cv, dict):
        return

    # One canonical JD text used everywhere (ATS Helper / ATS Optimizer / JD Analyzer)
    cv.setdefault("job_description", "")

    # Persistent per-job analysis
    cv.setdefault("jd_state", {})
    st = cv["jd_state"]
    if not isinstance(st, dict):
        cv["jd_state"] = {}
        st = cv["jd_state"]

    st.setdefault("active_job_id", "")
    st.setdefault("jobs", {})  # job_id -> analysis payload


def job_hash(jd_text: str) -> str:
    """
    Stable hash for a job description (used as job_id).
    """
    s = (jd_text or "").strip().encode("utf-8")
    return hashlib.sha256(s).hexdigest()[:16]


def auto_update_on_change(cv: dict, profile: Optional[dict] = None) -> None:
    """
    Call on rerun to auto-analyze when JD changes and persist results per job hash.
    Safe no-op if JD is empty.

    Expected by app.py:
      jd_optimizer.auto_update_on_change(cv, profile=profile)
    """
    ensure_jd_state(cv)
    jd = (cv.get("job_description") or "").strip()
    if not jd:
        return

    jid = job_hash(jd)
    st = cv["jd_state"]
    prev_id = st.get("active_job_id", "")

    # If same job already active, do nothing
    if prev_id == jid and jid in st.get("jobs", {}):
        return

    # Analyze and set active
    analysis = analyze_jd(jd_text=jd, lang=detect_lang(jd), profile=profile)
    st["jobs"][jid] = analysis
    st["active_job_id"] = jid

    # Optional: auto-apply extracted keywords into CV skills fields
    # (Keeps it ATS-friendly and reduces copy-paste)
    apply_keywords_to_cv(cv, analysis)


def get_active_analysis(cv: dict) -> Optional[dict]:
    ensure_jd_state(cv)
    st = cv["jd_state"]
    jid = st.get("active_job_id") or ""
    if not jid:
        return None
    jobs = st.get("jobs", {})
    if not isinstance(jobs, dict):
        return None
    return jobs.get(jid)


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
        ng = " ".join(tokens[i:i+n])
        out.append(ng)
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

    # single tokens
    singles = []
    for t in tokens:
        if t in stop:
            continue
        if len(t) <= 2 and t not in _TECH_HINTS:
            continue
        # remove pure numbers
        if re.fullmatch(r"\d+", t):
            continue
        singles.append(t)

    # bi-grams and tri-grams
    bigrams = [g for g in _ngrams(tokens, 2) if not any(w in stop for w in g.split())]
    trigrams = [g for g in _ngrams(tokens, 3) if not any(w in stop for w in g.split())]

    # score by frequency (very offline)
    freq: Dict[str, int] = {}
    for cand in singles + bigrams + trigrams:
        freq[cand] = freq.get(cand, 0) + 1

    # prefer multi-word tech phrases if present
    ranked = sorted(freq.items(), key=lambda kv: (kv[1], len(kv[0])), reverse=True)
    kws = [k for k, _ in ranked]

    # post-filter: drop things that look like sentences
    cleaned = []
    for k in kws:
        if len(k) > 42:
            continue
        if k.count(" ") >= 4:
            continue
        cleaned.append(k)

    return _dedupe_keep_order(cleaned)[:max_keywords]


def analyze_jd(jd_text: str, lang: str = "en", profile: Optional[dict] = None) -> Dict[str, Any]:
    """
    Returns:
      {
        "lang": "en|ro",
        "keywords": [...],
        "profile_id": "...",
        "role_hints": [...],
      }
    """
    kws = extract_keywords(jd_text, lang=lang, max_keywords=80)

    # role hints: use profile job_titles if available, otherwise heuristics
    role_hints: List[str] = []
    if isinstance(profile, dict):
        jts = profile.get("job_titles")
        if isinstance(jts, list):
            role_hints = [str(x) for x in jts if str(x).strip()][:8]

    if not role_hints:
        # fallback heuristics
        if any(x in jd_text.lower() for x in ["soc", "siem", "splunk", "sentinel"]):
            role_hints = ["soc analyst", "security analyst"]
        elif any(x in jd_text.lower() for x in ["pentest", "penetration", "burp", "oscp"]):
            role_hints = ["penetration tester", "application security"]
        elif any(x in jd_text.lower() for x in ["cloud", "aws", "azure", "gcp"]):
            role_hints = ["cloud engineer", "cloud security"]
        else:
            role_hints = ["general"]

    return {
        "lang": lang,
        "keywords": kws,
        "profile_id": (profile.get("id") if isinstance(profile, dict) else "") or "",
        "role_hints": role_hints,
    }


# ---------------------------
# CV integration
# ---------------------------
def apply_keywords_to_cv(cv: dict, analysis: dict) -> None:
    """
    Push JD keywords into the CV "Technical Skills" buckets (modern_* fields).
    Keeps existing user text; only appends missing items.
    """
    if not isinstance(cv, dict) or not isinstance(analysis, dict):
        return

    kws = analysis.get("keywords", [])
    if not isinstance(kws, list) or not kws:
        return

    # existing keywords text is stored as newline-separated
    existing = (cv.get("modern_keywords_extra") or "").strip()
    existing_list = [x.strip() for x in existing.splitlines() if x.strip()]
    merged = _dedupe_keep_order(existing_list + [str(x).strip() for x in kws if str(x).strip()])

    # Keep it reasonable (ATS-friendly but not spam)
    merged = merged[:80]
    cv["modern_keywords_extra"] = "\n".join(merged)


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
        # ignore invalid JSON
        pass
