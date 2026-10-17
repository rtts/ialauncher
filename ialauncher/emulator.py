"""Find the locations of the supported emulators: DOSBox, and ScummVM."""

import os
import subprocess
from collections.abc import Iterable, Iterator
from functools import cache
from pathlib import Path


class EmulatorError(Exception):
    """The emulator is not installed."""


def works(command: list[str]) -> bool:
    """Return whether the command can be executed."""
    try:
        subprocess.run(  # noqa: S603
            [*command, "--version"], capture_output=True, check=True, timeout=3
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
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


@cache
def get_dosbox_command() -> list[str]:
    """Return the command that runs DOSBox."""
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
        msg = """
This game needs DOSBox to play, but DOSBox could not be
found on your system.

Please visit https://www.dosbox.com/ to learn more about
DOSBox and to download the correct installer for your
operating system.

Alternatively, if you installed DOSBox in a non-standard
location, set the PATH environment variable to point to the
DOSBox directory.
        """
        raise EmulatorError(msg)
    return command


@cache
def get_scummvm_command() -> list[str]:
    """Return the command that runs ScummVM."""
    command = find_command(
        [
            ["scummvm"],
            # Hardcoded path on macOS
            ["/Applications/ScummVM.app/Contents/MacOS/scummvm"],
            # Special case for Windows
            *windows_candidates("scummvm*/scummvm.exe"),
        ]
    )
    if command is None:
        msg = """
This game needs ScummVM to play, but ScummVM could not be
found on your system.

Please visit https://www.scummvm.org/ to learn more about
ScummVM and to download the correct installer for your
operating system.

Alternatively, if you installed ScummVM in a non-standard
location, set the PATH environment variable to point to the
ScummVM directory.
        """
        raise EmulatorError(msg)
    return command
