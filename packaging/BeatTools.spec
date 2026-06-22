# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Paperhand's Beat Tools (onedir Windows build).

Bundles the GUI + shared engine, the heavy audio stack (librosa/numba/scipy/
soundfile/pydub/Pillow), PySide6 (incl. QtMultimedia for playback), and the
ffmpeg/ffprobe binaries so the installed app needs no separate ffmpeg install.

Build from the repo root:
    pyinstaller packaging/BeatTools.spec --noconfirm
"""

import glob
import os

from PyInstaller.utils.hooks import collect_all

# Script paths in a spec resolve relative to the spec file, so anchor to repo root.
ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))

datas, binaries, hiddenimports = [], [], []

# Pull data files, binaries, and submodules for the finicky packages.
for pkg in (
    "librosa", "soundfile", "soxr", "audioread", "pooch", "lazy_loader",
    "numba", "llvmlite", "scipy", "sklearn", "pydub", "joblib", "PIL",
):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as exc:  # noqa: BLE001
        print(f"[spec] collect_all({pkg}) skipped: {exc}")

# Bundle ffmpeg + ffprobe (placed at the bundle root so ffmpeg_runtime finds them).
_FF = os.path.expandvars(
    r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\**\bin")
for exe_name in ("ffmpeg.exe", "ffprobe.exe"):
    hits = glob.glob(os.path.join(_FF, exe_name), recursive=True)
    if hits:
        binaries.append((hits[0], "."))
    else:
        print(f"[spec] WARNING: {exe_name} not found under {_FF}")

hiddenimports += ["app", "core", "sklearn.utils._typedefs",
                  "sklearn.neighbors._partition_nodes", "scipy.special.cython_special"]

# Branding assets (icon/logo) for the window + header.
for _asset in ("icon.ico", "icon.png", "icon.svg"):
    _p = os.path.join(ROOT, "assets", _asset)
    if os.path.exists(_p):
        datas.append((_p, "assets"))

a = Analysis(
    [os.path.join(ROOT, "app", "main.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=["tkinter", "matplotlib", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PaperhandsBeatTools",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=os.path.join(ROOT, "assets", "icon.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PaperhandsBeatTools",
)
