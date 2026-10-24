"""Starfield Simulation."""

import random
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, override

import pygame as pg

from ialauncher import options
from ialauncher.emulator import (
    NO_WINDOW,
    EmulatorError,
    get_dosbox_command,
    get_dosbox_options,
)
from ialauncher.engine import NextScene
from ialauncher.game import Emulator, Game
from ialauncher.gamelist import gamelist
from ialauncher.utils import sharp_scale

from . import BLACK, Scene, hero

FPS = 30
SPEED = 30  # seconds from z = 1 to z = 0
CHECK_INTERVAL = 100  # milliseconds

# How far stars travel on average before they leave the screen,
# assuming a triangular distribution of stars, is equal to
# the integral of 4z² - 4z³ + z⁴ from 0 to 1.
TRAVELLED = 8 / 15


@dataclass(slots=True)
class Star:
    """A star with a fixed x and y and a moving z."""

    x: float
    y: float
    z: float
    game: Game
    size: int
    image: pg.Surface


def start_dosbox(*, autorun: bool = True) -> subprocess.Popen[bytes] | None:
    """Start stars.exe or do nothing."""
    try:
        dosbox = get_dosbox_command()
    except EmulatorError:
        return None
    command = [*dosbox, "stars.exe" if autorun else "."]
    command += [*get_dosbox_options(), "--set", "cpu_cycles=100000"]
    if autorun:
        command.append("-exit")
    return subprocess.Popen(  # noqa: S603
        command, cwd=Path(__file__).parent, creationflags=NO_WINDOW
    )


