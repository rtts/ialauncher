"""CRT: switching the CRT off and on."""

import pygame as pg

from ialauncher.engine import Scene
from ialauncher.scenes import BLACK, MAGENTA
from ialauncher.scenes.crt import CRT
from ialauncher.tests.support import End, HeadlessTestCase, Paint, Script, screen


def pixels() -> tuple[pg.Color, pg.Color]:
    """Return the colors in the middle and near the top of the screen."""
    surface = screen()
    x, y = surface.get_rect().center
    return surface.get_at((x, y)), surface.get_at((x, 10))


class TestCRT(HeadlessTestCase):
    """CRT."""

    def setUp(self) -> None:
        """Animate the CRT, which the other tests skip."""
        super().setUp()
        self.animate_crt = True

    def frames(self, start: Scene) -> Script:
        """Run the scene, and collect the pixels of each frame of the CRT."""
        self.pixels: list[tuple[pg.Color, pg.Color]] = []
        scene = yield start
        while scene is not None:
            if isinstance(scene, CRT):
                self.pixels.append(pixels())
            scene = yield None

    def test_off(self) -> Script:
        """Switching off squeezes the last frame into a line, and then into black."""
        yield from self.frames(Paint(MAGENTA, CRT(End(), on=False)))
        self.assertEqual(len(self.pixels), 17)
        self.assertEqual(self.pixels[0], (MAGENTA, MAGENTA))
        self.assertEqual(self.pixels[8], (MAGENTA, BLACK))
        self.assertEqual(self.pixels[-1], (BLACK, BLACK))
        self.assertEqual(self.trace, ["Paint", "CRT", "End"])

    def test_on(self) -> Script:
        """Switching on unsqueezes the first frame of a scene that hasn't run yet."""
        yield from self.frames(CRT(Paint(MAGENTA, End()), on=True))
        self.assertEqual(len(self.pixels), 17)
        self.assertEqual(self.pixels[0], (MAGENTA, BLACK))
        self.assertEqual(self.pixels[-1], (MAGENTA, MAGENTA))
        self.assertEqual(self.trace, ["CRT", "Paint", "End"])
