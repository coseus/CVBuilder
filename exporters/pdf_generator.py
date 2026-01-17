from __future__ import annotations

from io import BytesIO
from typing import List, Dict, Any, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    ListFlowable,
    ListItem,
    Image,
)

def _sync_primary_from_contact_items(cv: dict) -> dict:
    if not isinstance(cv, dict):
        return cv

    contacts = cv.get("contact_items", [])
    if not isinstance(contacts, list):
        return cv

    type_to_field = {
        "email": "email",
        "phone": "telefon",
        "location": "adresa",
        "linkedin": "linkedin",
        "github": "github",
        "website": "website",
    }

    for t, field in type_to_field.items():
        if str(cv.get(field, "")).strip():
            continue
        for it in contacts:
            if not isinstance(it, dict):
                continue
            if it.get("type") != t:
                continue
            val = str(it.get("value", "")).strip()
            if val:
                cv[field] = val
                break

    # backfill names
    if not str(cv.get("nume_prenume", "")).strip() and str(cv.get("full_name", "")).strip():
        cv["nume_prenume"] = cv["full_name"]
    if not str(cv.get("full_name", "")).strip() and str(cv.get("nume_prenume", "")).strip():
        cv["full_name"] = cv["nume_prenume"]

    return cv


def _try_register_font():
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
    ]
    for p in candidates:
        try:
            pdfmetrics.registerFont(TTFont("DejaVuSans", p))
            return "DejaVuSans"
        except Exception:
            continue
    return "Helvetica"


BASE_FONT = _try_register_font()


def _styles():
    ss = getSampleStyleSheet()

    ss["Normal"].fontName = BASE_FONT
    ss["Normal"].fontSize = 10
    ss["Normal"].leading = 13

    ss["Title"].fontName = BASE_FONT
    ss["Title"].fontSize = 18
    ss["Title"].leading = 22

    h = ParagraphStyle(
        "H",
        parent=ss["Normal"],
        fontName=BASE_FONT,
        fontSize=12,
        leading=16,
        spaceBefore=10,
        spaceAfter=6,
        textColor=colors.black,
    )
    ss.add(h)

    small = ParagraphStyle(
        "Small",
        parent=ss["Normal"],
        fontName=BASE_FONT,
        fontSize=9,
        leading=12,
        textColor=colors.black,
    )
    ss.add(small)

    muted = ParagraphStyle(
        "Muted",
        parent=ss["Normal"],
        fontName=BASE_FONT,
        fontSize=9,
        leading=12,
        textColor=colors.grey,
    )
    ss.add(muted)

    profile = ParagraphStyle(
        "ProfileLine",
        parent=ss["Normal"],
        fontName=BASE_FONT,
        fontSize=10,
        leading=13,
        textColor=colors.black,
        spaceAfter=2,
    )
    ss.add(profile)

    return ss


def _get_photo_bytes(cv: dict) -> Optional[bytes]:
    b = cv.get("photo")
    if isinstance(b, (bytes, bytearray)) and len(b) > 0:
        return bytes(b)
    return None


def _p(text: str, style) -> Paragraph:
    return Paragraph((text or "").replace("\n", "<br/>"), style)


def _split_lines(text: str) -> List[str]:
    if not text:
        return []
    return [x.strip() for x in str(text).splitlines() if x.strip()]


def _bullet_list(lines: List[str], style) -> ListFlowable:
    items = []
    for line in lines:
        t = (line or "").strip()
        if not t:
            continue
        t = t.lstrip("-•* ").strip()
        items.append(ListItem(_p(t, style), leftIndent=14))
    return ListFlowable(items, bulletType="bullet", leftIndent=14)


def _header_table(left_flowables: List[Any], right_flowable: Any = "") -> Table:
    tbl = Table([[left_flowables, right_flowable]], colWidths=[5.9 * inch, 1.3 * inch])
    tbl.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return tbl


def _write_section_title(elements, title: str, ss):
    elements.append(_p(title, ss["H"]))


def _modern_contact_line(cv: dict) -> str:
    city = ""
    availability = ""

    extras = cv.get("personal_info_extra", [])
    if isinstance(extras, list):
        for it in extras:
            if not isinstance(it, dict):
                continue
            lab = (it.get("label") or "").strip().lower()
            if lab in ("city", "oraș", "oras", "localitate"):
                city = it.get("value", "") or ""
            if lab in ("availability", "disponibilitate"):
                availability = it.get("value", "") or ""

    if not city:
        city = cv.get("adresa", "") or ""

    parts = []
    if city:
        parts.append(f"City: {city}")
    if availability:
        parts.append(f"Availability: {availability}")

    links = []
    if cv.get("email"):
        links.append(f"Email: {cv.get('email')}")
    if cv.get("telefon"):
        links.append(f"Phone: {cv.get('telefon')}")
    if cv.get("linkedin"):
        links.append(f"LinkedIn: {cv.get('linkedin')}")
    if cv.get("github"):
        links.append(f"GitHub: {cv.get('github')}")
    if cv.get("website"):
        links.append(f"Website: {cv.get('website')}")

    left = " | ".join([p for p in parts if p])
    right = " | ".join([p for p in links if p])
    if left and right:
        return f"{left}<br/>{right}"
    return left or right


