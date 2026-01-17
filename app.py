import hashlib
import streamlit as st
from utils.session import init_session_state, reset_everything, clear_runtime_only

# ====== NEW ATS COMPLETE COMPONENTS ======
from components.ats_personal_info import render_ats_personal_info
from components.ats_summary import render_ats_summary
from components.ats_skills import render_ats_skills
from components.ats_helper_panel import render_ats_helper_panel

# ====== Existing components you already have ======
from components.photo_upload import render_photo_upload
from components.work_experience import render_work_experience
from components.education import render_education
from components.profile_manager import render_profile_manager
from components.ats_dashboard import render_ats_score_dashboard
from components.ats_optimizer import render_ats_optimizer
from components.europass_complete import render_europass_complete
from components.ats_optimizer import render_jd_ml_offline_panel
from components.job_profile_manager import render_job_profile_manager

from utils.json_io import import_cv_json, export_cv_json
from utils.profiles import ProfileError, load_profile
from utils.pdf_autofill import file_to_cv
from utils.session import init_session_state, reset_everything, clear_runtime_only, reset_ats_only

from exporters.pdf_generator import generate_pdf_modern, generate_pdf_europass
from exporters.docx_generator import generate_docx_modern, generate_docx_europass


# ====== Optional PDF Autofill ======
PDF_AUTOFILL_AVAILABLE = True
try:
    from utils.pdf_autofill import pdf_to_cv
except Exception:
    PDF_AUTOFILL_AVAILABLE = False


st.set_page_config(page_title="Coseus - CV Builder - Modern & Europass", page_icon="utils/coseus.ico", layout="wide")

init_session_state()
cv = st.session_state.cv

st.title("Coseus - CV Builder - Modern (ATS) vs Europass")

# ==========================
# Sidebar: Import/Export/Reset
# ==========================
sidebar_logo = "utils/logo.png"
st.logo(sidebar_logo, size="large")
st.sidebar.header("Import / Export")

with st.sidebar.expander("Import CV (JSON)", expanded=False):
    up = st.sidebar.file_uploader("Upload JSON", type=["json"], key="json_upload")
    if up is not None:
        if st.sidebar.button("Import now", type="primary", use_container_width=True, key="btn_import_json"):
            raw = up.getvalue()
            sha = hashlib.sha256(raw).hexdigest()
            if st.session_state.get("_last_import_sha") == sha:
                st.sidebar.warning("Același fișier a fost deja importat în sesiunea curentă.")
            else:
                text = raw.decode("utf-8", errors="replace")
                st.session_state.cv = import_cv_json(text)
                st.session_state["_last_import_sha"] = sha
                st.session_state.pop("json_upload", None)
                clear_runtime_only()
                st.sidebar.success("CV importat.")
                st.rerun()

with st.sidebar.expander("Export CV (JSON)", expanded=False):
    st.sidebar.download_button(
        "Download CV JSON",
        data=export_cv_json(cv, include_photo_base64=False).encode("utf-8"), 
        file_name="cv_export.json",
        mime="application/json",
        use_container_width=True,
        key="btn_export_json",
    )
st.sidebar.markdown("---")
if st.sidebar.button("Reset ATS/JD (keep Experience/Education)", use_container_width=True):
    reset_ats_only()

st.sidebar.markdown("---")
if st.sidebar.button("RESET EVERYTHING", type="primary", use_container_width=True, key="btn_reset_all"):
    reset_everything()
    st.rerun()

# ==========================
# Tabs
# ==========================
tab_import, tab_modern, tab_europass = st.tabs(["Import PDF (Autofill)", "Modern (ATS-friendly)", "Europass Complet"])

