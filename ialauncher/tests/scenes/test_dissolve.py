"""Dissolve: one title screen into the next."""

import pygame as pg

from ialauncher.engine import Scene
from ialauncher.scenes import CYAN, MAGENTA
from ialauncher.scenes.dissolve import FRAMES, GRID, Dissolve, fizzle
from ialauncher.tests.support import End, HeadlessTestCase, Paint, Script, screen


class TestDissolve(HeadlessTestCase):
    """Dissolve."""

    def frames(self, start: Scene) -> Script:
        """Run the scene, and count the cyan pixels of each frame of Dissolve."""
        self.cyan: list[int] = []
        scene = yield start
        while scene is not None:
            if isinstance(scene, Dissolve):
                mask = pg.mask.from_threshold(screen(), CYAN, (1, 1, 1, 255))
                self.cyan.append(mask.count())
            scene = yield None

    def test_fizzle(self) -> None:
        """Every pixel of the grid changes exactly once."""
        pixels = fizzle()
        self.assertEqual(len(pixels), GRID[0] * GRID[1])
        self.assertEqual(
            set(pixels), {(x, y) for x in range(GRID[0]) for y in range(GRID[1])}
        )

    def test_dissolve(self) -> Script:
        """The last frame turns into the next scene's, a little more every frame."""
        yield from self.frames(Paint(MAGENTA, Dissolve(Paint(CYAN, End()))))
        self.assertEqual(len(self.cyan), FRAMES)
        self.assertEqual(self.cyan, sorted(self.cyan))
        self.assertGreater(self.cyan[0], 0)
        self.assertEqual(self.cyan[-1], screen().get_width() * screen().get_height())
        self.assertEqual(self.trace, ["Paint", "Dissolve", "Paint", "End"])
