"""Every scene transition in the docstring of ialauncher.scenes."""

import inspect
import sys
import unittest
from unittest import mock

import pygame as pg

from ialauncher import options, scenes
from ialauncher.gamelist import gamelist
from ialauncher.scenes import snake
from ialauncher.scenes.browse import IDLE
from ialauncher.scenes.grid import Grid
from ialauncher.scenes.hero import ADVANCE, Hero
from ialauncher.scenes.loading import Loading
from ialauncher.scenes.starfield import Starfield
from ialauncher.scenes.stars import Stars

from .support import Events, HeadlessTestCase, Script, click, key


def collide(starfield: Starfield) -> Events:
    """Add a star that collides with the screen right away."""
    star = starfield.star(center=True)
    star.game, star.z = gamelist.games[1], 0
    starfield.stars.append(star)
    return None


def click_first(grid: Grid) -> Events:
    """Click the first game of the grid."""
    _, cell = next(grid.cells())
    return click(cell.center)


def zoom_to_snake(grid: Grid) -> Events:
    """Zoom out to one column short of Snake, and then one more."""
    grid.resize(snake.SNAKE_COLS - 1)
    return key(pg.K_MINUS)


def skip_intro(intro: snake.Intro) -> Events:
    """Let all tiles disappear at once."""
    intro.tiles.clear()
    return None


class TestLoading(HeadlessTestCase):
    """The transitions from Loading."""

    def test_loaded(self) -> Script:
        """Loading > Hero."""
        yield from self.expect(Loading())

    def test_escape(self) -> Script:
        """Loading > escape > quit."""
        yield from self.expect(Loading(), key(pg.K_ESCAPE))


class TestHero(HeadlessTestCase):
    """The transitions from Hero."""

    loaded = True

    def test_enter(self) -> Script:
        """Hero > enter > CRT > Download > Unzip > Play > CRT > Hero."""
        yield from self.expect(Hero(), key(pg.K_RETURN))

    def test_ctrl_enter(self) -> Script:
        """Hero > ctrl-enter > Download > Unzip > Hero."""
        yield from self.expect(Hero(), key(pg.K_RETURN, pg.KMOD_LCTRL))

    def test_space(self) -> Script:
        """Hero > space/ADVANCE > CRT > Unzip > Autoplay > CRT > Hero."""
        options.autoplay = 300
        yield from self.expect(Hero(), key(pg.K_SPACE))

    def test_space_without_autoplay(self) -> Script:
        """Hero > space/ADVANCE > CRT > CRT > Hero."""
        yield from self.expect(Hero(), key(pg.K_SPACE))

    def test_slideshow_without_autoplay(self) -> Script:
        """Hero > space/ADVANCE > CRT > CRT > Hero."""
        yield from self.expect(Hero(slideshow=True), pg.event.Event(ADVANCE))

    def test_space_not_autoplayable(self) -> Script:
        """Hero > space/ADVANCE > CRT > CRT > Hero."""
        options.autoplay = 300
        self.game().autoplayable = False
        gamelist.current_game = 0
        yield from self.expect(Hero(), key(pg.K_SPACE))

    def test_slideshow(self) -> Script:
        """Hero > space/ADVANCE > CRT > Unzip > Autoplay > CRT > Hero."""
        self.qualify(gamelist.get_current_game())
        yield from self.expect(Hero(slideshow=True), pg.event.Event(ADVANCE))

    def test_after_screensaver(self) -> Script:
        """Hero > CRT > Unzip > Autoplay > Starfield/Stars."""
        options.slideshow = 0
        self.qualify(gamelist.get_current_game())
        yield from self.expect(Hero(screensaver=True))

    def test_idle(self) -> Script:
        """Hero > IDLE > Starfield/Stars."""
        yield from self.expect(Hero(), pg.event.Event(IDLE))

    def test_minus(self) -> Script:
        """Hero > minus > Grid."""
        yield from self.expect(Hero(), key(pg.K_MINUS))

    def test_metadata(self) -> Script:
        """Hero > METADATA > Hero."""
        yield from self.expect(Hero(), self.change_metadata)

    def test_escape(self) -> Script:
        """Hero > escape > quit."""
        yield from self.expect(Hero(), key(pg.K_ESCAPE))


