# **Coseus – CV Builder**

🚀 **Coseus CV Builder** is a **desktop-first, offline-capable CV generator** designed to create **ATS-optimized resumes** with precision and control.

It supports **Modern ATS-friendly CVs** and **full Europass format**, includes **offline job description analysis**, **keyword matching**, **domain-based profiles**, and **automatic CV optimization per job** — all without relying on cloud AI services.

---

## 🔗 Live Demo (no login required)

👉 [https://cvbuilder-v2.streamlit.app/](https://cvbuilder-v2.streamlit.app/)

---

## ✨ Key Features

### 🧩 Modern ATS-Friendly CV Builder

- Clean, recruiter-friendly layout
- High ATS parsing compatibility
- Keyword-dense yet human-readable structure
- Optional photo support (disabled by default for ATS safety)

### 📄 Europass CV (Full Editor)

- Complete Europass-compatible structure
- All official Europass fields supported
- PDF & DOCX export

---

## 🧠 Job Description Intelligence (Offline)

### 🔍 Offline Job Description Analyzer

- Paste a Job Description **once** (EN / RO)
- Automatic language detection
- Keyword extraction & ranking
- Coverage score (how well your CV matches the job)
- Persistent analysis per job (hash-based, no duplicates)

### ⚙️ ATS Optimizer

- Shows **present vs missing keywords**
- One-click auto-apply of missing keywords into CV
- Keeps CV ATS-safe (no keyword stuffing)

### 🧰 ATS Helper Panel

- Action verbs
- Metrics ideas
- Bullet templates
- Keywords (merged from libraries + profile)
- Fully localized **EN / RO**

---

## 📚 ATS Profiles & Domain Libraries

- IT & Non-IT profiles
- Domain-specific keyword libraries
- Profiles are **editable YAML files** (no code changes needed)
- Automatic merge order:

```
Core Library
  → Domain Library
    → Selected Profile

```

This ensures relevance, consistency, and ATS compatibility across roles.

---

## 🤖 Auto Profile Suggestion Engine

- Suggests the **best ATS profile** based on Job Description
- Works completely offline
- Ideal for non-technical users unsure which profile to choose

---

## 🔄 Import / Export

### Import

- PDF / DOCX CV autofill
- JSON import (stable schema)

### Export

- PDF (Modern / Europass)
- DOCX (Modern / Europass)
- Plain ATS-friendly `.txt`

---

## 🧱 Architecture Overview

```
CVBuilder/
│
├── app.py# Main Streamlit application
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
│   └── session.py# Session & reset logic
│
├── ats_profiles/
│   ├── domains_index.yaml
│   ├── core_en_ro.yaml
│   ├── cyber_security.yaml
│   └── libraries/
│       └── domains/
│
└── exporters/
    ├── pdf_generator.py
    └── docx_generator.py

```

---

## 🔁 Single Source of Truth – Job Description

The entire app uses **one shared Job Description field**:

```python
cv["job_description"]
```

It is consumed by:

- ATS Optimizer
- Job Description Analyzer
- ATS Helper
- ATS Score Dashboard

➡️ No duplicate copy-paste. Everything stays in sync.

---

## 🌍 Language Support

- English 🇬🇧
- Romanian 🇷🇴
- Automatic language detection
- Profiles & libraries support bilingual fields:

```yaml
keywords:
core:
en: [IncidentResponse,SIEM]
ro: [Răspunslaincidente,SIEM]
```

---

## 🎯 Target Users

- IT & Cybersecurity professionals
- Non-IT professionals (Finance, HR, Marketing, Sales, etc.)
- Recruiters & career coaches
- Anyone who wants **ATS-optimized CVs without cloud AI**

---

## 🔐 Privacy & Offline-First Design

- No external APIs
- No OpenAI / cloud AI calls
- Job descriptions never leave your machine
- Fully functional offline

---

## 🛠 Local Installation (Developers)

```bash
gitclone https://github.com/coseus/CVBuilder.git
cd CVBuilder

python -m venv venv
# Linux
source venv/bin/activate
# Windows
venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

---

## ☁️ Deploy on Streamlit Cloud

1. Push the repository to GitHub
2. Go to [https://streamlit.io/cloud](https://streamlit.io/cloud)
3. Select the repo and `app.py`
4. Deploy 🚀

👉 Live demo: [https://cvbuilder-v2.streamlit.app/](https://cvbuilder-v2.streamlit.app/)

---

## 🖥 Desktop Executables (Windows & Linux)

### 🔨 Build Locally

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-build.txt
pyinstaller cvbuilder_windows.spec --noconfirm --clean

```

### Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-build.txt
pyinstaller cvbuilder_linux.spec --noconfirm --clean
chmod +x dist/cvbuilder
```

Artifacts will be available in:

```
dist/cvbuilder/
```

---

## 📦 Prebuilt Desktop Releases

🔗 **Windows & Linux executables (Mega.nz)**

👉 [https://mega.nz/folder/zxYx3Dqa#X85rmbOzS_Oy_aUEdwUg4A](https://mega.nz/folder/zxYx3Dqa#X85rmbOzS_Oy_aUEdwUg4A)

### Files

- **Windows**: `CVBuilder.exe`
- **Linux**: `CVBuilder` (binary / AppImage)

⚠️ No Python installation required.

---

## 🚀 Quick Start (Executables)

1. Download the executable for your OS
2. Run it (double-click)
3. Paste Job Description once
4. Select ATS Profile (IT / Non-IT)
5. Optimize CV automatically
6. Export PDF / DOCX / ATS `.txt`

---

## ⚠️ Notes

- Antivirus software may warn on unsigned executables (false positives).
- Windows: **More info → Run anyway**
- Linux: `chmod +x CVBuilder` if needed
