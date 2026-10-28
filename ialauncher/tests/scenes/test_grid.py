"""Grid: all games in a grid, with a menu."""

from unittest import mock

import pygame as pg

from ialauncher import engine
from ialauncher.gamelist import gamelist
from ialauncher.scenes.grid import Grid
from ialauncher.tests.support import HeadlessTestCase, Script, click, key


class TestGrid(HeadlessTestCase):
    """Grid."""

    loaded = True

    def test_zoom(self) -> Script:
        """Minus shows more columns, Plus fewer."""
        grid = Grid()
        yield grid
        self.assertEqual(grid.cols, 2)
        yield key(pg.K_MINUS)
        self.assertEqual(grid.cols, 3)
        yield key(pg.K_PLUS)
        self.assertEqual(grid.cols, 2)
        self.assertIsNone((yield pg.event.Event(pg.QUIT)))

    def test_select(self) -> Script:
        """Pointing at a game selects it."""
        grid = Grid()
        yield grid
        pos, cell = list(grid.cells())[1]
        yield pg.event.Event(pg.MOUSEMOTION, pos=cell.center, rel=(0, 0), buttons=())
        self.assertEqual(gamelist.current_game, pos % len(gamelist.games))
        self.assertIsNone((yield pg.event.Event(pg.QUIT)))

    def test_menu(self) -> Script:
        """Right-clicking opens the menu, Escape closes it, and Enter plays."""
        grid = Grid()
        yield grid
        _, cell = next(grid.cells())
        yield click(cell.center, pg.BUTTON_RIGHT)
        self.assertIsNotNone(grid.menu)
        yield key(pg.K_ESCAPE)
        self.assertIsNone(grid.menu)
        yield click(cell.center, pg.BUTTON_RIGHT)
        yield key(pg.K_RETURN)
        self.assertIs((yield from self.wait_for(Grid)), grid)
        self.assertEqual(len(self.emulators), 1)
        self.assertEqual(self.trace, ["Grid", "Download", "Unzip", "Play", "Grid"])
        self.assertIsNone((yield pg.event.Event(pg.QUIT)))

    def test_layout(self) -> Script:
        """The grid is laid out again when the window changes size."""
        grid = Grid()
        yield grid
        self.enterContext(mock.patch.object(engine, "window_size", [800, 500]))
        engine.set_mode(fullscreen=False)
        yield None
        self.assertEqual(grid.layout_size, (800, 500))
        self.assertIsNone((yield pg.event.Event(pg.QUIT)))
