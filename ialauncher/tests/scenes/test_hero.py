"""Hero: a single title screen, with the slideshow."""

from unittest import mock

import pygame as pg

from ialauncher import options
from ialauncher.gamelist import gamelist
from ialauncher.scenes.grid import Grid
from ialauncher.scenes.hero import ADVANCE, Hero
from ialauncher.scenes.play import Autoplay, Play
from ialauncher.tests.support import HeadlessTestCase, Script, key, text


class TestHero(HeadlessTestCase):
    """Hero."""

    loaded = True

    def test_arrows(self) -> Script:
        """Right and Down show the next game, Left and Up the previous one."""
        yield Hero()
        start = gamelist.current_game
        following = (start + 1) % len(gamelist.games)
        for arrow, current in (
            (pg.K_RIGHT, following),
            (pg.K_LEFT, start),
            (pg.K_DOWN, following),
            (pg.K_UP, start),
        ):
            yield key(arrow)
            self.assertEqual(gamelist.current_game, current)
        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_typed_space(self) -> Script:
        """A space typed into the filter only types a space."""
        hero = Hero()
        yield hero
        yield text("prince of p")
        self.assertEqual(gamelist.query, "prince of p")
        self.assertFalse(hero.slideshow_running)
        self.assertEqual(self.trace, ["Hero"])
        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_slideshow_keys(self) -> Script:
        """Only keys that do something stop the slideshow, but not Tab or Backspace."""
        hero = Hero(slideshow=True)
        yield hero
        for k in (pg.K_TAB, pg.K_BACKSPACE, pg.K_LGUI, pg.K_RGUI, pg.K_F15):
            yield key(k)
        yield key(pg.K_PLUS, unicode="+")
        self.assertTrue(hero.slideshow_running)
        yield key(pg.K_RIGHT)
        self.assertFalse(hero.slideshow_running)
        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_not_autoplayable(self) -> Script:
        """Space on a game that never autoplays dissolves into the next game."""
        options.autoplay = True
        game = self.game("downloaded")
        game.autoplay = 0
        gamelist.current_game = 0
        hero = Hero()
        yield hero
        yield key(pg.K_SPACE)
        self.assertIs((yield from self.wait_for(Hero)), hero)
        self.assertEqual(self.trace, ["Hero", "Dissolve", "Hero"])
        self.assertEqual(self.unzips, [])
        self.assertIsNot(gamelist.get_current_game(), game)
        self.assertTrue(hero.slideshow_running)
        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_without_autoplay(self) -> Script:
        """Without autoplay, the slideshow dissolves into the next game."""
        game = self.game("downloaded")
        gamelist.current_game = 0
        yield Hero()
        yield key(pg.K_SPACE)
        yield from self.wait_for(Hero)
        self.assertEqual(self.trace, ["Hero", "Dissolve", "Hero"])
        self.assertIsNot(gamelist.get_current_game(), game)
        self.assertFalse(game.is_ready())
        self.assertEqual(self.unzips, [])
        self.assertEqual(self.emulators, [])
        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_not_downloaded(self) -> Script:
        """Space on an autoplayable game that isn't downloaded dissolves."""
        game = self.qualify(gamelist.get_current_game(), state="missing")
        yield Hero()
        yield key(pg.K_SPACE)
        yield from self.wait_for(Hero)
        self.assertEqual(self.trace, ["Hero", "Dissolve", "Hero"])
        self.assertIsNot(gamelist.get_current_game(), game)
        self.assertEqual(self.unzips, [])
        self.assertEqual(self.emulators, [])
        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_autoplay(self) -> Script:
        """The slideshow unzips and plays the game, and then shows the next one."""
        game = self.qualify(gamelist.get_current_game())
        yield Hero()
        yield key(pg.K_SPACE)
        yield from self.wait_for(Hero)
        self.assertEqual(len(self.unzips), 1)
        self.assertTrue(game.is_ready())
        self.assertIs(self.emulators[0].game, game)
        self.assertIsNot(gamelist.get_current_game(), game)
        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_ctrl_r(self) -> Script:
        """Ctrl-R plays the game, and saves how long it ran as autoplay."""
        game = self.qualify(gamelist.get_current_game())
        game.autoplay = 0
        yield Hero()
        yield key(pg.K_r, pg.KMOD_LCTRL, "\x12")
        yield from self.wait_for(Hero)
        self.assertIs(self.emulators[0].game, game)
        self.assertEqual(self.saved, [(game, "autoplay", "0")])
        self.assertIs(gamelist.get_current_game(), game)
        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_ctrl_shift_r(self) -> Script:
        """Ctrl-Shift-R resets the game before recording it."""
        game = self.qualify(gamelist.get_current_game(), "ready")
        # Resetting deletes the unzipped game, but keeps the download.
        self.enterContext(
            mock.patch.object(
                type(game),
                "reset",
                lambda _: self.files.update({game.identifier: "downloaded"}),
            )
        )
        yield Hero()
        yield key(pg.K_r, pg.KMOD_LCTRL | pg.KMOD_LSHIFT, "\x12")
        yield from self.wait_for(Hero)
        self.assertEqual(len(self.unzips), 1)
        self.assertIs(self.emulators[0].game, game)
        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_ctrl_a(self) -> Script:
        """Ctrl-A autoplays the game for its seconds, even without --autoplay."""
        self.keep_running = True
        game = self.qualify(gamelist.get_current_game())
        game.autoplay = 42
        options.autoplay = False
        yield Hero()
        yield key(pg.K_a, pg.KMOD_LCTRL, "\x01")
        autoplay = yield from self.wait_for(Autoplay)
        yield None
        self.assertIs(self.emulators[0].game, game)
        remaining = autoplay.deadline - pg.time.get_ticks()
        self.assertGreater(remaining, 41_000)
        self.assertLessEqual(remaining, 42_000)
        autoplay.deadline = 0
        yield from self.wait_for(Hero)
        self.assertTrue(self.emulators[0].stopped)
        self.assertEqual(self.saved, [])
        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_after_screensaver(self) -> Script:
        """After the screensaver, a keystroke cancels autoplaying the game."""
        self.qualify(gamelist.get_current_game())
        hero = Hero(screensaver=True)
        yield hero
        self.assertTrue(hero.after_screensaver)
        yield key(pg.K_RIGHT)
        self.assertFalse(hero.after_screensaver)
        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_after_screensaver_unqualified(self) -> Script:
        """After the screensaver, a game that doesn't qualify isn't autoplayed."""
        hero = Hero(screensaver=True)
        yield hero
        self.assertFalse(hero.after_screensaver)
        self.assertIsNone((yield key(pg.K_ESCAPE)))

    def test_timer(self) -> Script:
        """The slideshow timer stops when Hero does."""
        set_timer = self.enterContext(
            mock.patch.object(pg.time, "set_timer", wraps=pg.time.set_timer)
        )
        self.enterContext(mock.patch.object(pg.key, "get_mods", lambda: pg.KMOD_LCTRL))
        yield Hero(slideshow=True)
        yield pg.event.Event(pg.MOUSEWHEEL, x=0, y=-1, flipped=False)
        yield from self.wait_for(Grid)
        timers = [call.args for call in set_timer.call_args_list]
        self.assertEqual([t for t in timers if t[0] == ADVANCE][-1], (ADVANCE, 0))
        self.assertIsNone((yield pg.event.Event(pg.QUIT)))

    def test_one_emulator(self) -> Script:
        """Enter is ignored while the game runs, and starts it again after."""
        self.keep_running = True
        self.game("ready")
        gamelist.current_game = 0
        yield Hero()
        yield key(pg.K_RETURN)
        yield from self.wait_for(Play)
        yield key(pg.K_RETURN)
        self.assertEqual(len(self.emulators), 1)
        self.emulators[0].exit()
        yield from self.wait_for(Hero)
        yield key(pg.K_RETURN)
        yield from self.wait_for(Play)
        self.assertEqual(len(self.emulators), 2)
        self.emulators[1].exit()
        yield from self.wait_for(Hero)
        self.assertIsNone((yield key(pg.K_ESCAPE)))
