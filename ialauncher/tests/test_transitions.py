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


def zoom_to_stars(grid: Grid) -> Events:
    """Zoom out to the most columns possible, and then try one more."""
    grid.resize(10_000)
    return key(pg.K_MINUS)


def skip_intro(intro: snake.Intro) -> Events:
    """Let all tiles disappear at once."""
    intro.tiles.clear()
    return None


class TestLoading(HeadlessTestCase):
    """The transitions from Loading."""

    def test_loaded(self) -> Script:
        """Loading > Dissolve > Hero."""
        yield from self.expect(Loading())

    def test_escape(self) -> Script:
        """Loading > escape > quit."""
        yield from self.expect(Loading(), key(pg.K_ESCAPE))


class TestHero(HeadlessTestCase):
    """The transitions from Hero."""

    loaded = True

    def test_enter(self) -> Script:
        """Hero > enter > CRToff > Download > Unzip > Play > CRTon > Hero."""
        yield from self.expect(Hero(), key(pg.K_RETURN))

    def test_ctrl_enter(self) -> Script:
        """Hero > ctrl-enter > Download > Unzip > Hero."""
        yield from self.expect(Hero(), key(pg.K_RETURN, pg.KMOD_LCTRL))

    def test_shift_a(self) -> Script:
        """Hero > shift-A > CRToff > Download > Unzip > Record > CRTon > Hero."""
        yield from self.expect(Hero(), key(pg.K_a, pg.KMOD_LSHIFT, "A"))

    def test_ctrl_a(self) -> Script:
        """Hero > ctrl-A > CRToff > Download > Unzip > Autoplay > CRTon > Hero."""
        yield from self.expect(Hero(), key(pg.K_a, pg.KMOD_LCTRL, "\x01"))

    def test_space(self) -> Script:
        """Hero > space > CRToff > Unzip > Autoplay > CRTon > Hero."""
        self.qualify(gamelist.get_current_game())
        yield from self.expect(Hero(), key(pg.K_SPACE))

    def test_space_without_autoplay(self) -> Script:
        """Hero > space > Dissolve > Hero."""
        yield from self.expect(Hero(), key(pg.K_SPACE))

    def test_slideshow_without_autoplay(self) -> Script:
        """Hero > ADVANCE > Dissolve > Hero."""
        yield from self.expect(Hero(slideshow=True), pg.event.Event(ADVANCE))

    def test_space_not_autoplayable(self) -> Script:
        """Hero > space > Dissolve > Hero."""
        options.autoplay = True
        self.game().autoplay = 0
        gamelist.current_game = 0
        yield from self.expect(Hero(), key(pg.K_SPACE))

    def test_slideshow_not_autoplayable(self) -> Script:
        """Hero > ADVANCE > Dissolve > Hero."""
        options.autoplay = True
        self.game().autoplay = 0
        gamelist.current_game = 0
        yield from self.expect(Hero(slideshow=True), pg.event.Event(ADVANCE))

    def test_slideshow(self) -> Script:
        """Hero > ADVANCE > CRToff > Unzip > Autoplay > CRTon > Hero."""
        self.qualify(gamelist.get_current_game())
        yield from self.expect(Hero(slideshow=True), pg.event.Event(ADVANCE))

    def test_after_screensaver(self) -> Script:
        """Hero > CRToff > Unzip > Autoplay > Starfield."""
        options.slideshow = 0
        self.qualify(gamelist.get_current_game())
        yield from self.expect(Hero(screensaver=True))

    def test_idle(self) -> Script:
        """Hero > IDLE > Starfield."""
        yield from self.expect(Hero(), pg.event.Event(IDLE))

    def test_delete(self) -> Script:
        """Hero > delete > Starfield."""
        yield from self.expect(Hero(), key(pg.K_DELETE))

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
        """Grid > escape > Hero."""
        yield from self.expect(Grid(), key(pg.K_ESCAPE))

    def test_plus(self) -> Script:
        """Grid > plus > Hero."""
        yield from self.expect(Grid(), key(pg.K_PLUS))

    def test_metadata(self) -> Script:
        """Grid > METADATA > Hero."""
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

    def test_zoom_out(self) -> Script:
        """Grid > zoom out > Stars > Grid."""
        yield from self.expect(Grid(), zoom_to_stars, {Stars: self.exit_stars})

    def test_idle(self) -> Script:
        """Grid > IDLE > Starfield."""
        yield from self.expect(Grid(), pg.event.Event(IDLE))

    def test_delete(self) -> Script:
        """Grid > delete > Starfield."""
        yield from self.expect(Grid(), key(pg.K_DELETE))


class TestScreensaver(HeadlessTestCase):
    """The transitions from Starfield and Stars."""

    loaded = True

    def test_collision(self) -> Script:
        """Starfield > collision > Hero."""
        yield from self.expect(Starfield(Hero()), collide)

    def test_escape_to_hero(self) -> Script:
        """Starfield > escape > Hero."""
        yield from self.expect(Starfield(Hero()), key(pg.K_ESCAPE))

    def test_escape_to_grid(self) -> Script:
        """Starfield > escape > Grid."""
        yield from self.expect(Starfield(Grid()), key(pg.K_ESCAPE))

    def test_exit(self) -> Script:
        """Stars > exit > Grid."""
        yield from self.expect(Stars(Grid()), self.exit_stars)


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
