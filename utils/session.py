import streamlit as st

# Runtime-only session keys that can cause bloat / rerun loops
RUNTIME_KEYS_PREFIXES = (
    "ats_",        # ATS optimizer temp / widgets
    "rewrite_",    # rewrite suggestions temp / widgets
    "jd_",         # JD Analyzer (Offline) widgets/state
    "profile_",    # profile manager widgets/state
    "modern_",     # modern tab widgets state
    "europass_",   # europass tab widgets state
    "import_",     # import widgets
    "export_",     # export widgets
    "photo_",      # photo widget keys
)

RUNTIME_KEYS_EXACT = {
    "_last_import_sha",
    "json_upload",
    "pdf_upload",
}


def _default_cv() -> dict:
    """
    Single CV dict shared across tabs.
    Keep this aligned with utils/json_io._ensure_defaults().
    """
    return {
        # Core (used in both Modern & Europass)
        "nume_prenume": "",
        "full_name": "",

        # ✅ NEW: short profile line under name
        "profile_line": "",

        # ✅ Target title / headline
        "pozitie_vizata": "",

        # Primary contact fields (exporters read these)
        "telefon": "",
        "email": "",
        "adresa": "",
        "linkedin": "",
        "github": "",
        "website": "",

        # ✅ NEW: contact items list (add/edit/delete)
        "contact_items": [],

        # Summary
        "rezumat": "",          # legacy
        "rezumat_bullets": [],  # preferred

        # Optional photo
        "photo": None,
        "include_photo_modern": False,

        # Experience / Projects
        "experienta": [],

        # Education
        "educatie": [],

        # Languages (Europass)
        "limba_materna": "",
        "limbi_straine": [],

        # Europass detailed skills/competences
        "competente_sociale": "",
        "competente_organizatorice": "",
        "competente_tehnice": "",
        "competente_calculator": "",
        "competente_artistice": "",
        "alte_competente": "",
        "permis_conducere": "",
        "aptitudini_sections": [],  # list of {"category": str, "items": [str,...]}

        # Europass extras
        "nationalitate": "",
        "data_nasterii": "",
        "sex": "",
        "informatii_suplimentare": "",
        "personal_info_extra": [],  # list of {"label": str, "value": str}
        "anexe": "",

        # Modern ATS-friendly skills (short, keyword dense)
        "modern_skills_headline": "",
        "modern_tools": "",
        "modern_certs": "",
        "modern_keywords_extra": "",

        # ATS skills (structured categories)
        "ats_skills": [],

        # ✅ NEW: TECHNICAL SKILLS lines generated from JD analyzer (optional)
        "technical_skills_lines": [],

        # ATS helper
        "job_description": "",

        # ✅ NEW: Job Description Analyzer (Offline) state
        "jd_role_hint": "security engineer",
        "jd_keywords": [],
        "jd_buckets": {},
        "jd_missing": [],
        "jd_coverage": 0.0,
        "jd_templates": [],

        # ✅ NEW: active rewrite templates for current job/profile
        "ats_rewrite_templates_active": [],

        # ATS Profile (YAML profile name)
        "ats_profile": "cyber_security",
    }


def init_session_state():
    """Initialize session state with a single CV dict shared across tabs."""
    if "cv" not in st.session_state or not isinstance(st.session_state.cv, dict):
        st.session_state.cv = _default_cv()

    # Ensure new keys exist for older sessions / imported JSON
    cv = st.session_state.cv
    base = _default_cv()
    for k, v in base.items():
        cv.setdefault(k, v)

    # Backward compatibility: build rezumat_bullets from legacy rezumat if needed
    if (not cv.get("rezumat_bullets")) and cv.get("rezumat"):
        bullets = []
        for line in str(cv.get("rezumat") or "").splitlines():
            s = line.strip().lstrip("-•* ").strip()
            if s:
                bullets.append(s)
        cv["rezumat_bullets"] = bullets

    # Ensure stable types
    cv.setdefault("personal_info_extra", [])
    if not isinstance(cv.get("personal_info_extra"), list):
        cv["personal_info_extra"] = []

    cv.setdefault("aptitudini_sections", [])
    if not isinstance(cv.get("aptitudini_sections"), list):
        cv["aptitudini_sections"] = []

    cv.setdefault("contact_items", [])
    if not isinstance(cv.get("contact_items"), list):
        cv["contact_items"] = []

    cv.setdefault("include_photo_modern", bool(cv.get("include_photo_modern", False)))


def clear_runtime_only():
    """
    Clears runtime-only session keys that can cause state bloat / rerun loops,
    without touching the CV content itself.
    """
    # Exact keys
    for k in list(st.session_state.keys()):
        if k in RUNTIME_KEYS_EXACT:
            st.session_state.pop(k, None)

    # Prefix keys
    for k in list(st.session_state.keys()):
        if any(str(k).startswith(p) for p in RUNTIME_KEYS_PREFIXES):
            st.session_state.pop(k, None)


def reset_ats_only():
    """
    Resets ONLY ATS/JD state (no touch: experienta/educatie/etc).
    """
    if "cv" not in st.session_state or not isinstance(st.session_state.cv, dict):
        return

    cv = st.session_state.cv

    # ATS / JD Analyzer fields
    cv["job_description"] = ""
    cv["jd_role_hint"] = "security engineer"
    cv["jd_keywords"] = []
    cv["jd_buckets"] = {}
    cv["jd_missing"] = []
    cv["jd_coverage"] = 0.0
    cv["jd_templates"] = []

    # ATS outputs
    cv["technical_skills_lines"] = []
    cv["ats_rewrite_templates_active"] = []

    # ATS scoring caches/widgets (if any)
    # keep ats_profile (user selection) intact
    clear_runtime_only()
    st.rerun()


def reset_everything():
    """
    Hard reset: clears CV and runtime keys.

    ✅ Now also resets:
    - ATS Optimizer / keyword match (ats_skills, technical_skills_lines, rewrite templates)
    - Job Description Analyzer (Offline) (jd_* + job_description)
    - Profile line (short)
    - Target title/headline
    """
    st.session_state.cv = _default_cv()
    clear_runtime_only()
    st.session_state.pop("performing_reset", None)
    st.session_state.pop("last_import_error", None)
    st.rerun()
