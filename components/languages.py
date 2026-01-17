import streamlit as st


def _ensure_lang_defaults(item: dict) -> dict:
    """
    Ensure Europass keys exist to prevent KeyError.
    Supports both:
      - full Europass: ascultare/citire/interactiune/exprimare/scriere
      - simplified: nivel
    """
    if not isinstance(item, dict):
        return {"limba": "", "nivel": ""}

    item.setdefault("limba", "")
    item.setdefault("nivel", "")

    # Full Europass keys (default empty)
    item.setdefault("ascultare", "")
    item.setdefault("citire", "")
    item.setdefault("interactiune", "")
    item.setdefault("exprimare", "")
    item.setdefault("scriere", "")
    return item


def _apply_level_to_all(lang_item: dict, level: str):
    """
    If user provides a single CEFR level (A1..C2 or 'Intermediate'),
    fill all five Europass competences.
    """
    level = (level or "").strip()
    if not level:
        return
    for k in ["ascultare", "citire", "interactiune", "exprimare", "scriere"]:
        lang_item[k] = level


def render_languages(cv: dict, prefix: str = ""):
    if not isinstance(cv, dict):
        st.error("CV invalid.")
        return

    cv.setdefault("limba_materna", "")
    cv.setdefault("limbi_straine", [])

    st.subheader("Limbi")

    cv["limba_materna"] = st.text_input(
        "Limba maternă",
        value=cv.get("limba_materna", ""),
        key=f"{prefix}limba_materna",
        placeholder="ex: Română",
    )

    st.markdown("### Limbi străine")

    # Add language (supports both full Europass and simple level)
    with st.expander("➕ Adaugă limbă", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            limba = st.text_input("Limba", key=f"{prefix}add_lang_name")
        with col2:
            nivel = st.text_input("Nivel (CEFR sau text)", key=f"{prefix}add_lang_level", placeholder="ex: B1 / B2 / Intermediate")

        if st.button("Adaugă", key=f"{prefix}add_lang_btn"):
            item = {
                "limba": limba.strip(),
                "nivel": nivel.strip(),
                # full Europass keys empty by default:
                "ascultare": "",
                "citire": "",
                "interactiune": "",
                "exprimare": "",
                "scriere": "",
            }
            # if they gave a single level, apply to all
            if item["nivel"]:
                _apply_level_to_all(item, item["nivel"])

            cv["limbi_straine"].append(item)
            st.rerun()

    if cv.get("limbi_straine"):
        st.markdown("**Limbi adăugate:**")

        for i in range(len(cv["limbi_straine"])):
            l = _ensure_lang_defaults(cv["limbi_straine"][i])

            with st.expander(f"{l.get('limba','(fără nume)')}", expanded=False):
                l["limba"] = st.text_input("Limba", value=l.get("limba", ""), key=f"{prefix}lang_{i}_name")

                # Quick level (single field)
                l["nivel"] = st.text_input("Nivel (rapid)", value=l.get("nivel", ""), key=f"{prefix}lang_{i}_nivel")

                colA, colB, colC = st.columns(3)
                with colA:
                    l["ascultare"] = st.text_input("Ascultare", value=l.get("ascultare", ""), key=f"{prefix}lang_{i}_asc")
                    l["citire"] = st.text_input("Citire", value=l.get("citire", ""), key=f"{prefix}lang_{i}_cit")
                with colB:
                    l["interactiune"] = st.text_input("Interacțiune", value=l.get("interactiune", ""), key=f"{prefix}lang_{i}_int")
                    l["exprimare"] = st.text_input("Exprimare", value=l.get("exprimare", ""), key=f"{prefix}lang_{i}_expr")
                with colC:
                    l["scriere"] = st.text_input("Scriere", value=l.get("scriere", ""), key=f"{prefix}lang_{i}_scr")
                    if st.button("Aplică 'Nivel (rapid)' la toate", key=f"{prefix}lang_{i}_apply_all"):
                        _apply_level_to_all(l, l.get("nivel", ""))
                        st.rerun()

                # Save back
                cv["limbi_straine"][i] = l

                if st.button("Șterge", key=f"{prefix}del_lang_{i}"):
                    cv["limbi_straine"].pop(i)
                    st.rerun()
    else:
        st.caption("Nu ai adăugat încă limbi străine.")
