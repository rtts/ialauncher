"""Find the ScummVM executable."""

from functools import cache

from .dosbox import find_command, windows_candidates

SCUMMVM_NOT_FOUND = """

Uh-oh! The program ScummVM could not be found on your system. Some games
in IA Launcher are played with ScummVM instead of DOSBox.

Please visit https://www.scummvm.org/ to learn more about ScummVM and
download the correct installer for your operating system.

"""


class ScummVMNotFoundError(Exception):
    """ScummVM is not installed."""


@cache
def get_scummvm_path() -> list[str]:
    """Return the command that runs ScummVM on this system."""
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
        raise ScummVMNotFoundError(SCUMMVM_NOT_FOUND)
    return command
