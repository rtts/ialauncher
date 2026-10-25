"""Snake, hidden in the grid."""

import random
from collections import deque
from typing import TYPE_CHECKING, override

import pygame as pg

from ialauncher.bios import speaker
from ialauncher.cga import cga
from ialauncher.engine import NextScene
from ialauncher.gamelist import gamelist
from ialauncher.utils import grid_margin, sharp_scale

from . import BLACK, Scene

if TYPE_CHECKING:
    from .grid import Grid

DIRECTIONS = {
    pg.K_RIGHT: (1, 0),
    pg.K_LEFT: (-1, 0),
    pg.K_DOWN: (0, 1),
    pg.K_UP: (0, -1),
}
SNAKE_COLS = 40
FPS = 8
START_LENGTH = 8


class Snake(Scene):
    """Yes, the game."""

    def __init__(self, referrer: "Grid") -> None:
        """Store scene to hand back to."""
        super().__init__()
        self.referrer = referrer

    @override
    def run(self, screen: pg.Surface) -> NextScene:
        """Lay out the playing field and start with snake in the middle."""
        width, height = screen.get_size()
        self.cols = self.referrer.cols
        self.rows = round(height / self.referrer.row_height)
        cell_width, cell_height = width // self.cols, height // self.rows
        margin = grid_margin(cell_width)
        self.tile_size = cell_width - margin, cell_height - margin

        # The body is a list of cells composed of title screens.
        x, y = self.cols // 2, self.rows // 2
        self.body = deque((x - i, y) for i in range(START_LENGTH))
        self.images = deque(self.random_title() for _ in range(START_LENGTH))
        self.direction = DIRECTIONS[pg.K_RIGHT]
        self.turns: deque[tuple[int, int]] = deque()
        self.game_over = False
        self.place_food()
        speaker.blip()
        return super().run(screen)

    def random_title(self) -> pg.Surface:
        """Return the title screen of a random game, scaled to the tile size."""
        game = random.choice(gamelist.games)  # noqa: S311
        title = game.get_titlescreen(self.tile_size)
        if title is None:
            title = pg.image.load(game.titlescreen)
        return sharp_scale(cga.apply(title), self.tile_size)

    def place_food(self) -> bool:
        """Put a random title screen in a random empty cell, away from the edges."""
        occupied = set(self.body)
        free = [
            (x, y)
            for y in range(1, self.rows - 1)
            for x in range(1, self.cols - 1)
            if (x, y) not in occupied
        ]
        if not free:
            return False
        self.food = random.choice(free)  # noqa: S311
        self.food_image = self.random_title()
        return True

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Queue turns with the arrow keys, or hand back to the grid on Escape."""
        if event.type != pg.KEYDOWN:
            return None
        if event.key == pg.K_ESCAPE:
            return self.referrer
        if event.key in DIRECTIONS:
            self.turns.append(DIRECTIONS[event.key])
        return None

    def step(self) -> bool:
        """Move the snake one cell; return False when it dies."""
        while self.turns:
            dx, dy = self.turns.popleft()
            if self.direction not in {(dx, dy), (-dx, -dy)}:
                self.direction = dx, dy
                break
        if not self.advance(grow=False):
            return False
        if self.body[0] == self.food:
            self.images.appendleft(self.food_image)
            if not self.advance(grow=True):
                return False
            speaker.blip()
            return self.place_food()
        return True

    def advance(self, *, grow: bool) -> bool:
        """Add a cell in front of the head; return False on collision.

        Unless growing, the tail moves out of the way first.
        """
        dx, dy = self.direction
        x, y = self.body[0]
        head = x + dx, y + dy
        if not (0 <= head[0] < self.cols and 0 <= head[1] < self.rows):
            return False
        if not grow:
            self.body.pop()
        if head in self.body:
            return False
        self.body.appendleft(head)
        return True

    def cell(self, pos: tuple[int, int]) -> pg.Rect:
        """Return the tile rectangle centered in the cell at pos."""
        x, y = pos
        width, height = self.screen.get_size()
        tile = pg.Rect((0, 0), self.tile_size)
        tile.center = (
            (2 * x + 1) * width // (2 * self.cols),
            (2 * y + 1) * height // (2 * self.rows),
        )
        return tile

    @override
    def get_events(self) -> list[pg.event.Event]:
        """Run at FPS frames per second."""
        self.clock.tick(FPS)
        return pg.event.get()

    @override
    def update(self, screen: pg.Surface) -> NextScene:
        """Move snake and draw food, or beep for a frame when it dies."""
        if self.game_over:
            speaker.stop()
            return self.referrer
        if not self.step():
            speaker.start()
            self.game_over = True
            return None
        screen.fill(BLACK)
        screen.blit(self.food_image, self.cell(self.food))
        screen.fblits(
            (image, self.cell(pos))
            for image, pos in zip(self.images, self.body, strict=True)
        )
        return None
