from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

from utils.profiles import (
    ProfileError,
    load_profile,
    list_profiles,
    load_domains_index,
    flatten_domains_index,
)


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
    return str(val or "")


def render_profile_manager(cv: Dict[str, Any], lang: str = "en") -> Optional[Dict[str, Any]]:
    """
    UI: Select / preview / edit ATS profile.
    - Reads available profiles from utils.profiles.list_profiles()
    - Uses domains_index.yaml (grouped or flat) to offer an "IT / Non-IT" filter if present.
    - Updates cv["ats_profile"] with selected id.
    - Returns loaded (merged) profile dict.
    """
    if not isinstance(cv, dict):
        return None

    # Ensure default
    cv.setdefault("ats_profile", "cyber_security")

    idx = load_domains_index()
    domains = flatten_domains_index(idx)

    # Build groups (optional)
    groups: List[Dict[str, Any]] = []
    if isinstance(idx.get("groups"), list):
        for g in idx.get("groups") or []:
            if isinstance(g, dict) and g.get("id"):
                groups.append(g)

    # Domain filter UI
    domain_filter_id = cv.get("ats_domain_filter", "all")
    if groups:
        group_labels = {"all": "All"}
        for g in groups:
            gid = str(g.get("id"))
            group_labels[gid] = _pick_lang(g.get("label"), lang=lang) or gid

        domain_filter_id = st.selectbox(
            "Domain filter",
            options=list(group_labels.keys()),
            format_func=lambda k: group_labels.get(k, k),
            index=list(group_labels.keys()).index(domain_filter_id) if domain_filter_id in group_labels else 0,
            key="ats_domain_filter",
            help="Filters the profile list (IT / Non-IT etc.) if domains_index.yaml provides groups.",
        )
        cv["ats_domain_filter"] = domain_filter_id

    # Build allowed ids if filtered
    allowed_ids = None
    if groups and domain_filter_id != "all":
        allowed_ids = set()
        for d in domains:
            if d.get("group_id") == domain_filter_id:
                allowed_ids.add(d.get("id"))

    # List profiles (titles are already localized/friendly)
    profiles_list = list_profiles(lang=lang)
    if allowed_ids is not None:
        profiles_list = [p for p in profiles_list if p.get("id") in allowed_ids]

    if not profiles_list:
        st.warning("No profiles found for this filter. Check ats_profiles/ seeding or domains_index.yaml.")
        return None

    id_to_title = {p["id"]: p["title"] for p in profiles_list}

    # Keep selection stable
    if cv.get("ats_profile") not in id_to_title:
        cv["ats_profile"] = profiles_list[0]["id"]

    selected_id = st.selectbox(
        "Select profile",
        options=[p["id"] for p in profiles_list],
        format_func=lambda pid: f"{id_to_title.get(pid, pid)} ({pid})",
        index=[p["id"] for p in profiles_list].index(cv["ats_profile"]),
        key="ats_profile_select",
    )
    if selected_id != cv.get("ats_profile"):
        cv["ats_profile"] = selected_id
        # Clear cached analysis so UI updates immediately
        cv.pop("ats_analysis", None)
        cv.pop("ats_score", None)
        st.rerun()

    # Load profile merged with libraries
    try:
        prof = load_profile(cv["ats_profile"], lang=lang)
    except ProfileError as e:
        st.error(str(e))
        return None

    # Preview + warnings
    warnings = prof.get("_warnings") or []
    if warnings:
        st.warning(" • ".join([str(w) for w in warnings][:5]))

    with st.expander("Profile preview (merged)", expanded=False):
        st.write({"id": prof.get("id"), "domain": prof.get("domain"), "title": _pick_lang(prof.get("title"), lang)})
        st.caption("Keywords (top):")
        kw = prof.get("keywords") or {}
        if isinstance(kw, dict):
            top = []
            for bucket in ["core", "technologies", "tools", "certifications", "frameworks", "soft_skills"]:
                vals = kw.get(bucket) or []
                if isinstance(vals, list):
                    top.extend(vals[:8])
            st.write(", ".join(top[:40]) if top else "—")

    return prof