class TestGrid(HeadlessTestCase):
    """The transitions from Grid."""

    loaded = True

    def test_click(self) -> Script:
        """Grid > click > Download > Unzip > Play > Grid."""
        yield from self.expect(Grid(), click_first)

    def test_ctrl_click(self) -> Script:
        """Grid > ctrl-click > Download > Unzip > Grid."""
        self.enterContext(mock.patch.object(pg.key, "get_mods", lambda: pg.KMOD_LCTRL))
        yield from self.expect(Grid(), click_first)

    def test_space(self) -> Script:
        """Grid > space > Hero."""
        yield from self.expect(Grid(), key(pg.K_SPACE))

    def test_escape(self) -> Script:
        """Grid > escape/plus/METADATA > Hero."""
        yield from self.expect(Grid(), key(pg.K_ESCAPE))

    def test_plus(self) -> Script:
        """Grid > escape/plus/METADATA > Hero."""
        yield from self.expect(Grid(), key(pg.K_PLUS))

    def test_metadata(self) -> Script:
        """Grid > escape/plus/METADATA > Hero."""
        yield from self.expect(Grid(), self.change_metadata)

    def test_zoom(self) -> Script:
        """Grid > zoom > Intro > Snake > Grid."""
        tile = pg.Surface((1, 1))
        self.enterContext(mock.patch.object(snake.Intro, "title", return_value=tile))
        yield from self.expect(
            Grid(),
            zoom_to_snake,
            {snake.Intro: skip_intro, snake.Snake: key(pg.K_ESCAPE)},
        )

    def test_idle(self) -> Script:
        """Grid > IDLE > Starfield/Stars."""
        yield from self.expect(Grid(), pg.event.Event(IDLE))


class TestScreensaver(HeadlessTestCase):
    """The transitions from Starfield and Stars."""

    loaded = True

    def test_collision(self) -> Script:
        """Starfield > collision > Hero."""
        yield from self.expect(Starfield(Hero()), collide)

    def test_escape_to_hero(self) -> Script:
        """Starfield > escape > Hero/Grid."""
        yield from self.expect(Starfield(Hero()), key(pg.K_ESCAPE))

    def test_escape_to_grid(self) -> Script:
        """Starfield > escape > Hero/Grid."""
        yield from self.expect(Starfield(Grid()), key(pg.K_ESCAPE))

    def test_exit(self) -> Script:
        """Stars > exit > Hero."""
        yield from self.expect(Stars(Hero()), lambda _: self.exit_stars())

    def test_cant_start(self) -> Script:
        """Stars > Starfield."""
        self.stars_start = False
        yield from self.expect(Stars(Hero()))


class TestAny(HeadlessTestCase):
    """The transition from any scene."""

    loaded = True

    def test_close_hero(self) -> Script:
        """Any > close > quit."""
        yield from self.expect(Hero(), pg.event.Event(pg.QUIT))

    def test_close_grid(self) -> Script:
        """Any > close > quit."""
        yield from self.expect(Grid(), pg.event.Event(pg.QUIT))


class TestDocstring(unittest.TestCase):
    """The docstring of ialauncher.scenes."""

    def test_all_tested(self) -> None:
        """Every transition in the docstring has a test, and every test is in it."""
        documented = {
            line.removeprefix("- ")
            for line in (scenes.__doc__ or "").splitlines()
            if line.startswith("- ")
        }
        tested = {
            (method.__doc__ or "").removesuffix(".")
            for _, case in inspect.getmembers(sys.modules[__name__], inspect.isclass)
            if issubclass(case, HeadlessTestCase) and case is not HeadlessTestCase
            for name, method in vars(case).items()
            if name.startswith("test_")
        }
        self.assertEqual(tested, documented)
