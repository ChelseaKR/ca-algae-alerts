#!/usr/bin/env bash
# Render the site's raster icons from the sign-board mark (docs/DESIGN.md).
#
# Google Search shows a site icon only from a file it can crawl, in one of
# BMP, GIF, ICO, PNG, JPEG, PPM or TIFF, square, and it recommends a multiple
# of 48 px (developers.google.com/search/docs/appearance/favicon-in-search,
# read 2026-11-17). The SVG mark alone does not qualify. This writes, next to
# mark.svg:
#
#   icon-48.png, icon-96.png, icon-192.png   the <link rel="icon"> files
#   favicon.ico                              16, 32 and 48 px, for clients
#                                            that ask for /favicon.ico
#
# Every pixel comes from templates/mark.svg; nothing is drawn here. This is a
# developer tool, not part of the build: the outputs are committed, and the
# build copies them (site.py, extras). Run it again, and commit the files,
# only when mark.svg changes. Needs rsvg-convert (brew install librsvg).
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
templates="$root/pipeline/src/caalgae/templates"
mark="$templates/mark.svg"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

command -v rsvg-convert >/dev/null || {
  echo "rsvg-convert not found (brew install librsvg)" >&2
  exit 1
}

for size in 48 96 192; do
  rsvg-convert --width "$size" --height "$size" "$mark" --output "$templates/icon-$size.png"
done
for size in 16 32 48; do
  rsvg-convert --width "$size" --height "$size" "$mark" --output "$work/$size.png"
done

# An .ico file is a small directory followed by the images; each image may be
# a whole PNG file (every browser since Internet Explorer 11 reads that).
python3 - "$work" "$templates/favicon.ico" <<'PY'
import struct
import sys
from pathlib import Path

work, out = Path(sys.argv[1]), Path(sys.argv[2])
images = [(size, (work / f"{size}.png").read_bytes()) for size in (16, 32, 48)]
offset = 6 + 16 * len(images)
directory = struct.pack("<HHH", 0, 1, len(images))
for size, data in images:
    directory += struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(data), offset)
    offset += len(data)
out.write_bytes(directory + b"".join(data for _, data in images))
PY

ls -l "$templates"/icon-*.png "$templates/favicon.ico"
