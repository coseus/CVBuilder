# components/profile_manager.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st
import yaml

from utils.profiles import list_profiles, load_profile, save_profile_text, ProfileError


def _pick_lang(val: Any, lang: str = "en") -> str:
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
    return "" if val is None else str(val)


def _load_domains_index() -> Dict[str, Any]:
    path = Path("ats_profiles") / "domains_index.yaml"
    if not path.exists():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _domain_group_for(domain_id: str, domains_index: Dict[str, Any]) -> Optional[str]:
    groups = domains_index.get("groups", [])
    if not isinstance(groups, list):
        return None
    for g in groups:
        if not isinstance(g, dict):
            continue
        gid = str(g.get("id", "")).lower()  # it / non_it
        doms = g.get("domains", [])
        if not isinstance(doms, list):
            continue
        for d in doms:
            if isinstance(d, dict) and str(d.get("id", "")).strip() == domain_id:
                return gid
    return None


def render_profile_manager(cv: dict) -> Optional[Dict[str, Any]]:
    """
    UI: select ATS profile + preview/edit raw YAML.
    Adds filter: IT / Non-IT (based on ats_profiles/domains_index.yaml).
    Returns loaded profile dict (or None).
    """
    lang = cv.get("jd_lang") or cv.get("lang") or "en"
    lang = "ro" if str(lang).lower().startswith("ro") else "en"

    domains_index = _load_domains_index()

    # --- Filter (IT / Non-IT) ---
    filter_options = ["All", "IT", "Non-IT"]
    default_filter = cv.get("profile_filter", "All")
    if default_filter not in filter_options:
        default_filter = "All"

    colf1, colf2 = st.columns([1, 2], gap="small")
    with colf1:
        chosen_filter = st.selectbox(
            "Filter",
            filter_options,
            index=filter_options.index(default_filter),
            key="profile_filter_select",
        )
        cv["profile_filter"] = chosen_filter

    # --- Load profiles ---
    profiles = list_profiles()  # [{id, filename, title}]
    enriched: List[Dict[str, str]] = []

    for p in profiles:
        pid = p.get("id", "")
        title = p.get("title", pid)
        domain = pid
        try:
            prof = load_profile(pid, lang=lang)
            domain = str(prof.get("domain") or pid).strip() or pid
            title = _pick_lang(prof.get("title"), lang=lang) or title
        except Exception:
            pass

        group = _domain_group_for(domain, domains_index) or ""
        enriched.append({"id": pid, "title": title, "domain": domain, "group": group})

    if chosen_filter == "IT":
        enriched = [x for x in enriched if x.get("group") == "it"]
    elif chosen_filter == "Non-IT":
        enriched = [x for x in enriched if x.get("group") == "non_it"]

    enriched = sorted(enriched, key=lambda x: (x.get("title") or "").lower())

    if not enriched:
        st.warning("No profiles found for this filter.")
        return None

    current_pid = cv.get("ats_profile", "cyber_security")
    ids = [x["id"] for x in enriched]
    if current_pid not in ids:
        current_pid = ids[0]
        cv["ats_profile"] = current_pid

    labels = [f"{x['title']} ({x['id']})" for x in enriched]
    idx = ids.index(current_pid)

    selected_label = st.selectbox("ATS Profile", labels, index=idx, key="ats_profile_selectbox")
    selected_id = ids[labels.index(selected_label)]
    cv["ats_profile"] = selected_id

    # Load selected profile (merged libraries)
    try:
        profile = load_profile(selected_id, lang=lang)
    except ProfileError as e:
        st.error(str(e))
        return None
    except Exception:
        profile = None

    if not isinstance(profile, dict):
        return None

    # Preview
    with st.expander("Preview (merged)", expanded=False):
        st.json({k: v for k, v in profile.items() if not str(k).startswith("_")})

    # Raw editor (save back)
    with st.expander("Edit YAML (raw)", expanded=False):
        # IMPORTANT: save_profile_text expects raw YAML; we keep a simple editor.
        # We'll fetch current raw by dumping the profile WITHOUT internal fields.
        clean = {k: v for k, v in profile.items() if not str(k).startswith("_")}
        raw_yaml = yaml.safe_dump(clean, sort_keys=False, allow_unicode=True)

        new_yaml = st.text_area(
            "Profile YAML",
            value=raw_yaml,
            height=300,
            key=f"profile_yaml_editor_{selected_id}",
        )

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Save profile", type="primary", use_container_width=True, key=f"profile_save_{selected_id}"):
                try:
                    save_profile_text(selected_id, new_yaml)
                    st.success("Saved.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Save failed: {e}")

        with c2:
            if st.button("Reload", use_container_width=True, key=f"profile_reload_{selected_id}"):
                st.rerun()

    return profile
