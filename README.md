# Coseus - CV Builder

**CV Builder** is an **offline-first, ATS-optimized CV builder** that lets you create, analyze, and tailor resumes for specific job descriptions — without relying on external APIs or cloud AI services.

It supports **Modern ATS-friendly CVs** and **Europass format**, includes **job description analysis**, **keyword matching**, **profile/domain libraries**, and **automatic CV optimization per job**.

---

### 🔗 Live demo (no login required):
https://cvbuilder-v2.streamlit.app/

---
## 🚀 Key Features

### ✅ Modern ATS-Friendly CV Builder

- Clean, recruiter-optimized layout
- Strong ATS parsing compatibility
- Keyword-dense but human-readable structure
- Optional photo support (disabled by default for ATS)

### ✅ Europass CV (Full Editor)

- Complete Europass-compatible structure
- All official fields supported
- PDF & DOCX export

### ✅ Offline Job Description Analyzer

- Paste a Job Description once (EN / RO)
- Automatic language detection
- Keyword extraction & ranking
- Coverage score (how well your CV matches the job)
- Persistent analysis per job (hash-based)

### ✅ ATS Optimizer

- Shows **present vs missing keywords**
- One-click auto-apply of missing keywords into CV
- Keeps CV ATS-safe (no keyword stuffing)

### ✅ ATS Helper Panel

- Action verbs
- Metrics ideas
- Bullet templates
- Keywords (merged from libraries + profile)
- All localized EN / RO

### ✅ ATS Profiles & Domain Libraries

- IT & Non-IT profiles
- Domain-based keyword libraries
- Automatic merge order:
    
    ```bash
    Core Library → Domain Library → Selected Profile
    
    ```
    
- Profiles editable as YAML (no code changes needed)

### ✅ Auto Profile Suggestion

- Suggests best ATS profile based on Job Description
- Works offline
- Helps non-technical users choose the right profile

### ✅ Import / Export

- Import CV from **PDF / DOCX** (Autofill)
- Import / Export CV as **JSON**
- Export:
    - PDF (Modern / Europass)
    - DOCX (Modern / Europass)
    - Plain ATS `.txt`

### ✅ Desktop & Cloud Ready

- Runs locally with Streamlit
- Works on **Streamlit Cloud**
- Windows & Linux compatible
- PyInstaller desktop builds supported

---

## 🧠 Architecture Overview

```
CVBuilder
│
├── app.py# Main Streamlit app
│
├── components/# UI components
│   ├── ats_optimizer.py
│   ├── ats_helper_panel.py
│   ├── ats_dashboard.py
│   ├── profile_manager.py
│   └── ...
│
├── utils/
│   ├── profiles.py# Profiles, libraries, domain logic
│   ├── jd_optimizer.py# Offline JD analysis engine
│   ├── pdf_autofill.py# PDF / DOCX autofill
│   └── session.py# State & reset logic
│
├── ats_profiles/
│   ├── domains_index.yaml# IT / Non-IT domain mapping
│   ├── core_en_ro.yaml# Global library
│   ├── cyber_security.yaml# Example profile
│   └── libraries/
│       └── domains/
│           ├── cyber_security.yaml
│           ├── finance_accounting.yaml
│           └── ...
│
└── exporters/
    ├── pdf_generator.py
    └── docx_generator.py

```

---

## 🔁 Job Description Flow (Single Source of Truth)

There is **only one Job Description input** in the entire app:

```python
cv["job_description"]

```

It is shared by:

- ATS Optimizer
- Job Description Analyzer
- ATS Helper
- ATS Score Dashboard

This eliminates duplicate copy-paste and keeps everything in sync.

---

## 🌍 Language Support

- English 🇬🇧
- Romanian 🇷🇴
- Automatic detection from Job Description
- Profiles & libraries support bilingual fields:

```yaml
keywords:
core:
en: [IncidentResponse,SIEM]
ro: [Răspunslaincidente,SIEM]

```

---

## 🛠️ Installation (Local)

```bash
gitclone https://github.com/yourusername/CVBuilder.git
cd CVBuilder
python -m venv venv
source venv/bin/activate# Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py

```

---

## 🖥️ Desktop Build (Optional)

Windows example (PyInstaller):

```bash
pyinstaller cvbuilder.spec --clean --noconfirm

```

Produces a standalone executable running Streamlit locally.

---

## 🎯 Target Users

- Cybersecurity professionals
- IT & Non-IT job seekers
- Recruiters & career coaches
- Anyone who wants ATS-optimized CVs **without cloud AI**

---

## 🔐 Privacy & Offline First

- No external APIs
- No OpenAI / cloud AI calls
- Job descriptions stay local
- Works fully offline

---

## 📌 Roadmap (Optional Ideas)

- Per-experience keyword highlighting
- Multiple JD comparison
- CV versioning per job
- Cover letter generator (offline)
- Multi-language export toggle
