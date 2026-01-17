import json
import base64

DEFAULT_PROFILE = "cyber_security"


def _sync_primary_from_contact_items(cv: dict) -> dict:
    """
    Ensure primary fields are filled from contact_items:
    - email, telefon, adresa, linkedin, github, website
    """
    if not isinstance(cv, dict):
        return cv

    contacts = cv.get("contact_items", [])
    if not isinstance(contacts, list):
        return cv

    # Map contact type -> primary field name
    type_to_field = {
        "email": "email",
        "phone": "telefon",
        "location": "adresa",
        "linkedin": "linkedin",
        "github": "github",
        "website": "website",
    }

    # If primary field empty, fill with first matching contact_items value
    for t, field in type_to_field.items():
        if str(cv.get(field, "")).strip():
            continue  # already set
        for it in contacts:
            if not isinstance(it, dict):
                continue
            if it.get("type") != t:
                continue
            val = str(it.get("value", "")).strip()
            if val:
                cv[field] = val
                break

    # Optional: also backfill full_name/nume_prenume if one is missing
    if not str(cv.get("nume_prenume", "")).strip() and str(cv.get("full_name", "")).strip():
        cv["nume_prenume"] = cv["full_name"]
    if not str(cv.get("full_name", "")).strip() and str(cv.get("nume_prenume", "")).strip():
        cv["full_name"] = cv["nume_prenume"]

    return cv


def _safe_str(x) -> str:
    return "" if x is None else str(x)


def _ensure_defaults(cv: dict) -> dict:
    if not isinstance(cv, dict):
        return {}

    cv.setdefault("ats_profile", DEFAULT_PROFILE)

    # Modern + shared
    cv.setdefault("nume_prenume", "")
    cv.setdefault("pozitie_vizata", "")
    cv.setdefault("telefon", "")
    cv.setdefault("email", "")
    cv.setdefault("adresa", "")
    cv.setdefault("linkedin", "")
    cv.setdefault("github", "")
    cv.setdefault("website", "")

    cv.setdefault("personal_info_extra", [])  # list[{label,value}]

    # Summary bullets
    cv.setdefault("rezumat", "")
    cv.setdefault("rezumat_bullets", [])
    if (not cv.get("rezumat_bullets")) and cv.get("rezumat"):
        bullets = []
        for line in str(cv.get("rezumat") or "").splitlines():
            s = line.strip().lstrip("-•* ").strip()
            if s:
                bullets.append(s)
        cv["rezumat_bullets"] = bullets

    # Lists
    cv.setdefault("experienta", [])
    cv.setdefault("educatie", [])
    cv.setdefault("limbi_straine", [])

    # Modern skills (ATS-friendly)
    cv.setdefault("modern_skills_headline", "")
    cv.setdefault("modern_tools", "")
    cv.setdefault("modern_certs", "")
    cv.setdefault("modern_keywords_extra", "")

    # Europass fields
    cv.setdefault("limba_materna", "")
    cv.setdefault("competente_sociale", "")
    cv.setdefault("competente_organizatorice", "")
    cv.setdefault("competente_tehnice", "")
    cv.setdefault("competente_calculator", "")
    cv.setdefault("competente_artistice", "")
    cv.setdefault("alte_competente", "")
    cv.setdefault("aptitudini_sections", [])  # list[{category, items:[...]}]
    cv.setdefault("permis_conducere", "")

    # Extras
    cv.setdefault("informatii_suplimentare", "")
    cv.setdefault("anexe", "")

    # Photo
    cv.setdefault("photo", None)
    cv.setdefault("include_photo_modern", bool(cv.get("include_photo_modern", False)))

    # ATS helper
    cv.setdefault("job_description", "")

    return cv


def _first_lang_value(v, prefer="ro"):
    if isinstance(v, dict):
        return v.get(prefer) or v.get("en") or next(iter(v.values()), "")
    return v


