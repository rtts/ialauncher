"""Run the app headless and browse around."""

from unittest import mock

import pygame as pg

from ialauncher.game import Game
from ialauncher.scenes import browse as browse_scene
from ialauncher.scenes.browse import Browse
from ialauncher.scenes.loading import Loading

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

    def test_ready_only(self) -> Script:
        """Tab shows only the ready games, and Ctrl-Enter adds or removes one."""
        ready: set[str] = set()

        def download(game: Game) -> mock.Mock:
            return mock.Mock(run=lambda _: ready.add(game.identifier))

        self.enterContext(
            mock.patch.object(Game, "is_ready", lambda game: game.identifier in ready)
        )
        self.enterContext(
            mock.patch.object(
                Game, "reset", lambda game: ready.discard(game.identifier)
            )
        )
        self.enterContext(mock.patch.object(browse_scene, "Download", download))
        browse = yield from self.wait_for(Browse)
        games = browse.games
        total = len(games.games)

        def current() -> str:
            return games.get_current_game().identifier

        # Without ready games, Tab does nothing
        yield key(pg.K_TAB)
        self.assertFalse(games.ready_only)
        self.assertEqual(len(games.games), total)

        # Add two games, and show only those
        yield text("prince")
        yield key(pg.K_RETURN, mod=pg.KMOD_CTRL)
        prince = current()
        yield key(pg.K_RIGHT)
        yield key(pg.K_RETURN, mod=pg.KMOD_CTRL)
        self.assertEqual(ready, {prince, current()})
        yield key(pg.K_TAB)
        self.assertTrue(games.ready_only)
        self.assertEqual(sorted(g.identifier for g in games.games), sorted(ready))

        # Removing a game hides it, removing the last one shows all games
        yield key(pg.K_RETURN, mod=pg.KMOD_CTRL)
        self.assertEqual(len(games.games), 1)
        yield key(pg.K_RETURN, mod=pg.KMOD_CTRL)
        self.assertFalse(ready)
        self.assertFalse(games.ready_only)
        self.assertEqual(len(games.games), total)

        # Tab shows all games again
        yield key(pg.K_RETURN, mod=pg.KMOD_CTRL)
        yield key(pg.K_TAB)
        self.assertEqual(len(games.games), 1)
        yield key(pg.K_TAB)
        self.assertEqual(len(games.games), total)
        self.assertEqual(current(), next(iter(ready)))

        self.assertIsNone((yield key(pg.K_ESCAPE)))
