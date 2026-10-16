"""Convert to CGA colors."""

from weakref import WeakKeyDictionary

import pygame as pg

BLACK = (0, 0, 0)
PALETTES = [
    [BLACK, (170, 0, 0), (0, 170, 0), (170, 85, 0)],
    [BLACK, (255, 85, 85), (85, 255, 85), (255, 255, 85)],
    [BLACK, (170, 0, 170), (0, 170, 170), (170, 170, 170)],
    [BLACK, (255, 85, 255), (85, 255, 255), (255, 255, 255)],
    [BLACK, (170, 0, 0), (0, 170, 170), (170, 170, 170)],
    [BLACK, (255, 85, 85), (85, 255, 255), (255, 255, 255)],
]
PALETTE_BITSIZE = 8
WEIGHTS = 0.299, 0.587, 0.114  # Rec. 601
LUMA = [bytes(int(value * weight) for value in range(256)) for weight in WEIGHTS]


def luma(color: tuple[int, int, int]) -> float:
    """Return the perceived brightness of a color."""
    return sum(value * weight for value, weight in zip(color, WEIGHTS, strict=True))


class CGA:
    """The current CGA palette, if any.

    Converted images are cached until the palette changes.
    """

    def __init__(self) -> None:
        """Start without a palette, showing the original colors."""
        self.palette: int | None = None
        self.converted: WeakKeyDictionary[pg.Surface, pg.Surface] = WeakKeyDictionary()

    def set_palette(self, palette: int | None) -> None:
        """Switch to one of the PALETTES, or None for the original colors."""
        self.palette = palette
        self.converted.clear()

    def apply(self, image: pg.Surface) -> pg.Surface:
        """Return the image in the current palette."""
        if self.palette is None:
            return image
        if (converted := self.converted.get(image)) is None:
            converted = self.converted[image] = self.convert(image, self.palette)
        return converted

    def convert(self, image: pg.Surface, palette: int) -> pg.Surface:
        """Return the image converted to the given palette."""
        colors = PALETTES[palette]
        size = image.get_size()

        # Keep images that only use the colors of the palette already.
        if image.get_bitsize() == PALETTE_BITSIZE:
            indices = set(pg.image.tobytes(image, "P"))
            used = {tuple(image.get_palette_at(i))[:3] for i in indices}
            if used <= set(colors):
                return image

        # Combine the channels into one brightness byte per pixel.
        rgb = pg.image.tobytes(image, "RGB")
        channels = (int.from_bytes(rgb[c::3].translate(LUMA[c])) for c in range(3))
        levels = sum(channels).to_bytes(len(rgb) // 3)

        # Map each brightness to the nearest color of the palette.
        targets = [(luma(color) + 85 * i) / 2 for i, color in enumerate(colors)]
        nearest = [
            min(range(4), key=lambda i: abs(targets[i] - level)) for level in range(256)
        ]
        indexed = pg.image.frombytes(levels, size, "P")
        indexed.set_palette([colors[i] for i in nearest])

        return indexed


cga = CGA()
