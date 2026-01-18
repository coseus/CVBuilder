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


# ---------------------------
# App name (change once)
# ---------------------------
APP_NAME = "CVBuilder"


# ---------------------------
# Cross-platform user data root
# ---------------------------
def _user_data_root() -> Path:
    """
    Stable per-user data folder.
    Windows: %APPDATA%/<APP_NAME>
    macOS: ~/Library/Application Support/<APP_NAME>
    Linux: $XDG_DATA_HOME/<APP_NAME> or ~/.local/share/<APP_NAME>
    """
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_NAME

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME

    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / APP_NAME
    return Path.home() / ".local" / "share" / APP_NAME


# Where user-editable profiles/libraries live (persist between updates)
ATS_ROOT_DIR = _user_data_root() / "ats_profiles"
USER_PROFILES_DIR = ATS_ROOT_DIR / "profiles"
USER_LIBRARIES_DIR = ATS_ROOT_DIR / "libraries"
USER_DOMAIN_LIB_DIR = USER_LIBRARIES_DIR / "domains"

# Bundled profiles (inside repo / PyInstaller)
REPO_ATS_ROOT = Path("ats_profiles")
REPO_PROFILES_DIR = REPO_ATS_ROOT / "profiles"
REPO_LIBRARIES_DIR = REPO_ATS_ROOT / "libraries"
REPO_DOMAIN_LIB_DIR = REPO_LIBRARIES_DIR / "domains"


# ---------------------------
# Helpers
# ---------------------------
def _ensure_dirs() -> None:
    USER_PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    USER_DOMAIN_LIB_DIR.mkdir(parents=True, exist_ok=True)


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def _bundle_root() -> Optional[Path]:
    """
    If running from PyInstaller, resources are under sys._MEIPASS.
    We try to locate bundled ats_profiles folder there.
    """
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
    """
    If val is dict with 'en'/'ro', pick matching language; fallback order: en -> ro -> any.
    """
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
        k = s.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(s)
    return out


def _merge_lists(base: Any, extra: Any, lang: str) -> Any:
    """
    Merge list-like fields:
    - if both are dict(en/ro), merge per language
    - else pick language and merge as list
    """
    if isinstance(base, dict) and isinstance(extra, dict):
        merged = dict(base)
        for k, v in extra.items():
            if k in merged:
                merged[k] = _dedupe_preserve(_safe_list(merged[k]) + _safe_list(v))
            else:
                merged[k] = v
        return merged

    b = _safe_list(_pick_lang(base, lang))
    e = _safe_list(_pick_lang(extra, lang))
    return _dedupe_preserve(b + e)


def _merge_keywords(base_kw: Any, extra_kw: Any, lang: str) -> Dict[str, Any]:
    """
    keywords buckets merge (core/technologies/tools/certifications/frameworks/soft_skills)
    Supports bilingual dict values per bucket.
    """
    b = _safe_dict(base_kw)
    e = _safe_dict(extra_kw)

    buckets = ["core", "technologies", "tools", "certifications", "frameworks", "soft_skills"]

    out: Dict[str, Any] = {}
    for k in buckets:
        out[k] = _merge_lists(b.get(k), e.get(k), lang=lang)

    # legacy aliases -> technologies
    for legacy in ("services", "platforms", "languages", "concepts"):
        if legacy in b or legacy in e:
            out["technologies"] = _merge_lists(out.get("technologies"), b.get(legacy), lang=lang)
            out["technologies"] = _merge_lists(out.get("technologies"), e.get(legacy), lang=lang)

    return out


def _flatten_metrics(metrics: Any, lang: str = "en") -> Any:
    """
    metrics can be:
      - list[str]
      - dict(en/ro -> list[str])
      - legacy dict-of-lists
    Keep bilingual dict if present; otherwise pick lang.
    """
    if isinstance(metrics, dict) and ("en" in metrics or "ro" in metrics):
        # bilingual dict
        out = {}
        for k, v in metrics.items():
            out[k] = _dedupe_preserve(_safe_list(v))
        return out

    m = _pick_lang(metrics, lang=lang)
    if m is None:
        return []
    if isinstance(m, list):
        return _dedupe_preserve(_safe_list(m))
    if isinstance(m, dict):
        flat: List[str] = []
        for _, v in m.items():
            flat.extend(_safe_list(v))
        return _dedupe_preserve(flat)
    if isinstance(m, str):
        return _dedupe_preserve(_safe_list(m))
    return _dedupe_preserve(_safe_list(m))


def _normalize_section_priority(x: Any, lang: str = "en") -> Any:
    """
    Keep bilingual dict if present; otherwise normalize list.
    """
    if isinstance(x, dict) and ("en" in x or "ro" in x):
        out = {}
        for k, v in x.items():
            out[k] = _dedupe_preserve(_safe_list(v))
        return out

    items = _safe_list(_pick_lang(x, lang=lang))
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


