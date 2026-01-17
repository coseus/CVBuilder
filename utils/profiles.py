from __future__ import annotations

import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

import yaml


class ProfileError(Exception):
    pass


# -----------------------------
# Robust base dir (Streamlit Cloud + local + PyInstaller)
# -----------------------------
def _app_base_dir() -> str:
    """
    Determine where to resolve project-relative paths from.

    - PyInstaller: sys._MEIPASS points to unpacked temp folder.
    - Normal: resolve repo root relative to this file (utils/profiles.py -> ..).
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return os.path.abspath(meipass)

    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, ".."))  # repo root


_BASE_DIR = _app_base_dir()

# Support both layouts:
#   ats_profiles/*.yaml
#   ats_profiles/profiles/*.yaml
ATS_PROFILES_DIR = os.path.join(_BASE_DIR, "ats_profiles")
ATS_PROFILES_PROFILES_DIR = os.path.join(ATS_PROFILES_DIR, "profiles")


def _ensure_dir() -> None:
    os.makedirs(ATS_PROFILES_DIR, exist_ok=True)


def _profiles_root_dir() -> str:
    # If ats_profiles/profiles exists, use it; else fallback to ats_profiles
    if os.path.isdir(ATS_PROFILES_PROFILES_DIR):
        return ATS_PROFILES_PROFILES_DIR
    return ATS_PROFILES_DIR


def profile_path(profile_id: str) -> str:
    """
    Returns absolute path to profile yaml.
    Accepts both "cyber_security" and "cyber_security.yaml"
    """
    _ensure_dir()
    pid = (profile_id or "").strip()
    if not pid:
        raise ProfileError("Empty profile id")
    if not pid.endswith(".yaml"):
        pid += ".yaml"
    return os.path.join(_profiles_root_dir(), pid)


def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise ProfileError(f"Profile not found: {path}")
    except Exception as e:
        raise ProfileError(f"Failed to read profile: {e}")


def _write_text(path: str, text: str) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    except Exception as e:
        raise ProfileError(f"Failed to write profile: {e}")


def _safe_list(x: Any) -> List[str]:
    if x is None:
        return []
    if isinstance(x, list):
        return [str(i).strip() for i in x if str(i).strip()]
    if isinstance(x, str):
        return [s.strip() for s in x.splitlines() if s.strip()]
    return [str(x).strip()] if str(x).strip() else []


def _safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9\-_ ]+", "", s)
    s = re.sub(r"\s+", "_", s).strip("_")
    return s or "profile"


def _normalize_keywords(profile: Dict[str, Any]) -> Dict[str, List[str]]:
    kw = _safe_dict(profile.get("keywords"))
    out = {
        "core": _safe_list(kw.get("core")),
        "technologies": _safe_list(kw.get("technologies")),
        "tools": _safe_list(kw.get("tools")),
        "certifications": _safe_list(kw.get("certifications")),
        "frameworks": _safe_list(kw.get("frameworks")),
        "soft_skills": _safe_list(kw.get("soft_skills")),
    }

    for legacy_key in ("services", "platforms", "languages", "concepts"):
        if legacy_key in kw and isinstance(kw.get(legacy_key), (list, str)):
            out["technologies"].extend(_safe_list(kw.get(legacy_key)))

    for k in list(out.keys()):
        seen = set()
        deduped = []
        for item in out[k]:
            low = item.lower()
            if low in seen:
                continue
            seen.add(low)
            deduped.append(item)
        out[k] = deduped

    return out


def _flatten_metrics(metrics: Any) -> List[str]:
    if metrics is None:
        return []
    if isinstance(metrics, list):
        return _safe_list(metrics)
    if isinstance(metrics, dict):
        flat: List[str] = []
        for _, v in metrics.items():
            flat.extend(_safe_list(v))
        return _safe_list(flat)
    if isinstance(metrics, str):
        return _safe_list(metrics)
    return _safe_list(metrics)


def _normalize_section_priority(x: Any) -> List[str]:
    items = _safe_list(x)
    if not items:
        return [
            "Professional Experience",
            "Summary",
            "Technical Skills",
            "Education",
            "Certifications",
        ]
    norm_map = {
        "experience": "Professional Experience",
        "experience / projects": "Professional Experience",
        "projects": "Professional Experience",
        "work experience": "Professional Experience",
        "skills": "Technical Skills",
        "key skills": "Technical Skills",
        "technical skills": "Technical Skills",
        "summary": "Summary",
        "education": "Education",
        "certifications": "Certifications",
    }
    out = []
    for s in items:
        key = s.strip().lower()
        out.append(norm_map.get(key, s))
    seen = set()
    ded = []
    for s in out:
        if s.lower() in seen:
            continue
        seen.add(s.lower())
        ded.append(s)
    return ded


def _normalize_templates(x: Any) -> List[str]:
    t = _safe_list(x)
    if len(t) < 2:
        t.extend([
            "Delivered {scope} improvements using {tool_or_tech}; reduced {metric} by {value}.",
            "Implemented {control_or_feature} across {environment}; improved reliability/security and documented SOPs.",
        ])
    return t


def validate_profile(profile: Dict[str, Any]) -> Tuple[bool, List[str]]:
    warnings = []
    if not isinstance(profile, dict):
        raise ProfileError("Profile YAML root must be a mapping/object")

    if not profile.get("id"):
        warnings.append("Missing 'id' (recommended).")
    if not profile.get("title"):
        warnings.append("Missing 'title' (recommended for UI).")

    if "job_titles" in profile and not isinstance(profile["job_titles"], list):
        warnings.append("'job_titles' should be a list.")

    if "keywords" in profile and not isinstance(profile["keywords"], dict):
        warnings.append("'keywords' should be a mapping/object.")

    if "action_verbs" in profile and not isinstance(profile["action_verbs"], list):
        warnings.append("'action_verbs' should be a list.")

    if "metrics" in profile and not isinstance(profile["metrics"], (list, dict, str)):
        warnings.append("'metrics' should be a list (or dict/list legacy).")

    if "bullet_templates" in profile and not isinstance(profile["bullet_templates"], (list, str)):
        warnings.append("'bullet_templates' should be a list (or multiline string).")

    return True, warnings


def normalize_profile(profile: Dict[str, Any], fallback_id: str = "") -> Dict[str, Any]:
    p = dict(profile or {})

    pid = (p.get("id") or fallback_id or "").strip()
    if not pid:
        pid = _slugify(fallback_id or "profile")
    p["id"] = pid

    title = (p.get("title") or "").strip()
    if not title:
        jt = _safe_list(p.get("job_titles"))
        title = jt[0] if jt else pid.replace("_", " ").title()
    p["title"] = title

    p["job_titles"] = _safe_list(p.get("job_titles"))
    p["keywords"] = _normalize_keywords(p)
    p["action_verbs"] = _safe_list(p.get("action_verbs"))
    p["metrics"] = _flatten_metrics(p.get("metrics"))
    p["bullet_templates"] = _normalize_templates(p.get("bullet_templates"))
    p["section_priority"] = _normalize_section_priority(p.get("section_priority"))

    p.setdefault("ats_hint", "")
    p.setdefault("notes", "")

    return p


def list_profiles() -> List[Dict[str, str]]:
    _ensure_dir()
    root = _profiles_root_dir()
    out: List[Dict[str, str]] = []

    if not os.path.isdir(root):
        return out

    for fn in sorted(os.listdir(root)):
        if not fn.endswith(".yaml"):
            continue
        pid = fn[:-5]
        path = os.path.join(root, fn)
        title = pid.replace("_", " ").title()
        try:
            data = yaml.safe_load(_read_text(path)) or {}
            if isinstance(data, dict):
                title = (data.get("title") or "").strip() or title
        except Exception:
            pass
        out.append({"id": pid, "filename": fn, "title": title})
    return out


def load_profile(profile_id: str) -> Dict[str, Any]:
    pid = (profile_id or "").strip()
    if not pid:
        raise ProfileError("No profile selected")

    path = profile_path(pid)
    raw = yaml.safe_load(_read_text(path))
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ProfileError("Invalid YAML: root must be a mapping/object")

    _, warnings = validate_profile(raw)
    prof = normalize_profile(raw, fallback_id=pid)
    prof["_warnings"] = warnings
    prof["_source_file"] = os.path.basename(path)
    prof["_source_path"] = path
    return prof


def save_profile_text(profile_id: str, yaml_text: str) -> None:
    pid = (profile_id or "").strip()
    if not pid:
        raise ProfileError("Empty profile id")

    try:
        parsed = yaml.safe_load(yaml_text)
        if parsed is None:
            parsed = {}
        if not isinstance(parsed, dict):
            raise ProfileError("YAML root must be an object (mapping).")
    except yaml.YAMLError as e:
        raise ProfileError(f"Invalid YAML: {e}")

    normalized = normalize_profile(parsed, fallback_id=pid)
    text_out = yaml.safe_dump(normalized, sort_keys=False, allow_unicode=True)
    _write_text(profile_path(pid), text_out)


def save_profile_dict(profile: Dict[str, Any], profile_id: Optional[str] = None) -> str:
    pid = (profile_id or profile.get("id") or "").strip()
    if not pid:
        pid = _slugify(profile.get("title", "profile"))
    normalized = normalize_profile(profile, fallback_id=pid)
    text_out = yaml.safe_dump(normalized, sort_keys=False, allow_unicode=True)
    _write_text(profile_path(pid), text_out)
    return pid
