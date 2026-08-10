#!/usr/bin/env python3
"""Build an animated contribution-graph SVG for the profile README.

Paints the calendar as a terminal running ./contributions.sh: the prompt types
itself, then the squares light up in a left-to-right wave.

Two ways in. With a token (--token, or GH_TOKEN / GITHUB_TOKEN in the
environment) it asks the GraphQL API, which counts contributions to private
repositories — those are most of them for most people. Without one it scrapes
the public profile page, which shows an anonymous visitor's view: public
contributions only, unless "Include private contributions on my profile" is
switched on in GitHub's profile settings.

Usage:
    python3 tools/build_contributions.py Simone764 -o assets/contributions.svg
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import ssl
import urllib.error
import urllib.request
from pathlib import Path

import termsvg

SOURCE = "https://github.com/users/{user}/contributions"
GRAPHQL = "https://api.github.com/graphql"

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date weekday contributionCount contributionLevel }
        }
      }
    }
  }
}
"""

LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
          "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}

CELL = re.compile(
    r'<td[^>]*?data-date="(?P<date>\d{4}-\d\d-\d\d)"[^>]*?'
    r'id="(?P<id>contribution-day-component-(?P<row>\d+)-(?P<col>\d+))"'
    r'[^>]*?data-level="(?P<level>\d)"', re.S)
TIP = re.compile(
    r'<tool-tip[^>]*?for="(?P<id>[^"]+)"[^>]*?>(?P<text>[^<]*)</tool-tip>', re.S)
COUNT = re.compile(r"^(\d+) contribution")

# GitHub's own dark-theme ramp, level 0 dimmed to sit on the terminal ground
GREEN = ("#2a2f3a", "#0e4429", "#006d32", "#26a641", "#39d353")
BLUE = ("#2a2f3a", "#0a3069", "#1158c7", "#388bfd", "#58a6ff")
PALETTES = {"green": GREEN, "blue": BLUE}


def ssl_context() -> ssl.SSLContext:
    # python.org builds ship without the system trust store; certifi fills in
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def fetch(user: str) -> str:
    req = urllib.request.Request(
        SOURCE.format(user=user),
        headers={"User-Agent": "profile-readme-builder",
                 "X-Requested-With": "XMLHttpRequest"})
    with urllib.request.urlopen(req, timeout=30, context=ssl_context()) as r:
        return r.read().decode("utf-8", "replace")


def fetch_api(user: str, token: str) -> tuple[list[tuple[int, int, str, int, int]], int]:
    """Same shape as parse(), but counting private contributions too."""
    payload = json.dumps({"query": QUERY, "variables": {"login": user}}).encode()
    req = urllib.request.Request(GRAPHQL, data=payload, headers={
        "Authorization": f"bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "profile-readme-builder"})
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_context()) as r:
            doc = json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"GraphQL request failed: {e.code} {e.reason}") from e

    if doc.get("errors"):
        raise SystemExit(f"GraphQL: {doc['errors'][0].get('message')}")
    user_node = doc["data"]["user"]
    if user_node is None:
        raise SystemExit(f"no such user: {user}")

    cal = user_node["contributionsCollection"]["contributionCalendar"]
    days = [(day["weekday"], col, day["date"], LEVELS[day["contributionLevel"]],
             day["contributionCount"])
            for col, week in enumerate(cal["weeks"])
            for day in week["contributionDays"]]
    return days, cal["totalContributions"]


def parse(page: str) -> tuple[list[tuple[int, int, str, int, int]], int]:
    """-> [(row, col, date, level, count)] plus the yearly total.

    The calendar ships as one <tr> per weekday, and each cell carries its grid
    position in its id (`contribution-day-component-<weekday>-<week>`), so the
    layout survives the short first and last weeks of the year.
    """
    counts = {}
    for m in TIP.finditer(page):
        hit = COUNT.match(html.unescape(m["text"]).strip())
        counts[m["id"]] = int(hit[1]) if hit else 0

    days = [(int(m["row"]), int(m["col"]), m["date"], int(m["level"]),
             counts.get(m["id"], 0)) for m in CELL.finditer(page)]
    if not days:
        raise SystemExit("no contribution cells found; the page markup changed")
    return days, sum(d[4] for d in days)


