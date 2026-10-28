"""Title screen with progress bar while games are downloading."""

from typing import override

import pygame as pg

from ialauncher.engine import NextScene
from ialauncher.game import Game
from ialauncher.utils import show_error

from . import Scene, TitleScreen


class Download(TitleScreen):
    """Download the game if needed, and continue with the next scene."""

    def __init__(self, game: Game, then: Scene) -> None:
        """Prepare to download the game."""
        self.game = game
        self.then = then
        super().__init__()

    @override
    def start(self) -> NextScene:
        """Start downloading, unless the game already is downloaded."""
        if self.game.is_downloaded():
            return self.then
        self.game.download()  # Spawns a new thread
        return None

    @override
    def update(self) -> NextScene:
        """Draw the progress bar, or show the error if the download failed."""
        thread = self.game.download_thread
        if thread is None or not thread.is_alive():
            if thread is not None and thread.error:
                show_error(thread.error)
            return self.then
        self.draw_progress(thread.progress)
        return None

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Cancel on Escape."""
        if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
            return self.then
        return None

    @override
    def stop(self) -> None:
        """Cancel the download if it's not finished.

        The same note applies as in Loading.stop(): This waits for the
        download thread to terminate by calling Thread.join(). If the
        network is stalled, that can take up to 60 seconds, and the
        window is frozen until then.
        """
        if thread := self.game.download_thread:
            thread.cancel()
