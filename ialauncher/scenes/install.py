"""Title screen with a dialog that asks where to store the games."""

from pathlib import Path
from typing import override

import pygame as pg

from ialauncher import ega, options
from ialauncher.bios import speaker
from ialauncher.config import default_games_dir, read_games_dir, write_games_dir
from ialauncher.engine import NextScene
from ialauncher.utils import show_error

from . import BLACK, WHITE, Scene, TitleScreen

BLUE = (0, 0, 170)
RED = (170, 0, 0)
YELLOW = (255, 255, 85)
QUESTION = (
    "Welcome to IA Launcher!",
    "",
    "In which directory would you like to store your games?",
)
CONFIRMATION = (
    ("That directory does not exist! Create it?", WHITE),
    ("", WHITE),
    ("Press 'Y' to create, 'N' to retype directory.", YELLOW),
)
PROMPT = "\x10 "
COLUMNS = 56
CHAR_WIDTH, CHAR_HEIGHT = 8, 14
PADDING = 16, 12
BORDER = 4
SHADOW = 8
BLINK_INTERVAL = 250
ENTER_KEYS = {pg.K_RETURN, pg.K_KP_ENTER}


class Install(TitleScreen):
    """Ask where to store the games, in front of the title screen with progress bar."""

    def __init__(self, then: Scene) -> None:
        """Prefill the saved or default directory and put the cursor at the end."""
        self.then = then
        self.games_dir = read_games_dir()
        self.text = str(self.games_dir or default_games_dir())
        self.cursor = len(self.text)
        self.offset = 0
        self.blink_start = 0
        self.confirming = False
        super().__init__()

    @override
    def start(self) -> NextScene:
        """Continue right away if the games directory is saved and exists, or bleep."""
        if self.games_dir and self.games_dir.is_dir():
            options.games_dir = self.games_dir
            return self.then
        speaker.bleep()
        return None

    @override
    def update(self) -> NextScene:
        """Draw the title screen with an empty progress bar, and the dialog on top."""
        self.draw_progress(0)
        return None

    @override
    def draw_overlay(self, canvas: pg.Surface) -> None:
        """Draw the confirmation, or else the dialog."""
        if self.confirming:
            self.draw_confirmation(canvas)
        else:
            self.draw_dialog(canvas)

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Edit the directory, save it on Enter, and quit on Escape.

        If the directory doesn't exist, ask first whether to create it.
        """
        if event.type != pg.KEYDOWN:
            return None
        self.blink_start = pg.time.get_ticks()
        if event.key == pg.K_ESCAPE:
            return False
        if self.confirming:
            return self.confirm(event)
        if event.key in ENTER_KEYS:
            return self.enter()
        self.edit(event)
        return None

    def enter(self) -> NextScene:
        """Save an existing directory, or ask whether to create it, unless blank."""
        if not self.text.strip():
            return None
        if self.chosen_dir().is_dir():
            return self.save()
        self.confirming = True
        speaker.bloop()
        return None

    def confirm(self, event: pg.event.Event) -> NextScene:
        """Create the directory with Y, or go back to typing it with N."""
        if event.key == pg.K_y:
            speaker.bleep()
            return self.save()
        if event.key == pg.K_n:
            self.confirming = False
            speaker.bleep()
        return None

    def chosen_dir(self) -> Path:
        """Return the typed directory as an absolute path."""
        return Path(self.text).expanduser().absolute()

    def edit(self, event: pg.event.Event) -> None:
        """Move the cursor, delete a character, or type one."""
        text, cursor = self.text, self.cursor
        if event.key == pg.K_BACKSPACE and cursor:
            self.text = text[: cursor - 1] + text[cursor:]
            self.cursor -= 1
        elif event.key == pg.K_DELETE:
            self.text = text[:cursor] + text[cursor + 1 :]
        elif event.key == pg.K_LEFT:
            self.cursor = max(0, cursor - 1)
        elif event.key == pg.K_RIGHT:
            self.cursor = min(len(text), cursor + 1)
        elif event.key == pg.K_HOME:
            self.cursor = 0
        elif event.key == pg.K_END:
            self.cursor = len(text)
        elif event.unicode and event.unicode.isprintable():
            self.text = text[:cursor] + event.unicode + text[cursor:]
            self.cursor += len(event.unicode)

    def save(self) -> NextScene:
        """Create the directory and save it, then continue, or show why that failed."""
        games_dir = self.chosen_dir()
        try:
            games_dir.mkdir(parents=True, exist_ok=True)
            write_games_dir(games_dir)
        except OSError as e:
            show_error(f"Could not save {games_dir}\n\n{e}")
            self.confirming = False
            return None
        options.games_dir = games_dir
        return self.then

    def draw_dialog(self, canvas: pg.Surface) -> None:
        """Draw the question and the directory, with a blinking cursor."""
        lines = [(line, WHITE) for line in QUESTION]
        lines += [("", WHITE), (PROMPT + self.visible_text(), WHITE)]
        left, top = draw_box(canvas, lines, BLUE, COLUMNS)
        if (pg.time.get_ticks() - self.blink_start) // BLINK_INTERVAL % 2 == 0:
            column = len(PROMPT) + self.cursor - self.offset
            cursor = pg.Rect(0, 0, CHAR_WIDTH, 2)
            cursor.bottomleft = (
                left + column * CHAR_WIDTH,
                top + len(lines) * CHAR_HEIGHT - 1,
            )
            canvas.fill(WHITE, cursor)

    @staticmethod
    def draw_confirmation(canvas: pg.Surface) -> None:
        """Ask whether to create the directory."""
        columns = max(len(line) for line, _ in CONFIRMATION)
        draw_box(canvas, list(CONFIRMATION), RED, columns, centered=True)

    def visible_text(self) -> str:
        """Return the part of the directory that fits, scrolled to show the cursor."""
        width = COLUMNS - len(PROMPT) - 1
        self.offset = min(self.offset, self.cursor)
        self.offset = max(self.offset, self.cursor - width)
        return self.text[self.offset : self.offset + width + 1]


def draw_box(
    canvas: pg.Surface,
    lines: list[tuple[str, tuple[int, int, int]]],
    background: tuple[int, int, int],
    columns: int,
    *,
    centered: bool = False,
) -> tuple[int, int]:
    """Draw colored lines in a box with a shadow, and return the text's corner."""
    box = pg.Rect(
        0,
        0,
        columns * CHAR_WIDTH + 2 * PADDING[0],
        len(lines) * CHAR_HEIGHT + 2 * PADDING[1],
    )
    box.center = canvas.get_rect().center
    canvas.fill(BLACK, box.move(SHADOW, SHADOW))
    canvas.fill(background, box)
    pg.draw.rect(canvas, WHITE, box.inflate(-2 * BORDER, -2 * BORDER), 1)
    left, top = box.left + PADDING[0], box.top + PADDING[1]
    for row, (line, color) in enumerate(lines):
        if not line:
            continue
        image = ega.render(line, color, background, scale=1)
        x = box.centerx - image.get_width() // 2 if centered else left
        canvas.blit(image, (x, top + row * CHAR_HEIGHT))
    return left, top
