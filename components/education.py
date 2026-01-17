import streamlit as st

def render_education(cv, prefix="", list_key="educatie", title="Educație și formare"):
    st.subheader(title)
    cv.setdefault(list_key, [])

    with st.form(key=f"{prefix}{list_key}_add_form", clear_on_submit=True):
        col1, col2 = st.columns([1, 2])
        with col1:
            perioada = st.text_input("Perioada", key=f"{prefix}{list_key}_perioada")
        with col2:
            calificare = st.text_input("Calificare / Diplomă", key=f"{prefix}{list_key}_calificare")

        discipline = st.text_area("Discipline / Competențe (bullets recomandat)", height=100, key=f"{prefix}{list_key}_discipline")
        institutie = st.text_input("Instituție / Furnizor", key=f"{prefix}{list_key}_institutie")
        nivel = st.text_input("Nivel (EQF, Licență etc.)", key=f"{prefix}{list_key}_nivel")

        submitted = st.form_submit_button("Adaugă")
        if submitted and calificare.strip():
            cv[list_key].append({
                'perioada': perioada.strip(),
                'calificare': calificare.strip(),
                'discipline': discipline.strip(),
                'institutie': institutie.strip(),
                'nivel': nivel.strip()
            })
            st.success("Educație adăugată!")
            st.rerun()

    if not cv.get(list_key):
        st.caption("Nu ai adăugat încă educație.")
        return

    st.caption("Tip: poți reordona educația ca să pui cea mai relevantă sus.")
    for i, edu in enumerate(list(cv[list_key])):
        with st.expander(f"{edu.get('calificare', 'Fără titlu')} ({edu.get('perioada', 'nedefinit')})", expanded=False):
            top = st.columns([1,1,1,2])
            with top[0]:
                if st.button("⬆️ Sus", key=f"{prefix}{list_key}_up_{i}", disabled=(i==0)):
                    cv[list_key][i-1], cv[list_key][i] = cv[list_key][i], cv[list_key][i-1]
                    st.rerun()
            with top[1]:
                if st.button("⬇️ Jos", key=f"{prefix}{list_key}_down_{i}", disabled=(i==len(cv[list_key])-1)):
                    cv[list_key][i+1], cv[list_key][i] = cv[list_key][i], cv[list_key][i+1]
                    st.rerun()
            with top[2]:
                if st.button("🗑️ Șterge", key=f"{prefix}{list_key}_del_{i}"):
                    cv[list_key].pop(i)
                    st.rerun()
            with top[3]:
                st.caption("Editați și Save.")

            c1, c2 = st.columns([1,2])
            with c1:
                edu['perioada'] = st.text_input("Perioada", value=edu.get('perioada',''), key=f"{prefix}{list_key}_e_per_{i}")
            with c2:
                edu['calificare'] = st.text_input("Calificare / Diplomă", value=edu.get('calificare',''), key=f"{prefix}{list_key}_e_cal_{i}")

            edu['institutie'] = st.text_input("Instituție / Furnizor", value=edu.get('institutie',''), key=f"{prefix}{list_key}_e_inst_{i}")
            edu['nivel'] = st.text_input("Nivel", value=edu.get('nivel',''), key=f"{prefix}{list_key}_e_niv_{i}")
            edu['discipline'] = st.text_area("Discipline / Competențe", value=edu.get('discipline',''), height=120, key=f"{prefix}{list_key}_e_dis_{i}")

            if st.button("💾 Save", key=f"{prefix}{list_key}_save_{i}"):
                cv[list_key][i] = edu
                st.success("Salvat!")
                st.rerun()
