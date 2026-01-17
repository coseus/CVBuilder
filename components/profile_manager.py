import streamlit as st
import yaml

from utils.profiles import (
    ProfileError,
    list_profiles,
    load_profile,
    save_profile_text,
    save_profile_dict,
)


def _pretty_label(p: dict) -> str:
    title = (p.get("title") or "").strip()
    pid = (p.get("id") or "").strip()
    if title and pid:
        return f"{title}  ({pid})"
    return title or pid or "profile"


def render_profile_manager(cv: dict):
    """
    ATS Profile manager UI:
    - Select profile (shows title, stores id in cv['ats_profile'])
    - Preview normalized profile + warnings
    - Edit YAML and save
    - Duplicate as new profile (optional)
    Returns loaded normalized profile dict (or None).
    """
    if not isinstance(cv, dict):
        st.error("CV invalid.")
        return None

    # Load profile list
    profiles = list_profiles()
    if not profiles:
        st.warning("No ATS profiles found in ./ats_profiles")
        return None

    # Build selection lists
    ids = [p["id"] for p in profiles]
    labels = [_pretty_label(p) for p in profiles]

    current_id = (cv.get("ats_profile") or "").strip()
    if current_id not in ids:
        current_id = ids[0]
        cv["ats_profile"] = current_id

    current_idx = ids.index(current_id)

    st.markdown("### ATS Profile")

    sel = st.selectbox(
        "Select profile",
        options=list(range(len(ids))),
        index=current_idx,
        format_func=lambda i: labels[i],
        key="profile_select_idx",
    )
    selected_id = ids[sel]
    if selected_id != cv.get("ats_profile"):
        cv["ats_profile"] = selected_id
        st.rerun()

    # Load selected profile (normalized)
    try:
        profile = load_profile(cv["ats_profile"])
    except ProfileError as e:
        st.error(f"Profile load error: {e}")
        return None

    # Show warnings if any
    warnings = profile.get("_warnings", [])
    if warnings:
        for w in warnings:
            st.warning(w)

    # Buttons row
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        if st.button("Reload profile", use_container_width=True, key="profile_reload_btn"):
            st.rerun()
    with c2:
        if st.button("Show preview", use_container_width=True, key="profile_preview_btn"):
            st.session_state["profile_preview_open"] = True
    with c3:
        if st.button("Edit YAML", use_container_width=True, key="profile_edit_open_btn"):
            st.session_state["profile_editor_open"] = True

    # Preview
    if st.session_state.get("profile_preview_open", False):
        with st.expander("Profile preview (normalized)", expanded=True):
            # Hide internal keys in preview
            preview = {k: v for k, v in profile.items() if not str(k).startswith("_")}
            st.json(preview)

    # Editor (raw YAML)
    if st.session_state.get("profile_editor_open", False):
        with st.expander("Edit profile YAML", expanded=True):
            # We edit YAML derived from normalized profile (keeps schema consistent)
            editable = {k: v for k, v in profile.items() if not str(k).startswith("_")}
            yaml_text_default = yaml.safe_dump(editable, sort_keys=False, allow_unicode=True)

            yaml_text = st.text_area(
                "YAML",
                value=st.session_state.get("profile_yaml_buffer", yaml_text_default),
                height=420,
                key="profile_yaml_editor",
            )
            st.session_state["profile_yaml_buffer"] = yaml_text

            e1, e2, e3 = st.columns([1, 1, 1])
            with e1:
                if st.button("Save", use_container_width=True, key="profile_save_btn"):
                    try:
                        save_profile_text(cv["ats_profile"], yaml_text)
                        st.success("Saved.")
                        # clear buffer so it reloads from disk next time
                        st.session_state.pop("profile_yaml_buffer", None)
                        st.rerun()
                    except ProfileError as e:
                        st.error(str(e))
                    except Exception as e:
                        st.error(f"Save failed: {e}")

            with e2:
                # Duplicate as new profile id
                new_id = st.text_input(
                    "Duplicate as id",
                    value=f"{cv['ats_profile']}_copy",
                    key="profile_dup_id",
                    help="Creates a new YAML in ./ats_profiles",
                )
                if st.button("Duplicate", use_container_width=True, key="profile_duplicate_btn"):
                    try:
                        # Parse YAML in editor and save as new id
                        parsed = yaml.safe_load(yaml_text) or {}
                        if not isinstance(parsed, dict):
                            st.error("YAML root must be an object (mapping).")
                        else:
                            pid = save_profile_dict(parsed, profile_id=new_id.strip())
                            st.success(f"Created: {pid}")
                            cv["ats_profile"] = pid
                            st.session_state.pop("profile_yaml_buffer", None)
                            st.rerun()
                    except Exception as e:
                        st.error(f"Duplicate failed: {e}")

            with e3:
                if st.button("Close editor", use_container_width=True, key="profile_close_editor_btn"):
                    st.session_state["profile_editor_open"] = False
                    st.session_state.pop("profile_yaml_buffer", None)
                    st.rerun()

    return profile
