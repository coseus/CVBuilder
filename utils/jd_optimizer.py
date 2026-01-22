# utils/jd_optimizer.py
from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple


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
și si sau ori in în la pe cu din de a al ai ale alea unei unui un una unei care ce că ca pentru prin peste sub sus jos
este sunt era au avea avem aveam voi tu el ea ei ele noi lor
""".split())

_TECH_KEEP = set([
    "c#", "c++", ".net", "node.js", "node", "aws", "azure", "gcp", "m365", "o365",
    "siem", "soc", "edr", "xdr", "iam", "sso", "mfa", "vpn", "vlan", "ad", "entra",
    "tcp", "udp", "dns", "dhcp", "http", "https", "ssh", "rdp", "sql", "linux", "windows",
    "kubernetes", "k8s", "docker", "terraform", "ansible",
])


# -------------------------
# State helpers (public API)
# -------------------------
def ensure_jd_state(cv: Dict[str, Any]) -> None:
    """
    Shared JD state used by:
      - app.py "Job Description (shared)"
      - components/ats_optimizer.py
      - components/ats_helper_panel.py
      - components/ats_dashboard.py
    """
    if not isinstance(cv, dict):
        return

    cv.setdefault("job_description", "")
    cv.setdefault("jd_lang", "en")
    cv.setdefault("jd_role_hint", "")

    # persistent store per hash
    cv.setdefault("jd_store", {})         # hash -> analysis dict
    cv.setdefault("jd_active_hash", "nojd")

    # mirrored quick fields used by dashboard/helper
    cv.setdefault("jd_keywords", [])
    cv.setdefault("jd_present", [])
    cv.setdefault("jd_missing", [])
    cv.setdefault("jd_coverage", 0.0)

    # templates per job (used by ats_rewrite / helper)
    cv.setdefault("ats_rewrite_templates_active", [])


def get_current_jd(cv: Dict[str, Any]) -> str:
    ensure_jd_state(cv)
    return str(cv.get("job_description") or "")


def set_current_jd(cv: Dict[str, Any], text: str) -> None:
    ensure_jd_state(cv)
    cv["job_description"] = text or ""


def get_current_analysis(cv: Dict[str, Any]) -> Dict[str, Any]:
    ensure_jd_state(cv)
    h = str(cv.get("jd_active_hash") or "nojd")
    store = cv.get("jd_store")
    if isinstance(store, dict) and h in store:
        return store[h] or {}
    # fallback from mirrors
    return {
        "hash": h,
        "lang": cv.get("jd_lang", "en"),
        "keywords": cv.get("jd_keywords", []),
        "present": cv.get("jd_present", []),
        "missing": cv.get("jd_missing", []),
        "coverage": float(cv.get("jd_coverage", 0.0) or 0.0),
        "role_hint": cv.get("jd_role_hint", ""),
    }


def get_current_analysis_or_blank(cv: Dict[str, Any]) -> Dict[str, Any]:
    a = get_current_analysis(cv)
    return a if isinstance(a, dict) else {}


# -------------------------
# Core analysis (offline)
# -------------------------
def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def detect_language(text: str) -> str:
    t = (text or "").lower()
    if not t.strip():
        return "en"
    ro_hits = 0
    en_hits = 0
    if re.search(r"[ăâîșşțţ]", t):
        ro_hits += 3
    ro_hits += len(re.findall(r"\b(și|sau|în|din|pentru|cu|la|pe|care|este|sunt)\b", t))
    en_hits += len(re.findall(r"\b(and|or|the|with|for|to|is|are|you|we)\b", t))
    return "ro" if ro_hits > en_hits else "en"


def job_hash(text: str) -> str:
    b = (text or "").strip().encode("utf-8", errors="ignore")
    return hashlib.sha256(b).hexdigest()[:12] if b else "nojd"


def extract_keywords(text: str, lang: Optional[str] = None, max_keywords: int = 60) -> List[str]:
    t = _norm(text)
    if not t:
        return []
    if not lang:
        lang = detect_language(t)

    stop = _STOPWORDS_RO if lang == "ro" else _STOPWORDS_EN

    # keep tech-ish tokens
    tokens = re.findall(r"[a-z0-9][a-z0-9\+\#\.\-/]{1,}", t)

    cleaned: List[str] = []
    for tok in tokens:
        tok = tok.strip(".-/")
        if not tok:
            continue
        if tok in _TECH_KEEP:
            cleaned.append(tok)
            continue
        if len(tok) < 3:
            continue
        if tok in stop:
            continue
        cleaned.append(tok)

    freq = Counter(cleaned)
    ranked = [w for w, _ in freq.most_common(max_keywords)]
    # de-dupe preserve (Counter already)
    return ranked


def build_cv_blob(cv: Dict[str, Any]) -> str:
    """
    Text blob for matching keywords: keep it simple and robust to schema changes.
    """
    parts: List[str] = []
    parts.append(str(cv.get("pozitie_vizata", "") or ""))
    parts.append(str(cv.get("rezumat", "") or ""))

    # skills fields used by your exporters
    parts.append(str(cv.get("modern_skills_headline", "") or ""))
    parts.append(str(cv.get("modern_tools", "") or ""))
    parts.append(str(cv.get("modern_certs", "") or ""))
    parts.append(str(cv.get("modern_keywords_extra", "") or ""))

    # experience
    for e in (cv.get("experienta") or []):
        if not isinstance(e, dict):
            continue
        parts.append(str(e.get("functie", "") or ""))
        parts.append(str(e.get("angajator", "") or ""))
        parts.append(str(e.get("tehnologii", "") or ""))
        parts.append(str(e.get("activitati", "") or ""))

    # education (handle both schemas)
    for ed in (cv.get("educatie") or []):
        if not isinstance(ed, dict):
            continue
        parts.append(str(ed.get("titlu", "") or ed.get("calificare", "") or ""))
        parts.append(str(ed.get("organizatie", "") or ed.get("institutie", "") or ""))

    return "\n".join([p for p in parts if p])


def compute_coverage(cv_text: str, jd_keywords: List[str]) -> Tuple[float, List[str], List[str]]:
    hay = _norm(cv_text)
    present: List[str] = []
    missing: List[str] = []
    for kw in jd_keywords:
        k = _norm(kw)
        if not k:
            continue
        if k in hay:
            present.append(k)
        else:
            missing.append(k)
    cov = len(present) / max(1, len(present) + len(missing))
    return float(cov), present, missing


def persist_analysis(cv: Dict[str, Any], h: str, analysis: Dict[str, Any]) -> None:
    ensure_jd_state(cv)
    store = cv.get("jd_store")
    if not isinstance(store, dict):
        cv["jd_store"] = {}
        store = cv["jd_store"]
    store[h] = analysis


def analyze_jd(
    cv: Dict[str, Any],
    profile: Optional[Dict[str, Any]] = None,
    role_hint: str = "",
) -> Dict[str, Any]:
    """
    Analyze current JD from cv['job_description'], persist per hash,
    and mirror key fields on cv for quick UI.

    NOTE: this signature matches components/ats_optimizer.py.
    """
    ensure_jd_state(cv)

    jd = str(cv.get("job_description") or "").strip()
    lang = detect_language(jd)
    h = job_hash(jd)

    # store role hint
    if role_hint is not None:
        cv["jd_role_hint"] = (role_hint or "").strip()

    cv["jd_lang"] = lang
    cv["jd_active_hash"] = h

    if not jd:
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

    # mirror
    cv["jd_keywords"] = keywords
    cv["jd_present"] = present
    cv["jd_missing"] = missing
    cv["jd_coverage"] = float(coverage)

    return analysis


def auto_update_on_change(cv: Dict[str, Any], profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Re-analyze if JD hash changed.
    """
    ensure_jd_state(cv)
    jd = str(cv.get("job_description") or "").strip()
    h = job_hash(jd)
    if cv.get("jd_active_hash") != h:
        return analyze_jd(cv, profile=profile, role_hint=cv.get("jd_role_hint", ""))
    # hydrate from store if mirrors cleared
    store = cv.get("jd_store")
    if isinstance(store, dict) and h in store:
        a = store[h] or {}
        if not cv.get("jd_keywords"):
            cv["jd_keywords"] = a.get("keywords", [])
            cv["jd_present"] = a.get("present", [])
            cv["jd_missing"] = a.get("missing", [])
            cv["jd_coverage"] = float(a.get("coverage", 0.0) or 0.0)
            cv["jd_lang"] = a.get("lang", cv.get("jd_lang", "en"))
        return a
    return analyze_jd(cv, profile=profile, role_hint=cv.get("jd_role_hint", ""))


