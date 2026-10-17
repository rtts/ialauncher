"""Find the locations of the supported emulators: DOSBox, and ScummVM."""

import os
import subprocess
import sys
from collections.abc import Iterable, Iterator
from functools import cache
from pathlib import Path


class EmulatorError(Exception):
    """The emulator is not installed."""


@cache
def get_dosbox_command() -> list[str]:
    """Return the command that runs DOSBox."""
    return get_command(
        "DOSBox",
        "https://www.dosbox.com/",
        [
            ["dosbox"],
            *macos_candidates(["open", "-a", "DOSBox", "--args"]),
            ["/Applications/dosbox.app/Contents/MacOS/DOSBox"],
            *windows_candidates("dosbox*/dosbox.exe"),
        ],
    )


@cache
def get_scummvm_command() -> list[str]:
    """Return the command that runs ScummVM."""
    return get_command(
        "ScummVM",
        "https://www.scummvm.org/",
        [
            ["scummvm"],
            ["/Applications/ScummVM.app/Contents/MacOS/scummvm"],
            *windows_candidates("scummvm*/scummvm.exe"),
        ],
    )


def windows_candidates(pattern: str) -> Iterator[list[str]]:
    """Yield the executables in Program Files that match the pattern."""
    for var in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        if program_files := os.environ.get(var):
            for path in Path(program_files).glob(pattern):
                yield [str(path)]


def macos_candidates(command: list[str]) -> Iterator[list[str]]:
    """Yield the command on macOS only.

    Elsewhere, `open` is often xdg-open, which succeeds with any
    arguments as long as one of them is --version.
    """
    if sys.platform == "darwin":
        yield command


def get_command(name: str, url: str, candidates: Iterable[list[str]]) -> list[str]:
    """Return the first candidate command that works, or raise EmulatorError."""
    command = find_command(candidates)
    if command is None:
        msg = f"""
This game needs {name} to play, but {name} could not be
found on your system.

Please visit {url} to learn more about
{name} and to download the correct installer for your
operating system.

Alternatively, if you installed {name} in a non-standard
location, set the PATH environment variable to point to the
{name} directory.
        """
        raise EmulatorError(msg)
    return command


def find_command(candidates: Iterable[list[str]]) -> list[str] | None:
    """Return the first candidate command that works, or None."""
    return next((command for command in candidates if works(command)), None)


def works(command: list[str]) -> bool:
    """Return whether the command can be executed."""
    try:
        subprocess.run(  # noqa: S603
            [*command, "--version"], capture_output=True, check=True, timeout=3
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    return True
