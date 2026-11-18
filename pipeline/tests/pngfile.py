"""Read a PNG file's size and pixels with the standard library alone.

The site ships a few small images made from its mark (icons, the share
image). The tests look at their real pixels, and the project has no image
library, so this reads the one kind of PNG those files are: 8-bit RGBA,
not interlaced.
"""

from __future__ import annotations

import struct
import zlib

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
Pixel = tuple[int, int, int, int]


def png_size(data: bytes) -> tuple[int, int]:
    """Width and height from a PNG file's header chunk."""
    assert data[:8] == PNG_SIGNATURE, "not a PNG file"
    assert data[12:16] == b"IHDR"
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def _unfilter(kind: int, line: bytearray, previous: bytearray, step: int) -> None:
    """Undo one row's PNG filter in place (0 none, 1 left, 2 up, 3 average,
    4 Paeth); `step` is the bytes in one pixel."""
    if kind == 0:
        return
    for i in range(len(line)):
        left = line[i - step] if i >= step else 0
        up = previous[i]
        corner = previous[i - step] if i >= step else 0
        if kind == 1:
            line[i] = (line[i] + left) & 0xFF
        elif kind == 2:
            line[i] = (line[i] + up) & 0xFF
        elif kind == 3:
            line[i] = (line[i] + (left + up) // 2) & 0xFF
        else:
            line[i] = (line[i] + _paeth(left, up, corner)) & 0xFF


def png_pixels(data: bytes) -> list[list[Pixel]]:
    """Rows of (r, g, b, a) from an 8-bit RGBA or RGB, non-interlaced PNG.
    An RGB file has no clear pixels, so each one reads as fully opaque."""
    width, height = png_size(data)
    depth, color_type, _, _, interlace = struct.unpack(">BBBBB", data[24:29])
    assert depth == 8 and color_type in (2, 6) and interlace == 0, "8-bit RGB(A)"
    step = 4 if color_type == 6 else 3
    idat = b""
    at = 8
    while at < len(data):
        (length,) = struct.unpack(">I", data[at : at + 4])
        if data[at + 4 : at + 8] == b"IDAT":
            idat += data[at + 8 : at + 8 + length]
        at += 12 + length
    raw = zlib.decompress(idat)
    stride = width * step
    rows: list[list[Pixel]] = []
    previous = bytearray(stride)
    for y in range(height):
        start = y * (stride + 1)
        line = bytearray(raw[start + 1 : start + 1 + stride])
        _unfilter(raw[start], line, previous, step)
        rows.append(
            [
                (
                    line[x * step],
                    line[x * step + 1],
                    line[x * step + 2],
                    line[x * step + 3] if step == 4 else 255,
                )
                for x in range(width)
            ]
        )
        previous = line
    return rows
