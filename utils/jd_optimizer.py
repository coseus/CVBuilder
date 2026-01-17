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

_TECH_KEEP = set([
    "c#", "c++", ".net", "node.js", "node", "aws", "azure", "gcp", "m365", "o365",
    "siem", "soc", "edr", "xdr", "iam", "sso", "mfa", "vpn", "vlan", "ad", "entra",
    "tcp", "udp", "dns", "dhcp", "http", "https", "ssh", "rdp", "sql", "linux", "windows",
    "kubernetes", "k8s", "docker", "terraform", "ansible",
])


# -------------------------
# Helpers
# -------------------------
def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def detect_language(text: str) -> str:
    """
    Very lightweight EN/RO detection.
    Good enough for picking stopwords and a few label choices.
    """
    t = (text or "").lower()
    if not t.strip():
        return "en"

    ro_hits = 0
    en_hits = 0

    # diacritics
    if re.search(r"[ăâîșşțţ]", t):
        ro_hits += 3

    # common RO words
    ro_hits += len(re.findall(r"\b(și|sau|în|din|pentru|cu|la|pe|care|este|sunt)\b", t))
    # common EN words
    en_hits += len(re.findall(r"\b(and|or|the|with|for|to|is|are|you|we)\b", t))

    return "ro" if ro_hits > en_hits else "en"


def job_hash(text: str) -> str:
    b = (text or "").strip().encode("utf-8", errors="ignore")
    return hashlib.sha256(b).hexdigest()[:12] if b else "nojd"


def extract_keywords(text: str, lang: Optional[str] = None, max_keywords: int = 60) -> List[str]:
    """
    ATS-ish keyword extraction: offline, fast, no ML deps.
    Keeps tech tokens and longer words, filters stopwords EN/RO.
    """
    t = _norm(text)
    if not t:
        return []

    if not lang:
        lang = detect_language(t)

    tokens = re.findall(r"[a-z0-9][a-z0-9\+\#\.\-/]{1,}", t)
    cleaned: List[str] = []
    for tok in tokens:
        tok = tok.strip(".-/")
        if tok in _TECH_KEEP:
            cleaned.append(tok)
            continue
        if len(tok) < 3:
            continue
        if tok in _STOPWORDS_EN or tok in _STOPWORDS_RO:
            continue
        cleaned.append(tok)

    return [w for w, _ in Counter(cleaned).most_common(max_keywords)]


def build_cv_blob(cv: Dict[str, Any]) -> str:
    """
    Build a plain-text blob from CV fields to compare against JD keywords.
    Keep it stable & ATS-focused.
    """
    parts: List[str] = []

    parts.append(str(cv.get("pozitie_vizata", "") or ""))
    parts.append(str(cv.get("profile_line", "") or ""))
    parts.append(str(cv.get("rezumat", "") or ""))

    bullets = cv.get("rezumat_bullets", [])
    if isinstance(bullets, list):
        parts.extend([str(b) for b in bullets if str(b).strip()])

    parts.append(str(cv.get("modern_skills_headline", "") or ""))
    parts.append(str(cv.get("modern_tools", "") or ""))
    parts.append(str(cv.get("modern_certs", "") or ""))
    parts.append(str(cv.get("modern_keywords_extra", "") or ""))

    # experience/projects
    exp = cv.get("experienta", [])
    if isinstance(exp, list):
        for e in exp:
            if not isinstance(e, dict):
                continue
            parts.append(str(e.get("functie", "") or ""))
            parts.append(str(e.get("titlu", "") or ""))
            parts.append(str(e.get("angajator", "") or ""))
            parts.append(str(e.get("tehnologii", "") or ""))
            parts.append(str(e.get("activitati", "") or ""))

    # education
    edu = cv.get("educatie", [])
    if isinstance(edu, list):
        for ed in edu:
            if not isinstance(ed, dict):
                continue
            parts.append(str(ed.get("titlu", "") or ""))
            parts.append(str(ed.get("organizatie", "") or ""))
            parts.append(str(ed.get("descriere", "") or ""))

    return "\n".join([p for p in parts if str(p).strip()])


def compute_coverage(cv_blob: str, keywords: List[str]) -> Tuple[float, List[str], List[str]]:
    """
    Returns coverage, present, missing
    """
    cv_t = _norm(cv_blob)
    present = [k for k in keywords if k and k in cv_t]
    missing = [k for k in keywords if k and k not in cv_t]
    cov = len(present) / max(1, len(keywords))
    return cov, present, missing


def ensure_jd_state(cv: Dict[str, Any]) -> None:
    """
    Ensure all JD fields exist (safe defaults).
    """
    cv.setdefault("job_description", "")
    cv.setdefault("jd_lang", "en")
    cv.setdefault("jd_role_hint", "")
    cv.setdefault("jd_active_hash", "nojd")
    cv.setdefault("jd_store", {})  # hash -> analysis dict

    # latest analysis mirror (for UI)
    cv.setdefault("jd_keywords", [])
    cv.setdefault("jd_present", [])
    cv.setdefault("jd_missing", [])
    cv.setdefault("jd_coverage", 0.0)


def persist_analysis(cv: Dict[str, Any], h: str, analysis: Dict[str, Any]) -> None:
    ensure_jd_state(cv)
    store = cv.get("jd_store")
    if not isinstance(store, dict):
        store = {}
        cv["jd_store"] = store
    store[h] = analysis


def load_analysis(cv: Dict[str, Any], h: str) -> Optional[Dict[str, Any]]:
    store = cv.get("jd_store")
    if isinstance(store, dict):
        return store.get(h)
    return None


