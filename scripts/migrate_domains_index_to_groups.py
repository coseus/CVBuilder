#!/usr/bin/env python3
"""
CVBuilder - domains_index.yaml migration: flat -> grouped (IT / Non-IT)

- Reads ./ats_profiles/domains_index.yaml
- If it already contains "groups:", it exits.
- Otherwise, it converts:
    domains: [{id,label,library}, ...]
  into:
    groups: [ {id:"it", ...}, {id:"non_it", ...} ]

Heuristic: you can tune IT_DOMAIN_IDS below.

Usage:
  python scripts/migrate_domains_index_to_groups.py
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

INDEX_PATH = Path("ats_profiles/domains_index.yaml")

IT_DOMAIN_IDS = {
    "cyber_security",
    "soc_analyst",
    "application_security_appsec",
    "cloud_security",
    "dfir_incident_response",
    "endpoint_security",
    "grc_compliance",
    "network_administrator",
    "system_administrator",
    "backup_disaster_recovery",
    "data_analyst",
}


def pick_lang(val: Any, lang: str) -> str:
    if isinstance(val, dict):
        if lang in val and val.get(lang):
            return str(val.get(lang))
        if "en" in val and val.get("en"):
            return str(val.get("en"))
        if "ro" in val and val.get("ro"):
            return str(val.get("ro"))
        for _, v in val.items():
            if v:
                return str(v)
    return str(val or "")


def main() -> None:
    if not INDEX_PATH.exists():
        raise SystemExit("No ats_profiles/domains_index.yaml found.")

    raw = yaml.safe_load(INDEX_PATH.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise SystemExit("domains_index.yaml must be a YAML mapping/object.")

    if isinstance(raw.get("groups"), list):
        print("Already grouped; nothing to do.")
        return

    domains = raw.get("domains") or []
    if not isinstance(domains, list):
        raise SystemExit("Expected flat schema: domains: [ ... ]")

    it_domains: List[Dict[str, Any]] = []
    non_it_domains: List[Dict[str, Any]] = []

    for d in domains:
        if not isinstance(d, dict) or not d.get("id"):
            continue
        did = str(d.get("id")).strip()
        if did in IT_DOMAIN_IDS:
            it_domains.append(d)
        else:
            non_it_domains.append(d)

    grouped = {
        "version": 3,
        "ui": raw.get("ui") or {},
        "groups": [
            {
                "id": "it",
                "label": {"en": "IT", "ro": "IT"},
                "description": {
                    "en": "Auto-migrated group (edit domains_index.yaml to refine).",
                    "ro": "Grup migrat automat (editează domains_index.yaml pentru ajustări).",
                },
                "domains": it_domains,
            },
            {
                "id": "non_it",
                "label": {"en": "Non-IT", "ro": "Non-IT"},
                "description": {
                    "en": "Auto-migrated group (edit domains_index.yaml to refine).",
                    "ro": "Grup migrat automat (editează domains_index.yaml pentru ajustări).",
                },
                "domains": non_it_domains,
            },
        ],
    }

    INDEX_PATH.write_text(yaml.safe_dump(grouped, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print("Migrated domains_index.yaml to grouped schema (version: 3).")


if __name__ == "__main__":
    main()
