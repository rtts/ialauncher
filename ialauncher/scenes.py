import math
import os
import random
import shutil
from collections.abc import Callable, Iterator
from typing import override

import pygame as pg

import games as gd

from . import engine, options
from .cga import cga
from .engine import NextScene
from .game import Game
from .gamelist import SEARCH_TIMEOUT, GameList

CYAN = (0, 204, 255)
MAGENTA = (255, 0, 204)
BLACK = (0, 0, 0)
GRID_MARGIN = 5
FULLSCREEN_ASPECT_RATIO = 16 / 10
TILE_ASPECT_RATIO = 3 / 2
GRID_LARGER = {pg.K_MINUS, pg.K_KP_MINUS}
GRID_SMALLER = {pg.K_PLUS, pg.K_EQUALS, pg.K_KP_PLUS}
ADVANCE = pg.event.custom_type()
SEARCH_EXPIRED = pg.event.custom_type()
MENU_FONT = "dejavusans,liberationsans,arial,helvetica,sans"
MENU_ITEMS = [
    ("Start game", "Enter", 0),
    ("Reset game state", "Shift-Enter", pg.KMOD_SHIFT),
    ("DOSBox prompt", "Alt-Enter", pg.KMOD_ALT),
]


class Scene(engine.Scene):
    @override
    def intercept(self, event: pg.event.Event) -> bool:
        return cga.cheat(event)


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

        # The grid shows rows x cols games, starting at position `top`.
        # Positions are unbounded so the list appears to be infinite;
        # the game at a position is found by wrapping around the list.
        self.cols = 1
        self.top = self.pos = self.games.current_game
        self.cache: dict[tuple[int, tuple[int, int], int | None], pg.Surface] = {}
        self.menu: Menu | None = None
        self.slideshow = options.slideshow
        self.set_slideshow(bool(options.slideshow))
        self.cursor = pg.SYSTEM_CURSOR_HAND
        pg.mouse.set_system_cursor(self.cursor)
        self.handlers: dict[int, Callable[[], None]] = {
            pg.K_RIGHT: self.games.next_game,
            pg.K_LEFT: self.games.previous_game,
            pg.K_DOWN: self.games.next_letter,
            pg.K_UP: self.games.previous_letter,
            pg.K_SPACE: self.games.random_game,
        }
        super().__init__()

    @override
    def intercept(self, event: pg.event.Event) -> bool:
        if not super().intercept(event):
            return False
        self.games.reset_search()
        self.resize(1)
        self.games.random_game()
        self.follow()
        return True

    def set_slideshow(self, enabled: bool) -> None:
        pg.time.set_timer(ADVANCE, self.slideshow * 1000 if enabled else 0)

    @property
    def area(self) -> pg.Rect:
        # Leave room for the selection border, which can be wider than the margin
        return self.screen.get_rect().inflate(-2, -2)

    @property
    def rows(self) -> int:
        return grid_rows(self.cols, self.area.size)

    @property
    @override
    def show_mouse(self) -> bool:
        if self.menu:
            return True
        return self.cols > 1 and self.area.collidepoint(pg.mouse.get_pos())

    def cells(self) -> Iterator[tuple[int, pg.Rect]]:
        rect = self.area
        rows, cols = self.rows, self.cols
        for i in range(rows * cols):
            row, col = divmod(i, cols)
            x, y = rect.width * col // cols, rect.height * row // rows
            cell = pg.Rect(
                x,
                y,
                rect.width * (col + 1) // cols - x,
                rect.height * (row + 1) // rows - y,
            ).move(rect.topleft)
            yield self.top + i, cell

    def rows_to_scroll(self, pos: int) -> int:
        """Number of rows to scroll (negative is up) to bring pos into view"""
        rows, cols = self.rows, self.cols
        if pos < self.top:
            return (pos - self.top) // cols
        if pos >= self.top + rows * cols:
            return (pos - self.top) // cols - rows + 1
        return 0

    def scroll(self) -> None:
        self.top += self.rows_to_scroll(self.pos) * self.cols

    def resize(self, cols: int) -> None:
        self.cols = max(1, cols)
        self.cache = {}
        self.scroll()

    def select(self, pos: int) -> None:
        self.pos = pos
        self.games.current_game = pos % len(self.games.games)
        self.scroll()

    def point(self, point: tuple[int, int]) -> bool:
        for pos, cell in self.cells():
            if cell.collidepoint(point):
                if pos != self.pos:
                    self.set_slideshow(False)
                    self.games.reset_search()
                    self.select(pos)
                return True
        return False

    def play(self, mod: int) -> None:
        self.games.reset_search()
        game = self.games.get_current_game()
        if mod & pg.KMOD_SHIFT:
            game.reset()
        if not game.is_ready():
            Download(game).run(self.screen)
        if game.is_ready():

            # Start playing (spawns a new thread)
            game.start(autorun=not mod & pg.KMOD_ALT)

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

    def handle_menu(self, menu: "Menu", event: pg.event.Event) -> bool:
        if event.type == pg.MOUSEMOTION:
            menu.highlighted = menu.item_at(event.pos)
            return True
        if event.type in (pg.KEYDOWN, pg.MOUSEBUTTONDOWN, pg.MOUSEWHEEL, ADVANCE):
            self.menu = None
            if event.type == pg.MOUSEBUTTONDOWN and event.button == pg.BUTTON_LEFT:
                if menu.highlighted is not None:
                    self.play(MENU_ITEMS[menu.highlighted][2])
                return True
            return event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE
        return False

    @override
    def get_events(self) -> list[pg.event.Event]:
        return [pg.event.wait()]

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        if self.menu and self.handle_menu(self.menu, event):
            return None
        if event.type == ADVANCE:
            self.games.reset_search()
            self.games.random_game()
        if event.type == SEARCH_EXPIRED:
            self.games.reset_search()
        if event.type == pg.MOUSEMOTION and self.cols > 1:
            self.point(event.pos)
        if (
            event.type == pg.MOUSEBUTTONDOWN
            and event.button == pg.BUTTON_LEFT
            and self.cols > 1
            and self.point(event.pos)
        ):
            self.play(pg.key.get_mods())
        if (
            event.type == pg.MOUSEBUTTONDOWN
            and event.button == pg.BUTTON_RIGHT
            and self.cols > 1
            and self.point(event.pos)
        ):
            if not hasattr(self, "menu_font"):
                self.menu_font = pg.font.SysFont(MENU_FONT, 12)
            self.menu = Menu(
                self.menu_font,
                self.games.get_current_game(),
                event.pos,
                self.screen.get_rect(),
            )
        if event.type == pg.MOUSEWHEEL and event.y and pg.key.get_mods() & pg.KMOD_CTRL:
            self.set_slideshow(False)
            self.games.reset_search()
            self.resize(self.cols - 2 * event.y)
        elif event.type == pg.MOUSEWHEEL and event.y and self.show_mouse:
            self.set_slideshow(False)
            self.games.reset_search()
            delta = -event.y * self.cols
            self.top += delta
            self.select(self.pos + delta)
        if event.type == pg.KEYDOWN:
            if event.key == pg.K_ESCAPE:
                return False
            cols = self.cols
            grid = cols > 1
            grid_moves = {pg.K_RIGHT: 1, pg.K_LEFT: -1, pg.K_DOWN: cols, pg.K_UP: -cols}
            if event.key != pg.K_SPACE:
                self.set_slideshow(False)
            elif not self.games.is_searching():
                self.set_slideshow(True)
            if event.key == pg.K_SPACE and self.games.is_searching():
                self.games.search(" ")
            elif event.key == pg.K_SPACE and grid:
                self.resize(1)
                self.games.random_game()
            elif event.key in GRID_LARGER and not self.games.is_searching():
                self.resize(cols + 2)
            elif event.key in GRID_SMALLER and not self.games.is_searching():
                self.resize(cols - 2)
            elif grid and event.key in grid_moves:
                self.games.reset_search()
                self.select(self.pos + grid_moves[event.key])
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
                self.play(event.mod)
        self.follow()
        return None

    @override
    def update(self, screen: pg.Surface) -> None:
        self.scroll()
        if self.menu and self.menu.highlighted is None:
            cursor = pg.SYSTEM_CURSOR_ARROW
        else:
            cursor = pg.SYSTEM_CURSOR_HAND
        if cursor != self.cursor:
            self.cursor = cursor
            pg.mouse.set_system_cursor(cursor)
        cols = self.cols
        games = self.games.games
        cache: dict[tuple[int, tuple[int, int], int | None], pg.Surface] = {}
        selected = None
        margin = grid_margin(cols)
        screen.fill((0, 0, 0))
        for pos, cell in self.cells():
            if cols > 1:
                image_rect = cell.inflate(-2 * margin, -2 * margin)
            else:
                image_rect = letterbox(cell)

            # Only keep the scaled images that are currently visible
            index = pos % len(games)
            key = index, image_rect.size, cga.palette
            image = cache.get(key, self.cache.get(key))
            if image is None:
                title = cga.apply(self.games.get_image(games[index]))
                image = pg.transform.scale(title, image_rect.size)
            cache[key] = image
            screen.blit(image, image_rect)
            if pos == self.pos:
                selected = image_rect
        self.cache = cache
        if cols > 1 and selected is not None:
            border = max(2, margin)
            pg.draw.rect(
                screen, MAGENTA, selected.inflate(2 * border, 2 * border), border
            )
        if self.games.query:
            self.draw_query(screen)
        if self.menu:
            self.menu.draw(screen)

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


