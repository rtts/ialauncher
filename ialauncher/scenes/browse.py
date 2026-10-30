"""Base class for browsing title screens."""

import random
import shutil
import subprocess
from typing import override

import pygame as pg

from ialauncher import ega, options
from ialauncher.engine import NextScene
from ialauncher.game import EMULATOR_FAILED, Game, MetadataError
from ialauncher.gamelist import gamelist
from ialauncher.utils import find_emulator, show_error

from . import BLACK, CYAN, GRID_LARGER, GRID_SMALLER, MAGENTA, Scene, hero
from .download import Download
from .play import Play
from .starfield import Starfield
from .stars import Stars
from .unzip import Unzip

COMMAND_KEYS = {pg.K_SPACE} | GRID_LARGER | GRID_SMALLER
ARROW_KEYS = {pg.K_RIGHT, pg.K_LEFT, pg.K_DOWN, pg.K_UP}
BLINK = pg.event.custom_type()
BLINK_INTERVAL = 120
DOT_PULSE = (
    (),
    (),
    (),
    (),
    ((4, 4, 4, 4),),
    ((2, 2, 8, 8),),
    ((2, 0, 8, 12), (0, 2, 12, 8)),
    ((2, 2, 8, 8),),
)
IDLE = pg.event.custom_type()
INPUT_EVENTS = {pg.KEYDOWN, pg.MOUSEMOTION, pg.MOUSEBUTTONDOWN, pg.MOUSEWHEEL}
MESSAGE_EXPIRED = pg.event.custom_type()
MESSAGE_TIMEOUT = 1000
READY_MESSAGES = {None: "All", True: "Favorites", False: "Least favorites"}
NEXT_READY = {None: True, True: False, False: None}
SLOW_CYCLES = 300


