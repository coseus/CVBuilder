from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

from utils.profiles import (
    ProfileError,
    load_profile,
    list_profiles,
    load_domains_index,
    flatten_domains_index,
    pick_lang,
)


def _label(val: Any, lang: str) -> str:
    s = str(pick_lang(val, lang) or "").strip()
    return s


def render_profile_manager(cv: Dict[str, Any], lang: str = "en") -> Optional[Dict[str, Any]]:
    """
    UI: Select / preview / edit ATS profile.
    - Lists profile stubs (*.yaml) and domain-only entries from domains_index.
    - Optional filter (IT / Non-IT etc.) driven by domains_index.yaml.
    - Updates cv["ats_profile"] with selected id.
    - Returns loaded merged profile dict.

    NOTE:
      load_profile() can also resolve "domain-only" ids by loading the domain library
      even if a profile yaml doesn't exist (prevents rerun loops).
    """
    if not isinstance(cv, dict):
        return None

    cv.setdefault("ats_profile", "cyber_security")

    idx = load_domains_index()
    flat = flatten_domains_index(idx)
    groups: List[Dict[str, Any]] = flat.get("groups", []) if isinstance(flat.get("groups"), list) else []
    domains: List[Dict[str, Any]] = flat.get("domains", []) if isinstance(flat.get("domains"), list) else []
    by_id: Dict[str, Any] = flat.get("by_id", {}) if isinstance(flat.get("by_id"), dict) else {}

    # --- Domain filter (optional) ---
    domain_filter_id = cv.get("ats_domain_filter", "all")
    allowed_ids: Optional[set[str]] = None

    if groups:
        options = ["all"] + [str(g.get("id")) for g in groups if str(g.get("id") or "").strip()]
        labels = {"all": "All"}
        for g in groups:
            gid = str(g.get("id") or "").strip()
            if not gid:
                continue
            labels[gid] = _label(g.get("label"), lang) or gid

        domain_filter_id = st.selectbox(
            "Domain filter",
            options=options,
            format_func=lambda k: labels.get(k, k),
            index=options.index(domain_filter_id) if domain_filter_id in options else 0,
            key="ats_domain_filter",
            help="Filters the profile list (IT / Non-IT etc.) if domains_index.yaml provides groups.",
        )
        cv["ats_domain_filter"] = domain_filter_id

        if domain_filter_id != "all":
            allowed_ids = {d.get("id") for d in domains if isinstance(d, dict) and d.get("group_id") == domain_filter_id}
            allowed_ids = {x for x in allowed_ids if isinstance(x, str) and x.strip()}

    # --- Profiles list ---
    profiles_list = list_profiles(lang=lang)

    # apply filter using domains_index mapping (if present)
    if allowed_ids is not None:
        profiles_list = [p for p in profiles_list if p.get("id") in allowed_ids]

    if not profiles_list:
        st.warning("No profiles found for this filter. Check domains_index.yaml and ats_profiles seeding.")
        return None

    id_to_title = {p["id"]: p["title"] for p in profiles_list}

    # if current selected profile isn't in filtered list -> move to first
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
        # clear cached things so dashboard refreshes
        cv.pop("ats_analysis", None)
        cv.pop("ats_score", None)
        st.rerun()

    # --- Load merged profile ---
    try:
        prof = load_profile(cv["ats_profile"], lang=lang)
    except ProfileError as e:
        st.error(str(e))
        return None

    # warnings
    warnings = prof.get("_warnings") or []
    if warnings:
        st.warning(" • ".join([str(w) for w in warnings][:6]))

    # pretty preview
    with st.expander("Profile preview (merged)", expanded=False):
        ui_title = _label(prof.get("title"), lang) or str(prof.get("id") or "")
        st.markdown(f"**{ui_title}**")
        st.caption(f"id: `{prof.get('id')}` • domain: `{prof.get('domain')}` • source: `{prof.get('_source_file','')}`")

        # show which group it belongs to (if indexed)
        meta = by_id.get(str(prof.get("id") or "")) or by_id.get(str(prof.get("domain") or "")) or {}
        if isinstance(meta, dict) and meta.get("group_id"):
            gid = str(meta.get("group_id"))
            glabel = next((_label(g.get("label"), lang) for g in groups if str(g.get("id")) == gid), gid)
            st.caption(f"Group: **{glabel}**")

        kw = prof.get("keywords") or {}
        if isinstance(kw, dict):
            st.markdown("**Keywords (top)**")
            chips: List[str] = []
            for bucket in ["core", "technologies", "tools", "certifications", "frameworks", "soft_skills"]:
                vals = kw.get(bucket) or []
                if isinstance(vals, list) and vals:
                    chips.extend(vals[:10])
            st.write(", ".join(chips[:50]) if chips else "—")

        cols = st.columns(3)
        cols[0].metric("Action verbs", len(prof.get("action_verbs") or []))
        cols[1].metric("Metrics", len(prof.get("metrics") or []))
        cols[2].metric("Templates", len(prof.get("bullet_templates") or []))

    return prof