# --------------------------
# TAB: Import PDF (Autofill)
# --------------------------
with tab_import:
    st.info("Încarcă un CV PDF sau DOCX (RO/EN) și folosește Autofill. Apoi verifică în Modern/Europass.")
    if not PDF_AUTOFILL_AVAILABLE:
        st.warning("Autofill indisponibil (utils/pdf_autofill.py import error sau lipsă dependență).")
    else:
        up = st.file_uploader("Upload CV (PDF/DOCX)", type=["pdf", "docx"], key="pdf_upload")

        lang_hint = st.selectbox(
            "Document language hint",
            [("Auto/EN", "en"), ("Română", "ro")],
            format_func=lambda x: x[0],
            key="pdf_lang_hint",
        )[1]

        def _is_empty(val):
            return val in (None, "", [], {}) or (isinstance(val, str) and not val.strip())

        def _dedup_list_of_dicts(existing: list, incoming: list, key_fields: list):
            """
            Dedup by key_fields, preserving order: existing first, then new unique.
            """
            out = []
            seen = set()

            def make_key(d):
                if not isinstance(d, dict):
                    return None
                parts = []
                for k in key_fields:
                    parts.append(str(d.get(k, "")).strip().lower())
                return "|".join(parts)

            for it in existing:
                out.append(it)
                k = make_key(it)
                if k:
                    seen.add(k)

            for it in incoming:
                k = make_key(it)
                if k and k in seen:
                    continue
                out.append(it)
                if k:
                    seen.add(k)
            return out

        def merge_cv_safe(cv: dict, patch: dict):
            """
            Merge only useful extracted fields, without overwriting user's existing content.
            - Strings: fill only if target empty
            - Lists: if target empty -> set; else merge (dedup)
            - Dicts: shallow-merge keys that are missing
            """
            if not isinstance(patch, dict):
                return

            for k, v in patch.items():
                if _is_empty(v):
                    continue

                if k not in cv or _is_empty(cv.get(k)):
                    cv[k] = v
                    continue

                # Merge lists
                if isinstance(v, list) and isinstance(cv.get(k), list):
                    # special dedup rules per field
                    if k == "experienta":
                        cv[k] = _dedup_list_of_dicts(cv[k], v, ["functie", "angajator", "perioada"])
                    elif k == "educatie":
                        cv[k] = _dedup_list_of_dicts(cv[k], v, ["titlu", "organizatie", "perioada"])
                    elif k == "limbi_straine":
                        cv[k] = _dedup_list_of_dicts(cv[k], v, ["limba"])
                    elif k == "contact_items":
                        cv[k] = _dedup_list_of_dicts(cv[k], v, ["type", "value"])
                    elif k == "personal_info_extra":
                        cv[k] = _dedup_list_of_dicts(cv[k], v, ["label", "value"])
                    else:
                        # generic: append new unique scalars/dicts by string value
                        exist_set = set([str(x).strip().lower() for x in cv[k]])
                        for it in v:
                            if str(it).strip().lower() not in exist_set:
                                cv[k].append(it)
                                exist_set.add(str(it).strip().lower())
                    continue

                # Merge dicts shallowly
                if isinstance(v, dict) and isinstance(cv.get(k), dict):
                    for dk, dv in v.items():
                        if _is_empty(dv):
                            continue
                        if _is_empty(cv[k].get(dk)):
                            cv[k][dk] = dv
                    continue

                # Otherwise: keep user's current value (do nothing)

        if up is not None and st.button("Autofill from file", type="primary", key="btn_pdf_autofill"):
            import tempfile, os
            suffix = ".pdf" if up.name.lower().endswith(".pdf") else ".docx"
            fd, path = tempfile.mkstemp(suffix=suffix)
            os.close(fd)
            with open(path, "wb") as f:
                f.write(up.getvalue())

            # ✅ dispatcher: pdf OR docx
            from utils.pdf_autofill import file_to_cv

            new_cv = file_to_cv(path, lang_hint=lang_hint)

            # ✅ merge safe (doesn't overwrite user's existing content)
            merge_cv_safe(cv, new_cv)

            clear_runtime_only()
            st.success("Autofill completed. Check Modern/Europass tabs.")
            st.rerun()

