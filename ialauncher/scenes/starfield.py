"""Starfield Simulation."""

import math
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

if TYPE_CHECKING:
    from .browse import Browse

FPS = 60
SPEED = 5
ZOOM = 3

# How long stars live on average before they leave the screen, in seconds
# at warp 1. Assuming a triangular distribution of stars, they complete
# the integral of 4z² - 4z³ + z⁴ from 0 to 1 = 8/15 of the flight.
LIFESPAN = 8 / 15 * 100 / SPEED

# Stars that grow larger than this many pixels are discarded.
MAX_SIZE = 50_000


@dataclass(slots=True)
class Star:
    """A star with a fixed x and y and a moving z from 1 to 0."""

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
        self.games = gamelist.games
        self.step = options.warp * SPEED / (100 * FPS)
        # Filling at this rate prevents "waves" of stars.
        self.rate = options.density * options.warp / (LIFESPAN * FPS)
        self.due = 0.0
        # Chance per frame of adding a star in the exact center.
        self.chance = 1 / (options.mtbc * FPS) if options.mtbc else 0

    @override
    def start(self) -> NextScene:
        """Fill the field with few stars nearby and more further away.

        Stars at depth z are kept with probability z, so the field gets
        denser as we fly in. Counting the stars that are on screen, also
        the ones not kept, prevents "waves" of stars.
        """
        width, height = self.screen.get_size()
        full = 0
        while full < options.density:
            star = self.star()
            star.z = 1 - random.random()  # noqa: S311
            scale = 1 / star.z
            size = size_at(star.z)
            left = width // 2 - size // 2 + star.x * scale
            top = height // 2 - size // 2 + star.y * scale
            if -size < left < width and -size < top < height:
                full += 1
                # A star at depth z is on screen with a probability of
                # p(z) = (2z - z²)², so most visible stars are far away.
                # Keeping them with probability z therefore keeps
                # ∫z·p(z) / ∫p(z) = (11/30) / (8/15) = 11/16 ≈ 69% of stars
                if random.random() < star.z:  # noqa: S311
                    self.stars.append(star)
        self.stars.sort(key=lambda star: star.z, reverse=True)
        return None

    @override
    def update(self) -> NextScene:
        """Fly through space."""
        self.screen.fill(BLACK)
        width, height = self.screen.get_size()
        center_x, center_y = self.screen.get_rect().center
        collision_z = depth_at(height)
        min_z = depth_at(MAX_SIZE)

        # Each star is a point in space, at a fixed x and y that put it
        # anywhere on the screen at depth z = 1, mostly near the center,
        # and moves toward the viewer at z = 0 by the same distance every
        # frame. Dividing x and y by z projects it onto the screen.
        stars = []
        blits = []
        close = []
        for star in self.stars:
            star.z -= self.step
            if star.x == star.y == 0 and star.z <= collision_z:
                # Collision!
                gamelist.current_game = gamelist.games.index(star.game)
                return hero.Hero(screensaver=True)
            if star.z < min_z:
                continue
            scale = 1 / star.z
            size = size_at(star.z)
            left = center_x - size // 2 + star.x * scale
            top = center_y - size // 2 + star.y * scale
            if not (-size < left < width and -size < top < height):
                continue
            stars.append(star)
            if size > height:
                close.append((star.game, left, top, size))
                continue
            if size != star.size:
                star.size = size
                star.image = self.image(star.game, size)
            blits.append((star.image, (left, top)))
        self.screen.fblits(blits)
        for game, left, top, size in close:
            self.draw_close(game, left, top, size)

        # Replace the stars that left, and add more until the field is full.
        left = len(self.stars) - len(stars)
        self.due += self.rate
        due = int(self.due)
        self.due -= due
        new = min(max(left, due), options.density - len(stars))
        self.stars = [self.star() for _ in range(new)] + stars

        if random.random() < self.chance:  # noqa: S311
            self.stars.insert(0, self.star(center=True))
        return None

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Exit on Escape, add center star on Space."""
        if event.type != pg.KEYDOWN:
            return None
        if event.key == pg.K_SPACE:
            self.stars.insert(0, self.star(center=True))
            return None
        return self.referrer if event.key == pg.K_ESCAPE else None

    def star(self, *, center: bool = False) -> Star:
        """Return a new star at depth z = 1, optionally in the exact center."""
        width, height = self.screen.get_size()
        autoplayable = [game for game in self.games if game.autoplay] if center else []
        game = random.choice(autoplayable or self.games)  # noqa: S311
        x = 0.0 if center else random.triangular(-width / 2, width / 2)  # noqa: S311
        y = 0.0 if center else random.triangular(-height / 2, height / 2)  # noqa: S311
        return Star(x, y, 1, game, size=1, image=self.image(game, 1))

    def image(self, game: Game, size: int) -> pg.Surface:
        """Return the game's title screen as a star of the given size."""
        if size == 1 and game.color is not None:
            if (dot := self.dots.get(game)) is None:
                dot = self.dots[game] = pg.Surface((1, 1))
                dot.fill(game.color)
            return dot
        thumbnail = game.get_titlescreen((size, size)) or pg.Surface((1, 1))
        return sharp_scale(thumbnail, (size, size))

    def draw_close(self, game: Game, left: float, top: float, size: int) -> None:
        """Draw a star larger than the screen, scaling up only the part in view."""
        image = game.get_titlescreen((size, size))
        if image is None:
            return
        image_width, image_height = image.get_size()
        width, height = self.screen.get_size()
        pixel_width, pixel_height = size / image_width, size / image_height
        x0 = max(0, math.floor(-left / pixel_width))
        x1 = min(image_width, math.ceil((width - left) / pixel_width))
        y0 = max(0, math.floor(-top / pixel_height))
        y1 = min(image_height, math.ceil((height - top) / pixel_height))
        part = image.subsurface((x0, y0, x1 - x0, y1 - y0))
        scaled_size = round((x1 - x0) * pixel_width), round((y1 - y0) * pixel_height)
        position = round(left + x0 * pixel_width), round(top + y0 * pixel_height)
        self.screen.blit(sharp_scale(part, scaled_size), position)

    @override
    def get_events(self) -> list[pg.event.Event]:
        """Run at FPS frames per second."""
        self.clock.tick(FPS)
        return pg.event.get()


def size_at(z: float) -> int:
    """Return the size of a star at depth z, in pixels."""
    return int(1 + ZOOM * (1 / z - 1))


def depth_at(size: int) -> float:
    """Return the depth z at which a star becomes the given size."""
    return ZOOM / (ZOOM + size - 1)
