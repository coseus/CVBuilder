# utils/jd_optimizer.py
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Tuple


# ============================================================
# Session/CV state helpers (shared JD + per-job analyses)
# ============================================================
def ensure_jd_state(cv: dict) -> None:
    """
    Ensures CV dict contains the JD analyzer persistent state.
    Canonical JD field: cv["job_description"] (back-compat: cv["jd_text"])
    Persistent analysis: cv["jd_state"].
    """
    if not isinstance(cv, dict):
        return

    # Canonical JD text (single source of truth)
    if "job_description" not in cv and "jd_text" in cv:
        cv["job_description"] = cv.get("jd_text", "") or ""
    cv.setdefault("job_description", "")

    # Back-compat mirror (optional)
    cv.setdefault("jd_text", cv.get("job_description", "") or "")

    # Persistent per-job analysis
    cv.setdefault("jd_state", {})
    st = cv["jd_state"]
    if not isinstance(st, dict):
        cv["jd_state"] = {}
        st = cv["jd_state"]

    st.setdefault("active_job_id", "")
    st.setdefault("jobs", {})  # job_id -> analysis payload
    st.setdefault("current_role_hint", "")
    st.setdefault("last_jd_hash", "")


def get_current_jd(cv: dict) -> str:
    ensure_jd_state(cv)
    jd = (cv.get("job_description") or "").strip()
    if not jd:
        jd = (cv.get("jd_text") or "").strip()
    return jd


def set_current_jd(cv: dict, text: str) -> None:
    ensure_jd_state(cv)
    cv["job_description"] = (text or "")
    cv["jd_text"] = cv["job_description"]


def job_hash(jd_text: str) -> str:
    s = (jd_text or "").strip().encode("utf-8")
    return hashlib.sha256(s).hexdigest()[:16]


# ============================================================
# Language detection + keyword extraction (offline EN/RO)
# ============================================================
_STOP_EN = {
    "and","or","the","a","an","to","of","in","on","for","with","as","at","by","from","is","are","be","will","you",
    "we","our","your","this","that","these","those","it","they","their","them","us","who","what","when","where",
    "job","role","work","team","years","year","experience","skills","skill","responsibilities","responsibility",
    "required","requirements","preferred","plus","nice","have",
}
_STOP_RO = {
    "și","si","sau","un","o","unei","ale","al","a","la","în","in","pe","pentru","cu","ca","din","este","sunt","fi",
    "vei","voi","tu","voi","noi","nostru","noastra","acest","aceasta","aceste","acestia","job","rol","munca","echipa",
    "ani","an","experiență","experienta","abilități","abilitati","competențe","competente","responsabilități",
    "responsabilitati","cerințe","cerinte","preferabil","constitue","avantaj",
}

_TECH_HINTS = {
    "c#", "c++", "go", "aws", "gcp", "azure", "siem", "soar", "edr", "vpn", "lan", "wan", "sso", "mfa", "iam",
    "soc", "dfir", "xdr", "waf", "ids", "ips", "api", "sql", "splunk", "sentinel",
}

_RO_DIACRITICS = {"ă","â","î","ș","ş","ț","ţ"}


def detect_lang(text: str) -> str:
    """
    Tiny offline heuristic: returns 'ro' or 'en'
    """
    t = (text or "").lower()
    ro_diac = sum(1 for ch in t if ch in _RO_DIACRITICS)
    ro_hits = sum(1 for w in ["responsabilități", "cerințe", "experiență", "competențe"] if w in t)
    en_hits = sum(1 for w in ["responsibilities", "requirements", "experience", "skills"] if w in t)
    if ro_diac + ro_hits > en_hits:
        return "ro"
    return "en"


def _tokenize(text: str) -> List[str]:
    # keep tokens like "azure-ad", "c#", "c++", "iso27001"
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

    cleaned = []
    for k in kws:
        if len(k) > 42:
            continue
        if k.count(" ") >= 4:
            continue
        cleaned.append(k)

    return _dedupe_keep_order(cleaned)[:max_keywords]


