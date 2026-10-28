"""Intro and Snake: the game hidden in the grid."""

import pygame as pg

from ialauncher.scenes import snake
from ialauncher.scenes.grid import Grid
from ialauncher.tests.support import HeadlessTestCase, Script, key


class TestSnake(HeadlessTestCase):
    """Intro and Snake."""

    loaded = True

    def start(self) -> Script:
        """Zoom the grid out to Snake."""
        grid = Grid()
        yield grid
        grid.resize(snake.SNAKE_COLS - 1)
        yield key(pg.K_MINUS)

    def test_intro(self) -> Script:
        """The tiles disappear two by two, and then Snake starts."""
        yield from self.start()
        intro = yield from self.wait_for(snake.Intro)
        tiles = len(intro.tiles)
        yield None
        self.assertEqual(len(intro.tiles), tiles - 2)
        game = yield from self.wait_for(snake.Snake)
        self.assertEqual((game.cols, game.rows), (intro.cols, intro.rows))
        self.assertIsNone((yield pg.event.Event(pg.QUIT)))

    def test_take_over(self) -> Script:
        """An arrow key takes over from the AI."""
        yield from self.start()
        game = yield from self.wait_for(snake.Snake)
        self.assertTrue(game.ai)
        yield key(pg.K_UP)
        self.assertFalse(game.ai)
        self.assertIsNone((yield pg.event.Event(pg.QUIT)))

    def test_game_over(self) -> Script:
        """After game over, the grid is back."""
        yield from self.start()
        game = yield from self.wait_for(snake.Snake)
        game.game_over = True
        yield from self.wait_for(Grid)
        self.assertEqual(self.trace, ["Grid", "Intro", "Snake", "Grid"])
        self.assertIsNone((yield pg.event.Event(pg.QUIT)))
