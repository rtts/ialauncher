"""Starfield Simulation running as a 16-bit executable in DOSBox."""

import subprocess
from pathlib import Path
from typing import override

from ialauncher.emulator import (
    NO_WINDOW,
    EmulatorError,
    get_dosbox_command,
    get_dosbox_options,
)
from ialauncher.engine import NextScene

from . import Blackout, Scene


class Stars(Blackout):
    """A black screen behind STARS.EXE."""

    dosbox: subprocess.Popen[bytes]

    def __init__(self, then: Scene) -> None:
        """Prepare to run stars.exe."""
        super().__init__()
        self.then = then

    @override
    def start(self) -> NextScene:
        """Start stars.exe, or return if DOSBox can't be found."""
        try:
            dosbox = get_dosbox_command()
        except EmulatorError:
            return self.then
        command = [*dosbox, "stars.exe", *get_dosbox_options(), "-exit"]
        self.dosbox = subprocess.Popen(  # noqa: S603
            command, cwd=Path(__file__).parent, creationflags=NO_WINDOW
        )
        return None

    @override
    def update(self) -> NextScene:
        """Stay black, and return to the previous scene once stars.exe exits."""
        super().update()
        return None if self.dosbox.poll() is None else self.then