def _skills_map_from_ats(cv: dict) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    skills = cv.get("ats_skills", [])
    if isinstance(skills, list):
        for sec in skills:
            if not isinstance(sec, dict):
                continue
            cat = (sec.get("category") or "").strip()
            items = sec.get("items", [])
            if cat and isinstance(items, list):
                out[cat.lower()] = [str(x).strip() for x in items if str(x).strip()]
    return out


def _build_technical_skills_lines(cv: dict) -> List[str]:
    """
    Build grouped 'TECHNICAL SKILLS' lines like:
    • Cloud & Identity: Azure, Azure AD...
    """
    m = _skills_map_from_ats(cv)

    # Fallback: if ats_skills empty, try to derive from modern_* (best-effort)
    if not m:
        m = {}
        if cv.get("modern_tools"):
            m["tools"] = _split_lines(cv.get("modern_tools", ""))
        if cv.get("modern_certs"):
            m["certifications"] = _split_lines(cv.get("modern_certs", ""))
        if cv.get("modern_keywords_extra"):
            # dump keywords into security/tools buckets later
            m["keywords"] = _split_lines(cv.get("modern_keywords_extra", ""))

    def uniq(items: List[str]) -> List[str]:
        seen = set()
        out = []
        for x in items:
            k = x.strip()
            if not k:
                continue
            lk = k.lower()
            if lk in seen:
                continue
            seen.add(lk)
            out.append(k)
        return out

    # Define target groups (your exact structure)
    cloud_identity = uniq(m.get("cloud", []) + m.get("identity", []) + m.get("cloud & identity", []) )
    security = uniq(m.get("security", []) + m.get("keywords", []))
    networking = uniq(m.get("networking", []) + m.get("network", []))
    os_servers = uniq(m.get("windows/linux", []) + m.get("windows", []) + m.get("linux", []) + m.get("os & servers", []))
    scripting = uniq(m.get("scripting/automation", []) + m.get("automation", []) + m.get("scripting", []))
    tools = uniq(m.get("tools", []) )
    virtualization = uniq(m.get("virtualization", []) )

    # Smart routing (so keywords don’t make Security explode)
    # If Security is huge, keep only security-ish keywords and move OS/network keywords to their groups.
    sec_only = []
    moved_to_net = []
    moved_to_os = []
    for x in security:
        lx = x.lower()
        if any(k in lx for k in ["cisco", "vlan", "vpn", "firewall", "routing", "switch"]):
            moved_to_net.append(x)
        elif any(k in lx for k in ["windows", "linux", "active directory", "ad", "gpo", "server", "hyper-v", "vmware", "virtual"]):
            moved_to_os.append(x)
        else:
            sec_only.append(x)
    security = uniq(sec_only)
    networking = uniq(networking + moved_to_net)
    os_servers = uniq(os_servers + moved_to_os)

    # Merge cloud tools (Azure AD / Entra, M365 admin) if they exist in Tools
    # (helps the exact example output)
    for x in tools[:]:
        lx = x.lower()
        if any(k in lx for k in ["azure", "entra", "azure ad", "microsoft 365", "m365"]):
            cloud_identity.append(x)
            tools.remove(x)
    cloud_identity = uniq(cloud_identity)

    lines = []

    def add_group(title: str, items: List[str]):
        items = uniq(items)
        if items:
            lines.append(f"<b>{title}:</b> " + ", ".join(items))

    add_group("Cloud & Identity", cloud_identity)
    add_group("Security", security)
    add_group("Networking", networking)
    add_group("OS & Servers", os_servers)
    add_group("Scripting & Automation", scripting)
    add_group("Tools", tools)
    add_group("Virtualization", virtualization)

    # Certifications: keep as separate line inside the same section (not separate section)
    certs = uniq(m.get("certifications", []))
    if certs:
        add_group("Certifications", certs)

    return lines


