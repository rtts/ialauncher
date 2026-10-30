"""The boring scene in the background while you are playing a game."""

from typing import override

import pygame as pg

from ialauncher import options
from ialauncher.emulator import EmulatorError, get_dosbox_command
from ialauncher.engine import NextScene
from ialauncher.game import EMULATOR_FAILED, Emulator, Game
from ialauncher.utils import show_error

from . import Blackout, Scene


class Play(Blackout):
    """Start the game, and continue with the next scene when it exits.

    When started from the grid with wait=False, continue immediately
    so the grid will be shown while you're playing.
    """

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

    @override
    def update(self) -> NextScene:
        """Start the game if it's ready, and continue when it exits.

        The error, if any, is posted just before the game exits, so show
        it now, before changing scenes clears it.
        """
        if self.emulator is None:
            if not self.game.is_ready():  # Downloading or unzipping failed
                return self.then
            self.emulator = self.game.emulator = self.game.start(autorun=self.autorun)
            if not self.wait:
                return self.then
        if self.emulator.is_alive():
            return super().update()
        for event in pg.event.get(EMULATOR_FAILED):
            show_error(event.message)
        return self.then

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Show the error when the game exits suspiciously quickly."""
        if event.type == EMULATOR_FAILED:
            show_error(event.message)
        return None


class Autoplay(Play):
    """Play the game for a while, and continue with the next scene.

    Continue right away if the game doesn't qualify.
    """

    def __init__(self, game: Game, then: Scene) -> None:
        """Prepare to play the game."""
        super().__init__(game, then)
        self.deadline = 0

    @override
    def update(self) -> NextScene:
        """Continue when time is up, or when the game exits."""
        if self.emulator is None:
            if not self.qualifies(self.game):
                return self.then
            self.deadline = pg.time.get_ticks() + options.autoplay * 1000
        elif pg.time.get_ticks() >= self.deadline or not self.emulator.is_alive():
            self.emulator.stop()
            return self.then
        return super().update()

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Ignore everything, including errors: the show just continues."""
        return None

    @staticmethod
    def qualifies(game: Game) -> bool:
        """Return whether the game qualifies to autoplay."""
        if not options.autoplay:
            return False
        if not game.autoplayable or game.engine != "dosbox" or not game.emulator_start:
            return False
        try:
            get_dosbox_command()
        except EmulatorError:
            return False
        return game.is_downloaded()
