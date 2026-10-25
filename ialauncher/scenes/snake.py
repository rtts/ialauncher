"""Snake, hidden in the grid."""

import random
from collections import deque
from collections.abc import Iterator
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

type Cell = tuple[int, int]

DIRECTIONS = {
    pg.K_RIGHT: (1, 0),
    pg.K_LEFT: (-1, 0),
    pg.K_DOWN: (0, 1),
    pg.K_UP: (0, -1),
}
SNAKE_COLS = 40
FPS = 16
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
        self.turns: deque[Cell] = deque()
        self.ai = True
        self.plan: deque[Cell] = deque()
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
        random.shuffle(free)
        for self.food in free:
            if self.keeps_tail([]):
                break
        self.food_image = self.random_title()
        return True

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Take over from the AI with the arrow keys, or hand back on Escape."""
        if event.type != pg.KEYDOWN:
            return None
        if event.key == pg.K_ESCAPE:
            return self.referrer
        if event.key in DIRECTIONS:
            self.ai = False
            self.turns.append(DIRECTIONS[event.key])
        return None

    def step(self) -> bool:
        """Move the snake one cell; return False when it dies."""
        if self.ai:
            self.direction = self.think()
        while self.turns:
            dx, dy = self.turns.popleft()
            if self.direction not in {(dx, dy), (-dx, -dy)}:
                self.direction = dx, dy
                break
        length = len(self.body)
        if not self.move(self.body, self.direction):
            return False
        if len(self.body) > length:
            self.images.appendleft(self.food_image)
            speaker.blip()
            return self.place_food()
        return True

    def move(self, body: deque[Cell], direction: Cell) -> bool:
        """Move the body, one cell further when eating; return False on collision."""
        if not self.advance(body, direction, grow=False):
            return False
        if body[0] == self.food:
            return self.advance(body, direction, grow=True)
        return True

    def advance(self, body: deque[Cell], direction: Cell, *, grow: bool) -> bool:
        """Add a cell in front of the head; return False on collision.

        Unless growing, the tail moves out of the way first.
        """
        dx, dy = direction
        x, y = body[0]
        head = x + dx, y + dy
        if not self.on_field(head):
            return False
        if not grow:
            body.pop()
        if head in body:
            return False
        body.appendleft(head)
        return True

    def on_field(self, pos: Cell) -> bool:
        """Return whether pos is on the playing field."""
        x, y = pos
        return 0 <= x < self.cols and 0 <= y < self.rows

    def cell(self, pos: Cell) -> pg.Rect:
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

    def think(self) -> Cell:
        """Decide which way to go by following these rules.

        1. Keep the tail within reach: never move where the head can no
           longer find a clear path to the tail.
        2. Go towards the food along the shortest path that keeps the tail
           within reach once there, and stick to that plan.
        3. Without such a path, wander randomly, keeping the tail within
           reach.

        The food helps by appearing where it doesn't cut off the tail,
        whenever there is such a place.
        """
        if not self.plan:
            self.plan = deque(self.path_to_food())
        if self.plan:
            return self.plan.popleft()
        wander = [d for d in DIRECTIONS.values() if self.keeps_tail([d])]
        if wander:
            return random.choice(wander)  # noqa: S311
        return self.direction

    def path_to_food(self) -> list[Cell]:
        """Return the shortest path to the food that keeps the tail."""
        blocked = {*self.body, self.food} - {self.body[-1]}
        paths: dict[Cell, list[Cell]] = {self.body[0]: []}
        todo = deque(paths)
        while todo:
            pos = todo.popleft()
            for direction, nxt in self.neighbors(pos):
                path = [*paths[pos], direction]
                if nxt == self.food and self.keeps_tail(path):
                    return path
                if self.on_field(nxt) and nxt not in blocked and nxt not in paths:
                    paths[nxt] = path
                    todo.append(nxt)
        return []

    def keeps_tail(self, directions: list[Cell]) -> bool:
        """Return whether the snake can still reach its tail."""
        body = deque(self.body)
        if not all(self.move(body, direction) for direction in directions):
            return False
        tail = body[-1]
        seen = {*body, self.food}
        todo = [body[0]]
        while todo:
            for _, nxt in self.neighbors(todo.pop()):
                if nxt == tail:
                    return True
                if self.on_field(nxt) and nxt not in seen:
                    seen.add(nxt)
                    todo.append(nxt)
        return False

    def neighbors(self, pos: Cell) -> Iterator[tuple[Cell, Cell]]:
        """Yield the direction to and position of each cell next to pos."""
        x, y = pos
        for dx, dy in DIRECTIONS.values():
            yield (dx, dy), (x + dx, y + dy)
