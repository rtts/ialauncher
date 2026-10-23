"""Starfield Simulation."""

import random
from typing import override

import pygame as pg

from ialauncher.cga import cga
from ialauncher.engine import NextScene
from ialauncher.gamelist import gamelist
from ialauncher.utils import sharp_scale

from . import BLACK, INPUT_EVENTS, Scene

DENSITY = 10000
WARP = 1


class Starfield(Scene):
    """Starfield Simulation."""

    def __init__(self, referrer: Scene) -> None:
        """Remember the scene to hand back to."""
        super().__init__()
        self.referrer = referrer
        self.stars: list[list] = []

    def star(self, z: float = 1) -> list:
        """Return a star at depth z."""
        width, height = self.screen.get_size()
        game = random.choice(gamelist.games)  # noqa: S311
        x, y = random.triangular(-width, width), random.triangular(-height, height)  # noqa: S311
        return [x / height, y / height, z, game]

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Hand back to the referrer on any input."""
        return self.referrer if event.type in INPUT_EVENTS else None

    @override
    def update(self, screen: pg.Surface) -> NextScene:
        """Fly through space."""
        screen.fill(BLACK)
        rect = screen.get_rect()

        # Each star is a point in space, at a fixed x and y that put it
        # anywhere on the screen at depth z = 1, mostly near the center,
        # and moves toward the viewer at z = 0 by the same distance every
        # frame. Dividing x and y by z projects it onto the screen.
        if not self.stars:
            self.stars = [self.star(random.random()) for _ in range(DENSITY)]  # noqa: S311
        for star in self.stars:
            star[2] -= WARP / 1000
        self.stars.sort(key=lambda star: star[2], reverse=True)
        for star in self.stars:
            x, y, z, game = star
            if z <= 0:
                star[:] = self.star()
                continue
            offset = pg.Vector2(x, y) * rect.height / 2
            pos = rect.center + offset / z
            size = int(1 / z)
            if not rect.colliderect((pos, (size, size))):
                star[:] = self.star()
            else:
                thumbnail = game.get_titlescreen((size, size)) or pg.Surface((1, 1))
                screen.blit(sharp_scale(cga.apply(thumbnail), (size, size)), pos)
        return None
