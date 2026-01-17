import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from typing import Dict, List, Tuple

# Minimal stopwords (EN) – keep short to avoid missing tech terms
STOP = {
    "and","or","the","a","an","to","of","in","on","for","with","as","at","by",
    "from","is","are","be","been","being","this","that","these","those","you",
    "we","they","our","your","their","will","can","may","must","should","etc",
    "responsible","responsibilities","requirements","preferred","nice","plus",
    "minimum","basic","strong","experience","knowledge","skills","ability"
}

# Synonym normalization (expand as you like)
SYNONYMS = {
    "azure ad": "entra id",
    "microsoft entra": "entra id",
    "entra": "entra id",
    "o365": "microsoft 365",
    "m365": "microsoft 365",
    "office 365": "microsoft 365",
    "active directory": "active directory",
    "ad": "active directory",
    "powershell": "powershell",
    "ps": "powershell",
    "vulnerability management": "vulnerability management",
    "vulnerability scanning": "vulnerability scanning",
    "incident response": "incident response",
    "siem": "siem",
    "edr": "edr",
}

# Category keyword hints (used for routing)
CATEGORY_HINTS = {
    "cloud_identity": [
        "azure", "aws", "gcp", "entra id", "azure ad", "iam", "sso", "microsoft 365", "intune",
        "conditional access", "okta", "adfs", "saml", "oauth", "oidc", "sharepoint", "exchange online"
    ],
    "security": [
        "mfa", "hardening", "incident response", "siem", "edr", "vulnerability", "patch", "hunting",
        "soc", "mitre", "attack", "log analysis", "alert triage", "forensics", "iso 27001", "nist",
        "risk", "threat", "malware", "phishing", "security monitoring"
    ],
    "networking": [
        "cisco", "routing", "switching", "vlan", "vpn", "firewall", "ids", "ips", "network monitoring",
        "tcp/ip", "dns", "dhcp", "bgp", "ospf", "nat", "wireshark"
    ],
    "os_servers": [
        "windows server", "linux", "active directory", "gpo", "dns", "dhcp", "server", "rhel",
        "ubuntu", "debian", "powershell", "bash", "kernel", "systemd"
    ],
    "scripting_automation": [
        "powershell", "bash", "python", "automation", "scripting", "ansible", "terraform",
        "ci/cd", "git", "pipelines"
    ],
    "tools": [
        "intune", "knox", "defender", "sentinel", "splunk", "qradar", "elastic", "jira",
        "servicenow", "monitoring", "zabbix", "nagios", "prometheus", "grafana"
    ],
    "virtualization": [
        "vmware", "esxi", "vcenter", "hyper-v", "virtualization", "kvm", "docker", "kubernetes"
    ],
}

CATEGORY_LABELS = {
    "cloud_identity": "Cloud & Identity",
    "security": "Security",
    "networking": "Networking",
    "os_servers": "OS & Servers",
    "scripting_automation": "Scripting & Automation",
    "tools": "Tools",
    "virtualization": "Virtualization",
}

TECH_PHRASE_RE = re.compile(
    r"""
    (?:[A-Z][A-Za-z0-9\+\#\/\.\-]{1,})            # Proper-tech tokens
    (?:\s+[A-Z][A-Za-z0-9\+\#\/\.\-]{1,})*        # Multi-word Proper-tech phrases
    """,
    re.VERBOSE
)

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9\+\#\/\.\-]{1,}")


def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return SYNONYMS.get(s, s)


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def extract_keywords(jd_text: str, max_keywords: int = 50) -> List[Tuple[str, float]]:
    """
    Offline keyword extraction:
    - grabs tech phrases (Proper-case) and token words
    - ranks by frequency + phrase bonus
    Returns list of (keyword, score)
    """
    text = jd_text or ""
    # Normalize separators
    clean = re.sub(r"[•\u2022]", "\n", text)
    clean = re.sub(r"[/,;()]", " ", clean)
    clean = re.sub(r"\s+", " ", clean)

    # Candidates from Proper-case phrases (Azure AD, Windows Server, etc.)
    phrases = [p.strip() for p in TECH_PHRASE_RE.findall(text)]
    phrases = [_norm(p) for p in phrases if p and _norm(p) not in STOP and len(_norm(p)) > 2]

    # Token candidates
    words = [w.lower() for w in WORD_RE.findall(clean)]
    words = [_norm(w) for w in words if w not in STOP and len(w) > 2]

    # Build frequency
    c = Counter()
    for p in phrases:
        c[p] += 2.5  # phrase bonus
    for w in words:
        c[w] += 1.0

    # Drop very generic words
    for bad in list(c.keys()):
        if bad in STOP or bad.isdigit():
            del c[bad]

    # Keep top N
    items = c.most_common(max_keywords * 2)

    # Merge near-duplicates (entra id vs azure ad, etc.) by similarity
    merged: List[Tuple[str, float]] = []
    for k, sc in items:
        placed = False
        for i, (mk, msc) in enumerate(merged):
            if _similar(k, mk) >= 0.92:
                merged[i] = (mk, msc + sc)
                placed = True
                break
        if not placed:
            merged.append((k, float(sc)))

    merged.sort(key=lambda x: x[1], reverse=True)
    return merged[:max_keywords]


