from __future__ import annotations

import os
import re
import sys
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


class ProfileError(Exception):
    pass


# ---------------------------
# Cross-platform user data root
# ---------------------------
def _user_data_root() -> Path:
    """
    Stable per-user data folder (works for Streamlit Cloud too, but Cloud is ephemeral).
    Windows: %APPDATA%/CVBuilderATS
    macOS: ~/Library/Application Support/CVBuilderATS
    Linux: $XDG_DATA_HOME/CVBuilderATS or ~/.local/share/CVBuilderATS
    """
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "CVBuilderATS"

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "CVBuilderATS"

    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "CVBuilderATS"
    return Path.home() / ".local" / "share" / "CVBuilderATS"


# Where user-editable profiles live (persist between updates)
ATS_ROOT_DIR = _user_data_root() / "ats_profiles"
USER_PROFILES_DIR = ATS_ROOT_DIR / "profiles"          # optional
USER_LIBRARIES_DIR = ATS_ROOT_DIR / "libraries"
USER_DOMAIN_LIB_DIR = USER_LIBRARIES_DIR / "domains"

# Bundled profiles (inside repo / PyInstaller)
# We keep compatibility with your existing layout:
# - repo: ats_profiles/*.yaml (root)
# - optional: ats_profiles/profiles/*.yaml
# - optional: ats_profiles/libraries/...
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
        raise ProfileError(f"Failed to read profile: {e}")


