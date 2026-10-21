"""All games in a grid with infinite zoom and infinite scrolling."""

from collections.abc import Iterator
from contextlib import suppress
from functools import cached_property
from typing import override

import pygame as pg

from ialauncher.cga import cga
from ialauncher.engine import NextScene
from ialauncher.game import Game
from ialauncher.gamelist import gamelist
from ialauncher.utils import ASPECT_RATIO, grid_margin, letterbox, sharp_scale

from . import (
    ANTIALIAS,
    BLACK,
    CYAN,
    GRID_LARGER,
    GRID_SMALLER,
    MAGENTA,
    MENU_FONT,
    Browse,
    hero,
)

GRID_SCROLLS = {
    pg.K_RIGHT: (0, 1),
    pg.K_LEFT: (0, -1),
    pg.K_DOWN: (1, 0),
    pg.K_UP: (-1, 0),
}
MIN_COLS = 3
MENU_ITEMS = [
    ("Start game", "Enter", 0),
    ("Reset game state", "Shift-Enter", pg.KMOD_SHIFT),
    ("DOSBox prompt", "Alt-Enter", pg.KMOD_ALT),
    ("{} favorites", "Ctrl-Enter", pg.KMOD_CTRL),  # Add to/Remove from
]


class Grid(Browse):
    """All games in a grid with infinite zoom and infinite scrolling."""

    def __init__(self) -> None:
        """Initialize as a 3-column grid."""
        super().__init__()
        self.cols = MIN_COLS
        self.top = self.pos = gamelist.current_game
        self.shift = 0  # TODO(JJ): Rename to scroll()
        self.cache: dict[tuple[Game, tuple[int, int], int | None], pg.Surface] = {}
        self.menu: Menu | None = None
        self.set_cursor(pg.SYSTEM_CURSOR_HAND)

    @override
    def run(self, screen: pg.Surface) -> NextScene:
        """Lay out the grid on the screen."""
        self.screen = screen
        self.resize(self.cols)
        return super().run(screen)

    @override
    def intercept(self, event: pg.event.Event) -> bool:
        """Clear filter after switching CGA mode with cheat code."""
        if not super().intercept(event):
            return False
        self.clear_filter()
        return True

    def set_cursor(self, cursor: int) -> None:
        """Change the mouse pointer, if the video driver supports that."""
        self.cursor = cursor
        with suppress(pg.error):
            pg.mouse.set_cursor(cursor)

    @cached_property
    def menu_font(self) -> pg.font.Font:
        """The font of the menu."""
        return pg.font.SysFont(MENU_FONT, 12)

    @property
    def row_height(self) -> float:
        """The height of a row of 4:3 cells that fill the width of the grid."""
        return max(1, self.screen.get_width() / self.cols / ASPECT_RATIO)

    @property
    def tile_size(self) -> tuple[int, int]:
        """The size of each title screen."""
        margin = grid_margin(self.cols)
        cell = pg.Rect(0, 0, self.screen.get_width() // self.cols, int(self.row_height))
        return letterbox(cell.inflate(-2 * margin, -2 * margin)).size

    def row_top(self, row: int) -> int:
        """Return the top of a row in whole pixels, relative to the grid.

        Like the columns, each row is rounded separately, so that the
        rows fill the grid without gaps. On a 4:3 screen, as many rows
        as columns fit exactly.
        """
        return round(row * self.row_height - self.shift)

    def bottom_shift(self) -> int:
        """Return the shift that aligns the bottom row with the bottom of the grid."""
        height = self.screen.get_height()
        rows = 1
        while round(rows * self.row_height) < height:
            rows += 1
        return round(rows * self.row_height) - height

    @property
    @override
    def show_mouse(self) -> bool:
        """Show the mouse pointer."""
        return True

    def cells(self) -> Iterator[tuple[int, pg.Rect]]:
        """Yield the position and rectangle of every (partly) visible cell."""
        rect = self.screen.get_rect()
        cols = self.cols
        row = 0

        # TODO(JJ): Explain.
        while (y := self.row_top(row)) < rect.height:
            height = self.row_top(row + 1) - y
            for col in range(cols):
                x = rect.width * col // cols
                width = rect.width * (col + 1) // cols - x
                cell = pg.Rect(x, y, width, height)
                yield self.top + row * cols + col, cell
            row += 1

    def zoom(self, cols: int) -> NextScene:
        """Change the number of columns or hand over to the Hero scene."""
        if cols < MIN_COLS:
            return hero.Hero()
        self.resize(cols)
        return None

    def resize(self, cols: int) -> None:
        """Change the number of columns, keeping the selected game under the pointer."""
        self.cols = cols
        while self.cols > MIN_COLS and min(self.tile_size) < 1:
            self.cols -= 2
        self.shift = 0
        self.cache = {}
        self.top = self.pos
        mouse = pg.mouse.get_pos()
        self.top -= next(
            (pos - self.pos for pos, cell in self.cells() if cell.collidepoint(mouse)),
            0,
        )

    def select(self, pos: int) -> None:
        """Select the game at the given position."""
        self.pos = pos
        gamelist.current_game = pos % len(gamelist.games)

    def point(self, point: tuple[int, int]) -> bool:
        """Select the game under the mouse pointer; return False if there is none."""
        for pos, cell in self.cells():
            if cell.collidepoint(point):
                self.select(pos)
                return True
        return False

    def scroll_by(self, rows: int, cols: int = 0) -> None:
        """Scroll infinitely in all directions."""
        # TODO(JJ): Explain.
        if rows > 0:
            bottom_shift = self.bottom_shift()
            if self.shift != bottom_shift:
                rows -= 1
            self.shift = bottom_shift
        elif rows < 0:
            if self.shift:
                rows += 1
            self.shift = 0
        delta = rows * self.cols + cols
        self.top += delta
        self.select(self.pos + delta)
        self.point(pg.mouse.get_pos())

    @override
    def reshow(self) -> None:
        """Keep the current game in the same cell after the shown games changed."""
        offset = self.pos - self.top
        self.pos = gamelist.current_game
        self.top = self.pos - offset

    def handle_menu(self, menu: "Menu", event: pg.event.Event) -> bool:
        """Handle an event while the menu is open; return True if it was consumed."""
        if event.type == pg.MOUSEMOTION:
            highlighted = menu.item_at(event.pos)
            self.skip_frame = highlighted == menu.highlighted
            menu.highlighted = highlighted
            return True
        if event.type in (pg.KEYDOWN, pg.MOUSEBUTTONDOWN, pg.MOUSEWHEEL):
            # TODO(JJ): Handle Enter and its modifier keys the same way as Hero.
            self.menu = None
            if event.type == pg.MOUSEBUTTONDOWN and event.button == pg.BUTTON_LEFT:
                if menu.highlighted is not None:
                    self.play(MENU_ITEMS[menu.highlighted][2])
                return True
            return event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE
        return False

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Let the menu handle the event first, if it's open."""
        if self.menu and self.handle_menu(self.menu, event):
            return None
        return super().handle(event)

    @override
    def handle_mouse(self, event: pg.event.Event) -> NextScene:
        """Select the game under the pointer; play it or open the menu on click."""
        if event.type == pg.MOUSEMOTION:
            self.skip_frame = True
            self.point(event.pos)
        elif event.button == pg.BUTTON_LEFT and self.point(event.pos):
            self.play(pg.key.get_mods())
        elif event.button == pg.BUTTON_RIGHT and self.point(event.pos):
            self.open_menu(event.pos)
        return None

    def open_menu(self, pos: tuple[int, int]) -> None:
        """Open the menu of the current game at the given position."""
        self.menu = Menu(
            self.menu_font,
            gamelist.get_current_game(),
            pos,
            self.screen.get_rect(),
        )

    @override
    def handle_wheel(self, event: pg.event.Event) -> NextScene:
        """Zoom with Ctrl and the mouse wheel, or scroll with the wheel alone."""
        if pg.key.get_mods() & pg.KMOD_CTRL:
            if event.y:
                return self.zoom(self.cols - 2 * event.y)
        elif event.x or event.y:
            self.scroll_by(-event.y, event.x)
        return None

    @override
    def escape(self) -> NextScene:
        """Go back to Hero."""
        return hero.Hero()

    @override
    def navigate(self, event: pg.event.Event) -> NextScene:
        """Zoom, scroll, or jump to a random game in Hero, depending on the key."""
        if event.key == pg.K_SPACE:
            return hero.Hero(slideshow=True)
        if event.key in GRID_LARGER:
            return self.zoom(self.cols + 2)
        if event.key in GRID_SMALLER:
            return self.zoom(self.cols - 2)
        if event.key in GRID_SCROLLS:
            self.scroll_by(*GRID_SCROLLS[event.key])
        return None

    @override
    def update(self, screen: pg.Surface) -> NextScene:
        """Update the mouse pointer."""
        if self.menu and self.menu.highlighted is None:
            cursor = pg.SYSTEM_CURSOR_ARROW
        else:
            cursor = pg.SYSTEM_CURSOR_HAND
        if cursor != self.cursor:
            self.set_cursor(cursor)
        return super().update(screen)

    @override
    def draw(self, screen: pg.Surface) -> None:
        """Draw the grid."""
        if min(self.tile_size) < 1:
            self.resize(self.cols)
        games = gamelist.games
        cache: dict[tuple[Game, tuple[int, int], int | None], pg.Surface] = {}
        size = self.tile_size
        for pos, cell in self.cells():
            image_rect = pg.Rect((0, 0), size)
            image_rect.center = cell.center
            game = games[pos % len(games)]
            key = game, image_rect.size, cga.palette
            image = cache.get(key, self.cache.get(key))
            if image is None:
                title = game.get_titlescreen(image_rect.size)
                image = sharp_scale(cga.apply(title), image_rect.size)
            cache[key] = image
            screen.blit(image, image_rect)
        self.cache = cache

    @override
    def draw_overlays(self, screen: pg.Surface) -> None:
        """Draw the filter, the dot, the message, and the menu, if any."""
        super().draw_overlays(screen)
        if self.menu:
            self.menu.draw(screen)


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
        add_or_remove = "Remove from" if game.is_ready() else "Add to"
        self.labels = [label.format(add_or_remove) for label, _, _ in MENU_ITEMS]
        self.highlighted: int | None = None
        font.bold = True
        self.title = font.render(
            f"{game.title} ({game.year})", ANTIALIAS, self.TITLE_FOREGROUND
        )
        font.bold = False
        labels = max(font.size(label)[0] for label in self.labels)
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
        for item, (_, shortcut, _) in enumerate(MENU_ITEMS):
            label = self.labels[item]
            row = self.row(item)
            color = self.FOREGROUND
            if item == self.highlighted:
                screen.fill(self.HIGHLIGHT_BACKGROUND, row)
                color = self.HIGHLIGHT_FOREGROUND
            y = row.top + self.PADDING // 2
            screen.blit(self.font.render(label, ANTIALIAS, color), (x, y))
            screen.blit(self.font.render(shortcut, ANTIALIAS, color), (shortcut_x, y))