class Browse(Scene):
    """Base class for browsing title screens."""

    def __init__(self) -> None:
        """Initialize."""
        self.message = ""
        self.message_until = 0
        self.skip_frame = False
        self.slideshow_running = False
        self.blinking = False
        self.dot_phase = 0
        super().__init__()

    @override
    def start(self) -> NextScene:
        """Restart the blink and idle timers."""
        self.blink(restart=True)
        pg.time.set_timer(IDLE, options.idle * 1000)
        return None

    @override
    def update(self) -> NextScene:
        """Draw the game(s) and everything on top of them.

        But first, show the game whose metadata.ini changed, if any.
        """
        if next_scene := self.reload_changed():
            return next_scene
        if self.skip_frame:
            self.skip_frame = False
            return None
        self.screen.fill(BLACK)
        self.draw()
        self.draw_overlays()
        return None

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Handle mouse and keyboard input, and start screensaver when idle."""
        next_scene = None
        if event.type in INPUT_EVENTS:
            pg.time.set_timer(IDLE, options.idle * 1000)
        if event.type == IDLE:
            playing = any(game.is_running() for game in gamelist.all_games)
            busy = self.slideshow_running or playing or Stars.is_running()
            busy = busy or not gamelist.games
            next_scene = None if busy else self.screensaver()
        elif event.type == BLINK:
            self.dot_phase = (self.dot_phase + 1) % len(DOT_PULSE)
        elif event.type == EMULATOR_FAILED:
            show_error(event.message)
        elif event.type in (pg.MOUSEMOTION, pg.MOUSEBUTTONDOWN):
            next_scene = self.handle_mouse(event)
        elif event.type == pg.MOUSEWHEEL:
            next_scene = self.handle_wheel(event)
        elif (
            event.type == pg.KEYDOWN
            and event.mod & pg.KMOD_SHIFT
            and pg.K_a <= event.key <= pg.K_z
        ):
            next_scene = self.shift_command(event.key)
        elif event.type == pg.KEYDOWN:
            next_scene = self.handle_key(event)
        self.blink()
        return next_scene

    def blink(self, *, restart: bool = False) -> None:
        """Run the blink timer while the slideshow runs or the filter is active."""
        blinking = self.slideshow_running or bool(gamelist.query)
        if restart or blinking != self.blinking:
            self.blinking = blinking
            self.dot_phase = 0
            pg.time.set_timer(BLINK, BLINK_INTERVAL if blinking else 0)

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

    def play(self, mod: int) -> NextScene:
        """Download the current game if needed and start it.

        With Ctrl, delete the gamedir if it exists, or create it if it
        doesn't exist. The UI calls this "Add to / Remove from favorites".
        """
        game = gamelist.get_current_game()
        if game is None:
            return None
        if mod & pg.KMOD_CTRL:
            return self.add_or_remove(game)
        return self.start_game(game, mod)

    def play_at_speed(self, cpu_cycles: int) -> NextScene:
        """Start the current DOSBox game with cpu_cycles, and remember it."""
        game = gamelist.get_current_game()
        if game and game.engine == "dosbox" and not game.is_running():
            game.set_cpu_cycles(cpu_cycles)
            return self.start_game(game, 0)
        return None

    def shift_command(self, key: int) -> NextScene:
        """Execute one of the Shift commands."""
        if key == pg.K_s:
            return self.play_at_speed(SLOW_CYCLES)
        if key == pg.K_e:
            self.edit_metadata()
        elif key == pg.K_a and (game := gamelist.get_current_game()):
            game.autoplayable = False
            game.save_metadata("autoplayable", "no")
            self.show_message("AUTOPLAYABLE = NO")
        return None

    @staticmethod
    def edit_metadata() -> None:
        """Open the current game's metadata.ini in Emacs, if it's installed."""
        game = gamelist.get_current_game()
        if game and (emacs := shutil.which("emacs")):
            subprocess.Popen([emacs, game.path / "metadata.ini"])  # noqa: S603

    def add_or_remove(self, game: Game) -> NextScene:
        """Delete the gamedir if it exists, or get the game ready if it doesn't."""
        if game.is_ready():
            game.reset()
            self.show_message("REMOVED FROM FAVORITES")
            return None
        self.show_message("ADDED TO FAVORITES")
        return Download(game, Unzip(game, self))

    def start_game(self, game: Game, mod: int) -> NextScene:
        """Start the game, after resetting it with Shift."""
        if game.is_running() or not find_emulator(game):
            return None
        if mod & pg.KMOD_SHIFT:
            game.reset()
        return self.launch(game, autorun=not mod & pg.KMOD_ALT)

    def launch(self, game: Game, *, autorun: bool) -> NextScene:
        """Get the game ready if needed, and play it alongside this scene."""
        play = Play(game, self, autorun=autorun, wait=False)
        return Download(game, Unzip(game, play))

    @override
    def get_events(self) -> list[pg.event.Event]:
        """Sleep until the next event."""
        return [pg.event.wait()]

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

    @property
    def typing(self) -> bool:
        """Whether the filter is being typed, so that Space types a space."""
        return self.message_visible and self.message == gamelist.query.upper()

    def handle_key(self, event: pg.event.Event) -> NextScene:
        """Handle key event.

        Keys shared among subclasses:
        - Plus: zoom in
        - Minus: zoom out
        - Space: start slideshow
        - Tab: toggle "favorites"
        - Any character: append to filter query
        - Backspace: end filtering
        - Esc: quit, or whatever escape() does instead
        """
        if event.key == pg.K_ESCAPE:
            return self.escape()
        typing = self.typing
        new_query = self.typeable(event) and event.key not in COMMAND_KEYS
        if new_query and gamelist.query and not typing:
            self.clear_filter()
        added = self.filter(event, typing=typing)
        if added:
            self.show_message(gamelist.query.upper())
            self.reshow()
        elif new_query:
            return None
        self.keystroke(event)
        if added:
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
        """Add the typed character to the filter.

        Space, plus and minus only add to the filter once it has been
        started with another key, and while it's being typed. Return
        whether the character was added.
        """
        if not self.typeable(event):
            return False
        if not typing and event.key in COMMAND_KEYS:
            return False
        gamelist.add_to_filter(event.unicode)
        return True

    @staticmethod
    def typeable(event: pg.event.Event) -> bool:
        """Return whether the keystroke types a character.

        Shift with a letter doesn't type, leaving those keys free for
        commands. Shift with anything else does, for characters like ^.
        """
        if event.mod & pg.KMOD_SHIFT and event.unicode.isalpha():
            return False
        return bool(event.unicode) and event.unicode.isprintable()

    def keystroke(self, event: pg.event.Event) -> None:
        """React to a keystroke that wasn't ignored."""

    def screensaver(self) -> Scene:
        """Sometimes leave it to stars.exe instead of the starfield."""
        if not random.randrange(20):  # noqa: S311
            return Stars(self)
        return Starfield(self)

    def reload_changed(self) -> NextScene:
        """Reload the games whose metadata.ini changed, and show the last one in Hero.

        Clear the filters, so that the game is shown.
        """
        changed = None
        for game in gamelist.changed_games():
            try:
                if game.reload_metadata():
                    changed = game
            except MetadataError as e:
                show_error(str(e))
        if not changed:
            return None
        gamelist.show_game(changed)
        return hero.Hero()

    def escape(self) -> NextScene:
        """Quit."""
        return False

    def navigate(self, event: pg.event.Event) -> NextScene:  # noqa: ARG002
        """Handle a key that isn't part of the filter."""
        return None

    def draw_overlays(self) -> None:
        """Draw the dots and the message, if any."""
        if self.slideshow_running:
            self.draw_dot(MAGENTA, right=True)
        if gamelist.query:
            self.draw_dot(CYAN, right=False)
        if self.message_visible:
            self.draw_message()

    def dot_area(self) -> pg.Rect:
        """Return the area in whose bottom corners the dots are drawn."""
        return self.screen.get_rect()

    def draw_dot(self, color: tuple[int, int, int], *, right: bool) -> None:
        """Draw a dot 16 pixels from the bottom right or left corner.

        The slideshow dot is on the right, the filter dot on the left.
        """
        area = self.dot_area()
        left = area.right - 28 if right else area.left + 16
        top = area.bottom - 28
        for x, y, width, height in DOT_PULSE[self.dot_phase]:
            self.screen.fill(color, (left + x, top + y, width, height))

    def draw_message(self, padding: tuple[int, int] = (8, 4)) -> None:
        """Draw the message in the middle of the screen."""
        image = ega.render(self.message, BLACK, MAGENTA, padding)
        self.screen.blit(image, image.get_rect(center=self.screen.get_rect().center))
