"""A single title screen, full size, with an optional slideshow or autoplay."""

from typing import TYPE_CHECKING, override

import pygame as pg

from ialauncher import options
from ialauncher.cga import cga
from ialauncher.emulator import EmulatorError, get_dosbox_command
from ialauncher.engine import NextScene
from ialauncher.game import Emulator, Game
from ialauncher.gamelist import gamelist
from ialauncher.utils import letterbox, sharp_scale

from . import BLACK, GRID_LARGER, Blackout, Scene, grid
from .browse import Browse

if TYPE_CHECKING:
    from collections.abc import Callable

ADVANCE = pg.event.custom_type()
KEEP_SLIDESHOW = {pg.K_ESCAPE, pg.K_TAB, pg.K_BACKSPACE}
TITLE_DURATION = 1000  # milliseconds


class Hero(Browse):
    """A single title screen, full size, with an optional slideshow or autoplay."""

    def __init__(self, *, slideshow: bool = False, autoplay: bool = False) -> None:
        """Initialize."""
        super().__init__()
        if slideshow:
            gamelist.random_game()
        self.autoplay = autoplay
        self.slideshow_running = slideshow and options.slideshow > 0
        self.cache: dict[tuple[Game, tuple[int, int], int | None], pg.Surface] = {}
        self.handlers: dict[int, Callable[[], None]] = {
            pg.K_RIGHT: gamelist.next_game,
            pg.K_LEFT: gamelist.previous_game,
            pg.K_DOWN: gamelist.next_game,
            pg.K_UP: gamelist.previous_game,
            pg.K_SPACE: gamelist.random_game,
        }

    @override
    def run(self, screen: pg.Surface) -> NextScene:
        """Autoplay the current game once, if it qualifies.

        Otherwise, start slideshow timer if needed, and stop it when the
        scene exits.
        """
        if self.autoplay:
            self.autoplay = False
            if game := autoplay_game():
                return Autoplay(game, self)
        self.set_slideshow(enabled=self.slideshow_running)
        try:
            return super().run(screen)
        finally:
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
        """Start or stop the slideshow and the accompanying blinker."""
        self.slideshow_running = enabled and options.slideshow > 0
        running = self.slideshow_running
        pg.time.set_timer(ADVANCE, options.slideshow * 1000 if running else 0)
        self.blink(restart=True)

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Advance the slideshow."""
        if event.type == ADVANCE:
            gamelist.random_game()
        return super().handle(event)

    @override
    def handle_wheel(self, event: pg.event.Event) -> NextScene:
        """Zoom out to the grid with Ctrl and the mouse wheel."""
        if pg.key.get_mods() & pg.KMOD_CTRL and event.y < 0:
            return grid.Grid()
        return super().handle_wheel(event)

    @override
    def keystroke(self, event: pg.event.Event) -> None:
        """Stop the slideshow on most keystrokes."""
        if event.key not in KEEP_SLIDESHOW:
            self.set_slideshow(enabled=event.key == pg.K_SPACE)

    @override
    def navigate(self, event: pg.event.Event) -> NextScene:
        """Zoom out, start the game, or move to another game."""
        if event.key in GRID_LARGER:
            return grid.Grid()
        if event.key == pg.K_RETURN:
            self.play(event.mod)
        elif handler := self.handlers.get(event.key):
            handler()
        return None

    @override
    def wake(self) -> Scene:
        """Autoplay the game the screensaver collided with."""
        return Hero(autoplay=True)

    @override
    def draw(self, screen: pg.Surface) -> None:
        """Draw the title screen of the current game, letterboxed."""
        game = gamelist.get_current_game()
        rect = letterbox(screen.get_rect())
        key = game, rect.size, cga.palette
        image = self.cache.get(key)
        if image is None:
            title = pg.image.load(game.titlescreen)
            image = sharp_scale(cga.apply(title), rect.size)
        self.cache = {key: image}
        screen.blit(image, rect)

    @override
    def dot_area(self, screen: pg.Surface) -> pg.Rect:
        """Draw the dots in the corners of the title screen."""
        return letterbox(screen.get_rect())


class Autoplay(Blackout):
    """The title screen for a second, then a black screen behind the game."""

    def __init__(self, game: Game, hero: Hero) -> None:
        """Unzip the game first, if needed."""
        super().__init__()
        self.game = game
        self.hero = hero
        self.emulator: Emulator | None = None
        self.title_until = pg.time.get_ticks() + TITLE_DURATION
        self.deadline = 0
        self.unzipping = not game.is_ready()
        if self.unzipping:
            game.download()

    @override
    def run(self, screen: pg.Surface) -> NextScene:
        """Stop unzipping or close DOSBox when the scene exits."""
        try:
            return super().run(screen)
        finally:
            if self.unzipping and (thread := self.game.download_thread):
                thread.cancel()
            if self.emulator is not None:
                self.emulator.stop()

    @override
    def update(self, screen: pg.Surface) -> NextScene:
        """Start the game once it's unzipped, and continue when time is up.

        Continue with the screensaver, or with Hero if the game can't start.
        """
        if pg.time.get_ticks() < self.title_until:
            screen.fill(BLACK)
            self.hero.draw(screen)
            return None
        super().update(screen)
        game = self.game
        if self.emulator is None:
            if self.unzipping and (thread := game.download_thread):
                if thread.is_alive():
                    return None
                self.unzipping = False
            if not game.is_ready():
                return self.hero
            self.emulator = game.emulator = game.start()
            self.deadline = pg.time.get_ticks() + options.autoplay * 1000
            return None
        if self.emulator.is_alive() and pg.time.get_ticks() < self.deadline:
            return None
        return self.hero.screensaver()


def autoplay_game() -> Game | None:
    """Return the current game if it qualifies to autoplay."""
    if not options.autoplay:
        return None
    game = gamelist.get_current_game()
    if game.engine != "dosbox" or not game.emulator_start:
        return None
    try:
        get_dosbox_command()
    except EmulatorError:
        return None
    return game if game.is_downloaded() else None
