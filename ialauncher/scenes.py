import os
import random
import shutil
from collections.abc import Callable
from typing import override

import pygame as pg

import games as gd

from . import options
from .engine import NextScene, Scene
from .game import Game
from .gamelist import SEARCH_TIMEOUT, GameList

CYAN = (0, 204, 255)
MAGENTA = (255, 0, 204)
RED = (255, 0, 0)
GRID_MARGIN = 4
ASPECT_RATIO = 16 / 10
GRID_LARGER = {pg.K_MINUS, pg.K_KP_MINUS}
GRID_SMALLER = {pg.K_PLUS, pg.K_EQUALS, pg.K_KP_PLUS}
ADVANCE = pg.event.custom_type()
SEARCH_EXPIRED = pg.event.custom_type()


class TitleScreen(Scene):
    RESOLUTION = 320, 200
    BAR = pg.Rect(102, 171, 116, 8)

    def __init__(self) -> None:
        self.canvas = pg.Surface(self.RESOLUTION)
        self.title = pg.image.load(os.path.join(os.path.dirname(__file__), "title.png"))
        self.gradient = gradient(self.BAR.size, MAGENTA, CYAN)
        super().__init__()

    def draw_progress(self, screen: pg.Surface, fraction: float) -> None:
        canvas = self.canvas
        canvas.blit(self.title, (0, 0))
        progress = self.gradient.get_rect()
        progress.width = int(progress.width * fraction)
        canvas.blit(self.gradient, self.BAR, progress)
        screen.fill((0, 0, 0))
        target = screen.subsurface(letterbox(screen.get_rect()))
        pg.transform.scale(canvas, target.get_size(), target)


class Loading(TitleScreen):
    def __init__(self, slurp_mode: bool = False, capture_mode: bool = False) -> None:
        self.slurp_mode = slurp_mode
        self.capture_mode = capture_mode
        self.games_dir = os.path.dirname(gd.__file__)
        self.todo = [
            os.path.join(self.games_dir, entry)
            for entry in os.listdir(self.games_dir)
            if os.path.exists(os.path.join(self.games_dir, entry, "metadata.ini"))
        ]
        self.total = len(self.todo)
        self.downloading: Game | None = None
        self.games = GameList()
        super().__init__()

    @override
    def get_events(self) -> list[pg.event.Event]:
        return pg.event.get()

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
            return False
        return None

    @override
    def run(self, screen: pg.Surface) -> NextScene:
        try:
            return super().run(screen)
        finally:
            if self.downloading and (thread := self.downloading.download_thread):
                thread.cancel()

    def load_games(self, number_of_games: int) -> None:
        while self.todo and number_of_games:
            path = self.todo.pop()
            self.games.add(path)
            number_of_games -= 1

    def download_game(self) -> None:
        """
        Start downloading the next game once the previous download has
        finished. Downloads run in a separate thread, so the title screen
        keeps being redrawn in the meantime.
        """

        if self.downloading:
            thread = self.downloading.download_thread
            if thread is not None and thread.is_alive():
                return
            self.downloading = None
        if self.todo:
            path = self.todo.pop()
            self.games.add(path)
            self.downloading = self.games.games[-1]
            self.downloading.download(unzip=False)

    def done(self) -> NextScene:
        if self.slurp_mode:
            return False
        self.games.sort(slideshow=options.slideshow)
        if self.capture_mode:
            return Capture(self.games)
        return Browse(self.games)

    @override
    def update(self, screen: pg.Surface) -> NextScene:
        if self.slurp_mode:
            self.clock.tick(30)
            self.download_game()
        else:
            self.load_games(10)
        if not self.todo and not self.downloading:
            return self.done()
        finished = self.total - len(self.todo) - bool(self.downloading)
        self.draw_progress(screen, finished / self.total)
        return None


