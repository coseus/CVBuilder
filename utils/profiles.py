# utils/profiles.py
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
def _user_data_root(app_name: str = "CVBuilder") -> Path:
    """
    Stable per-user data folder (works for Streamlit Cloud too, but Cloud is ephemeral).
    Windows: %APPDATA%/<app_name>
    macOS: ~/Library/Application Support/<app_name>
    Linux: $XDG_DATA_HOME/<app_name> or ~/.local/share/<app_name>
    """
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / app_name

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / app_name

    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / app_name
    return Path.home() / ".local" / "share" / app_name


# Where user-editable profiles live (persist between updates)
ATS_ROOT_DIR = _user_data_root("CVBuilder") / "ats_profiles"
USER_PROFILES_DIR = ATS_ROOT_DIR / "profiles"  # stubs + user profiles
USER_LIBRARIES_DIR = ATS_ROOT_DIR / "libraries"
USER_DOMAIN_LIB_DIR = USER_LIBRARIES_DIR / "domains"

# Bundled repo layout (source / PyInstaller bundle)
REPO_ATS_ROOT = Path("ats_profiles")


# ---------------------------
# Helpers
# ---------------------------
def _ensure_dirs() -> None:
    USER_PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    USER_DOMAIN_LIB_DIR.mkdir(parents=True, exist_ok=True)


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def _bundle_root() -> Optional[Path]:
    """If running from PyInstaller, resources are under sys._MEIPASS/ats_profiles."""
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
    """If val is dict with 'en'/'ro', pick matching language; fallback to other."""
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
    out: List[str] = []
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


