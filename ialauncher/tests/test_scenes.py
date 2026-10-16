"""Run the app headless and browse around."""

import unittest

import pygame as pg

from ialauncher.scenes import Browse, Loading

from .support import HeadlessTestCase, Script, key, text


class TestLoading(HeadlessTestCase):
    """The progress bar while the games are loading."""

    def test_quit_while_loading(self) -> Script:
        """Escape quits while the games are still loading."""
        loading = yield from self.wait_for(Loading)
        self.assertTrue(loading.todo, "all games were loaded in the first frame")
        self.assertIsNone((yield key(pg.K_ESCAPE)))


class TestBrowse(HeadlessTestCase):
    """The title screens of the loaded games."""

    def test_browse(self) -> Script:
        """Load the games, browse the title screens, and quit with Escape."""
        browse = yield from self.wait_for(Browse)
        games = browse.games
        self.assertTrue(games.games, "no games with a title screen were loaded")
        start = games.current_game

        def letter() -> str:
            return games.get_current_game().identifier[0].lower()

        yield key(pg.K_RIGHT)
        self.assertEqual(games.current_game, (start + 1) % len(games.games))
        yield key(pg.K_LEFT)
        self.assertEqual(games.current_game, start)

        first = letter()
        yield key(pg.K_DOWN)
        self.assertNotEqual(letter(), first)
        yield key(pg.K_UP)
        self.assertEqual(letter(), first)

        yield key(pg.K_MINUS)
        self.assertEqual(browse.cols, 3)
        pos = browse.pos
        yield key(pg.K_DOWN)
        self.assertEqual(browse.pos, pos + 3)
        self.assertEqual(games.current_game, browse.pos % len(games.games))
        yield key(pg.K_PLUS)
        self.assertEqual(browse.cols, 1)

        yield text("prince")
        self.assertEqual(games.query, "prince")
        self.assertRegex(games.get_current_game().identifier, "(?i)^prince")

        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_no_downloads(self) -> Script:
        """Pressing Enter fails the test instead of downloading or starting a game."""
        yield from self.wait_for(Browse)
        with self.assertRaisesRegex(AssertionError, "tried to"):
            yield key(pg.K_RETURN)


if __name__ == "__main__":
    unittest.main()
