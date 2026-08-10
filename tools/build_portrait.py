#!/usr/bin/env python3
"""Build an animated ASCII-portrait SVG for a GitHub profile README.

photo -> ASCII art -> self-contained animated SVG (no JS, works inside <img>).

Usage:
    python3 tools/build_portrait.py photo.jpg -o assets/portrait.svg \
        --cols 100 --title "simone764@github: ~$ ./portrait.sh" --avatar photo.jpg
"""

from __future__ import annotations

import argparse
import base64
import mimetypes
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

# density ramp, light -> dense (rendered light-on-dark)
RAMP = " `.,-~:;=+*csoSC%#@"

CHAR_ASPECT = 0.5   # source pixel rows kept per column, monospace cell is ~2:1
ADVANCE = 0.60      # monospace advance width, in em


def background_mask(img: Image.Image, cols: int, rows: int, tol: float,
                    global_tol: float, scale: int = 4) -> list[list[bool]]:
    """Flood fill inward from every border pixel, stopping at strong edges.

    Colour distance, not luminance: a grey laptop and a beige wall can share a
    brightness while being obviously different colours. `tol` is the per-step
    edge threshold (gradual backgrounds keep flowing), `global_tol` caps how far
    any background pixel may drift from the border colour, so the fill cannot
    leak into the subject through a soft edge.
    """
    w, h = cols * scale, rows * scale
    rgb = img.convert("RGB").resize((w, h), Image.LANCZOS).load()
    step_sq = (tol * 255.0) ** 2
    glob_sq = (global_tol * 255.0) ** 2

    # chromaticity (hue-ish, luminance divided out) plus luminance kept apart:
    # a wall shaded by a lamp slides in luminance while its chromaticity holds,
    # whereas skin sits close to beige in RGB but far from it in chromaticity.
    px = [(0.0, 0.0, 0.0, 0.0)] * (w * h)
    for y in range(h):
        for x in range(w):
            r, g, b = rgb[x, y]
            s = r + g + b + 1
            px[y * w + x] = (765.0 * r / s, 765.0 * g / s, 765.0 * b / s,
                             0.299 * r + 0.587 * g + 0.114 * b)

    def chroma_sq(a, b):
        return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2

    def step_sq_of(a, b):
        # luminance still counts at edges, just weakly, so soft borders hold
        return chroma_sq(a, b) + (0.35 * (a[3] - b[3])) ** 2

    edge = ([y * w for y in range(h)] + [y * w + w - 1 for y in range(h)]
            + list(range(w)) + list(range((h - 1) * w, h * w)))

    # every border pixel seeds a region judged against its own colour, so a wall
    # and a desk of different tones both count as background
    bg = bytearray(w * h)
    for seed in edge:
        if bg[seed]:
            continue
        ref = px[seed]
        bg[seed] = 1
        stack = [seed]
        while stack:
            i = stack.pop()
            v = px[i]
            x, y = i % w, i // w
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h:
                    j = ny * w + nx
                    if not bg[j] and step_sq_of(px[j], v) <= step_sq \
                            and chroma_sq(px[j], ref) <= glob_sq:
                        bg[j] = 1
                        stack.append(j)

    # a cell is background when most of its sub-pixels are
    half = scale * scale / 2
    out = []
    for cy in range(rows):
        row = []
        for cx in range(cols):
            n = sum(bg[(cy * scale + sy) * w + cx * scale + sx]
                    for sy in range(scale) for sx in range(scale))
            row.append(n > half)
        out.append(row)
    return out


def image_to_ascii(path: Path, cols: int, contrast: float, gamma: float,
                   cutout: float, invert: bool, strip_bg: float,
                   bg_global: float, despeckle: int) -> list[str]:
    src = Image.open(path)
    rows = max(1, round(src.height / src.width * cols * CHAR_ASPECT))

    bg = (background_mask(src, cols, rows, strip_bg, bg_global)
          if strip_bg > 0 else None)

    gray = src.convert("L")
    img = ImageOps.invert(gray) if invert else gray
    small = img.resize((cols, rows), Image.LANCZOS)
    px = small.load()

    # stretch contrast over the subject only, so the removed wall cannot flatten it
    vals = [px[x, y] for y in range(rows) for x in range(cols)
            if bg is None or not bg[y][x]]
    lo, hi = (min(vals), max(vals)) if vals else (0, 255)
    span = max(1, hi - lo)

    n = len(RAMP) - 1
    out = []
    for y in range(rows):
        line = []
        for x in range(cols):
            if bg is not None and bg[y][x]:
                line.append(" ")
                continue
            v = (px[x, y] - lo) / span
            v = min(1.0, max(0.0, (v - 0.5) * contrast + 0.5)) ** gamma
            line.append(" " if v <= cutout else RAMP[max(0, min(n, round(v * n)))])
        out.append("".join(line).rstrip())

    if despeckle:
        grid = [list(l.ljust(cols)) for l in out]
        filled = [[c != " " for c in row] for row in grid]
        for y in range(rows):
            for x in range(cols):
                if not filled[y][x]:
                    continue
                near = sum(filled[j][i]
                           for j in range(max(0, y - 1), min(rows, y + 2))
                           for i in range(max(0, x - 2), min(cols, x + 3)))
                if near < despeckle:
                    grid[y][x] = " "
        out = ["".join(row).rstrip() for row in grid]

    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()

    # trim the empty gutter on the left so the art sits centred in the window
    indent = min((len(l) - len(l.lstrip()) for l in out if l.strip()), default=0)
    return [l[indent:] for l in out]


def xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def build_svg(art: list[str], title: str, avatar: Path | None, *,
              font_size: float, pad: float, bar_h: float, line_gap: float,
              bg: str, bar: str, fg: str, title_fg: str,
              type_start: float, type_dur: float,
              art_start: float, art_stagger: float, art_dur: float) -> str:
    adv = font_size * ADVANCE
    line_h = font_size * line_gap
    cols = max((len(l) for l in art), default=0)

    art_w = cols * adv
    title_fs = 13.0
    title_adv = title_fs * ADVANCE

    w = round(max(art_w + pad * 2, len(title) * title_adv + 160), 1)
    h = round(bar_h + pad + len(art) * line_h + pad, 1)

    # --- typing animation on the title bar (discrete steps, SMIL) ---
    n = len(title)
    tw = n * title_adv
    tx = round((w - tw) / 2, 2)
    ty = round(bar_h / 2 + title_fs * 0.36, 2)

    steps = [round(i * title_adv, 2) for i in range(n + 1)]
    key_times = ";".join(f"{i / n:.4f}" for i in range(n + 1))
    values = ";".join(str(s) for s in steps)
    cursor_x = ";".join(str(round(tx + s, 2)) for s in steps)
    type_end = type_start + type_dur

    art_y0 = bar_h + pad + font_size
    art_x = round((w - art_w) / 2, 2)

    lines = []
    for i, raw in enumerate(art):
        if not raw.strip():
            continue
        y = round(art_y0 + i * line_h, 2)
        delay = round(art_start + i * art_stagger, 3)
        lines.append(
            f'<text class="l" x="{art_x}" y="{y}" xml:space="preserve" '
            f'style="animation-delay:{delay}s">'
            f"{xml_escape(raw)}</text>"
        )
    art_block = "\n    ".join(lines)

    avatar_block = ""
    if avatar:
        a = bar_h * 0.72
        u = data_uri(avatar)
        ax = round(w - a - 12, 2)
        ay = round((bar_h - a) / 2, 2)
        avatar_block = (
            f'<clipPath id="av"><circle cx="{round(ax + a / 2, 2)}" '
            f'cy="{round(ay + a / 2, 2)}" r="{round(a / 2, 2)}"/></clipPath>'
        ), (
            f'<image href="{u}" xlink:href="{u}" x="{ax}" y="{ay}" width="{a}" '
            f'height="{a}" preserveAspectRatio="xMidYMid slice" clip-path="url(#av)"/>'
        )

    av_def, av_use = avatar_block if avatar_block else ("", "")

    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="ui-monospace,SFMono-Regular,SF Mono,Menlo,Consolas,DejaVu Sans Mono,monospace">
  <defs>
    <clipPath id="type"><rect x="{tx}" y="0" width="0" height="{bar_h}">
      <animate attributeName="width" values="{values}" keyTimes="{key_times}" calcMode="discrete" dur="{type_dur}s" begin="{type_start}s" fill="freeze"/>
    </rect></clipPath>
    {av_def}
    <style>
      .win {{ opacity:0; animation: win .7s cubic-bezier(.2,.8,.2,1) .05s forwards; }}
      @keyframes win {{ from {{ opacity:0; transform: translateY(10px) scale(.985); }}
                        to   {{ opacity:1; transform: none; }} }}
      .l {{ fill:{fg}; font-size:{font_size}px; white-space:pre; opacity:0;
            animation: rev {art_dur}s cubic-bezier(.2,.8,.2,1) forwards; }}
      @keyframes rev {{ from {{ opacity:0; transform: translateY(3px); }}
                        to   {{ opacity:.92; transform: none; }} }}
      .cur {{ opacity:0; animation: curin .01s {type_start}s forwards, blink 1s steps(1) {type_end}s infinite; }}
      @keyframes curin {{ to {{ opacity:1; }} }}
      @keyframes blink {{ 0%,50% {{ opacity:1; }} 50.01%,100% {{ opacity:0; }} }}
      @media (prefers-reduced-motion: reduce) {{
        .win,.l,.cur {{ animation: none !important; opacity:1; }}
      }}
    </style>
  </defs>

  <g class="win">
    <rect x="0" y="0" width="{w}" height="{h}" rx="10" fill="{bg}"/>
    <path d="M0 10a10 10 0 0 1 10-10h{w - 20}a10 10 0 0 1 10 10v{bar_h - 10}H0z" fill="{bar}"/>
    <line x1="0" y1="{bar_h}" x2="{w}" y2="{bar_h}" stroke="#000" stroke-opacity=".35"/>
    <circle cx="20" cy="{bar_h / 2}" r="6" fill="#ff5f57"/>
    <circle cx="40" cy="{bar_h / 2}" r="6" fill="#febc2e"/>
    <circle cx="60" cy="{bar_h / 2}" r="6" fill="#28c840"/>
    {av_use}
    <g clip-path="url(#type)">
      <text x="{tx}" y="{ty}" fill="{title_fg}" font-size="{title_fs}px" xml:space="preserve">{xml_escape(title)}</text>
    </g>
    <rect class="cur" x="{tx}" y="{round(bar_h / 2 - title_fs * 0.42, 2)}" width="{round(title_adv, 2)}" height="{round(title_fs, 2)}" fill="{title_fg}" fill-opacity=".8">
      <animate attributeName="x" values="{cursor_x}" keyTimes="{key_times}" calcMode="discrete" dur="{type_dur}s" begin="{type_start}s" fill="freeze"/>
    </rect>

    {art_block}
  </g>
