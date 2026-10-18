"""Helper functions."""

import ssl
from typing import TYPE_CHECKING

import pygame as pg

from ialauncher.emulator import EmulatorError

if TYPE_CHECKING:
    from ialauncher.game import Game

GRID_MARGIN = 5
ASPECT_RATIO = 4 / 3


def grid_margin(cols: int) -> int:
    """Return the minimum margin around each tile."""
    return max(1, round(GRID_MARGIN * 3 / cols))


def letterbox(rect: pg.Rect) -> pg.Rect:
    """Return the largest 4:3 rect centered within the rect."""
    width = min(rect.width, round(rect.height * ASPECT_RATIO))
    height = min(rect.height, round(rect.width / ASPECT_RATIO))
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
