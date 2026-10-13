import pygame as pg

# fmt: off
CHEAT_CODES: tuple[str, str, str, str, str, str, str] = (
    "dnkroz",       # Duke Nukem 3D
    "dnstuff",      # Duke Nukem 3D
    "iddqd",        # Doom
    "idkfa",        # Doom
    "ken sent me",  # Leisure Suit Larry
    "megahit",      # Prince of Persia
    "xyzzy",        # Colossal Cave Adventure
)
# fmt: on

BLACK = (0, 0, 0)
PALETTES = [
    [BLACK, (170, 0, 0), (0, 170, 0), (170, 85, 0)],
    [BLACK, (255, 85, 85), (85, 255, 85), (255, 255, 85)],
    [BLACK, (170, 0, 170), (0, 170, 170), (170, 170, 170)],
    [BLACK, (255, 85, 255), (85, 255, 255), (255, 255, 255)],
    [BLACK, (170, 0, 0), (0, 170, 170), (170, 170, 170)],
    [BLACK, (255, 85, 85), (85, 255, 255), (255, 255, 255)],
]


THIRDS = bytes(value // 3 for value in range(256))


class CGA:
    def __init__(self) -> None:
        self.typed = ""
        self.palette: int | None = None

    def cheat(self, event: pg.event.Event) -> bool:
        if event.type != pg.KEYDOWN or not event.unicode:
            return False
        longest = max(len(code) for code in CHEAT_CODES)
        self.typed = (self.typed + event.unicode.lower())[-longest:]
        for i, code in enumerate(CHEAT_CODES):
            if self.typed.endswith(code):
                self.typed = ""
                self.palette = (0, 1, 2, 3, 4, 5, None)[i]
                return True
        return False

    def apply(self, image: pg.Surface) -> pg.Surface:
        if self.palette is None:
            return image
        colors = PALETTES[self.palette]
        size = image.get_size()

        # Keep images that only use the colors of the palette already.
        if image.get_bitsize() == 8:
            indices = set(pg.image.tobytes(image, "P"))
            used = {tuple(image.get_palette_at(i))[:3] for i in indices}
            if used <= set(colors):
                return image

        # Average the channels into one brightness byte per pixel. Each third
        # fits in a byte, so the bytes can be added as big integers without
        # carrying over into their neighbors.
        rgb = pg.image.tobytes(image, "RGB")
        thirds = (int.from_bytes(rgb[c::3].translate(THIRDS)) for c in range(3))
        levels = sum(thirds).to_bytes(len(rgb) // 3)

        # Map the brightness to the colors of the palette (ordered from dark
        # to bright) in four equal steps.
        indexed = pg.image.frombytes(levels, size, "P")
        indexed.set_palette([colors[level * 4 // 256] for level in range(256)])
        return indexed


cga = CGA()
