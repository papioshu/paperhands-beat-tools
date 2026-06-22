# Build the app bundle (PyInstaller) + the Windows installer (Inno Setup).
# Run from anywhere:  powershell -ExecutionPolicy Bypass -File packaging\build.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "==> PyInstaller bundle..." -ForegroundColor Cyan
python -m PyInstaller packaging/BeatTools.spec --noconfirm
if (-not (Test-Path "dist\PaperhandsBeatTools\PaperhandsBeatTools.exe")) {
    throw "PyInstaller build failed (exe not found)."
}

Write-Host "==> Locating Inno Setup (ISCC.exe)..." -ForegroundColor Cyan
$iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    foreach ($c in @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
                     "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
                     "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe")) {
        if (Test-Path $c) { $iscc = $c; break }
    }
}
if (-not $iscc) {
    throw "Inno Setup not found. Install with: winget install JRSoftware.InnoSetup"
}

Write-Host "==> Building installer..." -ForegroundColor Cyan
& $iscc "packaging\installer.iss"
Write-Host "Done. Installer is in packaging\Output\" -ForegroundColor Green
