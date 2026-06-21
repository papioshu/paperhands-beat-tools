"""Procedural cover-art generation (Pillow) and importing your own image.

Generation is the *optional* path — produce a clean abstract cover seeded from a
beat's key/mood/BPM when you want to create or change artwork. Importing simply
copies your own image into the artwork folder. Pillow is imported lazily so the
rest of the engine doesn't depend on it.
"""

from __future__ import annotations

import colorsys
import hashlib
import random
import shutil
from pathlib import Path
from typing import Optional


def _seed_from(text: str) -> int:
    return int(hashlib.md5((text or "x").encode("utf-8")).hexdigest(), 16)


def _hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


def import_artwork(src_path: str, dst_path: str) -> str:
    """Copy a user-supplied image into the artwork folder (verbatim)."""
    Path(dst_path).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_path, dst_path)
    return dst_path


def generate_artwork(
    out_path: str,
    *,
    title: str = "",
    bpm: Optional[float] = None,
    key: Optional[str] = None,
    mood: Optional[str] = None,
    size: int = 1400,
) -> str:
    """Render an abstract cover PNG seeded from the beat's metadata."""
    from PIL import Image, ImageDraw, ImageFont

    seed_text = "|".join([key or "", mood or "", title or "x"])
    seed = _seed_from(seed_text)
    rng = random.Random(seed)
    hue = (seed % 360) / 360.0

    top = _hsv(hue, 0.55, 0.22)
    bottom = _hsv((hue + 0.08) % 1.0, 0.65, 0.55)

    img = Image.new("RGB", (size, size), top)
    # vertical gradient
    for y in range(size):
        t = y / size
        col = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        ImageDraw.Draw(img).line([(0, y), (size, y)], fill=col)

    # translucent accent shapes; count/scale nudged by BPM
    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    n_shapes = 5 + (int(bpm) % 6 if bpm else 3)
    accent = _hsv((hue + 0.5) % 1.0, 0.7, 0.95)
    for _ in range(n_shapes):
        r = rng.randint(size // 12, size // 3)
        cx, cy = rng.randint(0, size), rng.randint(0, size)
        alpha = rng.randint(20, 70)
        odraw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*accent, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    title_font = ImageFont.load_default(size=size // 14)
    sub_font = ImageFont.load_default(size=size // 28)

    text = (title or "Untitled").strip()
    draw.text((size * 0.08, size * 0.40), text, font=title_font, fill=(245, 245, 245))

    sub_bits = []
    if bpm is not None:
        sub_bits.append(f"{int(round(bpm))} BPM")
    if key:
        sub_bits.append(key)
    if mood:
        sub_bits.append(mood)
    if sub_bits:
        draw.text((size * 0.08, size * 0.40 + size // 11), "  ·  ".join(sub_bits),
                  font=sub_font, fill=(220, 220, 220))

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path
