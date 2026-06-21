"""Build ID3 metadata for exported MP3s (pure logic, no audio libraries).

The exported tag dict is consumed by pydub's ``export(tags=...)`` (which passes
them to ffmpeg). Producer name maps to the ID3 *artist*; BPM/key/mood/free-tags
are folded into the *comment* so they travel with the file.
"""

from __future__ import annotations

from typing import Dict, List, Optional

DEFAULT_PRODUCER = "paperhand"


def build_id3_tags(
    producer: str = DEFAULT_PRODUCER,
    *,
    title: Optional[str] = None,
    genre: Optional[str] = None,
    bpm: Optional[float] = None,
    key: Optional[str] = None,
    mood: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, str]:
    """Return an ffmpeg/pydub-ready tag dict, omitting empty fields.

        >>> build_id3_tags("paperhand", title="Night", bpm=140, key="F#min")
        {'artist': 'paperhand', 'title': 'Night', 'comment': '140 BPM | F#min'}
    """
    meta: Dict[str, str] = {}
    if producer:
        meta["artist"] = producer
        meta["album_artist"] = producer
    if title:
        meta["title"] = title
    if genre:
        meta["genre"] = genre
    if bpm is not None:
        meta["BPM"] = str(int(round(bpm)))

    comment_parts: List[str] = []
    if bpm is not None:
        comment_parts.append(f"{int(round(bpm))} BPM")
    if key:
        comment_parts.append(key)
    if mood:
        comment_parts.append(mood)
    if tags:
        comment_parts.append("tags: " + ", ".join(tags))
    if comment_parts:
        meta["comment"] = " | ".join(comment_parts)

    return meta
