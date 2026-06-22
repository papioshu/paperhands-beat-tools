# Internal Developer Notes

Internal build/release reference. Not user-facing — keep out of the public
product docs (README / USAGE / RELEASE).

## Run from source
```powershell
python -m pip install -r requirements.txt PySide6
python -m app.main          # desktop app
python tag_beats.py --help  # batch tagger CLI
```
Requires Python 3.10+ and ffmpeg on PATH (`winget install Gyan.FFmpeg`).
Optional: `pip install demucs` for stem separation (heavy; pulls PyTorch).

## Tests
```powershell
set QT_QPA_PLATFORM=offscreen
python -m pytest tests/ -q
```
Audio integration tests need ffmpeg on PATH; they skip cleanly otherwise.

## Build the installer
Prereqs (one time): `pip install pyinstaller`, ffmpeg installed, Inno Setup 6
(`winget install JRSoftware.InnoSetup`).
```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```
PyInstaller (`packaging/BeatTools.spec`) builds `dist/PaperhandsBeatTools/`
(bundled ffmpeg + icon); Inno Setup (`packaging/installer.iss`) produces
`packaging/Output/PaperhandsBeatTools-Setup-<version>.exe`.

## Cut a release
1. Bump the version in `app/version.py` **and** `packaging/installer.iss`.
2. Run the tests, then `packaging\build.ps1`.
3. Tag + publish:
   ```powershell
   git commit -am "Bump to vX.Y.Z" ; git push origin main
   git tag -a vX.Y.Z -m "vX.Y.Z" ; git push origin vX.Y.Z
   gh release create vX.Y.Z packaging\Output\PaperhandsBeatTools-Setup-X.Y.Z.exe `
     --title "vX.Y.Z" --notes "..."
   ```

## Auto-update
The app checks `app.version.UPDATE_REPO` for the latest GitHub release on launch
and offers Download & Install of the `*-Setup-*.exe` asset (see `app/updater.py`).
Publishing a tagged Release with the installer asset is the update.

## Release notes template
```
## vX.Y.Z

### Download
- Installer: PaperhandsBeatTools-Setup-X.Y.Z.exe
- Portable ZIP: PaperhandBeatManager-Portable-X.Y.Z.zip (no install; unzip & run)

### What changed
- …

### Known issues
- …

### Verify your download (optional, advanced)
SHA256 are in the .sha256 files attached to this release.
PowerShell:  Get-FileHash .\<file> -Algorithm SHA256
```
`packaging\build.ps1` emits the installer, the portable ZIP, and a `.sha256` for
each — upload all of them (incl. the `.sha256` files). The in-app updater
verifies a download against the published `<asset>.sha256` and refuses on
mismatch.

## Release-build checklist
- [ ] `app/version.py` + `installer.iss` versions match.
- [ ] `python -m pytest tests/ -q` green.
- [ ] No dev artifacts ship: `tests/`, `__pycache__/`, `*.spec`, `build/`,
      `packaging/`, internal docs, and `assets/papercrane-accurate.png` are NOT
      inside `dist/` (the installer copies `dist/PaperhandsBeatTools/*` only).
- [ ] ffmpeg + `assets/icon.*` present under `dist/PaperhandsBeatTools/_internal/`.
- [ ] Demucs/PyTorch are lazy-imported (no import at startup).
- [ ] Frozen exe launches (smoke test) and the icon shows.
- [ ] Installer compresses with LZMA2 (set in `installer.iss`).
- [ ] Release notes written for end users (no build instructions).
