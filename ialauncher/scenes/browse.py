"""Base class for browsing title screens."""

import random
from abc import abstractmethod
from functools import cached_property
from typing import override

import pygame as pg

from ialauncher import options
from ialauncher.engine import NextScene
from ialauncher.game import EMULATOR_FAILED, Game
from ialauncher.gamelist import gamelist
from ialauncher.utils import find_emulator, show_error

from . import BLACK, CYAN, FONT_FAMILY, GRID_LARGER, GRID_SMALLER, MAGENTA, Scene
from .download import Download
from .starfield import Starfield
from .stars import Stars

COMMAND_KEYS = {pg.K_SPACE} | GRID_LARGER | GRID_SMALLER
ARROW_KEYS = {pg.K_RIGHT, pg.K_LEFT, pg.K_DOWN, pg.K_UP}
BLINK = pg.event.custom_type()
BLINK_INTERVAL = 1000
IDLE = pg.event.custom_type()
INPUT_EVENTS = {pg.KEYDOWN, pg.MOUSEMOTION, pg.MOUSEBUTTONDOWN, pg.MOUSEWHEEL}
MESSAGE_EXPIRED = pg.event.custom_type()
MESSAGE_TIMEOUT = 1000
READY_MESSAGES = {None: "All", True: "Favorites", False: "Least favorites"}
NEXT_READY = {None: True, True: False, False: None}


