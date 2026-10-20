"""Run the app headless and browse around."""

from pathlib import Path
from unittest import mock

import pygame as pg

import games as gd
from ialauncher import bios
from ialauncher.game import Game
from ialauncher.scenes import BLACK, WHITE
from ialauncher.scenes import browse as browse_scene
from ialauncher.scenes.browse import Browse
from ialauncher.scenes.download import Download
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
    """The title screens of the loaded gamelist."""

    def test_browse(self) -> Script:
        """Load the games, browse the title screens, and quit with Escape."""
        browse = yield from self.wait_for(Browse)
        gamelist = browse.gamelist
        self.assertTrue(gamelist.games, "no games with a title screen were loaded")
        start = gamelist.current_game
        following = (start + 1) % len(gamelist.games)

        yield key(pg.K_RIGHT)
        self.assertEqual(gamelist.current_game, following)
        yield key(pg.K_LEFT)
        self.assertEqual(gamelist.current_game, start)

        # In 1x1 mode, Down and Up are the same as Right and Left
        yield key(pg.K_DOWN)
        self.assertEqual(gamelist.current_game, following)
        yield key(pg.K_UP)
        self.assertEqual(gamelist.current_game, start)

        yield key(pg.K_MINUS)
        self.assertEqual(browse.cols, 3)
        pos = browse.pos
        yield key(pg.K_DOWN)
        self.assertEqual(browse.pos, pos + 3)
        self.assertEqual(gamelist.current_game, browse.pos % len(gamelist.games))
        yield key(pg.K_PLUS)
        self.assertEqual(browse.cols, 1)

        yield text("prince")
        self.assertEqual(gamelist.query, "prince")
        self.assertRegex(gamelist.get_current_game().identifier, "(?i)prince")
        yield key(pg.K_BACKSPACE)

        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_filter(self) -> Script:
        """Typing filters the games on a substring of their identifier."""
        browse = yield from self.wait_for(Browse)
        gamelist = browse.gamelist
        library = {
            entry.name
            for entry in Path(gd.__file__).parent.iterdir()
            if (entry / "metadata.ini").exists()
        }

        def shown() -> set[str]:
            return {game.identifier for game in gamelist.games}

        def matching(query: str) -> set[str]:
            return {name for name in library if query.lower() in name.lower()}

        # The filter matches anywhere in the identifier, ignoring case
        self.assertEqual(shown(), library)
        yield text("PRINCE")
        self.assertEqual(gamelist.query, "PRINCE")
        self.assertEqual(shown(), matching("prince"))
        self.assertIn("Dizzy - Prince of the Yolkfolk", shown())
        self.assertIn("Machiavelli the Prince", shown())
        self.assertIn(gamelist.get_current_game().identifier, shown())

        # A character that matches no game is rejected, and the filter stays
        yield text("q")
        self.assertEqual(gamelist.query, "PRINCE")
        self.assertEqual(shown(), matching("prince"))

        # Space adds to the filter
        yield text(" of p")
        self.assertEqual(gamelist.query, "PRINCE of p")
        self.assertEqual(shown(), {"Prince of Persia", "Prince of Persia 2"})

        # Moving around keeps the filter
        yield key(pg.K_RIGHT)
        yield key(pg.K_RIGHT)
        self.assertEqual(gamelist.query, "PRINCE of p")
        self.assertEqual(len(gamelist.games), 2)

        # Minus and plus zoom when they match no game
        yield text("-")
        self.assertEqual(browse.cols, 3)
        yield text("+")
        self.assertEqual(browse.cols, 1)
        self.assertEqual(gamelist.query, "PRINCE of p")

        # Backspace erases the entire filter
        yield key(pg.K_BACKSPACE)
        self.assertEqual(gamelist.query, "")
        self.assertEqual(shown(), library)

        # Without a filter, minus zooms, even though it matches games
        self.assertTrue(matching("-"))
        yield text("-")
        self.assertEqual(browse.cols, 3)
        self.assertEqual(gamelist.query, "")

        # Any character can be filtered on, if a game matches it
        yield text("&")
        self.assertEqual(gamelist.query, "&")
        self.assertEqual(shown(), matching("&"))
        self.assertIn("Apples & Oranges", shown())

        # Escape erases the filter, then switches the grid to 1x1, then quits
        self.assertEqual(browse.cols, 3)
        yield key(pg.K_ESCAPE)
        self.assertEqual(gamelist.query, "")
        self.assertEqual(shown(), library)
        self.assertEqual(browse.cols, 3)
        yield key(pg.K_ESCAPE)
        self.assertEqual(browse.cols, 1)
        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_filter_drawn(self) -> Script:
        """The filter is drawn in white on black, centered at the bottom."""
        browse = yield from self.wait_for(Browse)
        screen = browse.screen

        def assert_drawn(query: str) -> None:
            width, height = browse.font.size(query)
            box = pg.Rect(0, 0, width + 32, height + 16)
            box.midbottom = screen.get_rect().midbottom
            pixels = [
                screen.get_at((x, y))[:3]
                for x in range(box.left, box.right)
                for y in range(box.top, box.bottom)
            ]
            self.assertTrue(
                all(r == g == b for r, g, b in pixels), "not white on black"
            )
            self.assertTrue(WHITE in pixels, f"{query!r} is not drawn")
            corners = [box.topleft, (box.right - 1, box.bottom - 1)]
            self.assertEqual([screen.get_at(c)[:3] for c in corners], [BLACK, BLACK])

        # The filter is centered again whenever it changes
        yield text("Prince")
        assert_drawn("Prince")
        yield text(" of Persia")
        assert_drawn("Prince of Persia")
        yield key(pg.K_ESCAPE)
        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_no_downloads(self) -> Script:
        """Pressing Enter fails the test instead of downloading or starting a game."""
        yield from self.wait_for(Browse)
        with self.assertRaisesRegex(AssertionError, "tried to"):
            yield key(pg.K_RETURN)

    def test_key_repeat_pileup(self) -> Script:
        """Key repeats that pile up during slow frames are dropped with a beep."""
        speaker = bios.speaker
        start = self.enterContext(
            mock.patch.object(speaker, "start", wraps=speaker.start)
        )
        stop = self.enterContext(mock.patch.object(speaker, "stop", wraps=speaker.stop))
        browse = yield from self.wait_for(Browse)
        minus, release = key(pg.K_MINUS)

        # The text input of each repeat would pile up too, so it's blocked
        self.assertTrue(pg.event.get_blocked(pg.TEXTINPUT))

        # While the key is held, each repeat zooms out
        yield minus
        yield minus
        self.assertEqual(browse.cols, 5)
        start.assert_not_called()

        # When repeats pile up, all but the current one are dropped, and it
        # beeps for as long as they keep piling up
        yield [minus] * 5
        self.assertEqual(browse.cols, 7)
        stop.reset_mock()  # It was called while silent, which does nothing
        yield [minus] * 5
        self.assertEqual(browse.cols, 9)
        self.assertEqual(start.call_count, 2)
        stop.assert_not_called()

        # A repeat with no others queued behind it stops the beep
        yield minus
        self.assertEqual(browse.cols, 11)
        stop.assert_called_once()

        # Once the key is released, its queued repeats are dropped silently
        yield [minus, minus, release]
        self.assertEqual(browse.cols, 11)
        self.assertEqual(start.call_count, 2)

        # But a short press always counts, however slow the frame
        yield key(pg.K_MINUS)
        self.assertEqual(browse.cols, 13)
        yield key(pg.K_ESCAPE)
        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_key_tapping_pileup(self) -> Script:
        """Taps of a key that pile up during a slow frame are dropped with a beep."""
        speaker = bios.speaker
        start = self.enterContext(
            mock.patch.object(speaker, "start", wraps=speaker.start)
        )
        browse = yield from self.wait_for(Browse)
        yield key(pg.K_MINUS) * 4
        self.assertEqual(browse.cols, 3)
        start.assert_called_once()

        # A single tap still counts, without a beep
        yield key(pg.K_MINUS)
        self.assertEqual(browse.cols, 5)
        start.assert_called_once()
        yield key(pg.K_ESCAPE)
        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_quit_while_downloading(self) -> Script:
        """Closing the window during a download cancels it and quits the app."""
        thread = mock.Mock(progress=0.0, error=None)
        thread.is_alive.return_value = True  # The download never finishes

        def download(game: Game) -> None:
            game.download_thread = thread

        self.enterContext(mock.patch.object(Game, "is_ready", return_value=False))
        self.enterContext(mock.patch.object(Game, "download", download))
        yield from self.wait_for(Browse)
        yield key(pg.K_RETURN)
        yield from self.wait_for(Download)

        # Download runs inside Browse, which must quit too
        self.assertIsNone((yield pg.event.Event(pg.QUIT)))
        thread.cancel.assert_called_once()

    def test_ready_only(self) -> Script:
        """Tab cycles through all, ready and unready games; Ctrl-Enter adds/removes."""
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
        gamelist = browse.gamelist
        total = len(gamelist.games)

        def current() -> str:
            return gamelist.get_current_game().identifier

        # Without ready games, Tab does nothing
        yield key(pg.K_TAB)
        self.assertIsNone(gamelist.ready)
        self.assertEqual(len(gamelist.games), total)

        # Add two games, and show only those
        yield text("prince")
        yield key(pg.K_RETURN, mod=pg.KMOD_CTRL)
        prince = current()
        yield key(pg.K_RIGHT)
        yield key(pg.K_RETURN, mod=pg.KMOD_CTRL)
        self.assertEqual(ready, {prince, current()})
        yield key(pg.K_TAB)
        self.assertTrue(gamelist.ready)
        self.assertEqual(gamelist.query, "prince")  # Filters the ready games
        self.assertEqual(sorted(g.identifier for g in gamelist.games), sorted(ready))

        # Removing a game keeps it shown until the next arrow key
        yield key(pg.K_RETURN, mod=pg.KMOD_CTRL)
        self.assertEqual(len(ready), 1)
        self.assertEqual(len(gamelist.games), 2)
        yield key(pg.K_RIGHT)
        self.assertTrue(gamelist.ready)
        self.assertEqual([g.identifier for g in gamelist.games], list(ready))

        # Tab shows the unready games, all games, then the ready games again
        yield key(pg.K_BACKSPACE)
        yield key(pg.K_TAB)
        self.assertIs(gamelist.ready, False)  # noqa: FBT003
        self.assertEqual(len(gamelist.games), total - 1)
        self.assertNotIn(current(), ready)
        yield key(pg.K_TAB)
        self.assertIsNone(gamelist.ready)
        self.assertEqual(len(gamelist.games), total)
        yield key(pg.K_TAB)
        self.assertEqual(len(gamelist.games), 1)

        # Removing the last game keeps it shown too
        yield key(pg.K_RETURN, mod=pg.KMOD_CTRL)
        self.assertFalse(ready)
        self.assertEqual(len(gamelist.games), 1)
        yield key(pg.K_TAB)
        self.assertEqual(len(gamelist.games), total)

        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_one_emulator(self) -> Script:
        """Enter's key repeat and a running emulator don't start a game twice."""
        emulator = mock.Mock(is_alive=lambda: running)
        start = mock.Mock(return_value=emulator)
        self.enterContext(mock.patch.object(Game, "is_ready", return_value=True))
        self.enterContext(mock.patch.object(Game, "start", start))
        yield from self.wait_for(Browse)
        enter, release = key(pg.K_RETURN)

        # Holding Enter starts the game once, even after the emulator exits
        running = True
        for _ in range(3):
            yield enter
        self.assertEqual(start.call_count, 1)
        running = False
        yield enter
        self.assertEqual(start.call_count, 1)

        # Pressing Enter again doesn't start the game a second time
        running = True
        yield [release, *key(pg.K_RETURN)]
        self.assertEqual(start.call_count, 1)

        # But it starts the game again once the emulator has exited
        running = False
        yield key(pg.K_RETURN)
        self.assertEqual(start.call_count, 2)
        self.assertIsNone((yield key(pg.K_ESCAPE)))
