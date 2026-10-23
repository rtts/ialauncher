"""Starfield Simulation."""

import random
from typing import override

import pygame as pg

from ialauncher import options
from ialauncher.cga import cga
from ialauncher.engine import NextScene
from ialauncher.gamelist import gamelist
from ialauncher.utils import sharp_scale

from . import BLACK, Scene, hero


class Starfield(Scene):
    """Starfield Simulation."""

    def __init__(self, referrer: Scene, warp: float | None = None) -> None:
        """Remember the scene to hand back to, and fly at options.warp by default."""
        super().__init__()
        self.referrer = referrer
        self.stars: list[list] = []
        self.warp = options.warp if warp is None else warp

    def star(self, z: float = 1) -> list:
        """Return a star at depth z."""
        width, height = self.screen.get_size()
        game = random.choice(gamelist.games)  # noqa: S311
        x, y = random.triangular(-width, width), random.triangular(-height, height)  # noqa: S311

        # Round x and y to whole pixels, so there's a chance you
        # collide with the star when both happen to be zero.
        x, y = round(x), round(y)
        return [x / height, y / height, z, game]

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Hand back to the referrer on Escape."""
        escape = event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE
        return self.referrer if escape else None

    @override
    def update(self, screen: pg.Surface) -> NextScene:
        """Fly through space."""
        screen.fill(BLACK)
        rect = screen.get_rect()

        # Each star is a point in space, at a fixed x and y that put it
        # anywhere on the screen at depth z = 1, mostly near the center,
        # and moves toward the viewer at z = 0 by the same distance every
        # frame. Dividing x and y by z projects it onto the screen.
        if len(self.stars) < options.density:
            self.stars.append(self.star())
        for star in self.stars:
            star[2] -= self.warp / 1000
        self.stars.sort(key=lambda star: star[2], reverse=True)
        for star in self.stars:
            x, y, z, game = star
            if z <= 0:
                if x == y == 0 and game in gamelist.games:
                    # Collision!
                    gamelist.current_game = gamelist.games.index(game)
                    return hero.Hero()
                star[:] = self.star()
                continue
            offset = pg.Vector2(x, y) * rect.height / 2
            size = int(1 / z)
            pos = pg.Rect(0, 0, size, size)
            pos.center = rect.center + offset / z
            if not rect.colliderect(pos):
                star[:] = self.star()
            else:
                thumbnail = game.get_titlescreen((size, size)) or pg.Surface((1, 1))
                screen.blit(sharp_scale(cga.apply(thumbnail), (size, size)), pos)
        return None
