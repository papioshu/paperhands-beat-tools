"""Check GitHub Releases for a newer version (pure stdlib; no Qt).

Compares the running ``app.version.__version__`` against the latest GitHub
release tag. This module only *detects* an update and points at the release;
actually installing it is the installer's job (the packaged app downloads and
runs the new installer). Network failures degrade quietly.
"""

from __future__ import annotations

import json
import shutil
import urllib.request
from typing import Tuple


def parse_version(s: str) -> tuple:
    """'v1.2.3' / '1.2.3' -> (1, 2, 3); missing/garbage parts become 0."""
    s = (s or "").strip().lstrip("vV")
    parts = []
    for chunk in s.split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def is_newer(latest: str, current: str) -> bool:
    return parse_version(latest) > parse_version(current)


def fetch_latest_release(owner: str, repo: str, timeout: float = 5.0) -> dict:
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "PaperhandBeatTools",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return {
        "tag": data.get("tag_name", ""),
        "url": data.get("html_url", ""),
        "name": data.get("name", ""),
        "installer_url": _pick_installer(data.get("assets", [])),
    }


def _pick_installer(assets: list) -> str:
    """Prefer a setup/installer .exe asset; fall back to any .exe."""
    exes = [a for a in assets if a.get("name", "").lower().endswith(".exe")]
    for a in exes:
        n = a.get("name", "").lower()
        if "setup" in n or "install" in n:
            return a.get("browser_download_url", "")
    return exes[0].get("browser_download_url", "") if exes else ""


def latest_installer_url(repo: str, timeout: float = 5.0) -> str:
    """The latest release's installer download URL, or '' if none/unreachable."""
    if not repo or "/" not in repo:
        return ""
    owner, name = repo.split("/", 1)
    try:
        return fetch_latest_release(owner.strip(), name.strip(), timeout).get(
            "installer_url", "")
    except Exception:  # noqa: BLE001
        return ""


def download(url: str, dest: str, timeout: float = 60.0) -> str:
    """Download ``url`` to ``dest`` (streamed), then verify its SHA256.

    If the release publishes ``<url>.sha256``, the download is checked against it
    and a mismatch raises (refusing a tampered/corrupt update). If no checksum is
    published, the download proceeds unverified.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "PaperhandBeatTools"})
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as fh:
        shutil.copyfileobj(resp, fh)
    expected = _fetch_text(url + ".sha256", timeout=10.0)
    if expected and not verify_sha256(dest, expected):
        raise ValueError("Update failed verification (SHA256 mismatch).")
    return dest


def sha256_file(path: str, _bufsize: int = 1 << 20) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_bufsize), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_sha256(path: str, expected: str) -> bool:
    """True if ``path``'s digest matches ``expected`` (a hex digest, optionally
    followed by a filename as in ``sha256sum`` output)."""
    if not expected:
        return False
    return sha256_file(path).lower() == expected.split()[0].lower()


def _fetch_text(url: str, timeout: float = 10.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "PaperhandBeatTools"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "replace").strip()
    except Exception:  # noqa: BLE001 - no published checksum -> unverified
        return ""


def check_for_update(current: str, repo: str, timeout: float = 5.0) -> Tuple[bool, str, str, str]:
    """Return ``(update_available, latest_tag, release_url, error)``.

    ``repo`` is "owner/name". Returns a non-empty error string (and no update)
    when unconfigured or the network call fails.
    """
    if not repo or "/" not in repo:
        return (False, "", "", "no update repo configured")
    owner, name = repo.split("/", 1)
    try:
        rel = fetch_latest_release(owner.strip(), name.strip(), timeout)
    except Exception as exc:  # noqa: BLE001 - offline / rate-limited / 404
        return (False, "", "", str(exc))
    return (is_newer(rel["tag"], current), rel["tag"], rel["url"], "")