def generate_pdf_modern(cv: dict, lang: str = "en") -> bytes:
    cv = _sync_primary_from_contact_items(cv)
    ss = _styles()
    buf = BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
        title="CV Modern",
    )

    elements: List[Any] = []

    # ---------------- Header ----------------
    name = cv.get("nume_prenume") or cv.get("full_name") or "Full Name"
    header_left: List[Any] = []
    header_left.append(_p(str(name), ss["Title"]))

    # ✅ NEW: profile line under name
    profile_line = (cv.get("profile_line") or "").strip()
    if profile_line:
        header_left.append(_p(profile_line, ss["ProfileLine"]))

    headline = cv.get("pozitie_vizata", "")
    if headline:
        header_left.append(_p(str(headline), ss["Muted"]))

    header_left.append(Spacer(1, 6))
    header_left.append(_p(_modern_contact_line(cv), ss["Small"]))

    right = ""
    photo = _get_photo_bytes(cv)
    if cv.get("include_photo_modern") and photo:
        try:
            img = Image(BytesIO(photo))
            img.drawHeight = 1.15 * inch
            img.drawWidth = 1.15 * inch
            right = img
        except Exception:
            right = ""

    elements.append(_header_table(header_left, right))
    elements.append(Spacer(1, 10))

    # ---------------- SUMMARY ----------------
    bullets = cv.get("rezumat_bullets", [])
    if isinstance(bullets, list) and any(str(x).strip() for x in bullets):
        _write_section_title(elements, "SUMMARY", ss)
        elements.append(_bullet_list([str(x) for x in bullets], ss["Normal"]))
        elements.append(Spacer(1, 8))
    else:
        rez = cv.get("rezumat", "")
        if rez:
            _write_section_title(elements, "SUMMARY", ss)
            elements.append(_p(str(rez), ss["Normal"]))
            elements.append(Spacer(1, 8))

    # ✅ TECHNICAL SKILLS (single structured section)
    tech_lines = cv.get("technical_skills_lines") or _build_technical_skills_lines(cv)
    if tech_lines:
        _write_section_title(elements, "TECHNICAL SKILLS", ss)
        elements.append(_bullet_list(tech_lines, ss["Normal"]))
        elements.append(Spacer(1, 8))

    # ✅ PROFESSIONAL EXPERIENCE (renamed)
    exp = cv.get("experienta", [])
    if isinstance(exp, list) and exp:
        _write_section_title(elements, "PROFESSIONAL EXPERIENCE", ss)
        for e in exp:
            if not isinstance(e, dict):
                continue

            company = e.get("titlu") or e.get("angajator") or ""
            period = e.get("perioada") or ""
            role = e.get("functie") or ""

            title_line = company
            if role:
                title_line = f"{role} — {company}" if company else role
            if period:
                title_line = f"{title_line} — {period}" if title_line else period

            elements.append(_p(f"<b>{title_line}</b>", ss["Normal"]))

            loc = e.get("locatie", "")
            if loc:
                elements.append(_p(f"<i>Location:</i> {loc}", ss["Small"]))

            acts = _split_lines(e.get("activitati", ""))
            if acts:
                elements.append(_bullet_list(acts, ss["Normal"]))

            elements.append(Spacer(1, 6))

        elements.append(Spacer(1, 6))

    # ---------------- EDUCATION ----------------
    edu = cv.get("educatie", [])
    if isinstance(edu, list) and edu:
        _write_section_title(elements, "EDUCATION", ss)
        for ed in edu:
            if not isinstance(ed, dict):
                continue
            per = ed.get("perioada", "")
            tit = ed.get("titlu", "")
            org = ed.get("organizatie", "")
            line = " — ".join([x for x in [per, tit] if x])
            if org:
                line = f"{line}<br/>{org}" if line else str(org)
            elements.append(_p(line, ss["Normal"]))
            elements.append(Spacer(1, 4))

    doc.build(elements)
    return buf.getvalue()


