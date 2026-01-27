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
    UI: Select / preview ATS profile (+ IT/Non-IT filter from domains_index.yaml).
    Updates cv["ats_profile"] and returns merged profile dict.
    """
    if not isinstance(cv, dict):
        return None

    cv.setdefault("ats_profile", "cyber_security")

    idx = load_domains_index()
    flat = flatten_domains_index(idx)

    # --- build groups map for filter UI ---
    group_labels: Dict[str, str] = {"all": "All"}
    groups = []
    if isinstance(idx, dict) and isinstance(idx.get("groups"), list):
        for g in idx.get("groups") or []:
            if isinstance(g, dict) and g.get("id"):
                gid = str(g.get("id")).strip()
                if gid:
                    groups.append(g)
                    group_labels[gid] = _pick_lang(g.get("label"), lang=lang) or gid

    # --- filter UI ---
    domain_filter_id = cv.get("ats_domain_filter", "all")
    if len(group_labels) > 1:
        keys = list(group_labels.keys())
        domain_filter_id = st.selectbox(
            "Domain filter",
            options=keys,
            format_func=lambda k: group_labels.get(k, k),
            index=keys.index(domain_filter_id) if domain_filter_id in keys else 0,
            key="ats_domain_filter",
            help="Filters profile list (IT / Non-IT) if domains_index.yaml provides groups.",
        )
        cv["ats_domain_filter"] = domain_filter_id
    else:
        domain_filter_id = "all"
        cv["ats_domain_filter"] = "all"

    # --- allowed ids from domains_index (this is where your error was) ---
    allowed_ids: Optional[set] = None
    if domain_filter_id != "all":
        allowed_ids = set()
        if isinstance(flat, list):
            for d in flat:
                # ✅ FIX: d may be str/None/etc
                if not isinstance(d, dict):
                    continue
                if d.get("group_id") == domain_filter_id:
                    did = (d.get("domain_id") or d.get("id") or "").strip()
                    if did:
                        allowed_ids.add(did)

    # --- list profiles (support both signatures) ---
    try:
        profiles_list = list_profiles(lang=lang)  # type: ignore
    except TypeError:
        profiles_list = list_profiles()

    if not isinstance(profiles_list, list):
        st.error("list_profiles() did not return a list.")
        return None

    if allowed_ids is not None and allowed_ids:
        filtered = [p for p in profiles_list if isinstance(p, dict) and p.get("id") in allowed_ids]
        if filtered:
            profiles_list = filtered
        else:
            st.warning(
                "No profiles found for this filter. "
                "Check domains_index.yaml: domains[].id must match profile filenames (ats_profiles/<id>.yaml). "
                "Showing all profiles."
            )

    if not profiles_list:
        st.warning("No profiles found. Check ats_profiles/ seeding or file names.")
        return None

    id_to_title = {}
    ids: List[str] = []
    for p in profiles_list:
        if not isinstance(p, dict):
            continue
        pid = str(p.get("id") or "").strip()
        if not pid:
            continue
        ids.append(pid)
        id_to_title[pid] = str(p.get("title") or pid)

    if not ids:
        st.warning("Profiles list is empty after normalization.")
        return None

    # keep selection stable
    if cv.get("ats_profile") not in id_to_title:
        cv["ats_profile"] = ids[0]

    selected_id = st.selectbox(
        "Select profile",
        options=ids,
        format_func=lambda pid: f"{id_to_title.get(pid, pid)} ({pid})",
        index=ids.index(cv["ats_profile"]) if cv["ats_profile"] in ids else 0,
        key="ats_profile_select",
    )

    if selected_id != cv.get("ats_profile"):
        cv["ats_profile"] = selected_id
        cv.pop("ats_analysis", None)
        cv.pop("ats_score", None)
        st.rerun()

    try:
        prof = load_profile(cv["ats_profile"], lang=lang)
    except ProfileError as e:
        st.error(str(e))
        return None
    except Exception as e:
        st.error(f"Failed to load profile: {e}")
        return None

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

    return prof
