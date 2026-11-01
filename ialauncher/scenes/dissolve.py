"""Dissolve one title screen into the next."""

from collections.abc import Iterator
from functools import cache
from typing import override

import pygame as pg

from ialauncher.engine import NextScene
from ialauncher.utils import letterbox

from . import BLACK, Scene

GRID = 320, 200
FRAMES = 60


class Dissolve(Scene):
    """Dissolve the last frame into the picture of the next scene."""

    def __init__(self, then: Scene) -> None:
        """Prepare to dissolve into the next scene."""
        super().__init__()
        self.then = then

    @override
    def start(self) -> NextScene:
        """Take two pictures: the last frame, and the next scene's first."""
        self.picture = self.screen.copy()
        self.screen.fill(BLACK)
        self.then.screen = self.screen
        self.then.draw()
        self.next_picture = self.screen.copy()
        rect = letterbox(self.screen.get_rect())
        self.xs = [rect.x + rect.width * x // GRID[0] for x in range(GRID[0] + 1)]
        self.ys = [rect.y + rect.height * y // GRID[1] for y in range(GRID[1] + 1)]
        self.done = 0
        return None

    @override
    def update(self) -> NextScene:
        """Change the next batch of pixels, and continue after the last."""
        pixels = fizzle()
        batch = pixels[self.done : self.done + -(-len(pixels) // FRAMES)]
        self.done += len(batch)
        xs, ys = self.xs, self.ys
        rects = [
            pg.Rect(xs[x], ys[y], xs[x + 1] - xs[x], ys[y + 1] - ys[y])
            for x, y in batch
        ]
        self.picture.blits(
            [(self.next_picture, rect, rect) for rect in rects], doreturn=False
        )
        self.screen.blit(self.picture, (0, 0))
        return self.then if self.done >= len(pixels) else None

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Ignore everything."""
        return None


@cache
def fizzle() -> list[tuple[int, int]]:
    """Return every pixel of the grid once, in a random-looking order.

    Like the "fizzlefade" of Wolfenstein 3D, which takes them from a
    17-bit linear-feedback shift register: the low 8 bits are y, and the
    high 9 bits are x. The register visits every value but 0 once.
    """
    return [(0, 0), *register()]


def register() -> Iterator[tuple[int, int]]:
    """Yield the x and y of each value of the register, until it repeats."""
    value = 1
    while True:
        x, y = value >> 8, value & 0xFF
        if x < GRID[0] and y < GRID[1]:
            yield x, y
        value = value >> 1 ^ (0x12000 if value & 1 else 0)
        if value == 1:
            return
