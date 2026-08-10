#!/usr/bin/env python3
"""Build an animated ASCII-wordmark SVG: a name set in big block letters.

The glyphs are rasterised with PIL, then each cell is turned into a character
picked by how much ink covers it — solid core, lighter edge — so the letters
read as drawn rather than as a blocky fill.

Usage:
    python3 tools/build_wordmark.py SIMONE -o assets/wordmark.svg
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import termsvg

CHAR_ASPECT = 0.5   # a monospace cell is about twice as tall as it is wide

FONTS = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

# ink coverage -> glyph: a solid body, a shoulder, a faint edge
LEVELS = ((0.66, "S"), (0.34, "+"), (0.12, "`"))


def pick_font(size: int, explicit: str | None) -> ImageFont.FreeTypeFont:
    for path in ([explicit] if explicit else []) + FONTS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    raise SystemExit("no usable TrueType font found; pass --font")


def text_to_ascii(text: str, rows: int, tracking: float,
                  font_path: str | None) -> list[str]:
    size = 220
    font = pick_font(size, font_path)

    # lay the glyphs out by hand so the letter spacing is ours, not the font's
    gap = round(size * tracking)
    probe = Image.new("L", (1, 1))
    d = ImageDraw.Draw(probe)
    widths = [d.textlength(c, font=font) for c in text]
    total = sum(widths) + gap * (len(text) - 1)
    asc, desc = font.getmetrics()

    img = Image.new("L", (int(total) + size, asc + desc + size), 0)
    d = ImageDraw.Draw(img)
    x = size / 2
    for c, cw in zip(text, widths):
        d.text((x, size / 2), c, font=font, fill=255)
        x += cw + gap

    box = img.getbbox()
    if not box:
        raise SystemExit("nothing to draw")
    img = img.crop(box)

    cols = max(1, round(img.width / img.height * rows / CHAR_ASPECT))
    cell = img.resize((cols, rows), Image.LANCZOS)
    px = cell.load()

    out = []
    for y in range(rows):
        line = []
        for x in range(cols):
            v = px[x, y] / 255.0
            line.append(next((ch for lim, ch in LEVELS if v >= lim), " "))
        out.append("".join(line).rstrip())
    return out


def build_svg(art: list[str], title: str, *, font_size: float, pad: float,
              line_gap: float, fg: str, type_start: float, type_dur: float,
              art_start: float, wipe_dur: float) -> str:
    adv = font_size * termsvg.ADVANCE
    line_h = font_size * line_gap
    cols = max((len(l) for l in art), default=0)

    art_w = cols * adv
    w = max(art_w + pad * 2,
            len(title) * termsvg.TITLE_FS * termsvg.ADVANCE + 160)
    h = termsvg.BAR_H + pad + len(art) * line_h + pad

    art_x = round((w - art_w) / 2, 2)
    art_y0 = termsvg.BAR_H + pad + font_size

    # the wordmark prints left to right behind a widening clip
    defs = (f'<clipPath id="wipe"><rect x="{art_x}" y="0" width="0" height="{h}">'
            f'<animate attributeName="width" from="0" to="{round(art_w, 2)}" '
            f'dur="{wipe_dur}s" begin="{art_start}s" fill="freeze" '
            f'calcMode="spline" keySplines="0.2 0.8 0.2 1" keyTimes="0;1"/>'
            f'</rect></clipPath>')

    rows = "\n".join(
        f'      <text x="{art_x}" y="{round(art_y0 + i * line_h, 2)}" '
        f'xml:space="preserve" textLength="{round(len(raw) * adv, 2)}" '
        f'lengthAdjust="spacing">{termsvg.escape(raw)}</text>'
        for i, raw in enumerate(art) if raw.strip()
    )
    body = (f'    <g class="art" clip-path="url(#wipe)" fill="{fg}" '
            f'font-size="{font_size}px">\n{rows}\n    </g>')

    css = ("      .art { opacity:0; animation: fade .35s ease "
           f"{art_start}s forwards; }}\n"
           "      @keyframes fade { to { opacity:.92; } }")

    return termsvg.terminal(width=w, height=h, title=title, body=body,
                            defs=defs, css=css, type_start=type_start,
                            type_dur=type_dur)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("text")
    p.add_argument("-o", "--out", type=Path, default=Path("assets/wordmark.svg"))
    p.add_argument("--txt", type=Path, help="also dump the raw ASCII art here")
    p.add_argument("--title", default="simone764@github: ~$ ./wordmark.sh --name")
    p.add_argument("--rows", type=int, default=11)
    p.add_argument("--tracking", type=float, default=0.16,
                   help="extra letter spacing, in em")
    p.add_argument("--font", help="path to a TrueType font")
    p.add_argument("--font-size", type=float, default=9.0)
    p.add_argument("--line-gap", type=float, default=1.15)
    p.add_argument("--pad", type=float, default=30.0)
    p.add_argument("--fg", default=termsvg.FG)
    p.add_argument("--type-start", type=float, default=0.6)
    p.add_argument("--type-dur", type=float, default=1.8)
    p.add_argument("--art-start", type=float, default=2.5)
    p.add_argument("--wipe-dur", type=float, default=1.4)
    a = p.parse_args()

    art = text_to_ascii(a.text, a.rows, a.tracking, a.font)
    if a.txt:
        a.txt.parent.mkdir(parents=True, exist_ok=True)
        a.txt.write_text("\n".join(art) + "\n")

    svg = build_svg(art, a.title, font_size=a.font_size, pad=a.pad,
                    line_gap=a.line_gap, fg=a.fg, type_start=a.type_start,
                    type_dur=a.type_dur, art_start=a.art_start,
                    wipe_dur=a.wipe_dur)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(svg)
    print(f"{a.out}  {len(art)} lines x {max(len(l) for l in art)} cols  "
          f"{a.out.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
