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
        t.extend(
            [
                "Delivered {scope} improvements using {tool_or_tech}; reduced {metric} by {value}.",
                "Implemented {control_or_feature} across {environment}; improved reliability/security and documented SOPs.",
            ]
        )
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

    # root yaml -> USER_PROFILES_DIR
    if src_root.exists():
        for fn in src_root.glob("*.yaml"):
            out = USER_PROFILES_DIR / fn.name
            if not out.exists():
                shutil.copy2(fn, out)

    # ats_profiles/profiles -> USER_PROFILES_DIR
    if (src_root / "profiles").exists():
        copy_tree_if_missing(src_root / "profiles", USER_PROFILES_DIR)

    # libraries
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


def _core_library_path() -> Path:
    ensure_seeded()
    return USER_LIBRARIES_DIR / "core_en_ro.yaml"


def load_domains_index() -> Dict[str, Any]:
    """Load `ats_profiles/domains_index.yaml` (if present).

    Supports two schemas:

    **Schema A (flat)**
      profiles: [{id,label,domain}]
      groups:   [{id,label,profiles:[ids]}]
      domains:  [{id, library}]

    **Schema B (nested)**
      groups: [{id,label,domains:[{id,label,library}]}]

    `flatten_domains_index()` converts schema B -> schema A.
    """
    ensure_seeded()

    candidates = [
        ATS_ROOT_DIR / "domains_index.yaml",
        REPO_ATS_ROOT / "domains_index.yaml",
    ]
    b = _bundle_root()
    if b is not None:
        candidates.insert(1, b / "domains_index.yaml")

    for cand in candidates:
        try:
            if cand.exists():
                obj = _load_yaml_file(cand)
                return obj if isinstance(obj, dict) else {}
        except Exception:
            continue
    return {}


def flatten_domains_index(idx: Optional[Dict[str, Any]] = None, *, lang: str = "en") -> Dict[str, Any]:
    """
    Return a normalized domains index (Schema A).

    Accepts:
      - flatten_domains_index() -> loads domains_index.yaml internally
      - flatten_domains_index(idx) -> uses provided dict (backward-compatible with existing UI)

    Output schema (Schema A):
      {
        "profiles": [{"id":..., "label":..., "domain":...}, ...],
        "groups":   [{"id":..., "label":..., "profiles":[profile_ids...]}, ...],
        "domains":  [{"id": domain_id, "library": "libraries/domains/<domain>.yaml"}, ...]
      }

    Supports input schemas:

    **Schema A (already flat)**
      profiles: [...]
      groups: [...]
      domains: [...]

    **Schema B (nested)**
      groups: [{id,label,domains:[{id,label,library}]}]
    """
    raw = idx if isinstance(idx, dict) else (load_domains_index() or {})

    # Already Schema A
    if isinstance(raw.get("profiles"), list) and isinstance(raw.get("groups"), list):
        return raw

    groups_in = raw.get("groups") or []
    if not isinstance(groups_in, list):
        return {"profiles": [], "groups": [], "domains": []}

    profiles: List[Dict[str, Any]] = []
    groups: List[Dict[str, Any]] = []
    domains_map: Dict[str, str] = {}

    for g in groups_in:
        if not isinstance(g, dict):
            continue

        gid = str(g.get("id") or "").strip() or "group"
        glabel = g.get("label") or {}
        gdomains = g.get("domains") or []
        if not isinstance(gdomains, list):
            gdomains = []

        group_profile_ids: List[str] = []

        for d in gdomains:
            if not isinstance(d, dict):
                continue

            pid = str(d.get("id") or "").strip()
            if not pid:
                continue

            label_val = d.get("label")
            if isinstance(label_val, dict):
                label = str(label_val.get(lang) or label_val.get("en") or label_val.get("ro") or pid).strip()
            else:
                label = str(label_val or pid).strip()

            lib_path = str(d.get("library") or "").strip()
            if lib_path:
                domain_id = Path(lib_path.replace("\\", "/")).stem
                domains_map[domain_id] = lib_path
            else:
                domain_id = pid

            profiles.append({"id": pid, "label": label, "domain": domain_id})
            group_profile_ids.append(pid)

        if isinstance(glabel, dict):
            glabel_str = str(glabel.get(lang) or glabel.get("en") or glabel.get("ro") or gid).strip()
        else:
            glabel_str = str(glabel or gid).strip()

        groups.append({"id": gid, "label": glabel_str, "profiles": group_profile_ids})

    domains = [{"id": did, "library": lpath} for did, lpath in sorted(domains_map.items())]

    # Dedup profiles by id
    seen = set()
    prof_out = []
    for p in profiles:
        if p["id"] in seen:
            continue
        seen.add(p["id"])
        prof_out.append(p)

    return {"profiles": prof_out, "groups": groups, "domains": domains}

