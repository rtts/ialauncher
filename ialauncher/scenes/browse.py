"""All games in a grid with infinite zoom and infinite scrolling."""

from collections.abc import Callable, Iterator
from contextlib import suppress
from functools import cached_property
from typing import override

import pygame as pg

from ialauncher import options
from ialauncher.cga import cga
from ialauncher.engine import NextScene
from ialauncher.game import EMULATOR_FAILED, Game
from ialauncher.gamelist import SEARCH_TIMEOUT, GameList
from ialauncher.utils import (
    find_emulator,
    grid_margin,
    grid_rows,
    letterbox,
    show_error,
)

from . import ANTIALIAS, BLACK, CYAN, MAGENTA, WHITE, Scene
from .download import Download

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


class Browse(Scene):
    """All games in a grid with infinite zoom and infinite scrolling."""

    def __init__(self, games: GameList) -> None:
        """Show a random game, full screen."""
        self.games = games
        self.games.random_game()
        self.cols = 1
        self.top = self.pos = self.games.current_game
        self.cache: dict[tuple[int, tuple[int, int], int | None], pg.Surface] = {}
        self.menu: Menu | None = None
        self.slideshow = options.slideshow
        self.set_slideshow(enabled=bool(options.slideshow))
        self.set_cursor(pg.SYSTEM_CURSOR_HAND)
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
        """Jump to random game after switching CGA mode with cheat code."""
        if not super().intercept(event):
            return False
        self.games.reset_search()
        self.resize(1)
        self.games.random_game()
        self.follow()
        self.set_slideshow(enabled=True)
        return True

    def set_cursor(self, cursor: int) -> None:
        """Change the mouse pointer, if the video driver supports that."""
        self.cursor = cursor
        with suppress(pg.error):
            pg.mouse.set_cursor(cursor)

    def set_slideshow(self, *, enabled: bool) -> None:
        """Start or stop the slideshow."""
        pg.time.set_timer(ADVANCE, self.slideshow * 1000 if enabled else 0)

    @cached_property
    def font(self) -> pg.font.Font:
        """The font of the search query."""
        return pg.font.SysFont("monospace", 24)

    @cached_property
    def menu_font(self) -> pg.font.Font:
        """The font of the menu."""
        return pg.font.SysFont(MENU_FONT, 12)

    @property
    def area(self) -> pg.Rect:
        """The part of the screen that holds the grid."""
        if self.cols == 1:
            return self.screen.get_rect()
        return self.screen.get_rect().inflate(-2, -2)

    @property
    def rows(self) -> int:
        """The number of rows in the grid."""
        return grid_rows(self.cols, self.area.size)

    @property
    @override
    def show_mouse(self) -> bool:
        """Show the mouse pointer over the grid and when the menu is open."""
        if self.menu:
            return True
        return self.cols > 1 and self.area.collidepoint(pg.mouse.get_pos())

    def cells(self) -> Iterator[tuple[int, pg.Rect]]:
        """Yield the position and rectangle of every visible cell."""
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
        """Return the rows to scroll (negative is up) to bring pos into view."""
        rows, cols = self.rows, self.cols
        if pos < self.top:
            return (pos - self.top) // cols
        if pos >= self.top + rows * cols:
            return (pos - self.top) // cols - rows + 1
        return 0

    def scroll(self) -> None:
        """Scroll the grid to bring the selected position into view."""
        self.top += self.rows_to_scroll(self.pos) * self.cols

    def resize(self, cols: int) -> None:
        """Change the number of columns."""
        self.cols = max(1, cols)
        self.cache = {}
        self.scroll()

    def select(self, pos: int) -> None:
        """Select the game at the given position."""
        self.pos = pos
        self.games.current_game = pos % len(self.games.games)
        self.scroll()

    def point(self, point: tuple[int, int]) -> bool:
        """Select the game under the mouse pointer; return False if there is none."""
        for pos, cell in self.cells():
            if cell.collidepoint(point):
                if pos != self.pos:
                    self.set_slideshow(enabled=False)
                    self.games.reset_search()
                    self.select(pos)
                return True
        return False

    def play(self, mod: int) -> None:
        """Download the current game if needed and start it."""
        self.games.reset_search()
        game = self.games.get_current_game()
        if not find_emulator(game):
            return
        if mod & pg.KMOD_SHIFT:
            game.reset()
        if not game.is_ready():
            Download(game).run(self.screen)
        if game.is_ready():
            # Start playing (spawns a new thread)
            game.start(autorun=not mod & pg.KMOD_ALT)

    def follow(self) -> None:
        """Move the position to the current game with the least scrolling.

        The current game may have been changed by a jump or search.
        """
        total = len(self.games.games)
        current = self.games.current_game
        if self.pos % total == current:
            return
        below = self.top + (current - self.top) % total
        self.pos = min(below, below - total, key=lambda p: abs(self.rows_to_scroll(p)))
        self.scroll()

    def handle_menu(self, menu: "Menu", event: pg.event.Event) -> bool:
        """Handle an event while the menu is open; return True if it was consumed."""
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
        """Sleep until the next event."""
        return [pg.event.wait()]

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Handle mouse and keyboard input."""
        if self.menu and self.handle_menu(self.menu, event):
            return None
        if event.type == ADVANCE:
            self.games.reset_search()
            self.games.random_game()
        elif event.type == SEARCH_EXPIRED:
            self.games.reset_search()
        elif event.type == EMULATOR_FAILED:
            show_error(event.message)
        elif event.type in (pg.MOUSEMOTION, pg.MOUSEBUTTONDOWN):
            self.handle_mouse(event)
        elif event.type == pg.MOUSEWHEEL:
            self.handle_wheel(event)
        elif event.type == pg.KEYDOWN:
            if event.key == pg.K_ESCAPE:
                return False
            self.handle_key(event)
        self.follow()
        return None

    def handle_mouse(self, event: pg.event.Event) -> None:
        """Select the game under the pointer; play it or open the menu on click."""
        if self.cols == 1:
            return
        if event.type == pg.MOUSEMOTION:
            self.point(event.pos)
        elif event.button == pg.BUTTON_LEFT and self.point(event.pos):
            self.play(pg.key.get_mods())
        elif event.button == pg.BUTTON_RIGHT and self.point(event.pos):
            self.open_menu(event.pos)

    def open_menu(self, pos: tuple[int, int]) -> None:
        """Open the menu of the current game at the given position."""
        self.menu = Menu(
            self.menu_font,
            self.games.get_current_game(),
            pos,
            self.screen.get_rect(),
        )

    def handle_wheel(self, event: pg.event.Event) -> None:
        """Zoom with Ctrl and the mouse wheel, or scroll with the wheel alone."""
        if not event.y:
            return
        if pg.key.get_mods() & pg.KMOD_CTRL:
            self.set_slideshow(enabled=False)
            self.games.reset_search()
            self.resize(self.cols - 2 * event.y)
        elif self.show_mouse:
            self.set_slideshow(enabled=False)
            self.games.reset_search()
            delta = -event.y * self.cols
            self.top += delta
            self.select(self.pos + delta)

    def handle_key(self, event: pg.event.Event) -> None:
        """Handle a keystroke other than Escape."""
        if event.key != pg.K_SPACE:
            self.set_slideshow(enabled=False)
        elif not self.games.is_searching():
            self.set_slideshow(enabled=True)
        self.navigate(event)

        # (Re)start the timer that removes the query from the screen
        if self.games.query:
            pg.time.set_timer(SEARCH_EXPIRED, SEARCH_TIMEOUT, loops=1)
        if event.key == pg.K_RETURN:
            self.play(event.mod)

    def navigate(self, event: pg.event.Event) -> None:
        """Search, zoom, move, or jump, depending on the key."""
        cols = self.cols
        grid = cols > 1
        grid_moves = {pg.K_RIGHT: 1, pg.K_LEFT: -1, pg.K_DOWN: cols, pg.K_UP: -cols}
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

    @override
    def update(self, screen: pg.Surface) -> None:
        """Draw the visible title screens, the search query, and the menu."""
        self.scroll()
        if self.menu and self.menu.highlighted is None:
            cursor = pg.SYSTEM_CURSOR_ARROW
        else:
            cursor = pg.SYSTEM_CURSOR_HAND
        if cursor != self.cursor:
            self.set_cursor(cursor)
        cols = self.cols
        games = self.games.games
        cache: dict[tuple[int, tuple[int, int], int | None], pg.Surface] = {}
        selected = None
        margin = grid_margin(cols)
        screen.fill(BLACK)
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
        """Draw the search query in the top left corner."""
        image = self.font.render(self.games.query, ANTIALIAS, WHITE)
        rect = image.get_rect().inflate(2 * padding, 2 * padding)
        rect.topleft = (margin, margin)
        screen.fill(BLACK, rect)
        screen.blit(image, image.get_rect(center=rect.center))


class Menu:
    """The context menu that opens when right-clicking a game."""

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
        """Lay out the menu for the game at pos, within the bounds."""
        self.font = font
        self.highlighted: int | None = None
        font.bold = True
        self.title = font.render(
            f"{game.title} ({game.year})", ANTIALIAS, self.TITLE_FOREGROUND
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
        """Return the rectangle of the given menu item, where -1 is the title."""
        top = self.rect.top + (item + 1) * self.line_height
        return pg.Rect(self.rect.left, top, self.rect.width, self.line_height)

    def item_at(self, point: tuple[int, int]) -> int | None:
        """Return the menu item at the given point, or None."""
        for item in range(len(MENU_ITEMS)):
            if self.row(item).collidepoint(point):
                return item
        return None

    def draw(self, screen: pg.Surface) -> None:
        """Draw the menu."""
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
            screen.blit(self.font.render(label, ANTIALIAS, color), (x, y))
            screen.blit(self.font.render(shortcut, ANTIALIAS, color), (shortcut_x, y))
