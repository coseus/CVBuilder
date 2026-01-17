# CV Builder – Modern (ATS-Friendly) & Europass

🚀 **CV Builder** is a Streamlit-based web application that helps you **create, optimize, import, and export CVs** in two professional formats:

- **Modern (ATS-Friendly)** – optimized for Applicant Tracking Systems and recruiters
- **Europass (Complete)** – compliant with the official Europass structure

The app supports **PDF & DOCX autofill**, **offline ATS optimization**, **job-specific keyword matching**, and export to **PDF, Word, TXT, and JSON**.

---

## ✨ Key Features

### 🧩 CV Editing

- Full CRUD support (Add / Edit / Delete) for:
    - Personal Information
    - Professional Summary (bullet-based, ATS-friendly)
    - Professional Experience / Projects
    - Education
    - Skills (structured for ATS)
    - Languages
    - Europass personal competencies
- **Short profile line under name**
    
    Example:
    
    `Senior System Administrator | Cloud & Security | 17+ years experience`
    

---

### 📄 CV Import (Autofill)

- Import CVs from:
    - **PDF** (eJobs, Europass, classic CV layouts)
    - **DOCX**
- Smart autofill engine:
    - fixes duplicated characters from PDFs (`CCoossmmiinn → Cosmin`)
    - ignores platform footers (e.g. `www.ejobs.ro`)
    - safe merge (never overwrites manually filled fields)

---

### 🤖 ATS Optimizer (Offline)

- Editable **ATS Profiles (YAML)**
- Offline **Job Description Analyzer**
- Keyword matching & coverage score
- Missing keywords detection
- Bullet rewrite templates
- Visual ATS score dashboard

> 🔐 No external APIs. Everything runs locally/offline.
> 

---

### 📤 Export Options

- PDF – Modern
- PDF – Europass
- Word – Modern
- Word – Europass
- ATS `.txt` (plain text, copy-paste friendly)
- Import / Export full CV as **JSON**

---

### 🔄 Reset & Persistence

- **Reset Everything**
- **Reset ATS / Job Description only**
- Persistent ATS profile per job

---

## 🧠 ATS Profiles

ATS profiles are stored as editable YAML files:

```
ats_profiles/

```

Examples:

- `cyber_security.yaml`
- `network_administrator.yaml`
- `cloud_engineer.yaml`
- `devops_platform_engineering.yaml`

Each profile defines:

- job titles
- keywords (structured & categorized)
- action verbs
- metrics
- bullet rewrite templates

👉 Profiles can be **selected, previewed, edited, and duplicated directly from the UI**.

---

## 🗂️ Project Structure

```
cvbuilderats/
├── app.py
├── components/
│   ├── personal_info_shared.py
│   ├── work_experience.py
│   ├── education.py
│   ├── skills.py
│   ├── ats_optimizer.py
│   ├── ats_dashboard.py
│   └── profile_manager.py
├── exporters/
│   ├── pdf_generator.py
│   └── docx_generator.py
├── utils/
│   ├──session.py
│   ├── json_io.py
│   ├── profiles.py
│   └── pdf_autofill.py
├── ats_profiles/
├── requirements.txt
└── README.md

```

---

## ▶️ Run Locally

### 1️⃣ Clone the repository

```bash
gitclone https://github.com/your-username/cvbuilderats.git
cd cvbuilderats

```

### 2️⃣ Install dependencies

```bash
pip install -r requirements.txt

```

### 3️⃣ Start the app

```bash
streamlit run app.py

```

---

## ☁️ Deploy on Streamlit Cloud

1. Push the repository to GitHub
2. Go to [https://streamlit.io/cloud](https://streamlit.io/cloud)
3. Select the repo and `app.py`
4. Deploy 🚀

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

## 🔐 Privacy & Security

- No external services or APIs
- ATS analysis is **100% offline**
- No data leaves the app
- Safe for real CVs and sensitive data

---

## 🧪 Known Limitations

- PDF parsing depends on text-layer quality
- Scanned PDFs (images) are not supported (no OCR yet)
- ATS scoring is heuristic (not ML-based)

---

## 🛣️ Roadmap

- [ ]  OCR support for scanned PDFs
- [ ]  Skill gap suggestions
- [ ]  Multiple CV variants per job
- [ ]  Cover Letter generator
- [ ]  LaTeX export
- [ ]  Desktop builds (Windows / Linux)

## Build commands
### Windows
``` bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-build.txt
pyinstaller .\cvbuilderats_windows.spec --noconfirm --clean
```
### Linux
``` bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-build.txt
pyinstaller cvbuilderats_linux.spec --noconfirm --clean
```

### Rezultatul va fi în:
``` bash
dist/CVBuilderATS/
```
