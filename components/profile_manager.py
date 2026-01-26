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
    UI: Select / preview ATS profile + optional IT/Non-IT filter via domains_index.yaml.
    Updates cv["ats_profile"] and returns loaded merged profile dict.
    """
    if not isinstance(cv, dict):
        return None

    cv.setdefault("ats_profile", "cyber_security")

    idx = load_domains_index()
    flat = flatten_domains_index(idx)  # list of rows with keys: group_id, domain_id, group_label, domain_label, library...

    # Build groups list for filter UI
    group_labels: Dict[str, str] = {"all": "All"}
    if isinstance(idx, dict) and isinstance(idx.get("groups"), list):
        for g in idx.get("groups") or []:
            if isinstance(g, dict) and g.get("id"):
                gid = str(g.get("id")).strip()
                if not gid:
                    continue
                group_labels[gid] = _pick_lang(g.get("label"), lang=lang) or gid

    # Domain filter UI (only if we actually have groups)
    domain_filter_id = cv.get("ats_domain_filter", "all")
    if len(group_labels) > 1:
        keys = list(group_labels.keys())
        domain_filter_id = st.selectbox(
            "Domain filter",
            options=keys,
            format_func=lambda k: group_labels.get(k, k),
            index=keys.index(domain_filter_id) if domain_filter_id in keys else 0,
            key="ats_domain_filter",
            help="Filters the profile list (IT / Non-IT etc.) if domains_index.yaml provides groups.",
        )
        cv["ats_domain_filter"] = domain_filter_id
    else:
        # no index/groups -> behave like "all"
        domain_filter_id = "all"
        cv["ats_domain_filter"] = "all"

    # Build allowed ids when filtered
    allowed_ids: Optional[set] = None
    if domain_filter_id != "all" and flat:
        allowed_ids = set()
        for row in flat:
            if not isinstance(row, dict):
                continue
            if row.get("group_id") == domain_filter_id:
                # ✅ IMPORTANT: use domain_id (not id)
                did = (row.get("domain_id") or "").strip()
                if did:
                    allowed_ids.add(did)

    # List profiles (safe call if list_profiles doesn't accept lang)
    try:
        profiles_list = list_profiles(lang=lang)  # type: ignore[arg-type]
    except TypeError:
        profiles_list = list_profiles()

    if allowed_ids is not None:
        profiles_filtered = [p for p in profiles_list if p.get("id") in allowed_ids]

        # Fallback if filter yields nothing -> show all and warn
        if not profiles_filtered:
            st.warning(
                "No profiles found for this filter. "
                "Check domains_index.yaml: domains[].id must match profile filenames (ats_profiles/<id>.yaml). "
                "Showing all profiles."
            )
        else:
            profiles_list = profiles_filtered

    if not profiles_list:
        st.warning("No profiles found. Check ats_profiles/ seeding or file names.")
        return None

    id_to_title = {p["id"]: p.get("title", p["id"]) for p in profiles_list if isinstance(p, dict) and p.get("id")}

    # Keep selection stable
    if cv.get("ats_profile") not in id_to_title:
        cv["ats_profile"] = profiles_list[0]["id"]

    ids = [p["id"] for p in profiles_list]
    selected_id = st.selectbox(
        "Select profile",
        options=ids,
        format_func=lambda pid: f"{id_to_title.get(pid, pid)} ({pid})",
        index=ids.index(cv["ats_profile"]) if cv["ats_profile"] in ids else 0,
        key="ats_profile_select",
    )

    if selected_id != cv.get("ats_profile"):
        cv["ats_profile"] = selected_id
        # Clear cached analysis so UI updates immediately
        cv.pop("ats_analysis", None)
        cv.pop("ats_score", None)
        st.rerun()

    # Load merged profile
    try:
        prof = load_profile(cv["ats_profile"], lang=lang)
    except ProfileError as e:
        st.error(str(e))
        return None
    except Exception as e:
        st.error(f"Failed to load profile: {e}")
        return None

    # Warnings
    warnings = prof.get("_warnings") or []
    if isinstance(warnings, list) and warnings:
        st.warning(" • ".join([str(w) for w in warnings][:5]))

    with st.expander("Profile preview (merged)", expanded=False):
        st.write(
            {
                "id": prof.get("id"),
                "domain": prof.get("domain"),
                "title": _pick_lang(prof.get("title"), lang),
                "source": prof.get("_source_file", ""),
            }
        )
        st.caption("Keywords (top):")
        kw = prof.get("keywords") or {}
        if isinstance(kw, dict):
            top: List[str] = []
            for bucket in ["core", "technologies", "tools", "certifications", "frameworks", "soft_skills"]:
                vals = kw.get(bucket) or []
                if isinstance(vals, list):
                    top.extend([str(x) for x in vals[:8]])
            st.write(", ".join(top[:40]) if top else "—")

    return prof
