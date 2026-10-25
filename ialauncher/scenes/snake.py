"""Snake, hidden in the grid."""

import math
import random
from collections import deque
from collections.abc import Iterator
from typing import TYPE_CHECKING, override

import pygame as pg

from ialauncher.bios import speaker
from ialauncher.cga import cga
from ialauncher.engine import NextScene
from ialauncher.game import Game
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
PAUSE = 500


class Field(Scene):
    """Base class for scenes on the playing field of Snake."""

    def __init__(self, referrer: "Grid") -> None:
        """Store scene to hand back to."""
        super().__init__()
        self.referrer = referrer

    def layout(self, screen: pg.Surface) -> None:
        """Lay out the playing field in whole rows of slightly stretched tiles."""
        width, height = screen.get_size()
        self.cols = self.referrer.cols
        self.rows = round(height / self.referrer.row_height)
        cell_width, cell_height = width // self.cols, height // self.rows
        margin = grid_margin(cell_width)
        self.tile_size = cell_width - margin, cell_height - margin

    def title(self, game: Game) -> pg.Surface:
        """Return the title screen of a game, scaled to the tile size."""
        title = game.get_titlescreen(self.tile_size)
        if title is None:
            title = pg.image.load(game.titlescreen)
        return sharp_scale(cga.apply(title), self.tile_size)

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
    def handle(self, event: pg.event.Event) -> NextScene:
        """Hand back on Escape."""
        if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
            return self.referrer
        return None


class Intro(Field):
    """The grid's tiles disappear two by two, then Snake starts."""

    @override
    def run(self, screen: pg.Surface) -> NextScene:
        """Fill the playing field with the grid's games, in random order."""
        self.layout(screen)
        games = gamelist.games
        top = self.referrer.top
        self.tiles = [
            (self.title(games[(top + i) % len(games)]), (i % self.cols, i // self.cols))
            for i in range(self.cols * self.rows)
        ]
        random.shuffle(self.tiles)
        self.start = pg.time.get_ticks() + PAUSE
        return super().run(screen)

    @override
    def get_events(self) -> list[pg.event.Event]:
        """Run as fast as possible."""
        return pg.event.get()

    @override
    def update(self, screen: pg.Surface) -> NextScene:
        """Pause, remove two tiles each frame, pause again, and start Snake."""
        screen.fill(BLACK)
        screen.fblits((image, self.cell(pos)) for image, pos in self.tiles)
        if pg.time.get_ticks() < self.start:
            return None
        if not self.tiles:
            return Snake(self.referrer)
        del self.tiles[-2:]
        if not self.tiles:
            self.start = pg.time.get_ticks() + PAUSE
        return None


class Snake(Field):
    """Yes, the game."""

    @override
    def run(self, screen: pg.Surface) -> NextScene:
        """Lay out the playing field and start with snake in the middle."""
        self.layout(screen)

        # The body is a list of cells composed of title screens.
        x, y = self.cols // 2, self.rows // 2
        self.body = deque((x - i, y) for i in range(START_LENGTH))
        self.images = deque(self.random_title() for _ in range(START_LENGTH))
        self.direction = DIRECTIONS[pg.K_RIGHT]
        self.turns: deque[Cell] = deque()
        self.ai = True
        self.game_over = False
        self.place_food()
        speaker.blip()
        return super().run(screen)

    def random_title(self) -> pg.Surface:
        """Return the title screen of a random game, scaled to the tile size."""
        return self.title(random.choice(gamelist.games))  # noqa: S311

    def place_food(self) -> bool:
        """Place food in a convenient location."""
        occupied = set(self.body)
        free = [
            (x, y)
            for y in range(1, self.rows - 1)
            for x in range(1, self.cols - 1)
            if (x, y) not in occupied
        ]
        if not free:
            return False
        reach = self.reach([self.body[0]], occupied)
        reachable = [pos for pos in free if pos in reach]
        roomy = [
            (x, y)
            for x, y in reachable
            if not any(
                (x + dx, y + dy) in occupied for dx in (-1, 0, 1) for dy in (-1, 0, 1)
            )
        ]
        self.food = random.choice(roomy or reachable or free)  # noqa: S311
        self.food_image = self.random_title()
        return True

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Take over from the AI with the arrow keys, or hand back on Escape."""
        if event.type == pg.KEYDOWN and event.key in DIRECTIONS:
            self.ai = False
            self.turns.append(DIRECTIONS[event.key])
        return super().handle(event)

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
        """Add a cell in front of the head; return False on collision."""
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

        1. Always keep the tail in sight.
        2. Always take the shortest path to food.
        """
        head = self.body[0]
        body = set(self.body)
        x, y = self.food
        walls = {*body, self.food} - {head}
        approaches = [
            pos
            for (dx, dy), pos in self.neighbors(self.food)
            if pos not in walls and (x - dx, y - dy) not in body
        ]
        distance = self.reach(approaches, walls)
        if head in approaches:
            distance[self.food] = -1
        moves = list(self.neighbors(head))
        random.shuffle(moves)
        moves.sort(key=lambda move: distance.get(move[1], math.inf))
        return next((d for d, _ in moves if self.keeps_tail(d)), self.direction)

    def keeps_tail(self, direction: Cell) -> bool:
        """Return whether the snake can still reach its tail after this move."""
        body = deque(self.body)
        if not self.move(body, direction):
            return False
        reach = self.reach([body[0]], {*body, self.food})
        return any(pos in reach for _, pos in self.neighbors(body[-1]))

    def reach(self, starts: list[Cell], walls: set[Cell]) -> dict[Cell, int]:
        """Return the distances to the cells reachable from starts, avoiding walls."""
        distance = dict.fromkeys(starts, 0)
        todo = deque(distance)
        while todo:
            pos = todo.popleft()
            for _, nxt in self.neighbors(pos):
                if self.on_field(nxt) and nxt not in walls and nxt not in distance:
                    distance[nxt] = distance[pos] + 1
                    todo.append(nxt)
        return distance

    def neighbors(self, pos: Cell) -> Iterator[tuple[Cell, Cell]]:
        """Yield the direction to and position of each cell next to pos."""
        x, y = pos
        for dx, dy in DIRECTIONS.values():
            yield (dx, dy), (x + dx, y + dy)