def analyze_jd(cv: Dict[str, Any], profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Analyze current JD, persist per hash, and mirror key fields on cv for quick UI.
    """
    ensure_jd_state(cv)
    jd = (cv.get("job_description") or "").strip()
    lang = detect_language(jd)
    h = job_hash(jd)
    cv["jd_lang"] = lang
    cv["jd_active_hash"] = h

    if not jd:
        # blank analysis
        analysis = {
            "hash": "nojd",
            "lang": lang,
            "keywords": [],
            "present": [],
            "missing": [],
            "coverage": 0.0,
            "role_hint": cv.get("jd_role_hint", ""),
            "profile_id": (profile or {}).get("id", "") if isinstance(profile, dict) else "",
        }
        persist_analysis(cv, "nojd", analysis)
        cv["jd_keywords"] = []
        cv["jd_present"] = []
        cv["jd_missing"] = []
        cv["jd_coverage"] = 0.0
        return analysis

    keywords = extract_keywords(jd, lang=lang, max_keywords=60)
    cv_blob = build_cv_blob(cv)
    coverage, present, missing = compute_coverage(cv_blob, keywords[:45])

    analysis = {
        "hash": h,
        "lang": lang,
        "keywords": keywords,
        "present": present,
        "missing": missing,
        "coverage": coverage,
        "role_hint": cv.get("jd_role_hint", ""),
        "profile_id": (profile or {}).get("id", "") if isinstance(profile, dict) else "",
    }
    persist_analysis(cv, h, analysis)

    # mirror fields
    cv["jd_keywords"] = keywords
    cv["jd_present"] = present
    cv["jd_missing"] = missing
    cv["jd_coverage"] = float(coverage)

    return analysis


def auto_update_on_change(cv: Dict[str, Any], profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    If JD hash changed vs last known active hash, auto re-analyze & persist.
    """
    ensure_jd_state(cv)
    jd = (cv.get("job_description") or "").strip()
    h = job_hash(jd)
    if cv.get("jd_active_hash") != h:
        return analyze_jd(cv, profile=profile)

    # if same hash, hydrate from store (in case mirror got cleared)
    cached = load_analysis(cv, h)
    if cached and not cv.get("jd_keywords"):
        cv["jd_keywords"] = cached.get("keywords", [])
        cv["jd_present"] = cached.get("present", [])
        cv["jd_missing"] = cached.get("missing", [])
        cv["jd_coverage"] = float(cached.get("coverage", 0.0))
        cv["jd_lang"] = cached.get("lang", cv.get("jd_lang", "en"))
    return cached or analyze_jd(cv, profile=profile)


def apply_missing_to_extra_keywords(cv: Dict[str, Any], limit: int = 25) -> None:
    missing = cv.get("jd_missing", []) or []
    if not missing:
        return
    existing = (cv.get("modern_keywords_extra") or "").strip()
    add = ", ".join([m for m in missing[:limit] if str(m).strip()])
    cv["modern_keywords_extra"] = (existing + (", " if existing and add else "") + add).strip()


def update_rewrite_templates_from_jd(cv: Dict[str, Any], profile: Optional[Dict[str, Any]] = None) -> List[str]:
    """
    Build a template list that is:
    - profile bullet_templates first
    - then a couple JD-aware templates
    Store in cv['ats_rewrite_templates_active'] for ats_rewrite.py usage.
    """
    base: List[str] = []
    if isinstance(profile, dict):
        bt = profile.get("bullet_templates", [])
        if isinstance(bt, list):
            base.extend([str(x) for x in bt if str(x).strip()])

    lang = cv.get("jd_lang") or "en"
    role = (cv.get("jd_role_hint") or "").strip().lower()

    if lang == "ro":
        jd_templates = [
            "Am aplicat {control_or_feature} în {environment}; am îmbunătățit {metric} cu {value}.",
            "Am automatizat {process} folosind {tool_or_tech}; am redus efortul manual cu {value}.",
            "Am investigat și remediat {issue}; am redus {metric} cu {value}.",
        ]
        if "soc" in role:
            jd_templates.insert(0, "Am monitorizat alertele în {siem}; am triat incidentele și am escaladat conform playbook-urilor.")
        if "penetration" in role:
            jd_templates.insert(0, "Am efectuat penetration testing pe {scope}; am identificat {vuln_type} și am livrat recomandări de remediere.")
    else:
        jd_templates = [
            "Implemented {control_or_feature} across {environment}; improved {metric} by {value}.",
            "Automated {process} using {tool_or_tech}; reduced manual effort by {value}.",
            "Investigated and remediated {issue}; reduced {metric} by {value}.",
        ]
        if "soc" in role:
            jd_templates.insert(0, "Monitored alerts in {siem}; triaged incidents and escalated per playbooks.")
        if "penetration" in role:
            jd_templates.insert(0, "Performed penetration testing on {scope}; identified {vuln_type} and delivered remediation guidance.")

    # dedupe, keep order
    seen = set()
    out: List[str] = []
    for t in base + jd_templates:
        k = t.strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(t.strip())

    cv["ats_rewrite_templates_active"] = out
    return out


def reset_ats_jd_only(cv: Dict[str, Any], keep_history: bool = True) -> None:
    """
    Reset only ATS/JD related fields.
    """
    cv["job_description"] = ""
    cv["jd_active_hash"] = "nojd"
    cv["jd_lang"] = "en"
    cv["jd_role_hint"] = ""

    for k in ["jd_keywords", "jd_present", "jd_missing", "jd_coverage"]:
        cv.pop(k, None)

    # optional history wipe
    if not keep_history:
        cv["jd_store"] = {}
