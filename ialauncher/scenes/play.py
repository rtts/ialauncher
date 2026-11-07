"""The boring scene in the background while you are playing a game."""

from typing import override

import pygame as pg

from ialauncher import ega
from ialauncher.emulator import EmulatorError, get_dosbox_command
from ialauncher.engine import NextScene
from ialauncher.game import EMULATOR_FAILED, Emulator, Game
from ialauncher.utils import show_error

from . import BLACK, WHITE, Blackout, Scene

DELAY = 3


class Play(Blackout):
    """Start the game, and continue with the next scene when it exits.

    When started from the grid with wait=False, continue immediately
    so the grid will be shown while you're playing.
    """

    delay = 0

    def __init__(
        self,
        game: Game,
        then: Scene,
        *,
        autorun: bool = True,
        wait: bool = True,
    ) -> None:
        """Prepare to play the game."""
        super().__init__()
        self.game = game
        self.then = then
        self.autorun = autorun
        self.wait = wait
        self.emulator: Emulator | None = None
        self.message = f"NOW PLAYING: {game.title.upper()}"
        self.message_at = 0
        self.end_at: int | None = None

    @override
    def start(self) -> NextScene:
        """Show the message after a while, when DOSBox has started up."""
        self.message_at = pg.time.get_ticks() + DELAY * 1000
        return super().start()

    @override
    def update(self) -> NextScene:
        """Start the game if it's ready, and continue a while after it exits.

        The error, if any, is posted just before the game exits, so
        handle it now, before changing scenes clears it.
        """
        if self.emulator is None:
            if not self.game.is_ready():  # Downloading or unzipping failed
                return self.then
            self.emulator = self.game.emulator = self.game.start(autorun=self.autorun)
            if not self.wait:
                return self.then
        super().update()
        now = pg.time.get_ticks()
        if self.emulator.is_alive():
            if now >= self.message_at and not self.emulator.stopped:
                image = ega.render(self.message, WHITE, BLACK, (8, 4))
                center = self.screen.get_rect().center
                self.screen.blit(image, image.get_rect(center=center))
            return None
        if self.end_at is None:
            for event in pg.event.get(EMULATOR_FAILED):
                self.handle(event)
            now = pg.time.get_ticks()  # The error may have taken a while
            self.end_at = now + self.delay * 1000
        return self.then if now >= self.end_at else None

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Show the error when the game exits suspiciously quickly."""
        if event.type == EMULATOR_FAILED:
            show_error(event.message)
        return None


class Autoplay(Play):
    """Play the game for its autoplay seconds, and continue with the next scene.

    Continue right away if the game doesn't qualify.
    """

    delay = DELAY

    def __init__(self, game: Game, then: Scene) -> None:
        """Prepare to play the game."""
        super().__init__(game, then)
        self.deadline = 0

    @override
    def update(self) -> NextScene:
        """Stop the game when time is up."""
        if self.emulator is None:
            if not self.qualifies(self.game):
                return self.then
            self.deadline = pg.time.get_ticks() + self.game.autoplay * 1000
        elif (
            self.emulator.is_alive()
            and not self.emulator.stopped
            and pg.time.get_ticks() >= self.deadline
        ):
            self.emulator.stop()
        return super().update()

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Ignore everything, including errors: the show just continues."""
        return None

    @staticmethod
    def qualifies(game: Game) -> bool:
        """Return whether the game qualifies to autoplay."""
        if not game.autoplay:
            return False
        if game.engine != "dosbox" or not game.emulator_start:
            return False
        try:
            get_dosbox_command()
        except EmulatorError:
            return False
        return game.is_downloaded()
