"""Download: downloading a game behind a progress bar."""

import pygame as pg

from ialauncher.scenes.download import Download
from ialauncher.tests.support import End, HeadlessTestCase, Script, key


class TestDownload(HeadlessTestCase):
    """Download."""

    loaded = True

    def test_downloaded(self) -> Script:
        """A downloaded game continues right away."""
        yield Download(self.game("downloaded"), End())
        yield from self.wait_until_quit()
        self.assertEqual(self.trace, ["Download", "End"])
        self.assertEqual(self.downloads, [])

    def test_progress(self) -> Script:
        """The progress bar stays until the download is done."""
        self.finish_jobs = False
        game = self.game()
        self.assertIsInstance((yield Download(game, End())), Download)
        self.downloads[0].progress = 0.5
        self.assertIsInstance((yield None), Download)
        self.downloads[0].finish()
        yield from self.wait_until_quit()
        self.assertEqual(self.trace, ["Download", "End"])
        self.assertTrue(game.is_downloaded())

    def test_escape(self) -> Script:
        """Escape cancels the download, and continues."""
        self.finish_jobs = False
        yield Download(self.game(), End())
        yield key(pg.K_ESCAPE)
        yield from self.wait_until_quit()
        self.assertTrue(self.downloads[0].cancelled.is_set())
        self.assertEqual(self.trace, ["Download", "End"])

    def test_error(self) -> Script:
        """A failed download shows the error, and continues."""
        self.finish_jobs = False
        game = self.game()
        yield Download(game, End())
        self.downloads[0].finish("No carrier")
        yield from self.wait_until_quit()
        self.assertEqual(self.errors, ["No carrier"])
        self.assertFalse(game.is_downloaded())
        self.assertEqual(self.trace, ["Download", "End"])

    def test_quit(self) -> Script:
        """Closing the window cancels the download, and quits."""
        self.finish_jobs = False
        yield Download(self.game(), End())
        self.assertIsNone((yield pg.event.Event(pg.QUIT)))
        self.assertTrue(self.downloads[0].cancelled.is_set())
        self.assertEqual(self.trace, ["Download"])
