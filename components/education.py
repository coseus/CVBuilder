import streamlit as st

def render_education(cv, prefix="", list_key="educatie", title="Education and training"):
    st.subheader(title)
    cv.setdefault(list_key, [])

    with st.form(key=f"{prefix}{list_key}_add_form", clear_on_submit=True):
        col1, col2 = st.columns([1, 2])
        with col1:
            perioada = st.text_input("Period", key=f"{prefix}{list_key}_perioada")
        with col2:
            calificare = st.text_input("Qualification / Diploma", key=f"{prefix}{list_key}_calificare")

        discipline = st.text_area("Disciplines / Skills (bullets recommended)", height=100, key=f"{prefix}{list_key}_discipline")
        institutie = st.text_input("Institution / Provider", key=f"{prefix}{list_key}_institutie")
        nivel = st.text_input("Level (EQF, Bachelor's degree, etc.)", key=f"{prefix}{list_key}_nivel")

        submitted = st.form_submit_button("Add")
        if submitted and calificare.strip():
            cv[list_key].append({
                'perioada': perioada.strip(),
                'calificare': calificare.strip(),
                'discipline': discipline.strip(),
                'institutie': institutie.strip(),
                'nivel': nivel.strip()
            })
            st.success("Added education!")
            st.rerun()

    if not cv.get(list_key):
        st.caption("You haven't added education yet.")
        return

    st.caption("Tip: you can reorder the education to put the most relevant one at the top.")
    for i, edu in enumerate(list(cv[list_key])):
        with st.expander(f"{edu.get('calificare', 'Untitled')} ({edu.get('perioada', 'nedefinit')})", expanded=False):
            top = st.columns([1,1,1,2])
            with top[0]:
                if st.button("⬆️ Up", key=f"{prefix}{list_key}_up_{i}", disabled=(i==0)):
                    cv[list_key][i-1], cv[list_key][i] = cv[list_key][i], cv[list_key][i-1]
                    st.rerun()
            with top[1]:
                if st.button("⬇️ Down", key=f"{prefix}{list_key}_down_{i}", disabled=(i==len(cv[list_key])-1)):
                    cv[list_key][i+1], cv[list_key][i] = cv[list_key][i], cv[list_key][i+1]
                    st.rerun()
            with top[2]:
                if st.button("🗑️ Delete", key=f"{prefix}{list_key}_del_{i}"):
                    cv[list_key].pop(i)
                    st.rerun()
            with top[3]:
                st.caption("Edit and Save.")

            c1, c2 = st.columns([1,2])
            with c1:
                edu['perioada'] = st.text_input("Period", value=edu.get('perioada',''), key=f"{prefix}{list_key}_e_per_{i}")
            with c2:
                edu['calificare'] = st.text_input("Qualification / Diploma", value=edu.get('calificare',''), key=f"{prefix}{list_key}_e_cal_{i}")

            edu['institutie'] = st.text_input("Institution / Provider", value=edu.get('institutie',''), key=f"{prefix}{list_key}_e_inst_{i}")
            edu['nivel'] = st.text_input("Nivel", value=edu.get('nivel',''), key=f"{prefix}{list_key}_e_niv_{i}")
            edu['discipline'] = st.text_area("Disciplines / Competencies", value=edu.get('discipline',''), height=120, key=f"{prefix}{list_key}_e_dis_{i}")

            if st.button("💾 Save", key=f"{prefix}{list_key}_save_{i}"):
                cv[list_key][i] = edu
                st.success("Salvat!")
                st.rerun()
