"""The scenes of IA Launcher.

Scene transitions:

- Loading > Hero
- Loading > escape > quit
- Hero > enter > CRT > Download > Unzip > Play > CRT > Hero
- Hero > ctrl-enter > Download > Unzip > Hero
- Hero > space/ADVANCE > CRT > Unzip > Autoplay > CRT > Hero
- Hero > space/ADVANCE > CRT > CRT > Hero
- Hero > CRT > Unzip > Autoplay > Starfield/Stars
- Hero > IDLE > Starfield/Stars
- Hero > minus > Grid
- Hero > METADATA > Hero
- Hero > escape > quit
- Grid > click > Download > Unzip > Play > Grid
- Grid > ctrl-click > Download > Unzip > Grid
- Grid > space > Hero
- Grid > escape/plus/METADATA > Hero
- Grid > zoom > Intro > Snake > Grid
- Grid > IDLE > Starfield/Stars
- Starfield > collision > Hero
- Starfield > escape > Hero/Grid
- Stars > exit > Hero
- Stars > Starfield
- Any > close > quit
"""

from pathlib import Path
from typing import override

import pygame as pg

from ialauncher import engine
from ialauncher.cheats import cheat
from ialauncher.engine import NextScene
from ialauncher.gamelist import LOADING_FAILED
from ialauncher.utils import gradient, letterbox, sharp_scale, show_error

CYAN = (0, 204, 255)
MAGENTA = (255, 0, 204)
BLACK = (0, 0, 0)
GRID_LARGER = {pg.K_MINUS, pg.K_KP_MINUS}
GRID_SMALLER = {pg.K_PLUS, pg.K_EQUALS, pg.K_KP_PLUS}
CHECK_INTERVAL = 100  # milliseconds
FONT_FAMILY = "dejavusans,liberationsans,arial,helvetica,sans"


class Scene(engine.Scene):
    """Base class for the scenes of IA Launcher."""

    def draw(self) -> None:
        """Draw the scene on a black screen, for CRT to switch on with."""

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

    def draw_progress(self, fraction: float) -> None:
        """Draw the title screen with the progress bar filled up to fraction."""
        canvas = self.canvas
        canvas.blit(self.title, (0, 0))
        progress = self.gradient.get_rect()
        progress.width = int(progress.width * fraction)
        canvas.blit(self.gradient, self.BAR, progress)
        self.screen.fill(BLACK)
        target = letterbox(self.screen.get_rect())
        self.screen.blit(sharp_scale(canvas, target.size), target)


class Blackout(Scene):
    """A black screen behind DOSBox."""

    @override
    def update(self) -> NextScene:
        """Stay black."""
        self.screen.fill(BLACK)
        return None

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Ignore everything."""
        return None

    @override
    def get_events(self) -> list[pg.event.Event]:
        """Wait until it's time to check on DOSBox again."""
        return [pg.event.wait(CHECK_INTERVAL)]


# Close your eyes!
from . import hero  # noqa: E402, F401
