"""Unzip a downloaded game without showing anything."""

from typing import override

import pygame as pg

from ialauncher.engine import NextScene
from ialauncher.game import Game
from ialauncher.game import Unzip as UnzipThread
from ialauncher.utils import show_error

from . import CHECK_INTERVAL, Scene


class Unzip(Scene):
    """Unzip the game if needed, and continue with the next scene.

    Meanwhile, keep showing whatever was shown before.
    """

    def __init__(self, game: Game, then: Scene) -> None:
        """Prepare to unzip the game."""
        super().__init__()
        self.game = game
        self.then = then
        self.thread: UnzipThread | None = None

    @override
    def update(self) -> NextScene:
        """Start unzipping, and continue when it's done or not needed."""
        if self.thread is None:
            if self.game.is_ready() or not self.game.is_downloaded():
                return self.then
            self.thread = self.game.unzip()
        if self.thread.is_alive():
            return None
        if self.thread.error:
            show_error(self.thread.error)
        return self.then

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Continue on Escape, while the game unzips anyway."""
        if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
            return self.then
        return None

    @override
    def get_events(self) -> list[pg.event.Event]:
        """Wait until it's time to check on the thread again."""
        return [pg.event.wait(CHECK_INTERVAL)]