</svg>
'''


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("photo", type=Path)
    p.add_argument("-o", "--out", type=Path, default=Path("assets/portrait.svg"))
    p.add_argument("--txt", type=Path, help="also dump the raw ASCII art here")
    p.add_argument("--avatar", type=Path, help="small image for the title bar")
    p.add_argument("--title", default="simone764@github: ~$ ./portrait.sh")
    p.add_argument("--cols", type=int, default=100)
    p.add_argument("--font-size", type=float, default=7.0)
    p.add_argument("--line-gap", type=float, default=1.1)
    p.add_argument("--pad", type=float, default=24.0)
    p.add_argument("--bar-h", type=float, default=34.0)
    p.add_argument("--contrast", type=float, default=1.15)
    p.add_argument("--gamma", type=float, default=1.0, help=">1 darker, <1 brighter")
    p.add_argument("--cutout", type=float, default=0.08,
                   help="luminance below this becomes blank (0..1)")
    p.add_argument("--invert", action="store_true", help="dark art on light photo")
    p.add_argument("--strip-bg", type=float, default=0.0, metavar="TOL",
                   help="flood-fill the background away from the borders, "
                        "e.g. 0.02; 0 disables")
    p.add_argument("--bg-global", type=float, default=0.14, metavar="TOL",
                   help="max colour drift from the border colour for a pixel "
                        "to count as background")
    p.add_argument("--despeckle", type=int, default=0, metavar="N",
                   help="blank any glyph with fewer than N neighbours in its "
                        "5x3 window; clears leftover background specks")
    p.add_argument("--bg", default="#171a21")
    p.add_argument("--bar", default="#242832")
    p.add_argument("--fg", default="#d7dae3")
    p.add_argument("--title-fg", default="#c3c8d4")
    p.add_argument("--type-start", type=float, default=0.6)
    p.add_argument("--type-dur", type=float, default=1.6)
    p.add_argument("--art-start", type=float, default=2.3)
    p.add_argument("--art-stagger", type=float, default=0.022)
    p.add_argument("--art-dur", type=float, default=0.5)
    a = p.parse_args()

    art = image_to_ascii(a.photo, a.cols, a.contrast, a.gamma, a.cutout,
                         a.invert, a.strip_bg, a.bg_global, a.despeckle)

    if a.txt:
        a.txt.parent.mkdir(parents=True, exist_ok=True)
        a.txt.write_text("\n".join(art) + "\n")

    svg = build_svg(
        art, a.title, a.avatar,
        font_size=a.font_size, pad=a.pad, bar_h=a.bar_h, line_gap=a.line_gap,
        bg=a.bg, bar=a.bar, fg=a.fg, title_fg=a.title_fg,
        type_start=a.type_start, type_dur=a.type_dur,
        art_start=a.art_start, art_stagger=a.art_stagger, art_dur=a.art_dur,
    )
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(svg)
    print(f"{a.out}  {len(art)} lines x {a.cols} cols  {a.out.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
