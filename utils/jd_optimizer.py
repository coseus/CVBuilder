from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


# ----------------------------
# Language detection (simple, offline)
# ----------------------------
_EN_STOP = {
    "the","a","an","and","or","to","of","in","on","for","with","as","at","by","from","is","are","was","were",
    "this","that","these","those","you","we","they","i","he","she","it","our","your","their",
    "experience","years","year","role","responsibilities","requirements","skills","knowledge",
}
_RO_STOP = {
    "și","sau","de","din","în","pe","la","cu","ca","prin","pentru","este","sunt","a","un","o","unei","unei",
    "acest","aceasta","aceste","acei","cei","cea","care","fie","fii","fiecare","anii","an","ani",
    "experiență","experienta","responsabilități","responsabilitati","cerințe","cerinte","abilități","abilitati",
    "cunoștințe","cunostinte",
}

def detect_lang(text: str, hint: Optional[str] = None) -> str:
    """
    Returns 'en' or 'ro'. If hint is provided and valid, uses it.
    """
    if hint in ("en", "ro"):
        return hint
    t = (text or "").lower()
    # Count stopwords hits
    en = sum(1 for w in _EN_STOP if f" {w} " in f" {t} ")
    ro = sum(1 for w in _RO_STOP if f" {w} " in f" {t} ")
    # Romanian diacritics heuristic
    if any(ch in t for ch in "ăâîșşțţ"):
        ro += 3
    return "ro" if ro > en else "en"


# ----------------------------
# Hashing / normalization
# ----------------------------
def _norm_text(s: str) -> str:
    s = (s or "").strip()
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def job_hash(text: str) -> str:
    """
    Stable hash for a JD. Used as job_id.
    """
    n = _norm_text(text).lower()
    return hashlib.sha256(n.encode("utf-8")).hexdigest()[:12]


# ----------------------------
# Tokenization helpers
# ----------------------------
_WORD_RX = re.compile(r"[A-Za-zĂÂÎȘŞȚŢăâîșşțţ0-9][A-Za-zĂÂÎȘŞȚŢăâîșşțţ0-9\+\#\.\-_/]*")

def _tokens(text: str) -> List[str]:
    return [m.group(0) for m in _WORD_RX.finditer(text or "")]

def _lower_tokens(text: str) -> List[str]:
    return [t.lower() for t in _tokens(text)]

def _dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for it in items:
        k = it.strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(it.strip())
    return out


