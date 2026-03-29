"""Generate Open Graph / Twitter Card images for book sharing."""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_FONTS_DIR = Path(__file__).resolve().parent.parent / "static" / "fonts"

W, H = 1200, 630

BG = (250, 246, 240)
TEXT_DARK = (29, 29, 31)
TEXT_MID = (120, 110, 100)
TEXT_LIGHT = (170, 160, 148)
ACCENT = (107, 83, 68)
RULE = (210, 200, 188)


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = _FONTS_DIR / name
    if path.exists():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size)


def _wrap(text: str, font, max_w: int, draw: ImageDraw.ImageDraw) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        test = f"{cur} {w}".strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [text]


def _text_centered(draw, y, text, font, fill, max_w=None):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, y), text, fill=fill, font=font)
    return bbox[3] - bbox[1]


def _draw_logo(draw: ImageDraw.ImageDraw, cx: int, cy: int, s: float, color):
    lw = max(2, round(2.5 * s))
    draw.line([(cx - 18*s, cy + 20*s), (cx, cy)], fill=color, width=lw)
    draw.line([(cx + 18*s, cy + 20*s), (cx, cy)], fill=color, width=lw)
    r = 3 * s
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=color)
    pts = []
    import math
    for i in range(14):
        t = i / 13.0
        y = cy - t * 22 * s
        x = cx + 4 * s * math.sin(t * math.pi * 3)
        pts.append((x, y))
    if len(pts) > 1:
        draw.line(pts, fill=color, width=lw)


def generate_og_image(
    title: str,
    subtitle: str = "",
    chapter_count: int = 0,
    total_words: int = 0,
) -> bytes:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    ft = _font("Georgia-Bold.ttf", 46)
    fs = _font("Georgia-Regular.ttf", 19)
    fm = _font("Arial-Regular.ttf", 15)
    fi = _font("Georgia-Regular.ttf", 13)

    px = 100
    cw = W - 2 * px

    # Top rule
    draw.line([(px, 80), (W - px, 80)], fill=RULE, width=1)

    # Title
    lines = _wrap(title, ft, cw, draw)[:3]
    lh = 62
    ty = 150 - (len(lines) - 1) * 12
    for i, ln in enumerate(lines):
        _text_centered(draw, ty + i * lh, ln, ft, TEXT_DARK)
    cur_y = ty + len(lines) * lh

    # Subtitle
    if subtitle:
        cur_y += 8
        slines = _wrap(subtitle, fs, cw - 60, draw)[:2]
        for i, ln in enumerate(slines):
            _text_centered(draw, cur_y + i * 28, ln, fs, TEXT_MID)
        cur_y += len(slines) * 28

    # Meta
    parts = []
    if chapter_count:
        parts.append(f"{chapter_count} chapters")
    if total_words:
        parts.append(f"{total_words:,} words")
    if parts:
        cur_y += 20
        _text_centered(draw, cur_y, "  ·  ".join(parts), fm, TEXT_LIGHT)

    # Bottom rule
    rule_y = H - 110
    draw.line([(px, rule_y), (W - px, rule_y)], fill=RULE, width=1)

    # Publisher imprint: logo + FEYNMAN text
    logo_cx = W // 2
    logo_cy = rule_y + 38
    _draw_logo(draw, logo_cx, logo_cy, 1.0, TEXT_LIGHT)

    imprint = "FEYNMAN"
    bbox = draw.textbbox((0, 0), imprint, font=fi)
    iw = bbox[2] - bbox[0]
    draw.text(((W - iw) // 2, logo_cy + 28), imprint, fill=TEXT_LIGHT, font=fi)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