class Menu:
    PADDING = 10
    GAP = 20
    TITLE_BACKGROUND = MAGENTA
    TITLE_FOREGROUND = BLACK
    BACKGROUND = MAGENTA
    FOREGROUND = BLACK
    HIGHLIGHT_BACKGROUND = CYAN
    HIGHLIGHT_FOREGROUND = BLACK

    def __init__(
        self, font: pg.font.Font, game: Game, pos: tuple[int, int], bounds: pg.Rect
    ) -> None:
        self.font = font
        self.highlighted: int | None = None
        if not game.configured:
            game.configure()
        font.bold = True
        self.title = font.render(
            f"{game.title} ({game.year})", True, self.TITLE_FOREGROUND
        )
        font.bold = False
        labels = max(font.size(label)[0] for label, _, _ in MENU_ITEMS)
        shortcuts = max(font.size(shortcut)[0] for _, shortcut, _ in MENU_ITEMS)
        self.shortcut_x = self.PADDING + labels + self.GAP
        width = max(self.PADDING + self.title.get_width(), self.shortcut_x + shortcuts)
        self.line_height = font.get_linesize() + self.PADDING
        size = width + self.PADDING, (len(MENU_ITEMS) + 1) * self.line_height
        self.rect = pg.Rect(pos, size).clamp(bounds)

    def row(self, item: int) -> pg.Rect:
        top = self.rect.top + (item + 1) * self.line_height
        return pg.Rect(self.rect.left, top, self.rect.width, self.line_height)

    def item_at(self, point: tuple[int, int]) -> int | None:
        for item in range(len(MENU_ITEMS)):
            if self.row(item).collidepoint(point):
                return item
        return None

    def draw(self, screen: pg.Surface) -> None:
        screen.fill(self.BACKGROUND, self.rect)
        screen.fill(self.TITLE_BACKGROUND, self.row(-1))
        x = self.rect.left + self.PADDING
        shortcut_x = self.rect.left + self.shortcut_x
        screen.blit(self.title, (x, self.rect.top + self.PADDING // 2))
        for item, (label, shortcut, _) in enumerate(MENU_ITEMS):
            row = self.row(item)
            color = self.FOREGROUND
            if item == self.highlighted:
                screen.fill(self.HIGHLIGHT_BACKGROUND, row)
                color = self.HIGHLIGHT_FOREGROUND
            y = row.top + self.PADDING // 2
            screen.blit(self.font.render(label, True, color), (x, y))
            screen.blit(self.font.render(shortcut, True, color), (shortcut_x, y))


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


def grid_margin(cols: int) -> int:
    return max(1, round(GRID_MARGIN * 3 / cols))


def grid_rows(cols: int, size: tuple[int, int]) -> int:
    if cols == 1:
        return 1
    width, height = size
    margin = grid_margin(cols)
    tile_width = width / cols - 2 * margin

    def error(rows: int) -> float:
        tile_height = height / rows - 2 * margin
        if tile_width <= 0 or tile_height <= 0:
            return math.inf
        return abs(math.log(tile_width / tile_height / TILE_ASPECT_RATIO))

    estimate = height * cols * TILE_ASPECT_RATIO / width
    candidates = {max(1, math.floor(estimate)), max(1, math.ceil(estimate))}
    return min(sorted(candidates), key=error)


def letterbox(rect: pg.Rect) -> pg.Rect:
    width = min(rect.width, round(rect.height * FULLSCREEN_ASPECT_RATIO))
    height = min(rect.height, round(rect.width / FULLSCREEN_ASPECT_RATIO))
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
