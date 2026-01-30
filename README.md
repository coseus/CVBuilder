# Coseus - CV Builder

🚀 **CV Builder** is a **desktop, offline-first CV generator** focused on **ATS (Applicant Tracking System) optimization**. 

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

## Build commands

---

## 🛠️ Installation (Local)

```bash
gitclone https://github.com/coseus/CVBuilder.git
cd CVBuilder
python -m venv venv
Linux: source venv/bin/activate
Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py

```
---

## ☁️ Deploy on Streamlit Cloud

1. Push the repository to GitHub
2. Go to [https://streamlit.io/cloud](https://streamlit.io/cloud)
3. Select the repo and `app.py`
4. Deploy 🚀

   ### Demo ###: https://cvbuilder-v2.streamlit.app/

✅ Fully compatible with Streamlit Cloud.

---

## 📥 JSON Import / Export

- Stable and forward-compatible schema
- Supports:
    - full CV export
    - optional photo (base64)
- Ideal for:
    - backups
    - versioning
    - migration between devices

---
## 🖥 Desktop Executables Build Localy
---
### Windows
``` bash
python -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
py -m pip install -r requirements-build.txt
py -m PyInstaller .\cvbuilder_windows.spec --noconfirm --clean
```
### Linux
``` bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m pip install -r requirements-build.txt
python3 -m PyInstaller ./cvbuilder_linux.spec --noconfirm --clean
chmod +x dist/cvbuilder
```

### The results are found in: 
``` bash
dist/cvbulder/
```

## 🖥 Desktop Executables Release

Download the latest **ready-to-run executables** here:

🔗 **Windows & Linux builds (Mega.nz)**

👉 [https://mega.nz/folder/zxYx3Dqa#X85rmbOzS_Oy_aUEdwUg4A](https://mega.nz/folder/zxYx3Dqa#X85rmbOzS_Oy_aUEdwUg4A)

### Available files

- **Windows**: `CVBuilder.exe`
- **Linux**: `CVBuilder` (AppImage / binary)

⚠️ No Python installation required.

---

## 🚀 How to Use

1. Download the executable for your OS
2. Run it (double-click)
3. Paste **Job Description once**
4. Select **ATS Profile** (IT / Non-IT)
5. Optimize CV automatically
6. Export as:
    - PDF (Modern / Europass)
    - DOCX
    - ATS-friendly `.txt`

---
