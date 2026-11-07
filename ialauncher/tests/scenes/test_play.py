"""Play and Autoplay: playing a game, by hand or for a while."""

import pygame as pg

from ialauncher.scenes import BLACK
from ialauncher.scenes.play import Autoplay, Play
from ialauncher.scenes.record import Record
from ialauncher.tests.support import End, HeadlessTestCase, Script, key, screen


class TestPlay(HeadlessTestCase):
    """Play."""

    loaded = True

    def test_play(self) -> Script:
        """The screen is black until the game exits."""
        self.keep_running = True
        yield Play(self.game("ready"), End())
        self.assertIsInstance((yield key(pg.K_RETURN)), Play)
        self.assertEqual(screen().get_at((0, 0)), BLACK)
        self.assertEqual(len(self.emulators), 1)
        self.emulators[0].exit()
        yield from self.wait_until_quit()
        self.assertEqual(self.trace, ["Play", "End"])

    def test_not_ready(self) -> Script:
        """A game that isn't ready continues right away, without playing."""
        yield Play(self.game("downloaded"), End())
        yield from self.wait_until_quit()
        self.assertEqual(self.emulators, [])
        self.assertEqual(self.trace, ["Play", "End"])

    def test_alongside(self) -> Script:
        """Without waiting, the game keeps running after Play continues."""
        self.keep_running = True
        yield Play(self.game("ready"), End(), wait=False)
        yield from self.wait_until_quit()
        self.assertTrue(self.emulators[0].is_alive())
        self.assertEqual(self.trace, ["Play", "End"])

    def test_error(self) -> Script:
        """A game that fails shows the error."""
        self.keep_running = True
        yield Play(self.game("ready"), End())
        self.emulators[0].exit("Illegal function call")
        yield from self.wait_until_quit()
        self.assertEqual(self.errors, ["Illegal function call"])


class TestAutoplay(HeadlessTestCase):
    """Autoplay."""

    loaded = True

    def test_qualifies(self) -> None:
        """Only a downloaded DOSBox game with a start command and time autoplays."""
        game = self.qualify(self.game())
        self.assertTrue(Autoplay.qualifies(game))
        self.qualify(game).autoplay = 0
        self.assertFalse(Autoplay.qualifies(game))
        self.qualify(game).engine = "scummvm"
        self.assertFalse(Autoplay.qualifies(game))
        self.qualify(game).emulator_start = None
        self.assertFalse(Autoplay.qualifies(game))
        self.qualify(game, "missing")
        self.assertFalse(Autoplay.qualifies(game))

    def test_skip(self) -> Script:
        """A game that doesn't qualify continues right away."""
        game = self.qualify(self.game(), "ready")
        game.autoplay = 0
        yield Autoplay(game, End())
        yield from self.wait_until_quit()
        self.assertEqual(self.emulators, [])
        self.assertEqual(self.trace, ["Autoplay", "End"])

    def test_time_up(self) -> Script:
        """The game stops when time is up, and Autoplay continues."""
        self.keep_running = True
        autoplay = Autoplay(self.qualify(self.game(), "ready"), End())
        yield autoplay
        remaining = autoplay.deadline - pg.time.get_ticks()
        self.assertGreater(remaining, 299_000)
        self.assertIsInstance((yield key(pg.K_ESCAPE)), Autoplay)
        autoplay.deadline = 0
        yield from self.wait_until_quit()
        self.assertTrue(self.emulators[0].stopped)
        self.assertEqual(self.trace, ["Autoplay", "End"])

    def test_own_time(self) -> Script:
        """Each game plays for exactly its own autoplay seconds."""
        self.keep_running = True
        game = self.qualify(self.game(), "ready")
        game.autoplay = 42
        autoplay = Autoplay(game, End())
        yield autoplay
        remaining = autoplay.deadline - pg.time.get_ticks()
        self.assertGreater(remaining, 41_000)
        self.assertLessEqual(remaining, 42_000)
        autoplay.deadline = 0
        yield from self.wait_until_quit()

    def test_error(self) -> Script:
        """A game that fails continues without showing the error."""
        self.keep_running = True
        yield Autoplay(self.qualify(self.game(), "ready"), End())
        self.emulators[0].exit("Illegal function call")
        yield from self.wait_until_quit()
        self.assertEqual(self.errors, [])
        self.assertEqual(self.trace, ["Autoplay", "End"])


class TestRecord(HeadlessTestCase):
    """Record."""

    loaded = True

    def test_record(self) -> Script:
        """When the game exits, its rounded running time is saved as autoplay."""
        self.keep_running = True
        game = self.game("ready")
        record = Record(game, End())
        yield record
        self.assertEqual(self.saved, [])
        record.started -= 41.6
        self.emulators[0].exit()
        yield from self.wait_until_quit()
        self.assertEqual(game.autoplay, 42)
        self.assertEqual(self.saved, [(game, "autoplay", "42")])
        self.assertEqual(self.trace, ["Record", "End"])

    def test_not_ready(self) -> Script:
        """A game that isn't ready continues right away, without saving."""
        game = self.game("downloaded")
        autoplay = game.autoplay
        yield Record(game, End())
        yield from self.wait_until_quit()
        self.assertEqual(self.emulators, [])
        self.assertEqual(self.saved, [])
        self.assertEqual(game.autoplay, autoplay)
