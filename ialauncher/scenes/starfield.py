"""Starfield Simulation."""

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

import pygame as pg

from ialauncher import options
from ialauncher.engine import NextScene
from ialauncher.game import Game
from ialauncher.gamelist import gamelist
from ialauncher.utils import sharp_scale

from . import BLACK, Scene, hero
from .stars import Stars

if TYPE_CHECKING:
    from .browse import Browse

FPS = 30
SPEED = 30  # seconds from z = 1 to z = 0

# How far stars travel on average before they leave the screen,
# assuming a triangular distribution of stars, is equal to
# the integral of 4z² - 4z³ + z⁴ from 0 to 1.
TRAVELLED = 8 / 15


@dataclass(slots=True)
class Star:
    """A star with a fixed x and y and a moving z."""

    x: float
    y: float
    z: float
    game: Game
    size: int
    image: pg.Surface


class Starfield(Scene):
    """Starfield Simulation."""

    def __init__(self, referrer: "Browse") -> None:
        """Initialize."""
        super().__init__()
        self.referrer = referrer
        self.stars: list[Star] = []
        self.dots: dict[Game, pg.Surface] = {}
        self.games = gamelist.autoplayable_games()
        self.step = options.warp / (SPEED * FPS)
        # Filling at this rate prevents "waves" of stars.
        self.rate = options.density * self.step / TRAVELLED
        self.due = 0.0
        # Chance per frame of adding a star in the exact center.
        self.chance = 1 / (options.mtbc * FPS) if options.mtbc else 0

    @override
    def update(self) -> NextScene:
        """Fly through space."""
        self.screen.fill(BLACK)
        width, height = self.screen.get_size()
        center_x, center_y = self.screen.get_rect().center

        # Each star is a point in space, at a fixed x and y that put it
        # anywhere on the screen at depth z = 1, mostly near the center,
        # and moves toward the viewer at z = 0 by the same distance every
        # frame. Dividing x and y by z projects it onto the screen.
        new = 0
        stars = []
        blits = []
        for star in self.stars:
            star.z -= self.step
            if star.z <= 1 / height:
                if star.x == star.y == 0:
                    # Collision!
                    gamelist.current_game = gamelist.games.index(star.game)
                    return hero.Hero(screensaver=True)
                new += 1
                continue
            scale = 1 / star.z
            if int(scale) != star.size:
                star.size = int(scale)
                star.image = self.image(star.game, star.size)
            left = center_x - star.size // 2 + star.x * scale
            top = center_y - star.size // 2 + star.y * scale
            if not (-star.size < left < width and -star.size < top < height):
                new += 1
                continue
            stars.append(star)
            blits.append((star.image, (left, top)))
        self.screen.fblits(blits)

        # Replace stars that left and add more until field is full.
        self.due += self.rate
        due = int(self.due)
        self.due -= due
        new = min(max(new, due), options.density - len(stars))
        self.stars = [self.star() for _ in range(new)] + stars

        if random.random() < self.chance:  # noqa: S311
            self.stars.append(self.star(center=True))
        return None

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Exit on Escape, start DOS version on Enter, add center star on Space."""
        if event.type != pg.KEYDOWN:
            return None
        if event.key in (pg.K_RETURN, pg.K_KP_ENTER):
            Stars.launch(autorun=not event.mod & pg.KMOD_ALT)
            return None
        if event.key == pg.K_SPACE:
            self.stars.append(self.star(center=True))
            return None
        return self.referrer if event.key == pg.K_ESCAPE else None

    def star(self, *, center: bool = False) -> Star:
        """Return a new star at depth z = 1, optionally in the exact center."""
        width, height = self.screen.get_size()
        game = random.choice(self.games)  # noqa: S311
        if center:
            x = y = 0.0
        else:
            x, y = random.triangular(-width, width), random.triangular(-height, height)  # noqa: S311
        return Star(x / 2, y / 2, 1, game, size=1, image=self.image(game, 1))

    def image(self, game: Game, size: int) -> pg.Surface:
        """Return the game's title screen as a star of the given size."""
        if size == 1 and game.color is not None:
            if (dot := self.dots.get(game)) is None:
                dot = self.dots[game] = pg.Surface((1, 1))
                dot.fill(game.color)
            return dot
        thumbnail = game.get_titlescreen((size, size)) or pg.Surface((1, 1))
        return sharp_scale(thumbnail, (size, size))

    @override
    def get_events(self) -> list[pg.event.Event]:
        """Run at FPS frames per second."""
        self.clock.tick(FPS)
        return pg.event.get()
