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
def _user_data_root(app_name: str = "CVBuilder") -> Path:
    """
    Stable per-user data folder.
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
USER_PROFILES_DIR = ATS_ROOT_DIR / "profiles"
USER_LIBRARIES_DIR = ATS_ROOT_DIR / "libraries"
USER_DOMAIN_LIB_DIR = USER_LIBRARIES_DIR / "domains"

# Bundled/repo folders
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


def pick_lang(val: Any, lang: str = "en") -> Any:
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
    out: List[str] = []
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
    metrics = pick_lang(metrics, lang=lang)
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
    x = pick_lang(x, lang=lang)
    t = _safe_list(x)
    if len(t) < 2:
        t.extend([
            "Delivered {scope} improvements using {tool_or_tech}; reduced {metric} by {value}.",
            "Implemented {control_or_feature} across {environment}; improved reliability/security and documented SOPs.",
        ])
    return t


def _normalize_section_priority(x: Any, lang: str = "en") -> List[str]:
    x = pick_lang(x, lang=lang)
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
    if src_root.exists():
        for fn in src_root.glob("*.yaml"):
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
# Paths
# ---------------------------
def profile_path(profile_id: str) -> Path:
    """
    Returns path to user profile YAML (in USER_PROFILES_DIR).
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
        raise ProfileError(f"Invalid YAML in {path.name}: root must be a mapping/object")
    return raw


# ---------------------------
# Domains index (UI filter + mapping)
# ---------------------------
def load_domains_index() -> Dict[str, Any]:
    """
    Loads ats_profiles/domains_index.yaml if present.
    Returns {} if missing.
    """
    ensure_seeded()
    p = USER_PROFILES_DIR / "domains_index.yaml"
    if not p.exists():
        # allow legacy in root of ats_profiles (source run)
        p2 = REPO_ATS_ROOT / "domains_index.yaml"
        if p2.exists():
            try:
                return _load_yaml_file(p2)
            except Exception:
                return {}
        return {}
    try:
        return _load_yaml_file(p)
    except Exception:
        return {}


