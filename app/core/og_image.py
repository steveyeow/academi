"""Generate Open Graph / Twitter Card images matching the reader cover aesthetic."""
from __future__ import annotations

import io
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_FONTS_DIR = Path(__file__).resolve().parent.parent / "static" / "fonts"

W, H = 1200, 630

BG = (30, 28, 26)
TEXT_PRIMARY = (240, 236, 228)
TEXT_SECONDARY = (170, 164, 152)
TEXT_MUTED = (120, 114, 104)
ACCENT = (185, 160, 120)
RULE = (65, 60, 52)


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


def _text_centered(draw: ImageDraw.ImageDraw, y: int, text: str, font, fill,
                    left: int, right: int) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    cx = left + (right - left - tw) // 2
    draw.text((cx, y), text, fill=fill, font=font)
    return th


def _draw_feynman_mark(draw: ImageDraw.ImageDraw, cx: int, cy: int, s: float, color):
    lw = max(2, round(2.5 * s))
    draw.line([(cx - 18 * s, cy + 20 * s), (cx, cy)], fill=color, width=lw)
    draw.line([(cx + 18 * s, cy + 20 * s), (cx, cy)], fill=color, width=lw)
    r = 3 * s
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=color)
    pts = []
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
    author: str = "",
) -> bytes:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    pad_x = 80
    content_l = pad_x
    content_r = W - pad_x
    content_w = content_r - content_l
    cx = W // 2

    ft_title = _font("Georgia-Bold.ttf", 48)
    ft_sub = _font("Georgia-Regular.ttf", 20)
    ft_author = _font("Georgia-Regular.ttf", 18)
    ft_meta = _font("Arial-Regular.ttf", 14)
    ft_brand = _font("Georgia-Regular.ttf", 13)

    # --- Layout: compute heights to vertically center the content block ---
    title_lines = _wrap(title, ft_title, content_w, draw)[:3]
    title_line_h = 62
    block_h = len(title_lines) * title_line_h

    if subtitle:
        sub_lines = _wrap(subtitle, ft_sub, content_w - 40, draw)[:2]
        block_h += 16 + len(sub_lines) * 28
    else:
        sub_lines = []

    block_h += 32  # gap before author
    if author:
        block_h += 24
    block_h += 28  # gap before stats
    block_h += 18  # stats line

    # Center the block vertically with slight upward bias
    top_y = max(50, (H - block_h) // 2 - 20)
    cur_y = top_y

    # --- Title ---
    for ln in title_lines:
        _text_centered(draw, cur_y, ln, ft_title, TEXT_PRIMARY, content_l, content_r)
        cur_y += title_line_h

    # --- Subtitle ---
    if sub_lines:
        cur_y += 16
        for ln in sub_lines:
            _text_centered(draw, cur_y, ln, ft_sub, TEXT_SECONDARY, content_l, content_r)
            cur_y += 28

    # --- Author ---
    cur_y += 32
    if author:
        _text_centered(draw, cur_y, author, ft_author, TEXT_SECONDARY, content_l, content_r)
        cur_y += 24

    # --- Stats line (chapters · words · read time) ---
    cur_y += 28
    parts = []
    if total_words:
        parts.append(f"{total_words:,} words")
    read_min = max(1, round(total_words / 230)) if total_words else 0
    if read_min:
        parts.append(f"~{read_min} min read")
    if chapter_count:
        parts.append(f"{chapter_count} chapters")
    if parts:
        stats_text = "  \u00b7  ".join(parts)
        _text_centered(draw, cur_y, stats_text, ft_meta, TEXT_MUTED, content_l, content_r)

    # --- Accent rule above the branding ---
    rule_y = H - 74
    rule_hw = 50
    draw.line([(cx - rule_hw, rule_y), (cx + rule_hw, rule_y)], fill=ACCENT, width=2)

    # --- Feynman brand mark + text ---
    brand_y = H - 44
    brand_text = "FEYNMAN"
    bbbox = draw.textbbox((0, 0), brand_text, font=ft_brand)
    bw = bbbox[2] - bbbox[0]
    bh = bbbox[3] - bbbox[1]
    logo_s = 0.5
    logo_w = 36 * logo_s
    gap = 8
    group_w = logo_w + gap + bw
    gx = cx - group_w // 2
    _draw_feynman_mark(draw, int(gx + logo_w // 2), brand_y - 2, logo_s, TEXT_MUTED)
    draw.text((int(gx + logo_w + gap), brand_y - bh // 2), brand_text,
              fill=TEXT_MUTED, font=ft_brand)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
