"""Starfield Simulation running as a 16-bit executable in DOSBox."""

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from ialauncher.emulator import (
    NO_WINDOW,
    EmulatorError,
    get_dosbox_command,
    get_dosbox_options,
)
from ialauncher.engine import NextScene
from ialauncher.gamelist import gamelist

from . import Blackout, hero, starfield

if TYPE_CHECKING:
    from .browse import Browse


class Stars(Blackout):
    """A black screen behind STARS.EXE."""

    dosbox: ClassVar[subprocess.Popen[bytes] | None] = None

    def __init__(self, referrer: "Browse") -> None:
        """Initialize."""
        super().__init__()
        self.referrer = referrer

    @override
    def start(self) -> NextScene:
        """Start stars.exe, or fall back to the starfield if it can't."""
        if not Stars.launch():
            return starfield.Starfield(self.referrer)
        return None

    @override
    def update(self) -> NextScene:
        """Continue with Hero, on a random autoplayable game, once stars.exe exits."""
        super().update()
        if self.is_running():
            return None
        gamelist.random_game()
        return hero.Hero(screensaver=True)

    @classmethod
    def launch(cls, *, autorun: bool = True) -> bool:
        """Start stars.exe, or do nothing. Return whether it started."""
        try:
            dosbox = get_dosbox_command()
        except EmulatorError:
            return False
        command = [*dosbox, "stars.exe" if autorun else ".", *get_dosbox_options()]
        if autorun:
            command.append("-exit")
        cls.dosbox = subprocess.Popen(  # noqa: S603
            command, cwd=Path(__file__).parent, creationflags=NO_WINDOW
        )
        return True

    @classmethod
    def is_running(cls) -> bool:
        """Return whether stars.exe is still running."""
        return cls.dosbox is not None and cls.dosbox.poll() is None