# ----------------------------
# Keyword bank from profile (already normalized by utils/profiles.py)
# ----------------------------
def build_keyword_bank(profile: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Returns keyword buckets. Each bucket is list[str].
    Expected schema:
      profile['keywords'] = { core, technologies, tools, certifications, frameworks, soft_skills }
    """
    kw = profile.get("keywords") if isinstance(profile, dict) else {}
    if not isinstance(kw, dict):
        return {
            "core": [], "technologies": [], "tools": [], "certifications": [], "frameworks": [], "soft_skills": []
        }

    out = {}
    for k in ("core","technologies","tools","certifications","frameworks","soft_skills"):
        v = kw.get(k, [])
        if isinstance(v, list):
            out[k] = [str(x).strip() for x in v if str(x).strip()]
        elif isinstance(v, str):
            out[k] = [s.strip() for s in v.splitlines() if s.strip()]
        else:
            out[k] = []
    return out


# ----------------------------
# Phrase matching (multiword-safe)
# ----------------------------
def _compile_phrases(phrases: List[str]) -> List[Tuple[str, re.Pattern]]:
    compiled = []
    for p in phrases:
        s = (p or "").strip()
        if not s:
            continue
        # Escape and allow flexible whitespace / separators for multiword terms
        # e.g. "azure ad" matches "Azure AD" etc.
        rx = re.escape(s)
        rx = rx.replace(r"\ ", r"\s+")
        pat = re.compile(rf"(?<!\w){rx}(?!\w)", re.IGNORECASE)
        compiled.append((s, pat))
    return compiled

def _count_phrase_hits(text: str, compiled: List[Tuple[str, re.Pattern]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for phrase, pat in compiled:
        hits = len(pat.findall(text or ""))
        if hits > 0:
            counts[phrase] = hits
    return counts


# ----------------------------
# Candidate extraction (fallback): frequent n-grams
# ----------------------------
def _ngram_candidates(text: str, lang: str, max_terms: int = 20) -> List[str]:
    lt = _lower_tokens(text)
    stop = _RO_STOP if lang == "ro" else _EN_STOP

    # keep alpha-ish tokens only
    lt = [t for t in lt if len(t) >= 3 and not t.isdigit()]
    lt = [t for t in lt if t not in stop]

    # unigram + bigram
    freq: Dict[str, int] = {}
    for i, w in enumerate(lt):
        freq[w] = freq.get(w, 0) + 1
        if i + 1 < len(lt):
            bg = f"{w} {lt[i+1]}"
            freq[bg] = freq.get(bg, 0) + 1

    # sort by frequency, prefer multiword
    items = sorted(freq.items(), key=lambda x: (x[1], len(x[0].split())), reverse=True)
    out = []
    for term, c in items:
        if c < 2 and len(out) >= 8:
            break
        if term in stop:
            continue
        out.append(term)
        if len(out) >= max_terms:
            break
    return _dedupe_keep_order(out)


# ----------------------------
# Main analysis
# ----------------------------
@dataclass
class JDResult:
    job_id: str
    lang: str
    jd_text: str
    matched: Dict[str, List[str]]          # bucket -> matched phrases
    counts: Dict[str, int]                 # phrase -> hits
    coverage: Dict[str, float]             # bucket -> coverage ratio
    score: int                             # 0..100
    suggested_extra_keywords: List[str]     # for modern_keywords_extra
    suggested_templates: List[str]          # ranked templates


def analyze_job_description(
    jd_text: str,
    profile: Dict[str, Any],
    lang_hint: Optional[str] = None,
) -> JDResult:
    jd = _norm_text(jd_text)
    if not jd:
        raise ValueError("Empty Job Description")

    lang = detect_lang(jd, hint=lang_hint)
    job_id = job_hash(jd)

    bank = build_keyword_bank(profile)
    all_phrases: List[str] = []
    bucket_phrases: Dict[str, List[str]] = {}
    for b, phrases in bank.items():
        bucket_phrases[b] = _dedupe_keep_order([p for p in phrases if p])
        all_phrases.extend(bucket_phrases[b])
    all_phrases = _dedupe_keep_order(all_phrases)

    compiled_all = _compile_phrases(all_phrases)
    counts = _count_phrase_hits(jd, compiled_all)

    matched: Dict[str, List[str]] = {}
    coverage: Dict[str, float] = {}

    total_phrases = max(1, len(all_phrases))
    total_matched = 0

    for b, phrases in bucket_phrases.items():
        m = [p for p in phrases if p in counts]
        matched[b] = m
        total_matched += len(m)
        coverage[b] = (len(m) / max(1, len(phrases))) if phrases else 0.0

    # score: weighted by important buckets
    # core(30), technologies(20), tools(20), frameworks(10), certs(10), soft(10)
    weights = {
        "core": 30, "technologies": 20, "tools": 20, "frameworks": 10, "certifications": 10, "soft_skills": 10
    }
    score = 0
    for b, w in weights.items():
        score += int(round(coverage.get(b, 0.0) * w))
    score = max(0, min(100, score))

    # Suggested extra keywords: top matched (by hit count) + candidates
    matched_sorted = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    top_matched = [k for k, v in matched_sorted[:25]]

    candidates = _ngram_candidates(jd, lang=lang, max_terms=18)
    # remove candidates that are already matched
    candidates = [c for c in candidates if c.lower() not in {m.lower() for m in top_matched}]

    suggested_extra_keywords = _dedupe_keep_order(top_matched[:18] + candidates[:12])

    # Template ranking: pick templates that “fit” by keyword presence (simple)
    templates = profile.get("bullet_templates", [])
    if not isinstance(templates, list):
        templates = []
    # score template by how many matched keywords appear in template string
    # (usually templates are placeholders; still keep order deterministic)
    def tmpl_score(t: str) -> int:
        s = (t or "").lower()
        # +1 if mentions security / automation / incident / etc. based on lang words
        bonus = 0
        for w in ("security","incident","vulnerability","monitor","automate","deploy","optimize","risk","compliance",
                  "securitate","incident","vulnerabil","monitor","automat","deploy","optimiz","risc","conform"):
            if w in s:
                bonus += 1
        return bonus

    suggested_templates = sorted([str(t) for t in templates if str(t).strip()], key=tmpl_score, reverse=True)[:8]

    return JDResult(
        job_id=job_id,
        lang=lang,
        jd_text=jd,
        matched=matched,
        counts=counts,
        coverage=coverage,
        score=score,
        suggested_extra_keywords=suggested_extra_keywords,
        suggested_templates=suggested_templates,
    )


# ----------------------------
# Persist in CV dict
# ----------------------------
def ensure_jd_store(cv: Dict[str, Any]) -> Dict[str, Any]:
    """
    cv['jd_store'] = {
      job_id: {
        'lang': 'en'/'ro',
        'jd_text': '...',
        'result': {..lightweight..},
        'overlay': {...}   # keywords/templates applied
      }
    }
    cv['active_job_id'] = job_id
    """
    if not isinstance(cv, dict):
        raise ValueError("cv must be a dict")
    cv.setdefault("jd_store", {})
    if not isinstance(cv["jd_store"], dict):
        cv["jd_store"] = {}
    cv.setdefault("active_job_id", "")
    return cv


def store_result(cv: Dict[str, Any], res: JDResult) -> None:
    ensure_jd_store(cv)

    # lightweight result (no heavy objects)
    cv["jd_store"][res.job_id] = {
        "lang": res.lang,
        "jd_text": res.jd_text,
        "result": {
            "score": res.score,
            "coverage": res.coverage,
            "matched": res.matched,
            "counts": dict(sorted(res.counts.items(), key=lambda x: x[1], reverse=True)[:50]),
            "suggested_extra_keywords": res.suggested_extra_keywords[:30],
            "suggested_templates": res.suggested_templates[:8],
        },
        "overlay": {},
    }
    cv["active_job_id"] = res.job_id


def list_jobs(cv: Dict[str, Any]) -> List[Tuple[str, str]]:
    ensure_jd_store(cv)
    jobs = []
    for job_id, obj in cv["jd_store"].items():
        if not isinstance(obj, dict):
            continue
        lang = obj.get("lang", "en")
        text = obj.get("jd_text", "")
        title = (text.splitlines()[0][:60] if text else job_id)
        jobs.append((f"[{lang}] {title}", job_id))
    return jobs


def build_overlay_from_result(res: JDResult) -> Dict[str, Any]:
    """
    Overlay used to influence ATS rewrite + skills keywords per job.
    """
    overlay = {
        "lang": res.lang,
        "keywords_extra": res.suggested_extra_keywords[:30],
        "templates_ranked": res.suggested_templates[:8],
        "matched_buckets": res.matched,
    }
    return overlay


def apply_overlay_to_cv(cv: Dict[str, Any], overlay: Dict[str, Any]) -> None:
    """
    Applies job-specific overlay into CV fields used by Modern export + ATS helper.
    - Updates modern_keywords_extra (append)
    - Stores ats_job_overlay for other components (rewrite/templates/scoring)
    """
    if not isinstance(cv, dict) or not isinstance(overlay, dict):
        return

    # Keep overlay in CV for other components
    cv["ats_job_overlay"] = overlay

    kws = overlay.get("keywords_extra", [])
    if not isinstance(kws, list):
        kws = []

    # Update modern_keywords_extra (newline separated)
    existing = (cv.get("modern_keywords_extra") or "").strip()
    existing_lines = [x.strip() for x in existing.splitlines() if x.strip()]
    merged = existing_lines + [str(x).strip() for x in kws if str(x).strip()]
    # dedupe
    seen = set()
    out = []
    for k in merged:
        low = k.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(k)

    cv["modern_keywords_extra"] = "\n".join(out).strip()

    # Also store a simple summary string for UI
    cv["ats_last_job_score"] = overlay.get("score", cv.get("ats_last_job_score", 0))
