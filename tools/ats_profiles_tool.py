#!/usr/bin/env python3
"""
CVBuilder - ATS Profiles Tool (validate/migrate/generate)

Usage:
  python tools/ats_profiles_tool.py validate --root ats_profiles
  python tools/ats_profiles_tool.py migrate  --root ats_profiles --write
  python tools/ats_profiles_tool.py generate --root ats_profiles --domain it --id new_profile --title "New Profile"

Notes:
- Requires: PyYAML
- Optional: rich (pretty output). Falls back to plain printing.
"""

from __future__ import annotations

import argparse
import sys
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


# -------------------------
# Pretty output (optional)
# -------------------------
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text

    _RICH = True
    console = Console()
except Exception:
    _RICH = False
    console = None  # type: ignore


def _p(msg: str) -> None:
    if _RICH:
        console.print(msg)
    else:
        print(msg)


def _ok(msg: str) -> None:
    if _RICH:
        console.print(f"[green]✔[/green] {msg}")
    else:
        print(f"[OK] {msg}")


def _warn(msg: str) -> None:
    if _RICH:
        console.print(f"[yellow]⚠[/yellow] {msg}")
    else:
        print(f"[WARN] {msg}")


def _err(msg: str) -> None:
    if _RICH:
        console.print(f"[red]✖[/red] {msg}")
    else:
        print(f"[ERROR] {msg}")


# -------------------------
# Paths / conventions
# -------------------------
PROFILE_EXT = ".yaml"

DEFAULT_CORE_LIB = "libraries/core_en_ro.yaml"
DEFAULT_DOMAIN_LIB_DIR = "libraries/domains"
DEFAULT_DOMAINS_INDEX = "domains_index.yaml"


# -------------------------
# YAML utils
# -------------------------
def load_yaml(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"Failed to parse YAML: {path} ({e})")


def dump_yaml(obj: Any) -> str:
    return yaml.safe_dump(obj, sort_keys=False, allow_unicode=True)


def write_yaml(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_yaml(obj), encoding="utf-8")


def slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9\-_ ]+", "", s)
    s = re.sub(r"\s+", "_", s).strip("_")
    return s or "profile"


def pick_lang(val: Any, lang: str) -> Any:
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


def safe_list(x: Any) -> List[str]:
    if x is None:
        return []
    if isinstance(x, list):
        return [str(i).strip() for i in x if str(i).strip()]
    if isinstance(x, str):
        return [s.strip() for s in x.splitlines() if s.strip()]
    s = str(x).strip()
    return [s] if s else []


def dedupe(items: List[str]) -> List[str]:
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


# -------------------------
# Schema checks
# -------------------------
@dataclass
class Issue:
    kind: str  # "error"|"warn"
    file: str
    message: str


def is_profile_file(path: Path) -> bool:
    # profile yaml at root OR ats_profiles/profiles/*.yaml (if you use that)
    return path.suffix.lower() == ".yaml" and path.name not in {
        Path(DEFAULT_CORE_LIB).name,
        Path(DEFAULT_DOMAINS_INDEX).name,
    } and "libraries" not in [p.name for p in path.parts]


def normalize_profile_min(profile: Dict[str, Any], pid_fallback: str) -> Dict[str, Any]:
    """
    Minimal migration (safe):
    - ensure id
    - ensure domain
    - keep bilingual dict fields as-is
    """
    p = dict(profile or {})
    pid = str(p.get("id") or pid_fallback or "").strip()
    if not pid:
        pid = slugify(pid_fallback or "profile")
    p["id"] = pid
    p["domain"] = str(p.get("domain") or pid).strip() or pid

    # optional: ensure containers are sane (do NOT destroy bilingual dicts)
    if "keywords" in p and p["keywords"] is None:
        p["keywords"] = {}
    if "job_titles" in p and not isinstance(p["job_titles"], (list, str, dict)):
        p["job_titles"] = safe_list(p["job_titles"])
    return p


