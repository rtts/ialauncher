"""Starfield Simulation."""

import random
from typing import override

import pygame as pg

from ialauncher.cga import cga
from ialauncher.engine import NextScene
from ialauncher.gamelist import gamelist
from ialauncher.utils import sharp_scale

from . import BLACK, GRID_LARGER, Scene, hero

DENSITY = 100
WARP = 1
GROWTH_FACTOR = (1 + 5**0.5) / 2  # φ


class Starfield(Scene):
    """Starfield Simulation."""

    def __init__(self) -> None:
        """Initialize."""
        super().__init__()
        self.stars: list[list] = []

    def star(self) -> list:
        """Return a star."""
        width, height = self.screen.get_size()
        game = random.choice(gamelist.games)  # noqa: S311
        thumbnail = game.get_titlescreen((20, 13)) or pg.Surface((1, 1))
        x, y = random.triangular(-width, width), random.triangular(-height, height)  # noqa: S311
        return [x / height, y / height, 1, cga.apply(thumbnail)]

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Go back to Hero."""
        if event.type == pg.MOUSEMOTION or (
            event.type == pg.KEYDOWN
            and event.key not in {*GRID_LARGER, pg.K_LCTRL, pg.K_RCTRL}
        ):
            return hero.Hero()
        return None

    @override
    def update(self, screen: pg.Surface) -> NextScene:
        """Fly through space."""
        screen.fill(BLACK)
        rect = screen.get_rect()

        # Each star is a point in space, at a fixed x and y that put it
        # anywhere on the screen at depth z = 1, mostly near the center,
        # and moves toward the viewer at z = 0 by the same distance every
        # frame. Dividing x and y by z projects it onto the screen.
        if len(self.stars) < DENSITY:
            self.stars.append(self.star())
        for star in self.stars:
            star[2] -= WARP / 1000
            x, y, z, image = star
            offset = pg.Vector2(x, y) * rect.height / 2
            if z <= 0 or not rect.collidepoint(pos := rect.center + offset / z):
                star[:] = self.star()
            else:
                size = int(GROWTH_FACTOR / z - GROWTH_FACTOR + 1)
                screen.blit(sharp_scale(image, (size, size)), pos)
        return None
