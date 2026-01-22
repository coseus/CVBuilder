# components/profile_manager.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

from utils.profiles import (
    ProfileError,
    load_profile,
    load_domains_index,
    index_profile_label,
)


def _pick_lang_from_ui() -> str:
    # prefer JD detected language if present, else EN
    # you can change to cv.get("lang") if you store it
    return st.session_state.get("export_lang", "en")


def render_profile_manager(cv: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Profile selector driven ONLY by domains_index.yaml (best practice).
    Saves selection into cv["ats_profile"].
    Returns loaded profile dict (merged libraries + normalized) or None.
    """
    lang = cv.get("jd_lang") or _pick_lang_from_ui() or "en"
    idx = load_domains_index()

    # Fallback: if index missing, keep current behavior minimal
    profiles_index = idx.get("profiles", [])
    groups_index = idx.get("groups", [])

    if not isinstance(profiles_index, list) or not profiles_index:
        st.warning("domains_index.yaml not found or empty. Please ensure ats_profiles/domains_index.yaml exists.")
        pid = cv.get("ats_profile", "cyber_security")
        try:
            p = load_profile(pid, lang=lang)
            return p
        except Exception:
            return None

    # Build group options
    group_options = [("all", "All / Toate")]
    if isinstance(groups_index, list):
        for g in groups_index:
            if not isinstance(g, dict):
                continue
            gid = (g.get("id") or "").strip()
            glabel = g.get("label")
            name = (glabel.get(lang) if isinstance(glabel, dict) else None) or gid
            if gid:
                group_options.append((gid, str(name)))

    # UI controls
    colA, colB = st.columns([1, 1], gap="small")
    with colA:
        group_id = st.selectbox(
            "Domain group",
            options=group_options,
            format_func=lambda x: x[1],
            key="ui_domain_group",
        )[0]
    with colB:
        q = st.text_input("Search profile", value="", key="ui_profile_search", placeholder="e.g. SOC, Accountant...").strip().lower()

    # Determine allowed profile ids by group
    allowed_ids = None
    if group_id != "all" and isinstance(groups_index, list):
        for g in groups_index:
            if isinstance(g, dict) and (g.get("id") or "").strip() == group_id:
                ids = g.get("profiles", [])
                if isinstance(ids, list):
                    allowed_ids = set([str(x).strip() for x in ids if str(x).strip()])
                break

    # Build selectable profiles list
    options: List[Dict[str, str]] = []
    for it in profiles_index:
        if not isinstance(it, dict):
            continue
        pid = (it.get("id") or "").strip()
        if not pid:
            continue
        if allowed_ids is not None and pid not in allowed_ids:
            continue

        label = it.get("label")
        title = (label.get(lang) if isinstance(label, dict) else None) or index_profile_label(pid, lang=lang) or pid.replace("_", " ").title()

        # Search filter
        hay = f"{pid} {title}".lower()
        if q and q not in hay:
            continue

        options.append({"id": pid, "title": title})

    # Keep selection stable
    current = (cv.get("ats_profile") or "").strip() or "cyber_security"
    ids = [o["id"] for o in options]
    if current not in ids and ids:
        current = ids[0]
        cv["ats_profile"] = current

    def _fmt(pid: str) -> str:
        # show "Title (id)"
        title = next((o["title"] for o in options if o["id"] == pid), pid.replace("_", " ").title())
        return f"{title} ({pid})"

    selected = st.selectbox(
        "ATS Profile",
        options=ids,
        index=ids.index(current) if current in ids else 0,
        format_func=_fmt,
        key="ats_profile_select",
    )

    if selected != cv.get("ats_profile"):
        cv["ats_profile"] = selected

    # Load profile
    try:
        prof = load_profile(cv["ats_profile"], lang=lang)
        # Optional: show warnings
        warns = prof.get("_warnings", [])
        if isinstance(warns, list) and warns:
            with st.expander("Profile warnings", expanded=False):
                for w in warns:
                    st.caption(f"• {w}")
        return prof
    except ProfileError as e:
        st.error(str(e))
    except Exception as e:
        st.error(f"Failed to load profile: {e}")

    return None
