# tools/generate_domains_index.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import re
import yaml

ROOT = Path("ats_profiles")
DOMAINS_DIR = ROOT / "libraries" / "domains"
OUT = ROOT / "domains_index.yaml"


IT_HINTS = {
    "cyber", "security", "soc", "dfir", "grc", "appsec", "iam", "identity",
    "network", "system", "cloud", "devops", "sre", "platform", "observability",
    "backup", "disaster", "endpoint", "infra", "architecture", "finops",
    "database", "data_engineer", "analytics_engineer",
}

NON_IT_HINTS = {
    "accounting", "finance", "hr", "recruit", "marketing", "sales",
    "customer_support", "operations", "supply_chain", "administrative_assistant",
    "project_management", "project_manager",
}


def _pick_lang(val: Any, lang: str) -> str:
    if isinstance(val, dict):
        if val.get(lang):
            return str(val.get(lang))
        if val.get("en"):
            return str(val.get("en"))
        if val.get("ro"):
            return str(val.get("ro"))
        for _, v in val.items():
            if v:
                return str(v)
    return "" if val is None else str(val)


def _title_case_id(s: str) -> str:
    s = s.replace("_", " ").strip()
    return re.sub(r"\s+", " ", s).title()


def _guess_group(domain_id: str) -> str:
    d = domain_id.lower()
    if any(h in d for h in NON_IT_HINTS):
        return "non_it"
    if any(h in d for h in IT_HINTS):
        return "it"
    # fallback: common IT-ish tokens
    if any(x in d for x in ["it", "tech", "security", "cloud", "network", "system"]):
        return "it"
    return "non_it"


def main() -> None:
    if not DOMAINS_DIR.exists():
        raise SystemExit(f"Missing folder: {DOMAINS_DIR}")

    it_domains: List[Dict[str, Any]] = []
    non_it_domains: List[Dict[str, Any]] = []

    for p in sorted(DOMAINS_DIR.glob("*.yaml")):
        domain_id = p.stem
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            continue

        title = raw.get("title")
        label_en = _pick_lang(title, "en").strip() or _title_case_id(domain_id)
        label_ro = _pick_lang(title, "ro").strip() or label_en

        entry = {
            "id": domain_id,
            "label": {"en": label_en, "ro": label_ro},
        }

        group = _guess_group(domain_id)
        if group == "it":
            it_domains.append(entry)
        else:
            non_it_domains.append(entry)

    out = {
        "version": 1,
        "groups": [
            {"id": "it", "label": {"en": "IT", "ro": "IT"}, "domains": it_domains},
            {"id": "non_it", "label": {"en": "Non-IT", "ro": "Non-IT"}, "domains": non_it_domains},
        ],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(yaml.safe_dump(out, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"✅ Wrote {OUT} (IT: {len(it_domains)}, Non-IT: {len(non_it_domains)})")


if __name__ == "__main__":
    main()
