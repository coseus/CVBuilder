# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    copy_metadata,
)

project_root = os.path.abspath(".")

datas = []

# Include project folders
for folder in ["components", "exporters", "utils", "ats_profiles"]:
    src = os.path.join(project_root, folder)
    if os.path.exists(src):
        datas.append((src, folder))

# Include top-level app.py
datas.append((os.path.join(project_root, "app.py"), "."))

# Streamlit assets + metadata
datas += collect_data_files("streamlit")
datas += copy_metadata("streamlit")

# Recommended metadata for common Streamlit deps
for pkg in [
    "altair",
    "blinker",
    "cachetools",
    "click",
    "jinja2",
    "markdown",
    "packaging",
    "protobuf",
    "pygments",
    "tornado",
    "watchdog",
]:
    try:
        datas += copy_metadata(pkg)
    except Exception:
        pass

# Hidden imports
hiddenimports = []
hiddenimports += collect_submodules("streamlit")

# App deps (import/export)
for pkg in ["pdfplumber", "docx", "reportlab"]:
    try:
        hiddenimports += collect_submodules(pkg)
        datas += copy_metadata(pkg)
        datas += collect_data_files(pkg)
    except Exception:
        pass

a = Analysis(
    ["run_desktop_linux.py"],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="CVBuilderATS",
    debug=False,
    strip=False,
    upx=True,
    console=False,  # set True if you want terminal logs
)