# ============================================================
# CV text extraction (for coverage)
# ============================================================
def _cv_to_text(cv: dict) -> str:
    """
    Build an ATS-ish text blob from CV fields to compute keyword presence.
    """
    if not isinstance(cv, dict):
        return ""

    parts: List[str] = []

    # Modern skills fields (ATS heavy)
    for k in ("modern_skills_headline", "modern_tools", "modern_certs", "modern_keywords_extra"):
        v = cv.get(k)
        if isinstance(v, str) and v.strip():
            parts.append(v.strip())

    # Summary bullets
    rb = cv.get("rezumat_bullets")
    if isinstance(rb, list):
        for b in rb:
            s = str(b).strip()
            if s:
                parts.append(s)
    elif isinstance(cv.get("rezumat"), str) and cv.get("rezumat").strip():
        parts.append(cv["rezumat"].strip())

    # Experience / projects
    exp = cv.get("experienta")
    if isinstance(exp, list):
        for e in exp:
            if not isinstance(e, dict):
                continue
            for k in ("functie", "angajator", "titlu", "tehnologii", "activitati", "sector"):
                val = e.get(k)
                if isinstance(val, str) and val.strip():
                    parts.append(val.strip())

    # Education
    edu = cv.get("educatie")
    if isinstance(edu, list):
        for ed in edu:
            if not isinstance(ed, dict):
                continue
            for k in ("titlu", "organizatie", "descriere"):
                val = ed.get(k)
                if isinstance(val, str) and val.strip():
                    parts.append(val.strip())

    # Languages
    langs = cv.get("limbi_straine")
    if isinstance(langs, list):
        for l in langs:
            if isinstance(l, dict):
                parts.append(f"{l.get('limba','')} {l.get('nivel','')}".strip())

    return "\n".join(parts)


def _presence_score(cv_text: str, keywords: List[str]) -> Tuple[List[str], List[str], float]:
    """
    present/missing + coverage%
    - uses simple substring match in normalized lower text
    """
    t = (cv_text or "").lower()

    present: List[str] = []
    missing: List[str] = []
    for kw in keywords:
        k = (kw or "").strip().lower()
        if not k:
            continue
        if k in t:
            present.append(kw)
        else:
            missing.append(kw)

    total = max(1, len(keywords))
    coverage = (len(present) / total) * 100.0
    return present, missing, coverage


# ============================================================
# Analyze JD (persist per hash) + shared analysis getters
# ============================================================
def analyze_jd(
    cv: dict,
    role_hint: str = "",
    profile: Optional[dict] = None,
    max_keywords: int = 80,
) -> Dict[str, Any]:
    """
    Analyzes current JD in cv, stores under cv["jd_state"]["jobs"][hash], sets active_job_id.
    Returns analysis dict.
    """
    ensure_jd_state(cv)

    jd = get_current_jd(cv).strip()
    lang = detect_lang(jd) if jd else "en"
    jid = job_hash(jd) if jd else ""

    if role_hint:
        cv["jd_state"]["current_role_hint"] = role_hint

    analysis: Dict[str, Any] = {
        "hash": jid,
        "lang": lang,
        "role_hint": role_hint or cv["jd_state"].get("current_role_hint", "") or "",
        "keywords": [],
        "present": [],
        "missing": [],
        "coverage": 0.0,
        "profile_id": (profile.get("id") if isinstance(profile, dict) else "") or "",
    }

    if not jd:
        # empty -> keep active empty
        cv["jd_state"]["active_job_id"] = ""
        return analysis

    keywords = extract_keywords(jd, lang=lang, max_keywords=max_keywords)
    cv_text = _cv_to_text(cv)
    present, missing, coverage = _presence_score(cv_text, keywords)

    analysis.update({
        "keywords": keywords,
        "present": present,
        "missing": missing,
        "coverage": coverage,
    })

    # persist
    stt = cv["jd_state"]
    jobs = stt.get("jobs", {})
    if not isinstance(jobs, dict):
        jobs = {}
        stt["jobs"] = jobs

    jobs[jid] = analysis
    stt["active_job_id"] = jid
    stt["last_jd_hash"] = jid

    # keep a simple cache key some components might use
    cv["ats_analysis"] = analysis

    return analysis


def get_current_analysis(cv: dict) -> Dict[str, Any]:
    """
    Returns active job analysis if available, else runs analyze_jd (light) on the fly.
    """
    ensure_jd_state(cv)
    jid = cv["jd_state"].get("active_job_id") or ""
    jobs = cv["jd_state"].get("jobs", {})
    if isinstance(jobs, dict) and jid and jid in jobs:
        return jobs[jid]
    # fallback compute
    return analyze_jd(cv, role_hint=cv["jd_state"].get("current_role_hint", "") or "")


def auto_update_on_change(cv: dict, profile: Optional[dict] = None) -> None:
    """
    Call on rerun to auto-analyze when JD changes (hash changes).
    """
    ensure_jd_state(cv)
    jd = get_current_jd(cv).strip()
    if not jd:
        return

    jid = job_hash(jd)
    prev = cv["jd_state"].get("last_jd_hash", "") or ""
    if jid == prev and cv["jd_state"].get("active_job_id") == jid:
        return

    analyze_jd(cv, role_hint=cv["jd_state"].get("current_role_hint", "") or "", profile=profile)


