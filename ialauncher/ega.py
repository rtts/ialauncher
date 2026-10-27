"""The 8x14 font of the EGA BIOS.

The glyphs are those of DOSBox Staging's int10_font_14, in code page
437 order, with one byte per row of eight pixels.
"""

from pathlib import Path

import pygame as pg

FONT = (Path(__file__).parent / "ega.f14").read_bytes()


def render(
    text: str,
    color: tuple[int, int, int],
    background: tuple[int, int, int],
    padding: tuple[int, int] = (0, 0),
) -> pg.Surface:
    """Return the text at 16x28 pixels per character, padding included.

    Characters that are not in code page 437 are shown as smiley faces.
    """
    codes = b"".join(c.encode("cp437", errors="ignore") or b"\x01" for c in text)
    width = len(codes) * 8 + 2 * padding[0]
    height = 14 + 2 * padding[1]
    pixels = bytearray(width * height)
    for row in range(14):
        start = (padding[1] + row) * width + padding[0]
        bits = "".join(f"{FONT[code * 14 + row]:08b}" for code in codes)
        pixels[start : start + len(bits)] = bytes(map(int, bits))
    image = pg.image.frombytes(bytes(pixels), (width, height), "P")
    image.set_palette([background, color])
    return pg.transform.scale_by(image, 2)
