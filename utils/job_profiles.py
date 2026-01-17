import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional

JOB_PROFILES_DIR = "job_profiles"


def _ensure_dir():
    os.makedirs(JOB_PROFILES_DIR, exist_ok=True)


def _slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9\-_\s]+", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s[:80] if s else "job"


def list_job_profiles() -> List[Dict]:
    _ensure_dir()
    items = []
    for fn in sorted(os.listdir(JOB_PROFILES_DIR)):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(JOB_PROFILES_DIR, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["_file"] = fn
            items.append(data)
        except Exception:
            continue
    # sort by saved_at desc if present
    def key(x):
        return x.get("saved_at", "")
    items.sort(key=key, reverse=True)
    return items


def save_job_profile(profile: Dict, name: str) -> str:
    _ensure_dir()
    slug = _slugify(name)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    fn = f"{ts}__{slug}.json"
    path = os.path.join(JOB_PROFILES_DIR, fn)

    payload = dict(profile or {})
    payload["name"] = name
    payload["saved_at"] = datetime.now().isoformat(timespec="seconds")
    payload["_version"] = 1

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return fn


def load_job_profile(filename: str) -> Optional[Dict]:
    if not filename:
        return None
    _ensure_dir()
    path = os.path.join(JOB_PROFILES_DIR, filename)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def delete_job_profile(filename: str) -> bool:
    if not filename:
        return False
    _ensure_dir()
    path = os.path.join(JOB_PROFILES_DIR, filename)
    if not os.path.isfile(path):
        return False
    try:
        os.remove(path)
        return True
    except Exception:
        return False