# ============================================================
# Apply helpers (keywords -> modern fields)
# ============================================================
def apply_auto_to_modern_skills(cv: dict, analysis: Dict[str, Any]) -> None:
    """
    Append analysis keywords to modern_keywords_extra (newline list).
    """
    if not isinstance(cv, dict) or not isinstance(analysis, dict):
        return
    kws = analysis.get("keywords", [])
    if not isinstance(kws, list) or not kws:
        return

    existing = (cv.get("modern_keywords_extra") or "").strip()
    existing_list = [x.strip() for x in existing.splitlines() if x.strip()]
    merged = _dedupe_keep_order(existing_list + [str(x).strip() for x in kws if str(x).strip()])
    cv["modern_keywords_extra"] = "\n".join(merged[:80])


def apply_missing_to_extra_keywords(cv: dict, limit: int = 25) -> None:
    analysis = get_current_analysis(cv)
    missing = analysis.get("missing", [])
    if not isinstance(missing, list) or not missing:
        return

    existing = (cv.get("modern_keywords_extra") or "").strip()
    existing_list = [x.strip() for x in existing.splitlines() if x.strip()]
    merged = _dedupe_keep_order(existing_list + [str(x).strip() for x in missing[:limit] if str(x).strip()])
    cv["modern_keywords_extra"] = "\n".join(merged[:80])


def update_rewrite_templates_from_jd(cv: dict, profile: Optional[dict] = None) -> None:
    """
    Optional hook: store "current JD keywords" into state for rewrite UI.
    Keeps it lightweight. Your ats_rewrite.py can consume cv["jd_state"]["jobs"][hash]["keywords"].
    """
    ensure_jd_state(cv)
    analysis = get_current_analysis(cv)
    # Nothing else needed here; rewrite UI can read analysis payload.


# ============================================================
# AUTO-SUGGEST PROFILE ENGINE (domain libraries aware)
# ============================================================
def _pick_lang(val: Any, lang: str = "en") -> Any:
    if isinstance(val, dict):
        if lang in val and val.get(lang) is not None:
            return val.get(lang)
        if "en" in val and val.get("en") is not None:
            return val.get("en")
        if "ro" in val and val.get("ro") is not None:
            return val.get("ro")
        for _, v in val.items():
            return v
    return val


def _safe_list(x: Any) -> List[str]:
    if x is None:
        return []
    if isinstance(x, list):
        return [str(i).strip() for i in x if str(i).strip()]
    if isinstance(x, str):
        return [s.strip() for s in x.splitlines() if s.strip()]
    return [str(x).strip()] if str(x).strip() else []


def _resolve_library_path(lib_rel: str) -> Optional[str]:
    """
    domains_index.yaml typically contains:
      library: libraries/domains/<domain>.yaml
    We try to resolve it against:
      - user data ats root (if exposed by utils.profiles)
      - repo ats_profiles/
    """
    if not lib_rel:
        return None

    lib_rel = lib_rel.replace("\\", "/").lstrip("/")

    # 1) Try user-data ATS root (if available)
    try:
        from utils import profiles as profmod  # type: ignore
        # try common attrs used in your profiles.py
        candidates = []
        for attr in ("ATS_ROOT_DIR", "USER_LIBRARIES_DIR"):
            base = getattr(profmod, attr, None)
            if base:
                candidates.append(str(base))
        for base in candidates:
            cand = f"{base}/{lib_rel}"
            return cand  # let open fail if not real; fallback below
    except Exception:
        pass

    # 2) Repo relative
    return f"ats_profiles/{lib_rel}"


def _read_yaml_file(path: str) -> Dict[str, Any]:
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            obj = yaml.safe_load(f) or {}
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _library_keywords_for_scoring(lib: Dict[str, Any], lang: str) -> List[str]:
    kw = lib.get("keywords") or {}
    if not isinstance(kw, dict):
        return []
    all_kws: List[str] = []
    for bucket in ("core", "technologies", "tools", "certifications", "frameworks", "soft_skills"):
        vals = _pick_lang(kw.get(bucket), lang=lang)
        all_kws.extend(_safe_list(vals))
    # normalize
    return _dedupe_keep_order([k.lower() for k in all_kws if k])


