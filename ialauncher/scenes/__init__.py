"""The scenes of IA Launcher.

It starts with Loading, which hands over to Browse, which hands over
to Download.
"""

from pathlib import Path
from typing import override

import pygame as pg

from ialauncher import engine
from ialauncher.cheats import cheat
from ialauncher.utils import gradient, letterbox

CYAN = (0, 204, 255)
MAGENTA = (255, 0, 204)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
ANTIALIAS = True


class Scene(engine.Scene):
    """Base class for the scenes of IA Launcher."""

    @override
    def intercept(self, event: pg.event.Event) -> bool:
        """Intercept keystrokes to check for cheats."""
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
    BAR = pg.Rect(101, 170, 116, 9)

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
        target = screen.subsurface(letterbox(screen.get_rect()))
        pg.transform.scale(canvas, target.get_size(), target)
