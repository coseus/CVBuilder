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
# Cross-platform user data root
# ---------------------------
APP_NAME = "CVBuilder"


def _user_data_root() -> Path:
    """
    Stable per-user data folder (works for Streamlit Cloud too, but Cloud is ephemeral).
    Windows: %APPDATA%/CVBuilder
    macOS: ~/Library/Application Support/CVBuilder
    Linux: $XDG_DATA_HOME/CVBuilder or ~/.local/share/CVBuilder
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


# Where user-editable ATS stuff lives (persist between app updates)
ATS_ROOT_DIR = _user_data_root() / "ats_profiles"
USER_PROFILES_DIR = ATS_ROOT_DIR / "profiles"          # user profiles (YAML)
USER_LIBRARIES_DIR = ATS_ROOT_DIR / "libraries"        # libraries (YAML)
USER_DOMAIN_LIB_DIR = USER_LIBRARIES_DIR / "domains"   # domain libs
USER_INDEX_PATH = ATS_ROOT_DIR / "domains_index.yaml"  # UI/index mapping (optional)

# Bundled repo paths (source or PyInstaller bundle)
REPO_ATS_ROOT = Path("ats_profiles")
REPO_PROFILES_DIR = REPO_ATS_ROOT / "profiles"
REPO_LIBRARIES_DIR = REPO_ATS_ROOT / "libraries"
REPO_DOMAIN_LIB_DIR = REPO_LIBRARIES_DIR / "domains"
REPO_INDEX_PATH = REPO_ATS_ROOT / "domains_index.yaml"


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
    base = Path(getattr(sys, "_MEIPASS"))  # type: ignore[attr-defined]
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


def _load_yaml_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(_read_text(path))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ProfileError(f"Invalid YAML in {path.name}: root must be a mapping/object")
    return raw


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

    # Copy index if missing
    if (src_root / "domains_index.yaml").exists() and not USER_INDEX_PATH.exists():
        shutil.copy2(src_root / "domains_index.yaml", USER_INDEX_PATH)

    # 1) profiles: allow both root-yaml and profiles/
    for fn in src_root.glob("*.yaml"):
        # skip libraries/index
        if fn.name in ("domains_index.yaml",):
            continue
        if fn.name == "core_en_ro.yaml":
            continue
        out = USER_PROFILES_DIR / fn.name
        if not out.exists():
            shutil.copy2(fn, out)

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

    b = _bundle_root()
    if b is not None and b.exists():
        _seed_from_source(b)
        return

    if REPO_ATS_ROOT.exists():
        _seed_from_source(REPO_ATS_ROOT)


# ---------------------------
# Index: domain groups + library mapping
# ---------------------------
def load_domains_index() -> Dict[str, Any]:
    """
    Reads domains_index.yaml (user first, then repo/bundle). Supports BOTH schemas:

    v1/v2 (flat):
      domains: [{id, label:{en,ro}, library: "libraries/domains/xyz.yaml"}, ...]

    grouped (recommended):
      groups:
        - id: it
          label: {en,ro}
          domains: [{id,label,library}, ...]

    Returns dict (possibly empty).
    """
    ensure_seeded()
    # prefer user copy, fallback to repo/bundle
    if USER_INDEX_PATH.exists():
        idx_path = USER_INDEX_PATH
    else:
        b = _bundle_root()
        if b is not None and (b / "domains_index.yaml").exists():
            idx_path = b / "domains_index.yaml"
        else:
            idx_path = REPO_INDEX_PATH

    if not idx_path.exists():
        return {}

    raw = yaml.safe_load(_read_text(idx_path)) or {}
    if not isinstance(raw, dict):
        return {}
    raw["_source_file"] = str(idx_path)
    return raw


def flatten_domains_index(idx: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Returns a flat list of domains:
      [{id, label, library, group_id, group_label}, ...]
    """
    if not isinstance(idx, dict):
        return []

    out: List[Dict[str, Any]] = []

    if isinstance(idx.get("domains"), list):
        for d in idx.get("domains") or []:
            if not isinstance(d, dict) or not d.get("id"):
                continue
            out.append({
                "id": str(d.get("id")).strip(),
                "label": d.get("label") or {},
                "library": d.get("library") or "",
                "group_id": "",
                "group_label": {},
            })

    if isinstance(idx.get("groups"), list):
        for g in idx.get("groups") or []:
            if not isinstance(g, dict) or not g.get("id"):
                continue
            gid = str(g.get("id")).strip()
            glabel = g.get("label") or {}
            for d in (g.get("domains") or []):
                if not isinstance(d, dict) or not d.get("id"):
                    continue
                out.append({
                    "id": str(d.get("id")).strip(),
                    "label": d.get("label") or {},
                    "library": d.get("library") or "",
                    "group_id": gid,
                    "group_label": glabel,
                })

    # dedupe by id (first wins)
    seen = set()
    ded: List[Dict[str, Any]] = []
    for d in out:
        did = d.get("id")
        if not did or did in seen:
            continue
        seen.add(did)
        ded.append(d)
    return ded