def suggest_profiles_from_jd(
    jd_text: str,
    lang: str = "en",
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Returns list of suggestions:
      [{ "profile_id": "...", "domain_id": "...", "score": 0-100, "label": "..." }, ...]

    Uses domains_index.yaml mapping domain -> domain library to compute overlap with JD keywords.
    Then maps top domains to available profile ids (if exist).
    """
    jd_text = (jd_text or "").strip()
    if not jd_text:
        return []

    # local keyword set from JD
    jd_lang = detect_lang(jd_text)
    use_lang = lang or jd_lang
    jd_kws = extract_keywords(jd_text, lang=jd_lang, max_keywords=90)
    jd_set = set([k.lower() for k in jd_kws])

    # Load domains index + profiles list
    try:
        from utils.profiles import load_domains_index, list_profiles  # type: ignore
        idx = load_domains_index()
        profiles = list_profiles(lang=use_lang)
    except Exception:
        return []

    available_ids = set()
    id_to_title = {}
    for p in profiles or []:
        pid = str(p.get("id") or "")
        if pid:
            available_ids.add(pid)
            id_to_title[pid] = str(p.get("title") or pid)

    domains: List[Dict[str, Any]] = []
    # index can be grouped
    if isinstance(idx, dict) and isinstance(idx.get("groups"), list):
        for g in idx.get("groups") or []:
            if not isinstance(g, dict):
                continue
            for d in (g.get("domains") or []):
                if isinstance(d, dict) and d.get("id"):
                    dd = dict(d)
                    dd["group_id"] = g.get("id")
                    domains.append(dd)
    # or flat
    if not domains and isinstance(idx, dict) and isinstance(idx.get("domains"), list):
        for d in idx.get("domains") or []:
            if isinstance(d, dict) and d.get("id"):
                domains.append(dict(d))

    scored: List[Tuple[float, Dict[str, Any]]] = []
    for d in domains:
        dom_id = str(d.get("id") or "").strip()
        lib_rel = str(d.get("library") or "").strip()
        if not dom_id or not lib_rel:
            continue

        lib_path = _resolve_library_path(lib_rel)
        if not lib_path:
            continue

        lib_obj = _read_yaml_file(lib_path)
        lib_kws = _library_keywords_for_scoring(lib_obj, lang=use_lang)
        if not lib_kws:
            continue

        lib_set = set(lib_kws)
        overlap = len(jd_set.intersection(lib_set))
        denom = max(1, min(len(jd_set), 40))  # cap influence
        score = (overlap / denom) * 100.0

        scored.append((score, d))

    scored.sort(key=lambda x: x[0], reverse=True)

    out: List[Dict[str, Any]] = []
    for score, d in scored[: max(10, top_k * 2)]:
        dom_id = str(d.get("id"))
        # Map to a profile id if present:
        # Prefer same id; otherwise try common root profiles
        candidate_ids = [dom_id]
        # some domains may share a library; try also "cyber_security" etc if index defines label only
        for cid in candidate_ids:
            if cid in available_ids:
                out.append({
                    "profile_id": cid,
                    "domain_id": dom_id,
                    "score": float(score),
                    "label": id_to_title.get(cid, cid),
                })
                break

    # fallback: if nothing mapped, return top domains as pseudo suggestions
    if not out:
        for score, d in scored[:top_k]:
            out.append({
                "profile_id": str(d.get("id")),
                "domain_id": str(d.get("id")),
                "score": float(score),
                "label": str(_pick_lang(d.get("label"), lang=use_lang) or d.get("id")),
            })

    # keep unique by profile_id, top_k
    uniq = {}
    for s in out:
        pid = s.get("profile_id")
        if pid and pid not in uniq:
            uniq[pid] = s
    return list(uniq.values())[:top_k]


# ============================================================
# Optional: export/import state
# ============================================================
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


# ---------------------------
# Convenience wrapper (used by components)
# ---------------------------
def analyze_current(cv: dict, profile: Optional[dict] = None, role_hint: str = "") -> Dict[str, Any]:
    """
    Analyze the shared JD stored in cv["job_description"] and return the analysis dict.
    This is a thin wrapper over analyze_jd(), keeping backward compatibility for components.

    - persists per-job hash in cv["jd_state"]
    - computes coverage/present/missing via analyze_jd()
    """
    ensure_jd_state(cv)
    jd_text = (cv.get("job_description") or "").strip()
    if not jd_text:
        # keep consistent keys so UI doesn't break
        return {
            "hash": "",
            "lang": cv.get("jd_lang", detect_lang("")),
            "coverage": 0.0,
            "present": [],
            "missing": [],
            "keywords": [],
            "role_hint": role_hint or "",
        }

    # store role_hint in state for convenience
    cv.setdefault("jd_state", {})["current_role_hint"] = role_hint or cv.get("jd_state", {}).get("current_role_hint", "")

    # analyze_jd() in this module already updates state + jobs hash
    return analyze_jd(cv, role_hint=role_hint or cv.get("jd_state", {}).get("current_role_hint", ""), profile=profile)