def validate_profile_dict(p: Any, filename: str) -> List[Issue]:
    issues: List[Issue] = []
    if not isinstance(p, dict):
        issues.append(Issue("error", filename, "Profile YAML root must be a mapping/object"))
        return issues

    if not p.get("id"):
        issues.append(Issue("warn", filename, "Missing 'id' (recommended)."))
    if not p.get("title"):
        issues.append(Issue("warn", filename, "Missing 'title' (recommended)."))
    if not p.get("domain"):
        issues.append(Issue("warn", filename, "Missing 'domain' (recommended: enables domain libraries)."))

    # types sanity
    if "keywords" in p and not isinstance(p.get("keywords"), (dict, type(None))):
        issues.append(Issue("warn", filename, "'keywords' should be a mapping/object (or omitted)."))
    if "action_verbs" in p and not isinstance(p.get("action_verbs"), (list, str, dict, type(None))):
        issues.append(Issue("warn", filename, "'action_verbs' should be list / multiline string / {en,ro}."))
    if "metrics" in p and not isinstance(p.get("metrics"), (list, str, dict, type(None))):
        issues.append(Issue("warn", filename, "'metrics' should be list / multiline string / {en,ro}."))
    if "bullet_templates" in p and not isinstance(p.get("bullet_templates"), (list, str, dict, type(None))):
        issues.append(Issue("warn", filename, "'bullet_templates' should be list / multiline string / {en,ro}."))
    if "section_priority" in p and not isinstance(p.get("section_priority"), (list, str, dict, type(None))):
        issues.append(Issue("warn", filename, "'section_priority' should be list / multiline string / {en,ro}."))
    return issues


def validate_library_dict(lib: Any, filename: str) -> List[Issue]:
    issues: List[Issue] = []
    if lib is None:
        issues.append(Issue("warn", filename, "Missing library file."))
        return issues
    if not isinstance(lib, dict):
        issues.append(Issue("error", filename, "Library YAML root must be a mapping/object"))
        return issues

    # suggested keys
    for k in ("action_verbs", "metrics", "bullet_templates", "keywords"):
        if k in lib and lib[k] is None:
            issues.append(Issue("warn", filename, f"'{k}' is null (should be omitted or valid)."))

    # keywords shape
    kw = lib.get("keywords")
    if kw is not None and not isinstance(kw, dict):
        issues.append(Issue("warn", filename, "'keywords' should be a mapping/object."))
    return issues


def load_domains_index(root: Path) -> Tuple[Optional[Dict[str, Any]], List[Issue]]:
    idx_path = root / DEFAULT_DOMAINS_INDEX
    issues: List[Issue] = []
    raw = load_yaml(idx_path)
    if raw is None:
        issues.append(Issue("warn", str(idx_path), "domains_index.yaml missing (UI filter optional)."))
        return None, issues
    if not isinstance(raw, dict):
        issues.append(Issue("error", str(idx_path), "domains_index.yaml root must be a mapping/object."))
        return None, issues
    return raw, issues


