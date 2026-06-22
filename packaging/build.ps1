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

$ver = (Select-String -Path "app\version.py" -Pattern '__version__ = "([^"]+)"').Matches[0].Groups[1].Value
$out = "packaging\Output"

Write-Host "==> Building portable ZIP..." -ForegroundColor Cyan
# A 'portable.txt' marker makes the app store its data beside the exe.
New-Item -ItemType File -Force "dist\PaperhandsBeatTools\portable.txt" | Out-Null
$zip = "$out\PaperhandBeatManager-Portable-$ver.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path "dist\PaperhandsBeatTools\*" -DestinationPath $zip
Remove-Item "dist\PaperhandsBeatTools\portable.txt"

Write-Host "==> SHA256 checksums..." -ForegroundColor Cyan
foreach ($f in @("$out\PaperhandsBeatTools-Setup-$ver.exe", $zip)) {
    if (Test-Path $f) {
        $h = (Get-FileHash $f -Algorithm SHA256).Hash.ToLower()
        "$h  $(Split-Path $f -Leaf)" | Out-File -Encoding ascii "$f.sha256"
        Write-Host "  $h  $(Split-Path $f -Leaf)"
    }
}
Write-Host "Done. Installer + portable ZIP + checksums are in $out\" -ForegroundColor Green
