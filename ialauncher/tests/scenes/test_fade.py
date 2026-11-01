"""Fade: fading to black and back."""

from ialauncher.engine import Scene
from ialauncher.scenes import BLACK, MAGENTA
from ialauncher.scenes.fade import FRAMES, Fade, Fadein, Fadeout
from ialauncher.tests.support import End, HeadlessTestCase, Paint, Script, screen


class TestFade(HeadlessTestCase):
    """Fadeout and Fadein."""

    def frames(self, start: Scene) -> Script:
        """Run the scene, and collect the color in the middle of each frame of Fade."""
        self.colors: list[tuple[int, ...]] = []
        scene = yield start
        while scene is not None:
            if isinstance(scene, Fade):
                self.colors.append(tuple(screen().get_at(screen().get_rect().center)))
            scene = yield None

    def test_fadeout(self) -> Script:
        """Fading out darkens the last frame to black."""
        yield from self.frames(Paint(MAGENTA, Fadeout(End())))
        self.assertEqual(len(self.colors), FRAMES)
        reds = [color[0] for color in self.colors]
        self.assertEqual(reds, sorted(reds, reverse=True))
        self.assertGreater(reds[0], 0)
        self.assertEqual(self.colors[-1][:3], BLACK)
        self.assertEqual(self.trace, ["Paint", "Fadeout", "End"])

    def test_fadein(self) -> Script:
        """Fading in brightens the first frame of the next scene from black."""
        yield from self.frames(Fadein(Paint(MAGENTA, End())))
        self.assertEqual(len(self.colors), FRAMES)
        reds = [color[0] for color in self.colors]
        self.assertEqual(reds, sorted(reds))
        self.assertLess(reds[0], MAGENTA[0])
        self.assertEqual(self.colors[-1][:3], MAGENTA)
        self.assertEqual(self.trace, ["Fadein", "Paint", "End"])
