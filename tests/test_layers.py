"""Tests for core.layers (solo/mute/enable filtering, pure)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import layers  # noqa: E402
from core.models import Placement  # noqa: E402


def _layers(**overrides):
    base = {"a.wav": layers.default_layer(), "b.wav": layers.default_layer()}
    for path, props in overrides.items():
        base[path].update(props)
    return base


def test_default_layer_audible():
    assert layers.active_tag_paths(_layers()) == {"a.wav", "b.wav"}


def test_mute_removes_layer():
    out = layers.active_tag_paths(_layers(**{"a.wav": {"mute": True}}))
    assert out == {"b.wav"}


def test_disabled_removes_layer():
    out = layers.active_tag_paths(_layers(**{"a.wav": {"enabled": False}}))
    assert out == {"b.wav"}


def test_solo_isolates():
    out = layers.active_tag_paths(_layers(**{"a.wav": {"solo": True}}))
    assert out == {"a.wav"}


def test_solo_plus_mute_on_same_layer_is_silent():
    out = layers.active_tag_paths(_layers(**{"a.wav": {"solo": True, "mute": True}}))
    assert out == set()


def test_filter_placements_respects_layers():
    pls = [Placement(0, "a.wav"), Placement(10, "b.wav"), Placement(20, "a.wav")]
    out = layers.filter_placements(pls, _layers(**{"b.wav": {"mute": True}}))
    assert [p.tag_path for p in out] == ["a.wav", "a.wav"]


def test_filter_with_no_layers_passes_all():
    pls = [Placement(0, "a.wav"), Placement(10, "b.wav")]
    assert layers.filter_placements(pls, {}) == pls
