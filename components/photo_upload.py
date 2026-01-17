import streamlit as st

def render_photo_upload(cv, prefix=""):
    st.subheader("Fotografie (optional)")

    uploaded = st.file_uploader(
        "Incarca fotografie (jpg/png)",
        type=["jpg","jpeg","png"],
        key=f"{prefix}photo_upload"
    )

    if uploaded is not None:
        try:
            cv['photo'] = uploaded.read()
            st.image(cv['photo'], width=180)
            st.success("Fotografie incarcata")
        except Exception:
            st.error("Eroare la procesare")

    if cv.get('photo') and st.button("Sterge fotografie", key=f"{prefix}delete_photo"):
        cv['photo'] = None
        st.rerun()
