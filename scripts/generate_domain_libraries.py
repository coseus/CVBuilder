#!/usr/bin/env python3
"""
CVBuilder - ATS domain libraries generator

What it does (safe):
- Scans ./ats_profiles/*.yaml (root profiles)
- For each profile_id, creates ./ats_profiles/libraries/domains/<domain_id>.yaml IF missing.
- Extracts ONLY reusable parts:
    keywords, action_verbs, metrics, bullet_templates, section_priority, job_titles, ats_hint, notes
- Keeps EN/RO bilingual dicts as-is.
- Does NOT overwrite existing domain libraries.

Usage:
  python scripts/generate_domain_libraries.py
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

ROOT = Path("ats_profiles")
DOMAINS_DIR = ROOT / "libraries" / "domains"


KEEP_KEYS = {
    "title",
    "job_titles",
    "keywords",
    "action_verbs",
    "metrics",
    "bullet_templates",
    "section_priority",
    "ats_hint",
    "notes",
}


def load_yaml(p: Path) -> Dict[str, Any]:
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return {}
    return raw


def dump_yaml(obj: Dict[str, Any], p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(obj, sort_keys=False, allow_unicode=True), encoding="utf-8")


def main() -> None:
    if not ROOT.exists():
        raise SystemExit("No ats_profiles/ folder found.")

    DOMAINS_DIR.mkdir(parents=True, exist_ok=True)

    created = 0
    for prof_path in sorted(ROOT.glob("*.yaml")):
        if prof_path.name in ("domains_index.yaml",):
            continue

        prof = load_yaml(prof_path)
        pid = (prof.get("id") or prof_path.stem).strip()
        domain_id = (prof.get("domain") or pid).strip()

        out_path = DOMAINS_DIR / f"{domain_id}.yaml"
        if out_path.exists():
            continue

        lib: Dict[str, Any] = {"id": domain_id}

        for k in KEEP_KEYS:
            if k in prof:
                lib[k] = prof.get(k)

        # Avoid misleading title defaults
        if "title" in lib and not lib["title"]:
            lib.pop("title", None)

        dump_yaml(lib, out_path)
        created += 1
        print(f"Created domain library: {out_path}")

    print(f"Done. Created {created} domain libraries.")


if __name__ == "__main__":
    main()
