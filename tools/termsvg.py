"""Shared terminal-window chrome for the profile README panels.

Every panel is a self-contained SVG: a macOS-ish window whose title bar types
itself out, then the body animates in. No JS, because GitHub renders these
through an <img> tag where scripts never run.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

FONT_STACK = ("ui-monospace,SFMono-Regular,SF Mono,Menlo,Consolas,"
              "DejaVu Sans Mono,monospace")
ADVANCE = 0.60      # monospace advance width, in em
BAR_H = 34.0
TITLE_FS = 13.0

BG = "#171a21"
BAR = "#242832"
FG = "#d7dae3"
TITLE_FG = "#c3c8d4"


def escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def terminal(*, width: float, height: float, title: str, body: str,
             defs: str = "", css: str = "", avatar: Path | None = None,
             bar_h: float = BAR_H, bg: str = BG, bar: str = BAR,
             title_fg: str = TITLE_FG, type_start: float = 0.6,
             type_dur: float = 1.6, title_fs: float = TITLE_FS) -> str:
    """Wrap `body` (drawn in window coordinates) in an animated window."""
    w, h = round(width, 1), round(height, 1)

    n = max(1, len(title))
    adv = title_fs * ADVANCE
    tx = round((w - n * adv) / 2, 2)
    ty = round(bar_h / 2 + title_fs * 0.36, 2)

    # discrete SMIL steps drive the typing: one keyframe per character
    key_times = ";".join(f"{i / n:.4f}" for i in range(n + 1))
    widths = ";".join(str(round(i * adv, 2)) for i in range(n + 1))
    cursor_x = ";".join(str(round(tx + i * adv, 2)) for i in range(n + 1))
    type_end = type_start + type_dur

    av_def = av_use = ""
    if avatar:
        a = bar_h * 0.72
        ax, ay = round(w - a - 12, 2), round((bar_h - a) / 2, 2)
        uri = data_uri(avatar)
        av_def = (f'<clipPath id="av"><circle cx="{round(ax + a / 2, 2)}" '
                  f'cy="{round(ay + a / 2, 2)}" r="{round(a / 2, 2)}"/></clipPath>')
        av_use = (f'<image href="{uri}" xlink:href="{uri}" x="{ax}" y="{ay}" '
                  f'width="{a}" height="{a}" preserveAspectRatio="xMidYMid slice" '
                  f'clip-path="url(#av)"/>')

    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="{FONT_STACK}">
  <defs>
    <clipPath id="type"><rect x="{tx}" y="0" width="0" height="{bar_h}">
      <animate attributeName="width" values="{widths}" keyTimes="{key_times}" calcMode="discrete" dur="{type_dur}s" begin="{type_start}s" fill="freeze"/>
    </rect></clipPath>
    {av_def}
    {defs}
    <style>
      text {{ font-variant-ligatures:none; }}
      .win {{ opacity:0; animation: win .7s cubic-bezier(.2,.8,.2,1) .05s forwards; }}
      @keyframes win {{ from {{ opacity:0; transform: translateY(10px) scale(.985); }}
                        to   {{ opacity:1; transform: none; }} }}
      .cur {{ opacity:0; animation: curin .01s {type_start}s forwards,
                                    blink 1s steps(1) {type_end}s infinite; }}
      @keyframes curin {{ to {{ opacity:1; }} }}
      @keyframes blink {{ 0%,50% {{ opacity:1; }} 50.01%,100% {{ opacity:0; }} }}
{css}
      @media (prefers-reduced-motion: reduce) {{
        .win,.cur,.l,.cell,.fade {{ animation: none !important; opacity:1; }}
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
      <text x="{tx}" y="{ty}" fill="{title_fg}" font-size="{title_fs}px" xml:space="preserve">{escape(title)}</text>
    </g>
    <rect class="cur" x="{tx}" y="{round(bar_h / 2 - title_fs * 0.42, 2)}" width="{round(adv, 2)}" height="{round(title_fs, 2)}" fill="{title_fg}" fill-opacity=".8">
      <animate attributeName="x" values="{cursor_x}" keyTimes="{key_times}" calcMode="discrete" dur="{type_dur}s" begin="{type_start}s" fill="freeze"/>
    </rect>

{body}
  </g>
</svg>
'''