def categorize_keywords(keywords: List[str]) -> Dict[str, List[str]]:
    """
    Route keywords into categories using hint lists + fuzzy contains.
    """
    buckets = {k: [] for k in CATEGORY_LABELS.keys()}

    def bucket_for(kw: str) -> str:
        kwl = kw.lower()
        # direct hints
        for cat, hints in CATEGORY_HINTS.items():
            for h in hints:
                hl = h.lower()
                if hl in kwl or kwl in hl:
                    return cat
        # fallback heuristics
        if any(x in kwl for x in ["azure", "aws", "entra", "iam", "microsoft 365", "intune", "sso"]):
            return "cloud_identity"
        if any(x in kwl for x in ["mfa", "hardening", "incident", "siem", "edr", "vulnerability", "patch", "soc"]):
            return "security"
        if any(x in kwl for x in ["cisco", "vlan", "vpn", "firewall", "routing", "switch", "dns", "dhcp"]):
            return "networking"
        if any(x in kwl for x in ["windows", "linux", "active directory", "gpo", "server"]):
            return "os_servers"
        if any(x in kwl for x in ["powershell", "bash", "python", "ansible", "terraform", "automation"]):
            return "scripting_automation"
        if any(x in kwl for x in ["vmware", "hyper-v", "kvm", "docker", "kubernetes", "virtual"]):
            return "virtualization"
        return "tools"

    for kw in keywords:
        k = _norm(kw)
        if not k or k in STOP:
            continue
        cat = bucket_for(k)
        buckets[cat].append(k)

    # Dedup and keep order
    for cat in buckets:
        seen = set()
        uniq = []
        for x in buckets[cat]:
            if x in seen:
                continue
            seen.add(x)
            uniq.append(x)
        buckets[cat] = uniq

    return buckets


def compute_coverage(cv_text: str, jd_keywords: List[str]) -> Tuple[float, List[str]]:
    """
    coverage = fraction of jd_keywords found in cv_text (simple contains).
    returns (coverage, missing_keywords)
    """
    hay = (cv_text or "").lower()
    found = []
    missing = []
    for kw in jd_keywords:
        k = _norm(kw)
        if not k:
            continue
        if k in hay:
            found.append(k)
        else:
            missing.append(k)
    coverage = (len(found) / max(1, len(found) + len(missing)))
    return coverage, missing


def build_technical_skills_lines_from_buckets(buckets: Dict[str, List[str]], cap_per_group: int = 12) -> List[str]:
    lines = []
    for cat_key, label in CATEGORY_LABELS.items():
        items = buckets.get(cat_key, [])
        if not items:
            continue
        items = items[:cap_per_group]
        # Title case for readability (keep acronyms)
        pretty = []
        for it in items:
            # keep known acronyms
            if it.upper() in {"MFA", "SIEM", "EDR", "VPN", "VLAN", "GPO", "AWS"}:
                pretty.append(it.upper())
            else:
                pretty.append(it.title() if it.islower() else it)
        lines.append(f"{label}: " + ", ".join(pretty))
    return lines


def suggested_bullet_templates(role_hint: str, buckets: Dict[str, List[str]]) -> List[str]:
    """
    Offline templates (no LLM). Choose based on role_hint: soc / pentest / seceng / general
    """
    rh = (role_hint or "").lower()

    # pick a few representative keywords to inject
    sec = buckets.get("security", [])[:5]
    cloud = buckets.get("cloud_identity", [])[:4]
    net = buckets.get("networking", [])[:4]
    tools = buckets.get("tools", [])[:4]
    os_ = buckets.get("os_servers", [])[:4]
    scr = buckets.get("scripting_automation", [])[:4]

    def pick(lst, default):
        return lst[0] if lst else default

    t1 = pick(tools, "monitoring tools")
    t2 = pick(sec, "incident response")
    t3 = pick(cloud, "entra id")
    t4 = pick(net, "vpn")
    t5 = pick(scr, "powershell")
    t6 = pick(os_, "windows server")

    if "pentest" in rh:
        return [
            f"Performed reconnaissance and vulnerability validation aligned to {pick(sec,'vulnerability management')}; documented findings and remediation guidance.",
            f"Validated security controls and misconfigurations across {t6}/{pick(os_,'linux')} and network surfaces; prioritized fixes by risk.",
            f"Automated repeatable checks using {t5}; improved consistency and reduced manual effort by (X)%.",
        ]
    if "soc" in rh or "analyst" in rh:
        return [
            f"Triaged alerts in {t1} and investigated suspicious activity; escalated incidents using a structured {t2} workflow.",
            f"Improved detection coverage by tuning rules for {pick(sec,'log analysis')} and mapping to MITRE ATT&CK; reduced false positives by (X)%.",
            f"Supported identity security in {t3} (MFA/Conditional Access); improved account hygiene and access control.",
        ]
    if "engineer" in rh or "security engineer" in rh:
        return [
            f"Implemented security controls (e.g., {t2}, MFA, hardening) across hybrid environments; improved compliance and reduced risk exposure.",
            f"Built and maintained secure identity and access configurations in {t3}; enforced least privilege and access reviews.",
            f"Automated operational tasks using {t5}/{pick(scr,'automation')}; reduced provisioning time by (X)%.",
        ]
    # general
    return [
        f"Administered hybrid environments and improved security posture using {t2} practices; documented SOPs and operational runbooks.",
        f"Strengthened identity and access in {t3}; implemented MFA and access hygiene improvements.",
        f"Supported network reliability and security across {t4}; improved monitoring and troubleshooting workflows using {t1}.",
    ]