class Starfield(Scene):
    """Starfield Simulation."""

    dosbox: ClassVar[subprocess.Popen[bytes] | None] = None

    def __init__(self, referrer: Scene) -> None:
        """Initialize."""
        super().__init__()
        self.referrer = referrer
        self.started = False
        self.stars: list[Star] = []
        self.dots: dict[Game, pg.Surface] = {}
        self.step = options.warp / (SPEED * FPS)
        # Filling at this rate prevents "waves" of stars.
        self.rate = options.density * self.step / TRAVELLED
        self.due = 0.0
        # Chance per frame of adding a star in the exact center.
        self.chance = 1 / (options.mtbc * FPS) if options.mtbc else 0

    def star(self, *, center: bool = False) -> Star:
        """Return a new star at depth z = 1, optionally in the exact center."""
        width, height = self.screen.get_size()
        game = random.choice(gamelist.games)  # noqa: S311
        if center:
            x = y = 0.0
        else:
            x, y = random.triangular(-width, width), random.triangular(-height, height)  # noqa: S311
        return Star(x / 2, y / 2, 1, game, size=1, image=self.image(game, 1))

    def image(self, game: Game, size: int) -> pg.Surface:
        """Return the game's title screen as a star of the given size."""
        if size == 1 and game.color is not None:
            if (dot := self.dots.get(game)) is None:
                dot = self.dots[game] = pg.Surface((1, 1))
                dot.fill(game.color)
            return dot
        thumbnail = game.get_titlescreen((size, size)) or pg.Surface((1, 1))
        return sharp_scale(thumbnail, (size, size))

    @override
    def get_events(self) -> list[pg.event.Event]:
        """Run at FPS frames per second."""
        self.clock.tick(FPS)
        return pg.event.get()

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Exit on Escape, start DOS version on Enter, add center star on Space."""
        if event.type != pg.KEYDOWN:
            return None
        if event.key in (pg.K_RETURN, pg.K_KP_ENTER):
            Starfield.dosbox = start_dosbox(autorun=not event.mod & pg.KMOD_ALT)
            return None
        if event.key == pg.K_SPACE:
            self.stars.append(self.star(center=True))
            return None
        return self.referrer if event.key == pg.K_ESCAPE else None

    @classmethod
    def dosbox_running(cls) -> bool:
        """Return whether DOSBox is still running."""
        return cls.dosbox is not None and cls.dosbox.poll() is None

    @override
    def run(self, screen: pg.Surface) -> NextScene:
        """Autoplay the current game, if it qualifies, then the screensaver."""
        if not self.started:
            self.started = True
            if not random.randrange(20) and (dosbox := start_dosbox()):  # noqa: S311
                Starfield.dosbox = dosbox
                return Stars()
            if game := self.autoplay_game():
                return Autoplay(game, self)
        return super().run(screen)

    def autoplay_game(self) -> Game | None:
        """Return whether the current game qualifies to autoplay."""
        if not options.autoplay or not isinstance(self.referrer, hero.Hero):
            return None
        game = gamelist.get_current_game()
        if game.engine != "dosbox" or not game.emulator_start:
            return None
        try:
            get_dosbox_command()
        except EmulatorError:
            return None
        return game if game.is_downloaded() else None

    @override
    def update(self, screen: pg.Surface) -> NextScene:
        """Fly through space."""
        screen.fill(BLACK)
        width, height = screen.get_size()
        center_x, center_y = screen.get_rect().center

        # Each star is a point in space, at a fixed x and y that put it
        # anywhere on the screen at depth z = 1, mostly near the center,
        # and moves toward the viewer at z = 0 by the same distance every
        # frame. Dividing x and y by z projects it onto the screen.
        new = 0
        stars = []
        blits = []
        for star in self.stars:
            star.z -= self.step
            if star.z <= 1 / height:
                if star.x == star.y == 0:
                    # Collision!
                    gamelist.current_game = gamelist.games.index(star.game)
                    return hero.Hero()
                new += 1
                continue
            scale = 1 / star.z
            if int(scale) != star.size:
                star.size = int(scale)
                star.image = self.image(star.game, star.size)
            left = center_x - star.size // 2 + star.x * scale
            top = center_y - star.size // 2 + star.y * scale
            if not (-star.size < left < width and -star.size < top < height):
                new += 1
                continue
            stars.append(star)
            blits.append((star.image, (left, top)))
        screen.fblits(blits)

        # Replace stars that left and add more until field is full.
        self.due += self.rate
        due = int(self.due)
        self.due -= due
        new = min(max(new, due), options.density - len(stars))
        self.stars = [self.star() for _ in range(new)] + stars

        if random.random() < self.chance:  # noqa: S311
            self.stars.append(self.star(center=True))
        return None


class Blackout(Scene):
    """A black screen behind DOSBox."""

    @override
    def get_events(self) -> list[pg.event.Event]:
        """Wait until it's time to check on DOSBox again."""
        return [pg.event.wait(CHECK_INTERVAL)]

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Ignore everything."""
        return None

    @override
    def update(self, screen: pg.Surface) -> NextScene:
        """Stay black."""
        screen.fill(BLACK)
        return None


class Stars(Blackout):
    """A black screen behind STARS.EXE."""

    @override
    def update(self, screen: pg.Surface) -> NextScene:
        """Show a random game once stars.exe has exited."""
        super().update(screen)
        if Starfield.dosbox_running():
            return None
        gamelist.random_game()
        return hero.Hero()


class Autoplay(Blackout):
    """A black screen behind an autoplaying game."""

    def __init__(self, game: Game, starfield: Starfield) -> None:
        """Unzip the game first, if needed."""
        super().__init__()
        self.game = game
        self.starfield = starfield
        self.emulator: Emulator | None = None
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
    def handle(self, event: pg.event.Event) -> NextScene:
        """Continue with the starfield on Escape."""
        if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
            return self.starfield
        return None

    @override
    def update(self, screen: pg.Surface) -> NextScene:
        """Start the game once it's unzipped, and continue when time is up."""
        super().update(screen)
        game = self.game
        if self.emulator is None:
            if self.unzipping and (thread := game.download_thread):
                if thread.is_alive():
                    return None
                self.unzipping = False
            if not game.is_ready():
                return self.starfield
            self.emulator = game.emulator = game.start()
            self.deadline = pg.time.get_ticks() + options.autoplay * 1000
            return None
        if self.emulator.is_alive() and pg.time.get_ticks() < self.deadline:
            return None
        return self.starfield
