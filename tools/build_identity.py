#!/usr/bin/env python3
"""Compose the profile panels into one "Terminal Identity" window.

Takes finished panel SVGs and nests them inside a single outer window: two
cards on the first row, one spanning the second. Nesting is what makes this a
single <img> the README can show — GitHub gives us no way to draw a frame
around three separate images.

Every id inside a nested panel gets a prefix first. Once the three documents
share one document, two ids called "bg" would collide and the second panel
would silently render with the first one's gradient.

Usage:
    python3 tools/build_identity.py -o assets/identity.svg \
        --portrait assets/gs-portrait.svg \
        --wordmark assets/gs-wordmark.svg \
        --heatmap  assets/gs-heatmap.svg
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from strip_watermark import strip as strip_watermark

SANS = ("-apple-system,BlinkMacSystemFont,Segoe UI,Inter,Helvetica Neue,"
        "Arial,sans-serif")

BG = "#08090b"          # window ground
BAR = "#101114"         # title bar
EDGE = "#1e2126"        # hairlines
CARD = "#0f1116"        # mat behind each panel
TITLE_FG = "#e9ecf1"

ROOT = re.compile(r"<svg\b[^>]*>", re.S)
ATTR = re.compile(r'(\w[\w:-]*)\s*=\s*"([^"]*)"')


# attributes that belong to the panel's own viewport, not to its contents
VIEWPORT_ATTRS = {"x", "y", "width", "height", "viewBox", "version", "xmlns",
                  "xmlns:xlink", "id", "role", "aria-label",
                  "preserveAspectRatio", "overflow"}


def read_panel(path: Path, prefix: str) -> tuple[str, str, float, float]:
    """-> (inner markup with namespaced ids, inherited attrs, width, height)."""
    src = path.read_text()
    src = re.sub(r"<\?xml.*?\?>", "", src, flags=re.S)
    src = re.sub(r"<!--.*?-->", "", src, flags=re.S)
    # a freshly downloaded panel still carries the vendor watermark; strip it
    # here too so the composed window is clean even if the panels are not
    src = strip_watermark(src)

    open_tag = ROOT.search(src)
    if not open_tag:
        raise SystemExit(f"{path}: no <svg> root")
    attrs = dict(ATTR.findall(open_tag.group()))

    if "viewBox" in attrs:
        _, _, vw, vh = (float(v) for v in attrs["viewBox"].replace(",", " ").split())
    else:
        vw, vh = float(attrs["width"]), float(attrs["height"])

    inner = src[open_tag.end():src.rindex("</svg>")]

    for ident in sorted(set(re.findall(r'\bid="([^"]+)"', inner)), key=len,
                        reverse=True):
        new = f"{prefix}-{ident}"
        inner = inner.replace(f'id="{ident}"', f'id="{new}"')
        inner = inner.replace(f"url(#{ident})", f"url(#{new})")
        inner = inner.replace(f'href="#{ident}"', f'href="#{new}"')
        # SMIL syncbases: begin="other.end+1s"
        inner = re.sub(rf'\b(begin|end)="{re.escape(ident)}\.',
                       rf'\1="{new}.', inner)

    # font-family and friends live on the root and are inherited by the
    # contents; dropping them would reset the panel's text to the default serif
    inherited = " ".join(f'{k}="{v}"' for k, v in attrs.items()
                         if k not in VIEWPORT_ATTRS)
    return inner, inherited, vw, vh


def place(panel: tuple[str, str, float, float], x: float, y: float,
          w: float) -> tuple[str, float]:
    """Scale a panel to width `w` at (x, y); returns markup and its height."""
    inner, inherited, vw, vh = panel
    h = round(w * vh / vw, 2)
    tag = (f'<svg x="{round(x, 2)}" y="{round(y, 2)}" width="{round(w, 2)}" '
           f'height="{h}" viewBox="0 0 {vw} {vh}" overflow="visible" '
           f'{inherited}>')
    return f"{tag}{inner}</svg>", h


def build(portrait: Path, wordmark: Path, heatmap: Path, *, title: str,
          width: float, bar_h: float, pad: float, gap: float,
          card_pad: float, left_share: float, heat_share: float) -> str:
    pt = read_panel(portrait, "pt")
    wm = read_panel(wordmark, "wm")
    hm = read_panel(heatmap, "hm")

    inner_w = width - pad * 2
    left_w = round((inner_w - gap) * left_share, 2)
    right_w = round(inner_w - gap - left_w, 2)

    row1_y = bar_h + pad
    # the taller of the two panels sets the row height; the other one centres
    _, pt_ph = place(pt, 0, 0, left_w - card_pad * 2)
    _, wm_ph = place(wm, 0, 0, right_w - card_pad * 2)
    row1_h = round(max(pt_ph, wm_ph) + card_pad * 2, 2)

    pt_svg, _ = place(pt, pad + card_pad, row1_y + (row1_h - pt_ph) / 2,
                      left_w - card_pad * 2)
    wm_svg, _ = place(wm, pad + left_w + gap + card_pad,
                      row1_y + (row1_h - wm_ph) / 2, right_w - card_pad * 2)

    row2_y = round(row1_y + row1_h + gap, 2)
    heat_w = round(inner_w * heat_share, 2)
    hm_svg, hm_ph = place(hm, pad + (inner_w - heat_w) / 2,
                          row2_y + card_pad, heat_w)
    row2_h = round(hm_ph + card_pad * 2, 2)

    height = round(row2_y + row2_h + pad, 2)
    title_fs = 21.0

    def card(x: float, y: float, w: float, h: float, delay: float) -> str:
        return (f'<rect class="card" x="{round(x, 2)}" y="{round(y, 2)}" '
                f'width="{round(w, 2)}" height="{round(h, 2)}" rx="9" '
                f'fill="{CARD}" stroke="{EDGE}" stroke-opacity=".7" '
                f'style="animation-delay:{delay}s"/>')

    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{title}">
  <defs>
    <style>
      .shell {{ opacity:0; animation: shell-in .6s cubic-bezier(.2,.8,.2,1) forwards; }}
      .card  {{ opacity:0; animation: card-in .5s cubic-bezier(.2,.8,.2,1) forwards; }}
      .panel {{ opacity:0; animation: card-in .5s cubic-bezier(.2,.8,.2,1) forwards; }}
      @keyframes shell-in {{ from {{ opacity:0; transform: translateY(8px) scale(.99); }}
                             to   {{ opacity:1; transform: none; }} }}
      @keyframes card-in  {{ from {{ opacity:0; transform: translateY(6px); }}
                             to   {{ opacity:1; transform: none; }} }}
      @media (prefers-reduced-motion: reduce) {{
        .shell,.card,.panel {{ animation: none !important; opacity:1; }}
      }}
    </style>
  </defs>

  <g class="shell">
    <rect x="0" y="0" width="{width}" height="{height}" rx="16" fill="{BG}"/>
    <path d="M0 16a16 16 0 0 1 16-16h{width - 32}a16 16 0 0 1 16 16v{bar_h - 16}H0z" fill="{BAR}"/>
    <line x1="0" y1="{bar_h}" x2="{width}" y2="{bar_h}" stroke="{EDGE}"/>
    <circle cx="34" cy="{bar_h / 2}" r="9" fill="#ff5f57"/>
    <circle cx="63" cy="{bar_h / 2}" r="9" fill="#febc2e"/>
    <circle cx="92" cy="{bar_h / 2}" r="9" fill="#28c840"/>
    <text x="128" y="{round(bar_h / 2 + title_fs * 0.35, 2)}" fill="{TITLE_FG}" font-family="{SANS}" font-size="{title_fs}px" font-weight="600">{title}</text>

    {card(pad, row1_y, left_w, row1_h, 0.18)}
    {card(pad + left_w + gap, row1_y, right_w, row1_h, 0.26)}
    {card(pad, row2_y, inner_w, row2_h, 0.34)}

    <g class="panel" style="animation-delay:.3s">{pt_svg}</g>
    <g class="panel" style="animation-delay:.38s">{wm_svg}</g>
    <g class="panel" style="animation-delay:.46s">{hm_svg}</g>
  </g>
</svg>
'''


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("-o", "--out", type=Path, default=Path("assets/identity.svg"))
    p.add_argument("--portrait", type=Path, default=Path("assets/gs-portrait.svg"))
    p.add_argument("--wordmark", type=Path, default=Path("assets/gs-wordmark.svg"))
    p.add_argument("--heatmap", type=Path, default=Path("assets/gs-heatmap.svg"))
    p.add_argument("--title", default="Terminal Identity")
    p.add_argument("--width", type=float, default=1160.0)
    p.add_argument("--bar-h", type=float, default=88.0)
    p.add_argument("--pad", type=float, default=22.0)
    p.add_argument("--gap", type=float, default=14.0)
    p.add_argument("--card-pad", type=float, default=14.0)
    p.add_argument("--left-share", type=float, default=0.41,
                   help="fraction of the first row taken by the portrait card")
    p.add_argument("--heat-share", type=float, default=0.62,
                   help="fraction of the width taken by the heatmap panel")
    a = p.parse_args()

    svg = build(a.portrait, a.wordmark, a.heatmap, title=a.title,
                width=a.width, bar_h=a.bar_h, pad=a.pad, gap=a.gap,
                card_pad=a.card_pad, left_share=a.left_share,
                heat_share=a.heat_share)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(svg)
    print(f"{a.out}  {a.out.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