def _normalize_templates(x: Any, lang: str = "en") -> Any:
    """
    Keep bilingual dict if present; else list with minimum defaults.
    """
    if isinstance(x, dict) and ("en" in x or "ro" in x):
        out = {}
        for k, v in x.items():
            lst = _safe_list(v)
            if len(lst) < 2:
                lst.extend([
                    "Delivered {scope} improvements using {tool_or_tech}; reduced {metric} by {value}.",
                    "Implemented {control_or_feature} across {environment}; improved reliability/security and documented SOPs.",
                ])
            out[k] = _dedupe_preserve(lst)
        return out

    t = _safe_list(_pick_lang(x, lang=lang))
    if len(t) < 2:
        t.extend([
            "Delivered {scope} improvements using {tool_or_tech}; reduced {metric} by {value}.",
            "Implemented {control_or_feature} across {environment}; improved reliability/security and documented SOPs.",
        ])
    return _dedupe_preserve(t)


# ---------------------------
# Seeding: copy bundled repo profiles/libraries into user data folder (first run)
# ---------------------------
def _seed_from_source(src_root: Path) -> None:
    """
    Copy ats_profiles from src_root into USER ATS_ROOT_DIR if missing.
    Does not overwrite user's existing files.
    Accepts both:
      - ats_profiles/*.yaml (root)
      - ats_profiles/profiles/*.yaml
      - ats_profiles/libraries/**/*
    """
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

    # 1) copy root yaml -> USER_PROFILES_DIR
    if src_root.exists():
        for fn in src_root.glob("*.yaml"):
            out = USER_PROFILES_DIR / fn.name
            if not out.exists():
                shutil.copy2(fn, out)

    # 2) copy ats_profiles/profiles -> USER_PROFILES_DIR
    if (src_root / "profiles").exists():
        copy_tree_if_missing(src_root / "profiles", USER_PROFILES_DIR)

    # 3) libraries
    if (src_root / "libraries").exists():
        copy_tree_if_missing(src_root / "libraries", USER_LIBRARIES_DIR)


def ensure_seeded() -> None:
    """
    Ensure ATS folder exists and is prepopulated from:
    - PyInstaller bundle ats_profiles/ (if frozen)
    - repo ats_profiles/ (if running from source)
    """
    _ensure_dirs()

    b = _bundle_root()
    if b is not None and b.exists():
        _seed_from_source(b)
        return

    if REPO_ATS_ROOT.exists():
        _seed_from_source(REPO_ATS_ROOT)


# ---------------------------
# Paths
# ---------------------------
def profile_path(profile_id: str) -> Path:
    """
    Returns absolute path to the user's profile YAML file (preferred).
    Accepts both "cyber_security" and "cyber_security.yaml"
    """
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
        return USER_DOMAIN_LIB_DIR / "_missing_.yaml"
    if not did.endswith(".yaml"):
        did += ".yaml"
    return USER_DOMAIN_LIB_DIR / did


def _load_yaml_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(_read_text(path))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ProfileError(f"Invalid YAML in {path.name}: root must be mapping/object")
    return raw


# ---------------------------
# Merge logic (core -> domain -> profile)
# ---------------------------
def _merge_profile_like(base: Dict[str, Any], extra: Dict[str, Any], lang: str) -> Dict[str, Any]:
    """
    Merge `extra` into `base` with smart rules:
    - keywords bucket merge
    - action_verbs / bullet_templates / metrics / job_titles / section_priority merge (concat + dedupe)
    - title/ats_hint/notes: profile overrides
    """
    out = dict(base or {})
    if not extra:
        return out

    # keywords
    out["keywords"] = _merge_keywords(out.get("keywords", {}), extra.get("keywords", {}), lang=lang)

    # list-like fields (support bilingual dict too)
    for k in ("action_verbs", "bullet_templates", "job_titles"):
        out[k] = _merge_lists(out.get(k), extra.get(k), lang=lang)

    # metrics, section priority
    out["metrics"] = _merge_lists(out.get("metrics"), extra.get("metrics"), lang=lang) if isinstance(out.get("metrics"), dict) or isinstance(extra.get("metrics"), dict) else _flatten_metrics(out.get("metrics"), lang=lang)
    # for metrics we want stable schema; if either has bilingual, keep bilingual; else list
    if isinstance(out.get("metrics"), dict) or isinstance(extra.get("metrics"), dict):
        out["metrics"] = _merge_lists(out.get("metrics"), extra.get("metrics"), lang=lang)
    else:
        out["metrics"] = _dedupe_preserve(_safe_list(out.get("metrics")) + _safe_list(_pick_lang(extra.get("metrics"), lang)))

    if isinstance(out.get("section_priority"), dict) or isinstance(extra.get("section_priority"), dict):
        out["section_priority"] = _merge_lists(out.get("section_priority"), extra.get("section_priority"), lang=lang)
    else:
        out["section_priority"] = _dedupe_preserve(
            _safe_list(_pick_lang(out.get("section_priority"), lang)) + _safe_list(_pick_lang(extra.get("section_priority"), lang))
        )

    # scalars (extra provides fallback only)
    for k in ("ats_hint", "notes"):
        if not out.get(k) and extra.get(k):
            out[k] = extra.get(k)

    # domain/title: do not overwrite if already set in base
    if not out.get("domain") and extra.get("domain"):
        out["domain"] = extra.get("domain")

    if not out.get("title") and extra.get("title"):
        out["title"] = extra.get("title")

    return out


