from __future__ import annotations

import os
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
    """
    Reads ats_profiles/domains_index.yaml (repo path).
    If missing, returns {} and UI will fallback gracefully.
    """
    path = Path("ats_profiles") / "domains_index.yaml"
    if not path.exists():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _domain_group_for(domain_id: str, domains_index: Dict[str, Any]) -> Optional[str]:
    """
    Returns group id: 'it' or 'non_it' if found in index.
    """
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
    UI: select ATS profile + optional preview/edit.
    Adds filter: IT / Non-IT (based on ats_profiles/domains_index.yaml).

    Returns loaded profile dict (or None if not loaded).
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

    # --- Load available profiles (seeded) ---
    profiles = list_profiles()  # [{id, filename, title}]
    # We will augment with domain info (best effort) so we can filter.
    enriched: List[Dict[str, str]] = []

    for p in profiles:
        pid = p.get("id", "")
        title = p.get("title", pid)
        domain = ""

        # Best-effort: read profile domain without fully loading/merging libraries
        # (safe + fast)
        try:
            # Try load to get domain/title merged properly if possible
            prof = load_profile(pid, lang=lang)
            domain = str(prof.get("domain") or pid)
            # Prefer bilingual title if present
            title = _pick_lang(prof.get("title"), lang=lang) or title
        except Exception:
            domain = pid

        group = _domain_group_for(domain, domains_index)
        enriched.append({
            "id": pid,
            "title": title,
            "domain": domain,
            "group": group or "",  # it / non_it / ""
        })

    # Apply filter
    if chosen_filter == "IT":
        enriched = [x for x in enriched if x.get("group") == "it"]
    elif chosen_filter == "Non-IT":
        enriched = [x for x in enriched if x.get("group") == "non_it"]

    # Sort alphabetic by displayed title
    enriched = sorted(enriched, key=lambda x: (x.get("title") or "").lower())

    # Build select choices
    if not enriched:
        st.warning("No profiles found for this filter.")
        return None

    # Current selection
    current_pid = cv.get("ats_profile", "cyber_security")
    ids = [x["id"] for x in enriched]
    if current_pid not in ids:
        current_pid = ids[0]
        cv["ats_profile"] = current_pid

    # Display label: "Title (id) — domain"
    labels = []
    for x in enriched:
        dom = x.get("domain") or x["id"]
        labels.append(f"{x.get('title') or x['id']} ({x['id']}) — {dom}")

    idx = ids.index(current_pid)

    selected_label = st.selectbox(
        "ATS Profile",
        labels,
        index=idx,
        key="ats_profile_selectbox",
    )
    selected_id = ids[labels.index(selected_label)]
    cv["ats_profile"] = selected_id

    # Load selected profile (full merged core+domain+profile)
    try:
        prof = load_profile(selected_id, lang=lang)
    except ProfileError as e:
        st.error(str(e))
        return None

    # Warnings (non-fatal)
    warns = prof.get("_warnings") or []
    if warns:
        with st.expander("Profile warnings", expanded=False):
            for w in warns:
                st.warning(w)

    # Preview/edit raw YAML (optional)
    with st.expander("Preview / Edit YAML", expanded=False):
        # Show merged profile (read-only) AND allow editing the profile file itself
        st.caption("Editing saves only the profile YAML (not the libraries). Libraries are auto-merged at load.")
        # Load raw profile yaml from user folder path (display/edit)
        # We'll reuse utils.profiles.save_profile_text to save safely.
        try:
            # the saved file is in user data dir, but save_profile_text knows the correct path
            raw_yaml = yaml.safe_dump(
                {k: v for k, v in prof.items() if not str(k).startswith("_")},
                sort_keys=False,
                allow_unicode=True,
            )
        except Exception:
            raw_yaml = ""

        new_yaml = st.text_area("Profile YAML", value=raw_yaml, height=360, key=f"yaml_edit_{selected_id}")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Save profile YAML", key=f"btn_save_profile_{selected_id}"):
                try:
                    save_profile_text(selected_id, new_yaml)
                    st.success("Saved.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Save failed: {e}")
        with col2:
            st.caption("Tip: keep `domain:` set to match a file in libraries/domains/.")

    return prof
