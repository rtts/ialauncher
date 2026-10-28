"""Browse: the filter, favorites and keys that Hero and Grid share."""

from pathlib import Path
from unittest import mock

import pygame as pg

import games as gd
from ialauncher import bios
from ialauncher.gamelist import gamelist
from ialauncher.scenes.grid import Grid
from ialauncher.scenes.hero import Hero
from ialauncher.tests.support import HeadlessTestCase, Script, key, text

LIBRARY = {
    entry.name
    for entry in Path(gd.__file__).parent.iterdir()
    if (entry / "metadata.ini").exists()
}


def current() -> str | None:
    """Return the identifier of the current game, if any."""
    game = gamelist.get_current_game()
    return game.identifier if game else None


def shown() -> set[str]:
    """Return the identifiers of the games that are shown."""
    return {game.identifier for game in gamelist.games}


def matching(query: str) -> set[str]:
    """Return the identifiers of the games that contain the query."""
    return {name for name in LIBRARY if query.lower() in name.lower()}


class TestBrowse(HeadlessTestCase):
    """Browse."""

    loaded = True

    def test_filter(self) -> Script:
        """Typing shows the games whose identifier contains it, ignoring case."""
        yield Hero()
        self.assertEqual(shown(), LIBRARY)
        yield text("PRINCE")
        self.assertEqual(gamelist.query, "PRINCE")
        self.assertEqual(shown(), matching("prince"))
        self.assertIn("Dizzy - Prince of the Yolkfolk", shown())
        self.assertIn(current(), shown())
        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_no_match(self) -> Script:
        """A filter that matches no game shows no games."""
        yield Hero()
        yield text("PRINCEq")
        self.assertEqual(shown(), set())
        self.assertIsNone(current())
        yield key(pg.K_BACKSPACE)
        self.assertEqual(shown(), LIBRARY)
        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_keep_filter(self) -> Script:
        """The filter stays while moving around, until Backspace erases it."""
        yield Hero()
        yield text("PRINCE of p")
        self.assertEqual(shown(), {"Prince of Persia", "Prince of Persia 2"})
        yield key(pg.K_RIGHT)
        self.assertEqual(gamelist.query, "PRINCE of p")
        yield key(pg.K_BACKSPACE)
        self.assertEqual(gamelist.query, "")
        self.assertEqual(shown(), LIBRARY)
        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_year(self) -> Script:
        """A year also shows the games from that year."""
        yield Hero()
        yield text("1989")
        from_1989 = {g.identifier for g in gamelist.all_games if g.year == "1989"}
        self.assertEqual(shown(), from_1989 | matching("1989"))
        self.assertIn("Sim City", shown())
        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_caret(self) -> Script:
        """A leading caret, typed with Shift-6, only matches the start."""
        hero = Hero()
        yield hero
        yield key(pg.K_6, pg.KMOD_SHIFT, "^")
        yield text("p")
        self.assertEqual(gamelist.query, "^p")
        self.assertEqual(shown(), {n for n in LIBRARY if n.lower().startswith("p")})
        self.assertEqual(hero.message, "^P")
        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_favorites(self) -> Script:
        """Ctrl-Enter adds favorites, and Tab shows all, favorites or others."""
        yield Hero()
        total = len(gamelist.games)
        yield key(pg.K_TAB)
        self.assertIsNone(gamelist.ready)
        yield text("prince")
        yield key(pg.K_RETURN, pg.KMOD_LCTRL)
        yield from self.wait_for(Hero)
        prince = current()
        yield key(pg.K_RIGHT)
        yield key(pg.K_RETURN, pg.KMOD_LCTRL)
        yield from self.wait_for(Hero)
        favorites = {prince, current()}
        self.assertEqual(favorites, set(self.files))
        yield key(pg.K_TAB)
        self.assertTrue(gamelist.ready)
        self.assertEqual(shown(), favorites)
        yield key(pg.K_BACKSPACE)
        yield key(pg.K_TAB)
        self.assertIs(gamelist.ready, False)  # noqa: FBT003
        self.assertEqual(len(gamelist.games), total - 2)
        yield key(pg.K_TAB)
        self.assertIsNone(gamelist.ready)
        self.assertEqual(len(gamelist.games), total)
        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_remove_favorite(self) -> Script:
        """Ctrl-Enter on a favorite removes it."""
        game = self.game("ready")
        gamelist.current_game = 0
        yield Hero()
        yield key(pg.K_RETURN, pg.KMOD_LCTRL)
        self.assertFalse(game.is_ready())
        self.assertEqual(self.trace, ["Hero"])
        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_key_repeat_pileup(self) -> Script:
        """Key repeats that pile up during slow frames are dropped with a beep."""
        speaker = bios.speaker
        start = self.enterContext(
            mock.patch.object(speaker, "start", wraps=speaker.start)
        )
        stop = self.enterContext(mock.patch.object(speaker, "stop", wraps=speaker.stop))
        grid = Grid()
        yield grid
        minus, release = key(pg.K_MINUS)
        self.assertTrue(pg.event.get_blocked(pg.TEXTINPUT))
        yield minus
        self.assertEqual(grid.cols, 3)
        start.assert_not_called()
        yield [minus] * 5
        self.assertEqual(grid.cols, 4)
        stop.reset_mock()
        yield [minus] * 5
        self.assertEqual(grid.cols, 5)
        self.assertEqual(start.call_count, 2)
        stop.assert_not_called()
        yield minus
        self.assertEqual(grid.cols, 6)
        stop.assert_called_once()
        yield [minus, minus, release]
        self.assertEqual(grid.cols, 6)
        self.assertEqual(start.call_count, 2)
        yield key(pg.K_MINUS)
        self.assertEqual(grid.cols, 7)
        self.assertIsNone((yield pg.event.Event(pg.QUIT)))