def validate_profile(profile: Dict[str, Any]) -> Tuple[bool, List[str]]:
    warnings = []
    if not isinstance(profile, dict):
        raise ProfileError("Profile YAML root must be a mapping/object")

    if not profile.get("id"):
        warnings.append("Missing 'id' (recommended).")
    if not profile.get("title"):
        warnings.append("Missing 'title' (recommended for UI).")

    # domain recommended (enables domain libraries)
    if not profile.get("domain"):
        warnings.append("Missing 'domain' (recommended: enables domain libraries).")

    return True, warnings


def normalize_profile(profile: Dict[str, Any], fallback_id: str = "", lang: str = "en") -> Dict[str, Any]:
    """
    Normalize schema so the rest of the app is stable.
    Keep bilingual dicts in the profile, but also provide lang-picked lists for UI usage.
    """
    p = dict(profile or {})

    pid = (p.get("id") or fallback_id or "").strip()
    if not pid:
        pid = _slugify(fallback_id or "profile")
    p["id"] = pid

    # domain
    p["domain"] = (p.get("domain") or pid).strip()

    # title: allow bilingual dict, but ensure UI can display something
    title_raw = p.get("title")
    title_pick = str(_pick_lang(title_raw, lang=lang) or "").strip()
    if not title_pick:
        # fallback to first job title or id
        jt = _safe_list(_pick_lang(p.get("job_titles"), lang=lang))
        title_pick = jt[0] if jt else pid.replace("_", " ").title()
    p["title"] = title_raw if isinstance(title_raw, dict) else title_pick

    # normalize buckets (keep bilingual dict if present)
    p["keywords"] = _merge_keywords(p.get("keywords", {}), {}, lang=lang)

    # action_verbs/templates/job_titles: keep bilingual dict if present; else list
    p["action_verbs"] = p.get("action_verbs", [])
    p["bullet_templates"] = _normalize_templates(p.get("bullet_templates"), lang=lang)
    p["job_titles"] = p.get("job_titles", [])

    # metrics/section_priority
    p["metrics"] = _flatten_metrics(p.get("metrics"), lang=lang)
    p["section_priority"] = _normalize_section_priority(p.get("section_priority"), lang=lang)

    # defaults
    p.setdefault("ats_hint", "")
    p.setdefault("notes", "")

    return p


def load_profile(profile_id: str, lang: str = "en") -> Dict[str, Any]:
    """
    Load profile YAML from user profiles dir, merge:
      core library -> domain library -> profile
    then normalize (lang-aware).
    """
    pid = (profile_id or "").strip()
    if not pid:
        raise ProfileError("No profile selected")

    ensure_seeded()

    path = profile_path(pid)
    raw = _load_yaml_file(path)
    if not raw:
        raise ProfileError(f"Profile not found: {path}")

    # ensure id/domain exists
    raw["id"] = raw.get("id") or pid
    raw["domain"] = raw.get("domain") or raw["id"]

    domain_id = str(raw.get("domain") or raw.get("id") or pid).strip()

    core_lib = _load_yaml_file(_core_library_path())
    domain_lib = _load_yaml_file(_domain_library_path(domain_id))

    merged = {}
    merged = _merge_profile_like(merged, core_lib, lang=lang)      # core first
    merged = _merge_profile_like(merged, domain_lib, lang=lang)    # then domain
    merged = _merge_profile_like(merged, raw, lang=lang)           # then profile overrides

    ok, warnings = validate_profile(merged)
    prof = normalize_profile(merged, fallback_id=pid, lang=lang)
    prof["_warnings"] = warnings
    prof["_source_file"] = path.name

    return prof


def list_profiles() -> List[Dict[str, str]]:
    """
    Profiles available to UI. Reads USER_PROFILES_DIR (seed ensures defaults exist).
    """
    ensure_seeded()
    out: List[Dict[str, str]] = []
    for fn in sorted(USER_PROFILES_DIR.glob("*.yaml")):
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
    """
    Save raw YAML text (profile editor). Validates parse first.
    NOTE: we do not force-normalize the whole profile here (keeps user's bilingual dicts).
    """
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
    """
    Save profile dict as YAML. Returns profile id.
    """
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
