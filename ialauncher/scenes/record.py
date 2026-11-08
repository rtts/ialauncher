"""Play the game, and record how long it ran as its autoplay seconds."""

from time import monotonic
from typing import override

from ialauncher.engine import NextScene

from .play import Play


class Record(Play):
    """Play the game, and when it exits, save autoplay = n to metadata.ini."""

    @override
    def update(self) -> NextScene:
        """Start the clock with the game, and save the time when it exits."""
        if self.emulator is None:
            self.started = monotonic()
        next_scene = super().update()
        if next_scene is self.then and self.emulator is not None:
            self.game.autoplay = round(monotonic() - self.started)
            self.game.save_metadata("autoplay", str(self.game.autoplay))
        return next_scene