def flatten_domains_index(index: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Normalizes domains_index into a predictable structure used by the UI.

    Returns:
      {
        "groups": [{"id","label","description"}...],
        "domains": [{"id","label","library","group_id"}...],
        "by_id": {id -> domain_dict}
      }
    """
    idx = index if isinstance(index, dict) else load_domains_index()
    out = {"groups": [], "domains": [], "by_id": {}}

    groups = idx.get("groups")
    if not isinstance(groups, list):
        return out

    for g in groups:
        if not isinstance(g, dict):
            continue
        gid = str(g.get("id") or "").strip()
        if not gid:
            continue

        out["groups"].append({
            "id": gid,
            "label": g.get("label") or {"en": gid, "ro": gid},
            "description": g.get("description") or {},
        })

        doms = g.get("domains")
        if not isinstance(doms, list):
            continue

        for d in doms:
            if not isinstance(d, dict):
                continue
            did = str(d.get("id") or "").strip()
            if not did:
                continue
            dom = {
                "id": did,
                "label": d.get("label") or {"en": did, "ro": did},
                "library": d.get("library") or "",
                "group_id": gid,
            }
            out["domains"].append(dom)
            out["by_id"][did] = dom

    return out


# ---------------------------
# Validation / normalization / merge
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

    # legacy groups into technologies
    technologies = _merge_lists(_safe_list(pick_lang(kw.get("technologies"), lang)), _safe_list(pick_lang(kw.get("services"), lang)))
    technologies = _merge_lists(technologies, _safe_list(pick_lang(kw.get("platforms"), lang)))
    technologies = _merge_lists(technologies, _safe_list(pick_lang(kw.get("languages"), lang)))
    technologies = _merge_lists(technologies, _safe_list(pick_lang(kw.get("concepts"), lang)))

    out = {
        "core": _safe_list(pick_lang(kw.get("core"), lang)),
        "technologies": technologies,
        "tools": _safe_list(pick_lang(kw.get("tools"), lang)),
        "certifications": _safe_list(pick_lang(kw.get("certifications"), lang)),
        "frameworks": _safe_list(pick_lang(kw.get("frameworks"), lang)),
        "soft_skills": _safe_list(pick_lang(kw.get("soft_skills"), lang)),
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

    p["domain"] = str(p.get("domain") or pid).strip() or pid

    # title (keep bilingual dict if provided)
    title_raw = p.get("title")
    title_pick = str(pick_lang(title_raw, lang=lang) or "").strip()
    if not title_pick:
        jt = _safe_list(pick_lang(p.get("job_titles"), lang=lang))
        title_pick = jt[0] if jt else pid.replace("_", " ").title()
    p["title"] = title_raw if isinstance(title_raw, dict) else title_pick

    p["job_titles"] = _safe_list(pick_lang(p.get("job_titles"), lang=lang))
    p["keywords"] = _normalize_keywords(p, lang=lang)

    p["action_verbs"] = _dedupe_preserve(_safe_list(pick_lang(p.get("action_verbs"), lang=lang)))
    p["metrics"] = _dedupe_preserve(_flatten_metrics(p.get("metrics"), lang=lang))
    p["bullet_templates"] = _normalize_templates(p.get("bullet_templates"), lang=lang)
    p["section_priority"] = _normalize_section_priority(p.get("section_priority"), lang=lang)

    p.setdefault("ats_hint", "")
    p.setdefault("notes", "")

    return p


def _merge_profile_like(base: Dict[str, Any], extra: Dict[str, Any], lang: str) -> Dict[str, Any]:
    """
    Merge profile-like dicts. base <- extra.
    - list-ish fields: concat + dedupe after lang pick.
    - keywords: merge buckets.
    - other keys: profile overrides libs.
    """
    out = dict(base or {})
    if not isinstance(extra, dict) or not extra:
        return out

    # simple overrides (id/domain/title/job_titles/ats_hint/notes/section_priority)
    for k in ("id", "domain", "title", "job_titles", "ats_hint", "notes", "section_priority"):
        if k in extra and extra.get(k) not in (None, "", [], {}):
            out[k] = extra.get(k)

    # merge list-like fields (support bilingual dict)
    for k in ("action_verbs", "metrics", "bullet_templates"):
        a = _safe_list(pick_lang(out.get(k), lang=lang))
        b = _safe_list(pick_lang(extra.get(k), lang=lang))
        if b:
            out[k] = _merge_lists(a, b)

    # keywords buckets
    base_kw = _safe_dict(out.get("keywords"))
    extra_kw = _safe_dict(extra.get("keywords"))
    if extra_kw:
        buckets = ["core", "technologies", "tools", "certifications", "frameworks", "soft_skills"]
        merged_kw: Dict[str, Any] = dict(base_kw)
        for b in buckets:
            merged_kw[b] = _merge_lists(
                _safe_list(pick_lang(base_kw.get(b), lang=lang)),
                _safe_list(pick_lang(extra_kw.get(b), lang=lang)),
            )
        out["keywords"] = merged_kw

    return out


# ---------------------------
# Public API
# ---------------------------
def list_profiles(lang: str = "en") -> List[Dict[str, str]]:
    """
    Returns list of selectable profile IDs for UI.
    Includes:
      - user profiles (*.yaml in USER_PROFILES_DIR, excluding domains_index)
      - domain-only entries from domains_index (even if no profile yaml exists yet)
        -> load_profile() can resolve these by falling back to domain library.
    """
    ensure_seeded()

    # 1) file-backed profiles
    out: List[Dict[str, str]] = []
    for fn in sorted(USER_PROFILES_DIR.glob("*.yaml")):
        if fn.name == "domains_index.yaml":
            continue
        pid = fn.stem
        title = pid.replace("_", " ").title()
        try:
            data = yaml.safe_load(_read_text(fn)) or {}
            if isinstance(data, dict):
                t = data.get("title")
                title = str(pick_lang(t, lang) or title).strip() or title
        except Exception:
            pass
        out.append({"id": pid, "filename": fn.name, "title": title})

    existing_ids = {p["id"] for p in out}

    # 2) domain-only entries
    flat = flatten_domains_index()
    for dom in flat.get("domains", []):
        did = dom.get("id")
        if not did or did in existing_ids:
            continue
        title = str(pick_lang(dom.get("label"), lang) or did).strip() or did
        out.append({"id": did, "filename": "", "title": title})

    # stable order: title then id
    out.sort(key=lambda d: (d.get("title", "").lower(), d.get("id", "").lower()))
    return out


def load_profile(profile_id: str, lang: str = "en") -> Dict[str, Any]:
    """
    Load profile YAML + merge core + domain libraries.

    IMPORTANT:
    - If user does NOT have a profile yaml for this id, but a domain library exists
      (libraries/domains/<id>.yaml), we build a minimal profile from that domain library.
      This prevents UI loops and makes every domain selectable.
    """
    pid = (profile_id or "").strip()
    if not pid:
        raise ProfileError("No profile selected")

    ensure_seeded()

    # 1) Try profile yaml
    path = profile_path(pid)
    raw = _load_yaml_file(path)

    # 2) Fallback: treat domain library as profile if profile yaml missing
    used_fallback = False
    if not raw:
        dom_lib_path = _domain_library_path(pid)
        dom_lib = _load_yaml_file(dom_lib_path)
        if not dom_lib:
            raise ProfileError(f"Profile not found: {path} (and no domain library at {dom_lib_path})")
        raw = {"id": pid, "domain": pid, **dom_lib}
        used_fallback = True

    raw["id"] = raw.get("id") or pid
    raw["domain"] = raw.get("domain") or raw["id"]
    domain_id = str(raw.get("domain") or raw.get("id") or pid).strip() or pid

    # libraries
    core_lib = _load_yaml_file(_core_library_path())
    domain_lib = _load_yaml_file(_domain_library_path(domain_id))

    merged: Dict[str, Any] = {}
    merged = _merge_profile_like(merged, core_lib, lang=lang)
    merged = _merge_profile_like(merged, domain_lib, lang=lang)
    merged = _merge_profile_like(merged, raw, lang=lang)

    ok, warnings = validate_profile(merged)
    prof = normalize_profile(merged, fallback_id=pid, lang=lang)
    prof["_warnings"] = warnings
    prof["_source_file"] = ("(domain library)" if used_fallback else path.name)
    return prof


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
        pid = _slugify(str(pick_lang(profile.get("title"), "en") or "profile"))

    profile = dict(profile or {})
    profile["id"] = profile.get("id") or pid
    profile["domain"] = profile.get("domain") or profile["id"]

    text_out = yaml.safe_dump(profile, sort_keys=False, allow_unicode=True)
    _write_text(profile_path(pid), text_out)
    return pid
