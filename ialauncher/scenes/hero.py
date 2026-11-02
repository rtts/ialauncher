"""A single title screen, full size, with an optional slideshow."""

from typing import TYPE_CHECKING, override

import pygame as pg

from ialauncher import options
from ialauncher.cga import cga
from ialauncher.engine import NextScene
from ialauncher.game import Game
from ialauncher.gamelist import gamelist
from ialauncher.utils import find_emulator, letterbox, sharp_scale

from . import GRID_LARGER, grid
from .browse import ARROW_KEYS, Browse
from .crt import CRToff, CRTon
from .dissolve import Dissolve
from .download import Download
from .play import Autoplay, Play
from .record import Record
from .unzip import Unzip

if TYPE_CHECKING:
    from collections.abc import Callable

ADVANCE = pg.event.custom_type()
SLIDESHOW_KEYS = {pg.K_SPACE, pg.K_RETURN} | ARROW_KEYS | GRID_LARGER
TIMED_KEYS: dict[int, type[Autoplay | Record]] = {pg.K_a: Autoplay, pg.K_r: Record}


class Hero(Browse):
    """A single title screen, full size, with an optional slideshow.

    After the screensaver collides with a star, show the title screen
    for --slideshow seconds, then autoplay the game, and show the next
    screensaver.

    With the slideshow enabled, do the same without the screensaver.
    """

    def __init__(self, *, slideshow: bool = False, screensaver: bool = False) -> None:
        """Initialize."""
        super().__init__()
        self.slideshow_running = slideshow and options.slideshow > 0
        game = gamelist.get_current_game()
        self.after_screensaver = bool(
            screensaver and game and options.autoplay and Autoplay.qualifies(game)
        )
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
        screensaver, continue with the screensaver. When the game can't
        be autoplayed, dissolve into the next game instead.

        Ctrl-A autoplays the game right away, Ctrl-R records it, and
        Ctrl-Shift-R resets the game before recording it.
        """
        ctrl = event.type == pg.KEYDOWN and event.mod & pg.KMOD_CTRL
        if ctrl and (scene := TIMED_KEYS.get(event.key)):
            reset = scene is Record and bool(event.mod & pg.KMOD_SHIFT)
            return self.play_timed(scene, reset=reset)
        if event.type != ADVANCE:
            return super().handle(event)
        game = gamelist.get_current_game()
        autoplay = bool(game and options.autoplay and Autoplay.qualifies(game))
        if self.after_screensaver:
            self.after_screensaver = False
            then = self.screensaver()
        else:
            gamelist.random_game()
            if not autoplay:
                return Dissolve(self)
            then = CRTon(self)
        if game and autoplay:
            then = Unzip(game, Autoplay(game, then), quiet=True)
        return CRToff(then)

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
    def keystroke(self, event: pg.event.Event, *, typed: bool) -> None:
        """Stop the slideshow and reset self.after_screensaver on certain keys."""
        if typed or event.key in SLIDESHOW_KEYS:
            self.after_screensaver = False
            self.set_slideshow(enabled=event.key == pg.K_SPACE and not typed)

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
        play = Play(game, CRTon(self), autorun=autorun)
        return CRToff(Download(game, Unzip(game, play)))

    def play_timed(
        self, scene: type[Autoplay | Record], *, reset: bool = False
    ) -> NextScene:
        """Unzip the game if needed, and autoplay or record it with the CRT off.

        Like the slideshow, never download the game.
        """
        game = gamelist.get_current_game()
        if game is None or game.is_running() or not game.is_downloaded():
            return None
        if scene is Autoplay and not Autoplay.qualifies(game):
            return None
        if not find_emulator(game):
            return None
        if reset:
            game.reset()
        return CRToff(Unzip(game, scene(game, CRTon(self))))

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
