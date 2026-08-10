#!/usr/bin/env python3
"""Drop the vendor watermark from a downloaded panel SVG.

The gitskins endpoints stamp a small "gitskins.com" label into the corner of
every section. It sits outside the drawing — removing it leaves the viewBox and
every coordinate untouched, so nothing reflows.

The workflow re-fetches the panels each night, which is why this lives in a
script instead of being a one-off edit: a hand-cleaned file would grow the
label back on the next refresh.

Usage:
    python3 tools/strip_watermark.py assets/gs-*.svg
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# a <text> whose content mentions the vendor, and any <a> wrapping such a label
WATERMARK = re.compile(
    r"<a\b[^>]*\bgitskins[^>]*>.*?</a>"
    r"|<text\b(?:(?!</text>).)*?gitskins(?:(?!</text>).)*?</text>",
    re.S | re.I,
)


def strip(markup: str) -> str:
    """-> the same markup with any vendor watermark element removed."""
    return WATERMARK.sub("", markup)


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__.strip(), file=sys.stderr)
        return 2

    for name in argv:
        path = Path(name)
        src = path.read_text()
        out = strip(src)
        if out == src:
            print(f"{path}: clean")
            continue
        path.write_text(out)
        print(f"{path}: watermark removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
