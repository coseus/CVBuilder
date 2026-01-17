import re
import streamlit as st


def _get_by_path(root, path: str):
    """
    Get nested value by a path like:
      'experienta[0].activitati'
    """
    cur = root
    tokens = re.findall(r"[a-zA-Z_]\w*|\[\d+\]", path)
    for tok in tokens:
        if tok.startswith("["):
            idx = int(tok[1:-1])
            cur = cur[idx]
        else:
            cur = cur[tok]
    return cur


def _set_by_path(root, path: str, value):
    """
    Set nested value by a path like:
      'experienta[0].activitati'
    """
    cur = root
    tokens = re.findall(r"[a-zA-Z_]\w*|\[\d+\]", path)
    for i, tok in enumerate(tokens):
        is_last = i == len(tokens) - 1
        if tok.startswith("["):
            idx = int(tok[1:-1])
            if is_last:
                cur[idx] = value
            else:
                cur = cur[idx]
        else:
            if is_last:
                cur[tok] = value
            else:
                if tok not in cur:
                    cur[tok] = {}
                cur = cur[tok]


def render_template_helper(profile: dict, key_prefix: str):
    templates = []
    if isinstance(profile, dict):
        templates = profile.get("bullet_templates", []) or []

    if not templates:
        st.caption("No bullet templates in this profile.")
        return None

    return st.selectbox(
        "Pick a template",
        templates,
        key=f"{key_prefix}__ats_template_pick",
    )


def render_auto_rewrite_box(
    cv: dict,
    profile: dict,
    field_path: str,
    item_key: str = "",
    label: str = "Rewrite suggestion",
):
    """
    Backward compatible with older calls that pass field_path.

    - field_path: where to write (e.g., 'experienta[0].activitati')
    - item_key: unique identifier per item (fallback uses field_path)
    """
    if not item_key:
        item_key = field_path

    kp = f"rewrite__{item_key}"

    st.markdown("#### Auto-rewrite (ATS)")

    tmpl = render_template_helper(profile, key_prefix=kp)

    col1, col2, col3 = st.columns([1, 1, 1.2])
    with col1:
        btn_insert = st.button("Insert template", key=f"{kp}__btn_insert", use_container_width=True)
    with col2:
        btn_rewrites = st.button("Generate rewrites", key=f"{kp}__btn_gen", use_container_width=True)
    with col3:
        btn_apply = st.button("Apply selected", key=f"{kp}__btn_apply", use_container_width=True)

    # Store suggestions
    suggestions_key = f"{kp}__suggestions"
    selected_key = f"{kp}__selected"

    # Insert template (just store it as selected)
    if btn_insert and tmpl:
        st.session_state[selected_key] = tmpl
        st.success("Template selected.")

    # Generate deterministic rewrite suggestions (simple heuristic)
    if btn_rewrites:
        try:
            current_text = _get_by_path(cv, field_path)
        except Exception:
            current_text = ""

        base = (current_text or "").strip()
        # basic suggestions; you can make them smarter later
        suggestions = []
        if base:
            suggestions.append(f"Optimized {base[:60]}... to improve reliability and security.")
            suggestions.append(f"Implemented {base[:60]}... reducing incidents and improving SLA compliance.")
        else:
            suggestions.append("Implemented security controls (MFA/least privilege), reducing account risk by X%.")
            suggestions.append("Conducted vulnerability assessments across N assets; remediated Y High/Critical issues.")

        st.session_state[suggestions_key] = suggestions
        st.session_state[selected_key] = suggestions[0] if suggestions else ""
        st.info("Rewrites generated. Pick one and Apply.")

    # Show suggestions + selection
    suggestions = st.session_state.get(suggestions_key, [])
    if suggestions:
        picked = st.radio(
            label,
            options=suggestions,
            key=f"{kp}__radio_pick",
        )
        st.session_state[selected_key] = picked

    # Apply selected to target field_path (append as bullet line)
    if btn_apply:
        selected = st.session_state.get(selected_key, "")
        if selected:
            try:
                current = _get_by_path(cv, field_path)
            except Exception:
                current = ""

            current = current or ""
            # Append nicely
            new_line = selected.strip()
            if current.strip():
                updated = current.rstrip() + "\n- " + new_line
            else:
                updated = "- " + new_line

            _set_by_path(cv, field_path, updated)
            st.success("Applied to the field.")
            st.rerun()
        else:
            st.warning("Nothing selected to apply.")
