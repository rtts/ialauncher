import math

import pygame as pg

GRID_MARGIN = 5
FULLSCREEN_ASPECT_RATIO = 16 / 10
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


def letterbox(rect: pg.Rect) -> pg.Rect:
    """Return a letterboxed rect adhering to FULLSCREEN_ASPECT_RATIO."""
    width = min(rect.width, round(rect.height * FULLSCREEN_ASPECT_RATIO))
    height = min(rect.height, round(rect.width / FULLSCREEN_ASPECT_RATIO))
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
