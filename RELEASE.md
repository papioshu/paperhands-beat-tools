# Release & Build Guide

How to build the Windows installer and cut a self-updating release.

## Prerequisites (one time)
- Python 3.10+ with deps: `python -m pip install -r requirements.txt PySide6 pyinstaller`
- ffmpeg installed (`winget install Gyan.FFmpeg`) — it gets bundled into the build
- Inno Setup 6 (`winget install JRSoftware.InnoSetup`)

## Cutting a release
1. **Bump the version** in two places:
   - `app/version.py` → `__version__ = "X.Y.Z"`
   - `packaging/installer.iss` → `#define MyAppVersion "X.Y.Z"`
2. **Run the tests**: `set QT_QPA_PLATFORM=offscreen && python -m pytest tests/ -q`
3. **Build the bundle + installer**:
   ```powershell
   powershell -ExecutionPolicy Bypass -File packaging\build.ps1
   ```
   This runs PyInstaller (`packaging/BeatTools.spec`) to produce
   `dist/PaperhandsBeatTools/` (the app + bundled ffmpeg), then Inno Setup to
   produce `packaging/Output/PaperhandsBeatTools-Setup-X.Y.Z.exe`.
4. **Commit, tag, and release**:
   ```powershell
   git commit -am "Bump to vX.Y.Z"
   git push origin main
   git tag -a vX.Y.Z -m "vX.Y.Z" ; git push origin vX.Y.Z
   gh release create vX.Y.Z packaging\Output\PaperhandsBeatTools-Setup-X.Y.Z.exe `
     --title "vX.Y.Z" --notes "release notes..."
   ```

## How auto-update works
- The app checks `app.version.UPDATE_REPO` (default
  `papioshu/paperhands-beat-tools`) for the latest GitHub release on launch.
- If the release tag is newer than the running version, it offers
  **Download & Install** — it downloads the release's `*-Setup-*.exe` asset and
  runs it. (Detection + download are wired in `app/updater.py`.)
- So: publishing a tagged Release with the installer asset *is* the update.

## Notes
- The installer bundles all **required** Python deps + ffmpeg, so the app runs
  with no separate install.
- **Demucs (stem separation)** and its PyTorch dependency are NOT bundled (they'd
  add several GB). The app installs them on demand via the one-click prompt. See
  the README/USAGE for the stem-splitting flow.
- The build is unsigned; sign `PaperhandsBeatTools.exe` and the installer with a
  code-signing certificate to avoid SmartScreen warnings.
