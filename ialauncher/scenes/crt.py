"""Cathode ray tube."""

from typing import override

import pygame as pg

from ialauncher.engine import NextScene
from ialauncher.utils import letterbox

from . import BLACK, Scene

STEPS = 8


class CRT(Scene):
    """Squeeze the picture into a line, then into nothing, like a CRT.

    Switching on does the same in reverse, with the picture of the next
    scene. Either way, continue with the next scene.
    """

    def __init__(self, then: Scene, *, on: bool) -> None:
        """Prepare to switch the CRT off or on."""
        super().__init__()
        self.then = then
        self.on = on

    @override
    def start(self) -> NextScene:
        """Take the picture: the last frame, or the next scene when switching on."""
        if self.on:
            self.screen.fill(BLACK)
            self.then.screen = self.screen  # It may not have run yet
            self.then.draw()
        self.picture = self.screen.copy()
        steps = range(STEPS, -STEPS, -1)
        self.steps = iter(reversed(steps) if self.on else steps)
        return None

    @override
    def update(self) -> NextScene:
        """Draw the next step, and continue with the next scene after the last."""
        self.screen.fill(BLACK)
        step = next(self.steps, None)
        if step is None:
            if self.on:
                self.screen.blit(self.picture, (0, 0))
            return self.then
        rect = self.screen.get_rect()
        box = letterbox(rect)
        line = max(1, rect.height // 200)
        if step > 0:
            size = box.width, max(line, box.height * step // STEPS)
        else:
            size = box.width * (STEPS + step) // STEPS, line
        squeezed = pg.transform.scale(self.picture.subsurface(box), size)
        self.screen.blit(squeezed, squeezed.get_rect(center=rect.center))
        return None

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Ignore everything."""
        return None