def _domain_library_path(domain_id: str) -> Path:
    """Resolve domain library path.

    Default: USER_DOMAIN_LIB_DIR/<domain_id>.yaml

    If domains_index.yaml maps domain -> custom library path, prefer that.
    """
    ensure_seeded()
    did = (domain_id or "").strip()
    if not did:
        return USER_DOMAIN_LIB_DIR / "core.yaml"  # won't exist; safe

    idx = flatten_domains_index(lang="en")
    for d in idx.get("domains", []) or []:
        if isinstance(d, dict) and str(d.get("id") or "") == did:
            lib = str(d.get("library") or "").strip()
            if lib:
                lib_norm = lib.replace("\\", "/")
                if lib_norm.startswith("libraries/"):
                    rel = Path(lib_norm).relative_to("libraries")
                    return USER_LIBRARIES_DIR / rel
                return ATS_ROOT_DIR / lib_norm

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
    # keep dict if user uses bilingual dict, else store computed string
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


def _merge_profile_like(
    base: Dict[str, Any],
    extra: Dict[str, Any],
    *,
    lang: str = "en",
    is_library: bool = False,
) -> Dict[str, Any]:
    """
    Merge profile-like dicts without clobbering user/profile identity.

    - libraries: merge only ATS content (keywords, verbs, metrics, templates, hints), NOT id/title/domain/job_titles
    - profile: can set id/title/domain/job_titles

    keywords buckets are merged at normalize-time (lang-aware).
    """
    out = dict(base or {})

    if not isinstance(extra, dict) or not extra:
        return out

    # Libraries should NOT override profile identity fields.
    # (Otherwise UI can show 'Core Library' as title for every profile.)
    if is_library:
        extra = {k: v for k, v in extra.items() if k not in ("id", "domain", "title", "job_titles")}

    # Merge list-ish fields (allow bilingual dicts to remain dicts; normalize_profile will pick lang)
    for k in ("action_verbs", "bullet_templates", "metrics", "section_priority"):
        if k not in extra:
            continue
        if k not in out:
            out[k] = extra.get(k)
            continue

        lv = extra.get(k)
        pv = out.get(k)

        if isinstance(lv, dict) and isinstance(pv, dict):
            merged = dict(lv)
            merged.update(pv)  # base overrides
            out[k] = merged
        elif isinstance(lv, list) and isinstance(pv, list):
            out[k] = _dedupe_preserve(list(pv) + list(lv))
        else:
            # keep base
            out[k] = pv

    # Merge keywords as dict (profile buckets override library buckets)
    if isinstance(extra.get("keywords"), dict):
        out_kw = _safe_dict(out.get("keywords"))
        lib_kw = _safe_dict(extra.get("keywords"))
        merged_kw = dict(lib_kw)
        merged_kw.update(out_kw)
        out["keywords"] = merged_kw

    # Scalars: profile may set; libraries only fill if missing
    for k in ("id", "domain", "title", "job_titles", "ats_hint", "notes"):
        if k not in extra:
            continue
        if k not in out or out.get(k) in (None, "", [], {}):
            out[k] = extra.get(k)

    return out


