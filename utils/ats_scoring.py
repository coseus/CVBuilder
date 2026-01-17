from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


_METRIC_UNITS = [
    "%", "ms", "s", "sec", "mins", "min", "hrs", "hour", "hours",
    "gb", "tb", "req/s", "rps", "users", "hosts", "assets", "endpoints",
    "incidents", "tickets", "sla", "mttr", "mttd", "mtta", "cve", "cvss",
]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def split_bullets(text: str) -> List[str]:
    """Split by newlines; keep non-empty lines."""
    lines = [(l or "").strip(" \t-•") for l in (text or "").splitlines()]
    return [l for l in lines if l]


def bullet_has_metric(b: str) -> bool:
    t = normalize(b)
    if re.search(r"\d", t):
        return True
    for u in _METRIC_UNITS:
        if u in t:
            return True
    # patterns like '2x'
    if re.search(r"\b\d+\s*x\b", t):
        return True
    return False


def starting_verb(b: str) -> str:
    b = (b or "").strip()
    if not b:
        return ""
    first = re.split(r"\s+", b, maxsplit=1)[0]
    return re.sub(r"[^A-Za-z]", "", first)


def flatten_keywords(profile_keywords: Dict[str, Any]) -> List[str]:
    """Flatten nested keyword dict/list into a list of strings."""
    out: List[str] = []

    def walk(x: Any):
        if x is None:
            return
        if isinstance(x, str):
            if x.strip():
                out.append(x.strip())
        elif isinstance(x, list):
            for i in x:
                walk(i)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)

    walk(profile_keywords)
    # de-dupe while preserving order
    seen = set()
    deduped = []
    for k in out:
        kl = k.lower()
        if kl in seen:
            continue
        seen.add(kl)
        deduped.append(k)
    return deduped


@dataclass
class ATSScore:
    keyword_coverage: int
    jd_match: int
    metrics_coverage: int
    verb_variety: int
    completeness: int
    overall: int

    # details
    missing_profile_keywords: List[str]
    missing_jd_keywords: List[str]
    bullets_missing_metrics: List[str]
    repeated_starting_verbs: List[Tuple[str, int]]


def compute_score(cv: Dict[str, Any], profile: Dict[str, Any], jd_keywords: List[str]) -> ATSScore:
    """Compute a practical ATS-oriented score (0-100)."""
    # Build CV text blob
    cv_blob = "\n".join([
        cv.get('pozitie_vizata', ''),
        cv.get('rezumat', ''),
        cv.get('modern_skills_headline', ''),
        cv.get('modern_tools', ''),
        cv.get('modern_certs', ''),
        cv.get('modern_keywords_extra', ''),
        "\n".join([
            f"{e.get('functie','')} {e.get('tehnologii','')} {e.get('activitati','')}"
            for e in (cv.get('experienta') or [])
        ]),
        "\n".join([
            f"{e.get('calificare','')} {e.get('institutie','')}"
            for e in (cv.get('educatie') or [])
        ]),
    ])
    cv_text = normalize(cv_blob)

    profile_kw = flatten_keywords(profile.get('keywords', {}))
    present_profile = [k for k in profile_kw if k.lower() in cv_text]
    missing_profile = [k for k in profile_kw if k.lower() not in cv_text]
    keyword_coverage = int(round(100 * (len(present_profile) / max(1, len(profile_kw)))))

    present_jd = [k for k in jd_keywords if k in cv_text]
    missing_jd = [k for k in jd_keywords if k not in cv_text]
    jd_match = int(round(100 * (len(present_jd) / max(1, len(jd_keywords)))))

    # Bullets: summary + each experience
    all_bullets: List[str] = []
    all_bullets += split_bullets(cv.get('rezumat', ''))
    for e in (cv.get('experienta') or []):
        all_bullets += split_bullets(e.get('activitati', ''))

    if not all_bullets:
        metrics_coverage = 0
        bullets_missing = []
    else:
        with_metrics = [b for b in all_bullets if bullet_has_metric(b)]
        bullets_missing = [b for b in all_bullets if not bullet_has_metric(b)]
        metrics_coverage = int(round(100 * (len(with_metrics) / len(all_bullets))))

    # Verb variety
    verbs = [starting_verb(b) for b in all_bullets if starting_verb(b)]
    unique = len(set(v.lower() for v in verbs))
    total = len(verbs) or 1
    verb_variety = int(round(100 * (unique / total)))

    # repeated verbs
    counts: Dict[str, int] = {}
    for v in verbs:
        vl = v.lower()
        counts[vl] = counts.get(vl, 0) + 1
    repeated = sorted([(v, c) for v, c in counts.items() if c >= 3], key=lambda x: (-x[1], x[0]))

    # completeness
    checks = [
        bool(cv.get('nume_prenume')),
        bool(cv.get('email')),
        bool(cv.get('telefon')),
        bool(cv.get('rezumat')),
        bool(cv.get('modern_tools') or cv.get('modern_skills_headline')),
        bool(cv.get('experienta')),
    ]
    completeness = int(round(100 * (sum(1 for c in checks if c) / len(checks))))

    # weighted overall
    overall = int(round(
        0.25 * keyword_coverage +
        0.25 * jd_match +
        0.20 * metrics_coverage +
        0.15 * verb_variety +
        0.15 * completeness
    ))

    return ATSScore(
        keyword_coverage=keyword_coverage,
        jd_match=jd_match,
        metrics_coverage=metrics_coverage,
        verb_variety=verb_variety,
        completeness=completeness,
        overall=overall,
        missing_profile_keywords=missing_profile[:50],
        missing_jd_keywords=missing_jd[:50],
        bullets_missing_metrics=bullets_missing[:20],
        repeated_starting_verbs=repeated[:10],
    )
