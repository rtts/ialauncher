"""Cathode ray tube."""

from abc import abstractmethod
from typing import override

import pygame as pg

from ialauncher.engine import NextScene
from ialauncher.utils import letterbox

from . import BLACK, Scene

STEPS = 8
FRAMES = 2 * STEPS + 1


class CRT(Scene):
    """Squeeze a picture into a line, then into nothing, like a CRT, or back.

    Subclasses take the picture, and choose the steps.
    """

    picture: pg.Surface

    def __init__(self, then: Scene) -> None:
        """Prepare to switch the CRT off or on, and continue with the next scene."""
        super().__init__()
        self.then = then
        self.frame = 0

    @abstractmethod
    def step(self, frame: int) -> int:
        """Return the step in the given frame, from 0.

        From STEPS down to 0, the picture is squeezed into a line, and
        from 0 down to -STEPS, the line into nothing.
        """

    @override
    def update(self) -> NextScene:
        """Draw the next step, and continue with the next scene after the last."""
        step = self.step(self.frame)
        self.frame += 1
        self.screen.fill(BLACK)
        rect = self.screen.get_rect()
        box = letterbox(rect)
        line = max(1, rect.height // 200)
        if step > 0:
            size = box.width, max(line, box.height * step // STEPS)
        else:
            size = box.width * (STEPS + step) // STEPS, line
        if size[0] > 0:
            squeezed = pg.transform.scale(self.picture.subsurface(box), size)
            self.screen.blit(squeezed, squeezed.get_rect(center=rect.center))
        return self.then if self.frame >= FRAMES else None

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Ignore everything."""
        return None


class CRToff(CRT):
    """Switch the CRT off, squeezing the last frame into nothing."""

    @override
    def start(self) -> NextScene:
        """Take the picture: the last frame."""
        self.picture = self.screen.copy()
        return None

    @override
    def step(self, frame: int) -> int:
        """Squeeze from the whole picture into nothing."""
        return STEPS - frame


class CRTon(CRT):
    """Switch the CRT on, unsqueezing the first frame of the next scene."""

    @override
    def start(self) -> NextScene:
        """Take the picture: the next scene's first frame."""
        self.screen.fill(BLACK)
        self.then.screen = self.screen  # It hasn't run yet
        self.then.draw()
        self.picture = self.screen.copy()
        return None

    @override
    def step(self, frame: int) -> int:
        """Unsqueeze from a short line into the whole picture, and show it once more."""
        return min(frame + 1 - STEPS, STEPS)
