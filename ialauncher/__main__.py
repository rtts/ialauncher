"""Command-line entry point of IA Launcher."""

import argparse
import io
import sys
from pathlib import Path

import games

from . import options
from .emulator import has_opengl
from .engine import run
from .game import Game, write_metadata_cache
from .gamelist import gamelist
from .scenes.loading import Loading


def main() -> None:
    """Parse the command-line arguments and start IA Launcher."""
    # Print what the console's encoding can't show as "?" instead of crashing
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(
        description="DOSBox frontend for the Internet Archive MS-DOS games collection"
    )
    parser.add_argument(
        "--slideshow",
        type=int,
        metavar="X",
        help="Advance the slideshow every X seconds (default 10, 0 to disable)",
    )
    parser.add_argument(
        "--idle",
        type=int,
        metavar="X",
        help="Start the screensaver after X seconds (default 60, 0 to disable)",
    )
    parser.add_argument(
        "--warp",
        type=float,
        help="Warp speed (default 1.0)",
    )
    parser.add_argument(
        "--density",
        type=int,
        help="Density (default 10000)",
    )
    parser.add_argument(
        "--fullscreen",
        action=argparse.BooleanOptionalAction,
        help="Start in fullscreen mode (default) or in a window",
    )
    parser.add_argument(
        "--dosbox",
        metavar="PATH",
        help="Run DOSBox from PATH instead of looking for it",
    )
    parser.add_argument(
        "--scummvm",
        metavar="PATH",
        help="Run ScummVM from PATH instead of looking for it",
    )
    parser.add_argument(
        "--slurp",
        dest="slurp",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--build-cache",
        action="store_true",
        help="Build metadata cache (for faster startup!)",
    )
    args = parser.parse_args()

    if args.build_cache:
        games_dir = Path(games.__file__).parent
        cache = {
            path.name: dict(Game(path).config["metadata"])
            for path in games_dir.iterdir()
            if (path / "metadata.ini").exists()
        }
        write_metadata_cache(games_dir, cache)
        print("Done!")
        return

    if args.fullscreen is not None:
        options.fullscreen = args.fullscreen
    if args.slideshow is not None:
        options.slideshow = args.slideshow
    if args.idle is not None:
        options.idle = args.idle
    if args.warp is not None:
        options.warp = max(1, args.warp)
    if args.density is not None:
        options.density = max(0, args.density)
    if args.dosbox is not None:
        options.dosbox_executable = args.dosbox
    if args.scummvm is not None:
        options.scummvm_executable = args.scummvm

    has_opengl()
    try:
        run(
            Loading(slurp=args.slurp),
            title="IA Launcher",
            fullscreen=options.fullscreen,
        )
    finally:
        gamelist.stop_loading()


if __name__ == "__main__":
    main()
