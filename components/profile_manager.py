# components/profile_manager.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

from utils.profiles import (
    ProfileError,
    load_profile,
    list_profiles,
    load_domains_index,
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


def _flatten_domains_index(idx: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Returns a flat list of domains with optional group_id:
      [{id,label,library,group_id?}, ...]
    Supports both grouped and flat formats.
    """
    out: List[Dict[str, Any]] = []
    if not isinstance(idx, dict):
        return out

    if isinstance(idx.get("groups"), list):
        for g in idx.get("groups") or []:
            if not isinstance(g, dict):
                continue
            gid = str(g.get("id") or "").strip()
            for d in (g.get("domains") or []):
                if not isinstance(d, dict):
                    continue
                if not d.get("id"):
                    continue
                dd = dict(d)
                dd["group_id"] = gid
                out.append(dd)

    if not out and isinstance(idx.get("domains"), list):
        for d in idx.get("domains") or []:
            if isinstance(d, dict) and d.get("id"):
                out.append(dict(d))

    return out


def render_profile_manager(cv: Dict[str, Any], lang: str = "en") -> Optional[Dict[str, Any]]:
    """
    UI: Select / preview ATS profile + domain filter + auto-suggest from JD.
    Updates cv["ats_profile"] with selected id and returns loaded (merged) profile dict.
    """
    if not isinstance(cv, dict):
        return None

    cv.setdefault("ats_profile", "cyber_security")

    idx = load_domains_index()
    domains = _flatten_domains_index(idx)

    # Groups for filter
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

    # Allowed ids based on filter
    allowed_ids: Optional[set] = None
    if groups and domain_filter_id != "all":
        allowed_ids = set()
        for d in domains:
            if isinstance(d, dict) and d.get("group_id") == domain_filter_id:
                allowed_ids.add(str(d.get("id")))

    # List profiles (friendly titles)
    profiles_list = list_profiles(lang=lang)
    if allowed_ids is not None:
        profiles_list = [p for p in profiles_list if str(p.get("id")) in allowed_ids]

    if not profiles_list:
        st.warning("No profiles found for this filter. Check domains_index.yaml mapping or profile ids.")
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

    # Load selected profile merged with libraries
    try:
        prof = load_profile(cv["ats_profile"], lang=lang)
    except ProfileError as e:
        st.error(str(e))
        return None

    # Warnings
    warnings = prof.get("_warnings") or []
    if warnings:
        st.warning(" • ".join([str(w) for w in warnings][:5]))

    # -------------------------
    # Auto-suggest from shared JD
    # -------------------------
    from utils import jd_optimizer

    jd_optimizer.ensure_jd_state(cv)
    jd_text = jd_optimizer.get_current_jd(cv)

    with st.expander("Auto-suggest profile from Job Description", expanded=False):
        if not jd_text.strip():
            st.info("Paste a Job Description in the shared JD box to get suggestions.")
        else:
            sugg = jd_optimizer.suggest_profiles_from_jd(jd_text, lang=lang, top_k=5)
            if not sugg:
                st.info("No suggestions found (not enough signal in JD or libraries missing).")
            else:
                st.caption("Top suggestions (domain-library keyword overlap):")
                for s in sugg:
                    pid = str(s.get("profile_id") or "")
                    label = str(s.get("label") or pid)
                    score = float(s.get("score") or 0.0)

                    c1, c2, c3 = st.columns([3, 1, 1], gap="small")
                    with c1:
                        st.write(f"**{label}**  (`{pid}`)")
                    with c2:
                        st.write(f"{score:.0f}%")
                    with c3:
                        disabled = (pid == cv.get("ats_profile"))
                        if st.button("Switch", key=f"switch_{pid}", use_container_width=True, disabled=disabled):
                            cv["ats_profile"] = pid
                            cv.pop("ats_analysis", None)
                            cv.pop("ats_score", None)
                            st.rerun()

                # Helpful mismatch warning
                role_hint = (cv.get("jd_state", {}) or {}).get("current_role_hint", "")
                if role_hint and isinstance(prof.get("job_titles"), list):
                    titles = " ".join([str(x).lower() for x in prof.get("job_titles") or []])
                    if role_hint.lower() not in titles:
                        st.warning(
                            "⚠️ Role hint seems different from selected profile job titles. "
                            "Consider switching to a suggested profile for better results."
                        )

    # Preview
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
