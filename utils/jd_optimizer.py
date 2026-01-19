# utils/jd_optimizer.py
from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional


# -------------------------
# Stopwords (small, fast, offline)
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
este sunt era au avea avem aveam voi tu el ea ei ele noi lor
""".split())

# Keep technical tokens even if short
_TECH_KEEP = {
    "c#", "c++", ".net", "node.js", "node", "aws", "azure", "gcp", "m365", "o365",
    "siem", "soc", "edr", "xdr", "iam", "sso", "mfa", "vpn", "vlan", "ad", "entra",
    "tcp", "udp", "dns", "dhcp", "http", "https", "ssh", "rdp", "sql", "linux", "windows",
    "kubernetes", "k8s", "docker", "terraform", "ansible",
}


# -------------------------
# Helpers
# -------------------------
def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def detect_language(text: str) -> str:
    """
    Very lightweight EN/RO detection for offline usage.
    """
    t = (text or "").lower()
    if not t.strip():
        return "en"

    ro_hits = 0
    en_hits = 0

    # diacritics
    if re.search(r"[ăâîșşțţ]", t):
        ro_hits += 3

    # common RO / EN words
    ro_hits += len(re.findall(r"\b(și|sau|în|din|pentru|cu|la|pe|care|este|sunt)\b", t))
    en_hits += len(re.findall(r"\b(the|and|with|to|for|from|in|on|is|are)\b", t))

    return "ro" if ro_hits >= en_hits + 1 else "en"


def jd_hash(text: str) -> str:
    t = (text or "").strip().encode("utf-8")
    return hashlib.sha256(t).hexdigest()[:16]


def ensure_jd_state(cv: Dict[str, Any]) -> None:
    """
    Ensure cv has a stable container for JD analyses (persist per job hash).
    """
    if not isinstance(cv, dict):
        return
    st = cv.get("jd_state")
    if not isinstance(st, dict):
        st = {}
        cv["jd_state"] = st

    st.setdefault("current_hash", "")
    st.setdefault("current_role_hint", "")
    st.setdefault("current_lang", "en")
    st.setdefault("jobs", {})  # hash -> analysis dict
    if not isinstance(st["jobs"], dict):
        st["jobs"] = {}


def set_current_jd(cv: Dict[str, Any], text: str) -> str:
    """
    Single source of truth for JD text:
      cv["job_description"] AND cv["jd_text"] are kept in sync (back-compat).
    Returns job hash.
    """
    ensure_jd_state(cv)
    text = text or ""
    cv["jd_text"] = text
    cv["job_description"] = text  # keep old key working
    h = jd_hash(text)
    cv["jd_state"]["current_hash"] = h
    cv["jd_state"]["current_lang"] = detect_language(text)
    return h


def get_current_jd(cv: Dict[str, Any]) -> str:
    """
    Read JD from the single source of truth.
    """
    if not isinstance(cv, dict):
        return ""
    return cv.get("jd_text") or cv.get("job_description") or ""


def _tokenize(text: str) -> List[str]:
    # normalize dashes, punctuation
    t = (text or "").replace("–", "-").replace("—", "-")
    # keep words, numbers, dots, plus, hash
    raw = re.findall(r"[a-zA-Z0-9\.\+#/]{2,}", t.lower())
    out: List[str] = []
    for w in raw:
        w = w.strip().strip("/").strip()
        if not w:
            continue
        out.append(w)
    return out


def extract_keywords(text: str, lang: Optional[str] = None, top_n: int = 60) -> List[str]:
    """
    Offline keyword extraction:
    - tokenization + stopword removal
    - keep tech tokens
    - rank by frequency with a light bias toward tech-like tokens
    """
    text = text or ""
    if lang is None:
        lang = detect_language(text)

    stop = _STOPWORDS_RO if lang == "ro" else _STOPWORDS_EN
    toks = _tokenize(text)

    cleaned: List[str] = []
    for w in toks:
        if w in _TECH_KEEP:
            cleaned.append(w)
            continue
        if len(w) <= 2:
            continue
        if w in stop:
            continue
        # drop pure numbers
        if re.fullmatch(r"\d+", w):
            continue
        cleaned.append(w)

    freq = Counter(cleaned)

    def score(tok: str) -> float:
        base = float(freq[tok])
        # bias technical-looking tokens
        if any(ch in tok for ch in [".", "#", "+", "/"]):
            base += 0.75
        if tok in _TECH_KEEP:
            base += 1.5
        # prefer mid-length tokens
        if 4 <= len(tok) <= 18:
            base += 0.25
        return base

    ranked = sorted(freq.keys(), key=score, reverse=True)
    # de-dup near duplicates (basic)
    out: List[str] = []
    seen = set()
    for k in ranked:
        if k in seen:
            continue
        seen.add(k)
        out.append(k)
        if len(out) >= top_n:
            break

    return out


def _cv_text_for_match(cv: Dict[str, Any]) -> str:
    """
    Build a string from current CV fields for keyword coverage.
    """
    parts: List[str] = []

    def add(x: Any):
        if x is None:
            return
        if isinstance(x, str) and x.strip():
            parts.append(x.strip())
        elif isinstance(x, list):
            for it in x:
                add(it)
        elif isinstance(x, dict):
            for _, v in x.items():
                add(v)

    add(cv.get("rezumat"))
    add(cv.get("rezumat_bullets"))
    add(cv.get("modern_skills_headline"))
    add(cv.get("modern_tools"))
    add(cv.get("modern_certs"))
    add(cv.get("modern_keywords_extra"))

    # experience bullets
    exp = cv.get("experienta", [])
    if isinstance(exp, list):
        for e in exp:
            if not isinstance(e, dict):
                continue
            add(e.get("functie"))
            add(e.get("angajator"))
            add(e.get("titlu"))
            add(e.get("tehnologii"))
            add(e.get("activitati"))

    return " ".join(parts).lower()


def coverage_report(cv: Dict[str, Any], keywords: List[str]) -> Tuple[List[str], List[str], float]:
    """
    Returns (present, missing, coverage_ratio).
    """
    hay = _cv_text_for_match(cv)
    present: List[str] = []
    missing: List[str] = []
    for kw in keywords:
        k = (kw or "").strip().lower()
        if not k:
            continue
        if k in hay:
            present.append(kw)
        else:
            missing.append(kw)
    ratio = (len(present) / max(1, (len(present) + len(missing)))) * 100.0
    return present, missing, ratio


def analyze_jd(cv: Dict[str, Any], role_hint: str = "") -> Dict[str, Any]:
    """
    Analyze current JD and persist per job hash.
    """
    ensure_jd_state(cv)
    text = get_current_jd(cv)
    h = set_current_jd(cv, text)

    lang = cv["jd_state"].get("current_lang") or detect_language(text)
    kws = extract_keywords(text, lang=lang, top_n=70)

    present, missing, ratio = coverage_report(cv, kws)

    analysis = {
        "hash": h,
        "lang": lang,
        "role_hint": (role_hint or "").strip(),
        "keywords": kws,
        "present": present,
        "missing": missing,
        "coverage": ratio,
    }

    cv["jd_state"]["jobs"][h] = analysis
    cv["jd_state"]["current_role_hint"] = analysis["role_hint"]
    cv["jd_state"]["current_hash"] = h
    return analysis


def get_current_analysis(cv: Dict[str, Any]) -> Dict[str, Any]:
    ensure_jd_state(cv)
    h = cv["jd_state"].get("current_hash") or jd_hash(get_current_jd(cv))
    jobs = cv["jd_state"].get("jobs", {})
    if isinstance(jobs, dict) and h in jobs and isinstance(jobs[h], dict):
        return jobs[h]
    # fallback: analyze once if missing
    return analyze_jd(cv, role_hint=cv["jd_state"].get("current_role_hint", ""))


def apply_auto_to_modern_skills(cv: Dict[str, Any], analysis: Dict[str, Any], max_add: int = 28) -> None:
    """
    Minimal "auto-update" rule:
    - add missing keywords into modern_keywords_extra (newline separated)
    - keep it deduped and capped
    """
    if not isinstance(cv, dict) or not isinstance(analysis, dict):
        return
    missing = analysis.get("missing", [])
    if not isinstance(missing, list):
        return

    existing = (cv.get("modern_keywords_extra") or "").splitlines()
    existing = [x.strip() for x in existing if x.strip()]
    existing_l = {x.lower() for x in existing}

    to_add: List[str] = []
    for kw in missing:
        s = (kw or "").strip()
        if not s:
            continue
        if s.lower() in existing_l:
            continue
        to_add.append(s)
        if len(to_add) >= max_add:
            break

    merged = existing + to_add
    # dedupe preserve
    out: List[str] = []
    seen = set()
    for x in merged:
        k = x.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(x)

    cv["modern_keywords_extra"] = "\n".join(out).strip()
