# scripts/migrate_domains_index_old_to_new.py
from __future__ import annotations

"""
Migrate old domains_index.yaml schema (profiles: [...]) to new grouped schema (groups: [...]).

Usage:
  python scripts/migrate_domains_index_old_to_new.py --in ats_profiles/domains_index.yaml --out ats_profiles/domains_index.yaml
"""
import argparse
from collections import defaultdict
from pathlib import Path
import yaml


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="outp", required=True)
    args = ap.parse_args()

    inp = Path(args.inp)
    outp = Path(args.outp)

    data = yaml.safe_load(inp.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit("Input YAML root must be a mapping")

    if isinstance(data.get("groups"), list):
        print("Already new schema. Nothing to do.")
        outp.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return

    profs = data.get("profiles")
    if not isinstance(profs, list):
        raise SystemExit("Expected old schema with 'profiles: [...]'")

    grouped = defaultdict(list)
    ui = data.get("ui") if isinstance(data.get("ui"), dict) else {}

    for p in profs:
        if not isinstance(p, dict):
            continue
        gid = str(p.get("group") or p.get("group_id") or "other").strip() or "other"
        grouped[gid].append({
            "id": p.get("id"),
            "label": p.get("label") if isinstance(p.get("label"), dict) else {},
            "library": p.get("library"),
        })

    out = {
        "version": 1,
        "ui": ui or {
            "title": {"en": "Domain Filter", "ro": "Filtru domenii"},
            "hint": {"en": "Filter profiles by domain", "ro": "Filtrează profilele după domeniu"},
        },
        "groups": []
    }

    for gid, items in grouped.items():
        out["groups"].append({
            "id": gid,
            "label": {"en": gid.upper(), "ro": gid.upper()},
            "domains": items,
        })

    outp.write_text(yaml.safe_dump(out, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"Wrote new schema to: {outp}")


if __name__ == "__main__":
    main()
