import streamlit as st
from utils.job_profiles import list_job_profiles, save_job_profile, load_job_profile, delete_job_profile


def _current_job_payload(cv: dict) -> dict:
    return {
        "role_hint": cv.get("jd_role_hint", "security engineer"),
        "job_description": cv.get("job_description", ""),
        "jd_keywords": cv.get("jd_keywords", []),
        "jd_buckets": cv.get("jd_buckets", {}),
        "jd_missing": cv.get("jd_missing", []),
        "jd_coverage": cv.get("jd_coverage", 0.0),
        "jd_templates": cv.get("jd_templates", []),
        "technical_skills_lines": cv.get("technical_skills_lines", []),
        "ats_rewrite_templates_active": cv.get("ats_rewrite_templates_active", []),
        "ats_profile": cv.get("ats_profile", "cyber_security"),
    }


def _apply_payload_to_cv(cv: dict, payload: dict):
    cv["jd_role_hint"] = payload.get("role_hint", cv.get("jd_role_hint", "security engineer"))
    cv["job_description"] = payload.get("job_description", "")
    cv["jd_keywords"] = payload.get("jd_keywords", [])
    cv["jd_buckets"] = payload.get("jd_buckets", {})
    cv["jd_missing"] = payload.get("jd_missing", [])
    cv["jd_coverage"] = payload.get("jd_coverage", 0.0)
    cv["jd_templates"] = payload.get("jd_templates", [])

    # apply-to-export helpers
    cv["technical_skills_lines"] = payload.get("technical_skills_lines", [])
    cv["ats_rewrite_templates_active"] = payload.get("ats_rewrite_templates_active", payload.get("jd_templates", []))

    # keep ATS profile if stored
    if payload.get("ats_profile"):
        cv["ats_profile"] = payload.get("ats_profile")


def render_job_profile_manager(cv: dict):
    st.subheader("Job Profiles (persist per job)")

    profiles = list_job_profiles()
    options = ["— none —"] + [f"{p.get('name','(no name)')}  •  {p.get('saved_at','')}" for p in profiles]
    idx = 0

    pick = st.selectbox("Saved job profiles", options, index=idx, key="jobprof_pick")

    selected = None
    selected_file = None
    if pick != "— none —":
        i = options.index(pick) - 1
        selected = profiles[i]
        selected_file = selected.get("_file")

    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("↻ Refresh list", use_container_width=True, key="jobprof_refresh"):
            st.rerun()

    with c2:
        if selected_file and st.button("Load & Apply", use_container_width=True, key="jobprof_load_apply"):
            payload = load_job_profile(selected_file) or {}
            _apply_payload_to_cv(cv, payload)
            st.success("Applied job profile to ATS/JD.")
            st.rerun()

    with c3:
        if selected_file and st.button("Delete", use_container_width=True, key="jobprof_delete"):
            ok = delete_job_profile(selected_file)
            if ok:
                st.success("Deleted.")
                st.rerun()
            else:
                st.error("Delete failed.")

    st.markdown("---")
    st.markdown("### Save current JD analysis as a job profile")
    name = st.text_input(
        "Profile name",
        key="jobprof_new_name",
        placeholder="e.g., Company - Role - 2026-01",
    )

    colA, colB = st.columns([2, 1])
    with colA:
        st.caption("This saves JD + extracted keywords + templates + generated TECHNICAL SKILLS.")
    with colB:
        if st.button("Save", use_container_width=True, key="jobprof_save"):
            if not name.strip():
                st.warning("Please enter a profile name.")
            else:
                payload = _current_job_payload(cv)
                fn = save_job_profile(payload, name.strip())
                st.success(f"Saved: {fn}")
                st.rerun()

    if selected:
        with st.expander("Preview selected profile", expanded=False):
            st.write(selected)