def domain_library_from_index(domain_id: str, idx: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """
    If domains_index.yaml maps domain_id -> library path, return it.
    Otherwise None.
    """
    did = (domain_id or "").strip()
    if not did:
        return None
    idx = idx or load_domains_index()
    for d in flatten_domains_index(idx):
        if d.get("id") == did:
            lib = str(d.get("library") or "").strip()
            return lib or None
    return None


# ---------------------------
# Paths
# ---------------------------
def profile_path(profile_id: str) -> Path:
    """
    Returns path to the user's profile YAML file (preferred location).
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
    """
    Default mapping: USER_LIBRARIES_DIR/domains/<domain_id>.yaml
    BUT if domains_index.yaml specifies a library path, prefer that.
    """
    ensure_seeded()
    did = (domain_id or "").strip()
    if not did:
        return USER_DOMAIN_LIB_DIR / "_missing.yaml"

    idx = load_domains_index()
    lib_rel = domain_library_from_index(did, idx=idx)

    if lib_rel:
        # allow both "libraries/domains/x.yaml" and "domains/x.yaml"
        lib_rel = lib_rel.replace("\\", "/")
        if lib_rel.startswith("libraries/"):
            lib_rel = lib_rel[len("libraries/"):]
        # resolve under USER_LIBRARIES_DIR
        return USER_LIBRARIES_DIR / lib_rel

    if not did.endswith(".yaml"):
        did += ".yaml"
    return USER_DOMAIN_LIB_DIR / did


# ---------------------------
# Normalization / merge
# ---------------------------
def validate_profile(profile: Dict[str, Any]) -> Tuple[bool, List[str]]:
    warnings: List[str] = []
    if not isinstance(profile, dict):
        raise ProfileError("Profile YAML root must be a mapping/object")

    if not profile.get("id"):
        warnings.append("Missing 'id' (recommended).")
    if not profile.get("title"):
        warnings.append("Missing 'title' (recommended for UI).")
    if not profile.get("domain"):
        warnings.append("Missing 'domain' (recommended: enables domain libraries).")
    return True, warnings


def _normalize_keywords(profile: Dict[str, Any], lang: str) -> Dict[str, List[str]]:
    kw = _safe_dict(profile.get("keywords"))

    # legacy group names mapped into technologies
    technologies = _safe_list(_pick_lang(kw.get("technologies"), lang))
    for legacy_key in ("services", "platforms", "languages", "concepts"):
        technologies = _merge_lists(technologies, _safe_list(_pick_lang(kw.get(legacy_key), lang)))

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

    # domain
    p["domain"] = str(p.get("domain") or pid).strip()

    # Title: keep bilingual dict if provided by user profile (NOT from libraries)
    title_raw = p.get("title")
    title = str(_pick_lang(title_raw, lang=lang) or "").strip()
    if not title:
        jt = _safe_list(_pick_lang(p.get("job_titles"), lang=lang))
        title = jt[0] if jt else pid.replace("_", " ").title()
        p["title"] = title  # simple string fallback

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


def _merge_profile_like(base: Dict[str, Any], extra: Dict[str, Any], lang: str, source: str) -> Dict[str, Any]:
    """
    Merge a "profile-like" dict into base.

    source:
      - "core"   (core library)
      - "domain" (domain library)
      - "profile" (actual profile file)

    Rules:
      - lists -> concat + dedupe
      - keywords buckets -> concat + dedupe per bucket
      - for libraries, DO NOT merge 'title' (prevents UI showing "Core Library" everywhere)
    """
    if not isinstance(extra, dict) or not extra:
        return base

    out = dict(base or {})

    # Scalar fields
    for k in ("id", "domain", "ats_hint", "notes"):
        if k in extra and (k not in out or not out.get(k)):
            out[k] = extra.get(k)

    # Title: profile wins; libraries should never override UI label
    if source == "profile" and extra.get("title") and not out.get("title"):
        out["title"] = extra.get("title")

    # job_titles (profile-only typically)
    if "job_titles" in extra:
        out["job_titles"] = _merge_lists(_safe_list(out.get("job_titles")), _safe_list(_pick_lang(extra.get("job_titles"), lang)))

    # action verbs / metrics / templates
    for k in ("action_verbs", "metrics", "bullet_templates", "section_priority"):
        if k in extra:
            if k == "metrics":
                vals = _flatten_metrics(extra.get(k), lang=lang)
            elif k == "section_priority":
                vals = _normalize_section_priority(extra.get(k), lang=lang)
            elif k == "bullet_templates":
                vals = _normalize_templates(extra.get(k), lang=lang)
            else:
                vals = _safe_list(_pick_lang(extra.get(k), lang=lang))

            out[k] = _merge_lists(_safe_list(out.get(k)), vals)

    # keywords buckets
    if isinstance(extra.get("keywords"), dict):
        base_kw = _safe_dict(out.get("keywords"))
        extra_kw = _safe_dict(extra.get("keywords"))
        merged_kw: Dict[str, Any] = dict(base_kw)
        for bucket in ("core", "technologies", "tools", "certifications", "frameworks", "soft_skills", "services", "platforms", "languages", "concepts"):
            if bucket in extra_kw:
                b = _safe_list(_pick_lang(base_kw.get(bucket), lang=lang))
                e = _safe_list(_pick_lang(extra_kw.get(bucket), lang=lang))
                merged_kw[bucket] = _merge_lists(b, e)
        out["keywords"] = merged_kw

    return out


# ---------------------------
# Public API
# ---------------------------
def load_profile(profile_id: str, lang: str = "en") -> Dict[str, Any]:
    """
    Load profile YAML from user's profiles dir, merge core+domain libraries, normalize.
    lang: 'en' or 'ro' for UI/export usage.
    """
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

    merged: Dict[str, Any] = {}
    merged = _merge_profile_like(merged, core_lib, lang=lang, source="core")
    merged = _merge_profile_like(merged, domain_lib, lang=lang, source="domain")
    merged = _merge_profile_like(merged, raw, lang=lang, source="profile")

    ok, warnings = validate_profile(merged)
    prof = normalize_profile(merged, fallback_id=pid, lang=lang)

    # Prefer UI labels from domains_index (if present) when profile has no explicit title
    if not raw.get("title"):
        idx = load_domains_index()
        for d in flatten_domains_index(idx):
            if d.get("id") == domain_id:
                prof["title"] = d.get("label") or prof.get("title")
                break

    prof["_warnings"] = warnings
    prof["_source_file"] = path.name
    return prof


def list_profiles(lang: str = "en") -> List[Dict[str, str]]:
    """
    Returns list of profiles available to UI.
    Reads from USER_PROFILES_DIR. (Seed ensures defaults exist.)
    """
    ensure_seeded()

    idx = load_domains_index()
    label_by_id: Dict[str, str] = {}
    for d in flatten_domains_index(idx):
        did = d.get("id")
        label = str(_pick_lang(d.get("label"), lang=lang) or "").strip()
        if did and label:
            label_by_id[did] = label

    out: List[Dict[str, str]] = []
    for fn in sorted(USER_PROFILES_DIR.glob("*.yaml")):
        pid = fn.stem

        title = label_by_id.get(pid, pid.replace("_", " ").title())

        try:
            data = yaml.safe_load(_read_text(fn)) or {}
            if isinstance(data, dict):
                t = data.get("title")
                # only trust profile's own title if present
                if t:
                    title = str(_pick_lang(t, lang) or title).strip() or title
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