# --------------------------
# TAB: Modern (ATS-friendly)
# --------------------------
with tab_modern:
    st.info("Format modern - scurt, clar, optimizat pentru ATS + recrutori. Recomandat pentru aplicații online.")

    # Load selected ATS profile (user-editable YAML in ./ats_profiles)
    try:
        profile = load_profile(cv.get("ats_profile", "cyber_security"))
    except ProfileError:
        profile = load_profile("cyber_security")
        cv["ats_profile"] = "cyber_security"

    col1, col2 = st.columns([3, 1.6], gap="large")

    # ---- Left: ATS Complete (personal info + summary bullets + skills + helper) ----
    with col1:
        # ✅ Personal Info with contact items add/edit/delete + extra fields add/edit/delete
        render_ats_personal_info(cv, key_prefix="ats_pi_modern")

        st.markdown("---")

        # ✅ Professional Summary bullets (add/edit/delete/reorder)
        render_ats_summary(cv, key_prefix="ats_sum_modern")

        st.markdown("---")

        # ✅ Skills ATS (categories + add/edit/delete/reorder)
        # also syncs to modern_* fields for your existing exporters
        render_ats_skills(cv, key_prefix="ats_sk_modern")

        st.markdown("---")

        # ✅ ATS helper panel (keywords/metrics/verbs/templates)
        render_ats_helper_panel(cv, key_prefix="ats_help_modern")

    # ---- Right: photo toggle + profile manager + scoring ----
    with col2:
        st.subheader("Foto (nu e recomandat pentru ATS)")
        cv["include_photo_modern"] = st.toggle(
            "Include foto în Modern export",
            value=bool(cv.get("include_photo_modern", False)),
            key="modern_include_photo",
        )
        if cv["include_photo_modern"]:
            render_photo_upload(cv, prefix="modern_")

        st.markdown("---")

        # ✅ ONE shared JD input (used by ATS Optimizer + JD Analyzer + Helper)
        with st.expander("Job Description (shared)", expanded=True):
            from utils import jd_optimizer
            jd_optimizer.ensure_jd_state(cv)

            cv["job_description"] = st.text_area(
                "Paste Job Description (EN/RO) once — used everywhere below",
                value=cv.get("job_description", ""),
                height=240,
                key="job_description_shared",
                placeholder="Paste aici anunțul de job (EN/RO)...",
            )

            # auto update analysis when text changes
            jd_optimizer.auto_update_on_change(cv, profile=profile)

            cols_jd = st.columns([1, 1, 1])
            if cols_jd[0].button("Re-analyze now", use_container_width=True, key="jd_shared_reanalyze"):
                jd_optimizer.analyze_jd(cv, profile=profile)
                st.success("JD analyzed.")
                st.rerun()

            if cols_jd[1].button("Apply missing → Extra keywords", use_container_width=True, key="jd_shared_apply_missing"):
                jd_optimizer.apply_missing_to_extra_keywords(cv, limit=25)
                st.success("Applied into Modern → Extra keywords.")
                st.rerun()

            if cols_jd[2].button("Update rewrite templates", use_container_width=True, key="jd_shared_update_templates"):
                jd_optimizer.update_rewrite_templates_from_jd(cv, profile=profile)
                st.success("Updated templates for this job.")
                st.rerun()

        st.markdown("---")
        render_ats_optimizer(cv, profile=profile)
        st.markdown("---")
        render_jd_ml_offline_panel(cv, profile=profile)
        st.markdown("---")
        render_ats_score_dashboard(cv, profile)
        st.markdown("---")
        render_job_profile_manager(cv)


    st.markdown("---")
    st.subheader("Proiecte / Experiență relevantă (top 3–6)")
    render_work_experience(
        cv,
        profile=profile,
        prefix="modern_",
        title="",
        item_label="Proiect",
        show_employer_fields=True,
        show_sector_field=False,
        show_tech_and_link=True,
    )

    st.markdown("---")
    render_education(cv, prefix="modern_", list_key="educatie", title="Educație")

# --------------------------
# TAB: Europass Complet
# --------------------------
with tab_europass:
    st.info("Format Europass - complet, toate câmpurile.")
    # ✅ Use the full editor you already have
    render_europass_complete(cv, key_prefix="europass")

    # keep these (optional extras)
    st.markdown("---")
    col_left, col_right = st.columns([3, 1.6], gap="large")
    with col_left:
        # You already edit exp/edu in europass_complete; these can be redundant.
        st.caption("Note: Exp/Edu/Languages/Skills sunt deja în Europass Complete (dacă vrei, pot elimina duplicarea).")
    with col_right:
        render_photo_upload(cv, prefix="europass_")
        st.markdown("---")
        cv["informatii_suplimentare"] = st.text_area(
            "Informatii suplimentare",
            value=cv.get("informatii_suplimentare", ""),
            height=120,
            key="europass_info_supl",
        )
        cv["anexe"] = st.text_area("Anexe", value=cv.get("anexe", ""), height=120, key="europass_anexe")

# ==========================
# Sidebar exports (kept from your old app, but improved with lang selector)
# ==========================
st.sidebar.header("Export")

col_pdf, col_docx = st.sidebar.columns(2)

