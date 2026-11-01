"""Fade to black."""

from abc import abstractmethod
from typing import override

import pygame as pg

from ialauncher.engine import NextScene

from . import BLACK, Scene

LEVELS = 63  # The brightest level of the VGA palette
FRAMES = 60


class Fade(Scene):
    """Fade a picture through the levels of the VGA palette."""

    picture: pg.Surface

    def __init__(self, then: Scene) -> None:
        """Prepare to fade, and continue with the next scene."""
        super().__init__()
        self.then = then
        self.frame = 0

    @abstractmethod
    def level(self, frame: int) -> int:
        """Return the level of the palette in the given frame, from 1."""

    @override
    def update(self) -> NextScene:
        """Draw the picture at the next level, and continue after the last."""
        self.frame += 1
        value = round(255 * self.level(self.frame) / LEVELS)
        self.screen.blit(self.picture, (0, 0))
        self.screen.fill((value, value, value), special_flags=pg.BLEND_MULT)
        return self.then if self.frame >= FRAMES else None

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Ignore everything."""
        return None


class Fadeout(Fade):
    """Fade the last frame to black."""

    @override
    def start(self) -> NextScene:
        """Take the picture: the last frame."""
        self.picture = self.screen.copy()
        return None

    @override
    def level(self, frame: int) -> int:
        """Darken from the brightest level to black."""
        return LEVELS - LEVELS * frame // FRAMES


class Fadein(Fade):
    """Fade the first frame of the next scene in from black."""

    @override
    def start(self) -> NextScene:
        """Take the picture: the next scene's first frame."""
        self.screen.fill(BLACK)
        self.then.screen = self.screen
        self.then.draw()
        self.picture = self.screen.copy()
        return None

    @override
    def level(self, frame: int) -> int:
        """Brighten from black to the brightest level."""
        return LEVELS * frame // FRAMES