def index_profile_domain(profile_id: str) -> str:
    """Return domain id for a profile based on domains_index.yaml (if present)."""
    pid = (profile_id or "").strip()
    if not pid:
        return ""
    idx = flatten_domains_index(lang="en")
    for p in idx.get("profiles", []) or []:
        if isinstance(p, dict) and str(p.get("id") or "") == pid:
            return str(p.get("domain") or "").strip()
    return ""


def index_profile_label(profile_id: str, *, lang: str = "en") -> str:
    """Return UI label for a profile id based on domains_index.yaml (if present)."""
    pid = (profile_id or "").strip()
    if not pid:
        return ""
    idx = flatten_domains_index(lang=lang)
    for p in idx.get("profiles", []) or []:
        if isinstance(p, dict) and str(p.get("id") or "") == pid:
            return str(p.get("label") or "").strip() or pid
    return pid


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

    # domain from YAML OR domains_index mapping OR fallback to id
    mapped_domain = index_profile_domain(raw["id"])
    raw["domain"] = raw.get("domain") or mapped_domain or raw["id"]

    domain_id = str(raw.get("domain") or raw.get("id") or pid).strip()

    core_lib = _load_yaml_file(_core_library_path())
    domain_lib = _load_yaml_file(_domain_library_path(domain_id))

    merged: Dict[str, Any] = {}
    merged = _merge_profile_like(merged, core_lib, lang=lang, is_library=True)
    merged = _merge_profile_like(merged, domain_lib, lang=lang, is_library=True)
    merged = _merge_profile_like(merged, raw, lang=lang, is_library=False)

    ok, warnings = validate_profile(merged)
    prof = normalize_profile(merged, fallback_id=pid, lang=lang)
    prof["_warnings"] = warnings
    prof["_source_file"] = path.name
    return prof


def list_profiles(*, lang: str = "en") -> List[Dict[str, str]]:
    """
    Returns list of profiles available to UI.
    """
    ensure_seeded()

    # If domains_index exists, prefer it for labeling + ordering
    idx = flatten_domains_index(lang=lang)
    idx_profiles = idx.get("profiles") if isinstance(idx.get("profiles"), list) else None
    if idx_profiles:
        out: List[Dict[str, str]] = []
        for p in idx_profiles:
            if not isinstance(p, dict):
                continue
            pid = str(p.get("id") or "").strip()
            if not pid:
                continue
            label = str(p.get("label") or pid).strip()
            out.append({"id": pid, "filename": f"{pid}.yaml", "title": label})
        return out

    out: List[Dict[str, str]] = []
    for fn in sorted(USER_PROFILES_DIR.glob("*.yaml")):
        pid = fn.stem
        title = pid.replace("_", " ").title()
        try:
            data = yaml.safe_load(_read_text(fn)) or {}
            if isinstance(data, dict):
                t = data.get("title")
                title = str(_pick_lang(t, lang) or title).strip() or title
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
    parsed["domain"] = parsed.get("domain") or index_profile_domain(parsed["id"]) or parsed["id"]

    text_out = yaml.safe_dump(parsed, sort_keys=False, allow_unicode=True)
    _write_text(profile_path(pid), text_out)


def save_profile_dict(profile: Dict[str, Any], profile_id: Optional[str] = None) -> str:
    ensure_seeded()
    pid = (profile_id or profile.get("id") or "").strip()
    if not pid:
        pid = _slugify(str(_pick_lang(profile.get("title"), "en") or "profile"))
    profile = dict(profile or {})
    profile["id"] = profile.get("id") or pid
    profile["domain"] = profile.get("domain") or index_profile_domain(profile["id"]) or profile["id"]

    text_out = yaml.safe_dump(profile, sort_keys=False, allow_unicode=True)
    _write_text(profile_path(pid), text_out)
    return pid