class Browse(Scene):
    """Base class for browsing title screens."""

    def __init__(self) -> None:
        """Initialize."""
        self.message = ""
        self.message_until = 0
        self.skip_frame = False
        self.slideshow_running = False
        self.blinking = False
        self.dot_visible = False
        super().__init__()

    @override
    def run(self, screen: pg.Surface) -> NextScene:
        """Restart the blink and idle timers."""
        self.blink(restart=True)
        pg.time.set_timer(IDLE, options.idle * 1000)
        return super().run(screen)

    def blink(self, *, restart: bool = False) -> None:
        """Run the blink timer while the slideshow runs or the filter is active."""
        blinking = self.slideshow_running or bool(gamelist.query)
        if restart or blinking != self.blinking:
            self.blinking = blinking
            self.dot_visible = False
            pg.time.set_timer(BLINK, BLINK_INTERVAL if blinking else 0)

    @cached_property
    def message_font(self) -> pg.font.Font:
        """The font of the message."""
        return pg.font.SysFont(FONT_FAMILY, 20)

    def show_ready(self, *, ready: bool | None) -> None:
        """Show only the games that are (not) ready to play, or all games (None)."""
        gamelist.show_ready(ready=ready)
        self.reshow()

    def clear_filter(self) -> None:
        """Show all ready games again."""
        gamelist.clear_filter()
        self.reshow()

    def reshow(self) -> None:
        """Adjust to the shown games having changed."""

    def play(self, mod: int) -> None:
        """Download the current game if needed and start it.

        With Ctrl, delete the gamedir if it exists, or create it if it
        doesn't exist. The UI calls this "Add to / Remove from favorites".
        """
        game = gamelist.get_current_game()
        if mod & pg.KMOD_CTRL:
            self.add_or_remove(game)
        else:
            self.start(game, mod)

    def add_or_remove(self, game: Game) -> None:
        """Delete the gamedir if it exists, or create it if it doesn't exist."""
        if game.is_ready():
            game.reset()
        else:
            self.download(game)

    def start(self, game: Game, mod: int) -> None:
        """Download the game if needed and start it."""
        if game.is_running():
            return
        if not find_emulator(game):
            return
        if mod & pg.KMOD_SHIFT:
            game.reset()
        if not game.is_ready():
            self.download(game)
        if game.is_ready():
            game.emulator = game.start(autorun=not mod & pg.KMOD_ALT)

    def download(self, game: Game) -> None:
        """Download the game while showing its progress."""
        Download(game).run(self.screen)

    @override
    def get_events(self) -> list[pg.event.Event]:
        """Sleep until the next event."""
        return [pg.event.wait()]

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Handle mouse and keyboard input, and start screensaver when idle."""
        next_scene = None
        if event.type in INPUT_EVENTS:
            pg.time.set_timer(IDLE, options.idle * 1000)
        if event.type == IDLE:
            playing = any(game.is_running() for game in gamelist.all_games)
            busy = self.slideshow_running or playing or Stars.is_running()
            next_scene = None if busy else self.screensaver()
        elif event.type == BLINK:
            self.dot_visible = self.blinking and not self.dot_visible
        elif event.type == EMULATOR_FAILED:
            show_error(event.message)
        elif event.type in (pg.MOUSEMOTION, pg.MOUSEBUTTONDOWN):
            next_scene = self.handle_mouse(event)
        elif event.type == pg.MOUSEWHEEL:
            next_scene = self.handle_wheel(event)
        elif event.type == pg.KEYDOWN:
            next_scene = self.handle_key(event)
        self.blink()
        return next_scene

    def handle_mouse(self, event: pg.event.Event) -> NextScene:  # noqa: ARG002
        """Handle a mouse movement or click."""
        self.skip_frame = True
        return None

    def handle_wheel(self, event: pg.event.Event) -> NextScene:  # noqa: ARG002
        """Handle the mouse wheel."""
        self.skip_frame = True
        return None

    def show_message(self, message: str) -> None:
        """Show a message that disappears by itself."""
        self.message = message
        self.message_until = pg.time.get_ticks() + MESSAGE_TIMEOUT
        pg.time.set_timer(MESSAGE_EXPIRED, MESSAGE_TIMEOUT, loops=1)

    @property
    def message_visible(self) -> bool:
        """Whether the message is visible."""
        return pg.time.get_ticks() < self.message_until

    def handle_key(self, event: pg.event.Event) -> NextScene:
        """Handle key event.

        Keys shared among subclasses:
        - Plus: zoom in
        - Minus: zoom out
        - Space: start slideshow
        - Tab: toggle "favorites"
        - Any character: append to filter query
        - Backspace: end filtering
        - Esc: end filtering or end scene
        """
        if event.key == pg.K_ESCAPE:
            if not gamelist.query:
                return self.escape()
            self.clear_filter()
            return None
        typing = self.message_visible and self.message == gamelist.query
        new_query = self.typeable(event) and event.key not in COMMAND_KEYS
        if new_query and gamelist.query and not typing:
            self.clear_filter()
        added = self.filter(event, typing=typing)
        if added:
            self.show_message(gamelist.query)
            self.reshow()
        elif new_query:
            return None
        self.keystroke(event)
        if added and event.key != pg.K_SPACE:
            return None
        if event.key == pg.K_BACKSPACE:
            self.clear_filter()
        elif event.key == pg.K_TAB:
            self.show_ready(ready=NEXT_READY[gamelist.ready])
            self.show_message(READY_MESSAGES[gamelist.ready])
        next_scene = self.navigate(event)
        if event.key in ARROW_KEYS:
            self.show_ready(ready=gamelist.ready)
        return next_scene

    def filter(self, event: pg.event.Event, *, typing: bool) -> bool:
        """Add the typed character to the filter if any game matches.

        Space, plus and minus only add to the filter once it has been
        started with another key, and while it's being typed. Return
        whether the character was added.
        """
        if not self.typeable(event):
            return False
        if not typing and event.key in COMMAND_KEYS:
            return False
        return gamelist.add_to_filter(event.unicode)

    @staticmethod
    def typeable(event: pg.event.Event) -> bool:
        """Return whether the keystroke types a character."""
        return bool(event.unicode) and event.unicode.isprintable()

    def keystroke(self, event: pg.event.Event) -> None:
        """React to a keystroke that wasn't ignored."""

    def screensaver(self) -> Scene:
        """Sometimes leave it to stars.exe instead of the starfield."""
        if not random.randrange(20) and (stars := Stars.start(self)):  # noqa: S311
            return stars
        return Starfield(self)

    @abstractmethod
    def wake(self) -> Scene:
        """Return the scene to show when the screensaver collides with a game."""

    def escape(self) -> NextScene:
        """Handle Escape when there is no filter to clear."""
        return False

    def navigate(self, event: pg.event.Event) -> NextScene:  # noqa: ARG002
        """Handle a key that isn't part of the filter."""
        return None

    @override
    def update(self, screen: pg.Surface) -> NextScene:
        """Draw the game(s) and everything on top of them."""
        if self.skip_frame:
            self.skip_frame = False
            return None
        screen.fill(BLACK)
        self.draw(screen)
        self.draw_overlays(screen)
        return None

    def draw(self, screen: pg.Surface) -> None:
        """Draw the game(s)."""

    def draw_overlays(self, screen: pg.Surface) -> None:
        """Draw the dots and the message, if any."""
        if self.dot_visible and self.slideshow_running:
            self.draw_dot(screen, MAGENTA, right=True)
        if self.dot_visible and gamelist.query:
            self.draw_dot(screen, CYAN, right=False)
        if self.message_visible:
            self.draw_message(screen)

    def dot_area(self, screen: pg.Surface) -> pg.Rect:
        """Return the area in whose bottom corners the dots are drawn."""
        return screen.get_rect()

    def draw_dot(
        self,
        screen: pg.Surface,
        color: tuple[int, int, int],
        *,
        right: bool,
        size: int = 8,
        margin: int = 16,
    ) -> None:
        """Draw a dot in the bottom right or left corner.

        The slideshow dot is on the right, the filter dot on the left.
        """
        rect = pg.Rect(0, 0, size, size)
        area = self.dot_area(screen)
        if right:
            rect.bottomright = area.bottomright
            rect.move_ip(-margin, -margin)
        else:
            rect.bottomleft = area.bottomleft
            rect.move_ip(margin, -margin)
        pg.draw.ellipse(screen, color, rect)

    def draw_message(
        self, screen: pg.Surface, padding: tuple[int, int] = (24, 16)
    ) -> None:
        """Draw the message in the middle of the screen."""
        image = self.message_font.render(self.message, antialias=True, color=BLACK)
        rect = image.get_rect(center=screen.get_rect().center)
        screen.fill(MAGENTA, rect.inflate(2 * padding[0], 2 * padding[1]))
        screen.blit(image, rect)