def build_svg(days: list[tuple[int, int, str, int, int]], total: int, user: str,
              *, title: str, palette: tuple[str, ...], size: float, gap: float,
              pad: float, type_start: float, type_dur: float,
              grid_start: float, col_stagger: float, cell_dur: float) -> str:
    weeks = max(d[1] for d in days) + 1
    step = size + gap

    prompt_fs, foot_fs = 12.0, 11.0
    grid_y = termsvg.BAR_H + pad + prompt_fs + 22
    grid_w = weeks * step - gap
    grid_h = 7 * step - gap

    w = max(grid_w + pad * 2,
            len(title) * termsvg.TITLE_FS * termsvg.ADVANCE + 160)
    h = grid_y + grid_h + 26 + foot_fs + pad
    x0 = round((w - grid_w) / 2, 2)

    cells = []
    for row, col, date, level, count in days:
        x = round(x0 + col * step, 2)
        y = round(grid_y + row * step, 2)
        delay = round(grid_start + col * col_stagger, 3)
        label = f"{count} on {date}" if count else date
        cells.append(
            f'<rect class="cell" x="{x}" y="{y}" width="{size}" height="{size}" '
            f'rx="2" fill="{palette[level]}" style="animation-delay:{delay}s">'
            f'<title>{termsvg.escape(label)}</title></rect>')

    prompt = f"{user.lower()}@github:~$ ./contributions.sh"
    foot = f"{total} contribution{'' if total == 1 else 's'} in the last year"
    body = f'''    <text class="fade" x="{x0}" y="{round(termsvg.BAR_H + pad + prompt_fs, 2)}" fill="{palette[3]}" font-size="{prompt_fs}px" font-weight="700" xml:space="preserve" style="animation-delay:{type_start + type_dur * .6}s">{termsvg.escape(prompt)}</text>
    <g>
      {"".join(cells)}
    </g>
    <text class="fade" x="{x0}" y="{round(grid_y + grid_h + 26, 2)}" fill="#8b93a5" font-size="{foot_fs}px" style="animation-delay:{round(grid_start + weeks * col_stagger + cell_dur, 3)}s">{termsvg.escape(foot)}</text>'''

    css = f"""      .cell {{ opacity:0; animation: pop {cell_dur}s cubic-bezier(.2,.8,.2,1) forwards; }}
      @keyframes pop {{ from {{ opacity:0; transform: translateY(2px) scale(.7); }}
                        to   {{ opacity:1; transform: none; }} }}
      .fade {{ opacity:0; animation: fade .5s ease forwards; }}
      @keyframes fade {{ to {{ opacity:1; }} }}"""

    return termsvg.terminal(width=w, height=h, title=title, body=body, css=css,
                            type_start=type_start, type_dur=type_dur)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("user")
    p.add_argument("-o", "--out", type=Path,
                   default=Path("assets/contributions.svg"))
    p.add_argument("--title")
    p.add_argument("--token",
                   help="GitHub token; also read from GH_TOKEN / GITHUB_TOKEN. "
                        "Needed to count private contributions")
    p.add_argument("--html", type=Path,
                   help="read a saved contributions page instead of fetching")
    p.add_argument("--palette", choices=sorted(PALETTES), default="green")
    p.add_argument("--size", type=float, default=11.0, help="cell size in px")
    p.add_argument("--gap", type=float, default=3.0)
    p.add_argument("--pad", type=float, default=26.0)
    p.add_argument("--type-start", type=float, default=0.6)
    p.add_argument("--type-dur", type=float, default=1.9)
    p.add_argument("--grid-start", type=float, default=2.6)
    p.add_argument("--col-stagger", type=float, default=0.022)
    p.add_argument("--cell-dur", type=float, default=0.45)
    a = p.parse_args()

    token = a.token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if a.html:
        days, total = parse(a.html.read_text())
    elif token:
        days, total = fetch_api(a.user, token)
    else:
        days, total = parse(fetch(a.user))
    title = a.title or f"{a.user.lower()}@github: ~$ ./contributions.sh"

    svg = build_svg(days, total, a.user, title=title,
                    palette=PALETTES[a.palette], size=a.size, gap=a.gap,
                    pad=a.pad, type_start=a.type_start, type_dur=a.type_dur,
                    grid_start=a.grid_start, col_stagger=a.col_stagger,
                    cell_dur=a.cell_dur)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(svg)
    source = "saved page" if a.html else ("GraphQL API" if token else "public page")
    print(f"{a.out}  {len(days)} days, {total} contributions via {source}  "
          f"{a.out.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
