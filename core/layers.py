"""Tag-layer model + mixing rules (pure; no audio/Qt).

A *layer* is one producer tag used on a beat, with its own volume/pan and
mute/solo/enable state. Placements reference a tag; the layer for that tag
decides whether (and how loud / where) each placement sounds. Solo/mute/enable
filtering is pure and unit-tested; the audio engine applies the gain/pan.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class TagLayer:
    volume_db: float = 0.0     # gain applied to this tag
    pan: float = 0.0           # -1 left .. +1 right
    mute: bool = False
    solo: bool = False
    enabled: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


def default_layer() -> dict:
    return TagLayer().to_dict()


def active_tag_paths(layers: dict) -> set:
    """Tags that should sound, honoring enable + mute + solo.

    If any layer is soloed, only soloed (and enabled, un-muted) layers sound.
    """
    soloed = any(l.get("solo") for l in layers.values())
    active = set()
    for path, l in layers.items():
        if not l.get("enabled", True) or l.get("mute"):
            continue
        if soloed and not l.get("solo"):
            continue
        active.add(path)
    return active


def filter_placements(placements, layers: dict):
    """Keep only placements whose layer is currently audible.

    With no layer info (empty dict) all placements pass — preserves the original
    behavior for callers that don't use layers.
    """
    if not layers:
        return list(placements)
    active = active_tag_paths(layers)
    return [p for p in placements if p.tag_path in active]