def generate_pdf_europass(cv: dict, lang: str = "en") -> bytes:
    cv = _sync_primary_from_contact_items(cv)
    ss = _styles()
    buf = BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
        title="CV Europass",
    )

    elements: List[Any] = []

    name = cv.get("nume_prenume") or cv.get("full_name") or "Full Name"
    header_left: List[Any] = []
    header_left.append(_p(str(name), ss["Title"]))
    header_left.append(_p("CURRICULUM VITAE (Europass)", ss["Muted"]))
    header_left.append(Spacer(1, 6))

    # ✅ Profile line also useful in Europass (optional)
    profile_line = (cv.get("profile_line") or "").strip()
    if profile_line:
        header_left.append(_p(profile_line, ss["ProfileLine"]))

    extras = cv.get("personal_info_extra", [])
    city = ""
    availability = ""
    if isinstance(extras, list):
        for it in extras:
            if not isinstance(it, dict):
                continue
            lab = (it.get("label") or "").strip().lower()
            if lab in ("city", "oraș", "oras", "localitate"):
                city = it.get("value", "") or ""
            if lab in ("availability", "disponibilitate"):
                availability = it.get("value", "") or ""
    parts = []
    if city:
        parts.append(f"City: {city}")
    if availability:
        parts.append(f"Availability: {availability}")
    if parts:
        header_left.append(_p(" | ".join(parts), ss["Small"]))

    right = ""
    photo = _get_photo_bytes(cv)
    if photo:
        try:
            img = Image(BytesIO(photo))
            img.drawHeight = 1.25 * inch
            img.drawWidth = 1.25 * inch
            right = img
        except Exception:
            right = ""

    elements.append(_header_table(header_left, right))
    elements.append(Spacer(1, 12))

    _write_section_title(elements, "PERSONAL INFORMATION", ss)
    info_lines = []
    if cv.get("email"):
        info_lines.append(f"Email: {cv.get('email')}")
    if cv.get("telefon"):
        info_lines.append(f"Phone: {cv.get('telefon')}")
    if cv.get("adresa"):
        info_lines.append(f"Location: {cv.get('adresa')}")
    if cv.get("linkedin"):
        info_lines.append(f"LinkedIn: {cv.get('linkedin')}")
    if cv.get("github"):
        info_lines.append(f"GitHub: {cv.get('github')}")
    if cv.get("website"):
        info_lines.append(f"Website: {cv.get('website')}")

    if isinstance(extras, list):
        for it in extras:
            if not isinstance(it, dict):
                continue
            lab = (it.get("label") or "").strip()
            val = (it.get("value") or "").strip()
            if lab and val and lab.lower() not in ("city", "oraș", "oras", "localitate", "availability", "disponibilitate"):
                info_lines.append(f"{lab}: {val}")

    if info_lines:
        elements.append(_bullet_list(info_lines, ss["Normal"]))
    elements.append(Spacer(1, 8))

    exp = cv.get("experienta", [])
    if isinstance(exp, list) and exp:
        _write_section_title(elements, "WORK EXPERIENCE", ss)
        for e in exp:
            if not isinstance(e, dict):
                continue
            role = e.get("functie") or ""
            company = e.get("angajator") or e.get("titlu") or ""
            period = e.get("perioada") or ""
            title = " — ".join([x for x in [role, period] if x])
            elements.append(_p(f"<b>{title}</b>", ss["Normal"]))
            if company:
                elements.append(_p(str(company), ss["Small"]))
            loc = e.get("locatie") or ""
            if loc:
                elements.append(_p(f"Location: {loc}", ss["Small"]))
            acts = _split_lines(e.get("activitati", ""))
            if acts:
                elements.append(_bullet_list(acts, ss["Normal"]))
            elements.append(Spacer(1, 6))
        elements.append(Spacer(1, 6))

    edu = cv.get("educatie", [])
    if isinstance(edu, list) and edu:
        _write_section_title(elements, "EDUCATION AND TRAINING", ss)
        for ed in edu:
            if not isinstance(ed, dict):
                continue
            per = ed.get("perioada", "")
            tit = ed.get("titlu", "")
            org = ed.get("organizatie", "")
            line = " — ".join([x for x in [per, tit] if x])
            if org:
                line = f"{line}<br/>{org}" if line else str(org)
            elements.append(_p(line, ss["Normal"]))
            elements.append(Spacer(1, 4))
        elements.append(Spacer(1, 6))

    _write_section_title(elements, "LANGUAGE SKILLS", ss)
    mother = cv.get("limba_materna", "")
    if mother:
        elements.append(_p(f"<b>Mother tongue:</b> {mother}", ss["Normal"]))

    langs = cv.get("limbi_straine", [])
    if isinstance(langs, list) and langs:
        lines = []
        for l in langs:
            if not isinstance(l, dict):
                continue
            nm = l.get("limba", "")
            lvl = l.get("nivel", "") or l.get("ascultare", "")
            if nm:
                lines.append(f"{nm}: {lvl}".strip())
        if lines:
            elements.append(_bullet_list(lines, ss["Normal"]))
    elements.append(Spacer(1, 6))

    _write_section_title(elements, "PERSONAL SKILLS", ss)
    secs = cv.get("aptitudini_sections", [])
    if isinstance(secs, list) and secs:
        for sec in secs:
            if not isinstance(sec, dict):
                continue
            cat = sec.get("category", "")
            items = sec.get("items", [])
            if cat:
                elements.append(_p(f"<b>{cat}</b>", ss["Normal"]))
            if isinstance(items, list) and items:
                elements.append(_bullet_list([str(x) for x in items], ss["Normal"]))
            elements.append(Spacer(1, 4))

    doc.build(elements)
    return buf.getvalue()
