"""Check GitHub Releases for a newer version (pure stdlib; no Qt).

Compares the running ``app.version.__version__`` against the latest GitHub
release tag. This module only *detects* an update and points at the release;
actually installing it is the installer's job (the packaged app downloads and
runs the new installer). Network failures degrade quietly.
"""

from __future__ import annotations

import json
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
    }


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
