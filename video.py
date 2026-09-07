"""Shareable MP4: a branded card (Pillow) with the user's message + an animated waveform (ffmpeg showwaves)
married to the mastered audio. Square 1080x1080 by default — plays everywhere, posts everywhere.

    python3 video.py out.mp3 "hey julie can you grab dog food" out.mp4
"""
import os
import subprocess
import sys
import textwrap

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_TITLE = os.path.join(HERE, "fonts", "Bangers-Regular.ttf")
FONT_BODY = os.path.join(HERE, "fonts", "Anton-Regular.ttf")
FONT_SMALL = os.path.join(HERE, "fonts", "BebasNeue-Regular.ttf")
W = H = 1080
WAVE_H = 250
WAVE_Y = H - WAVE_H - 90


def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)


def _gradient_text(size, text, font, top=(255, 236, 90), bottom=(255, 92, 0), stroke=10):
    """Text filled with a vertical gradient and a black outline, on a transparent layer."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).text((size[0] // 2, size[1] // 2), text, font=font, fill=255, anchor="mm")
    grad = Image.new("RGBA", size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(size[1]):
        t = y / max(1, size[1] - 1)
        c = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)) + (255,)
        gd.line([(0, y), (size[0], y)], fill=c)
    outline = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(outline).text((size[0] // 2, size[1] // 2), text, font=font, fill=(0, 0, 0, 255),
                                 anchor="mm", stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
    layer.alpha_composite(outline)
    layer.paste(grad, (0, 0), mask)
    return layer


def _skew(img, shear=-0.18):
    w, h = img.size
    pad = int(abs(shear) * h) + 2
    canvas = Image.new("RGBA", (w + 2 * pad, h), (0, 0, 0, 0))
    canvas.paste(img, (pad, 0))
    return canvas.transform(canvas.size, Image.AFFINE, (1, shear, -shear * h / 2 if shear < 0 else 0, 0, 1, 0),
                            resample=Image.BICUBIC)


def _fit_lines(text, font_path, max_w, max_h, start=150, min_size=64):
    """Largest font size whose wrapped text fits the box. Returns (font, lines)."""
    size = start
    while size >= min_size:
        font = _font(font_path, size)
        avg = font.getlength("ABCDEFGHIJKLMNOPQRSTUVWXYZ") / 26
        width = max(8, int(max_w / avg))
        lines = textwrap.wrap(text, width=width) or [text]
        line_h = int(size * 1.05)
        if all(font.getlength(l) <= max_w for l in lines) and len(lines) * line_h <= max_h:
            return font, lines
        size -= 8
    font = _font(font_path, min_size)
    return font, textwrap.wrap(text, width=28)[:5]


def make_card(message, out_png, intro_line=None):
    img = Image.new("RGB", (W, H), (12, 10, 14))
    d = ImageDraw.Draw(img)
    # arena glow: warm at the bottom, cool at the top
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r in range(900, 0, -12):
        t = r / 900
        gd.ellipse([W // 2 - r, H - 120 - r * 0.55, W // 2 + r, H - 120 + r * 0.55],
                   fill=(int(110 * (1 - t)), int(28 * (1 - t)), 0))
    glow = glow.filter(ImageFilter.GaussianBlur(40))
    img = Image.blend(img, Image.composite(glow, img, glow.convert("L").point(lambda v: min(255, v * 3))), 0.85)
    d = ImageDraw.Draw(img)
    # speed lines
    for i in range(0, W, 54):
        d.line([(i, 0), (i - 260, H)], fill=(22, 18, 26), width=2)
    # wordmark
    title = _gradient_text((W, 260), "TRUCK-A-FY", _font(FONT_TITLE, 190))
    title = _skew(title, -0.12)
    img.paste(title, ((W - title.size[0]) // 2, 38), title)
    d = ImageDraw.Draw(img)
    sub = _font(FONT_SMALL, 46)
    d.text((W // 2, 300), (intro_line or "SUNDAY! SUNDAY! SUNDAY!").upper().replace(",", "!"), font=sub,
           fill=(255, 176, 0), anchor="mm")
    # the message
    body_font, lines = _fit_lines(message.upper(), FONT_BODY, W - 140, WAVE_Y - 380)
    line_h = int(body_font.size * 1.05)
    y = 350 + ((WAVE_Y - 30) - 350 - len(lines) * line_h) // 2
    for l in lines:
        d.text((W // 2, y), l, font=body_font, fill=(255, 255, 255), anchor="ma",
               stroke_width=max(4, body_font.size // 16), stroke_fill=(0, 0, 0))
        y += line_h
    # waveform baseline + footer
    d.line([(60, WAVE_Y + WAVE_H // 2), (W - 60, WAVE_Y + WAVE_H // 2)], fill=(70, 40, 20), width=2)
    d.text((W // 2, H - 42), "TRUCK-A-FY   •   TYPE ANYTHING. GET THE TREATMENT.", font=_font(FONT_SMALL, 34),
           fill=(150, 130, 120), anchor="mm")
    img.save(out_png, "PNG")
    return out_png


def make_mp4(mp3_path, message, out_mp4, intro_line=None, tmpdir=None):
    tmpdir = tmpdir or os.path.dirname(os.path.abspath(out_mp4))
    card = make_card(message, os.path.join(tmpdir, "card.png"), intro_line)
    fc = (f"[1:a]aformat=channel_layouts=mono,showwaves=s={W}x{WAVE_H}:mode=cline:rate=30:"
          f"colors=#ffb000|#ff5a00:scale=sqrt,format=rgba[w];"
          f"[0:v][w]overlay=0:{WAVE_Y}:shortest=1,format=yuv420p[v]")
    cmd = ["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", "30", "-i", card, "-i", mp3_path,
           "-filter_complex", fc, "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "25", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", out_mp4]
    subprocess.run(cmd, check=True)
    return out_mp4


if __name__ == "__main__":
    mp3, msg, out = sys.argv[1], sys.argv[2], sys.argv[3]
    print(make_mp4(mp3, msg, out))