def _normalize_incoming_schema(data: dict) -> dict:
    """
    Normalizes:
      A) app-native schema (already has nume_prenume / experienta / educatie etc)
      B) bilingual/minimal schema with keys:
         personal_info, summary, skills, experience, education, certifications, languages, other
    """
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object (dict).")

    # A) Already app-native
    if "experienta" in data or "educatie" in data or "nume_prenume" in data:
        return data

    # B) Bilingual/minimal schema
    out = {}

    out["ats_profile"] = data.get("ats_profile", DEFAULT_PROFILE)

    # ---- personal_info ----
    pi = data.get("personal_info", {})
    if isinstance(pi, dict):
        out["nume_prenume"] = _safe_str(pi.get("full_name"))

        headline = pi.get("headline", "")
        out["pozitie_vizata"] = _safe_str(_first_lang_value(headline, prefer="ro"))

        contact = pi.get("contact", {}) if isinstance(pi.get("contact", {}), dict) else {}
        out["email"] = _safe_str(contact.get("email"))
        out["telefon"] = _safe_str(contact.get("phone"))

        loc = pi.get("location", {}) if isinstance(pi.get("location", {}), dict) else {}
        city = _safe_str(loc.get("city")).strip()
        country = _safe_str(loc.get("country")).strip()
        out["adresa"] = ", ".join([x for x in [city, country] if x]).strip(", ")

        links = pi.get("links", {}) if isinstance(pi.get("links", {}), dict) else {}
        out["linkedin"] = _safe_str(links.get("linkedin"))
        out["github"] = _safe_str(links.get("github"))
        out["website"] = _safe_str(links.get("website"))

        # extra fields
        out["personal_info_extra"] = []
        ef = pi.get("extra_fields", [])
        if isinstance(ef, list):
            for item in ef:
                if not isinstance(item, dict):
                    continue
                label = item.get("label", "")
                label = _safe_str(_first_lang_value(label, prefer="ro"))
                value = _safe_str(item.get("value"))
                if label and value:
                    out["personal_info_extra"].append({"label": label, "value": value})

    # ---- summary ----
    summ = data.get("summary", {})
    bullets = []
    if isinstance(summ, dict):
        b = summ.get("bullets")
        if isinstance(b, dict):
            bullets = b.get("ro") or b.get("en") or []
        elif isinstance(b, list):
            bullets = b
    out["rezumat_bullets"] = [_safe_str(x).strip() for x in bullets if _safe_str(x).strip()]

    # ---- skills ----
    skills = data.get("skills", {})
    if isinstance(skills, dict):
        modern = skills.get("modern_ats_friendly", {})
        if isinstance(modern, dict):
            out["modern_skills_headline"] = _safe_str(modern.get("headline"))

            tools = modern.get("tools", [])
            if isinstance(tools, list):
                out["modern_tools"] = "\n".join([_safe_str(x) for x in tools if _safe_str(x).strip()])
            else:
                out["modern_tools"] = _safe_str(tools)

            certs = modern.get("certifications", [])
            if isinstance(certs, list):
                out["modern_certs"] = "\n".join([_safe_str(x) for x in certs if _safe_str(x).strip()])
            else:
                out["modern_certs"] = _safe_str(certs)

            extra = modern.get("extra_keywords", [])
            if isinstance(extra, list):
                out["modern_keywords_extra"] = "\n".join([_safe_str(x) for x in extra if _safe_str(x).strip()])
            else:
                out["modern_keywords_extra"] = _safe_str(extra)

        euro = skills.get("europass", {})
        # Map Europass general skills to aptitudini_sections
        out["aptitudini_sections"] = out.get("aptitudini_sections", [])
        if isinstance(euro, dict):
            gs = euro.get("general_skills", {})
            if isinstance(gs, dict):
                ro_list = gs.get("ro") or []
                en_list = gs.get("en") or []
                items = ro_list if ro_list else en_list
                if items:
                    out["aptitudini_sections"].append({
                        "category": "Aptitudini și competențe personale",
                        "items": [_safe_str(x) for x in items if _safe_str(x).strip()]
                    })

            tech = euro.get("technical_skills", [])
            if isinstance(tech, list) and tech:
                out["competente_tehnice"] = ", ".join([_safe_str(x) for x in tech if _safe_str(x).strip()])

    # ---- experience -> experienta ----
    out["experienta"] = []
    exp = data.get("experience", [])
    if isinstance(exp, list):
        for e in exp:
            if not isinstance(e, dict):
                continue

            role = e.get("role", "")
            role = _safe_str(_first_lang_value(role, prefer="ro"))

            company = _safe_str(e.get("company"))
            location = _safe_str(e.get("location"))

            start = _safe_str(e.get("start"))
            end = e.get("end")
            end_str = "Present" if end in (None, "", "null") else _safe_str(end)

            highlights = e.get("highlights", [])
            if isinstance(highlights, dict):
                highlights = highlights.get("ro") or highlights.get("en") or []
            if isinstance(highlights, str):
                highlights = [highlights]
            highlights_text = "\n".join([f"- {_safe_str(x).strip()}" for x in highlights if _safe_str(x).strip()])

            out["experienta"].append({
                # ✅ new field for project title
                "titlu": company if company else role,
                "perioada": f"{start} - {end_str}".strip(),
                "functie": role,
                "angajator": company,
                "locatie": location,
                "activitati": highlights_text,
                "sector": "",
                "tehnologii": "",
                "link": ""
            })

    # ---- education -> educatie ----
    out["educatie"] = []
    edu = data.get("education", [])
    if isinstance(edu, list):
        for ed in edu:
            if not isinstance(ed, dict):
                continue

            deg = ed.get("degree", "")
            deg = _safe_str(_first_lang_value(deg, prefer="ro"))

            institution = _safe_str(ed.get("institution"))
            location = _safe_str(ed.get("location"))

            sy = _safe_str(ed.get("start_year"))
            ey = _safe_str(ed.get("end_year"))
            perio = " - ".join([x for x in [sy, ey] if x]).strip()

            out["educatie"].append({
                "perioada": perio,
                "titlu": deg,                 # ✅ fixes “Fără titlu”
                "organizatie": institution,   # ✅ fills institution
                "locatie": location,
                "descriere": ""
            })

    # ---- languages (Europass) ----
    langs = data.get("languages", [])
    out["limbi_straine"] = []
    if isinstance(langs, list) and langs:
        # first one as mother tongue only if marked; otherwise keep mother tongue empty
        # If your JSON doesn’t specify mother tongue, we keep it blank.
        for l in langs:
            if not isinstance(l, dict):
                continue
            name = l.get("language", "")
            name = _safe_str(_first_lang_value(name, prefer="ro"))
            lvl = l.get("level", "")
            lvl = _safe_str(_first_lang_value(lvl, prefer="ro"))
            if name:
                out["limbi_straine"].append({"limba": name, "nivel": lvl})

    # ---- driving license ----
    other = data.get("other", {})
    if isinstance(other, dict):
        dl = other.get("driving_license", [])
        if isinstance(dl, list) and dl:
            out["permis_conducere"] = ", ".join([_safe_str(x) for x in dl if _safe_str(x).strip()])

    return out


