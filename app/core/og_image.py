"""Generate Open Graph / Twitter Card images — portrait book cover on dark field."""
from __future__ import annotations

import io
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_FONTS_DIR = Path(__file__).resolve().parent.parent / "static" / "fonts"

W, H = 1200, 630

# Card background
BG = (24, 22, 20)

# Book cover palette
COVER_BG = (250, 246, 238)
SPINE = (70, 60, 50)
SPINE_HIGHLIGHT = (185, 160, 120)
ACCENT = (139, 109, 82)
GOLD = (185, 160, 120)
RULE = (200, 188, 172)
TEXT_DARK = (29, 29, 31)
TEXT_MID = (100, 90, 80)
TEXT_LIGHT = (145, 135, 122)
TEXT_MUTED = (170, 160, 145)

# Right-side text (on the dark bg)
SIDE_TEXT = (200, 194, 184)
SIDE_MUTED = (120, 114, 104)


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
    draw.text((left + (right - left - tw) // 2, y), text, fill=fill, font=font)
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

    # --- Portrait book cover dimensions (left portion of card) ---
    cover_h = H - 60
    cover_w = int(cover_h * 0.68)
    spine_w = 18
    cover_x = 80
    cover_y = (H - cover_h) // 2

    # Shadow behind the book
    for i in range(8):
        alpha = 40 - i * 5
        if alpha <= 0:
            break
        c = max(0, 24 - i * 2)
        shadow_color = (c, c - 1 if c > 0 else 0, c - 2 if c > 1 else 0)
        draw.rectangle(
            [(cover_x + spine_w + i + 3, cover_y + i + 3),
             (cover_x + spine_w + cover_w + i + 3, cover_y + cover_h + i + 1)],
            fill=shadow_color,
        )

    # Spine
    draw.rectangle(
        [(cover_x, cover_y), (cover_x + spine_w, cover_y + cover_h)],
        fill=SPINE,
    )
    draw.line(
        [(cover_x + spine_w, cover_y), (cover_x + spine_w, cover_y + cover_h)],
        fill=SPINE_HIGHLIGHT, width=1,
    )

    # Cover face
    face_l = cover_x + spine_w + 1
    face_r = cover_x + spine_w + cover_w
    draw.rectangle([(face_l, cover_y), (face_r, cover_y + cover_h)], fill=COVER_BG)
    draw.rectangle([(face_l, cover_y), (face_r, cover_y + cover_h)], outline=RULE, width=1)

    face_cx = face_l + (face_r - face_l) // 2
    pad = 28
    text_l = face_l + pad
    text_r = face_r - pad
    text_w = text_r - text_l

    # Cover fonts
    ft_title = _font("Georgia-Bold.ttf", 28)
    ft_sub = _font("Georgia-Regular.ttf", 13)
    ft_author = _font("Georgia-Regular.ttf", 12)
    ft_meta = _font("Arial-Regular.ttf", 10)
    ft_imprint = _font("Georgia-Regular.ttf", 9)

    # Top accent band
    band_y = cover_y + 24
    draw.rectangle([(text_l + 10, band_y), (text_r - 10, band_y + 2)], fill=ACCENT)

    # Title on cover
    title_lines = _wrap(title, ft_title, text_w, draw)[:4]
    title_line_h = 36
    total_title_h = len(title_lines) * title_line_h

    title_zone_top = cover_y + 50
    title_zone_bot = cover_y + cover_h - 120
    title_start = title_zone_top + (title_zone_bot - title_zone_top - total_title_h) // 2
    title_start = max(title_start, title_zone_top)

    for i, ln in enumerate(title_lines):
        _text_centered(draw, title_start + i * title_line_h, ln, ft_title, TEXT_DARK, text_l, text_r)
    cur_y = title_start + len(title_lines) * title_line_h

    # Subtitle on cover
    if subtitle:
        cur_y += 8
        sub_lines = _wrap(subtitle, ft_sub, text_w - 16, draw)[:2]
        for i, ln in enumerate(sub_lines):
            _text_centered(draw, cur_y + i * 18, ln, ft_sub, TEXT_MID, text_l, text_r)

    # Bottom rule + author on cover
    bot_rule_y = cover_y + cover_h - 64
    draw.line([(text_l + 20, bot_rule_y), (text_r - 20, bot_rule_y)], fill=RULE, width=1)

    author_display = f"by {author}" if author else ""
    if author_display:
        _text_centered(draw, bot_rule_y + 10, author_display, ft_author, TEXT_MID, text_l, text_r)

    # Feynman imprint at bottom of cover
    imprint_y = cover_y + cover_h - 22
    _draw_feynman_mark(draw, face_cx - 20, imprint_y - 2, 0.35, TEXT_LIGHT)
    ibbox = draw.textbbox((0, 0), "FEYNMAN", font=ft_imprint)
    draw.text((face_cx - 8, imprint_y - (ibbox[3] - ibbox[1]) // 2 - 1),
              "FEYNMAN", fill=TEXT_LIGHT, font=ft_imprint)

    # --- Right side: info on dark background ---
    info_l = face_r + 60
    info_r = W - 60
    info_w = info_r - info_l
    if info_w < 100:
        info_l = face_r + 30
        info_r = W - 30
        info_w = info_r - info_l

    ft_side_title = _font("Georgia-Bold.ttf", 26)
    ft_side_sub = _font("Georgia-Regular.ttf", 15)
    ft_side_meta = _font("Arial-Regular.ttf", 13)
    ft_side_brand = _font("Georgia-Regular.ttf", 12)

    # Title (right side)
    side_title_lines = _wrap(title, ft_side_title, info_w, draw)[:3]
    side_y = cover_y + 30
    for ln in side_title_lines:
        draw.text((info_l, side_y), ln, fill=SIDE_TEXT, font=ft_side_title)
        side_y += 34

    # Subtitle (right side)
    if subtitle:
        side_y += 8
        side_sub_lines = _wrap(subtitle, ft_side_sub, info_w, draw)[:2]
        for ln in side_sub_lines:
            draw.text((info_l, side_y), ln, fill=SIDE_MUTED, font=ft_side_sub)
            side_y += 22

    # Author (right side)
    if author:
        side_y += 16
        draw.text((info_l, side_y), author, fill=SIDE_TEXT, font=ft_side_sub)
        side_y += 24

    # Stats
    parts = []
    if total_words:
        parts.append(f"{total_words:,} words")
    read_min = max(1, round(total_words / 230)) if total_words else 0
    if read_min:
        parts.append(f"~{read_min} min read")
    if chapter_count:
        parts.append(f"{chapter_count} chapters")
    if parts:
        side_y += 12
        draw.text((info_l, side_y), "  \u00b7  ".join(parts), fill=SIDE_MUTED, font=ft_side_meta)

    # feynman.wiki at bottom right
    brand_y = cover_y + cover_h - 16
    draw.text((info_l, brand_y), "feynman.wiki", fill=SIDE_MUTED, font=ft_side_brand)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