class Browse(Scene):
    def __init__(self, games: GameList) -> None:
        self.games = games
        self.games.games = [game for game in games.games if game.get_titlescreen()]
        self.games.random_game()

        # The grid shows size x size games, starting at position `top`.
        # Positions are unbounded so the list appears to be infinite;
        # the game at a position is found by wrapping around the list.
        self.size = 1
        self.top = self.pos = self.games.current_game
        self.cache: dict[tuple[int, tuple[int, int]], pg.Surface] = {}
        self.slideshow = options.slideshow
        self.set_slideshow(bool(options.slideshow))
        self.handlers: dict[int, Callable[[], None]] = {
            pg.K_RIGHT: self.games.next_game,
            pg.K_LEFT: self.games.previous_game,
            pg.K_DOWN: self.games.next_letter,
            pg.K_UP: self.games.previous_letter,
            pg.K_SPACE: self.games.random_game,
        }
        super().__init__()

    def set_slideshow(self, enabled: bool) -> None:
        pg.time.set_timer(ADVANCE, self.slideshow * 1000 if enabled else 0)

    def rows_to_scroll(self, pos: int) -> int:
        """Number of rows to scroll (negative is up) to bring pos into view"""
        n = self.size
        if pos < self.top:
            return (pos - self.top) // n
        if pos >= self.top + n * n:
            return (pos - self.top) // n - n + 1
        return 0

    def scroll(self) -> None:
        self.top += self.rows_to_scroll(self.pos) * self.size

    def resize(self, size: int) -> None:
        self.size = max(1, size)
        self.cache = {}
        self.scroll()

    def move(self, step: int) -> None:
        self.pos += step
        self.games.current_game = self.pos % len(self.games.games)
        self.scroll()

    def follow(self) -> None:
        """
        Move the position to the current game (which may have been
        changed by a jump or search) with the least amount of scrolling.
        """

        total = len(self.games.games)
        current = self.games.current_game
        if self.pos % total == current:
            return
        below = self.top + (current - self.top) % total
        self.pos = min(below, below - total, key=lambda p: abs(self.rows_to_scroll(p)))
        self.scroll()

    @override
    def get_events(self) -> list[pg.event.Event]:
        return [pg.event.wait()]

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        if event.type == ADVANCE:
            self.games.reset_search()
            self.games.random_game()
        if event.type == SEARCH_EXPIRED:
            self.games.reset_search()
        if event.type == pg.KEYDOWN:
            if event.key == pg.K_ESCAPE:
                return False
            n = self.size
            grid_moves = {pg.K_RIGHT: 1, pg.K_LEFT: -1, pg.K_DOWN: n, pg.K_UP: -n}
            if event.key != pg.K_SPACE:
                self.set_slideshow(False)
            elif not self.games.is_searching():
                self.set_slideshow(True)
            if event.key == pg.K_SPACE and self.games.is_searching():
                self.games.search(" ")
            elif event.key == pg.K_SPACE and n > 1:
                self.resize(1)
                self.games.random_game()
            elif event.key in GRID_LARGER and not self.games.is_searching():
                self.resize(n + 1)
            elif event.key in GRID_SMALLER and not self.games.is_searching():
                self.resize(n - 1)
            elif n > 1 and event.key in grid_moves:
                self.games.reset_search()
                self.move(grid_moves[event.key])
            elif event.key == pg.K_BACKSPACE:
                self.games.backspace()
            elif handler := self.handlers.get(event.key):
                self.games.reset_search()
                handler()
            elif event.unicode.isprintable() and event.unicode:
                self.games.search(event.unicode)

            # (Re)start the timer that removes the query from the screen
            if self.games.query:
                pg.time.set_timer(SEARCH_EXPIRED, SEARCH_TIMEOUT, loops=1)
            if event.key == pg.K_RETURN:
                self.games.reset_search()
                game = self.games.get_current_game()
                if event.mod & pg.KMOD_SHIFT:
                    game.reset()
                if not game.is_ready():
                    Download(game).run(self.screen)
                if game.is_ready():

                    # Start playing (spawns a new thread)
                    game.start(autorun=not event.mod & pg.KMOD_ALT)
        self.follow()
        return None

    @override
    def update(self, screen: pg.Surface) -> None:
        rect = screen.get_rect()
        n = self.size
        games = self.games.games
        cache: dict[tuple[int, tuple[int, int]], pg.Surface] = {}
        selected = None
        screen.fill((0, 0, 0))
        for i in range(n * n):
            row, col = divmod(i, n)
            x, y = rect.width * col // n, rect.height * row // n
            cell = pg.Rect(
                x, y, rect.width * (col + 1) // n - x, rect.height * (row + 1) // n - y
            )
            if n > 1:
                image_rect = cell.inflate(-2 * GRID_MARGIN, -2 * GRID_MARGIN)
            else:
                image_rect = letterbox(cell)

            # Only keep the scaled images that are currently visible
            index = (self.top + i) % len(games)
            key = index, image_rect.size
            image = cache.get(key, self.cache.get(key))
            if image is None:
                image = pg.transform.scale(
                    self.games.get_image(games[index]), image_rect.size
                )
            cache[key] = image
            screen.blit(image, image_rect)
            if self.top + i == self.pos:
                selected = cell
        self.cache = cache
        if n > 1 and selected is not None:
            pg.draw.rect(screen, RED, selected, GRID_MARGIN)
        if self.games.query:
            self.draw_query(screen)

    def draw_query(
        self, screen: pg.Surface, margin: int = 15, padding: int = 8
    ) -> None:
        if not hasattr(self, "font"):
            self.font = pg.font.SysFont("monospace", 24)
        image = self.font.render(self.games.query, True, (255, 255, 255))
        rect = image.get_rect().inflate(2 * padding, 2 * padding)
        rect.topleft = (margin, margin)
        screen.fill((0, 0, 0), rect)
        screen.blit(image, image.get_rect(center=rect.center))


