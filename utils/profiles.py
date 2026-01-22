# utils/profiles.py
from __future__ import annotations

import os
import re
import sys
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


class ProfileError(Exception):
    pass


APP_NAME = "CVBuilder"


def _user_data_root() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / APP_NAME
    return Path.home() / ".local" / "share" / APP_NAME


ATS_ROOT_DIR = _user_data_root() / "ats_profiles"
USER_PROFILES_DIR = ATS_ROOT_DIR / "profiles"
USER_LIBRARIES_DIR = ATS_ROOT_DIR / "libraries"
USER_DOMAIN_LIB_DIR = USER_LIBRARIES_DIR / "domains"

REPO_ATS_ROOT = Path("ats_profiles")


def _ensure_dirs() -> None:
    USER_PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    USER_DOMAIN_LIB_DIR.mkdir(parents=True, exist_ok=True)


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def _bundle_root() -> Optional[Path]:
    if not _is_frozen():
        return None
    base = Path(getattr(sys, "_MEIPASS"))  # type: ignore
    cand = base / "ats_profiles"
    return cand if cand.exists() else None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ProfileError(f"Profile not found: {path}")
    except Exception as e:
        raise ProfileError(f"Failed to read file: {e}")


def _write_text(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except Exception as e:
        raise ProfileError(f"Failed to write file: {e}")


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


def _pick_lang(val: Any, lang: str = "en") -> Any:
    if isinstance(val, dict):
        if lang in val:
            return val.get(lang)
        if "en" in val:
            return val.get("en")
        if "ro" in val:
            return val.get("ro")
        for _, v in val.items():
            return v
    return val


def _dedupe_preserve(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for it in items:
        s = (it or "").strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _merge_lists(base: List[str], extra: List[str]) -> List[str]:
    return _dedupe_preserve(list(base) + list(extra))


def _flatten_metrics(metrics: Any, lang: str = "en") -> List[str]:
    metrics = _pick_lang(metrics, lang=lang)
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


def _normalize_templates(x: Any, lang: str = "en") -> List[str]:
    x = _pick_lang(x, lang=lang)
    t = _safe_list(x)
    if len(t) < 2:
        t.extend([
            "Delivered {scope} improvements using {tool_or_tech}; reduced {metric} by {value}.",
            "Implemented {control_or_feature} across {environment}; improved reliability/security and documented SOPs.",
        ])
    return t


def _normalize_section_priority(x: Any, lang: str = "en") -> List[str]:
    x = _pick_lang(x, lang=lang)
    items = _safe_list(x)
    if not items:
        return ["Professional Experience", "Summary", "Technical Skills", "Education", "Certifications"]

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
    out = [norm_map.get(s.strip().lower(), s) for s in items]
    return _dedupe_preserve(out)


def _seed_from_source(src_root: Path) -> None:
    _ensure_dirs()

    def copy_tree_if_missing(src: Path, dst: Path) -> None:
        if not src.exists():
            return
        dst.mkdir(parents=True, exist_ok=True)
        for p in src.rglob("*"):
            if p.is_dir():
                continue
            rel = p.relative_to(src)
            out = dst / rel
            if out.exists():
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, out)

    # root yaml profiles -> USER_PROFILES_DIR
    if src_root.exists():
        for fn in src_root.glob("*.yaml"):
            out = USER_PROFILES_DIR / fn.name
            if not out.exists():
                shutil.copy2(fn, out)

    # ats_profiles/profiles -> USER_PROFILES_DIR
    if (src_root / "profiles").exists():
        copy_tree_if_missing(src_root / "profiles", USER_PROFILES_DIR)

    # ats_profiles/libraries -> USER_LIBRARIES_DIR
    if (src_root / "libraries").exists():
        copy_tree_if_missing(src_root / "libraries", USER_LIBRARIES_DIR)


def ensure_seeded() -> None:
    _ensure_dirs()
    b = _bundle_root()
    if b is not None and b.exists():
        _seed_from_source(b)
        return
    if REPO_ATS_ROOT.exists():
        _seed_from_source(REPO_ATS_ROOT)


def profile_path(profile_id: str) -> Path:
    ensure_seeded()
    pid = (profile_id or "").strip()
    if not pid:
        raise ProfileError("Empty profile id")
    if not pid.endswith(".yaml"):
        pid += ".yaml"
    return USER_PROFILES_DIR / pid


def _core_library_path() -> Path:
    ensure_seeded()
    return USER_LIBRARIES_DIR / "core_en_ro.yaml"


def _domain_library_path(domain_id: str) -> Path:
    ensure_seeded()
    did = (domain_id or "").strip()
    if not did:
        return USER_DOMAIN_LIB_DIR / "core.yaml"
    if not did.endswith(".yaml"):
        did += ".yaml"
    return USER_DOMAIN_LIB_DIR / did


def validate_profile(profile: Dict[str, Any]) -> Tuple[bool, List[str]]:
    warnings = []
    if not isinstance(profile, dict):
        raise ProfileError("Profile YAML root must be a mapping/object")
    if not profile.get("id"):
        warnings.append("Missing 'id' (recommended).")
    if not profile.get("title"):
        warnings.append("Missing 'title' (recommended for UI).")
    if not profile.get("domain"):
        warnings.append("Missing 'domain' (recommended: enables domain libraries).")
    return True, warnings


def _load_yaml_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(_read_text(path))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ProfileError(f"Invalid YAML in {path.name}: root must be a mapping/object")
    return raw


def _normalize_keywords(profile: Dict[str, Any], lang: str) -> Dict[str, List[str]]:
    kw = _safe_dict(profile.get("keywords"))

    technologies = _merge_lists(_safe_list(_pick_lang(kw.get("technologies"), lang)),
                               _safe_list(_pick_lang(kw.get("services"), lang)))
    technologies = _merge_lists(technologies, _safe_list(_pick_lang(kw.get("platforms"), lang)))
    technologies = _merge_lists(technologies, _safe_list(_pick_lang(kw.get("languages"), lang)))
    technologies = _merge_lists(technologies, _safe_list(_pick_lang(kw.get("concepts"), lang)))

    out = {
        "core": _safe_list(_pick_lang(kw.get("core"), lang)),
        "technologies": technologies,
        "tools": _safe_list(_pick_lang(kw.get("tools"), lang)),
        "certifications": _safe_list(_pick_lang(kw.get("certifications"), lang)),
        "frameworks": _safe_list(_pick_lang(kw.get("frameworks"), lang)),
        "soft_skills": _safe_list(_pick_lang(kw.get("soft_skills"), lang)),
    }
    for k in list(out.keys()):
        out[k] = _dedupe_preserve(out[k])
    return out


def normalize_profile(profile: Dict[str, Any], fallback_id: str = "", lang: str = "en") -> Dict[str, Any]:
    p = dict(profile or {})

    pid = (p.get("id") or fallback_id or "").strip()
    if not pid:
        pid = _slugify(fallback_id or "profile")
    p["id"] = pid

    p["domain"] = (p.get("domain") or pid).strip()

    title_raw = p.get("title")
    title = str(_pick_lang(title_raw, lang=lang) or "").strip()
    if not title:
        jt = _safe_list(_pick_lang(p.get("job_titles"), lang=lang))
        title = jt[0] if jt else pid.replace("_", " ").title()
    p["title"] = title_raw if isinstance(title_raw, dict) else title

    p["job_titles"] = _safe_list(_pick_lang(p.get("job_titles"), lang=lang))
    p["keywords"] = _normalize_keywords(p, lang=lang)

    p["action_verbs"] = _dedupe_preserve(_safe_list(_pick_lang(p.get("action_verbs"), lang=lang)))
    p["metrics"] = _dedupe_preserve(_flatten_metrics(p.get("metrics"), lang=lang))
    p["bullet_templates"] = _normalize_templates(p.get("bullet_templates"), lang=lang)
    p["section_priority"] = _normalize_section_priority(p.get("section_priority"), lang=lang)

    p.setdefault("ats_hint", "")
    p.setdefault("notes", "")
    return p


def _merge_profile_like(base: Dict[str, Any], extra: Dict[str, Any], lang: str) -> Dict[str, Any]:
    """
    Merge library/profile objects without clobbering:
    - keywords: merge buckets
    - lists: concat + dedupe
    - dict bilingual fields: keep dicts, normalize later
    """
    out = dict(base or {})
    if not isinstance(extra, dict) or not extra:
        return out

    # merge scalar fields if missing
    for k in ("title", "domain", "ats_hint", "notes"):
        if k in extra and not out.get(k):
            out[k] = extra.get(k)

    # merge job_titles
    if extra.get("job_titles"):
        if not out.get("job_titles"):
            out["job_titles"] = extra.get("job_titles")
        else:
            out["job_titles"] = _merge_lists(_safe_list(_pick_lang(out.get("job_titles"), lang)),
                                             _safe_list(_pick_lang(extra.get("job_titles"), lang)))

    # merge keywords dict shallow (profile overrides buckets)
    if isinstance(extra.get("keywords"), dict):
        kw_base = _safe_dict(out.get("keywords"))
        kw_extra = _safe_dict(extra.get("keywords"))
        merged = dict(kw_base)
        for bk, bv in kw_extra.items():
            if bk not in merged:
                merged[bk] = bv
            else:
                # keep both; normalize later
                merged[bk] = merged[bk]
        out["keywords"] = dict(kw_extra, **kw_base)  # profile buckets override

    # merge list-like (action_verbs/templates/metrics)
    for k in ("action_verbs", "bullet_templates", "metrics", "section_priority"):
        if k in extra:
            if not out.get(k):
                out[k] = extra.get(k)
            else:
                # keep both; normalize later
                ov = out.get(k)
                ev = extra.get(k)
                if isinstance(ov, dict) and isinstance(ev, dict):
                    # library provides defaults, base overrides
                    merged = dict(ev)
                    merged.update(ov)
                    out[k] = merged
                elif isinstance(ov, list) and isinstance(ev, list):
                    out[k] = _dedupe_preserve(list(ev) + list(ov))
                else:
                    out[k] = ov

    return out


def load_profile(profile_id: str, lang: str = "en") -> Dict[str, Any]:
    pid = (profile_id or "").strip()
    if not pid:
        raise ProfileError("No profile selected")

    ensure_seeded()

    path = profile_path(pid)
    raw = _load_yaml_file(path)
    if not raw:
        raise ProfileError(f"Profile not found: {path}")

    raw["id"] = raw.get("id") or pid
    raw["domain"] = raw.get("domain") or raw["id"]

    domain_id = str(raw.get("domain") or raw.get("id") or pid).strip()

    core_lib = _load_yaml_file(_core_library_path())
    domain_lib = _load_yaml_file(_domain_library_path(domain_id))

    merged = {}
    merged = _merge_profile_like(merged, core_lib, lang=lang)
    merged = _merge_profile_like(merged, domain_lib, lang=lang)
    merged = _merge_profile_like(merged, raw, lang=lang)

    ok, warnings = validate_profile(merged)
    prof = normalize_profile(merged, fallback_id=pid, lang=lang)
    prof["_warnings"] = warnings
    prof["_source_file"] = path.name
    return prof


def list_profiles() -> List[Dict[str, str]]:
    """
    Returns list of selectable profiles for UI.
    Excludes:
      - ats_profiles/domains_index.yaml
      - ats_profiles/libraries/**
    Reads from USER_PROFILES_DIR (seeded).
    """
    ensure_seeded()

    exclude_names = {"domains_index.yaml", "core_en_ro.yaml"}
    out: List[Dict[str, str]] = []

    for fn in sorted(USER_PROFILES_DIR.glob("*.yaml")):
        if fn.name in exclude_names:
            continue

        # If user accidentally copied libraries into profiles folder, skip by convention
        if fn.name.startswith("core_") or fn.name.endswith("_library.yaml"):
            continue

        pid = fn.stem
        title = pid.replace("_", " ").title()

        try:
            data = yaml.safe_load(_read_text(fn)) or {}
            if isinstance(data, dict):
                t = data.get("title")
                title = str(_pick_lang(t, "en") or title).strip() or title
        except Exception:
            pass

        out.append({"id": pid, "filename": fn.name, "title": title})

    return out


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

    parsed["id"] = parsed.get("id") or pid
    parsed["domain"] = parsed.get("domain") or parsed["id"]

    text_out = yaml.safe_dump(parsed, sort_keys=False, allow_unicode=True)
    _write_text(profile_path(pid), text_out)


def save_profile_dict(profile: Dict[str, Any], profile_id: Optional[str] = None) -> str:
    ensure_seeded()
    pid = (profile_id or profile.get("id") or "").strip()
    if not pid:
        pid = _slugify(str(_pick_lang(profile.get("title"), "en") or "profile"))
    profile = dict(profile or {})
    profile["id"] = profile.get("id") or pid
    profile["domain"] = profile.get("domain") or profile["id"]

    text_out = yaml.safe_dump(profile, sort_keys=False, allow_unicode=True)
    _write_text(profile_path(pid), text_out)
    return pid
