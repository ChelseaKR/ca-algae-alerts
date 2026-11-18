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


def png_pixels(data: bytes) -> list[list[tuple[int, int, int, int]]]:
    """Rows of (r, g, b, a) from an 8-bit RGBA, non-interlaced PNG."""
    width, height = png_size(data)
    depth, color_type, _, _, interlace = struct.unpack(">BBBBB", data[24:29])
    assert (depth, color_type, interlace) == (8, 6, 0), "expected 8-bit RGBA"
    idat = b""
    at = 8
    while at < len(data):
        (length,) = struct.unpack(">I", data[at : at + 4])
        if data[at + 4 : at + 8] == b"IDAT":
            idat += data[at + 8 : at + 8 + length]
        at += 12 + length
    raw = zlib.decompress(idat)
    stride = width * 4
    rows: list[list[tuple[int, int, int, int]]] = []
    previous = bytearray(stride)
    for y in range(height):
        start = y * (stride + 1)
        kind = raw[start]
        line = bytearray(raw[start + 1 : start + 1 + stride])
        for i in range(stride):
            left = line[i - 4] if i >= 4 else 0
            up = previous[i]
            corner = previous[i - 4] if i >= 4 else 0
            if kind == 1:
                line[i] = (line[i] + left) & 0xFF
            elif kind == 2:
                line[i] = (line[i] + up) & 0xFF
            elif kind == 3:
                line[i] = (line[i] + (left + up) // 2) & 0xFF
            elif kind == 4:
                line[i] = (line[i] + _paeth(left, up, corner)) & 0xFF
        rows.append(
            [
                (line[x * 4], line[x * 4 + 1], line[x * 4 + 2], line[x * 4 + 3])
                for x in range(width)
            ]
        )
        previous = line
    return rows
