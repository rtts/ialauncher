"""Starfield Simulation running as a 16-bit executable in DOSBox."""

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

import pygame as pg

from ialauncher.emulator import (
    NO_WINDOW,
    EmulatorError,
    get_dosbox_command,
    get_dosbox_options,
)
from ialauncher.engine import NextScene
from ialauncher.gamelist import gamelist

from . import Blackout

if TYPE_CHECKING:
    from .browse import Browse


class Stars(Blackout):
    """A black screen behind STARS.EXE."""

    dosbox: ClassVar[subprocess.Popen[bytes] | None] = None

    def __init__(self, referrer: "Browse") -> None:
        """Initialize."""
        super().__init__()
        self.referrer = referrer

    @classmethod
    def start(cls, referrer: "Browse") -> "Stars | None":
        """Start stars.exe and return a black screen, or None if it can't."""
        return cls(referrer) if cls.launch() else None

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

    @override
    def update(self, screen: pg.Surface) -> NextScene:
        """Wake up with a random game once stars.exe has exited."""
        super().update(screen)
        if self.is_running():
            return None
        gamelist.random_game()
        return self.referrer.wake()
