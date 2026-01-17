# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    copy_metadata,
)

project_root = os.path.abspath(".")

datas = []

# --- include your project folders ---
for folder in ["components", "exporters", "utils", "ats_profiles"]:
    src = os.path.join(project_root, folder)
    if os.path.exists(src):
        datas.append((src, folder))

# include top-level app.py
datas.append((os.path.join(project_root, "app.py"), "."))

# --- Streamlit assets + metadata (CRITICAL) ---
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

# --- Hidden imports (dynamic) ---
hiddenimports = []
hiddenimports += collect_submodules("streamlit")

# --- Your app deps (import/export) ---
for pkg in ["pdfplumber", "docx", "reportlab"]:
    try:
        hiddenimports += collect_submodules(pkg)
        datas += copy_metadata(pkg)
        datas += collect_data_files(pkg)
    except Exception:
        pass

block_cipher = None

a = Analysis(
    ["run_desktop.py"],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="CVBuilderATS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # set True temporarily for debugging
    icon=os.path.join(project_root, "utils", "coseus.ico"),
)