# -------------------------
# Apply helpers used by UI buttons
# -------------------------
def apply_missing_to_extra_keywords(cv: Dict[str, Any], limit: int = 25) -> None:
    ensure_jd_state(cv)
    missing = cv.get("jd_missing", []) or []
    if not missing:
        return
    existing = (cv.get("modern_keywords_extra") or "").strip()
    add = ", ".join([m for m in missing[:limit] if str(m).strip()])
    cv["modern_keywords_extra"] = (existing + (", " if existing and add else "") + add).strip()


# Back-compat name used by some components
def apply_auto_to_modern_skills(cv: Dict[str, Any], analysis: Optional[Dict[str, Any]] = None, limit: int = 25) -> None:
    """
    Alias: applies missing keywords into modern_keywords_extra.
    """
    ensure_jd_state(cv)
    if analysis and isinstance(analysis, dict):
        missing = analysis.get("missing", []) or []
        if missing:
            existing = (cv.get("modern_keywords_extra") or "").strip()
            add = ", ".join([m for m in missing[:limit] if str(m).strip()])
            cv["modern_keywords_extra"] = (existing + (", " if existing and add else "") + add).strip()
            return
    apply_missing_to_extra_keywords(cv, limit=limit)


def update_rewrite_templates_from_jd(cv: Dict[str, Any], profile: Optional[Dict[str, Any]] = None) -> List[str]:
    """
    Build a template list:
      - profile bullet_templates first
      - then a few JD-aware templates (RO/EN)
    Saves in cv['ats_rewrite_templates_active'].
    """
    ensure_jd_state(cv)

    base: List[str] = []
    if isinstance(profile, dict):
        bt = profile.get("bullet_templates", [])
        if isinstance(bt, list):
            base.extend([str(x) for x in bt if str(x).strip()])

    lang = (cv.get("jd_lang") or "en").lower()
    role = (cv.get("jd_role_hint") or "").strip().lower()

    if lang == "ro":
        jd_templates = [
            "Am implementat {control_or_feature} în {environment}; am îmbunătățit {metric} cu {value}.",
            "Am automatizat {process} folosind {tool_or_tech}; am redus efortul manual cu {value}.",
            "Am investigat și remediat {issue}; am redus {metric} cu {value}.",
        ]
        if "soc" in role:
            jd_templates.insert(0, "Am triat alerte în {siem}; am investigat incidente și am escaladat conform playbook-urilor.")
        if "penetration" in role or "pentest" in role:
            jd_templates.insert(0, "Am identificat vulnerabilități și am validat impactul; am documentat findings și recomandări de remediere.")
    else:
        jd_templates = [
            "Implemented {control_or_feature} across {environment}; improved {metric} by {value}.",
            "Automated {process} using {tool_or_tech}; reduced manual effort by {value}.",
            "Diagnosed and remediated {issue}; reduced {metric} by {value}.",
        ]
        if "soc" in role:
            jd_templates.insert(0, "Triaged alerts in {siem}; investigated incidents and escalated per playbooks/runbooks.")
        if "penetration" in role or "pentest" in role:
            jd_templates.insert(0, "Identified and validated vulnerabilities; documented findings and remediation guidance.")

    merged: List[str] = []
    seen = set()
    for t in base + jd_templates:
        s = str(t).strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(s)

    cv["ats_rewrite_templates_active"] = merged[:25]
    return cv["ats_rewrite_templates_active"]
