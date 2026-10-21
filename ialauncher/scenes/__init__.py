"""The scenes of IA Launcher.

It starts with Loading, which hands over to Hero. Hero and Grid hand
over to each other, and both run Download to download a game.
"""

from functools import cached_property
from pathlib import Path
from typing import override

import pygame as pg

from ialauncher import engine
from ialauncher.cheats import cheat
from ialauncher.engine import NextScene
from ialauncher.game import EMULATOR_FAILED, Game
from ialauncher.gamelist import LOADING_FAILED, gamelist
from ialauncher.utils import find_emulator, gradient, letterbox, sharp_scale, show_error

CYAN = (0, 204, 255)
MAGENTA = (255, 0, 204)
BLACK = (0, 0, 0)
ANTIALIAS = True
GRID_LARGER = {pg.K_MINUS, pg.K_KP_MINUS}
GRID_SMALLER = {pg.K_PLUS, pg.K_EQUALS, pg.K_KP_PLUS}
COMMAND_KEYS = {pg.K_SPACE} | GRID_LARGER | GRID_SMALLER
ARROW_KEYS = {pg.K_RIGHT, pg.K_LEFT, pg.K_DOWN, pg.K_UP}
BLINK = pg.event.custom_type()
BLINK_INTERVAL = 1000
MESSAGE_EXPIRED = pg.event.custom_type()
MESSAGE_TIMEOUT = 1000
READY_MESSAGES = {None: "All", True: "Favorites", False: "Least favorites"}
NEXT_READY = {None: True, True: False, False: None}
FONT_FAMILY = "dejavusans,liberationsans,arial,helvetica,sans"


class Scene(engine.Scene):
    """Base class for the scenes of IA Launcher."""

    @override
    def intercept(self, event: pg.event.Event) -> bool:
        """Quit with an error message when a game failed to load."""
        if event.type == LOADING_FAILED:
            show_error(event.message)
            pg.event.post(pg.event.Event(pg.QUIT))
        return cheat(event)


class TitleScreen(Scene):
    """Storytime.

    My original games launcher was a blue menu with twelve numbered
    entries, and I knew every one of them by heart. 3 was Commander
    Keen. 7 was Prince of Persia. 11 was a flight simulator, and only
    once did I manage to get the plane off the runway. On Saturday
    mornings, I would sneak out of my bedroom before anyone else was
    awake and switch on the 486. The blue glow of the menu lit up my
    happy young face until I pressed 1: Duke Nukem.

    Then, one evening in the winter of 1992, my father came home with
    a stack of floppy disks and a smile from ear to ear. He shut
    himself in the study for hours. At bedtime he came up to my room,
    sat on the edge of my bed, and whispered: "Tomorrow, you're going
    to fly through space."

    I didn't sleep that night. I could already see the spaceship. A
    cockpit with illuminated buttons everywhere. Not one, but two
    computer screens running advanced simulations within the
    simulation. And in the distance, a beautiful collection of
    colorful stars and galaxies.

    The next morning, the computer greeted me with a strange trumpet
    sound. There were odd little boxes on a brick background, and the
    games launcher was gone. My father leaned over my shoulder,
    clicked around until he found something called "Starfield
    Simulation", and clicked a button called "Test". The screen went
    black, and little white dots came drifting out of nowhere.

    "See?" he said.

    I waited for the ship. I moved the mouse to find the controls, but
    the stars vanished and the boxes came back. My father clicked
    "Test" again.

    "Stay absolutely still," he said. "If you don't move, the stars
    will keep appearing. Every star you see is a discarded bit of
    memory. They need to be cleaned up, you see?"

    I cried. Losing my games was the worst thing that could happen to
    nine-year-old me. My father, meanwhile, thought the whole thing
    was hilarious. He opened AUTOEXEC.BAT and added this:

        echo Turn the computer off and go outside to play!
        pause
        win

    Don't worry, the games menu came back soon enough, with an added
    game called "Windows". But I never forgot that night of lying
    awake, waiting for my spaceship. And I promised myself that one
    day, I would build the greatest games launcher ever, with a title
    screen that shows a real cockpit, illuminated buttons, and all the
    colorful stars I had dreamed of.

    This class is that title screen.
    """

    RESOLUTION = 320, 200
    BAR = pg.Rect(102, 171, 116, 8)

    def __init__(self) -> None:
        """Load the title screen and draw the progress bar gradient."""
        self.canvas = pg.Surface(self.RESOLUTION)
        self.title = pg.image.load(Path(__file__).parent.parent / "title.png")
        self.gradient = gradient(self.BAR.size, MAGENTA, CYAN)
        super().__init__()

    def draw_progress(self, screen: pg.Surface, fraction: float) -> None:
        """Draw the title screen with the progress bar filled up to fraction."""
        canvas = self.canvas
        canvas.blit(self.title, (0, 0))
        progress = self.gradient.get_rect()
        progress.width = int(progress.width * fraction)
        canvas.blit(self.gradient, self.BAR, progress)
        screen.fill(BLACK)
        target = letterbox(screen.get_rect())
        screen.blit(sharp_scale(canvas, target.size), target)


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
        """Restart the blink timer."""
        self.blink(restart=True)
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
        if game.emulator is not None and game.emulator.is_alive():
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
        from .download import Download  # noqa: PLC0415

        Download(game).run(self.screen)

    @override
    def get_events(self) -> list[pg.event.Event]:
        """Sleep until the next event."""
        return [pg.event.wait()]

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Handle mouse and keyboard input."""
        next_scene = None
        if event.type == BLINK:
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
        image = self.message_font.render(self.message, ANTIALIAS, BLACK)
        rect = image.get_rect(center=screen.get_rect().center)
        screen.fill(MAGENTA, rect.inflate(2 * padding[0], 2 * padding[1]))
        screen.blit(image, rect)
