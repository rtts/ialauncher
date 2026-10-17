"""Find the ScummVM executable."""

from functools import cache

from .dosbox import EmulatorError, find_command, windows_candidates


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
