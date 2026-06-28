# Refresh packaging\Output to match the CURRENT version (app/version.py).
# Builds the PyInstaller bundle, the Windows installer (if Inno Setup is present),
# and the portable ZIP + SHA256s, then deletes any Output files from other
# versions so the folder only ever holds the current release.
#
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1
#   ...add -SkipBundle to reuse an existing dist\ (skip the slow PyInstaller step).
param([switch]$SkipBundle)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# Single source of truth for the version.
$ver = (Select-String -Path "app\version.py" -Pattern '__version__ = "([^"]+)"').Matches[0].Groups[1].Value
if (-not $ver) { throw "Could not read __version__ from app/version.py" }
Write-Host "==> Building Output for version $ver" -ForegroundColor Cyan
$out = "packaging\Output"
New-Item -ItemType Directory -Force $out | Out-Null

if (-not $SkipBundle) {
    Write-Host "==> PyInstaller bundle..." -ForegroundColor Cyan
    python -m PyInstaller packaging/BeatTools.spec --noconfirm
}
if (-not (Test-Path "dist\PaperhandsBeatTools\PaperhandsBeatTools.exe")) {
    throw "PyInstaller bundle missing (run without -SkipBundle)."
}

# Installer (optional: only if Inno Setup is installed). Version is injected so
# installer.iss never holds a stale number.
$iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    foreach ($c in @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
                     "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
                     "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe")) {
        if (Test-Path $c) { $iscc = $c; break }
    }
}
if ($iscc) {
    Write-Host "==> Building installer..." -ForegroundColor Cyan
    & $iscc "/DMyAppVersion=$ver" "packaging\installer.iss"
} else {
    Write-Host "==> Inno Setup not found - skipping Setup.exe (portable ZIP still built)." -ForegroundColor Yellow
    Write-Host "    Install with: winget install JRSoftware.InnoSetup" -ForegroundColor Yellow
}

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

# Purge anything in Output that isn't the current version, so the folder always
# matches what we're working on.
Write-Host "==> Pruning stale-version artifacts..." -ForegroundColor Cyan
Get-ChildItem $out -File | Where-Object { $_.Name -notlike "*$ver*" } | ForEach-Object {
    Write-Host "  removing $($_.Name)" -ForegroundColor DarkGray
    Remove-Item $_.FullName -Force
}

Write-Host "Done. Output now matches v${ver}:" -ForegroundColor Green
Get-ChildItem $out -File | ForEach-Object { Write-Host "  $($_.Name)" }