def _write_text(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
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


def _pick_lang(val: Any, lang: str = "en") -> Any:
    """
    If val is dict with 'en'/'ro', pick matching language; fallback to other.
    Otherwise return val unchanged.
    """
    if isinstance(val, dict):
        if lang in val:
            return val.get(lang)
        # fallback order: en -> ro -> any
        if "en" in val:
            return val.get("en")
        if "ro" in val:
            return val.get("ro")
        # any first item
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
def _merge_bilingual_value(lib_v: Any, prof_v: Any) -> Any:
    """
    Merge lib_v into prof_v.
    Supports:
      - list -> concat + dedupe
      - dict bilingual {en: [...], ro: [...]} -> merge per key
      - strings -> keep profile if present else lib
    Profile (prof_v) wins when conflict.
    """
    if prof_v is None or prof_v == "" or prof_v == [] or prof_v == {}:
        return lib_v

    # bilingual dict merge
    if isinstance(lib_v, dict) and isinstance(prof_v, dict):
        out = dict(lib_v)
        for k, v in prof_v.items():
            if k in out and isinstance(out[k], list) and isinstance(v, list):
                out[k] = _dedupe_preserve(list(out[k]) + list(v))
            else:
                out[k] = v  # profile overrides
        return out

    # list merge
    if isinstance(lib_v, list) and isinstance(prof_v, list):
        return _dedupe_preserve(list(lib_v) + list(prof_v))

    # string / fallback -> keep profile
    return prof_v


def _merge_keywords_bilingual(lib_kw: Any, prof_kw: Any) -> Any:
    """
    Deep merge for keywords buckets.
    Each bucket can be:
      - list[str]
      - dict[lang] -> list[str]
    We merge per bucket, and per language if dict.
    """
    if not isinstance(lib_kw, dict) and not isinstance(prof_kw, dict):
        return prof_kw if prof_kw else lib_kw

    lib_kw = lib_kw if isinstance(lib_kw, dict) else {}
    prof_kw = prof_kw if isinstance(prof_kw, dict) else {}

    buckets = ["core", "technologies", "tools", "certifications", "frameworks", "soft_skills"]
    out: Dict[str, Any] = {}

    for b in buckets:
        lv = lib_kw.get(b)
        pv = prof_kw.get(b)
        if lv is None and pv is None:
            continue

        # dict bilingual
        if isinstance(lv, dict) or isinstance(pv, dict):
            lv = lv if isinstance(lv, dict) else {}
            pv = pv if isinstance(pv, dict) else {}
            merged = dict(lv)
            for lang_k, lang_v in pv.items():
                if lang_k in merged and isinstance(merged[lang_k], list) and isinstance(lang_v, list):
                    merged[lang_k] = _dedupe_preserve(list(merged[lang_k]) + list(lang_v))
                else:
                    merged[lang_k] = lang_v
            out[b] = merged
        else:
            # list / string -> normalize to list via _safe_list later, but we can merge lists now
            out[b] = _merge_bilingual_value(_safe_list(lv), _safe_list(pv))

    # Preserve any extra/legacy buckets too (services/platforms/languages/concepts)
    for k in ("services", "platforms", "languages", "concepts"):
        if k in lib_kw or k in prof_kw:
            out[k] = _merge_bilingual_value(lib_kw.get(k), prof_kw.get(k))

    return out


def _merge_lists(base: List[str], extra: List[str]) -> List[str]:
    # base first, then extra, dedupe
    return _dedupe_preserve(list(base) + list(extra))


def _merge_kw_bucket(base_bucket: Any, extra_bucket: Any, lang: str) -> List[str]:
    b = _safe_list(_pick_lang(base_bucket, lang=lang))
    e = _safe_list(_pick_lang(extra_bucket, lang=lang))
    return _merge_lists(b, e)


def _merge_keywords(base_kw: Dict[str, Any], extra_kw: Dict[str, Any], lang: str) -> Dict[str, List[str]]:
    buckets = ["core", "technologies", "tools", "certifications", "frameworks", "soft_skills"]
    out: Dict[str, List[str]] = {}
    for k in buckets:
        out[k] = _merge_kw_bucket(base_kw.get(k), extra_kw.get(k), lang=lang)
    return out


def _flatten_metrics(metrics: Any, lang: str = "en") -> List[str]:
    metrics = _pick_lang(metrics, lang=lang)

    if metrics is None:
        return []
    if isinstance(metrics, list):
        return _safe_list(metrics)
    if isinstance(metrics, dict):
        # legacy dict-of-lists
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


# ---------------------------
# Seeding: copy bundled repo profiles/libraries into user data folder (first run)
# ---------------------------
def _seed_from_source(src_root: Path) -> None:
    """
    Copy ats_profiles from src_root into USER ATS_ROOT_DIR if missing.
    Does not overwrite user's existing files.
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

    # 1) profiles: allow both root-yaml and profiles/
    # Copy root yaml files into USER_PROFILES_DIR
    if src_root.exists():
        for fn in src_root.glob("*.yaml"):
            out = USER_PROFILES_DIR / fn.name
            if not out.exists():
                shutil.copy2(fn, out)

    # Copy ats_profiles/profiles -> USER_PROFILES_DIR
    if (src_root / "profiles").exists():
        copy_tree_if_missing(src_root / "profiles", USER_PROFILES_DIR)

    # 2) libraries
    if (src_root / "libraries").exists():
        copy_tree_if_missing(src_root / "libraries", USER_LIBRARIES_DIR)


def ensure_seeded() -> None:
    """
    Ensure ATS folder exists and is prepopulated from:
    - PyInstaller bundle ats_profiles/ (if frozen)
    - repo ats_profiles/ (if running from source)
    """
    _ensure_dirs()

    # Prefer bundle if available
    b = _bundle_root()
    if b is not None and b.exists():
        _seed_from_source(b)
        return

    # Source run: seed from repo (optional)
    if REPO_ATS_ROOT.exists():
        _seed_from_source(REPO_ATS_ROOT)


# ---------------------------
# Profile path resolution
# ---------------------------
def profile_path(profile_id: str) -> Path:
    """
    Returns absolute path to the user's profile YAML file (preferred location).
    Accepts both "cyber_security" and "cyber_security.yaml"
    """
    ensure_seeded()

    pid = (profile_id or "").strip()
    if not pid:
        raise ProfileError("Empty profile id")
    if not pid.endswith(".yaml"):
        pid += ".yaml"
    return USER_PROFILES_DIR / pid


def _library_core_path() -> Path:
    ensure_seeded()
    return USER_LIBRARIES_DIR / "core_en_ro.yaml"


def _library_domain_path(domain_id: str) -> Path:
    ensure_seeded()
    did = (domain_id or "").strip()
    if not did:
        return USER_DOMAIN_LIB_DIR / "core.yaml"  # won't exist; safe
    if not did.endswith(".yaml"):
        did += ".yaml"
    return USER_DOMAIN_LIB_DIR / did


# ---------------------------
# Loading / normalizing
# ---------------------------
def validate_profile(profile: Dict[str, Any]) -> Tuple[bool, List[str]]:
    warnings = []
    if not isinstance(profile, dict):
        raise ProfileError("Profile YAML root must be a mapping/object")

    if not profile.get("id"):
        warnings.append("Missing 'id' (recommended).")
    if not profile.get("title"):
        warnings.append("Missing 'title' (recommended for UI).")

    # Optional: domain recommended (for libraries)
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
    """
    Enforce keyword buckets (each bucket is list[str] after language pick).
    Supports EN/RO dict values per bucket.
    """
    kw = _safe_dict(profile.get("keywords"))
    # allow legacy group names mapped into technologies
    technologies = _merge_lists(
        _safe_list(_pick_lang(kw.get("technologies"), lang)),
        _safe_list(_pick_lang(kw.get("services"), lang)),
    )
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
    """
    Normalize schema for stable UI/export usage.
    lang affects picking bilingual dict fields.
    """
    p = dict(profile or {})

    pid = (p.get("id") or fallback_id or "").strip()
    if not pid:
        pid = _slugify(fallback_id or "profile")
    p["id"] = pid

    # Domain for libraries
    p["domain"] = (p.get("domain") or pid).strip()

    # Title
    title_raw = p.get("title")
    title = str(_pick_lang(title_raw, lang=lang) or "").strip()
    if not title:
        jt = _safe_list(_pick_lang(p.get("job_titles"), lang=lang))
        title = jt[0] if jt else pid.replace("_", " ").title()
    p["title"] = title_raw if isinstance(title_raw, dict) else title  # keep dict if user uses it

    # Job titles
    p["job_titles"] = _safe_list(_pick_lang(p.get("job_titles"), lang=lang))

    # Keywords buckets
    p["keywords"] = _normalize_keywords(p, lang=lang)

    # Action verbs / templates / metrics - bilingual dict supported
    p["action_verbs"] = _dedupe_preserve(_safe_list(_pick_lang(p.get("action_verbs"), lang=lang)))
    p["metrics"] = _dedupe_preserve(_flatten_metrics(p.get("metrics"), lang=lang))
    p["bullet_templates"] = _normalize_templates(p.get("bullet_templates"), lang=lang)
    p["section_priority"] = _normalize_section_priority(p.get("section_priority"), lang=lang)

    # Optional knobs
    p.setdefault("ats_hint", "")
    p.setdefault("notes", "")

    return p


def _merge_library_into_profile(profile_raw: Dict[str, Any], lib_raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge library into profile without clobbering profile-specific customizations.
    Order: library -> profile (profile wins)
    """
    out = dict(profile_raw or {})
    if not isinstance(lib_raw, dict) or not lib_raw:
        return out

    # --- keywords deep merge (buckets + bilingual) ---
    out["keywords"] = _merge_keywords_bilingual(lib_raw.get("keywords"), out.get("keywords"))

    # --- list-like fields (support bilingual dict too) ---
    for k in ("action_verbs", "bullet_templates", "metrics", "section_priority"):
        if k in lib_raw:
            out[k] = _merge_bilingual_value(lib_raw.get(k), out.get(k))

    # --- optional text hints ---
    if lib_raw.get("ats_hint") and not out.get("ats_hint"):
        out["ats_hint"] = lib_raw.get("ats_hint")
    if lib_raw.get("notes") and not out.get("notes"):
        out["notes"] = lib_raw.get("notes")

    # --- title / job_titles only as fallback (profile keeps control) ---
    if lib_raw.get("title") and not out.get("title"):
        out["title"] = lib_raw.get("title")
    if lib_raw.get("job_titles") and not out.get("job_titles"):
        out["job_titles"] = lib_raw.get("job_titles")

    return out


def load_profile(profile_id: str, lang: str = "en") -> Dict[str, Any]:
    """
    Load profile YAML from user's profiles dir, merge core+domain libraries, normalize.
    lang: 'en' or 'ro' for UI/export usage.
    """
    pid = (profile_id or "").strip()
    if not pid:
        raise ProfileError("No profile selected")

    path = profile_path(pid)
    raw = _load_yaml_file(path)

    if not raw:
        # As a last resort, try to load from repo root (source run) or bundle root
        # but seed should have copied it already.
        raise ProfileError(f"Profile not found: {path}")

    # Determine domain
    domain_id = (raw.get("domain") or raw.get("id") or pid).strip()

    # Merge libraries (core -> domain -> profile)
    core_lib = _load_yaml_file(_library_core_path())
    domain_lib = _load_yaml_file(_library_domain_path(domain_id))

    merged = _merge_library_into_profile(raw, core_lib)
    merged = _merge_library_into_profile(merged, domain_lib)

    ok, warnings = validate_profile(merged)
    prof = normalize_profile(merged, fallback_id=pid, lang=lang)
    prof["_warnings"] = warnings
    prof["_source_file"] = path.name
    return prof


def list_profiles() -> List[Dict[str, str]]:
    """
    Returns list of profiles available to UI.
    Reads from USER_PROFILES_DIR. (Seed ensures defaults exist.)
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
                # if bilingual dict, prefer en for list display
                title = str(_pick_lang(t, "en") or title).strip() or title
        except Exception:
            pass
        out.append({"id": pid, "filename": fn.name, "title": title})
    return out


def save_profile_text(profile_id: str, yaml_text: str) -> None:
    """
    Save raw YAML text (used by profile editor). Validates parse first.
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

    # Keep user's bilingual dicts intact; but ensure id exists
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
