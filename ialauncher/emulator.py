"""Find the locations of the supported emulators: DOSBox, and ScummVM."""

import ctypes
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterable, Iterator
from functools import cache
from pathlib import Path

import pygame as pg

from . import options

# Only on Windows, NO_WINDOW will have a non-zero value.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
MINIMUM_OPENGL = 3, 3
GL_VERSION = 0x1F02


class EmulatorError(Exception):
    """The emulator is not installed."""


@cache
def get_dosbox_command() -> list[str]:
    """Return the command that runs DOSBox."""
    if options.dosbox_executable:
        return get_executable("DOSBox", options.dosbox_executable)
    return get_command(
        "DOSBox",
        "https://www.dosbox.com/",
        [
            *bundled_candidates(),
            ["dosbox"],
            *macos_candidates(["open", "-a", "DOSBox", "--args"]),
            ["/Applications/dosbox.app/Contents/MacOS/DOSBox"],
            *windows_candidates("dosbox*/dosbox.exe"),
        ],
    )


@cache
def get_scummvm_command() -> list[str]:
    """Return the command that runs ScummVM."""
    if options.scummvm_executable:
        return get_executable("ScummVM", options.scummvm_executable)
    return get_command(
        "ScummVM",
        "https://www.scummvm.org/",
        [
            ["scummvm"],
            ["/Applications/ScummVM.app/Contents/MacOS/scummvm"],
            *windows_candidates("scummvm*/scummvm.exe"),
        ],
    )


@cache
def is_dosbox_staging() -> bool:
    """Return whether DOSBox is DOSBox Staging, or False if it isn't installed."""
    try:
        result = subprocess.run(  # noqa: S603
            [*get_dosbox_command(), "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
            creationflags=NO_WINDOW,
        )
    except (EmulatorError, OSError, subprocess.TimeoutExpired):
        return False
    return result.stdout.startswith("dosbox-staging")


def bundled_candidates() -> Iterator[list[str]]:
    """Yield the DOSBox Staging that ships with the Windows installer."""
    if getattr(sys, "frozen", False):
        yield [str(Path(sys.executable).parent / "dosbox-staging" / "dosbox.exe")]


@cache
def has_opengl() -> bool:
    """Check whether this system has OpenGL 3.3.

    This is for extreme backwards compatibility, only.
    """
    if sys.platform != "win32":
        return True
    pg.display.init()
    try:
        pg.display.set_mode((1, 1), pg.OPENGL | pg.HIDDEN)
        # SDL quietly falls back to 1.1, so ask the context instead.
        get_string = ctypes.windll.opengl32.glGetString
        get_string.restype = ctypes.c_char_p
        version = get_string(GL_VERSION) or b""
    except (pg.error, OSError):
        return False
    finally:
        pg.display.quit()
    if match := re.match(rb"(\d+)\.(\d+)", version):
        return (int(match[1]), int(match[2])) >= MINIMUM_OPENGL
    return False


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


def get_executable(name: str, path: str) -> list[str]:
    """Return the command for the executable given on the command line.

    A file at the path wins over a command of that name on the PATH. It's
    made absolute, because emulators run in the game directory. Raise
    EmulatorError if the executable doesn't work.
    """
    file = Path(path) if Path(path).is_file() else Path(shutil.which(path) or path)
    command = [str(file.absolute())]
    if not works(command):
        option = f"--{name.lower()}"
        msg = f"""
This game needs {name} to play, but {path},
given with {option}, could not be run.
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
            [*command, "--version"],
            capture_output=True,
            check=True,
            timeout=3,
            creationflags=NO_WINDOW,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    return True
