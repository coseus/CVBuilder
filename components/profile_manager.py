# components/profile_manager.py
from __future__ import annotations

import streamlit as st
from utils.profiles import list_profiles, load_profile, save_profile_text, ProfileError


def render_profile_manager(cv: dict):
    """
    UI: select + preview + edit ATS profile (YAML).
    Stores selected profile id in cv['ats_profile'].
    Returns loaded profile dict or None.
    """
    cv.setdefault("ats_profile", "cyber_security")

    st.markdown("### ATS Profile")
    profiles = list_profiles()  # [{id, filename, title}, ...]

    if not profiles:
        st.warning("No ATS profiles found.")
        return None

    # --- Filter group (IT / Non-IT) based on id naming convention or title keywords
    # If you also add domains_index.yaml later, we can read it here, but this keeps it simple and robust.
    def is_it(p: dict) -> bool:
        pid = (p.get("id") or "").lower()
        title = (p.get("title") or "").lower()
        it_tokens = ["cyber", "soc", "security", "network", "system", "cloud", "devops", "sre", "platform", "infra", "observability", "iam", "appsec", "dfir"]
        return any(t in pid for t in it_tokens) or any(t in title for t in it_tokens)

    filter_choice = st.radio(
        "Filter",
        ["All", "IT", "Non-IT"],
        horizontal=True,
        key="pm_filter",
    )

    if filter_choice == "IT":
        profiles_filtered = [p for p in profiles if is_it(p)]
    elif filter_choice == "Non-IT":
        profiles_filtered = [p for p in profiles if not is_it(p)]
    else:
        profiles_filtered = profiles

    # keep stable selection
    ids = [p["id"] for p in profiles_filtered]
    titles = {p["id"]: f"{p.get('title','').strip()} ({p['id']})" for p in profiles_filtered}

    current = cv.get("ats_profile", "cyber_security")
    if current not in ids:
        # fallback: if current filtered out, keep it but show first filtered
        current = ids[0] if ids else cv.get("ats_profile", "cyber_security")

    sel = st.selectbox(
        "Select profile",
        ids,
        index=ids.index(current) if current in ids else 0,
        format_func=lambda pid: titles.get(pid, pid),
        key="pm_select_profile",
    )

    cv["ats_profile"] = sel

    # Load
    try:
        prof = load_profile(sel, lang="en")
    except TypeError:
        # if your load_profile does not accept lang, fallback
        prof = load_profile(sel)
    except ProfileError as e:
        st.error(str(e))
        return None
    except Exception as e:
        st.error(f"Failed to load profile: {e}")
        return None

    # Preview warnings
    warns = prof.get("_warnings", [])
    if warns:
        with st.expander("Profile warnings", expanded=False):
            for w in warns:
                st.warning(w)

    # YAML editor (optional)
    with st.expander("Edit YAML (advanced)", expanded=False):
        st.caption("Editing YAML is optional. Save only if you know what you're changing.")
        # We can’t reliably re-serialize the original source here without reading the file again,
        # so we offer editing text and saving it back.
        yaml_text = st.text_area(
            "Profile YAML",
            value=_best_effort_dump_profile_yaml(prof),
            height=320,
            key="pm_yaml_editor",
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Save YAML", use_container_width=True, key="pm_save_yaml"):
                try:
                    save_profile_text(sel, yaml_text)
                    st.success("Saved.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Save failed: {e}")
        with c2:
            if st.button("Reload", use_container_width=True, key="pm_reload"):
                st.rerun()

    return prof


def _best_effort_dump_profile_yaml(profile: dict) -> str:
    """
    If profile already contains normalized structures, dumping it still produces valid YAML.
    This avoids needing direct file reads in the component.
    """
    try:
        import yaml
        # remove runtime keys
        p = {k: v for k, v in (profile or {}).items() if not str(k).startswith("_")}
        return yaml.safe_dump(p, sort_keys=False, allow_unicode=True)
    except Exception:
        return ""
