from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------
# Storage (per-job persistence)
# ---------------------------

def _app_data_dir() -> str:
    # Streamlit Cloud: filesystem is ephemeral, but still works per session
    base = os.environ.get("CVBUILDER_DATA_DIR", ".cvbuilder_data")
    os.makedirs(base, exist_ok=True)
    return base


def _jd_db_path() -> str:
    return os.path.join(_app_data_dir(), "jd_analyses.json")


def _load_db() -> Dict[str, Any]:
    p = _jd_db_path()
    if not os.path.exists(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_db(db: Dict[str, Any]) -> None:
    p = _jd_db_path()
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception:
        # best-effort
        pass


# ---------------------------
# Language detect (lightweight offline)
# ---------------------------

_RO_MARKERS = {"și", "sau", "pentru", "care", "din", "fără", "între", "este", "sunt", "când", "trebuie"}
_EN_MARKERS = {"and", "or", "for", "with", "without", "between", "is", "are", "when", "must", "should"}


def detect_lang(text: str, hint: str = "auto") -> str:
    hint = (hint or "auto").lower()
    if hint in ("ro", "en"):
        return hint

    t = (text or "").lower()
    ro = sum(1 for w in _RO_MARKERS if w in t)
    en = sum(1 for w in _EN_MARKERS if w in t)

    # diacritics -> RO
    if re.search(r"[ăâîșț]", t):
        ro += 2

    if ro > en:
        return "ro"
    return "en"


# ---------------------------
# Keyword extraction (offline, EN/RO)
# ---------------------------

_STOP_EN = {
    "the","a","an","and","or","to","in","on","for","with","of","from","at","by","as","is","are","be","will",
    "you","your","we","our","they","their","this","that","these","those","role","team","years","year","must","should",
    "responsible","responsibility","requirements","skills","experience"
}
_STOP_RO = {
    "și","sau","în","pe","pentru","cu","din","la","de","prin","ca","este","sunt","fi","vei","tu","voi","noi","ei","ele",
    "acest","această","aceste","acei","rol","echipă","ani","an","trebuie","responsabil","responsabilități","cerințe","abilități",
    "experiență"
}

# Keep common tech tokens
_TECH_KEEP = {
    "aws","azure","gcp","m365","o365","entra","active","directory","ad","iam","vpn","vlan","siem","soc","edr","xdr","splunk",
    "sentinel","defender","linux","windows","vmware","hyper-v","kubernetes","docker","terraform","ansible",
    "powershell","bash","python","sql","nginx","apache","firewall","waf","sso","mfa","oauth","saml","oidc",
    "burp","nmap","metasploit","nessus","qualys"
}


def _tokenize(text: str) -> List[str]:
    t = (text or "").replace("\u2013", "-").replace("\u2014", "-")
    # allow + # . - in tokens (C++, C#, node.js, etc.)
    toks = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9\+\#\.\-_/]{1,}", t.lower())
    return toks


def extract_keywords(text: str, lang: str = "en", max_keywords: int = 120) -> List[str]:
    toks = _tokenize(text)
    stop = _STOP_RO if lang == "ro" else _STOP_EN

    # simple scoring: frequency, plus boost for tech-ish tokens
    freq: Dict[str, int] = {}
    for w in toks:
        if len(w) < 3:
            continue
        if w in stop and w not in _TECH_KEEP:
            continue
        if re.fullmatch(r"\d+", w):
            continue
        freq[w] = freq.get(w, 0) + 1

    scored = []
    for w, c in freq.items():
        score = c
        if w in _TECH_KEEP:
            score += 3
        if any(ch in w for ch in ("+", "#", ".", "-", "/")):
            score += 1
        scored.append((score, c, w))

    scored.sort(reverse=True)
    out = []
    seen = set()
    for _, _, w in scored:
        if w in seen:
            continue
        seen.add(w)
        out.append(w)
        if len(out) >= max_keywords:
            break
    return out


# ---------------------------
# Hashing / persistence per JD
# ---------------------------

def jd_hash(text: str) -> str:
    t = (text or "").strip().encode("utf-8", errors="ignore")
    return hashlib.sha1(t).hexdigest()[:16]


@dataclass
class JDAnalysis:
    lang: str
    role_hint: str
    keywords: List[str]
    matched: List[str]
    missing: List[str]
    coverage: int  # 0..100


def _flatten_cv_text(cv: Dict[str, Any]) -> str:
    parts: List[str] = []

    for k in [
        "profile_line",
        "pozitie_vizata",
        "nume_prenume",
        "email",
        "telefon",
        "adresa",
        "linkedin",
        "github",
        "website",
        "modern_skills_headline",
        "modern_tools",
        "modern_certs",
        "modern_keywords_extra",
    ]:
        v = cv.get(k)
        if isinstance(v, str) and v.strip():
            parts.append(v)

    rb = cv.get("rezumat_bullets", [])
    if isinstance(rb, list):
        parts.extend([str(x) for x in rb if str(x).strip()])

    exp = cv.get("experienta", [])
    if isinstance(exp, list):
        for e in exp:
            if not isinstance(e, dict):
                continue
            for kk in ("titlu", "functie", "angajator", "activitati", "tehnologii"):
                vv = e.get(kk)
                if isinstance(vv, str) and vv.strip():
                    parts.append(vv)

    edu = cv.get("educatie", [])
    if isinstance(edu, list):
        for ed in edu:
            if not isinstance(ed, dict):
                continue
            for kk in ("titlu", "organizatie", "descriere"):
                vv = ed.get(kk)
                if isinstance(vv, str) and vv.strip():
                    parts.append(vv)

    return "\n".join(parts).lower()


def analyze_jd(cv: Dict[str, Any], jd_text: str, lang_hint: str = "auto", role_hint: str = "") -> JDAnalysis:
    lang = detect_lang(jd_text, hint=lang_hint)
    kws = extract_keywords(jd_text, lang=lang, max_keywords=140)

    cv_text = _flatten_cv_text(cv)
    matched = [k for k in kws if k in cv_text]
    missing = [k for k in kws if k not in cv_text]

    coverage = 0
    if kws:
        coverage = int(100 * len(matched) / max(1, len(kws)))

    return JDAnalysis(
        lang=lang,
        role_hint=(role_hint or "").strip(),
        keywords=kws,
        matched=matched,
        missing=missing,
        coverage=coverage,
    )


def save_analysis(job_id: str, jd_text: str, analysis: JDAnalysis) -> None:
    db = _load_db()
    db[job_id] = {
        "jd": jd_text,
        "lang": analysis.lang,
        "role_hint": analysis.role_hint,
        "keywords": analysis.keywords,
        "matched": analysis.matched,
        "missing": analysis.missing,
        "coverage": analysis.coverage,
    }
    _save_db(db)


def load_analysis(job_id: str) -> Optional[Dict[str, Any]]:
    db = _load_db()
    v = db.get(job_id)
    return v if isinstance(v, dict) else None


# ---------------------------
# Apply to CV (offline auto-update)
# ---------------------------

def apply_jd_to_cv(cv: Dict[str, Any], analysis: JDAnalysis, mode: str = "append") -> None:
    """
    Applies missing keywords into Modern ATS fields (offline).
    - mode="append": appends missing keywords into modern_keywords_extra
    - mode="replace": replaces modern_keywords_extra with missing keywords (first N)
    """
    cv.setdefault("modern_keywords_extra", "")

    missing = analysis.missing[:60]  # keep sane
    if not missing:
        return

    existing_lines = [ln.strip() for ln in str(cv.get("modern_keywords_extra") or "").splitlines() if ln.strip()]
    existing_set = {x.lower() for x in existing_lines}

    new_lines = []
    for k in missing:
        if k.lower() in existing_set:
            continue
        new_lines.append(k)

    if not new_lines:
        return

    if mode == "replace":
        cv["modern_keywords_extra"] = "\n".join(new_lines)
        return

    # append
    combined = existing_lines + new_lines
    cv["modern_keywords_extra"] = "\n".join(combined)


def role_hints_from_profile(profile: Dict[str, Any]) -> List[str]:
    """
    Build role hints list from profile job_titles (plus safe defaults).
    """
    hints: List[str] = []
    jt = profile.get("job_titles", [])
    if isinstance(jt, list):
        for x in jt:
            s = str(x).strip()
            if s:
                hints.append(s.lower())

    # fallback defaults
    if not hints:
        hints = ["general", "it", "operations"]
    # dedupe preserve
    seen = set()
    out = []
    for h in hints:
        if h in seen:
            continue
        seen.add(h)
        out.append(h)
    return out[:12]
