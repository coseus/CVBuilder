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
        gid = g.get("id")
        doms = g.get("domains", [])
        if not isinstance(doms, list):
            continue
        for d in doms:
            if isinstance(d, dict) and d.get("id") == domain_id:
                return str(gid)
    return None


def render_profile_manager(cv: dict) -> Optional[Dict[str, Any]]:
    """
    Select ATS profile + preview/edit.
    Adds filter IT/Non-IT based on ats_profiles/domains_index.yaml.
    Returns loaded merged profile (core+domain+profile).
    """
    lang = cv.get("jd_lang") or cv.get("lang") or "en"
    lang = "ro" if str(lang).lower().startswith("ro") else "en"

    domains_index = _load_domains_index()

    filter_options = ["All", "IT", "Non-IT"]
    default_filter = cv.get("profile_filter", "All")
    if default_filter not in filter_options:
        default_filter = "All"

    chosen_filter = st.selectbox(
        "Filter",
        filter_options,
        index=filter_options.index(default_filter),
        key="profile_filter_select",
    )
    cv["profile_filter"] = chosen_filter

    profiles = list_profiles()  # [{id, filename, title}]
    enriched: List[Dict[str, str]] = []

    for p in profiles:
        pid = p.get("id", "")
        title = p.get("title", pid)

        # best-effort: domain == id if unknown
        domain = pid
        group = _domain_group_for(domain, domains_index)

        enriched.append({
            "id": pid,
            "title": title,
            "domain": domain,
            "group": group or "",
        })

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

    labels = []
    for x in enriched:
        dom = x.get("domain") or x["id"]
        labels.append(f"{x.get('title') or x['id']} ({x['id']}) — {dom}")

    idx = ids.index(current_pid)
    selected_label = st.selectbox("ATS Profile", labels, index=idx, key="ats_profile_selectbox")
    selected_id = ids[labels.index(selected_label)]
    cv["ats_profile"] = selected_id

    try:
        prof = load_profile(selected_id, lang=lang)
    except ProfileError as e:
        st.error(str(e))
        return None

    warns = prof.get("_warnings") or []
    if warns:
        with st.expander("Profile warnings", expanded=False):
            for w in warns:
                st.warning(w)

    with st.expander("Preview / Edit YAML", expanded=False):
        st.caption("Editing saves only the profile YAML (not the libraries). Libraries are auto-merged at load.")
        try:
            raw_yaml = yaml.safe_dump(
                {k: v for k, v in prof.items() if not str(k).startswith("_")},
                sort_keys=False,
                allow_unicode=True,
            )
        except Exception:
            raw_yaml = ""

        new_yaml = st.text_area("Profile YAML", value=raw_yaml, height=360, key=f"yaml_edit_{selected_id}")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Save profile YAML", key=f"btn_save_profile_{selected_id}"):
                try:
                    save_profile_text(selected_id, new_yaml)
                    st.success("Saved.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Save failed: {e}")
        with c2:
            st.caption("Tip: include `domain:` ca să folosească libraries/domains/<domain>.yaml")

    return prof
