import pygame as pg

from .cga import cga

# fmt: off
CHEAT_CODES: dict[str, int | None] = {
    "dnkroz": 0,       # Duke Nukem 3D
    "dnstuff": 1,      # Duke Nukem 3D
    "iddqd": 2,        # Doom
    "idkfa": 3,        # Doom
    "ken sent me": 4,  # Leisure Suit Larry
    "megahit": 5,      # Prince of Persia
    "xyzzy": None,     # Colossal Cave Adventure
}
# fmt: on


class Cheats:
    def __init__(self) -> None:
        self.typed = ""
        self.longest = max(len(code) for code in CHEAT_CODES)

    def cheat(self, event: pg.event.Event) -> bool:
        if event.type != pg.KEYDOWN or not event.unicode:
            return False
        self.typed = (self.typed + event.unicode.lower())[-self.longest :]
        for code, palette in CHEAT_CODES.items():
            if self.typed.endswith(code):
                self.typed = ""
                cga.set_palette(palette)
                return True
        return False


cheats = Cheats()
cheat = cheats.cheat