with col_pdf:
    if st.button("PDF Modern", use_container_width=True):
        try:
            pdf_bytes = generate_pdf_modern(cv, lang=st.session_state.get("export_lang", "en")) if "lang" in generate_pdf_modern.__code__.co_varnames else generate_pdf_modern(cv)
            st.sidebar.download_button(
                label="Descarcă PDF Modern",
                data=pdf_bytes,
                file_name="cv_modern.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.sidebar.error(f"Eroare PDF Modern: {str(e)}")

    if st.button("PDF Europass", use_container_width=True):
        try:
            pdf_bytes = generate_pdf_europass(cv, lang=st.session_state.get("export_lang", "en")) if "lang" in generate_pdf_europass.__code__.co_varnames else generate_pdf_europass(cv)
            st.sidebar.download_button(
                label="Descarcă PDF Europass",
                data=pdf_bytes,
                file_name="cv_europass.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.sidebar.error(f"Eroare PDF Europass: {str(e)}")

with col_docx:
    if st.button("Word Modern", use_container_width=True):
        try:
            docx_bytes = generate_docx_modern(cv, lang=st.session_state.get("export_lang", "en")) if "lang" in generate_docx_modern.__code__.co_varnames else generate_docx_modern(cv)
            st.sidebar.download_button(
                label="Descarcă Word Modern",
                data=docx_bytes,
                file_name="cv_modern.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        except Exception as e:
            st.sidebar.error(f"Eroare Word Modern: {str(e)}")

    if st.button("Word Europass", use_container_width=True):
        try:
            docx_bytes = generate_docx_europass(cv, lang=st.session_state.get("export_lang", "en")) if "lang" in generate_docx_europass.__code__.co_varnames else generate_docx_europass(cv)
            st.sidebar.download_button(
                label="Descarcă Word Europass",
                data=docx_bytes,
                file_name="cv_europass.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        except Exception as e:
            st.sidebar.error(f"Eroare Word Europass: {str(e)}")

st.sidebar.markdown("---")

# Plain text export (kept, but updated to prefer rezumat_bullets)
if st.sidebar.button("Export ATS .txt (plain)", use_container_width=True):
    parts = []
    parts.append(cv.get("nume_prenume", ""))
    parts.append(cv.get("pozitie_vizata", ""))

    parts.append(f"Phone: {cv.get('telefon','')}")
    parts.append(f"Email: {cv.get('email','')}")
    if cv.get("linkedin"):
        parts.append(f"LinkedIn: {cv.get('linkedin')}")
    if cv.get("github"):
        parts.append(f"GitHub: {cv.get('github')}")
    if cv.get("website"):
        parts.append(f"Website: {cv.get('website')}")

    parts.append("")

    # Summary
    bullets = cv.get("rezumat_bullets", [])
    if isinstance(bullets, list) and bullets:
        parts.append("SUMMARY")
        for b in bullets:
            b = str(b).strip()
            if b:
                parts.append(f"• {b}")
        parts.append("")
    elif cv.get("rezumat"):
        parts.append("SUMMARY")
        parts.append(str(cv.get("rezumat", "")).strip())
        parts.append("")

    parts.append("SKILLS")
    for line in [
        cv.get("modern_skills_headline", ""),
        cv.get("modern_tools", ""),
        cv.get("modern_certs", ""),
        cv.get("modern_keywords_extra", ""),
    ]:
        if str(line).strip():
            parts.append(str(line).strip())

    parts.append("")

    if cv.get("experienta"):
        parts.append("EXPERIENCE / PROJECTS")
        for e in cv.get("experienta", []):
            parts.append(f"- {e.get('functie','')} ({e.get('perioada','')})")
            if e.get("tehnologii"):
                parts.append(f"  Tools: {e.get('tehnologii')}")
            if e.get("link"):
                parts.append(f"  Link: {e.get('link')}")
            if e.get("activitati"):
                for b in str(e.get("activitati", "")).splitlines():
                    b = b.strip()
                    if b:
                        parts.append(f"  • {b.lstrip('-• ').strip()}")
        parts.append("")

    if cv.get("educatie"):
        parts.append("EDUCATION")
        for ed in cv.get("educatie", []):
            # your schema uses titlu/organizatie/perioada in newer code
            parts.append(f"- {ed.get('titlu','')} — {ed.get('organizatie','')} ({ed.get('perioada','')})")

    text = "\n".join([p for p in parts if p is not None])
    st.sidebar.download_button(
        "Descarcă ATS.txt",
        text,
        file_name="cv_ats_plain.txt",
        mime="text/plain",
        use_container_width=True,
    )
