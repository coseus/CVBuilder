import streamlit as st


def render_string_list_editor(
    label: str,
    items: list,
    key_prefix: str,
    placeholder: str = "",
    help_text: str | None = None,
):
    """
    Edit/add/delete/reorder for list[str].
    Returns updated list.
    """
    if not isinstance(items, list):
        items = []

    if help_text:
        st.caption(help_text)

    # Existing items
    for i in range(len(items)):
        col1, col2, col3, col4 = st.columns([8, 1, 1, 1])
        with col1:
            items[i] = st.text_input(
                f"{label} #{i+1}",
                value=str(items[i] or ""),
                key=f"{key_prefix}_item_{i}",
                placeholder=placeholder,
                label_visibility="collapsed",
            )
        with col2:
            if st.button("⬆", key=f"{key_prefix}_up_{i}", help="Move up") and i > 0:
                items[i - 1], items[i] = items[i], items[i - 1]
                st.rerun()
        with col3:
            if st.button("⬇", key=f"{key_prefix}_down_{i}", help="Move down") and i < len(items) - 1:
                items[i + 1], items[i] = items[i], items[i + 1]
                st.rerun()
        with col4:
            if st.button("🗑", key=f"{key_prefix}_del_{i}", help="Delete"):
                items.pop(i)
                st.rerun()

    # Add new item
    st.markdown("**Add new**")
    new_val = st.text_input("New", value="", key=f"{key_prefix}_new", placeholder=placeholder, label_visibility="collapsed")
    if st.button("Add", key=f"{key_prefix}_add", use_container_width=False):
        if new_val.strip():
            items.append(new_val.strip())
            st.rerun()
        else:
            st.warning("Enter a value first.")

    return items


def render_kv_list_editor(
    label: str,
    items: list,
    key_prefix: str,
    label_name: str = "Label",
    value_name: str = "Value",
    help_text: str | None = None,
):
    """
    Edit/add/delete for list[{"label":str,"value":str}]
    Returns updated list.
    """
    if not isinstance(items, list):
        items = []

    if help_text:
        st.caption(help_text)

    for i in range(len(items)):
        row = items[i] if isinstance(items[i], dict) else {"label": "", "value": ""}
        row.setdefault("label", "")
        row.setdefault("value", "")

        colA, colB, colC = st.columns([3, 5, 1])
        with colA:
            row["label"] = st.text_input(label_name, value=row.get("label", ""), key=f"{key_prefix}_kv_{i}_label")
        with colB:
            row["value"] = st.text_input(value_name, value=row.get("value", ""), key=f"{key_prefix}_kv_{i}_value")
        with colC:
            if st.button("🗑", key=f"{key_prefix}_kv_{i}_del", help="Delete"):
                items.pop(i)
                st.rerun()

        items[i] = row

    st.markdown("**Add new**")
    c1, c2 = st.columns(2)
    with c1:
        nl = st.text_input(label_name, value="", key=f"{key_prefix}_kv_new_label")
    with c2:
        nv = st.text_input(value_name, value="", key=f"{key_prefix}_kv_new_value")
    if st.button("Add", key=f"{key_prefix}_kv_add"):
        if nl.strip() and nv.strip():
            items.append({"label": nl.strip(), "value": nv.strip()})
            st.rerun()
        else:
            st.warning("Complete both Label and Value.")

    return items
