"""Shareable MP4: an 8-bit title-screen card (Pillow: pixel wordmark from logo.py + Press Start 2P text) with the
user's message and an animated waveform (ffmpeg showwaves) married to the mastered audio. Square 1080x1080 —
plays everywhere, posts everywhere.

    python3 video.py out.mp3 "hey julie can you grab dog food" out.mp4
"""
import os
import subprocess
import sys
import textwrap

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import logo

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_PIXEL = os.path.join(HERE, "fonts", "PressStart2P-Regular.ttf")
W = H = 1080
WAVE_H = 252  # 21 blocks of 12 px
WAVE_PX = 12  # size of one waveform block — the meter is drawn tiny and blown up with nearest-neighbour
WAVE_Y = H - WAVE_H - 90
LOGO_SCALE = 10  # 95 px grid -> 950 px wide
STYLE = "fire"  # main.py sets this from LOGO_STYLE; colours the wordmark, glow, text shadows and the meter


def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)


def _pixel_lines(text, max_w, sizes=(32, 24, 16), max_lines=2):
    """Press Start 2P is drawn on an 8-px grid, so only multiples of 8 stay crisp. Largest size that fits on one
    line wins; otherwise wrap at the smaller sizes. Returns (font, lines)."""
    for size in sizes:
        font = _font(FONT_PIXEL, size)
        if font.getlength(text) <= max_w:
            return font, [text]
    for size in sizes[1:]:
        font = _font(FONT_PIXEL, size)
        lines = textwrap.wrap(text, width=max(8, int(max_w // size)))
        if len(lines) <= max_lines and all(font.getlength(l) <= max_w for l in lines):
            return font, lines
    font = _font(FONT_PIXEL, sizes[-1])
    return font, textwrap.wrap(text, width=max(8, int(max_w // sizes[-1])))[:max_lines]


def _pixel_text(d, xy, text, font, fill, shadow=(60, 12, 0), drop=None):
    """Hard-edged drop shadow (no blur, no anti-aliased stroke) — the 8-bit way."""
    x, y = xy
    drop = drop or max(2, font.size // 8)
    d.text((x + drop, y + drop), text, font=font, fill=shadow, anchor="ma")
    d.text((x, y), text, font=font, fill=fill, anchor="ma")


def _pixel_paragraph(text, max_w, max_h, sizes=(56, 48, 40, 32, 24), leading=1.45):
    """The message itself: largest 8-px-grid size whose wrapped lines fit the box. Returns (font, lines, line_h)."""
    font, lines, line_h = None, [], 0
    for size in sizes:
        font = _font(FONT_PIXEL, size)
        lines = textwrap.wrap(text, width=max(6, int(max_w // size))) or [text]
        line_h = int(size * leading)
        if all(font.getlength(l) <= max_w for l in lines) and len(lines) * line_h <= max_h:
            break
    return font, lines, line_h


def make_card(message, out_png, intro_line=None, style=None):
    style = style or STYLE
    ui = logo.STYLES[style]["ui"]
    gr, gg, gb = ui["glow"]
    img = Image.new("RGB", (W, H), (12, 10, 14))
    d = ImageDraw.Draw(img)
    # arena glow at the bottom, in the palette's colour
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r in range(900, 0, -12):
        t = r / 900
        gd.ellipse([W // 2 - r, H - 120 - r * 0.55, W // 2 + r, H - 120 + r * 0.55],
                   fill=(int(gr * 0.43 * (1 - t)), int(gg * 0.43 * (1 - t)), int(gb * 0.43 * (1 - t))))
    glow = glow.filter(ImageFilter.GaussianBlur(40))
    img = Image.blend(img, Image.composite(glow, img, glow.convert("L").point(lambda v: min(255, v * 3))), 0.85)
    d = ImageDraw.Draw(img)
    # speed lines
    for i in range(0, W, 54):
        d.line([(i, 0), (i - 260, H)], fill=(22, 18, 26), width=2)
    # CRT scanlines, faint
    for y in range(0, H, 4):
        d.line([(0, y), (W, y)], fill=(8, 6, 10), width=1)
    # 8-bit wordmark (pixel art, nearest-neighbour — every block stays a hard square)
    mark = logo.render(LOGO_SCALE, style)
    img.paste(mark, ((W - mark.size[0]) // 2, 44), mark)
    d = ImageDraw.Draw(img)
    # intro line in the arcade font, hard drop shadow
    sub_text = (intro_line or "SUNDAY! SUNDAY! SUNDAY!").upper().replace(",", "!")
    sub_font, sub_lines = _pixel_lines(sub_text, W - 120)
    y = 44 + mark.size[1] + 34
    for l in sub_lines:
        _pixel_text(d, (W // 2, y), l, sub_font, fill=logo._hex(ui["sun"]), shadow=logo._hex(ui["rust"]))
        y += int(sub_font.size * 1.5)
    top = y + 16
    # the message, white on a hard rust shadow like an NES text box
    body_font, lines, line_h = _pixel_paragraph(message.upper(), W - 120, WAVE_Y - 30 - top)
    y = top + ((WAVE_Y - 30) - top - len(lines) * line_h) // 2
    for l in lines:
        _pixel_text(d, (W // 2, y), l, body_font, fill=(255, 255, 255), shadow=ui["shadow"])
        y += line_h
    # waveform baseline + footer
    d.line([(60, WAVE_Y + WAVE_H // 2), (W - 60, WAVE_Y + WAVE_H // 2)], fill=tuple(int(v * 0.3) for v in logo._hex(ui["hot"])), width=2)
    _pixel_text(d, (W // 2, H - 58), "TYPE ANYTHING. GET THE TREATMENT.", _font(FONT_PIXEL, 16),
                fill=(160, 140, 130), shadow=(0, 0, 0))
    img.save(out_png, "PNG")
    return out_png


def make_mp4(mp3_path, message, out_mp4, intro_line=None, tmpdir=None, style=None):
    style = style or STYLE
    tmpdir = tmpdir or os.path.dirname(os.path.abspath(out_mp4))
    card = make_card(message, os.path.join(tmpdir, "card.png"), intro_line, style)
    fc = (f"[1:a]aformat=channel_layouts=mono,showwaves=s={W // WAVE_PX}x{WAVE_H // WAVE_PX}:mode=cline:rate=30:"
          f"colors={logo.STYLES[style]['ui']['wave']}:scale=sqrt,scale={W}:{WAVE_H}:flags=neighbor,format=rgba[w];"
          f"[0:v][w]overlay=0:{WAVE_Y}:shortest=1,format=yuv420p[v]")
    cmd = ["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", "30", "-i", card, "-i", mp3_path,
           "-filter_complex", fc, "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "25", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", out_mp4]
    subprocess.run(cmd, check=True)
    return out_mp4


if __name__ == "__main__":
    mp3, msg, out = sys.argv[1], sys.argv[2], sys.argv[3]
    print(make_mp4(mp3, msg, out))
