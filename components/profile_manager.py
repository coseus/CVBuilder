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

    Uses:
      - utils.profiles.list_profiles(lang=...)
      - ats_profiles/domains_index.yaml (optional) via load_domains_index()
      - utils.profiles.flatten_domains_index(idx) which returns a dict:
          {
            "groups": [{"id","label","description","profiles":[profile_id,...]}, ...],
            "profiles": [{"id","label","group_id","library"}, ...]
          }

    Behavior:
      - Optional filter: All / IT / Non-IT (or whatever groups exist)
      - Updates cv["ats_profile"] with selected profile id
      - Returns loaded merged profile dict
    """
    if not isinstance(cv, dict):
        return None

    cv.setdefault("ats_profile", "cyber_security")

    # Load and flatten domain index (optional)
    idx = load_domains_index()
    flat = flatten_domains_index(idx)

    groups: List[Dict[str, Any]] = []
    if isinstance(flat, dict) and isinstance(flat.get("groups"), list):
        groups = [g for g in flat.get("groups") or [] if isinstance(g, dict) and g.get("id")]

    # Domain filter
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
            help="Filter profiles by domain group (IT / Non-IT) if domains_index.yaml exists.",
        )
        cv["ats_domain_filter"] = domain_filter_id

    allowed_ids: Optional[set[str]] = None
    if groups and domain_filter_id != "all":
        allowed_ids = set()
        # Prefer group->profiles mapping (more stable than per-domain items)
        for g in groups:
            if str(g.get("id")) == domain_filter_id:
                for pid in (g.get("profiles") or []):
                    if pid:
                        allowed_ids.add(str(pid))
                break

    # List profiles and apply filter
    profiles_list = list_profiles(lang=lang)
    if allowed_ids is not None:
        profiles_list = [p for p in profiles_list if p.get("id") in allowed_ids]

    if not profiles_list:
        st.warning("No profiles found for this filter. Check domains_index.yaml mapping and ats_profiles seeding.")
        return None

    id_to_title = {p["id"]: p["title"] for p in profiles_list}

    # Keep selection valid
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
        # clear cached analysis so UI refreshes
        cv.pop("ats_analysis", None)
        cv.pop("ats_score", None)
        st.rerun()

    try:
        prof = load_profile(cv["ats_profile"], lang=lang)
    except ProfileError as e:
        st.error(str(e))
        return None

    warnings = prof.get("_warnings") or []
    if warnings:
        st.warning(" • ".join([str(w) for w in warnings][:6]))

    with st.expander("Profile preview (merged)", expanded=False):
        st.write(
            {
                "id": prof.get("id"),
                "domain": prof.get("domain"),
                "title": _pick_lang(prof.get("title"), lang),
                "source": prof.get("_source_file"),
            }
        )
        kw = prof.get("keywords") or {}
        if isinstance(kw, dict):
            top: List[str] = []
            for bucket in ["core", "technologies", "tools", "certifications", "frameworks", "soft_skills"]:
                vals = kw.get(bucket) or []
                if isinstance(vals, list):
                    top.extend(vals[:8])
            st.caption("Keywords (top):")
            st.write(", ".join(top[:40]) if top else "—")

    return prof
