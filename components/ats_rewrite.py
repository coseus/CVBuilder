import re
import streamlit as st


def _get_by_path(root, path: str):
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


def _dedupe_keep_order(items):
    seen = set()
    out = []
    for it in items or []:
        s = str(it).strip()
        if not s:
            continue
        k = s.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(s)
    return out


def _get_ranked_templates_from_overlay(cv: dict) -> list:
    """
    Priority:
      1) cv['ats_job_overlay']['templates_ranked']
      2) cv['ats_rewrite_templates_active']
    """
    overlay = cv.get("ats_job_overlay", {})
    if isinstance(overlay, dict):
        t = overlay.get("templates_ranked")
        if isinstance(t, list) and t:
            return [str(x) for x in t if str(x).strip()]

    t2 = cv.get("ats_rewrite_templates_active")
    if isinstance(t2, list) and t2:
        return [str(x) for x in t2 if str(x).strip()]

    return []


def render_template_helper(profile: dict, cv: dict, key_prefix: str):
    # Base templates from profile
    templates = []
    if isinstance(profile, dict):
        templates = profile.get("bullet_templates", []) or []

    # Ranked templates from JD overlay (per job)
    ranked = _get_ranked_templates_from_overlay(cv)

    # Merge with ranked first
    merged = _dedupe_keep_order(ranked + (templates if isinstance(templates, list) else []))

    if not merged:
        st.caption("No bullet templates available (profile + JD overlay empty).")
        return None

    return st.selectbox(
        "Pick a template",
        merged,
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
    Backward compatible:
    - field_path: where to write (e.g., 'experienta[0].activitati')
    - item_key: unique identifier per item (fallback uses field_path)
    """
    if not item_key:
        item_key = field_path

    # Make sure key is Streamlit-safe (no brackets etc)
    safe_item_key = re.sub(r"[^a-zA-Z0-9_\-]+", "_", item_key)
    kp = f"rewrite__{safe_item_key}"

    st.markdown("#### Auto-rewrite (ATS)")

    tmpl = render_template_helper(profile, cv=cv, key_prefix=kp)

    col1, col2, col3 = st.columns([1, 1, 1.2])
    with col1:
        btn_insert = st.button("Insert template", key=f"{kp}__btn_insert", use_container_width=True)
    with col2:
        btn_rewrites = st.button("Generate rewrites", key=f"{kp}__btn_gen", use_container_width=True)
    with col3:
        btn_apply = st.button("Apply selected", key=f"{kp}__btn_apply", use_container_width=True)

    suggestions_key = f"{kp}__suggestions"
    selected_key = f"{kp}__selected"

    if btn_insert and tmpl:
        st.session_state[selected_key] = tmpl
        st.success("Template selected.")

    if btn_rewrites:
        try:
            current_text = _get_by_path(cv, field_path)
        except Exception:
            current_text = ""

        base = (current_text or "").strip()

        # If we have templates_ranked from overlay, also propose a few “filled” variants
        ranked = _get_ranked_templates_from_overlay(cv)

        suggestions = []
        if base:
            suggestions.append(f"Optimized {base[:60]}... to improve reliability and security.")
            suggestions.append(f"Implemented {base[:60]}... reducing incidents and improving SLA compliance.")
        else:
            suggestions.append("Implemented security controls (MFA/least privilege), reducing account risk by X%.")
            suggestions.append("Conducted vulnerability assessments across N assets; remediated Y High/Critical issues.")

        # Add ranked templates as suggestions too (so user can apply quickly)
        for t in ranked[:4]:
            suggestions.append(t)

        st.session_state[suggestions_key] = _dedupe_keep_order(suggestions)
        st.session_state[selected_key] = st.session_state[suggestions_key][0] if st.session_state[suggestions_key] else ""
        st.info("Rewrites generated. Pick one and Apply.")

    suggestions = st.session_state.get(suggestions_key, [])
    if suggestions:
        picked = st.radio(
            label,
            options=suggestions,
            key=f"{kp}__radio_pick",
        )
        st.session_state[selected_key] = picked

    if btn_apply:
        selected = st.session_state.get(selected_key, "")
        if selected:
            try:
                current = _get_by_path(cv, field_path)
            except Exception:
                current = ""

            current = current or ""
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