# ---------------------------
# Seeding: copy bundled repo ats_profiles into user data folder (first run)
# ---------------------------
def _seed_from_source(src_root: Path) -> None:
    """
    Copy ats_profiles into USER ATS_ROOT_DIR if missing.
    - root *.yaml -> USER_PROFILES_DIR (stubs)
    - profiles/*.yaml -> USER_PROFILES_DIR
    - libraries/** -> USER_LIBRARIES_DIR
    Does not overwrite user files.
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

    # root yaml -> profiles dir (stubs)
    for fn in src_root.glob("*.yaml"):
        out = USER_PROFILES_DIR / fn.name
        if not out.exists():
            shutil.copy2(fn, out)

    # optional ats_profiles/profiles -> profiles dir
    if (src_root / "profiles").exists():
        copy_tree_if_missing(src_root / "profiles", USER_PROFILES_DIR)

    # libraries
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


# ---------------------------
# Paths
# ---------------------------
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


def _domain_library_default_path(domain_id: str) -> Path:
    ensure_seeded()
    did = (domain_id or "").strip()
    if not did:
        return USER_DOMAIN_LIB_DIR / "_missing.yaml"
    if not did.endswith(".yaml"):
        did += ".yaml"
    return USER_DOMAIN_LIB_DIR / did


def _domains_index_path() -> Path:
    # domains_index.yaml can be shipped either in profiles dir or in root repo;
    # seed copies root yaml into USER_PROFILES_DIR.
    ensure_seeded()
    p = USER_PROFILES_DIR / "domains_index.yaml"
    if p.exists():
        return p
    # fallback: in ATS root (older layout)
    p2 = ATS_ROOT_DIR / "domains_index.yaml"
    return p2


# ---------------------------
# Domains index (supports BOTH schemas)
# ---------------------------
@dataclass
class DomainEntry:
    profile_id: str
    group_id: str
    label: Dict[str, str]  # {en, ro}
    library_rel: str       # relative path inside ats_profiles, e.g. libraries/domains/cloud_security.yaml


def load_domains_index() -> Dict[str, Any]:
    """
    Loads domains_index.yaml if present.
    Supports:
    - NEW schema (your latest):
        version: 1
        groups: [{id, label{en,ro}, domains:[{id,label{en,ro},library}]}]
    - Older schema:
        profiles: [{id, group, label{en,ro}, library}]
    """
    path = _domains_index_path()
    if not path.exists():
        return {}

    raw = yaml.safe_load(_read_text(path)) or {}
    if not isinstance(raw, dict):
        return {}
    return raw


def _domains_index_entries() -> List[DomainEntry]:
    idx = load_domains_index()
    out: List[DomainEntry] = []

    # New schema
    groups = idx.get("groups")
    if isinstance(groups, list):
        for g in groups:
            if not isinstance(g, dict):
                continue
            gid = str(g.get("id") or "").strip() or "other"
            domains = g.get("domains")
            if not isinstance(domains, list):
                continue
            for d in domains:
                if not isinstance(d, dict):
                    continue
                pid = str(d.get("id") or "").strip()
                if not pid:
                    continue
                label = d.get("label") if isinstance(d.get("label"), dict) else {}
                lib = str(d.get("library") or "").strip()
                if not lib:
                    continue
                out.append(DomainEntry(profile_id=pid, group_id=gid, label=label, library_rel=lib))
        return out

    # Old schema
    profs = idx.get("profiles")
    if isinstance(profs, list):
        for p in profs:
            if not isinstance(p, dict):
                continue
            pid = str(p.get("id") or "").strip()
            if not pid:
                continue
            gid = str(p.get("group") or p.get("group_id") or "other").strip() or "other"
            label = p.get("label") if isinstance(p.get("label"), dict) else {}
            lib = str(p.get("library") or "").strip()
            if not lib:
                continue
            out.append(DomainEntry(profile_id=pid, group_id=gid, label=label, library_rel=lib))
    return out


def index_profile_label(profile_id: str, lang: str = "en") -> str:
    """Return UI label from domains_index.yaml for profile_id, else fallback to prettified id."""
    pid = (profile_id or "").strip()
    if not pid:
        return ""
    for e in _domains_index_entries():
        if e.profile_id == pid:
            v = _pick_lang(e.label, lang=lang)
            s = str(v or "").strip()
            if s:
                return s
    return pid.replace("_", " ").title()


def index_profile_group(profile_id: str) -> str:
    pid = (profile_id or "").strip()
    for e in _domains_index_entries():
        if e.profile_id == pid:
            return e.group_id
    return "other"


def index_group_options(lang: str = "en") -> List[Tuple[str, str]]:
    """
    Returns list of (group_id, group_label) for UI filters.
    """
    idx = load_domains_index()
    groups = idx.get("groups")
    if not isinstance(groups, list):
        # fallback: derive from entries
        seen = set()
        out: List[Tuple[str, str]] = []
        for e in _domains_index_entries():
            if e.group_id in seen:
                continue
            seen.add(e.group_id)
            out.append((e.group_id, e.group_id.upper()))
        return out

    out: List[Tuple[str, str]] = []
    for g in groups:
        if not isinstance(g, dict):
            continue
        gid = str(g.get("id") or "").strip()
        if not gid:
            continue
        label = g.get("label") if isinstance(g.get("label"), dict) else {}
        out.append((gid, str(_pick_lang(label, lang=lang) or gid).strip()))
    return out


def index_library_for_profile(profile_id: str) -> Optional[Path]:
    """
    If domains_index maps a profile_id to a specific library file, return absolute Path to it.
    Otherwise return None.
    """
    pid = (profile_id or "").strip()
    if not pid:
        return None

    for e in _domains_index_entries():
        if e.profile_id == pid and e.library_rel:
            # Make it absolute inside user ATS root (seeded files live in USER_LIBRARIES_DIR/...)
            rel = Path(e.library_rel)
            # normalize: library_rel starts with "libraries/..."
            return ATS_ROOT_DIR / rel
    return None


# ---------------------------
# Loading / normalizing + library merge
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

    def bucket(name: str) -> List[str]:
        v = _pick_lang(kw.get(name), lang=lang)
        return _dedupe_preserve(_safe_list(v))

    # legacy keys merged into technologies
    tech = bucket("technologies")
    for legacy in ("services", "platforms", "languages", "concepts"):
        tech = _dedupe_preserve(tech + _safe_list(_pick_lang(kw.get(legacy), lang=lang)))

    return {
        "core": bucket("core"),
        "technologies": tech,
        "tools": bucket("tools"),
        "certifications": bucket("certifications"),
        "frameworks": bucket("frameworks"),
        "soft_skills": bucket("soft_skills"),
    }


def _flatten_metrics(metrics: Any, lang: str = "en") -> List[str]:
    metrics = _pick_lang(metrics, lang=lang)
    if metrics is None:
        return []
    if isinstance(metrics, list):
        return _dedupe_preserve(_safe_list(metrics))
    if isinstance(metrics, dict):
        flat: List[str] = []
        for _, v in metrics.items():
            flat.extend(_safe_list(v))
        return _dedupe_preserve(flat)
    if isinstance(metrics, str):
        return _dedupe_preserve(_safe_list(metrics))
    return _dedupe_preserve(_safe_list(metrics))


def _normalize_templates(x: Any, lang: str = "en") -> List[str]:
    x = _pick_lang(x, lang=lang)
    t = _safe_list(x)
    if len(t) < 2:
        t.extend([
            "Delivered {scope} improvements using {tool_or_tech}; reduced {metric} by {value}.",
            "Implemented {control_or_feature} across {environment}; improved reliability/security and documented SOPs.",
        ])
    return _dedupe_preserve(t)


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
    p = dict(profile or {})

    pid = (p.get("id") or fallback_id or "").strip()
    if not pid:
        pid = _slugify(fallback_id or "profile")
    p["id"] = pid

    # Domain
    p["domain"] = str(p.get("domain") or pid).strip()

    # Title (bilingual dict supported)
    title_raw = p.get("title")
    title = str(_pick_lang(title_raw, lang=lang) or "").strip()
    if not title:
        title = index_profile_label(pid, lang=lang)
    # keep dict if user uses it, else string
    p["title"] = title_raw if isinstance(title_raw, dict) else title

    # Job titles
    p["job_titles"] = _safe_list(_pick_lang(p.get("job_titles"), lang=lang))

    # Keywords buckets
    p["keywords"] = _normalize_keywords(p, lang=lang)

    p["action_verbs"] = _dedupe_preserve(_safe_list(_pick_lang(p.get("action_verbs"), lang=lang)))
    p["metrics"] = _flatten_metrics(p.get("metrics"), lang=lang)
    p["bullet_templates"] = _normalize_templates(p.get("bullet_templates"), lang=lang)
    p["section_priority"] = _normalize_section_priority(p.get("section_priority"), lang=lang)

    p.setdefault("ats_hint", "")
    p.setdefault("notes", "")

    return p


def _merge_profile_like(base: Dict[str, Any], extra: Dict[str, Any], lang: str) -> Dict[str, Any]:
    """
    Merge library/profile dicts without clobbering profile-specific fields.
    - For list fields: concat + dedupe
    - For keywords: merge buckets (extra first, then base, then normalize later)
    - For dict bilingual fields: keep both, profile overrides
    """
    out = dict(base or {})
    if not isinstance(extra, dict) or not extra:
        return out

    # Merge keywords (keep as raw dict; normalize later)
    if isinstance(extra.get("keywords"), dict):
        kw_out = _safe_dict(out.get("keywords"))
        kw_extra = _safe_dict(extra.get("keywords"))
        merged_kw = dict(kw_extra)
        merged_kw.update(kw_out)  # base overrides library
        out["keywords"] = merged_kw

    # Merge list-like fields
    for k in ("action_verbs", "metrics", "bullet_templates", "job_titles", "section_priority"):
        ev = extra.get(k)
        bv = out.get(k)
        if bv is None:
            out[k] = ev
            continue
        if isinstance(ev, dict) and isinstance(bv, dict):
            merged = dict(ev)
            merged.update(bv)  # base overrides
            out[k] = merged
        elif isinstance(ev, list) and isinstance(bv, list):
            out[k] = _dedupe_preserve(list(ev) + list(bv))
        else:
            # keep base
            out[k] = bv

    # Scalar fields (only fill if missing)
    for k in ("title", "domain", "ats_hint", "notes", "id"):
        if out.get(k):
            continue
        if extra.get(k):
            out[k] = extra.get(k)

    return out


def load_profile(profile_id: str, lang: str = "en") -> Dict[str, Any]:
    """
    Load profile YAML from USER_PROFILES_DIR, merge:
      core library -> domain library -> profile
    Domain library can be resolved via:
      - domains_index.yaml mapping (best)
      - fallback: libraries/domains/<domain>.yaml
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

    # libraries
    core_lib = _load_yaml_file(_core_library_path())

    # domain library: prefer domains_index mapping for pid, else by domain_id
    lib_path = index_library_for_profile(pid) or index_library_for_profile(domain_id) or _domain_library_default_path(domain_id)
    domain_lib = _load_yaml_file(lib_path) if lib_path else {}

    merged: Dict[str, Any] = {}
    merged = _merge_profile_like(merged, core_lib, lang=lang)
    merged = _merge_profile_like(merged, domain_lib, lang=lang)
    merged = _merge_profile_like(merged, raw, lang=lang)

    # If profile stub didn't define title, force a label from domains_index (prevents "Core Library (...)")
    if not raw.get("title"):
        merged["title"] = {"en": index_profile_label(pid, "en"), "ro": index_profile_label(pid, "ro")}

    ok, warnings = validate_profile(merged)
    prof = normalize_profile(merged, fallback_id=pid, lang=lang)
    prof["_warnings"] = warnings
    prof["_source_file"] = path.name
    return prof


def list_profiles() -> List[Dict[str, str]]:
    """
    List available profiles for UI.
    Ignores libraries and special index/core files.
    Shows labels from domains_index where possible.
    """
    ensure_seeded()
    out: List[Dict[str, str]] = []
    for fn in sorted(USER_PROFILES_DIR.glob("*.yaml")):
        pid = fn.stem
        if pid in ("core_en_ro", "domains_index"):
            continue

        title = index_profile_label(pid, lang="en")  # list view in EN
        try:
            data = yaml.safe_load(_read_text(fn)) or {}
            if isinstance(data, dict) and data.get("title"):
                # prefer explicit profile title
                t = data.get("title")
                title = str(_pick_lang(t, "en") or title).strip() or title
        except Exception:
            pass

        out.append({"id": pid, "filename": fn.name, "title": title})
    return out


def save_profile_text(profile_id: str, yaml_text: str) -> None:
    """
    Save raw YAML text (profile editor). Validates parse first.
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
