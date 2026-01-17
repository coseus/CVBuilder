# utils/jd_optimizer.py
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Any


# -------------------------
# Lightweight EN/RO keyword extraction (offline)
# -------------------------

STOP_EN = {
    "the", "and", "or", "to", "of", "in", "for", "with", "on", "at", "by", "an", "a",
    "is", "are", "as", "from", "this", "that", "you", "your", "we", "our", "will",
    "be", "have", "has", "hands", "using", "use", "used", "into", "across"
}
STOP_RO = {
    "și", "sau", "de", "din", "la", "în", "pe", "cu", "pentru", "că", "care", "este",
    "sunt", "un", "o", "ai", "ale", "al", "a", "din", "prin", "se", "sa", "fie"
}

# Common multiword patterns (expand as needed)
PHRASES = [
    "active directory", "azure ad", "entra id", "microsoft 365", "office 365",
    "incident response", "vulnerability management", "penetration testing",
    "security operations", "siem", "log management", "threat hunting",
    "network security", "cloud security", "iam", "identity and access management",
    "endpoint security", "patch management", "risk management"
]

# Tool-ish tokens allowed even if short
ALLOW_SHORT = {"c", "c++", "go", "siem", "edr", "iam", "soc", "splunk", "qradar", "aws", "gcp", "aad"}


def _clean_text(s: str) -> str:
    s = s or ""
    s = s.replace("\u2013", "-").replace("\u2014", "-")
    # keep slashes and plus for tokens (c++, azure/ad)
    s = re.sub(r"[^\w\s\-/\+\.#]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def detect_lang(text: str) -> str:
    t = (text or "").lower()
    ro_hits = sum(1 for w in ("și", "în", "pentru", "responsabil", "cerințe", "abilități") if w in t)
    en_hits = sum(1 for w in ("responsibilities", "requirements", "skills", "experience") if w in t)
    return "ro" if ro_hits > en_hits else "en"


def job_hash(text: str, profile_id: str = "", role_hint: str = "") -> str:
    base = f"{profile_id}||{role_hint}||{(text or '').strip()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def _tokenize(text: str) -> List[str]:
    t = _clean_text(text).lower()
    # split, keep dots for things like "microsoft.365" -> normalized later
    raw = re.split(r"\s+", t)
    out = []
    for r in raw:
        r = r.strip().strip(".")
        if not r:
            continue
        out.append(r)
    return out


def extract_keywords(text: str, lang: Optional[str] = None, max_terms: int = 80) -> List[str]:
    if not text or not str(text).strip():
        return []
    lang = lang or detect_lang(text)
    stop = STOP_RO if lang == "ro" else STOP_EN

    t = " " + _clean_text(text).lower() + " "

    # 1) phrases first
    found = []
    for p in PHRASES:
        if f" {p} " in t:
            found.append(p)

    # 2) tokens
    tokens = _tokenize(text)

    # normalize tokens, drop stopwords, very short noise
    candidates = []
    for tok in tokens:
        if tok in stop:
            continue
        tok2 = tok.replace(".", " ").strip()
        tok2 = tok2.replace("m365", "microsoft 365")
        tok2 = tok2.replace("o365", "office 365")

        if len(tok2) < 3 and tok2 not in ALLOW_SHORT:
            continue
        if tok2.isdigit():
            continue
        # collapse "azure/ad" to "azure ad"
        tok2 = tok2.replace("/", " ").replace("-", " ")
        tok2 = re.sub(r"\s+", " ", tok2).strip()
        if not tok2:
            continue
        candidates.append(tok2)

    # frequency score (simple)
    freq: Dict[str, int] = {}
    for c in candidates:
        freq[c] = freq.get(c, 0) + 1

    # combine: phrases boosted
    for p in found:
        freq[p] = freq.get(p, 0) + 4

    # rank
    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    out = []
    seen = set()
    for term, _ in ranked:
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(term)
        if len(out) >= max_terms:
            break
    return out


def derive_role_hint_from_profile(profile: Dict[str, Any]) -> str:
    """
    Map profile id/domain to analyzer role hints.
    Keeps your limited list: security engineer / soc analyst / penetration tester / general cyber security
    """
    pid = (profile.get("id") or "").lower().strip()
    dom = (profile.get("domain") or "").lower().strip()
    s = f"{pid} {dom}"

    if "soc" in s:
        return "soc analyst"
    if "pentest" in s or "penetration" in s:
        return "penetration tester"
    if "security_engineer" in s or "sec_eng" in s or "security engineer" in s:
        return "security engineer"
    if "cyber" in s or "security" in s:
        return "general cyber security"
    return "general cyber security"


def get_store(cv: Dict[str, Any]) -> Dict[str, Any]:
    if "jd_store" not in cv or not isinstance(cv.get("jd_store"), dict):
        cv["jd_store"] = {}
    return cv["jd_store"]


def load_analysis(cv: Dict[str, Any], job_id: str) -> Dict[str, Any]:
    store = get_store(cv)
    return store.get(job_id, {})


def save_analysis(cv: Dict[str, Any], job_id: str, analysis: Dict[str, Any]) -> None:
    store = get_store(cv)
    store[job_id] = analysis


def analyze_job_description(
    cv: Dict[str, Any],
    jd_text: str,
    profile: Dict[str, Any],
    lang: Optional[str] = None,
    role_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Computes analysis + persists under cv['jd_store'][job_id].
    """
    lang = lang or detect_lang(jd_text)
    role_hint = role_hint or derive_role_hint_from_profile(profile)
    pid = (profile.get("id") or "").strip()
    jid = job_hash(jd_text, profile_id=pid, role_hint=role_hint)

    kws = extract_keywords(jd_text, lang=lang, max_terms=100)

    analysis = {
        "job_id": jid,
        "profile_id": pid,
        "role_hint": role_hint,
        "lang": lang,
        "keywords": kws,
        "jd_preview": (jd_text or "").strip()[:8000],  # cap
    }
    save_analysis(cv, jid, analysis)
    return analysis
