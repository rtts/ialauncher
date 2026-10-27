"""Title screen with progress bar while games are downloading."""

from typing import override

import pygame as pg

from ialauncher.engine import NextScene
from ialauncher.game import Game
from ialauncher.utils import show_error

from . import BLACK, TitleScreen


class Download(TitleScreen):
    """Title screen with progress bar while games are downloading."""

    def __init__(self, game: Game, *, black: bool = False) -> None:
        """Start downloading the game, on a black screen if black."""
        self.game = game
        self.black = black
        super().__init__()

        # Start downloading (spawns a new thread)
        self.game.download()

    @override
    def run(self, screen: pg.Surface) -> NextScene:
        """Cancel the download when the scene exits before it's finished.

        The same note applies as in Loading.run(): This waits for the download
        thread to terminate by calling Thread.join(). If the network
        is stalled, that can take up to 60 seconds, and the window is
        frozen until then.
        """
        try:
            return super().run(screen)
        finally:
            if thread := self.game.download_thread:
                thread.cancel()

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Cancel on Escape."""
        if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
            return False
        return None

    @override
    def update(self, screen: pg.Surface) -> NextScene:
        """Draw the progress bar or black, or show the error if the download failed."""
        thread = self.game.download_thread
        if thread is None or not thread.is_alive():
            if thread is not None and thread.error:
                show_error(thread.error)
            return False
        if self.black:
            screen.fill(BLACK)
        else:
            self.draw_progress(screen, thread.progress)
        return None
