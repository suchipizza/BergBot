"""Mascot asset pipeline and lookup (FR-B1..B4).

`build_assets()` reads brand/mascot/src/<variant>.{png,svg}, removes a near-white background, and writes
dist/<variant>.webp (256 px, ≤ 40 KB), dist/<variant>-512.png, dist/<variant>.datauri.txt and dist/avatar.png.
`mascot_datauri(variant)` returns the inline snippet for the report or a neutral placeholder SVG when no art
exists — the build never depends on the artwork. Placement rules live in manifest.json and the templates."""

from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Any

from bergbot.paths import brand_dir

MAX_WEBP_BYTES = 40_000
SIZE = 256
AVATAR = 512


@lru_cache(maxsize=1)
def manifest() -> dict[str, Any]:
    path = brand_dir() / "manifest.json"
    if not path.exists():
        return {"variants": ["default"], "fallback": "default", "activity_to_variant": {}, "placements": {}}
    return dict(json.loads(path.read_text(encoding="utf-8")))


def variant_for_activity(activity: str) -> str:
    m = manifest()
    v = m.get("activity_to_variant", {}).get(activity, m.get("fallback", "default"))
    return str(v)


def _dist(variant: str) -> Path:
    return brand_dir() / "dist" / f"{variant}.datauri.txt"


def mascot_datauri(variant: str) -> str:
    """Data URI (webp) for `variant`, falling back to the manifest fallback, then to a placeholder SVG."""
    m = manifest()
    for v in (variant, str(m.get("fallback", "default"))):
        p = _dist(v)
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    return placeholder_datauri(variant)


def placeholder_datauri(variant: str) -> str:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SIZE}" height="{SIZE}" viewBox="0 0 {SIZE} {SIZE}">'
        f'<rect width="{SIZE}" height="{SIZE}" rx="24" fill="#e8ecef"/>'
        f'<text x="50%" y="52%" text-anchor="middle" font-family="sans-serif" font-size="22" fill="#6b7680">{variant}</text></svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def has_art(variant: str) -> bool:
    return _dist(variant).exists()


def build_assets() -> Iterator[str]:
    from PIL import Image

    src_dir = brand_dir() / "src"
    dist = brand_dir() / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    m = manifest()
    sources = sorted(src_dir.glob("*.png")) + sorted(src_dir.glob("*.PNG"))
    if not sources:
        yield "no source art in brand/mascot/src — placeholders will be used"
        return
    for path in sources:
        variant = path.stem
        im = Image.open(path).convert("RGBA")
        im = _remove_background(im)
        im = _trim(im)
        big = _fit(im, AVATAR)
        big.save(dist / f"{variant}-512.png", format="PNG", optimize=True)
        small = _fit(im, SIZE)
        data = _encode_webp(small)
        (dist / f"{variant}.webp").write_bytes(data)
        uri = "data:image/webp;base64," + base64.b64encode(data).decode("ascii")
        (dist / f"{variant}.datauri.txt").write_text(uri, encoding="utf-8")
        yield f"{variant}: webp {len(data) // 1024} KB, png-512 {(dist / f'{variant}-512.png').stat().st_size // 1024} KB"
    avatar_variant = str(m.get("avatar_variant", "default"))
    src = dist / f"{avatar_variant}-512.png"
    if src.exists():
        av = Image.open(src).convert("RGBA")
        canvas = Image.new("RGBA", (AVATAR, AVATAR), (255, 255, 255, 255))
        canvas.alpha_composite(av, ((AVATAR - av.width) // 2, (AVATAR - av.height) // 2))
        canvas.convert("RGB").save(dist / "avatar.png", format="PNG", optimize=True)
        yield f"avatar.png from {avatar_variant}"


def _remove_background(im: Any, threshold: int = 222) -> Any:
    """Flood-fill transparent from the borders through near-white pixels; keeps white on the character."""
    from collections import deque

    w, h = im.size
    px = im.load()

    seen = bytearray(w * h)
    q: deque[tuple[int, int]] = deque([(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)])
    while q:
        x, y = q.popleft()
        if x < 0 or y < 0 or x >= w or y >= h or seen[y * w + x]:
            continue
        r, g, b, a = px[x, y]
        if min(r, g, b) < threshold:
            continue
        seen[y * w + x] = 1
        px[x, y] = (r, g, b, 0)
        q.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    # feather: opaque near-white pixels touching the removed region fade out instead of leaving a halo
    for y in range(h):
        for x in range(w):
            if seen[y * w + x]:
                continue
            r, g, b, a = px[x, y]
            v = min(r, g, b)
            if v < 200:
                continue
            near = any(
                0 <= x + dx < w and 0 <= y + dy < h and seen[(y + dy) * w + (x + dx)]
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (2, 0), (-2, 0), (0, 2), (0, -2))
            )
            if near:
                alpha = int(max(0, min(255, (255 - v) * 255 / 55)))
                px[x, y] = (r, g, b, alpha)
    return im


def _trim(im: Any) -> Any:
    bbox = im.getbbox()
    return im.crop(bbox) if bbox else im


def _fit(im: Any, size: int) -> Any:
    from PIL import Image

    scale = min(size / im.width, size / im.height)
    out = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.Resampling.LANCZOS)
    return out


def _encode_webp(im: Any) -> bytes:
    import io

    for q in (82, 72, 62, 52, 42, 32):
        buf = io.BytesIO()
        im.save(buf, format="WEBP", quality=q, method=6)
        data = buf.getvalue()
        if len(data) <= MAX_WEBP_BYTES:
            return data
    return data