def import_cv_json(json_text: str) -> dict:
    if not isinstance(json_text, str) or not json_text.strip():
        raise ValueError("Empty JSON input.")

    # 1) Parse
    data = json.loads(json_text)

    # 2) Restore bytes if the JSON contains base64-wrapped binary blobs (optional)
    data = _restore_bytes(data)

    # 3) Normalize schema (app-native OR bilingual/minimal)
    normalized = _normalize_incoming_schema(data)

    # 4) Ensure defaults
    normalized = _ensure_defaults(normalized)

    # 5) Sync primary fields from contact_items (important!)
    normalized = _sync_primary_from_contact_items(normalized)

    return normalized


def _json_safe(obj, include_photo_base64: bool = False):
    """
    Convert cv dict into JSON-safe structure.
    - bytes are removed by default (photo bytes)
    - optionally encode bytes as base64 if include_photo_base64=True
    """
    if obj is None:
        return None

    # bytes: photo or binary blobs
    if isinstance(obj, (bytes, bytearray)):
        if include_photo_base64:
            return {
                "__type__": "bytes_base64",
                "data": base64.b64encode(bytes(obj)).decode("ascii")
            }
        return None  # drop by default

    # primitives
    if isinstance(obj, (str, int, float, bool)):
        return obj

    # dict
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            # common photo keys (drop even if include_photo_base64 is False)
            if str(k).lower() in {"photo", "photo_bytes", "image", "image_bytes", "photo_data"}:
                safe_v = _json_safe(v, include_photo_base64=include_photo_base64)
                if include_photo_base64 and safe_v is not None:
                    out[k] = safe_v
                continue

            safe_v = _json_safe(v, include_photo_base64=include_photo_base64)
            # keep keys even if value is None? (for stability) -> drop Nones
            if safe_v is not None:
                out[k] = safe_v
        return out

    # list/tuple
    if isinstance(obj, (list, tuple)):
        out_list = []
        for v in obj:
            safe_v = _json_safe(v, include_photo_base64=include_photo_base64)
            if safe_v is not None:
                out_list.append(safe_v)
        return out_list

    # fallback: stringify unknown objects
    return str(obj)
    
def _restore_bytes(obj):
    if isinstance(obj, dict):
        if obj.get("__type__") == "bytes_base64" and "data" in obj:
            return base64.b64decode(obj["data"].encode("ascii"))
        return {k: _restore_bytes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_restore_bytes(x) for x in obj]
    return obj

def export_cv_json(cv: dict, include_photo_base64: bool = False) -> str:
    """
    Export CV as JSON. By default drops binary blobs (photo bytes),
    so export never crashes.
    """
    cv = _sync_primary_from_contact_items(cv)
    safe = _json_safe(cv, include_photo_base64=include_photo_base64)
    return json.dumps(safe, ensure_ascii=False, indent=2)
