"""Find the DOSBox executable."""

import os
import subprocess
from collections.abc import Iterable, Iterator
from pathlib import Path

DOSBOX_NOT_FOUND = """

Uh-oh! The program DOSBox could not be found on your system. IA Launcher
acts as a frontend for DOSBox: when you select a game, it starts DOSBox
with the right arguments to play that game.

Please visit https://www.dosbox.com/ to learn more about DOSBox and
download the correct installer for your operating system.

"""


class DOSBoxNotFoundError(Exception):
    """DOSBox is not installed."""


def works(command: list[str]) -> bool:
    """Return whether the command can be executed."""
    try:
        subprocess.run(  # noqa: S603 - the candidates are hardcoded
            [*command, "--version"], capture_output=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def find_command(candidates: Iterable[list[str]]) -> list[str] | None:
    """Return the first candidate command that works, or None."""
    return next((command for command in candidates if works(command)), None)


def windows_candidates(pattern: str) -> Iterator[list[str]]:
    """Yield the executables in Program Files that match the pattern."""
    for var in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        if program_files := os.environ.get(var):
            for path in Path(program_files).glob(pattern):
                yield [str(path)]


def get_dosbox_path() -> list[str]:
    """Return the command that runs DOSBox on this system."""
    command = find_command(
        [
            ["dosbox"],
            # Proper way to do it on macOS
            ["open", "-a", "DOSBox", "--args"],
            # Fallback to hardcoded path on macOS
            ["/Applications/dosbox.app/Contents/MacOS/DOSBox"],
            # Special case for Windows
            *windows_candidates("dosbox*/dosbox.exe"),
        ]
    )
    if command is None:
        raise DOSBoxNotFoundError(DOSBOX_NOT_FOUND)
    return command
