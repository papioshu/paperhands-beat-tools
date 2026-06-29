# Refresh packaging\Output to match the CURRENT version (app/version.py).
#
# Default: build the PyInstaller bundle and drop the uncompressed, runnable
#   bundle folder into Output as PaperhandsBeatTools-<ver>\ (double-click the exe
#   inside — no unzip, no install).
# -Release: also build the Inno Setup installer + portable ZIP + SHA256s (the
#   shippable artifacts the in-app updater downloads from GitHub).
# -SkipBundle: reuse an existing dist\ (skip the slow PyInstaller step).
#
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1
param([switch]$SkipBundle, [switch]$Release)

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

# Default deliverable: the uncompressed runnable bundle, copied into Output.
$dest = "$out\PaperhandsBeatTools-$ver"
Write-Host "==> Copying runnable bundle -> $dest" -ForegroundColor Cyan
if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
Copy-Item "dist\PaperhandsBeatTools" $dest -Recurse

if ($Release) {
    # Installer (optional: only if Inno Setup is installed). Version is injected
    # so installer.iss never holds a stale number.
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
        Write-Host "==> Inno Setup not found - skipping Setup.exe." -ForegroundColor Yellow
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
}

# Purge anything in Output (file or folder) that isn't the current version, so
# the folder always matches what we're working on. In the default (non-Release)
# build the deliverable is just the runnable folder, so drop release-only files.
Write-Host "==> Pruning stale artifacts..." -ForegroundColor Cyan
Get-ChildItem $out | Where-Object {
    ($_.Name -notlike "*$ver*") -or
    (-not $Release -and $_.PSIsContainer -eq $false)   # release-only files (zip/exe/sha)
} | ForEach-Object {
    Write-Host "  removing $($_.Name)" -ForegroundColor DarkGray
    Remove-Item $_.FullName -Recurse -Force
}

Write-Host "Done. Output now matches v${ver}:" -ForegroundColor Green
Get-ChildItem $out | ForEach-Object { Write-Host "  $($_.Name)" }
