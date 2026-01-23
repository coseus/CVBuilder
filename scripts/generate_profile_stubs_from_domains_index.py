# scripts/generate_profile_stubs_from_domains_index.py
from __future__ import annotations

"""
Generate profile stub YAMLs (ats_profiles/profiles/*.yaml) from ats_profiles/domains_index.yaml.

Why:
- If your profiles are stubs (only id/domain), the merged title can become "Core Library".
- This generator writes stubs with proper bilingual titles and domain/library mappings.

Usage:
  python scripts/generate_profile_stubs_from_domains_index.py --ats-root ats_profiles

It will create/update:
  ats_profiles/profiles/<profile_id>.yaml
"""
import argparse
from pathlib import Path
import yaml


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ats-root", default="ats_profiles", help="Path to ats_profiles folder")
    args = ap.parse_args()

    ats_root = Path(args.ats_root)
    idx_path = ats_root / "domains_index.yaml"
    if not idx_path.exists():
        raise SystemExit(f"domains_index.yaml not found at: {idx_path}")

    idx = yaml.safe_load(idx_path.read_text(encoding="utf-8")) or {}
    if not isinstance(idx, dict):
        raise SystemExit("domains_index.yaml root must be a mapping")

    out_dir = ats_root / "profiles"
    out_dir.mkdir(parents=True, exist_ok=True)

    created = 0
    groups = idx.get("groups")
    if not isinstance(groups, list):
        raise SystemExit("Expected new schema: groups: [...]")

    for g in groups:
        if not isinstance(g, dict):
            continue
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
            # domain id defaults to pid, but you can override per profile
            domain = pid

            stub = {
                "id": pid,
                "domain": domain,
                "title": {
                    "en": (label.get("en") or pid.replace("_", " ").title()),
                    "ro": (label.get("ro") or label.get("en") or pid.replace("_", " ").title()),
                },
                "library": lib,  # informational; utils/profiles uses domains_index mapping anyway
                "job_titles": [],
                "keywords": {},
            }

            out_path = out_dir / f"{pid}.yaml"
            out_path.write_text(yaml.safe_dump(stub, sort_keys=False, allow_unicode=True), encoding="utf-8")
            created += 1

    print(f"Generated/updated {created} stubs in {out_dir}")


if __name__ == "__main__":
    main()
