"""Output-filename construction (pure logic, no audio libraries).

The rules (from the spec):

* Preserve the original filename.
* Append BPM and key tokens **only if they are not already present**, so re-runs
  and already-labelled beats don't accumulate duplicate tokens.
* Append a ``_tagged`` suffix (configurable), but never double it.

Example:  ``Midnight.mp3`` + 140 BPM + F# minor  ->  ``Midnight_140BPM_Fsharpmin_tagged``
          ``Midnight_140BPM_Fsharpmin.mp3``       ->  ``Midnight_140BPM_Fsharpmin_tagged``
"""

from __future__ import annotations

import re
from typing import Optional

# Matches an existing BPM token like "140bpm", "140 BPM", "92Bpm".
# No leading \b: an underscore ("Beat_140BPM") is a word char, so \b would miss
# it. A negative lookbehind for a digit is enough to avoid matching mid-number.
_BPM_TOKEN = re.compile(r"(?i)(?<!\d)\d{2,3}\s*bpm")

# Matches an existing key token like "Fsharpmin", "F#min", "Bbmaj", "Amin",
# "G minor". Note + optional accidental (#, b, sharp, flat) + quality.
_KEY_TOKEN = re.compile(
    r"(?i)(?<![A-Za-z])[A-G](?:#|b|sharp|flat)?\s?(?:min|maj|minor|major)(?![A-Za-z])"
)


def has_bpm_token(stem: str) -> bool:
    """True if the filename stem already carries a BPM label."""
    return bool(_BPM_TOKEN.search(stem))


def has_key_token(stem: str) -> bool:
    """True if the filename stem already carries a musical-key label."""
    return bool(_KEY_TOKEN.search(stem))


def format_key_for_filename(key: str) -> str:
    """Turn a canonical key like ``F#min`` / ``Bbmaj`` into a filename-safe token.

    ``#`` -> ``sharp`` and a flat ``b`` -> ``flat`` (so the result is unambiguous
    and path-legal). ``minor``/``major`` are shortened to ``min``/``maj``.

        >>> format_key_for_filename("F#min")
        'Fsharpmin'
        >>> format_key_for_filename("Bbmaj")
        'Bflatmaj'
        >>> format_key_for_filename("A minor")
        'Amin'
    """
    if not key:
        return ""
    s = key.strip().replace(" ", "")
    note = s[0].upper()
    rest = s[1:]

    accidental = ""
    if rest[:1] == "#":
        accidental, rest = "sharp", rest[1:]
    elif rest[:5].lower() == "sharp":
        accidental, rest = "sharp", rest[5:]
    elif rest[:1] == "b" and rest[1:2] != "":  # a lone "B" note has no rest
        accidental, rest = "flat", rest[1:]
    elif rest[:4].lower() == "flat":
        accidental, rest = "flat", rest[4:]

    quality = rest.lower()
    if quality.startswith("minor"):
        quality = "min"
    elif quality.startswith("major"):
        quality = "maj"
    return f"{note}{accidental}{quality}"


def build_output_stem(
    original_stem: str,
    bpm: Optional[float] = None,
    key: Optional[str] = None,
    suffix: str = "_tagged",
) -> str:
    """Build the output filename stem (no extension).

    Args:
        original_stem: Source filename without extension (e.g. ``"Midnight"``).
        bpm: Detected/overridden BPM, or ``None`` to skip the BPM token.
        key: Canonical key string (e.g. ``"F#min"``), or ``None``/empty to skip.
        suffix: Appended once at the end; never doubled.
    """
    parts = [original_stem]

    if bpm is not None and not has_bpm_token(original_stem):
        parts.append(f"{int(round(bpm))}BPM")

    if key and not has_key_token(original_stem):
        parts.append(format_key_for_filename(key))

    stem = "_".join(parts)

    if suffix and not stem.lower().endswith(suffix.lower()):
        stem += suffix
    return stem
