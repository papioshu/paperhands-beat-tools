"""Tests for app.updater version logic (pure; no network)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import updater  # noqa: E402


def test_parse_version_handles_v_prefix_and_garbage():
    assert updater.parse_version("v1.2.3") == (1, 2, 3)
    assert updater.parse_version("1.2.3") == (1, 2, 3)
    assert updater.parse_version("v2.0") == (2, 0)
    assert updater.parse_version("") == (0,)


def test_is_newer():
    assert updater.is_newer("v1.2.0", "1.1.9")
    assert updater.is_newer("2.0.0", "1.9.9")
    assert not updater.is_newer("1.0.0", "1.0.0")
    assert not updater.is_newer("0.9.0", "1.0.0")


def test_check_for_update_requires_repo():
    avail, tag, url, err = updater.check_for_update("0.1.0", "")
    assert avail is False
    assert err  # message explaining it's unconfigured


def test_check_for_update_handles_bad_repo_string():
    avail, *_rest, err = updater.check_for_update("0.1.0", "not-a-repo")
    assert avail is False
    assert err