def flatten_domains_index(idx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize to Schema A:
      { profiles:[{id,label,domain}], groups:[{id,label,profiles:[]}] , domains:[{id,library}] }
    Supports nested Schema B:
      groups:[{id,label,domains:[{id,label,library}]}]
    """
    if isinstance(idx.get("profiles"), list) and isinstance(idx.get("groups"), list):
        return idx

    groups_in = idx.get("groups") or []
    if not isinstance(groups_in, list):
        return {"profiles": [], "groups": [], "domains": []}

    profiles: List[Dict[str, Any]] = []
    groups: List[Dict[str, Any]] = []
    domains_map: Dict[str, str] = {}

    for g in groups_in:
        if not isinstance(g, dict):
            continue
        gid = str(g.get("id") or "").strip() or "group"
        glabel = g.get("label") or {"en": gid, "ro": gid}
        gdomains = g.get("domains") or []
        if not isinstance(gdomains, list):
            gdomains = []

        prof_ids: List[str] = []
        for d in gdomains:
            if not isinstance(d, dict):
                continue
            pid = str(d.get("id") or "").strip()
            if not pid:
                continue
            lbl = d.get("label") or {"en": pid, "ro": pid}
            lib = str(d.get("library") or "").strip()
            domain_id = Path(lib.replace("\\", "/")).stem if lib else pid
            if lib:
                domains_map[domain_id] = lib
            profiles.append({"id": pid, "label": lbl, "domain": domain_id})
            prof_ids.append(pid)

        groups.append({"id": gid, "label": glabel, "profiles": prof_ids})

    # dedupe profiles
    seen = set()
    prof_out = []
    for p in profiles:
        if p["id"] in seen:
            continue
        seen.add(p["id"])
        prof_out.append(p)

    domains = [{"id": did, "library": lpath} for did, lpath in sorted(domains_map.items())]
    return {"profiles": prof_out, "groups": groups, "domains": domains}


def validate_domains_index(idx: Dict[str, Any], root: Path) -> List[Issue]:
    issues: List[Issue] = []
    flat = flatten_domains_index(idx)

    groups = flat.get("groups", [])
    profiles = flat.get("profiles", [])
    domains = flat.get("domains", [])

    if not isinstance(groups, list) or not isinstance(profiles, list) or not isinstance(domains, list):
        issues.append(Issue("error", str(root / DEFAULT_DOMAINS_INDEX), "Invalid domains_index schema."))
        return issues

    # check referenced library files exist
    for d in domains:
        if not isinstance(d, dict):
            continue
        lib = str(d.get("library") or "").strip()
        if not lib:
            continue
        p = (root / lib).resolve()
        if not p.exists():
            issues.append(Issue("warn", str(root / DEFAULT_DOMAINS_INDEX), f"Missing domain library file: {lib}"))

    # check profiles listed exist as yaml in root
    prof_ids = {str(p.get("id")) for p in profiles if isinstance(p, dict) and p.get("id")}
    for pid in sorted([x for x in prof_ids if x]):
        f = root / f"{pid}.yaml"
        if not f.exists():
            issues.append(Issue("warn", str(root / DEFAULT_DOMAINS_INDEX), f"Profile listed but file missing: {pid}.yaml"))

    return issues


# -------------------------
# Commands
# -------------------------
def cmd_validate(root: Path) -> int:
    issues: List[Issue] = []

    # core library
    core_path = root / DEFAULT_CORE_LIB
    issues.extend(validate_library_dict(load_yaml(core_path), str(core_path)))

    # domain libs
    dom_dir = root / DEFAULT_DOMAIN_LIB_DIR
    if dom_dir.exists():
        for p in sorted(dom_dir.glob("*.yaml")):
            issues.extend(validate_library_dict(load_yaml(p), str(p)))
    else:
        issues.append(Issue("warn", str(dom_dir), "Domain libraries folder missing (libraries/domains)."))

    # profiles
    prof_files = sorted([p for p in root.glob("*.yaml") if is_profile_file(p)])
    if not prof_files:
        issues.append(Issue("warn", str(root), "No root profiles found (ats_profiles/*.yaml)."))

    for pf in prof_files:
        raw = load_yaml(pf)
        issues.extend(validate_profile_dict(raw, str(pf)))

        # extra check: domain library existence (recommended)
        if isinstance(raw, dict):
            domain_id = str(raw.get("domain") or raw.get("id") or pf.stem).strip()
            if domain_id:
                lib_path = (root / DEFAULT_DOMAIN_LIB_DIR / f"{domain_id}.yaml")
                if not lib_path.exists():
                    issues.append(Issue("warn", str(pf), f"Recommended domain library missing: {DEFAULT_DOMAIN_LIB_DIR}/{domain_id}.yaml"))

    # domains_index
    idx, idx_issues = load_domains_index(root)
    issues.extend(idx_issues)
    if isinstance(idx, dict):
        issues.extend(validate_domains_index(idx, root))

    # pretty report
    errors = [i for i in issues if i.kind == "error"]
    warns = [i for i in issues if i.kind == "warn"]

    if _RICH:
        if issues:
            tbl = Table(title="ATS Profiles Validation Report", show_lines=False)
            tbl.add_column("Type", style="bold")
            tbl.add_column("File")
            tbl.add_column("Message")
            for i in errors + warns:
                t = "[red]ERROR[/red]" if i.kind == "error" else "[yellow]WARN[/yellow]"
                tbl.add_row(t, i.file, i.message)
            console.print(tbl)
        else:
            console.print(Panel.fit("[green]All good — no issues found.[/green]"))
    else:
        for i in errors + warns:
            prefix = "ERROR" if i.kind == "error" else "WARN"
            print(f"{prefix}: {i.file} :: {i.message}")
        if not issues:
            print("All good — no issues found.")

    if errors:
        _err(f"{len(errors)} error(s), {len(warns)} warning(s)")
        return 2
    if warns:
        _warn(f"{len(warns)} warning(s)")
        return 1
    _ok("Validation passed.")
    return 0


def cmd_migrate(root: Path, write: bool) -> int:
    """
    Minimal migration:
    - Ensure each root profile has id/domain.
    - Ensure domains_index.yaml exists (optional) -> create basic one if missing.
    """
    changed: List[Path] = []
    issues: List[Issue] = []

    # migrate profiles
    prof_files = sorted([p for p in root.glob("*.yaml") if is_profile_file(p)])
    for pf in prof_files:
        raw = load_yaml(pf)
        if raw is None:
            issues.append(Issue("error", str(pf), "Empty/invalid YAML (None)."))
            continue
        if not isinstance(raw, dict):
            issues.append(Issue("error", str(pf), "Profile YAML root must be mapping/object."))
            continue

        before = dump_yaml(raw)
        norm = normalize_profile_min(raw, pid_fallback=pf.stem)
        after = dump_yaml(norm)

        if after != before:
            changed.append(pf)
            if write:
                write_yaml(pf, norm)

    # ensure domains_index
    idx_path = root / DEFAULT_DOMAINS_INDEX
    if not idx_path.exists():
        template = {
            "version": 1,
            "ui": {
                "title": {"en": "Domain Filter", "ro": "Filtru domenii"},
                "hint": {
                    "en": "Filter profiles by domain group (IT / Non-IT). Domains map to libraries/domains/*.yaml",
                    "ro": "Filtrează profilele după grup (IT / Non-IT). Domeniile mapate la libraries/domains/*.yaml",
                },
            },
            "groups": [
                {"id": "it", "label": {"en": "IT", "ro": "IT"}, "description": {"en": "", "ro": ""}, "domains": []},
                {"id": "non_it", "label": {"en": "Non-IT", "ro": "Non-IT"}, "description": {"en": "", "ro": ""}, "domains": []},
            ],
        }
        changed.append(idx_path)
        if write:
            write_yaml(idx_path, template)

    # report
    if _RICH:
        if changed:
            items = "\n".join(f"- {p}" for p in changed)
            console.print(Panel.fit(f"[cyan]Migration changes:[/cyan]\n{items}\n\nwrite={write}"))
        else:
            console.print(Panel.fit("[green]No migration changes needed.[/green]"))
    else:
        if changed:
            print("Migration changes:")
            for p in changed:
                print(f"- {p}")
            print(f"write={write}")
        else:
            print("No migration changes needed.")

    if issues:
        for i in issues:
            _err(f"{i.file}: {i.message}")
        return 2
    return 0


def cmd_generate(root: Path, domain_group: str, profile_id: str, title: str) -> int:
    """
    Generates:
      - ats_profiles/<profile_id>.yaml  (profile)
      - ats_profiles/libraries/domains/<domain_id>.yaml  (domain library)
      - updates domains_index.yaml (adds into group)
    """
    profile_id = slugify(profile_id)
    if not profile_id:
        _err("Invalid profile id.")
        return 2

    domain_id = profile_id  # simple: domain = profile id (you can change later)
    prof_path = root / f"{profile_id}.yaml"
    domlib_path = root / DEFAULT_DOMAIN_LIB_DIR / f"{domain_id}.yaml"
    idx_path = root / DEFAULT_DOMAINS_INDEX

    if prof_path.exists():
        _err(f"Profile already exists: {prof_path}")
        return 2

    # profile skeleton (bilingual title)
    prof = {
        "id": profile_id,
        "domain": domain_id,
        "title": {"en": title, "ro": title},
        "job_titles": {"en": [], "ro": []},
        "keywords": {
            "core": {"en": [], "ro": []},
            "technologies": {"en": [], "ro": []},
            "tools": {"en": [], "ro": []},
            "certifications": {"en": [], "ro": []},
            "frameworks": {"en": [], "ro": []},
            "soft_skills": {"en": [], "ro": []},
        },
        "action_verbs": {"en": [], "ro": []},
        "metrics": {"en": [], "ro": []},
        "bullet_templates": {"en": [], "ro": []},
        "section_priority": {"en": [], "ro": []},
        "ats_hint": {"en": "", "ro": ""},
        "notes": {"en": "", "ro": ""},
    }

    # domain library skeleton
    domlib = {
        "title": {"en": f"{title} Library", "ro": f"Librărie {title}"},
        "keywords": {
            "core": {"en": [], "ro": []},
            "technologies": {"en": [], "ro": []},
            "tools": {"en": [], "ro": []},
            "certifications": {"en": [], "ro": []},
            "frameworks": {"en": [], "ro": []},
            "soft_skills": {"en": [], "ro": []},
        },
        "action_verbs": {"en": [], "ro": []},
        "metrics": {"en": [], "ro": []},
        "bullet_templates": {"en": [], "ro": []},
        "section_priority": {"en": [], "ro": []},
    }

    write_yaml(prof_path, prof)
    write_yaml(domlib_path, domlib)

    # update domains_index
    idx = load_yaml(idx_path)
    if not isinstance(idx, dict):
        idx = {
            "version": 1,
            "groups": [],
        }
    groups = idx.get("groups")
    if not isinstance(groups, list):
        groups = []
        idx["groups"] = groups

    # find group
    grp = None
    for g in groups:
        if isinstance(g, dict) and str(g.get("id")) == domain_group:
            grp = g
            break
    if grp is None:
        grp = {"id": domain_group, "label": {"en": domain_group, "ro": domain_group}, "domains": []}
        groups.append(grp)

    doms = grp.get("domains")
    if not isinstance(doms, list):
        doms = []
        grp["domains"] = doms

    entry = {
        "id": profile_id,
        "label": {"en": title, "ro": title},
        "library": f"{DEFAULT_DOMAIN_LIB_DIR}/{domain_id}.yaml",
    }
    doms.append(entry)
    write_yaml(idx_path, idx)

    _ok(f"Generated profile: {prof_path}")
    _ok(f"Generated domain library: {domlib_path}")
    _ok(f"Updated domains index: {idx_path}")
    return 0


# -------------------------
# CLI
# -------------------------
def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="ats_profiles_tool", description="CVBuilder ATS Profiles Tool")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_val = sub.add_parser("validate", help="Validate profiles/libraries/domains_index.yaml")
    p_val.add_argument("--root", default="ats_profiles", help="ATS profiles root folder (default: ats_profiles)")

    p_mig = sub.add_parser("migrate", help="Minimal migration (ensure id/domain + create domains_index if missing)")
    p_mig.add_argument("--root", default="ats_profiles", help="ATS profiles root folder (default: ats_profiles)")
    p_mig.add_argument("--write", action="store_true", help="Actually write changes (otherwise dry-run)")

    p_gen = sub.add_parser("generate", help="Generate a new profile + domain library + update domains_index")
    p_gen.add_argument("--root", default="ats_profiles", help="ATS profiles root folder (default: ats_profiles)")
    p_gen.add_argument("--domain", default="it", help="domains_index group id (e.g., it / non_it)")
    p_gen.add_argument("--id", required=True, help="Profile id (slug will be used)")
    p_gen.add_argument("--title", required=True, help="Profile title (EN/RO label)")

    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    if not root.exists():
        _err(f"Root folder not found: {root}")
        return 2

    if args.cmd == "validate":
        return cmd_validate(root)
    if args.cmd == "migrate":
        return cmd_migrate(root, write=bool(args.write))
    if args.cmd == "generate":
        return cmd_generate(root, domain_group=str(args.domain), profile_id=str(args.id), title=str(args.title))

    _err("Unknown command.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
