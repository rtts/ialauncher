"""Unzip: unzipping a downloaded game, while the screen stays as it was."""

import pygame as pg

from ialauncher.scenes import MAGENTA
from ialauncher.scenes.unzip import Unzip
from ialauncher.tests.support import End, HeadlessTestCase, Paint, Script, key, screen


class TestUnzip(HeadlessTestCase):
    """Unzip."""

    loaded = True

    def test_ready(self) -> Script:
        """A game that's already unzipped continues right away."""
        yield Unzip(self.game("ready"), End())
        yield from self.wait_until_quit()
        self.assertEqual(self.unzips, [])
        self.assertEqual(self.trace, ["Unzip", "End"])

    def test_not_downloaded(self) -> Script:
        """A game that isn't downloaded continues right away."""
        yield Unzip(self.game(), End())
        yield from self.wait_until_quit()
        self.assertEqual(self.unzips, [])
        self.assertEqual(self.trace, ["Unzip", "End"])

    def test_unzip(self) -> Script:
        """The screen stays as it was until the game is unzipped."""
        self.finish_jobs = False
        game = self.game("downloaded")
        yield Paint(MAGENTA, Unzip(game, End()))
        self.assertIsInstance((yield None), Unzip)
        self.assertEqual(screen().get_at((0, 0)), MAGENTA)
        self.unzips[0].finish()
        yield from self.wait_until_quit()
        self.assertTrue(game.is_ready())
        self.assertEqual(self.trace, ["Paint", "Unzip", "End"])

    def test_join(self) -> Script:
        """A game that's already being unzipped isn't unzipped twice."""
        self.finish_jobs = False
        game = self.game("downloaded")
        game.unzip()
        yield Unzip(game, End())
        self.unzips[0].finish()
        yield from self.wait_until_quit()
        self.assertEqual(len(self.unzips), 1)
        self.assertTrue(game.is_ready())

    def test_escape(self) -> Script:
        """Escape continues, while the game is still being unzipped."""
        self.finish_jobs = False
        yield Unzip(self.game("downloaded"), End())
        yield key(pg.K_ESCAPE)
        yield from self.wait_until_quit()
        self.assertTrue(self.unzips[0].is_alive())
        self.assertEqual(self.trace, ["Unzip", "End"])

    def test_error(self) -> Script:
        """A failed unzip shows the error, and continues."""
        self.finish_jobs = False
        game = self.game("downloaded")
        yield Unzip(game, End())
        self.unzips[0].finish("Bad CRC")
        yield from self.wait_until_quit()
        self.assertEqual(self.errors, ["Bad CRC"])
        self.assertFalse(game.is_ready())
