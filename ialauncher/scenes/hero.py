"""A single title screen, full size, with an optional slideshow."""

from typing import TYPE_CHECKING, override

import pygame as pg

from ialauncher import options
from ialauncher.cga import cga
from ialauncher.engine import NextScene
from ialauncher.game import Game
from ialauncher.gamelist import gamelist
from ialauncher.utils import letterbox, sharp_scale

from . import GRID_LARGER, grid
from .browse import Browse
from .crt import CRT
from .download import Download
from .play import Autoplay, Play
from .unzip import Unzip

if TYPE_CHECKING:
    from collections.abc import Callable

ADVANCE = pg.event.custom_type()
KEEP_SLIDESHOW = {pg.K_ESCAPE, pg.K_TAB, pg.K_BACKSPACE}


class Hero(Browse):
    """A single title screen, full size, with an optional slideshow.

    After the screensaver collides with a star, show the title screen
    for --slideshow seconds, then unzip, start the game, terminate it
    after --autoplay seconds, and show the next screensaver.

    With the slideshow enabled, do the same without the screensaver.
    """

    def __init__(self, *, slideshow: bool = False, screensaver: bool = False) -> None:
        """Initialize."""
        super().__init__()
        self.slideshow_running = slideshow and options.slideshow > 0
        game = gamelist.get_current_game()
        self.after_screensaver = bool(screensaver and game and Autoplay.qualifies(game))
        self.cache: dict[tuple[Game, tuple[int, int], int | None], pg.Surface] = {}
        self.handlers: dict[int, Callable[[], None]] = {
            pg.K_RIGHT: gamelist.next_game,
            pg.K_LEFT: gamelist.previous_game,
            pg.K_DOWN: gamelist.next_game,
            pg.K_UP: gamelist.previous_game,
        }

    @override
    def start(self) -> NextScene:
        """Start the slideshow timer if needed."""
        self.set_slideshow(enabled=self.slideshow_running)
        return super().start()

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Switch off the CRT when the slideshow advances, and autoplay the game.

        Switch the CRT back on with the next game, or after the
        screensaver, continue with the screensaver.
        """
        if event.type != ADVANCE:
            return super().handle(event)
        game = gamelist.get_current_game()
        if self.after_screensaver:
            self.after_screensaver = False
            then = self.screensaver()
        else:
            gamelist.random_game()
            then = CRT(self, on=True)
        if game and game.autoplayable and options.autoplay:
            then = Unzip(game, Autoplay(game, then))
        return CRT(then, on=False)

    @override
    def stop(self) -> None:
        """Stop the slideshow timer."""
        pg.time.set_timer(ADVANCE, 0)

    @override
    def intercept(self, event: pg.event.Event) -> bool:
        """Clear filter and jump to a random game after switching CGA mode."""
        if not super().intercept(event):
            return False
        self.clear_filter()
        gamelist.random_game()
        self.set_slideshow(enabled=True)
        return True

    def set_slideshow(self, *, enabled: bool) -> None:
        """Start or stop the slideshow and the accompanying blinker.

        The timer also runs once after the screensaver, even without the
        slideshow.
        """
        self.slideshow_running = enabled and options.slideshow > 0
        if self.slideshow_running or self.after_screensaver:
            pg.time.set_timer(ADVANCE, max(1, options.slideshow * 1000))
        else:
            pg.time.set_timer(ADVANCE, 0)
        self.blink(restart=True)

    @override
    def handle_wheel(self, event: pg.event.Event) -> NextScene:
        """Zoom out to the grid with Ctrl and the mouse wheel."""
        if pg.key.get_mods() & pg.KMOD_CTRL and event.y < 0:
            return grid.Grid()
        return super().handle_wheel(event)

    @override
    def keystroke(self, event: pg.event.Event) -> None:
        """Stop the slideshow on most keystrokes, and after the screensaver.

        Space starts it, unless it typed a space into the filter.
        """
        if event.key not in KEEP_SLIDESHOW:
            self.after_screensaver = False
            self.set_slideshow(enabled=event.key == pg.K_SPACE and not self.typing)

    @override
    def navigate(self, event: pg.event.Event) -> NextScene:
        """Zoom out, start the game, advance the slideshow, or move to another game."""
        if event.key in GRID_LARGER:
            return grid.Grid()
        if event.key == pg.K_RETURN:
            return self.play(event.mod)
        if event.key == pg.K_SPACE:
            pg.event.post(pg.event.Event(ADVANCE))
        elif handler := self.handlers.get(event.key):
            handler()
        return None

    @override
    def launch(self, game: Game, *, autorun: bool) -> NextScene:
        """Switch off the CRT, get the game ready and play it, and switch it on."""
        play = Play(game, CRT(self, on=True), autorun=autorun)
        return CRT(Download(game, Unzip(game, play)), on=False)

    @override
    def draw(self) -> None:
        """Draw the title screen of the current game, letterboxed, if any."""
        game = gamelist.get_current_game()
        if game is None:
            return
        rect = letterbox(self.screen.get_rect())
        key = game, rect.size, cga.palette
        image = self.cache.get(key)
        if image is None:
            title = pg.image.load(game.titlescreen)
            image = sharp_scale(cga.apply(title), rect.size)
        self.cache = {key: image}
        self.screen.blit(image, rect)

    @override
    def dot_area(self) -> pg.Rect:
        """Draw the dots in the corners of the title screen."""
        return letterbox(self.screen.get_rect())
