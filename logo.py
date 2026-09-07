"""TRUCK-A-FY wordmark as 8-bit pixel art (NES title-screen style): hand-drawn 8x11 glyphs, banded shading,
black outline, 45-degree extrusion. One pixel map feeds both the share card (PNG, nearest-neighbour) and the
web page (SVG rects, crisp at any size).

    python3 logo.py out.png [style]      # style: fire (default) | chrome | ice
"""
import sys

GLYPHS = {
    "T": ["########",
          "########",
          "...##...",
          "...##...",
          "...##...",
          "...##...",
          "...##...",
          "...##...",
          "...##...",
          "...##...",
          "...##..."],
    "R": ["######..",
          "#######.",
          "##....##",
          "##....##",
          "#######.",
          "######..",
          "##.##...",
          "##..##..",
          "##...##.",
          "##....##",
          "##....##"],
    "U": ["##....##",
          "##....##",
          "##....##",
          "##....##",
          "##....##",
          "##....##",
          "##....##",
          "##....##",
          "##....##",
          ".######.",
          "..####.."],
    "C": ["..####..",
          ".######.",
          "##....##",
          "##......",
          "##......",
          "##......",
          "##......",
          "##......",
          "##....##",
          ".######.",
          "..####.."],
    "K": ["##....##",
          "##...##.",
          "##..##..",
          "##.##...",
          "####....",
          "####....",
          "##.##...",
          "##..##..",
          "##...##.",
          "##....##",
          "##....##"],
    "A": ["..####..",
          ".######.",
          "##....##",
          "##....##",
          "##....##",
          "########",
          "########",
          "##....##",
          "##....##",
          "##....##",
          "##....##"],
    "F": ["########",
          "########",
          "##......",
          "##......",
          "######..",
          "######..",
          "##......",
          "##......",
          "##......",
          "##......",
          "##......"],
    "Y": ["##....##",
          "##....##",
          "##....##",
          ".##..##.",
          "..####..",
          "...##...",
          "...##...",
          "...##...",
          "...##...",
          "...##...",
          "...##..."],
    "-": ["....",
          "....",
          "....",
          "....",
          "....",
          "####",
          "####",
          "....",
          "....",
          "....",
          "...."],
}
ROWS = 11

# shading bands by row: (row_from, row_to_inclusive) -> colour
STYLES = {
    # sun-on-chrome fire: near-white shine, yellow, orange, red
    "fire": dict(bands=[(0, 1, "#fff6b0"), (2, 4, "#ffcf1e"), (5, 7, "#ff7a00"), (8, 10, "#d61f00")],
                 extrude="#5a1200", outline="#0a0400", depth=3),
    # 80s box-art chrome: white, sky, blue, navy with a warm horizon line
    "chrome": dict(bands=[(0, 1, "#ffffff"), (2, 4, "#a8e0ff"), (5, 5, "#ffd23f"), (6, 7, "#2a7cff"), (8, 10, "#0b2e8a")],
                   extrude="#06153f", outline="#000000", depth=3),
    # ice: white to cyan to purple
    "ice": dict(bands=[(0, 1, "#ffffff"), (2, 4, "#b8fff4"), (5, 7, "#20c8f0"), (8, 10, "#6a2cff")],
                extrude="#24104a", outline="#000000", depth=3),
}


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def band_colour(row, bands):
    for a, b, col in bands:
        if a <= row <= b:
            return col
    return bands[-1][2]


def pixel_map(text="TRUCK-A-FY", style="fire", gap=2):
    """Returns (pixels, width, height): pixels is {(x, y): '#rrggbb'} in glyph units, including the extrusion
    and the 1-px outline. Origin is the top-left of the outline."""
    st = STYLES[style]
    depth = st["depth"]
    face, owner = {}, {}
    x = 1  # leave room for the outline
    for n, ch in enumerate(text):
        g = GLYPHS[ch]
        for gy, row in enumerate(g):
            for gx, c in enumerate(row):
                if c == "#":
                    face[(x + gx, 1 + gy)] = band_colour(gy, st["bands"])
                    owner[(x + gx, 1 + gy)] = n
        x += len(g[0]) + gap
    extr, extr_owner = {}, {}
    for (px, py), n in owner.items():
        for i in range(1, depth + 1):
            p = (px + i, py + i)
            if p not in face:
                extr[p] = st["extrude"]
                extr_owner[p] = n
    body = dict(extr)
    body.update(face)
    pixels = {}
    for (px, py) in body:  # outer outline around letters + extrusion
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                p = (px + dx, py + dy)
                if p not in body:
                    pixels[p] = st["outline"]
    pixels.update(extr)
    for (px, py), n in owner.items():  # a letter keeps a black edge where it sits on a neighbour's extrusion
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                p = (px + dx, py + dy)
                if p in extr and extr_owner[p] != n and p not in face:
                    pixels[p] = st["outline"]
    pixels.update(face)
    w = max(p[0] for p in pixels) + 1
    h = max(p[1] for p in pixels) + 1
    return pixels, w, h


def render(scale=12, style="fire", text="TRUCK-A-FY"):
    """RGBA image of the wordmark, nearest-neighbour scaled so every pixel stays a hard square."""
    from PIL import Image  # lazy: svg() must work without Pillow (Cloud Shell)
    pixels, w, h = pixel_map(text, style)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for (x, y), col in pixels.items():
        px[x, y] = _hex(col) + (255,)
    return img.resize((w * scale, h * scale), Image.NEAREST)


def svg(style="fire", text="TRUCK-A-FY"):
    """Inline-able SVG: one path per colour made of horizontal runs, crisp edges, scales with CSS width."""
    pixels, w, h = pixel_map(text, style)
    runs = {}
    for y in range(h):
        x = 0
        while x < w:
            col = pixels.get((x, y))
            if col is None:
                x += 1
                continue
            x0 = x
            while x < w and pixels.get((x, y)) == col:
                x += 1
            runs.setdefault(col, []).append(f"M{x0} {y}h{x - x0}v1h-{x - x0}z")
    paths = "".join(f'<path fill="{col}" d="{"".join(d)}"/>' for col, d in runs.items())
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" shape-rendering="crispEdges" '
            f'role="img" aria-label="{text}">{paths}</svg>')


if __name__ == "__main__":
    from PIL import Image
    out = sys.argv[1] if len(sys.argv) > 1 else "logo.png"
    style = sys.argv[2] if len(sys.argv) > 2 else "fire"
    im = render(12, style)
    bg = Image.new("RGBA", im.size, (12, 10, 14, 255))
    bg.alpha_composite(im)
    bg.save(out)
    print(out, im.size)
