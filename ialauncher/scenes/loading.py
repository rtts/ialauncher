"""Title screen with progress bar while games are loading.

We could technically load all the games in a fraction of a second,
but where's the fun in that?

So we load 10 games per frame and uncap the framerate. This allows
the loading time to double as a benchmark.
"""

from pathlib import Path
from typing import TYPE_CHECKING, override

import pygame as pg

import games as gd
from ialauncher.engine import NextScene
from ialauncher.game import MetadataError
from ialauncher.gamelist import gamelist
from ialauncher.utils import show_error

from . import TitleScreen
from .hero import Hero

if TYPE_CHECKING:
    from ialauncher.game import Game


class Loading(TitleScreen):
    """Title screen with progress bar while games are loading."""

    def __init__(self, *, slurp: bool = False) -> None:
        """Find the directories of all games."""
        self.slurp = slurp
        self.games_dir = Path(gd.__file__).parent
        self.todo = [
            entry
            for entry in self.games_dir.iterdir()
            if (entry / "metadata.ini").exists()
        ]
        self.total = len(self.todo)
        self.downloading: Game | None = None
        super().__init__()

    @override
    def get_events(self) -> list[pg.event.Event]:
        """Uncap the frame rate."""
        return pg.event.get()

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Quit on Escape."""
        if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
            return False
        return None

    @override
    def run(self, screen: pg.Surface) -> NextScene:
        """Cancel the download in progress when the scene exits.

        This waits for the download thread to terminate by calling
        Thread.join(). If the network is stalled, that can take up to
        60 seconds, and the window is frozen until then.

        Using processes instead of threads would fix this, but they
        don't play nice on Windows.
        """
        try:
            return super().run(screen)
        finally:
            if self.downloading and (thread := self.downloading.download_thread):
                thread.cancel()

    def load_games(self, number_of_games: int) -> None:
        """Load the next N games."""
        while self.todo and number_of_games:
            path = self.todo.pop()
            gamelist.add(path)
            number_of_games -= 1

    def download_game(self) -> None:
        """Download the next game."""
        if self.downloading:
            thread = self.downloading.download_thread
            if thread is not None and thread.is_alive():
                return
            self.downloading = None
        if self.todo:
            path = self.todo.pop()
            gamelist.add(path)
            self.downloading = gamelist.games[-1]
            self.downloading.download(unzip=False)

    def done(self) -> NextScene:
        """Choose the next scene."""
        if self.slurp:
            return False
        if not gamelist.games:
            show_error(
                f"No games were found!\n\nThere are no games in {self.games_dir}"
            )
            return False
        gamelist.sort()
        return Hero(slideshow=True)

    @override
    def update(self, screen: pg.Surface) -> NextScene:
        """Load (or in slurp mode, download) games and draw the progress.

        Quit if a game has invalid metadata.
        """
        try:
            if self.slurp:
                # Loading doesn't cap the frame rate and the download
                # happens in a separate thread, so cap the framerate to
                # prevent 100% CPU.
                self.clock.tick(30)

                self.download_game()
            else:
                self.load_games(30)
        except MetadataError as e:
            show_error(str(e))
            return False
        if not self.todo and not self.downloading:
            return self.done()
        finished = self.total - len(self.todo) - bool(self.downloading)
        self.draw_progress(screen, finished / self.total)
        return None
