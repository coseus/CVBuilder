import streamlit as st
from components.list_editor import render_string_list_editor


DEFAULT_SKILL_CATEGORIES = [
    "Security",
    "Networking",
    "Cloud",
    "Windows/Linux",
    "Scripting/Automation",
    "Tools",
    "Certifications",
]


def render_ats_skills(cv: dict, key_prefix: str = "ats_sk"):
    """
    ATS skills editor with categories.
    Stored in cv["ats_skills"] = [{"category": str, "items": [str,...]}]
    Also auto-fills legacy modern_* fields for exports.
    """
    cv.setdefault("ats_skills", [])
    if not isinstance(cv["ats_skills"], list) or not cv["ats_skills"]:
        cv["ats_skills"] = [{"category": c, "items": []} for c in DEFAULT_SKILL_CATEGORIES]

    st.subheader("Skills (ATS-friendly)")

    # Category management
    with st.expander("Manage categories", expanded=False):
        cats = [x.get("category", "") for x in cv["ats_skills"] if isinstance(x, dict)]
        cats = render_string_list_editor("Category", cats, key_prefix=f"{key_prefix}_cats", placeholder="Category name")
        # rebuild preserving items where possible
        new = []
        old_map = {x.get("category"): x.get("items", []) for x in cv["ats_skills"] if isinstance(x, dict)}
        for c in cats:
            new.append({"category": c, "items": old_map.get(c, []) if isinstance(old_map.get(c, []), list) else []})
        cv["ats_skills"] = new

    # Edit items per category
    for idx, sec in enumerate(cv["ats_skills"]):
        if not isinstance(sec, dict):
            continue
        sec.setdefault("category", f"Category {idx+1}")
        sec.setdefault("items", [])

        with st.expander(sec["category"], expanded=True):
            sec["items"] = render_string_list_editor(
                label="Skill",
                items=sec.get("items", []),
                key_prefix=f"{key_prefix}_cat_{idx}",
                placeholder="ex: Active Directory, Azure AD, SIEM, Nessus, Burp Suite...",
            )

    # Backward-compatible export fields (modern_*)
    # - headline = compact category summary
    # - tools = Tools category
    # - certs = Certifications category
    # - extra keywords = everything else
    cats = {s["category"].lower(): s.get("items", []) for s in cv["ats_skills"] if isinstance(s, dict)}

    def _join(items):
        return "\n".join([str(x) for x in items if str(x).strip()])

    tools = cats.get("tools", [])
    certs = cats.get("certifications", [])
    rest = []
    for k, v in cats.items():
        if k in ("tools", "certifications"):
            continue
        rest.extend(v if isinstance(v, list) else [])

    cv["modern_tools"] = _join(tools)
    cv["modern_certs"] = _join(certs)
    cv["modern_keywords_extra"] = _join(rest)

    headline_parts = []
    for s in cv["ats_skills"]:
        if isinstance(s, dict) and s.get("category") and s.get("items"):
            headline_parts.append(s["category"])
    cv["modern_skills_headline"] = " • ".join(headline_parts[:6])
