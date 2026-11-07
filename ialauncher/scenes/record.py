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
        playing = self.end_at is None
        next_scene = super().update()
        if playing and self.end_at is not None:  # It just exited
            self.game.autoplay = round(monotonic() - self.started)
            self.game.save_metadata("autoplay", str(self.game.autoplay))
        return next_scene
