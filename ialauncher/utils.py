"""Helper functions."""

import math
import ssl
from typing import TYPE_CHECKING

import pygame as pg

from ialauncher.emulator import EmulatorError, is_dosbox_staging

if TYPE_CHECKING:
    from ialauncher.game import Game

GRID_MARGIN = 5
TILE_ASPECT_RATIO = 3 / 2


def grid_margin(cols: int) -> int:
    """Return the margin around each tile."""
    return max(1, round(GRID_MARGIN * 3 / cols))


def grid_rows(cols: int, size: tuple[int, int]) -> int:
    """Return the number of rows that best approximates TILE_ASPECT_RATIO."""
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


def fullscreen_aspect_ratio() -> float:
    """Return the aspect ratio of a 320x200 game in fullscreen DOSBox.

    DOSBox shows square pixels (16:10), but DOSBox Staging stretches
    them vertically like a CRT monitor did (4:3).
    """
    return 4 / 3 if is_dosbox_staging() else 16 / 10


def letterbox(rect: pg.Rect, ratio: float | None = None) -> pg.Rect:
    """Return a letterboxed rect adhering to the ratio.

    The ratio defaults to the fullscreen aspect ratio.
    """
    ratio = ratio or fullscreen_aspect_ratio()
    width = min(rect.width, round(rect.height * ratio))
    height = min(rect.height, round(rect.width / ratio))
    letterboxed = pg.Rect(0, 0, width, height)
    letterboxed.center = rect.center
    return letterboxed


def gradient(
    size: tuple[int, int], start: tuple[int, int, int], end: tuple[int, int, int]
) -> pg.Surface:
    """Return a surface filled with a horizontal gradient."""
    width, height = size
    surface = pg.Surface(size)
    for x in range(width):
        color = pg.Color(start).lerp(end, x / max(width - 1, 1))
        pg.draw.line(surface, color, (x, 0), (x, height - 1))
    return surface


def show_error(message: str) -> None:
    """Show the error to the user."""
    print(message)
    if hasattr(pg.display, "message_box"):  # n/a in pygame
        pg.display.message_box("IA Launcher", message, message_type="error")


def find_emulator(game: "Game") -> bool:
    """Return whether the game's emulator is correctly installed."""
    try:
        game.get_emulator()
    except EmulatorError as e:
        show_error(str(e).strip())
        return False
    return True


def tls_context() -> ssl.SSLContext:
    """Return a context that also accepts older root certificates.

    Since Python 3.13, strict mode rejects old roots like the Go Daddy
    Class 2 CA, which Windows installs when you visit archive.org in
    your browser.
    """
    context = ssl.create_default_context()
    context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return context
