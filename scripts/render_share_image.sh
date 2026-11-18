#!/usr/bin/env bash
# Render the site's one share image: the picture a link preview shows
# (Open Graph, 1200 by 630).
#
# It carries the sign-board mark and the site's name, and nothing else: no
# level, no lake, no status, no tagline. The mark is templates/mark.svg,
# unchanged. The name is set the way the site's own header sets it
# (style.css, .site-name a): the signage face, bold, capitals, tracked
# 0.06em, in the brand indigo on the page's paper.
#
# This is a developer tool, not part of the build: the output is committed
# and the build copies it (site.py, extras). Run it again, and commit the
# file, only when the mark or the name changes.
#
# Needs rsvg-convert (brew install librsvg) and the signage face's first
# choice, DIN Alternate Bold, which macOS ships. Without that font the
# script stops, so the name is never set in a fallback face by accident.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
templates="$root/pipeline/src/caalgae/templates"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

command -v rsvg-convert >/dev/null || {
  echo "rsvg-convert not found (brew install librsvg)" >&2
  exit 1
}
fc-match --format '%{family}' 'DIN Alternate:bold' | grep -q 'DIN Alternate' || {
  echo "DIN Alternate Bold is not installed; the name would be set in another face" >&2
  exit 1
}

python3 - "$templates/mark.svg" "$root/pipeline/src/caalgae/site.py" "$work/share.svg" <<'PY'
import re
import sys
from html import escape
from pathlib import Path

mark = Path(sys.argv[1]).read_text(encoding="utf-8")
inner = re.search(r"<svg[^>]*>(.*)</svg>", mark, re.S).group(1)
inner = re.sub(r"<title>.*?</title>", "", inner)
name = re.search(r'^SITE_NAME = "([^"]+)"$', Path(sys.argv[2]).read_text(encoding="utf-8"), re.M).group(1)

PAPER, BRAND = "#fbfaf6", "#262a6b"
SIZE = 112  # px; tracking is 0.06em, as in the header
Path(sys.argv[3]).write_text(
    f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
<rect width="1200" height="630" fill="{PAPER}"/>
<svg x="470" y="96" width="260" height="260" viewBox="0 0 32 32">{inner}</svg>
<text x="{600 + SIZE * 0.06 / 2}" y="506" text-anchor="middle" font-family="DIN Alternate" font-weight="700"
 font-size="{SIZE}" letter-spacing="{SIZE * 0.06}" fill="{BRAND}">{escape(name.upper())}</text>
</svg>
""",
    encoding="utf-8",
)
PY

rsvg-convert --width 1200 --height 630 "$work/share.svg" --output "$templates/og-image.png"
ls -l "$templates/og-image.png"