class Capture(Scene):
    """
    List all games without a title screen. While a game is running,
    watch the captures directory and move every new screenshot to the
    title.png of that game.
    """

    POLL_INTERVAL = 500

    def __init__(self, games: GameList) -> None:
        self.games = [game for game in games.games if not game.get_titlescreen()]
        self.current = 0
        self.offset = 0
        self.captured: set[Game] = set()
        self.running: Game | None = None
        self.existing: set[str] = set()
        self.sizes: dict[str, int] = {}
        self.captures_dir = os.path.expanduser(options.captures_dir)
        self.last_poll = 0
        self.preview: pg.Surface | None = None
        super().__init__()

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        if event.type != pg.KEYDOWN:
            return None
        if event.key == pg.K_ESCAPE:
            return False
        moves = {
            pg.K_DOWN: 1,
            pg.K_UP: -1,
            pg.K_PAGEDOWN: 20,
            pg.K_PAGEUP: -20,
            pg.K_END: len(self.games),
            pg.K_HOME: -len(self.games),
        }
        if event.key in moves and self.games:
            self.current = max(
                0, min(len(self.games) - 1, self.current + moves[event.key])
            )
            self.preview = None
        if event.key == pg.K_RETURN and self.games and not self.running:
            game = self.games[self.current]
            if event.mod & pg.KMOD_SHIFT:
                game.reset()
            if not game.is_ready():
                Download(game).run(self.screen)
            if game.is_ready():
                self.watch(game)

                # Start playing (spawns a new thread)
                game.start(autorun=not event.mod & pg.KMOD_ALT)
        return None

    def watch(self, game: Game) -> None:
        os.makedirs(self.captures_dir, exist_ok=True)
        self.running = game
        self.existing = set(os.listdir(self.captures_dir))
        self.sizes = {}

    def poll(self, game: Game) -> None:
        """
        Move new screenshots to the title screen of the given game,
        but only once their size has stopped changing.
        """

        for name in sorted(os.listdir(self.captures_dir)):
            path = os.path.join(self.captures_dir, name)
            if name in self.existing or not name.lower().endswith(".png"):
                continue
            size = os.path.getsize(path)
            if size and self.sizes.get(name) == size:
                dest = os.path.join(game.path, "title.png")
                shutil.copyfile(path, dest)
                os.remove(path)
                print(f"Captured {name} as title screen of {game.identifier}")
                self.captured.add(game)
                self.preview = None
                del self.sizes[name]
            else:
                self.sizes[name] = size

    @override
    def update(self, screen: pg.Surface) -> None:
        if self.running and pg.time.get_ticks() - self.last_poll >= self.POLL_INTERVAL:
            self.last_poll = pg.time.get_ticks()
            running = self.running.is_running()
            self.poll(self.running)
            if not running:
                self.running = None

        screen.fill((0, 0, 0))
        if not hasattr(self, "font"):
            self.font = pg.font.SysFont("monospace", 24)
        rect = screen.get_rect()
        margin = 15
        line_height = self.font.get_linesize()

        status = (
            f"Running: {self.running.identifier}"
            if self.running
            else "Enter: play, Alt-Enter: play without autorun, Esc: quit"
        )
        header = f"{len(self.captured)} of {len(self.games)} captured | {status}"
        screen.blit(self.font.render(header, True, (255, 255, 0)), (margin, margin))

        # Game list on the left half, scrolled to keep the selection visible
        top = margin + 2 * line_height
        rows = max(1, (rect.height - top - margin) // line_height)
        if self.current < self.offset:
            self.offset = self.current
        elif self.current >= self.offset + rows:
            self.offset = self.current - rows + 1
        list_width = rect.width // 2 - 2 * margin
        for i, game in enumerate(
            self.games[self.offset : self.offset + rows], self.offset
        ):
            mark = "*" if game in self.captured else " "
            color = (0, 0, 0) if i == self.current else (255, 255, 255)
            y = top + (i - self.offset) * line_height
            if i == self.current:
                screen.fill((255, 255, 255), (margin, y, list_width, line_height))
            text = self.font.render(f"{mark} {game.identifier}", True, color)
            screen.blit(text, (margin, y), (0, 0, list_width, line_height))

        # Preview of the captured title screen on the right half
        if self.games and (path := self.games[self.current].get_titlescreen()):
            if self.preview is None:
                self.preview = pg.image.load(path)
            area = pg.Rect(
                rect.width // 2,
                top,
                rect.width // 2 - margin,
                rect.height - top - margin,
            )
            w, h = self.preview.get_size()
            scale = min(area.width / w, area.height / h)
            image = pg.transform.scale(self.preview, (int(w * scale), int(h * scale)))
            screen.blit(image, image.get_rect(midtop=area.midtop))


class Download(TitleScreen):
    def __init__(self, game: Game, unzip: bool = True) -> None:
        self.game = game
        super().__init__()

        # Start downloading (spawns a new thread)
        self.game.download(unzip)

    @override
    def run(self, screen: pg.Surface) -> NextScene:
        try:
            return super().run(screen)
        finally:
            if thread := self.game.download_thread:
                thread.cancel()

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        if event.type == pg.KEYDOWN:
            if event.key == pg.K_ESCAPE:
                return False
        return None

    @override
    def update(self, screen: pg.Surface) -> NextScene:
        thread = self.game.download_thread
        if thread is None or not thread.is_alive():
            return False
        self.draw_progress(screen, thread.progress)
        return None


def letterbox(rect: pg.Rect) -> pg.Rect:
    """Largest rect with a fixed aspect ratio centered within the given rect"""
    width = min(rect.width, round(rect.height * ASPECT_RATIO))
    height = min(rect.height, round(rect.width / ASPECT_RATIO))
    letterboxed = pg.Rect(0, 0, width, height)
    letterboxed.center = rect.center
    return letterboxed


def gradient(
    size: tuple[int, int], start: tuple[int, int, int], end: tuple[int, int, int]
) -> pg.Surface:
    width, height = size
    surface = pg.Surface(size)
    for x in range(width):
        color = pg.Color(start).lerp(end, x / max(width - 1, 1))
        pg.draw.line(surface, color, (x, 0), (x, height - 1))
    return surface
